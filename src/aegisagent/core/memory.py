from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.security.redaction import redact_text


MEMORY_NOTE_TARGETS = {
    "workspace": "MEMORY.md",
    "user": "USER.md",
}


class MemoryStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self._init_db()

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            conn.execute("create table if not exists memory (id integer primary key, kind text, title text, body text)")
            try:
                conn.execute("create virtual table if not exists memory_fts using fts5(title, body, content='memory', content_rowid='id')")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def index_curated_files(self) -> int:
        count = 0
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            conn.execute("delete from memory where kind = 'curated'")
            for file in sorted(self.paths.memory_dir.glob("*.md")):
                body = file.read_text(encoding="utf-8")
                conn.execute("insert into memory(kind, title, body) values (?, ?, ?)", ("curated", file.name, body))
                count += 1
            try:
                conn.execute("insert into memory_fts(memory_fts) values ('rebuild')")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        return count

    def add_session_note(self, title: str, body: str) -> int:
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            cursor = conn.execute("insert into memory(kind, title, body) values (?, ?, ?)", ("session", title, body))
            rowid = int(cursor.lastrowid)
            try:
                conn.execute("insert into memory_fts(rowid, title, body) values (?, ?, ?)", (rowid, title, body))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return rowid

    def add_curated_note(self, kind: str, title: str, body: str, *, approved: bool = False) -> dict[str, Any]:
        clean_kind = kind.strip().lower() or "workspace"
        clean_title = " ".join(title.strip().split())
        clean_body = body.strip()
        target_name = MEMORY_NOTE_TARGETS.get(clean_kind, "")
        metadata: dict[str, Any] = {
            "operation": "add",
            "kind": clean_kind,
            "approved": approved,
            "memory_write_performed": False,
            "workspace_mutation_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
        }
        if not target_name:
            return {
                "operation": "add",
                "kind": clean_kind,
                "status": "blocked",
                "error": "memory kind must be workspace or user",
                "metadata": {**metadata, "blocked": True},
            }
        metadata["target"] = target_name
        if not clean_title or not clean_body:
            return {
                "operation": "add",
                "kind": clean_kind,
                "target": target_name,
                "status": "blocked",
                "error": "title and body are required",
                "metadata": {**metadata, "blocked": True},
            }
        if len(clean_title) > 120 or len(clean_body) > 4000:
            return {
                "operation": "add",
                "kind": clean_kind,
                "target": target_name,
                "status": "blocked",
                "error": "title must be 120 characters or fewer and body must be 4000 characters or fewer",
                "metadata": {**metadata, "blocked": True},
            }
        redacted_title = redact_text(clean_title)
        redacted_body = redact_text(clean_body)
        metadata["redacted"] = redacted_title.redacted or redacted_body.redacted
        if not approved:
            return {
                "operation": "add",
                "kind": clean_kind,
                "target": target_name,
                "title": redacted_title.text,
                "status": "needs_approval",
                "next": "rerun with explicit approval to append this note to curated memory",
                "metadata": metadata,
            }
        target = self.paths.memory_dir / target_name
        note = f"\n## {redacted_title.text}\n\n{redacted_body.text}\n"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(note)
        rowid = self._insert_memory(f"{clean_kind}_note", redacted_title.text, redacted_body.text)
        metadata.update(
            {
                "memory_write_performed": True,
                "workspace_mutation_performed": True,
                "rowid": rowid,
            }
        )
        return {
            "operation": "add",
            "kind": clean_kind,
            "target": target_name,
            "title": redacted_title.text,
            "rowid": rowid,
            "status": "ok",
            "metadata": metadata,
        }

    def _insert_memory(self, kind: str, title: str, body: str) -> int:
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            cursor = conn.execute("insert into memory(kind, title, body) values (?, ?, ?)", (kind, title, body))
            rowid = int(cursor.lastrowid)
            try:
                conn.execute("insert into memory_fts(rowid, title, body) values (?, ?, ?)", (rowid, title, body))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return rowid

    def search(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    select memory.id, memory.kind, memory.title, snippet(memory_fts, 1, '[', ']', '...', 12) as body
                    from memory_fts join memory on memory_fts.rowid = memory.id
                    where memory_fts match ?
                    limit ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "select id, kind, title, body from memory where title like ? or body like ? limit ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
        return [dict(row) for row in rows]


def memory_files(paths: RuntimePaths) -> list[Path]:
    ensure_runtime(paths)
    return sorted(paths.memory_dir.glob("*.md"))
