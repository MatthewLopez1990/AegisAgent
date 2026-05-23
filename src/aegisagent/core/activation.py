from __future__ import annotations

import os
from typing import Any

from aegisagent.config import RuntimePaths


def terminal_activation_payload(paths: RuntimePaths) -> dict[str, Any]:
    command_name = os.environ.get("AEGIS_COMMAND_NAME", "aegisagent").strip() or "aegisagent"
    primary_command = f"{command_name} tui"
    fallback = f"{command_name} tui --print"
    return {
        "title": "AEGIS TERMINAL ACTIVATION",
        "workspace": str(paths.workspace),
        "primary_command": primary_command,
        "installed_alias": "aegis tui",
        "default_entrypoint": command_name,
        "module_entrypoint": "PYTHONPATH=src python3 -m aegisagent",
        "fallback": fallback,
        "terminal_first": True,
        "browser_required": False,
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
        "web_gui": {
            "optional": True,
            "command": "aegisagent web",
            "opens_browser": False,
            "note": "Use only when you explicitly want the secondary browser console.",
        },
        "tui_commands": [
            "/setup run-checks",
            "/dashboard",
            "/install",
            "/update",
            "/capabilities",
            "/gaps",
            "/tasks",
            "/agents",
            "/browser",
            "/activation",
        ],
        "next": [
            f"Run `{command_name}` or `{primary_command}` in a real terminal.",
            "Use `PYTHONPATH=src python3 -m aegisagent` from a source checkout.",
            "Use `/setup run-checks` inside the TUI for metadata-only readiness.",
            "Use `/web` only to print optional Web GUI instructions.",
        ],
    }


def format_terminal_activation(payload: dict[str, Any]) -> str:
    lines = [
        str(payload["title"]),
        f"workspace   {payload['workspace']}",
        f"primary     {payload['primary_command']}",
        f"alias       {payload['installed_alias']}",
        f"source      {payload['module_entrypoint']}",
        f"default     {payload['default_entrypoint']} -> terminal TUI",
        f"fallback    {payload['fallback']}",
        "",
        "safety",
        f"- terminal_first: {str(payload['terminal_first']).lower()}",
        f"- browser_required: {str(payload['browser_required']).lower()}",
        f"- browser_auto_launch: {str(payload['browser_auto_launch']).lower()}",
        f"- gateway_started: {str(payload['gateway_started']).lower()}",
        f"- external_action_started: {str(payload['external_action_started']).lower()}",
        "",
        "inside the TUI",
    ]
    lines.extend(f"- {command}" for command in payload["tui_commands"])
    lines.extend(["", "next"])
    lines.extend(f"- {item}" for item in payload["next"])
    lines.extend(["", f"optional web: {payload['web_gui']['command']} ({payload['web_gui']['note']})"])
    return "\n".join(lines)
