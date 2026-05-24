from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
import fcntl
from pathlib import Path
from typing import Iterable

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.models import AuditReceipt
from aegisagent.security.redaction import redact_mapping

GENESIS_HASH = "0" * 64


def _canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _entry_hash(previous_hash: str, receipt: dict) -> str:
    return hashlib.sha256(f"{previous_hash}\n{_canonical(receipt)}".encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self._init_db()

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.paths.audit_db)) as conn:
            conn.execute(
                """
                create table if not exists receipts (
                    id text primary key,
                    created_at text not null,
                    event_type text not null,
                    previous_hash text not null,
                    entry_hash text not null,
                    payload text not null
                )
                """
            )
            conn.commit()

    def _load_entries(self) -> list[dict]:
        if not self.paths.audit_jsonl.exists():
            return []
        entries = []
        for line in self.paths.audit_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        return entries

    def append(self, event_type: str, payload: dict) -> dict:
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.paths.state_dir / "audit.lock"
        with lock_path.open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                clean_payload, redacted = redact_mapping(payload)
                receipt = AuditReceipt(event_type=event_type, payload={**clean_payload, "redacted": redacted}).to_dict()
                entries = self._load_entries()
                previous = entries[-1]["entry_hash"] if entries else GENESIS_HASH
                entry_hash = _entry_hash(previous, receipt)
                entry = {**receipt, "previous_hash": previous, "entry_hash": entry_hash}
                with self.paths.audit_jsonl.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, sort_keys=True) + "\n")
                with closing(sqlite3.connect(self.paths.audit_db)) as conn:
                    conn.execute(
                        "insert or replace into receipts values (?, ?, ?, ?, ?, ?)",
                        (
                            entry["id"],
                            entry["created_at"],
                            entry["event_type"],
                            entry["previous_hash"],
                            entry["entry_hash"],
                            json.dumps(entry["payload"], sort_keys=True),
                        ),
                    )
                    conn.commit()
                return entry
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def verify(self) -> dict:
        try:
            entries = self._load_entries()
        except (json.JSONDecodeError, TypeError) as exc:
            return {"ok": False, "count": 0, "failed_index": 0, "error": f"malformed audit entry: {exc}"}
        previous = GENESIS_HASH
        for index, entry in enumerate(entries):
            try:
                receipt = {key: entry[key] for key in ("id", "created_at", "event_type", "payload")}
            except (KeyError, TypeError) as exc:
                return {"ok": False, "count": len(entries), "failed_index": index, "error": f"malformed audit entry: {exc}"}
            expected = _entry_hash(previous, receipt)
            if entry.get("previous_hash") != previous or entry.get("entry_hash") != expected:
                return {"ok": False, "count": len(entries), "failed_index": index, "expected_hash": expected}
            previous = entry["entry_hash"]
        return {"ok": True, "count": len(entries), "head": previous}

    def recent(self, limit: int = 10) -> list[dict]:
        entries = self._load_entries()
        return entries[-limit:]


def verify_jsonl(path: Path) -> dict:
    fake_paths = type(
        "Paths",
        (),
        {
            "audit_jsonl": path,
            "audit_db": path.with_suffix(".sqlite"),
            "state_dir": path.parent,
            "memory_dir": path.parent / "memory",
            "skills_dir": path.parent / "skills",
            "sessions_dir": path.parent / "sessions",
            "subagents_dir": path.parent / "subagents",
            "jobs_dir": path.parent / "jobs",
            "tasks_dir": path.parent / "tasks",
            "automations_dir": path.parent / "automations",
            "improvements_dir": path.parent / "improvements",
            "browser_sessions_dir": path.parent / "browser_sessions",
        },
    )()
    return AuditLog(fake_paths).verify()  # type: ignore[arg-type]
