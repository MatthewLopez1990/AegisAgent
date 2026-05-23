# Checkpoint 15 - Subagent Timeline

Status: persisted subagent timeline events exposed through CLI and TUI

Decision:

- Subagent work needs an inspectable terminal timeline before live curses streaming can be useful.
- Timeline events should be workspace-local, durable, and tied to a root subagent id.
- The TUI should expose a readable timeline view instead of requiring operators to inspect JSON or audit internals.

Implemented in this checkpoint:

- `SubagentEvent` records root id, event type, role, worker id, message, and timestamp.
- `SubagentStore.append_event(...)` writes `.aegisagent/subagents/events.jsonl`.
- `SubagentStore.events(...)` retrieves a root-scoped timeline.
- Delegation records `root.started`, `worker.started`, `worker.completed`, and `root.completed`.
- Cascade stop records `record.stopped` events.
- `aegisagent subagents --events <root-id>` returns persisted timeline events.
- `/subagents watch <root-id>` and `/subagents events <root-id>` render a compact terminal timeline.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_tui tests.test_cli tests.test_terminal_agent_slice -v
root_id=$(PYTHONPATH=src python3 -m aegisagent subagents --delegate 'timeline smoke orchestration' | python3 -c 'import json,sys; print(json.load(sys.stdin)["root"]["id"])')
PYTHONPATH=src python3 -m aegisagent subagents --events "$root_id"
```

Still incomplete:

- True live streaming inside the curses render loop while a delegation is running.
- Model-backed worker loops with independent tool contexts.
- TUI progress cards that update in-place without waiting for command completion.
- Event compaction and search across large subagent histories.
