# Checkpoint 23 - Detached Task Workers

Status: top-level terminal tasks can run in detached worker processes

Decision:

- A durable task queue is not enough for Hermes-style operation if each task still blocks the foreground terminal.
- Normal queued tasks should be able to run out-of-band like subagent background jobs.
- Cancellation must update task state and terminate the worker process group when Aegis owns that process.

Implemented in this checkpoint:

- Added `pid` tracking to task records.
- Added detached task worker launch through `TaskRunner.start_background(...)`.
- Added `TaskRunner.submit_background(...)` to queue and start a task in one call.
- Worker processes run through the existing CLI path:
  - `python -m aegisagent --workspace <workspace> tasks --run <task-id>`
- Added deterministic test hooks:
  - `AEGISAGENT_TASK_NO_SPAWN=1`
  - `AEGISAGENT_TASK_SLEEP=<seconds>`
  - `AEGISAGENT_TASK_WORKER=1`
- Added task background receipts:
  - `task.background.queued`
  - `task.background.started`
  - `task.background.start_ignored`
- `TaskRunner.cancel(...)` now sends `SIGTERM` to a running task process group when a pid is present.
- Owned detached task processes are retained and reaped to keep warning-enabled test runs clean.
- CLI additions:
  - `aegisagent tasks --background "<request>"`
  - `aegisagent tasks --start <task-id>`
- TUI slash additions:
  - `/tasks bg <request>`
  - `/tasks start <task-id>`

Verified locally:

```bash
PYTHONPATH=src python3 -Wd -m unittest tests.test_terminal_agent_slice.GovernedTaskQueueTests.test_task_background_cancel_running_process -v
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
task_id=$(PYTHONPATH=src python3 -m aegisagent tasks --background 'background detached terminal task' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PYTHONPATH=src python3 -m aegisagent tasks --show "$task_id"
task_id=$(AEGISAGENT_TASK_SLEEP=5 PYTHONPATH=src python3 -m aegisagent tasks --background 'cancel detached terminal task' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PYTHONPATH=src python3 -m aegisagent tasks --cancel "$task_id"
PYTHONPATH=src python3 -m aegisagent tui
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Live progress streaming for detached task workers.
- Pause/resume semantics beyond cancellation.
- Multi-step autonomous queue loops.
- Durable recovery for a worker process killed by the OS without Aegis seeing the exit.
