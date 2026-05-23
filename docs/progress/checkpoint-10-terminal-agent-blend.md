# Checkpoint 10 - Terminal Agent Blend

Status: first terminal-first upgrade complete, broader Hermes-class build still active

Reference inspected:

- `MatthewLopez1990/Aegis-Agent` cloned read-only to `/tmp/aegis-agent-reference`.
- Useful executable reference files: `src/aegis/cli/main.py`, `src/aegis/tui/interactive.py`, `src/aegis/tui/main.py`, `src/aegis/product/setup.py`, `tests/test_tui.py`, and `tests/test_cli.py`.

Decision:

- Browser/Web GUI remains optional.
- `aegisagent tui` is the primary activation path.
- `aegisagent tui --print` is only a static fallback for CI/docs/snapshots.
- `aegisagent tui --classic` bypasses the curses UI and uses the fallback renderer.

Implemented in this checkpoint:

- Curses-backed prompt-first terminal UI in `src/aegisagent/tui/interactive.py`.
- Interactive panel model for agent status, active console, security posture, memory/skills, and slash palette.
- Slash commands: `/help`, `/setup`, `/tools`, `/audit`, `/memory`, `/skills`, `/sessions`, `/subagents`, `/policy shell`, `/run`, `/web`, `/status`, `/exit`, and `/quit`.
- Terminal prompt behavior: normal prompt capture, slash palette, Tab completion, arrow history/palette navigation, q/Esc exit, and mouse-click handling for terminals that emit mouse events.
- CLI routing so `aegisagent tui` attempts the interactive terminal UI before falling back.
- Tests for terminal activation, static fallback, panel model, slash palette, and prompt audit capture.
- Persistent terminal sessions in `.aegisagent/sessions`.
- Governed shell execution for short-lived commands through `aegisagent run` and `/run`.

Verified:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice -v
PYTHONPATH=src python3 -m aegisagent tui
```

The PTY smoke opened the curses UI and exited cleanly with `/exit`.

Still incomplete at checkpoint 10:

- Real model-provider execution loop. Checkpoint 11 adds the first local terminal provider; external routing is still incomplete.
- Broader tool execution backends beyond the current governed shell executor.
- Richer session UX beyond persisted terminal prompt/tool transcripts.
- Setup readiness payload matching the reference four-step wizard more closely.
- Actual multi-agent worker execution and orchestration.
- Broader migration of mature security, connectors, channels, MCP, browser, memory, skills, learning, and web-control-plane behavior from the reference repo.

Next checkpoint expectations covered by focused tests:

- Persist terminal session messages under workspace state in `.aegisagent/sessions`, reloadable by session ID.
- Plain TUI prompt dispatch should append a user message to the active `main` session while still recording the audit receipt. Checkpoint 11 upgrades this into user plus assistant messages through the local provider.
- Governed shell execution should run read-only commands such as `rg --files` through policy, capture stdout/stderr/return code, and write an audit receipt.
- Destructive or unapproved mutating shell commands must not execute; the runner should return a blocked result with a receipt while leaving workspace files intact.
- Acceptance tests for this slice live in `tests/test_terminal_agent_slice.py`.
