# Checkpoint 31: Nonblocking Subagent Job Monitor

Status: TUI subagent background jobs can be monitored while the composer remains usable

## Why

- Background subagent work should be inspectable from the terminal without turning the TUI into a modal wait loop.
- `/subagents watch <root-id>` already means persisted subagent timeline, so background job supervision needs a separate command.
- Hermes-style terminal operation needs durable work plus lightweight live monitors that can be stopped without killing the session.

## Implemented

- Added `/subagents monitor <job-id>` to the slash palette and command lanes.
- Added `/subagents unwatch` to stop an active live monitor while keeping the composer active.
- The curses loop now refreshes either task monitors or subagent job monitors on a short timeout.
- Static dispatch for `/subagents monitor <job-id>` renders the same job snapshot, including the timeline once a root id exists.
- Background subagent start output now points operators to `/subagents monitor <job-id>` and keeps `/subagents job <job-id>` as the inspect command.
- README command lists now include the new monitor and unwatch paths.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_memory_skills_subagents tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

## Next

- Add stdout/stderr capture for subagent detached workers if subagent jobs start doing more than deterministic local delegation.
- Add stale running recovery for subagent background jobs, matching the top-level task queue. Completed in checkpoint 32.
