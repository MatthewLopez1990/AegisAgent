# Checkpoint 13 - Local Subagent Orchestration

Status: bounded local subagent delegation implemented for CLI, TUI, and prompt turns

Decision:

- The terminal agent needs real delegation behavior, not only a static subagent limits panel.
- This checkpoint implements local deterministic subagents first, with persistent records, isolated sessions, and audit receipts.
- The design remains terminal-first; no browser or external model route is needed for delegation.

Implemented in this checkpoint:

- `RuntimePaths` now includes `.aegisagent/subagents`.
- `SubagentRecord` now stores role, session id, status, children, summary, and timestamps.
- `SubagentStore` persists subagent records as workspace-local JSON.
- `LocalSubagentOrchestrator` creates a coordinator plus planner, researcher, implementer, and reviewer workers under the existing bounds: max concurrency `8`, max depth `2`, and max children `5`.
- Each subagent gets an isolated session transcript in `.aegisagent/sessions`.
- Delegation writes `subagent.delegation.started` and `subagent.delegation.completed` audit receipts.
- `aegisagent subagents --delegate "<task>"` runs a bounded local delegation and `aegisagent subagents` lists persisted records.
- `/subagents <task>` runs delegation inside the TUI.
- Normal prompt turns containing delegation language invoke `subagents.delegate` and surface the announce-back in the assistant response.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_terminal_agent_slice tests.test_tui tests.test_cli -v
PYTHONPATH=src python3 -m aegisagent subagents --delegate 'blend the terminal agent with bounded workers'
PYTHONPATH=src python3 -m aegisagent chat 'delegate this to many subagents' --json
```

Still incomplete:

- Concurrent worker execution against independent model/tool contexts.
- Cascade stop over persisted records from the CLI/TUI.
- Streaming subagent progress cards in the curses UI.
- Routing subagents through real external provider/tool policies.
- Higher-depth delegation and worker-to-worker artifact passing.
