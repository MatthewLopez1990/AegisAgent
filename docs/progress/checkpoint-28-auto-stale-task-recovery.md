# Checkpoint 28 - Automatic Stale Task Recovery

Status: normal terminal task supervision now self-heals stale detached workers

Decision:

- Operators should not need to know a separate recovery command before trusting the task list or watch view.
- Listing, showing, or watching tasks are supervision actions, so they should first reconcile dead worker pids.
- Manual recovery remains available, but the common terminal paths should not leave obviously dead work marked `running`.

Implemented in this checkpoint:

- Added `TaskRunner.get(..., recover_stale=True)`.
- Added `TaskRunner.list(..., recover_stale=True)`.
- CLI task listing and `--show` now automatically recover stale running records before printing.
- TUI `/tasks`, `/tasks show <id>`, and `/tasks watch <id>` now automatically recover stale running records before rendering.
- Existing recovery remains audited through `task.recovered_stale` and visible through `recovered.stale` task events.
- Updated README to document automatic recovery on normal task supervision paths.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
```

Still incomplete:

- True live stdout/stderr streaming from detached worker processes while they are running.
- Nonblocking watch that keeps the composer usable while monitoring.
- External model routing through setup.
