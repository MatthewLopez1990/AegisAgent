from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimePaths:
    workspace: Path
    state_dir: Path
    audit_jsonl: Path
    audit_db: Path
    memory_db: Path
    memory_dir: Path
    skills_dir: Path
    sessions_dir: Path
    subagents_dir: Path
    jobs_dir: Path
    tasks_dir: Path
    automations_dir: Path
    improvements_dir: Path
    browser_sessions_dir: Path
    web_dir: Path


DEFAULT_CONFIG: dict[str, Any] = {
    "policy": {
        "network_default": "ask",
        "host_execution": "ask",
        "shell_writes": "ask",
        "external_delivery": "ask",
        "secret_echo": "deny",
        "sandbox": "docker-preferred",
    },
    "subagents": {"max_concurrency": 8, "max_depth": 2, "max_children": 5},
    "providers": {
        "active": "local/terminal-v0",
        "default": "local/terminal-v0",
        "routes": {
            "local/terminal-v0": {
                "name": "local/terminal-v0",
                "mode": "local",
                "browser_required": False,
            },
            "openai/gpt-5.5": {
                "name": "openai/gpt-5.5",
                "mode": "not_configured",
                "browser_required": False,
            },
        },
    },
    "connectors": {
        "routes": {
            "slack": {"name": "slack", "kind": "messaging", "enabled": False, "token_env": "SLACK_BOT_TOKEN", "approval": "ask_send"},
            "teams": {"name": "teams", "kind": "messaging", "enabled": False, "token_env": "TEAMS_BOT_TOKEN", "approval": "ask_send"},
            "webhook": {"name": "webhook", "kind": "webhook", "enabled": False, "url_env": "AEGIS_WEBHOOK_URL", "approval": "ask_send"},
            "mcp": {"name": "mcp", "kind": "external_tools", "enabled": False, "approval": "ask_connect"},
            "browser": {"name": "browser", "kind": "local_browser", "enabled": False, "approval": "manual_open", "browser_auto_launch": False},
            "openwebui": {"name": "openwebui", "kind": "messaging", "enabled": False, "url_env": "OPENWEBUI_BASE_URL", "approval": "ask_send"},
        }
    },
}


def runtime_paths(workspace: str | Path | None = None) -> RuntimePaths:
    root = Path(workspace or os.getcwd()).resolve()
    state = root / ".aegisagent"
    return RuntimePaths(
        workspace=root,
        state_dir=state,
        audit_jsonl=state / "audit.jsonl",
        audit_db=state / "audit.sqlite",
        memory_db=state / "memory.sqlite",
        memory_dir=state / "memory",
        skills_dir=root / "skills",
        sessions_dir=state / "sessions",
        subagents_dir=state / "subagents",
        jobs_dir=state / "jobs",
        tasks_dir=state / "tasks",
        automations_dir=state / "automations",
        improvements_dir=state / "improvements",
        browser_sessions_dir=state / "browser_sessions",
        web_dir=root / "web",
    )


def ensure_runtime(paths: RuntimePaths) -> None:
    for directory in (paths.state_dir, paths.memory_dir, paths.skills_dir, paths.sessions_dir, paths.subagents_dir, paths.jobs_dir, paths.tasks_dir, paths.automations_dir, paths.improvements_dir, paths.browser_sessions_dir):
        directory.mkdir(parents=True, exist_ok=True)
    config_path = paths.state_dir / "config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    for name, body in {
        "MEMORY.md": "# AegisAgent Memory\n\nCurated operator and workspace memory lives here.\n",
        "USER.md": "# AegisAgent User Context\n\nAdd stable user preferences and environment notes here.\n",
    }.items():
        target = paths.memory_dir / name
        if not target.exists():
            target.write_text(body, encoding="utf-8")
