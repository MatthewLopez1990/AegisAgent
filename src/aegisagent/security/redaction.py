from __future__ import annotations

import re
from dataclasses import dataclass

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|bearer)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redacted: bool
    count: int


def redact_text(value: str) -> RedactionResult:
    text = value
    count = 0
    for pattern in SECRET_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            if match.lastindex and match.lastindex >= 2:
                return f"{match.group(1)}=[REDACTED]"
            return "[REDACTED]"

        text = pattern.sub(replace, text)
    return RedactionResult(text=text, redacted=count > 0, count=count)


def redact_mapping(payload: dict) -> tuple[dict, bool]:
    redacted = False
    clean: dict = {}
    for key, value in payload.items():
        if isinstance(value, str):
            result = redact_text(value)
            clean[key] = result.text
            redacted = redacted or result.redacted or "secret" in key.lower() or "token" in key.lower()
            if "secret" in key.lower() or "token" in key.lower() or "password" in key.lower():
                clean[key] = "[REDACTED]"
        elif isinstance(value, dict):
            clean[key], child_redacted = redact_mapping(value)
            redacted = redacted or child_redacted
        elif isinstance(value, list):
            next_values = []
            for item in value:
                if isinstance(item, str):
                    result = redact_text(item)
                    next_values.append(result.text)
                    redacted = redacted or result.redacted
                elif isinstance(item, dict):
                    next_item, child_redacted = redact_mapping(item)
                    next_values.append(next_item)
                    redacted = redacted or child_redacted
                else:
                    next_values.append(item)
            clean[key] = next_values
        else:
            clean[key] = value
    return clean, redacted
