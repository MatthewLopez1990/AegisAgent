# AegisAgent Security-First Hermes/OpenClaw Build Plan

## Summary
Build `AegisAgent` from this mostly empty repo into a security-grounded autonomous agent platform with Hermes/OpenClaw-style capabilities, but with visible governance as the core product. The implementation should scaffold a Python core, Textual-based TUI, FastAPI/WebSocket backend, and React Web GUI that mirrors the TUI design in `ReferenceImages/`.

Research basis:
- Hermes: self-improving agent, tools, memory, subagents, messaging gateway, sandboxing, approvals, skills, and multi-platform surfaces from the official docs: [overview](https://hermes-agent.nousresearch.com/docs/), [tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/), [skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/), [memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory), [security](https://hermes-agent.nousresearch.com/docs/user-guide/security), [messaging](https://hermes-agent.nousresearch.com/docs/user-guide/messaging).
- OpenClaw: gateway-first TUI/Web model, typed tools, sessions, subagents, tool policy, skills, approvals, browser control, and security posture from official docs: [TUI](https://openclawlab.com/en/docs/web/tui/), [tools](https://openclawlab.com/en/docs/tools/), [subagents](https://openclawlab.com/en/docs/tools/subagents/), [skills](https://openclawlab.com/en/docs/tools/skills/), [security](https://openclawlab.com/en/docs/gateway/security/).
- Security threat model: OpenClaw-style agents create high attack surface through high-privilege execution and sensitive integrations, so Aegis must default to least privilege, sandboxing, visible approvals, secret redaction, and audit receipts: [Taming OpenClaw](https://arxiv.org/abs/2603.11619), [Your Agent, Their Asset](https://arxiv.org/abs/2604.04759).

## Goal Prompt For Codex
Create a security-focused autonomous agent platform in `/Users/matthewlopez/Code Projects/AegisAgent` named `AegisAgent`. It must provide Hermes/OpenClaw-level capabilities through a security-first architecture: prompt-first TUI, matching Web GUI, gateway backend, typed tool registry, skills system, memory/session search, sandboxed execution, browser/web/file/git/shell tools, subagent orchestration, cron/automation, messaging-ready adapters, policy approvals, redacted secrets, append-only audit receipts, and health/readiness commands.

Use these skills during execution:
- `tui-design`
- `tui-designer`
- `tui-design-taste`
- `tui-agent-design-pack`
- `frontend-design`

Use `ReferenceImages/Secure TUI setup view.png`, `ReferenceImages/Secure TUI tools matrix.png`, and `ReferenceImages/Secure TUI command view.png` as the visual contract. The TUI is the source design; the Web GUI should be a clickable GUI translation of the same security console.

Run implementation in checkpoints. At each checkpoint, spawn parallel subagents where useful, record progress in `docs/progress/`, run focused tests, and verify with CLI/TUI/Web smoke checks before moving on.

## Key Changes
- Scaffold a Python 3.12 project with `src/aegisagent/`, `tests/`, `docs/`, `web/`, `pyproject.toml`, `README.md`, and `Makefile`.
- Core runtime:
  - `aegisagent gateway`: FastAPI + WebSocket control plane for TUI/Web clients.
  - `aegisagent tui`: Textual prompt-first console matching the reference images.
  - `aegisagent web`: starts API plus React/Vite Web GUI.
  - `aegisagent setup`, `health`, `audit verify`, `tools`, `skills`, `memory`, `sessions`, `subagents`.
- Security model:
  - Default deny for network, shell writes, host execution, secret echo, external delivery, and elevated actions.
  - Docker sandbox preferred for shell/code execution; host execution requires explicit approval.
  - Hard blocklist for destructive commands even when approvals are relaxed.
  - Policy engine returns `allow`, `ask`, `deny`, risk level, rationale, and receipt id for every tool call.
  - Append-only SQLite + JSONL audit chain with hash verification and redacted transcript storage.
- Agent abilities:
  - Tool groups equivalent to Hermes/OpenClaw: filesystem, git, shell/process, web search/fetch, browser automation, memory/session search, skills, subagents, cron, messaging adapters, MCP-compatible external tools.
  - Skills follow `SKILL.md` / AgentSkills-compatible folders with bundled, global, and workspace scopes.
  - Memory includes curated `MEMORY.md` / `USER.md` plus SQLite FTS session search.
  - Subagents support max concurrency `8`, max depth `2`, max children per agent `5`, isolated sessions, separate audit receipts, cascade stop, and summarized announce-back.
- TUI:
  - Prompt-first stable layout with transcript/composer always reachable.
  - Right security posture pane, approval card, slash palette, setup wizard, tools matrix, audit receipt viewer.
  - Shortcuts: `Tab`, `Shift+Tab`, `Enter`, `Esc`, `/`, `?`, `:`, `q`, plus visible footer.
  - Must support 80x24, 120x40, 200x60, no-color mode, and keyboard-only operation.
- Web GUI:
  - React/Vite app using the same semantic tokens and layout hierarchy as the TUI.
  - Clickable panels for chat, approvals, tool policy, audit log, subagents, setup, memory, skills, and settings.
  - WebSocket streaming for messages, tool cards, approval events, subagent status, and audit receipts.

## Execution Checkpoints
1. Foundation and architecture: scaffold repo, CLI, config, SQLite schema, docs, and shared event models.
2. Security kernel: policy engine, command classifier, approvals, secret redaction, audit chain, sandbox interface.
3. Agent loop and tools: model provider abstraction, typed tools, process/background sessions, web/browser/file/git tools.
4. Memory and skills: curated memory files, FTS session search, skill loader, skill bundle support, security scan/quarantine for skills.
5. Subagents and automation: `sessions_spawn`, subagent queue, cascade stop, cron jobs, announce-back, progress telemetry.
6. TUI implementation: Textual app matching reference images and requested TUI skills.
7. Web GUI implementation: React console matching TUI design with clickable controls.
8. Messaging/MCP readiness: adapter interfaces for Slack/Discord/Teams/Webhooks/Open WebUI-style surfaces and MCP server registry.
9. Verification and handoff: docs, screenshots, terminal-size checks, browser checks, health/readiness output, final progress log.

## Test Plan
- Unit tests for policy decisions, redaction, command blocklist, sandbox routing, tool schema validation, audit hash chain, session storage, memory limits, and subagent queue rules.
- Integration tests for CLI commands: `setup`, `health`, `audit verify`, `tools`, `skills`, `subagents`, `gateway`.
- TUI smoke tests in a PTY at 80x24, 120x40, and 200x60; verify no layout break, composer reachable, help overlay works, approvals keyboard flow works.
- Web tests with Playwright/Browser: desktop and narrow layouts, WebSocket chat streaming, approval buttons, audit viewer, setup wizard, tools matrix.
- Security acceptance: no secret appears in transcript/audit output; destructive commands fail closed; host writes/network require visible approval; audit verification detects tampering.

## Assumptions
- The repo now has a checkpointed terminal-first foundation; continue by extending the current implementation instead of treating it as blank.
- Python core + Textual TUI + FastAPI backend + React Web GUI is the chosen stack.
- Hermes/OpenClaw are comparison targets, not code to copy directly.
- “Same abilities” means parity by capability class, with Aegis-specific security controls taking precedence over exact UX or internal implementation.
- Subagent fan-out is aggressive but bounded: global concurrency `8`, depth `2`, children per agent `5`.
