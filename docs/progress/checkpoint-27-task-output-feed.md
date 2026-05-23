# Checkpoint 27 - Task Output Feed

Status: task workers persist assistant and tool output for terminal inspection

Decision:

- A live task timeline is not enough for long-running terminal work; operators need the worker's actual output in the same terminal flow.
- Task output should be durable so detached workers, later CLI checks, and the TUI watch view all show the same result.
- Output must stay redacted and tied to existing task events/audit receipts.

Implemented in this checkpoint:

- Added `AgentTurnResult.tool_results` so task workers can persist the tool cards used during a turn.
- Added `TaskOutput` records persisted to `.aegisagent/tasks/outputs.jsonl`.
- Added task output APIs:
  - `TaskStore.append_output(...)`
  - `TaskStore.outputs(...)`
  - `TaskRunner.outputs(...)`
- Task runs now record:
  - `tool` output entries for typed tool results
  - `assistant` output entries for the final assistant response
  - `output.tool` and `output.assistant` task timeline events
- Added terminal formatting through `format_task_outputs(...)`.
- CLI addition: `aegisagent tasks --output <task-id>`.
- TUI slash addition: `/tasks output <task-id>`.
- `/tasks watch <task-id>` now includes task status, events, and recorded output in one terminal view.
- Updated README task queue examples and current-gap wording.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
task_id=$(PYTHONPATH=src python3 -m aegisagent tasks --submit 'read file README.md' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PYTHONPATH=src python3 -m aegisagent tasks --run "$task_id"
PYTHONPATH=src python3 -m aegisagent tasks --output "$task_id"
# expect-driven PTY smoke: /tasks watch <task-id> matched AEGIS TASK OUTPUT and workspace.read_file, then exited with return code 0
```

Still incomplete:

- True live stdout/stderr streaming from detached worker processes while they are running.
- Nonblocking watch that keeps the composer usable while monitoring.
- External model routing through setup.
