# Checkpoint 16 - Live Subagent Stream

Status: subagent events can stream into CLI and curses TUI while delegation runs

Decision:

- A terminal agent should show work as it happens, not only after a final JSON result.
- The orchestrator should expose a reusable event sink so CLI, TUI, and future model-backed workers can share one event stream.
- The live path stays terminal-first and does not start the web gateway or browser.

Implemented in this checkpoint:

- `LocalSubagentOrchestrator.delegate(...)` accepts `event_sink`.
- Every persisted `SubagentEvent` is also sent to the sink in order.
- `format_event_line(...)` renders single-line timeline updates for live terminals.
- `aegisagent subagents --stream "<task>"` prints `SUBAGENT LIVE` and event lines as the delegation runs, followed by root id, receipt id, and final status.
- `/subagents live <task>` in the curses TUI repaints the transcript as events arrive.
- `/subagents live <task>` also has a static fallback through `dispatch_interactive_command(...)` for non-curses tests and snapshots.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent subagents --stream 'improve live terminal feedback'
```

Still incomplete:

- Non-blocking background TUI workers that leave the composer active while running.
- Rich in-place progress cards with per-worker elapsed time.
- True model-backed workers with independent tool contexts.
- Approval-aware cancellation for long-running external tools.
