from __future__ import annotations

from typing import Any

from aegisagent import __version__
from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.core.activation import terminal_activation_payload
from aegisagent.core.automation import AutomationRegistry
from aegisagent.core.browser_sessions import BrowserSessionStore
from aegisagent.core.capabilities import capability_map
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.improvement import ImprovementStore
from aegisagent.core.provider_config import ProviderStore, ProviderUsageStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.subagents import BackgroundJobStore, SubagentStore, agent_contracts_payload
from aegisagent.core.tasks import TaskStore
from aegisagent.core.tools import enabled_counts
from aegisagent.security.audit import AuditLog
from aegisagent.security.sandbox import detect_sandbox


def dashboard_payload(paths: RuntimePaths) -> dict[str, Any]:
    ensure_runtime(paths)
    audit = AuditLog(paths).verify()
    capabilities = capability_map(paths)
    provider = ProviderStore(paths).summary()
    connectors = ConnectorStore(paths).summary()
    activation = terminal_activation_payload(paths)
    contracts = agent_contracts_payload(paths)
    sandbox = detect_sandbox().to_dict()
    tasks = TaskStore(paths).list(limit=1000)
    sessions = SessionStore(paths).list(limit=1000)
    automations = AutomationRegistry(paths).list(limit=1000)
    improvements = ImprovementStore(paths).list(limit=1000)
    subagents = SubagentStore(paths).list(limit=1000)
    jobs = BackgroundJobStore(paths).list(limit=1000)
    browser_sessions = BrowserSessionStore(paths).list(limit=1000)
    usage = ProviderUsageStore(paths).summary(limit=5)
    gap_rows = capabilities["gaps"]
    return {
        "title": "AEGIS TERMINAL DASHBOARD",
        "version": __version__,
        "workspace": str(paths.workspace),
        "terminal_first": True,
        "browser_required": False,
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
        "metadata_only": True,
        "activation": {
            "primary_command": activation["primary_command"],
            "default_entrypoint": activation["default_entrypoint"],
            "fallback": activation["fallback"],
        },
        "safety": {
            "audit_chain_ok": audit["ok"],
            "audit_receipts": audit["count"],
            "sandbox": sandbox,
            "tools": enabled_counts(),
        },
        "runtime": {
            "sessions": len(sessions),
            "tasks": len(tasks),
            "automations": len(automations),
            "improvements": len(improvements),
            "subagents": len(subagents),
            "agent_jobs": len(jobs),
            "browser_sessions": len(browser_sessions),
            "model_usage_records": usage["count"],
        },
        "model": {
            "active_provider": provider["active_provider"],
            "mode": provider["mode"],
            "browser_required": provider["browser_required"],
        },
        "connectors": {
            "enabled_count": connectors["enabled_count"],
            "available_count": len(connectors["connectors"]),
            "external_delivery_performed": connectors["external_delivery_performed"],
            "browser_auto_launch": connectors["browser_auto_launch"],
        },
        "capabilities": {
            "counts": capabilities["counts"],
            "top_gaps": [
                {
                    "label": item["label"],
                    "status": item["status"],
                    "next_step": item["next_step"],
                }
                for item in gap_rows[:5]
            ],
        },
        "agents": {
            "contract_version": contracts["contract_version"],
            "profiles": [profile["role"] for profile in contracts["profiles"]],
            "limits": contracts["limits"],
        },
        "next": [
            "Run `aegisagent tui` for the prompt-first terminal UI.",
            "Run `/agents contracts` before delegating multi-agent work.",
            "Run `/gaps` to continue closing Hermes-class gaps.",
            "Use `/web` only when you explicitly want optional browser instructions.",
        ],
    }


def format_dashboard(payload: dict[str, Any]) -> str:
    runtime = payload["runtime"]
    safety = payload["safety"]
    tools = safety["tools"]
    counts = payload["capabilities"]["counts"]
    sandbox = safety["sandbox"]
    connectors = payload["connectors"]
    model = payload["model"]
    agents = payload["agents"]
    lines = [
        payload["title"],
        f"workspace   {payload['workspace']}",
        f"activate    {payload['activation']['primary_command']}  (default: {payload['activation']['default_entrypoint']})",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()} "
            f"gateway_started={str(payload['gateway_started']).lower()}"
        ),
        "",
        "runtime",
        f"- audit      {'ok' if safety['audit_chain_ok'] else 'review'} receipts={safety['audit_receipts']}",
        f"- sandbox    {sandbox['backend']} host_approval={str(sandbox['host_execution_requires_approval']).lower()}",
        f"- tools      {tools['enabled']} enabled / {tools['ask']} ask / {tools['blocked']} blocked",
        f"- work       tasks={runtime['tasks']} automations={runtime['automations']} improvements={runtime['improvements']}",
        f"- agents     subagents={runtime['subagents']} jobs={runtime['agent_jobs']} contracts={agents['contract_version']}",
        f"- sessions   transcripts={runtime['sessions']} browser_sessions={runtime['browser_sessions']}",
        "",
        "routes",
        f"- model      {model['active_provider']} mode={model['mode']} browser_required={str(model['browser_required']).lower()}",
        f"- connectors enabled={connectors['enabled_count']}/{connectors['available_count']} delivery={str(connectors['external_delivery_performed']).lower()}",
        "",
        "capability posture",
        f"- ready={counts['ready']} partial={counts['partial']} metadata-ready={counts['metadata_ready']} planned={counts['planned']}",
    ]
    for gap in payload["capabilities"]["top_gaps"]:
        lines.append(f"- {gap['status']:<14} {gap['label']}: {gap['next_step']}")
    lines.extend(["", "next"])
    lines.extend(f"- {item}" for item in payload["next"])
    return "\n".join(lines)
