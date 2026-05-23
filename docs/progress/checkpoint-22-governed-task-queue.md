# Checkpoint 22 - Governed Task Queue

Status: durable top-level task controls added for terminal agent work

Decision:

- Subagent background jobs are useful, but normal prompt work also needs durable queue controls.
- A Hermes-style terminal agent should let the operator submit, inspect, run, and cancel top-level work without opening the browser.
- Task records should be redacted, persisted, and receipt-backed before execution.

Implemented in this checkpoint:

- Added `.aegisagent/tasks/` runtime state.
- Added `TaskRecord`, `TaskStore`, and `TaskRunner`.
- Task lifecycle states: `queued`, `running`, `completed`, `failed`, `cancelled`.
- Task receipts:
  - `task.submitted`
  - `task.started`
  - `task.completed`
  - `task.failed`
  - `task.cancelled`
  - ignored run/cancel receipts for terminal states.
- CLI additions:
  - `aegisagent tasks --submit "<request>"`
  - `aegisagent tasks --run <task-id>`
  - `aegisagent tasks --show <task-id>`
  - `aegisagent tasks --cancel <task-id>`
  - `aegisagent tasks`
- TUI slash additions:
  - `/tasks`
  - `/tasks submit <request>`
  - `/tasks run <task-id>`
  - `/tasks show <task-id>`
  - `/tasks cancel <task-id>`
  - `/q <request>`
- Completed tasks run through the existing `AgentRuntime`, so typed tools, session transcripts, redaction, and audit receipts remain shared with normal `chat` and TUI prompt turns.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
task_id=$(PYTHONPATH=src python3 -m aegisagent tasks --submit 'draft a safe terminal task plan' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PYTHONPATH=src python3 -m aegisagent tasks --run "$task_id"
PYTHONPATH=src python3 -m aegisagent tui
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Detached process execution for normal tasks.
- Pause/resume while a task is actively running.
- Task event streaming and progress cards in the curses view.
- Multi-step autonomous loops over the queue.
