# Checkpoint 24 - Task Progress Events

Status: top-level task progress is persisted and visible from terminal commands

Decision:

- Detached task workers need more than final status; operators need a timeline they can inspect later.
- Task events should be persisted on disk so the foreground TUI and CLI can show progress without holding the worker process in memory.
- This should remain terminal-first and browser-optional.

Implemented in this checkpoint:

- Added `TaskEvent` records persisted to `.aegisagent/tasks/events.jsonl`.
- Added task event APIs:
  - `TaskStore.append_event(...)`
  - `TaskStore.events(...)`
  - `TaskRunner.events(...)`
- Added event emission for:
  - `submitted`
  - `background.queued`
  - `background.started`
  - `background.start_ignored`
  - `started`
  - `waiting`
  - `model.completed`
  - `completed`
  - `failed`
  - `cancelled`
  - `run.ignored`
  - `cancel.ignored`
  - `stopped`
- Added terminal formatting through `format_task_events(...)`.
- CLI addition: `aegisagent tasks --events <task-id>`.
- TUI slash addition: `/tasks events <task-id>` and `/tasks timeline <task-id>`.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
task_id=$(PYTHONPATH=src python3 -m aegisagent tasks --background 'evented detached terminal task' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PYTHONPATH=src python3 -m aegisagent tasks --events "$task_id"
PYTHONPATH=src python3 -m aegisagent tui
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Live repainting of task events while a detached worker is running.
- Streaming stdout/tool cards from task workers.
- Recovery marking for stale `running` tasks after process death.
