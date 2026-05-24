from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aegisagent import __version__
from aegisagent.config import RuntimePaths
from aegisagent.core.command_names import terminal_command_name
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.memory import MemoryStore
from aegisagent.core.provider_config import ProviderStore
from aegisagent.core.skills import SkillLoader
from aegisagent.core.tools import enabled_counts
from aegisagent.security.audit import AuditLog
from aegisagent.security.sandbox import detect_sandbox


SETUP_SECTIONS = ("model", "secrets", "sandbox", "tools", "connectors", "memory")
SETUP_ALIASES = {
    "1": "model",
    "2": "secrets",
    "3": "sandbox",
    "4": "tools",
    "5": "connectors",
    "6": "memory",
    "initialize": "quickstart",
    "model-auth": "model",
    "connections": "connectors",
    "skills": "memory",
    "plugins": "memory",
    "check": "run-checks",
    "checks": "run-checks",
    "verify": "run-checks",
    "doctor": "run-checks",
    "init": "quickstart",
}
SETUP_SECTION_CHOICES = (*SETUP_SECTIONS, "next", "first-task", *SETUP_ALIASES)
SETUP_NEXT_SECTION_COUNT = len(SETUP_SECTIONS)


@dataclass(frozen=True, slots=True)
class SetupSection:
    name: str
    status: str
    summary: str
    commands: tuple[str, ...]
    checks: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        command = self.commands[0] if self.commands else ""
        ready = self.status in {"ready", "local"} or self.status.endswith("_enabled")
        return {
            "id": self.name,
            "name": self.name,
            "label": self.name.replace("_", " ").title(),
            "status": self.status,
            "state": "ready" if ready else "action_required",
            "summary": self.summary,
            "detail": self.summary,
            "command": command,
            "commands": list(self.commands),
            "next_commands": list(self.commands),
            "checks": list(self.checks),
            "ready": ready,
            "action_required": not ready,
            "safe_to_run_now": True,
        }


@dataclass(frozen=True, slots=True)
class SetupPriority:
    section: str
    status: str
    label: str
    reason: str
    command: str
    slash_command: str
    index: int
    total: int = SETUP_NEXT_SECTION_COUNT
    terminal_first: bool = True
    browser_required: bool = False
    browser_auto_launch: bool = False
    external_action_started: bool = False
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "status": self.status,
            "label": self.label,
            "reason": self.reason,
            "command": self.command,
            "slash_command": self.slash_command,
            "index": self.index,
            "total": self.total,
            "terminal_first": self.terminal_first,
            "browser_required": self.browser_required,
            "browser_auto_launch": self.browser_auto_launch,
            "external_action_started": self.external_action_started,
            "done": self.done,
        }


