from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.models import utc_now
from aegisagent.security.redaction import redact_text


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "session"


@dataclass(slots=True)
class SessionMessage:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class SessionRecord:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[SessionMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
        }


class SessionStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)

    def create(self, title: str = "Main") -> SessionRecord:
        now = utc_now()
        session = SessionRecord(id=f"{_slug(title)}-{uuid4().hex[:8]}", title=title, created_at=now, updated_at=now)
        self._write(session)
        return session

    def get(self, session_id: str = "main") -> SessionRecord:
        path = self._path_for(session_id)
        if not path.exists() and session_id == "main":
            return self.create("main")
        if not path.exists():
            raise KeyError(f"session not found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionRecord(
            id=str(data["id"]),
            title=str(data["title"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            messages=[
                SessionMessage(
                    role=str(message["role"]),
                    content=str(message["content"]),
                    created_at=str(message.get("created_at") or utc_now()),
                    metadata=dict(message.get("metadata") or {}),
                )
                for message in data.get("messages", [])
                if isinstance(message, dict)
            ],
        )

    def append(self, session_id: str, role: str, content: str, *, metadata: dict[str, Any] | None = None) -> SessionRecord:
        session = self.get(session_id)
        redacted = redact_text(content)
        message_metadata = dict(metadata or {})
        if redacted.redacted:
            message_metadata["redacted"] = True
            message_metadata["redaction_count"] = redacted.count
        session.messages.append(SessionMessage(role=role, content=redacted.text, metadata=message_metadata))
        session.updated_at = utc_now()
        self._write(session)
        return session

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.sessions_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            session = self.get(path.stem)
            rows.append(
                {
                    "id": session.id,
                    "title": session.title,
                    "updated_at": session.updated_at,
                    "message_count": len(session.messages),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def transcript(self, session_id: str = "main", limit: int = 20) -> list[dict[str, Any]]:
        session = self.get(session_id)
        return [message.to_dict() for message in session.messages[-limit:]]

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        needle = query.lower().strip()
        if not needle:
            return []
        matches: list[dict[str, Any]] = []
        for path in sorted(self.paths.sessions_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            session = self.get(path.stem)
            for index, message in enumerate(session.messages):
                haystack = f"{session.title}\n{message.role}\n{message.content}".lower()
                if needle not in haystack:
                    continue
                matches.append(
                    {
                        "session_id": session.id,
                        "title": session.title,
                        "message_index": index,
                        "role": message.role,
                        "created_at": message.created_at,
                        "snippet": _snippet(message.content, needle),
                        "metadata": message.metadata,
                    }
                )
                if len(matches) >= limit:
                    return matches
        return matches

    def _path_for(self, session_id: str) -> Path:
        if session_id == "main":
            matches = sorted(self.paths.sessions_dir.glob("main-*.json"))
            if matches:
                return matches[0]
        return self.paths.sessions_dir / f"{session_id}.json"

    def _write(self, session: SessionRecord) -> None:
        self.paths.sessions_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.sessions_dir / f"{session.id}.json").write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")


def _snippet(content: str, needle: str, *, radius: int = 80) -> str:
    lower = content.lower()
    index = lower.find(needle)
    if index < 0:
        return content[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(content), index + len(needle) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end].strip()}{suffix}"
