from __future__ import annotations

from aegisagent.models import ToolSpec
from aegisagent.security.policy import decide_tool


DEFAULT_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("filesystem", "host", "on", "read/write cwd", "ask write", "medium", "Read workspace files and stage approved writes."),
    ToolSpec("shell", "process", "gated", "docker preferred", "ask risky", "medium", "Execute commands through policy and sandbox routing."),
    ToolSpec("git", "workspace", "on", "repo only", "ask push", "low", "Inspect and mutate git state with approval for writes."),
    ToolSpec("browser", "web", "gated", "session records", "ask open", "medium", "Record explicit browser sessions and screenshot evidence without surprise launch."),
    ToolSpec("network", "web", "gated", "allowlist", "ask", "high", "Fetch remote data only after approval or policy allowlist."),
    ToolSpec("secrets", "vault", "locked", "read handle", "never echo", "high", "Store handles to secret values without transcript echo."),
    ToolSpec("memory", "knowledge", "on", "user files", "ask write", "medium", "Search curated memory and indexed session records."),
    ToolSpec("skills", "extension", "on", "passive manifest", "auto", "low", "Discover SKILL.md folders and verify optional checksum manifests without execution."),
    ToolSpec("subagents", "orchestration", "on", "isolated sessions", "ask spawn", "medium", "Spawn bounded helper sessions with cascade stop."),
    ToolSpec("cron", "automation", "gated", "workspace jobs", "ask schedule", "medium", "Schedule local automation jobs with receipt trails."),
    ToolSpec("messaging", "adapter", "gated", "external delivery", "ask send", "high", "Prepare Slack/Teams/Discord/webhook adapters."),
    ToolSpec("mcp", "external", "gated", "registered servers", "ask connect", "high", "Register and invoke MCP-compatible external tools."),
)


class ToolRegistry:
    def __init__(self, tools: tuple[ToolSpec, ...] = DEFAULT_TOOLS):
        self._tools = {tool.name: tool for tool in tools}

    def list(self) -> list[dict[str, str]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def evaluate(self, name: str, action: str, *, approved: bool = False) -> dict:
        if name not in self._tools:
            decision = decide_tool(name, action, approved=approved)
            return {**decision.to_dict(), "known": False}
        decision = decide_tool(name, action, approved=approved)
        return {**decision.to_dict(), "known": True, "tool_spec": self._tools[name].to_dict()}


def enabled_counts() -> dict[str, int]:
    tools = DEFAULT_TOOLS
    return {
        "enabled": sum(1 for tool in tools if tool.status == "on"),
        "ask": sum(1 for tool in tools if "ask" in tool.approval or tool.status == "gated"),
        "blocked": sum(1 for tool in tools if tool.status in {"locked", "blocked"}),
        "total": len(tools),
    }
