from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.core.model_provider import ModelRequest, ModelResponse, provider_for_active_route
from aegisagent.core.provider_config import ProviderUsageStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.subagents import LocalSubagentOrchestrator
from aegisagent.core.web_tools import WebToolRunner
from aegisagent.core.workspace_tools import WorkspaceToolRunner
from aegisagent.security.audit import AuditLog


@dataclass(frozen=True, slots=True)
class RuntimeToolResult:
    name: str
    status: str
    content: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    session_id: str
    provider: str
    mode: str
    assistant_message: str
    receipt_id: str
    usage_id: str = ""
    tool_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "mode": self.mode,
            "assistant_message": self.assistant_message,
            "receipt_id": self.receipt_id,
            "usage_id": self.usage_id,
            "tool_results": list(self.tool_results),
        }


class AgentRuntime:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.sessions = SessionStore(paths)
        self.audit = AuditLog(paths)
        self.provider, self.provider_route = provider_for_active_route(paths)
        self.workspace_tools = WorkspaceToolRunner(paths)
        self.web_tools = WebToolRunner(paths)
        self.subagents = LocalSubagentOrchestrator(paths)

    def respond(self, prompt: str, *, session_id: str = "main", source: str = "tui") -> AgentTurnResult:
        session_query = _extract_session_search_query(prompt)
        session_matches = self.sessions.search(session_query, limit=8) if session_query else []
        session = self.sessions.append(session_id, "user", prompt, metadata={"source": source})
        tool_results = self.workspace_tools.run_for_prompt(prompt)
        fetch_url = _extract_fetch_url(prompt)
        if fetch_url:
            tool_results.append(self.web_tools.fetch(fetch_url, approved=False))
        if session_query:
            tool_results.append(
                RuntimeToolResult(
                    name="sessions.search",
                    status="ok",
                    content=_json_dumps({"query": session_query, "results": session_matches}),
                    metadata={"query": session_query, "result_count": len(session_matches), "limit": 8},
                )
            )
        if _should_delegate(prompt):
            delegation = self.subagents.delegate(prompt, parent_session_id=session.id)
            tool_results.append(
                RuntimeToolResult(
                    name="subagents.delegate",
                    status="ok",
                    content=delegation.announce_back,
                    metadata={
                        "root_id": delegation.root.id,
                        "worker_count": len(delegation.workers),
                        "worker_roles": [worker.role for worker in delegation.workers],
                        "event_count": len(delegation.events),
                        "receipt_id": delegation.receipt_id,
                    },
                )
            )
        for result in tool_results:
            tool_receipt = self.audit.append(
                "agent.tool.completed",
                {
                    "session_id": session.id,
                    "tool": result.name,
                    "status": result.status,
                    "metadata": result.metadata,
                    "external_action_started": result.metadata.get("external_action_started", False),
                    "browser_auto_launch": False,
                },
            )
            session = self.sessions.append(
                session.id,
                "tool",
                result.content,
                metadata={"source": "agent", "tool": result.name, "receipt_id": tool_receipt["id"], **result.metadata},
            )
        transcript = self.sessions.transcript(session.id, limit=20)
        response: ModelResponse = self.provider.complete(
            ModelRequest(
                prompt=prompt,
                session_id=session.id,
                transcript=transcript,
                workspace=self.paths.workspace,
                tool_results=[result.to_dict() for result in tool_results],
            )
        )
        session = self.sessions.append(
            session.id,
            "assistant",
            response.content,
            metadata={"source": "agent", "provider": response.provider, "mode": response.mode, **response.metadata},
        )
        receipt = self.audit.append(
            "agent.turn.completed",
            {
                "session_id": session.id,
                "provider": response.provider,
                "provider_mode": response.mode,
                "source": source,
                "prompt_chars": len(prompt),
                "assistant_chars": len(response.content),
                "tool_count": len(tool_results),
                "tools": [result.name for result in tool_results],
                "model_invocation_performed": True,
                "external_model_invocation_performed": bool(response.metadata.get("external_model_invocation_performed")),
                "provider_route_status": response.metadata.get("provider_route_status", ""),
                "primary_provider": response.metadata.get("primary_provider", ""),
                "fallback_used": bool(response.metadata.get("fallback_used")),
                "fallback_provider": response.metadata.get("fallback_provider", ""),
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        usage = ProviderUsageStore(self.paths).record(
            provider=response.provider,
            mode=response.mode,
            status="completed",
            session_id=session.id,
            source=source,
            prompt_chars=len(prompt),
            assistant_chars=len(response.content),
            external_model_invocation_performed=bool(response.metadata.get("external_model_invocation_performed")),
            provider_route_status=str(response.metadata.get("provider_route_status", "")),
            primary_provider=str(response.metadata.get("primary_provider", "")),
            fallback_used=bool(response.metadata.get("fallback_used")),
            fallback_provider=str(response.metadata.get("fallback_provider", "")),
            prompt_tokens=response.metadata.get("prompt_tokens") if isinstance(response.metadata.get("prompt_tokens"), int) else None,
            completion_tokens=response.metadata.get("completion_tokens") if isinstance(response.metadata.get("completion_tokens"), int) else None,
            total_tokens=response.metadata.get("total_tokens") if isinstance(response.metadata.get("total_tokens"), int) else None,
            receipt_id=receipt["id"],
            redacted=bool(response.metadata.get("redacted")),
        )
        return AgentTurnResult(
            session_id=session.id,
            provider=response.provider,
            mode=response.mode,
            assistant_message=response.content,
            receipt_id=receipt["id"],
            usage_id=usage["id"],
            tool_results=tuple(result.to_dict() for result in tool_results),
        )


def _should_delegate(prompt: str) -> bool:
    lower = prompt.lower()
    return any(term in lower for term in ("subagent", "sub-agent", "delegate", "parallel agents", "many agents"))


def _extract_session_search_query(prompt: str) -> str:
    lower = prompt.lower()
    for marker in ("search sessions for ", "session search ", "search transcripts for ", "search transcript for "):
        index = lower.find(marker)
        if index >= 0:
            return prompt[index + len(marker) :].strip().strip("'\"")[:120]
    return ""


def _extract_fetch_url(prompt: str) -> str:
    lower = prompt.lower()
    if "fetch" not in lower and "get url" not in lower and "read url" not in lower:
        return ""
    for raw in prompt.split():
        cleaned = raw.strip().strip("<>()[]{}'\".,;")
        if cleaned.startswith(("http://", "https://")):
            return cleaned
    return ""


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2)