class SetupGuide:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.audit = AuditLog(paths)

    def quickstart(self) -> dict[str, Any]:
        sections = [self.section(name) for name in SETUP_SECTIONS]
        command = terminal_command_name()
        priority = self.priority()
        return {
            "title": "AEGIS SETUP QUICKSTART",
            "version": __version__,
            "workspace": str(self.paths.workspace),
            "status": "needs_operator_review" if not priority.done else "ready_for_checks",
            "metadata_only": True,
            "terminal_first": True,
            "browser_required": False,
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": False,
            "model_invocation_performed": False,
            "send_probe_performed": False,
            "raw_secret_values_included": False,
            "setup_progress": {
                "current": priority.index,
                "total": priority.total,
                "complete": priority.done,
                "priority_step": priority.section,
            },
            "priority_step": priority.to_dict(),
            "priority": priority.to_dict(),
            "steps": [section.to_dict() for section in sections],
            "verification_commands": [f"{command} setup --run-checks", "/setup run-checks", "/setup verify"],
            "next": [
                f"1. Run `{command} setup next` or `/setup next`.",
                f"2. Run `{command} setup --run-checks` or `/setup run-checks`.",
                f"3. Launch `{command}` or `{command} tui` and keep working from the terminal composer.",
            ],
        }

    def next_payload(self) -> dict[str, Any]:
        priority = self.priority()
        return {
            "title": "AEGIS SETUP NEXT",
            "workspace": str(self.paths.workspace),
            "metadata_only": True,
            "terminal_first": True,
            "browser_required": False,
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": False,
            "model_invocation_performed": False,
            "send_probe_performed": False,
            "raw_secret_values_included": False,
            "priority_step": {
                "id": priority.section,
                "position": priority.index,
                "total": priority.total,
                "command": priority.slash_command,
                "cli_command": priority.command,
                "status": priority.status,
                "summary": priority.reason,
                "next_command": "/setup next",
            },
            "priority": priority.to_dict(),
        }

    def priority(self) -> SetupPriority:
        command = terminal_command_name()
        provider = ProviderStore(self.paths).summary()
        provider_mode = str(provider.get("mode") or "unknown")
        if provider_mode in {"unknown", "not_configured", "local"}:
            return SetupPriority(
                section="model",
                status=provider_mode,
                label="Choose model route",
                reason="Pick the local terminal route or save an external provider handle before running real agent turns.",
                command=f"{command} setup model",
                slash_command="/setup model",
                index=1,
            )

        sandbox = detect_sandbox()
        if sandbox.backend != "docker":
            return SetupPriority(
                section="sandbox",
                status=sandbox.backend,
                label="Review execution sandbox",
                reason="Host execution is allowed only through policy gates; review this before enabling broader tools.",
                command=f"{command} setup sandbox",
                slash_command="/setup sandbox",
                index=3,
            )

        connector_summary = ConnectorStore(self.paths).summary()
        if connector_summary["enabled_count"] == 0:
            return SetupPriority(
                section="connectors",
                status="0_enabled",
                label="Review connector metadata",
                reason="External delivery stays disabled until a connector is explicitly configured and approved.",
                command=f"{command} setup connectors",
                slash_command="/setup connectors",
                index=5,
            )

        return SetupPriority(
            section="checks",
            status="ready",
            label="Run setup checks",
            reason="Core setup metadata is present; run the local readiness receipt before normal use.",
            command=f"{command} setup --run-checks",
            slash_command="/setup run-checks",
            index=SETUP_NEXT_SECTION_COUNT,
            done=True,
        )

    def section(self, name: str) -> SetupSection:
        if name == "model":
            provider = ProviderStore(self.paths).summary()
            command = terminal_command_name()
            return SetupSection(
                "model",
                str(provider.get("mode") or "unknown"),
                f"Active provider: {provider.get('active_provider', '')}. Configure external routes by environment-variable handle, not raw secret.",
                (
                    f"{command} model providers",
                    f"{command} model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY",
                    f"{command} model doctor",
                ),
                tuple({"name": route["name"], "status": route["status"]} for route in provider.get("routes", [])),
            )
        if name == "secrets":
            command = terminal_command_name()
            return SetupSection(
                "secrets",
                "handles_only",
                "Secrets are referenced by handles such as environment variable names; raw secret values are not stored in setup config or audit payloads.",
                ("export OPENAI_API_KEY=...", f"{command} model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY"),
                ({"name": "raw_secret_values_included", "ok": False},),
            )
        if name == "sandbox":
            sandbox = detect_sandbox()
            command = terminal_command_name()
            return SetupSection(
                "sandbox",
                sandbox.backend,
                sandbox.rationale,
                (f"{command} health", "/status", "/policy shell rg --files"),
                (sandbox.to_dict(),),
            )
        if name == "tools":
            counts = enabled_counts()
            command = terminal_command_name()
            return SetupSection(
                "tools",
                "policy_gated",
                f"{counts['enabled']} tools enabled, {counts['ask']} actions require approval.",
                (f"{command} tools --matrix", "/tools", "/policy shell <command>"),
                (counts,),
            )
        if name == "connectors":
            connector_summary = ConnectorStore(self.paths).summary()
            command = terminal_command_name()
            return SetupSection(
                "connectors",
                f"{connector_summary['enabled_count']}_enabled",
                "Slack, Teams, webhooks, MCP, browser, and Open WebUI adapters are tracked as local metadata; none can deliver externally without explicit future approval.",
                (f"{command} connectors", f"{command} connectors doctor", f"{command} connectors configure slack --token-env SLACK_BOT_TOKEN --enable"),
                (
                    {"name": "external_delivery", "default": "ask", "external_delivery_performed": connector_summary["external_delivery_performed"]},
                    {"name": "browser_auto_launch", "ok": connector_summary["browser_auto_launch"]},
                    *tuple({"name": item["name"], "status": item["status"], "approval": item["approval"]} for item in connector_summary["connectors"]),
                ),
            )
        if name == "memory":
            skill_summary = SkillLoader([self.paths.skills_dir]).trust_summary()
            skill_counts = skill_summary["counts"]
            command = terminal_command_name()
            return SetupSection(
                "memory",
                "local",
                "Workspace memory and skill discovery stay local unless a future connector is explicitly configured.",
                (f"{command} memory --index", f"{command} skills", "/memory", "/skills"),
                (
                    {"name": "skills_found", "count": skill_counts["total"]},
                    {"name": "skills_trusted", "count": skill_counts["trusted"]},
                    {"name": "skills_review", "count": skill_counts["review"]},
                    {"name": "skills_quarantined", "count": skill_counts["quarantined"]},
                    {"name": "skill_trust_metadata", "ok": True, "execution_performed": skill_summary["execution_performed"]},
                ),
            )
        raise KeyError(f"unknown setup section: {name}")

    def first_task_payload(self) -> dict[str, Any]:
        command = terminal_command_name()
        return {
            "title": "AEGIS SETUP FIRST TASK",
            "workspace": str(self.paths.workspace),
            "status": "ready",
            "terminal_first": True,
            "browser_required": False,
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": False,
            "model_invocation_performed": False,
            "raw_secret_values_included": False,
            "examples": [
                f"{command} chat \"summarize this workspace\"",
                "read file README.md",
                "git status",
                "/subagents live review the current plan",
            ],
            "next": [
                f"Run `{command}` or `{command} tui` to use the live terminal composer.",
                "Use `/commands` inside the TUI for command lanes.",
                "Use `/setup run-checks` before configuring external routes.",
            ],
        }

    def run_checks(self) -> dict[str, Any]:
        indexed = MemoryStore(self.paths).index_curated_files()
        provider = ProviderStore(self.paths).doctor()
        connectors = ConnectorStore(self.paths).doctor()
        sections = [self.section(name).to_dict() for name in SETUP_SECTIONS]
        receipt = self.audit.append(
            "setup.check",
            {
                "external_action_started": False,
                "browser_auto_launch": False,
                "gateway_started": False,
                "model_invocation_performed": False,
                "send_probe_performed": False,
                "raw_secret_values_included": False,
                "memory_files_indexed": indexed,
                "provider_receipt": provider["receipt"],
                "connector_receipt": connectors["receipt"],
                "sections": [section["name"] for section in sections],
            },
        )
        return {
            "ok": True,
            "version": __version__,
            "workspace": str(self.paths.workspace),
            "state_dir": str(self.paths.state_dir),
            "metadata_only": True,
            "terminal_first": True,
            "browser_required": False,
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": False,
            "model_invocation_performed": False,
            "send_probe_performed": False,
            "raw_secret_values_included": False,
            "memory_files_indexed": indexed,
            "provider": provider,
            "connectors": connectors,
            "sections": sections,
            "receipt": receipt["id"],
        }


