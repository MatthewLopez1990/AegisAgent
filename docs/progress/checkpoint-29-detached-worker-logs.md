# Checkpoint 29 - Detached Worker Logs

Status: detached task worker stdout/stderr is captured for terminal inspection

Decision:

- Background work should not disappear behind `/dev/null`.
- Detached workers should leave a terminal-readable trail even when the main TUI session is not attached to the worker process.
- The watch view should show task state, events, recorded assistant/tool output, and raw worker logs in one place.

Implemented in this checkpoint:

- Detached task workers now write stdout to `.aegisagent/tasks/<task-id>.stdout.log`.
- Detached task workers now write stderr to `.aegisagent/tasks/<task-id>.stderr.log`.
- Added `TaskRunner.worker_logs(...)`.
- Added terminal formatting through `format_task_worker_logs(...)`.
- CLI addition: `aegisagent tasks --logs <task-id>`.
- TUI slash addition: `/tasks logs <task-id>`.
- `/tasks watch <task-id>` now includes worker stdout/stderr logs after the task output section.
- Updated README task queue examples and current-gap wording.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
AEGISAGENT_TASK_SLEEP=0.1 PYTHONPATH=src python3 -m aegisagent tasks --background 'runtime worker log smoke'
PYTHONPATH=src python3 -m aegisagent tasks --logs <task-id>
# expect-driven PTY smoke: /tasks watch <task-id> matched AEGIS TASK WORKER LOGS and completed, then exited with return code 0
```

Still incomplete:

- Nonblocking watch that keeps the composer usable while monitoring.
- External model routing through setup.
- Broader model-backed multi-agent worker loops with richer independent tool contexts.
