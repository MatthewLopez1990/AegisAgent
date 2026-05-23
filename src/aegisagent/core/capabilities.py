from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.core.automation import AutomationRegistry
from aegisagent.core.browser_sessions import BrowserSessionStore
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.improvement import ImprovementStore
from aegisagent.core.provider_config import ProviderUsageStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.subagents import BackgroundJobStore, SubagentStore
from aegisagent.core.tasks import TaskStore
from aegisagent.core.tools import enabled_counts
from aegisagent.security.audit import AuditLog


@dataclass(frozen=True, slots=True)
class Capability:
    key: str
    label: str
    status: str
    summary: str
    terminal: str
    next_step: str
    commands: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "summary": self.summary,
            "terminal": self.terminal,
            "next_step": self.next_step,
            "commands": list(self.commands),
        }


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "terminal_activation",
        "Terminal activation",
        "ready",
        "Default entrypoint opens the terminal UI in a TTY and prints an activation card outside one.",
        "primary",
        "Keep default launch terminal-first while web stays explicit.",
        ("aegisagent", "aegisagent activate", "aegisagent tui"),
    ),
    Capability(
        "prompt_first_tui",
        "Prompt-first TUI",
        "ready",
        "Composer, slash palette, setup deck, task monitors, and static fallback are available.",
        "primary",
        "Continue polishing narrow terminal copy and help density.",
        ("aegisagent tui", "aegisagent tui --print", "/commands"),
    ),
    Capability(
        "setup_wizard",
        "Setup wizard",
        "ready",
        "First launch opens terminal setup with provider, secrets, sandbox, connectors, memory, and checks.",
        "primary",
        "Add deeper provider-specific setup validation as routes mature.",
        ("aegisagent setup --quick", "aegisagent setup --run-checks", "/setup"),
    ),
    Capability(
        "policy_audit_security",
        "Policy, audit, and security",
        "ready",
        "Policy gates, secret redaction, sandbox posture, and append-only audit verification are in place.",
        "primary",
        "Expand receipts around future external and browser tool execution.",
        ("aegisagent tools", "aegisagent audit verify", "/policy shell rg --files"),
    ),
    Capability(
        "typed_workspace_tools",
        "Typed workspace tools",
        "partial",
        "Read, search, list, git status, git diff, approval-gated git staging, commit, branch operations, remote fetch/pull/push, allowlisted test runs, exact text replacement, and approval-gated web fetch are typed/audited.",
        "primary",
        "Add richer browser automation and approved connector actions behind receipts.",
        ("/read README.md", "/web fetch <url> | approve", "/edit replace"),
    ),
    Capability(
        "task_queue",
        "Governed task queue",
        "ready",
        "Top-level tasks can be queued, detached, watched, inspected, cancelled, and stale-recovered.",
        "primary",
        "Connect richer model-backed execution while preserving receipt trails.",
        ("aegisagent tasks --submit <request>", "aegisagent tasks --background <request>", "/tasks watch <id>"),
    ),
    Capability(
        "agents_subagents",
        "Agents and subagents",
        "partial",
        "Planner, researcher, implementer, and reviewer profiles run through bounded local subagents with visible role contracts, deliverables, budgets, isolated sessions, and audit receipts.",
        "primary",
        "Add stronger model routing and deeper role-specific tool execution.",
        ("aegisagent agents", "aegisagent agents contracts", "aegisagent agents delegate <task>", "/agents bg <task>"),
    ),
    Capability(
        "memory_sessions_skills",
        "Memory, sessions, and skills",
        "partial",
        "Local memory files, approval-gated curated memory writes, redacted session search, and SKILL.md discovery are available.",
        "primary",
        "Build memory review/delete controls and stronger skill trust metadata.",
        ("aegisagent memory --add <note> --title <title> --approved", "aegisagent sessions --query <text>", "/memory add"),
    ),
    Capability(
        "model_provider_routing",
        "Model provider routing",
        "partial",
        "Local provider is default; ready OpenAI-compatible API-key routes can serve terminal chat, failed attempted external calls fall back to the local provider, and usage is recorded in a terminal-visible ledger.",
        "primary",
        "Add multi-provider fallback ordering and subscription bridge readiness.",
        ("aegisagent chat <prompt>", "aegisagent model usage", "/model usage"),
    ),
    Capability(
        "connectors_messaging_mcp_browser",
        "Connectors, MCP, and browser",
        "metadata-ready",
        "Slack, Teams, webhook, MCP, browser, and Open WebUI readiness metadata is visible and gated; terminal web fetch and browser session records are available as approved actions.",
        "primary",
        "Add approved send/connect/open actions with explicit operator confirmation.",
        ("aegisagent connectors", "aegisagent browser sessions", "/browser open <url> | approve"),
    ),
    Capability(
        "gateway_web",
        "Gateway and Web GUI",
        "partial",
        "FastAPI gateway and web source are optional secondary surfaces; activation never auto-starts them.",
        "secondary",
        "Keep parity with terminal status without making web the default path.",
        ("aegisagent web", "aegisagent gateway", "/web"),
    ),
    Capability(
        "automations_cron",
        "Automations and schedules",
        "partial",
        "Durable schedule records can be created with interval, daily, weekday, weekend, weekly, monthly, month-end, timezone-aware, and local-date exception labels; checked for due state; checked for missed windows; replayed explicitly; ticked into governed tasks; run through an explicit foreground worker; inspected through persisted worker logs; packaged into an operator-loaded service wrapper; inspected for service status and health metrics; paused; resumed; deleted; and audited.",
        "primary",
        "Add broader typed tool execution and richer model-backed orchestration.",
        ("aegisagent automations due", "aegisagent automations missed", "/automations due"),
    ),
    Capability(
        "self_improvement_learning_loop",
        "Self-improvement loop",
        "partial",
        "Durable improvement proposals, failure classification, review gates, advisory repair candidates, read-only candidate diff reviews, candidate verification receipts, verified candidate apply-review handoffs, and evidence-backed implemented state are terminal-visible.",
        "primary",
        "Add external model routing and richer typed tool execution.",
        ("aegisagent improve diff <candidate-id>", "aegisagent improve verify <candidate-id>", "/improve apply <candidate-id>"),
    ),
    Capability(
        "browser_live_automation",
        "Browser sessions and evidence",
        "partial",
        "Approved browser session records and screenshot receipts are available without auto-launching a browser.",
        "secondary",
        "Add governed live browser control and screenshot capture when an operator explicitly asks for it.",
        ("aegisagent browser open <url> --approved", "aegisagent browser screenshot <id> <path> --approved", "/browser"),
    ),
    Capability(
        "remote_mobile_control",
        "Remote and mobile control",
        "planned",
        "No durable remote-control or mobile operator surface is implemented in this repo yet.",
        "planned",
        "Design remote auth, approvals, audit, and revocation before exposing it.",
        ("planned: remote operator console",),
    ),
)


