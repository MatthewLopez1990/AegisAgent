# Checkpoint 30 - Nonblocking Task Monitor

Status: TUI task watch refreshes while the composer remains usable

Decision:

- `/tasks watch <task-id>` should behave like a terminal monitor, not a modal wait loop.
- The composer must remain reachable while detached work is running.
- Operators need an explicit way to stop the monitor without exiting the TUI.

Implemented in this checkpoint:

- Removed the blocking sleep loop from the curses task watch path.
- Added task monitor state to the TUI main loop.
- The curses loop now uses timed `getch()` polling only while a task monitor is active.
- `/tasks watch <task-id>` and `/tasks live <task-id>` start a nonblocking monitor.
- The monitor periodically refreshes task status, events, recorded output, and worker logs.
- The monitor stops itself when the task reaches `completed`, `failed`, `cancelled`, or `unknown`.
- Added `/tasks unwatch` to stop an active monitor while keeping the composer active.
- Static dispatch for `/tasks unwatch` now explains that the command only affects the live TUI monitor.
- Updated README terminal command lists and current-gap wording.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_terminal_agent_slice tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
AEGISAGENT_TASK_SLEEP=2 PYTHONPATH=src python3 -m aegisagent tasks --background 'nonblocking monitor smoke'
# expect-driven PTY smoke: /tasks watch <task-id> showed "composer remains active", /tasks unwatch was accepted while the task was still running, and the worker later completed
```

Still incomplete:

- External model routing through setup.
- Richer typed tool execution beyond the current local workspace/git/session/subagent paths.
- Broader model-backed multi-agent worker loops with independent tool contexts.
