from __future__ import annotations

import json
from typing import Any

from aegisagent.config import runtime_paths
from aegisagent.core.automation import AutomationRegistry
from aegisagent.core.browser_sessions import browser_summary
from aegisagent.core.capabilities import capability_map
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.dashboard import dashboard_payload
from aegisagent.core.improvement import improvement_summary
from aegisagent.core.provider_config import ProviderStore, ProviderUsageStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.setup_flow import SETUP_SECTIONS, SetupGuide
from aegisagent.core.subagents import BackgroundJobStore, SubagentStore, agent_contracts_payload, agent_status
from aegisagent.core.tasks import TaskStore
from aegisagent.core.tools import ToolRegistry
from aegisagent.security.audit import AuditLog
from aegisagent.security.policy import decide_tool


def app_factory(workspace: str | None = None) -> Any:
    try:
        from fastapi import FastAPI, HTTPException, WebSocket
        from fastapi.middleware.cors import CORSMiddleware
    except Exception as exc:
        raise RuntimeError("FastAPI is not installed. Install with `pip install -e .[gateway]`.") from exc

    paths = runtime_paths(workspace)
    audit = AuditLog(paths)
    connectors = ConnectorStore(paths)
    setup = SetupGuide(paths)
    tools = ToolRegistry()
    app = FastAPI(title="AegisAgent Gateway", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "audit": audit.verify(), "workspace": str(paths.workspace)}

    @app.get("/tools")
    def list_tools() -> list[dict]:
        return tools.list()

    @app.get("/audit")
    def audit_status() -> dict:
        payload = audit.verify()
        return {
            **payload,
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "metadata_only": True,
        }

    @app.get("/dashboard")
    def dashboard() -> dict:
        return dashboard_payload(paths)

    @app.get("/capabilities")
    def capabilities() -> dict:
        return capability_map(paths)

    @app.get("/capabilities/gaps")
    def capability_gaps() -> dict:
        payload = capability_map(paths)
        return {
            **payload,
            "title": "AEGIS CAPABILITY GAPS",
            "capabilities": payload["gaps"],
        }

    @app.get("/setup")
    def setup_quickstart() -> dict:
        return setup.quickstart()

    @app.get("/setup/run-checks")
    def setup_run_checks() -> dict:
        return setup.run_checks()

    @app.get("/setup/{section}")
    def setup_section(section: str) -> dict:
        if section not in SETUP_SECTIONS:
            raise HTTPException(status_code=404, detail=f"unknown setup section: {section}")
        return setup.section(section).to_dict()

    @app.get("/connectors")
    def connector_summary() -> dict:
        return connectors.summary()

    @app.get("/connectors/doctor")
    def connector_doctor() -> dict:
        return connectors.doctor()

    @app.get("/model/providers")
    def model_providers() -> dict:
        return ProviderStore(paths).summary()

    @app.get("/model/doctor")
    def model_doctor() -> dict:
        return ProviderStore(paths).doctor()

    @app.get("/model/usage")
    def model_usage(limit: int = 20) -> dict:
        return ProviderUsageStore(paths).summary(limit=limit)

    @app.get("/sessions")
    def sessions(limit: int = 20) -> dict:
        return {
            "workspace": str(paths.workspace),
            "sessions": SessionStore(paths).list(limit=limit),
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "metadata_only": True,
        }

    @app.get("/tasks")
    def tasks(limit: int = 20) -> dict:
        rows = TaskStore(paths).list(limit=limit)
        return {
            "workspace": str(paths.workspace),
            "task_count": len(rows),
            "tasks": rows,
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "metadata_only": True,
        }

    @app.get("/automations")
    def automations(limit: int = 20) -> dict:
        rows = AutomationRegistry(paths).list(limit=limit)
        return {
            "workspace": str(paths.workspace),
            "automation_count": len(rows),
            "automations": rows,
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "schedule_worker_started": False,
            "metadata_only": True,
        }

    @app.get("/improvements")
    def improvements() -> dict:
        return improvement_summary(paths)

    @app.get("/agents/status")
    def agents() -> dict:
        return agent_status(paths)

    @app.get("/agents/contracts")
    def agent_contracts() -> dict:
        return agent_contracts_payload(paths)

    @app.get("/subagents")
    def subagents(limit: int = 20) -> dict:
        rows = SubagentStore(paths).list(limit=limit)
        return {
            "workspace": str(paths.workspace),
            "subagent_count": len(rows),
            "subagents": rows,
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "metadata_only": True,
        }

    @app.get("/subagents/jobs")
    def subagent_jobs(limit: int = 20) -> dict:
        rows = BackgroundJobStore(paths).list(limit=limit)
        return {
            "workspace": str(paths.workspace),
            "job_count": len(rows),
            "jobs": rows,
            "terminal_first": True,
            "browser_auto_launch": False,
            "external_action_started": False,
            "metadata_only": True,
        }

    @app.get("/browser/sessions")
    def browser_sessions(limit: int = 20) -> dict:
        return browser_summary(paths, limit=limit)

    @app.post("/policy/{tool}")
    async def policy(tool: str, payload: dict) -> dict:
        action = str(payload.get("action", ""))
        approved = bool(payload.get("approved", False))
        decision = decide_tool(tool, action, approved=approved)
        audit.append("policy.decision", decision.to_dict())
        return decision.to_dict()

    @app.websocket("/ws")
    async def websocket(ws: WebSocket) -> None:
        await ws.accept()
        await ws.send_json({"type": "system", "message": "aegis gateway online", "audit": audit.verify()})
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            decision = decide_tool(str(payload.get("tool", "shell")), str(payload.get("action", "")), approved=bool(payload.get("approved", False)))
            receipt = audit.append("ws.event", {"input": payload, "decision": decision.to_dict()})
            await ws.send_json({"type": "policy", "decision": decision.to_dict(), "receipt": receipt["id"]})

    return app


def run_gateway(host: str, port: int, workspace: str | None = None) -> int:
    try:
        import uvicorn
    except Exception:
        print("FastAPI/uvicorn are not installed. Run: pip install -e .[gateway]")
        return 2
    uvicorn.run(app_factory(workspace), host=host, port=port)
    return 0
