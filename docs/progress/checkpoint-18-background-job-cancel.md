# Checkpoint 18 - Background Job Cancel

Status: cancellable background subagent jobs implemented

Decision:

- Long-running terminal agent work needs an operator cancellation path.
- Cancellation should update persisted job state and leave audit evidence.
- Background worker processes should launch in their own process group so cancellation can target the job cleanly.

Implemented in this checkpoint:

- Background subagent workers now launch with `start_new_session=True`.
- `LocalSubagentOrchestrator.cancel_background(...)` marks queued/running jobs as `cancelled`.
- Running jobs receive `SIGTERM` through their process group when a pid is still alive.
- Cancelled jobs persist `completed_at` and `summary`.
- Cancellation writes `subagent.background.cancelled`; ignored cancellation of terminal states writes `subagent.background.cancel_ignored`.
- CLI addition: `aegisagent subagents --cancel <job-id>`.
- TUI addition: `/subagents cancel <job-id>`.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_cli tests.test_tui -v
```

Still incomplete:

- Grace-period escalation from SIGTERM to SIGKILL.
- In-place cancellation buttons/progress cards in the curses UI.
- Cancellation propagation into future model-backed tool calls.
