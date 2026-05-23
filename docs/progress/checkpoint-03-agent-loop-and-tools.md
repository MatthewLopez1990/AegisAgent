# Checkpoint 03 - Agent Loop And Tools

Status: scaffolded

Implemented:

- Typed tool registry with filesystem, shell, git, browser, network, secrets, memory, skills, subagents, cron, messaging, and MCP capability classes.
- Policy evaluation path for tool actions.
- CLI surface for `aegisagent tools --matrix` and `aegisagent tools --evaluate`.
- Optional WebSocket gateway that evaluates policy events and writes audit receipts.

Remaining production work:

- Actual model-provider invocation loop.
- Sandboxed command execution backend.
- Browser automation adapter implementation.
