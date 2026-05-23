# Checkpoint 11 - Local Terminal Agent Loop

Status: local request-response loop implemented, broader Hermes-class build still active

Decision:

- Normal terminal prompt input now creates an assistant turn instead of only capturing the user message.
- The first provider is intentionally local and deterministic, so the terminal shell works without browser launch, network access, API keys, or external model routing.
- External provider setup remains a later governed checkpoint.

Implemented in this checkpoint:

- `src/aegisagent/core/model_provider.py` defines the provider request/response boundary and `LocalTerminalProvider`.
- `src/aegisagent/core/agent.py` defines `AgentRuntime`, appending user and assistant messages to persistent sessions and writing `agent.turn.completed` audit receipts.
- `aegisagent chat "<prompt>"` runs one non-curses terminal agent turn for smoke testing and automation.
- Plain TUI prompt dispatch now calls `AgentRuntime.respond(...)`, prints the assistant message, and records the receipt ID.
- Existing `/run` remains the governed shell execution path, separate from normal prompt turns.

Verification added:

- CLI coverage for `aegisagent chat "draft a safe plan" --json`.
- TUI dispatch coverage for local agent turns and `agent.turn.completed` receipts.
- Session coverage proving prompt dispatch writes both `user` and `assistant` messages.
- Runtime coverage proving local provider metadata records that no external model invocation occurred.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli -v
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_terminal_agent_slice -v
PYTHONPATH=src python3 -m aegisagent chat 'summarize this workspace' --json
```

Still incomplete:

- External model-provider routing through setup.
- Tool-calling inside the agent loop.
- Long-running/background process sessions.
- Actual multi-agent worker execution and orchestration.
- Broader Hermes/OpenClaw parity across connectors, memory, browser control, MCP, learning, and web control plane.