def format_setup_quickstart(payload: dict[str, Any]) -> str:
    command = terminal_command_name()
    lines = [str(payload["title"]), f"workspace  {payload['workspace']}", f"terminal   {command} tui", ""]
    priority = payload.get("priority") or {}
    if priority:
        lines.append(f"start here {command} setup next  (/setup next)")
        lines.append(f"opens      {priority['command']}  ({priority['slash_command']})")
        lines.append(f"why        {priority['reason']}")
        lines.append("")
    for index, section in enumerate(payload["steps"], start=1):
        lines.append(f"{index}. {section['name']:<10} {section['status']:<18} {section['summary']}")
        if section["commands"]:
            lines.append(f"   next: {section['commands'][0]}")
    lines.extend(["", f"No browser is launched by setup. Run `{command} setup --run-checks` for metadata-only verification."])
    return "\n".join(lines)


def format_setup_section(section: SetupSection) -> str:
    lines = [f"AEGIS SETUP :: {section.name}", f"status  {section.status}", "", section.summary, "", "commands"]
    lines.extend(f"- {command}" for command in section.commands)
    if section.checks:
        lines.extend(["", "checks"])
        for check in section.checks:
            lines.append("- " + json.dumps(check, sort_keys=True))
    lines.extend(
        [
            "",
            "safety",
            "- terminal_first: true",
            "- browser_required: false",
            "- browser_auto_launch: false",
            "- gateway_started: false",
            "- external_action_started: false",
            "- raw_secret_values_included: false",
        ]
    )
    return "\n".join(lines)


def format_setup_first_task(payload: dict[str, Any]) -> str:
    lines = [
        str(payload["title"]),
        f"workspace   {payload['workspace']}",
        f"status      {payload['status']}",
        "",
        "Try one safe terminal task. It uses the local terminal provider, audited typed tools, and no browser launch.",
        "",
        "examples",
    ]
    lines.extend(f"- {example}" for example in payload["examples"])
    lines.extend(
        [
            "",
            "safety",
            f"- terminal_first: {str(payload['terminal_first']).lower()}",
            f"- browser_required: {str(payload['browser_required']).lower()}",
            f"- browser_auto_launch: {str(payload['browser_auto_launch']).lower()}",
            f"- gateway_started: {str(payload['gateway_started']).lower()}",
            f"- external_action_started: {str(payload['external_action_started']).lower()}",
            f"- raw_secret_values_included: {str(payload['raw_secret_values_included']).lower()}",
            "",
            "next",
        ]
    )
    lines.extend(f"- {item}" for item in payload["next"])
    return "\n".join(lines)


def format_setup_next(priority: SetupPriority | dict[str, Any]) -> str:
    data = priority.to_dict() if isinstance(priority, SetupPriority) else priority
    lines = [
        "AEGIS SETUP :: next",
        "Start here: /setup next",
        f"step       {data['index']}/{data['total']} {data['section']}",
        f"status     {data['status']}",
        f"guided    {data['label']}",
        f"command    {data['command']}",
        f"tui        {data['slash_command']}",
        f"reason     {data['reason']}",
        "",
        "safety",
        f"- terminal_first: {str(data['terminal_first']).lower()}",
        f"- browser_required: {str(data['browser_required']).lower()}",
        f"- browser_auto_launch: {str(data['browser_auto_launch']).lower()}",
        f"- external_action_started: {str(data['external_action_started']).lower()}",
        "- model_invocation_performed: false",
        "- raw_secret_values_included: false",
        "",
        "then",
        f"- Run `{terminal_command_name()} setup --run-checks` after completing this step.",
        "- Use `/setup hide` when you want the setup wizard out of the default TUI.",
    ]
    return "\n".join(lines)


def normalize_setup_section(section: str | None) -> str:
    raw = (section or "").strip()
    return SETUP_ALIASES.get(raw, raw)
