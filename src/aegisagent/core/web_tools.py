from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from aegisagent.config import RuntimePaths
from aegisagent.security.redaction import redact_text


@dataclass(frozen=True, slots=True)
class WebToolResult:
    name: str
    status: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "content": self.content,
            "metadata": self.metadata,
        }


class WebToolRunner:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths

    def fetch(self, url: str, *, approved: bool = False, timeout: float = 10.0, max_bytes: int = 20000) -> WebToolResult:
        clean_url = url.strip()
        parsed = urlparse(clean_url)
        metadata: dict[str, Any] = {
            "operation": "fetch",
            "url": clean_url,
            "approved": approved,
            "network_capable": True,
            "network_request_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "workspace_mutation_performed": False,
        }
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return WebToolResult(
                name="web.fetch",
                status="blocked",
                content=json.dumps({"operation": "fetch", "url": clean_url, "status": "blocked", "error": "url must be an explicit http(s) URL without embedded credentials"}, indent=2),
                metadata={**metadata, "blocked": True},
            )
        redacted_url = redact_text(clean_url)
        metadata["redacted"] = redacted_url.redacted
        if not approved:
            return WebToolResult(
                name="web.fetch",
                status="needs_approval",
                content=json.dumps(
                    {
                        "operation": "fetch",
                        "url": redacted_url.text,
                        "status": "needs_approval",
                        "next": "rerun with explicit approval to perform this network fetch",
                    },
                    indent=2,
                ),
                metadata={**metadata, "url": clean_url, "approved": False},
            )

        request = urllib.request.Request(
            clean_url,
            headers={
                "Accept": "text/plain,text/html,application/json,*/*;q=0.8",
                "User-Agent": "AegisAgent/0.1 terminal-web-fetch",
            },
            method="GET",
        )
        metadata.update({"network_request_performed": True, "external_action_started": True})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(max_bytes + 1)
                status_code = int(response.status)
                final_url = response.geturl()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raw = exc.read(max_bytes + 1)
            status_code = int(exc.code)
            final_url = exc.geturl()
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = redact_text(str(exc))
            return WebToolResult(
                name="web.fetch",
                status="error",
                content=json.dumps({"operation": "fetch", "url": redacted_url.text, "status": "error", "error": error.text}, indent=2),
                metadata={**metadata, "returncode": 1, "redacted": metadata["redacted"] or error.redacted},
            )

        truncated = len(raw) > max_bytes
        text = raw[:max_bytes].decode("utf-8", errors="replace")
        redacted_body = redact_text(text)
        final_url_redacted = redact_text(final_url)
        ok = 200 <= status_code < 400
        return WebToolResult(
            name="web.fetch",
            status="ok" if ok else "error",
            content=json.dumps(
                {
                    "operation": "fetch",
                    "url": redacted_url.text,
                    "final_url": final_url_redacted.text,
                    "status": "ok" if ok else "error",
                    "status_code": status_code,
                    "content_type": content_type,
                    "body": redacted_body.text,
                    "truncated": truncated,
                },
                indent=2,
            ),
            metadata={
                **metadata,
                "status_code": status_code,
                "bytes": min(len(raw), max_bytes),
                "truncated": truncated,
                "redacted": metadata["redacted"] or final_url_redacted.redacted or redacted_body.redacted,
            },
        )
