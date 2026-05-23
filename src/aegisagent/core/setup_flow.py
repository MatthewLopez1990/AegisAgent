from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aegisagent import __version__
from aegisagent.config import RuntimePaths
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.memory import MemoryStore
from aegisagent.core.provider_config import ProviderStore
from aegisagent.core.skills import SkillLoader
from aegisagent.core.tools import enabled_counts
from aegisagent.security.audit import AuditLog
from aegisagent.security.sandbox import detect_sandbox


SETUP_SECTIONS = ("model", "secrets", "sandbox", "tools", "connectors", "memory")


@dataclass(frozen=True, slots=True)
class SetupSection:
    name: str
    status: str
    summary: str
    commands: tuple[str, ...]
    checks: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "commands": list(self.commands),
            "checks": list(self.checks),
        }


class SetupGuide:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.audit = AuditLog(paths)

    def quickstart(self) -> dict[str, Any]:
        sections = [self.section(name) for name in SETUP_SECTIONS]
        return {
            "title": "AEGIS SETUP QUICKSTART",
            "version": __version__,
            "workspace": str(self.paths.workspace),
            "metadata_only": True,
            "terminal_first": True,
            "browser_required": False,
            "steps": [section.to_dict() for section in sections],
            "next": [
                "1. Run `aegisagent setup model` or `/setup model`.",
                "2. Run `aegisagent setup --run-checks` or `/setup run-checks`.",
                "3. Launch `aegisagent tui` and keep working from the terminal composer.",
            ],
        }

    def section(self, name: str) -> SetupSection:
        if name == "model":
            provider = ProviderStore(self.paths).summary()
            return SetupSection(
                "model",
                str(provider.get("mode") or "unknown"),
                f"Active provider: {provider.get('active_provider', '')}. Configure external routes by environment-variable handle, not raw secret.",
                (
                    "aegisagent model providers",
                    "aegisagent model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY",
                    "aegisagent model doctor",
                ),
                tuple({"name": route["name"], "status": route["status"]} for route in provider.get("routes", [])),
            )
        if name == "secrets":
            return SetupSection(
                "secrets",
                "handles_only",
                "Secrets are referenced by handles such as environment variable names; raw secret values are not stored in setup config or audit payloads.",
                ("export OPENAI_API_KEY=...", "aegisagent model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY"),
                ({"name": "raw_secret_values_included", "ok": False},),
            )
        if name == "sandbox":
            sandbox = detect_sandbox()
            return SetupSection(
                "sandbox",
                sandbox.backend,
                sandbox.rationale,
                ("aegisagent health", "/status", "/policy shell rg --files"),
                (sandbox.to_dict(),),
            )
        if name == "tools":
            counts = enabled_counts()
            return SetupSection(
                "tools",
                "policy_gated",
                f"{counts['enabled']} tools enabled, {counts['ask']} actions require approval.",
                ("aegisagent tools --matrix", "/tools", "/policy shell <command>"),
                (counts,),
            )
        if name == "connectors":
            connector_summary = ConnectorStore(self.paths).summary()
            return SetupSection(
                "connectors",
                f"{connector_summary['enabled_count']}_enabled",
                "Slack, Teams, webhooks, MCP, browser, and Open WebUI adapters are tracked as local metadata; none can deliver externally without explicit future approval.",
                ("aegisagent connectors", "aegisagent connectors doctor", "aegisagent connectors configure slack --token-env SLACK_BOT_TOKEN --enable"),
                (
                    {"name": "external_delivery", "default": "ask", "external_delivery_performed": connector_summary["external_delivery_performed"]},
                    {"name": "browser_auto_launch", "ok": connector_summary["browser_auto_launch"]},
                    *tuple({"name": item["name"], "status": item["status"], "approval": item["approval"]} for item in connector_summary["connectors"]),
                ),
            )
        if name == "memory":
            skills = SkillLoader([self.paths.skills_dir]).discover()
            return SetupSection(
                "memory",
                "local",
                "Workspace memory and skill discovery stay local unless a future connector is explicitly configured.",
                ("aegisagent memory --index", "aegisagent skills", "/memory", "/skills"),
                ({"name": "skills_found", "count": len(skills)},),
            )
        raise KeyError(f"unknown setup section: {name}")

    def run_checks(self) -> dict[str, Any]:
        indexed = MemoryStore(self.paths).index_curated_files()
        provider = ProviderStore(self.paths).doctor()
        connectors = ConnectorStore(self.paths).doctor()
        sections = [self.section(name).to_dict() for name in SETUP_SECTIONS]
        receipt = self.audit.append(
            "setup.check",
            {
                "external_action_started": False,
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
    lines = [str(payload["title"]), f"workspace  {payload['workspace']}", "terminal   aegisagent tui", ""]
    for index, section in enumerate(payload["steps"], start=1):
        lines.append(f"{index}. {section['name']:<10} {section['status']:<18} {section['summary']}")
        if section["commands"]:
            lines.append(f"   next: {section['commands'][0]}")
    lines.extend(["", "No browser is launched by setup. Run `aegisagent setup --run-checks` for metadata-only verification."])
    return "\n".join(lines)


def format_setup_section(section: SetupSection) -> str:
    lines = [f"AEGIS SETUP :: {section.name}", f"status  {section.status}", "", section.summary, "", "commands"]
    lines.extend(f"- {command}" for command in section.commands)
    if section.checks:
        lines.extend(["", "checks"])
        for check in section.checks:
            lines.append("- " + json.dumps(check, sort_keys=True))
    return "\n".join(lines)
