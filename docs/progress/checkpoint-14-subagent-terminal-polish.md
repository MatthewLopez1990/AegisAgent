# Checkpoint 14 - Subagent Terminal Polish

Status: cleaner terminal subagent UX and bounded concurrent local execution implemented

Decision:

- Subagents should be visible as terminal work, not raw JSON dumps in the TUI.
- Local worker execution should be bounded and concurrent, even before external model-backed subagents are wired.
- Stopping a subagent tree should persist to workspace state and leave an audit receipt.

Implemented in this checkpoint:

- `LocalSubagentOrchestrator.delegate(...)` now runs worker summaries through a bounded `ThreadPoolExecutor`.
- Each worker emits `subagent.worker.started` and `subagent.worker.completed` receipts.
- `SubagentStore.cascade_stop(...)` marks a persisted subagent tree as stopped.
- `LocalSubagentOrchestrator.stop(...)` writes a `subagent.cascade_stopped` receipt.
- `/subagents <task>` now prints a compact terminal summary instead of JSON.
- `/subagents list` prints a readable table of persisted records.
- `/subagents stop <id>` stops a persisted tree and prints a compact receipt summary.
- `aegisagent subagents --stop <id>` exposes cascade stop through the CLI.
- SQLite audit and memory helpers now explicitly close database connections to avoid Python 3.14 resource warnings.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_tui tests.test_cli tests.test_terminal_agent_slice -v
PYTHONPATH=src python3 -m aegisagent subagents --delegate 'improve terminal orchestration'
```

Still incomplete:

- True model-backed concurrent subagents with independent tool contexts.
- Live streaming progress cards inside the curses layout while workers run.
- Approval-aware cancellation of long-running external tools.
- Worker artifact passing and final synthesis beyond deterministic local summaries.
