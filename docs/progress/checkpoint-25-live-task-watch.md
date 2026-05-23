# Checkpoint 25 - Live Task Watch

Status: top-level task progress can be watched live from the terminal TUI

Decision:

- Operators should not have to bounce between static task snapshots while detached work is running.
- The TUI should use the existing persisted event timeline so live progress works across foreground and detached workers.
- The browser remains optional; live task progress belongs in the terminal-first surface.

Implemented in this checkpoint:

- Added slash palette and command lane entries for `/tasks watch <task-id>`.
- Added curses live watch handling for `/tasks watch <task-id>` and `/tasks live <task-id>`.
- Live watch repaints the current `AEGIS TASK` record and `AEGIS TASK EVENTS` timeline until the task reaches `completed`, `failed`, or `cancelled`.
- Added static fallback output for `/tasks watch <task-id>` and `/tasks live <task-id>` for non-curses terminals, tests, and docs.
- Updated background task output to point to `/tasks watch <task-id>`.
- Updated README task queue examples and terminal activation command list.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui -v
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_terminal_agent_slice -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
AEGISAGENT_TASK_SLEEP=1 PYTHONPATH=src python3 -m aegisagent tasks --background 'watchable detached terminal task'
PYTHONPATH=src python3 -m aegisagent tui
# expect-driven PTY smoke: /tasks watch <task-id> rendered AEGIS TASK EVENTS, saw completed, and exited with return code 0
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Streaming stdout/tool cards from task workers.
- Nonblocking watch that keeps the composer usable while monitoring.
- Recovery marking for stale `running` tasks after process death.
