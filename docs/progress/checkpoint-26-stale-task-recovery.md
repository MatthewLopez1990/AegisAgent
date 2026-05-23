# Checkpoint 26 - Stale Task Recovery

Status: stale detached task workers can be recovered from the terminal

Decision:

- A detached worker can die before it writes a terminal task state.
- Operators need an audited terminal command that corrects stuck `running` tasks whose worker pid is gone.
- Recovery should reuse task events and audit receipts so the correction is visible later.

Implemented in this checkpoint:

- Added `TaskRunner.recover_stale_running(...)`.
- Running tasks with a missing worker pid are marked `failed`, cleared of pid, and given a recovery summary.
- Added `task.recovered_stale` audit receipts.
- Added `recovered.stale` task timeline events.
- CLI addition: `aegisagent tasks --recover-stale`.
- TUI slash addition: `/tasks recover` and `/tasks recover-stale`.
- Added slash palette and command lane entries for `/tasks recover`.
- Updated README task queue command lists.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Automatic recovery on task listing or TUI startup.
- Streaming stdout/tool cards from task workers.
- Nonblocking watch that keeps the composer usable while monitoring.
