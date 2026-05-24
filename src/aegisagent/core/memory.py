from __future__ import annotations

import sqlite3
from contextlib import closing
import hashlib
from pathlib import Path
import re
from typing import Any

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.security.redaction import redact_text


MEMORY_NOTE_TARGETS = {
    "workspace": "MEMORY.md",
    "user": "USER.md",
}
_ENTRY_ID_RE = re.compile(r"^(workspace|user):([a-f0-9]{12})$")
_ENTRY_START_RE = re.compile(r'^<!-- aegis-memory-entry id="(?P<id>(workspace|user):[a-f0-9]{12})" hash="(?P<hash>[a-f0-9]{64})" -->\s*$')
_ENTRY_END = "<!-- /aegis-memory-entry -->"


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
                if file.is_symlink() or not file.is_file():
                    continue
                try:
                    file.resolve().relative_to(self.paths.memory_dir.resolve())
                except ValueError:
                    continue
                body = redact_text(file.read_text(encoding="utf-8")).text
                title = redact_text(file.name).text
                conn.execute("insert into memory(kind, title, body) values (?, ?, ?)", ("curated", title, body))
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
            "raw_secret_values_included": False,
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
        target = self._target_file(clean_kind)
        if target is None:
            return {
                "operation": "add",
                "kind": clean_kind,
                "target": target_name,
                "status": "blocked",
                "error": "memory target must be a regular file inside the memory directory",
                "metadata": {**metadata, "blocked": True},
            }
        entry_hash = _entry_hash(clean_kind, redacted_title.text, redacted_body.text)
        entry_id = f"{clean_kind}:{entry_hash[:12]}"
        metadata.update({"entry_id": entry_id, "content_hash": entry_hash})
        if not approved:
            return {
                "operation": "add",
                "kind": clean_kind,
                "target": target_name,
                "entry_id": entry_id,
                "title": redacted_title.text,
                "status": "needs_approval",
                "next": "rerun with explicit approval to append this note to curated memory",
                "metadata": metadata,
            }
        note = "\n".join(
            [
                "",
                f'<!-- aegis-memory-entry id="{entry_id}" hash="{entry_hash}" -->',
                f"## {redacted_title.text}",
                "",
                redacted_body.text,
                _ENTRY_END,
                "",
            ]
        )
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
            "entry_id": entry_id,
            "title": redacted_title.text,
            "rowid": rowid,
            "status": "ok",
            "metadata": metadata,
        }

    def list_curated_entries(self, *, kind: str = "", limit: int = 20) -> dict[str, Any]:
        clean_kind = kind.strip().lower()
        allowed_kinds = tuple(MEMORY_NOTE_TARGETS)
        if clean_kind and clean_kind not in allowed_kinds:
            return {
                "operation": "list",
                "status": "blocked",
                "error": "memory kind must be workspace or user",
                "metadata": {
                    "kind": clean_kind,
                    "memory_write_performed": False,
                    "workspace_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                    "blocked": True,
                },
            }
        entries = []
        redacted = False
        for target_kind in (clean_kind,) if clean_kind else allowed_kinds:
            try:
                target_entries = self._curated_entries(target_kind)
            except ValueError as exc:
                return _memory_blocked("list", "", str(exc), metadata={"kind": target_kind})
            for entry in target_entries:
                title = redact_text(entry["title"])
                preview = redact_text(_preview(entry["body"]))
                redacted = redacted or title.redacted or preview.redacted
                entries.append(
                    {
                        "id": entry["id"],
                        "kind": entry["kind"],
                        "target": entry["target"],
                        "title": title.text,
                        "preview": preview.text,
                        "character_count": len(entry["body"]),
                        "redacted": title.redacted or preview.redacted,
                    }
                )
                if len(entries) >= max(0, limit):
                    break
            if len(entries) >= max(0, limit):
                break
        return {
            "operation": "list",
            "status": "ok",
            "count": len(entries),
            "entries": entries,
            "metadata": {
                "memory_write_performed": False,
                "workspace_mutation_performed": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
                "redacted": redacted,
            },
        }

    def show_curated_entry(self, entry_id: str) -> dict[str, Any]:
        try:
            found = self._find_curated_entry(entry_id)
        except ValueError as exc:
            return _memory_blocked("show", entry_id, str(exc))
        if found is None:
            return _memory_blocked("show", entry_id, "memory entry id must exist and look like user:abcdef123456 or workspace:abcdef123456")
        entry = found["entry"]
        title = redact_text(entry["title"])
        body = redact_text(entry["body"].strip())
        return {
            "operation": "show",
            "status": "ok",
            "entry": {
                "id": entry["id"],
                "kind": entry["kind"],
                "target": entry["target"],
                "title": title.text,
                "body": body.text,
                "character_count": len(entry["body"]),
                "content_hash": entry["content_hash"],
                "redacted": title.redacted or body.redacted,
            },
            "metadata": {
                "memory_write_performed": False,
                "workspace_mutation_performed": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
                "redacted": title.redacted or body.redacted,
            },
        }

    def delete_curated_entry(self, entry_id: str, *, approved: bool = False) -> dict[str, Any]:
        try:
            found = self._find_curated_entry(entry_id)
        except ValueError as exc:
            return _memory_blocked("delete", entry_id, str(exc))
        metadata: dict[str, Any] = {
            "operation": "delete",
            "entry_id": entry_id.strip(),
            "approved": approved,
            "memory_write_performed": False,
            "workspace_mutation_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
        }
        if found is None:
            return _memory_blocked("delete", entry_id, "memory entry id must exist and look like user:abcdef123456 or workspace:abcdef123456", metadata=metadata)
        entry = found["entry"]
        title = redact_text(entry["title"])
        metadata.update(
            {
                "kind": entry["kind"],
                "target": entry["target"],
                "title": title.text,
                "content_hash": entry["content_hash"],
                "line_start": int(entry["start_line"]) + 1,
                "line_end": int(entry["end_line"]),
                "redacted": title.redacted,
            }
        )
        if entry.get("hash_mismatch"):
            return _memory_blocked("delete", entry_id, "memory entry changed after it was written; review the current entry before deleting", metadata=metadata)
        if not approved:
            return {
                "operation": "delete",
                "status": "needs_approval",
                "entry_id": entry["id"],
                "kind": entry["kind"],
                "target": entry["target"],
                "title": title.text,
                "next": "rerun with explicit approval to remove this curated memory entry",
                "metadata": metadata,
            }
        lines = found["lines"]
        start = int(entry["start_line"])
        end = int(entry["end_line"])
        before_text = "".join(lines)
        del lines[start:end]
        target = self._target_file(str(entry["kind"]))
        if target is None:
            return _memory_blocked("delete", entry_id, "memory target must be a regular file inside the memory directory", metadata=metadata)
        after_text = "".join(lines)
        target.write_text(after_text, encoding="utf-8")
        deleted_rows = self._delete_memory_rows(f"{entry['kind']}_note", str(entry["title"]), str(entry["body"]))
        indexed = self.index_curated_files()
        metadata.update(
            {
                "memory_write_performed": True,
                "workspace_mutation_performed": True,
                "deleted_rows": deleted_rows,
                "indexed": indexed,
                "pre_file_hash": _sha256(before_text),
                "post_file_hash": _sha256(after_text),
            }
        )
        return {
            "operation": "delete",
            "status": "ok",
            "entry_id": entry["id"],
            "kind": entry["kind"],
            "target": entry["target"],
            "title": title.text,
            "metadata": metadata,
        }

    def _delete_memory_rows(self, kind: str, title: str, body: str) -> int:
        with closing(sqlite3.connect(self.paths.memory_db)) as conn:
            cursor = conn.execute("delete from memory where kind = ? and title = ? and body = ?", (kind, title, body))
            deleted = cursor.rowcount
            try:
                conn.execute("insert into memory_fts(memory_fts) values ('rebuild')")
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return int(deleted)

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
        redacted_rows: list[dict[str, str]] = []
        for row in rows:
            item = dict(row)
            redacted_rows.append({key: redact_text(str(value)).text for key, value in item.items()})
        return redacted_rows

    def _find_curated_entry(self, entry_id: str) -> dict[str, Any] | None:
        clean_id = entry_id.strip()
        match = _ENTRY_ID_RE.fullmatch(clean_id)
        if not match:
            return None
        kind = match.group(1)
        target = self._target_file(kind)
        if target is None:
            raise ValueError("memory target must be a regular file inside the memory directory")
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        for entry in self._curated_entries(kind, lines=lines):
            if entry["id"] == clean_id:
                return {"entry": entry, "lines": lines}
        return None

    def _curated_entries(self, kind: str, *, lines: list[str] | None = None) -> list[dict[str, Any]]:
        target_name = MEMORY_NOTE_TARGETS[kind]
        target = self._target_file(kind)
        if target is None:
            raise ValueError("memory target must be a regular file inside the memory directory")
        source_lines = lines if lines is not None else target.read_text(encoding="utf-8").splitlines(keepends=True)
        entries: list[dict[str, Any]] = []
        index = 0
        while index < len(source_lines):
            match = _ENTRY_START_RE.match(source_lines[index])
            if not match:
                index += 1
                continue
            end = index + 1
            while end < len(source_lines) and source_lines[end].strip() != _ENTRY_END:
                end += 1
            if end >= len(source_lines):
                index += 1
                continue
            title_line_index = index + 1
            title = ""
            if title_line_index < end and source_lines[title_line_index].startswith("## "):
                title = source_lines[title_line_index].removeprefix("## ").strip()
                body_start = title_line_index + 1
            else:
                body_start = index + 1
            body = "".join(source_lines[body_start:end]).strip()
            current_hash = _entry_hash(kind, title, body)
            entries.append(
                {
                    "id": match.group("id"),
                    "kind": kind,
                    "target": target_name,
                    "title": title,
                    "body": body,
                    "content_hash": current_hash,
                    "stored_hash": match.group("hash"),
                    "hash_mismatch": current_hash != match.group("hash"),
                    "start_line": index,
                    "end_line": end + 1,
                }
            )
            index = end + 1
        if entries:
            return entries
        starts = [line_index for line_index, line in enumerate(source_lines) if line.startswith("## ")]
        for ordinal, start in enumerate(starts, start=1):
            end = starts[ordinal] if ordinal < len(starts) else len(source_lines)
            title = source_lines[start].removeprefix("## ").strip()
            body = "".join(source_lines[start + 1 : end]).strip()
            content_hash = _entry_hash(kind, title, body)
            entries.append(
                {
                    "id": f"{kind}:{content_hash[:12]}",
                    "kind": kind,
                    "target": target_name,
                    "title": title,
                    "body": body,
                    "content_hash": content_hash,
                    "stored_hash": content_hash,
                    "hash_mismatch": False,
                    "start_line": start,
                    "end_line": end,
                }
            )
        return entries

    def _target_file(self, kind: str) -> Path | None:
        target_name = MEMORY_NOTE_TARGETS.get(kind, "")
        if not target_name:
            return None
        target = self.paths.memory_dir / target_name
        if target.is_symlink() or not target.is_file():
            return None
        try:
            target.resolve().relative_to(self.paths.memory_dir.resolve())
        except ValueError:
            return None
        return target


def memory_files(paths: RuntimePaths) -> list[Path]:
    ensure_runtime(paths)
    return sorted(paths.memory_dir.glob("*.md"))


def _memory_blocked(operation: str, entry_id: str, error: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    base_metadata = {
        "operation": operation,
        "entry_id": entry_id.strip(),
        "memory_write_performed": False,
        "workspace_mutation_performed": False,
        "external_action_started": False,
        "browser_auto_launch": False,
        "raw_secret_values_included": False,
        "blocked": True,
    }
    return {
        "operation": operation,
        "status": "blocked",
        "entry_id": entry_id.strip(),
        "error": error,
        "metadata": {**base_metadata, **(metadata or {}), "blocked": True},
    }


def _preview(value: str, *, limit: int = 160) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "."


def _entry_hash(kind: str, title: str, body: str) -> str:
    return _sha256(f"{kind}\0{title}\0{body}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