def capability_map(paths: RuntimePaths) -> dict[str, Any]:
    ensure_runtime(paths)
    audit = AuditLog(paths).verify()
    connectors = ConnectorStore(paths).summary()
    tasks = TaskStore(paths).list(limit=1000)
    sessions = SessionStore(paths).list(limit=1000)
    automations = AutomationRegistry(paths).list(limit=1000)
    improvements = ImprovementStore(paths).list(limit=1000)
    usage = ProviderUsageStore(paths).summary(limit=1)
    browser_sessions = BrowserSessionStore(paths).list(limit=1000)
    capabilities = [capability.to_dict() for capability in CAPABILITIES]
    counts = {
        "ready": sum(1 for capability in capabilities if capability["status"] == "ready"),
        "partial": sum(1 for capability in capabilities if capability["status"] == "partial"),
        "metadata_ready": sum(1 for capability in capabilities if capability["status"] == "metadata-ready"),
        "planned": sum(1 for capability in capabilities if capability["status"] == "planned"),
        "total": len(capabilities),
    }
    return {
        "title": "AEGIS CAPABILITY MAP",
        "workspace": str(paths.workspace),
        "terminal_first": True,
        "browser_auto_launch": False,
        "browser_required": False,
        "external_action_started": False,
        "gateway_started": False,
        "counts": counts,
        "runtime": {
            "audit_chain_ok": audit["ok"],
            "audit_receipts": audit["count"],
            "tool_counts": enabled_counts(),
            "sessions": len(sessions),
            "tasks": len(tasks),
            "automations": len(automations),
            "improvements": len(improvements),
            "subagents": len(SubagentStore(paths).list(limit=1000)),
            "agent_jobs": len(BackgroundJobStore(paths).list(limit=1000)),
            "connectors": connectors["enabled_count"],
            "model_usage_records": usage["count"],
            "model_usage_tokens": usage["total_tokens"],
            "browser_sessions": len(browser_sessions),
        },
        "capabilities": capabilities,
        "gaps": [capability for capability in capabilities if capability["status"] != "ready"],
        "next": [
            "Use `aegisagent capabilities --gaps` or `/gaps` to see remaining Hermes-class backlog.",
            "Use `aegisagent setup --run-checks` before configuring external routes or connectors.",
            "Use `/agents bg <task>` for bounded terminal-first multi-agent work.",
        ],
    }


def format_capabilities(payload: dict[str, Any], *, gaps_only: bool = False) -> str:
    rows = payload["gaps"] if gaps_only else payload["capabilities"]
    title = "AEGIS CAPABILITY GAPS" if gaps_only else payload["title"]
    lines = [
        title,
        f"workspace   {payload['workspace']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()} "
            f"gateway_started={str(payload['gateway_started']).lower()}"
        ),
        (
            "counts      "
            f"ready={payload['counts']['ready']} "
            f"partial={payload['counts']['partial']} "
            f"metadata-ready={payload['counts']['metadata_ready']} "
            f"planned={payload['counts']['planned']} "
            f"total={payload['counts']['total']}"
        ),
        (
            "runtime     "
            f"audit={'ok' if payload['runtime']['audit_chain_ok'] else 'review'} "
            f"receipts={payload['runtime']['audit_receipts']} "
            f"tasks={payload['runtime']['tasks']} "
            f"automations={payload['runtime']['automations']} "
            f"improvements={payload['runtime']['improvements']} "
            f"subagents={payload['runtime']['subagents']} "
            f"jobs={payload['runtime']['agent_jobs']} "
            f"browser-sessions={payload['runtime']['browser_sessions']} "
            f"model-usage={payload['runtime']['model_usage_records']}"
        ),
        "",
    ]
    if not rows:
        lines.append("All tracked capabilities are marked ready.")
    for capability in rows:
        commands = ", ".join(capability["commands"][:3])
        lines.extend(
            [
                f"[{capability['status']}] {capability['label']}",
                f"  {capability['summary']}",
                f"  terminal: {capability['terminal']} | commands: {commands}",
                f"  next: {capability['next_step']}",
                "",
            ]
        )
    lines.append("next")
    lines.extend(f"- {item}" for item in payload["next"])
    return "\n".join(lines).rstrip()
