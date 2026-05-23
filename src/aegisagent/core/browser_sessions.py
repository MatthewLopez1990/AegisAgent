from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.security.redaction import redact_text


class BrowserSessionStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        records = [self._read_record(path) for path in sorted(self.paths.browser_sessions_dir.glob("browser-*.json"))]
        return [record for record in records if record is not None][-limit:]

    def get(self, session_id: str) -> dict[str, Any]:
        clean_id = session_id.strip()
        record = self._read_record(self.paths.browser_sessions_dir / f"{clean_id}.json")
        if record is None:
            raise KeyError(f"unknown browser session: {session_id}")
        return record

    def open_url(self, url: str, *, title: str = "", approved: bool = False, source: str = "cli") -> dict[str, Any]:
        clean_url = url.strip()
        clean_title = " ".join(title.strip().split())[:120]
        parsed = urlparse(clean_url)
        metadata: dict[str, Any] = {
            "operation": "open",
            "approved": approved,
            "source": source,
            "browser_session_created": False,
            "browser_launch_performed": False,
            "browser_auto_launch": False,
            "external_action_started": False,
            "workspace_mutation_performed": False,
        }
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return {
                "operation": "open",
                "status": "blocked",
                "url": clean_url,
                "error": "url must be an explicit http(s) URL without embedded credentials",
                "metadata": {**metadata, "blocked": True},
            }
        redacted_url = redact_text(clean_url)
        redacted_title = redact_text(clean_title)
        metadata["redacted"] = redacted_url.redacted or redacted_title.redacted
        if not approved:
            return {
                "operation": "open",
                "status": "needs_approval",
                "url": redacted_url.text,
                "title": redacted_title.text,
                "next": "rerun with explicit approval to create a browser session record; Aegis will still not auto-launch a browser",
                "metadata": metadata,
            }
        now = _now()
        session_id = f"browser-{uuid.uuid4().hex[:12]}"
        record = {
            "id": session_id,
            "created_at": now,
            "updated_at": now,
            "url": redacted_url.text,
            "title": redacted_title.text,
            "status": "ready_for_operator",
            "source": source,
            "operator_open_url": redacted_url.text,
            "browser_auto_launch": False,
            "browser_launch_performed": False,
            "screenshots": [],
        }
        self._write_record(record)
        return {
            "operation": "open",
            "status": "ok",
            "session": record,
            "metadata": {
                **metadata,
                "session_id": session_id,
                "browser_session_created": True,
            },
        }

    def record_screenshot(self, session_id: str, screenshot_path: str, *, approved: bool = False, note: str = "", source: str = "cli") -> dict[str, Any]:
        clean_id = session_id.strip()
        clean_note = note.strip()[:500]
        metadata: dict[str, Any] = {
            "operation": "screenshot",
            "session_id": clean_id,
            "approved": approved,
            "source": source,
            "screenshot_receipt_recorded": False,
            "browser_launch_performed": False,
            "browser_auto_launch": False,
            "external_action_started": False,
            "workspace_mutation_performed": False,
        }
        try:
            record = self.get(clean_id)
        except KeyError:
            return {
                "operation": "screenshot",
                "status": "blocked",
                "session_id": clean_id,
                "error": "browser session does not exist",
                "metadata": {**metadata, "blocked": True},
            }
        resolved = self._resolve_workspace_file(screenshot_path)
        if resolved is None:
            return {
                "operation": "screenshot",
                "status": "blocked",
                "session_id": clean_id,
                "path": screenshot_path,
                "error": "screenshot path must be an existing file inside the workspace",
                "metadata": {**metadata, "blocked": True},
            }
        rel = str(resolved.relative_to(self.paths.workspace))
        redacted_note = redact_text(clean_note)
        metadata.update({"path": rel, "redacted": redacted_note.redacted})
        if not approved:
            return {
                "operation": "screenshot",
                "status": "needs_approval",
                "session_id": clean_id,
                "path": rel,
                "note": redacted_note.text,
                "next": "rerun with explicit approval to attach this screenshot receipt to the browser session",
                "metadata": metadata,
            }
        screenshot = {
            "id": f"screenshot-{uuid.uuid4().hex[:12]}",
            "created_at": _now(),
            "path": rel,
            "note": redacted_note.text,
            "source": source,
        }
        record.setdefault("screenshots", []).append(screenshot)
        record["updated_at"] = screenshot["created_at"]
        self._write_record(record)
        return {
            "operation": "screenshot",
            "status": "ok",
            "session_id": clean_id,
            "screenshot": screenshot,
            "metadata": {**metadata, "screenshot_id": screenshot["id"], "screenshot_receipt_recorded": True},
        }

    def _resolve_workspace_file(self, raw_path: str) -> Path | None:
        if not raw_path.strip():
            return None
        candidate = (self.paths.workspace / raw_path.strip()).resolve()
        try:
            candidate.relative_to(self.paths.workspace)
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        return candidate

    def _read_record(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_record(self, record: dict[str, Any]) -> None:
        target = self.paths.browser_sessions_dir / f"{record['id']}.json"
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def browser_summary(paths: RuntimePaths, *, limit: int = 20) -> dict[str, Any]:
    store = BrowserSessionStore(paths)
    sessions = store.list(limit=limit)
    return {
        "browser_auto_launch": False,
        "browser_launch_performed": False,
        "session_count": len(sessions),
        "sessions": sessions,
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
