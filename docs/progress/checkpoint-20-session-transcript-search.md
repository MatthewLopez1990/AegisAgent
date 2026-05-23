# Checkpoint 20 - Session Transcript Search

Status: redacted terminal transcript search is available from CLI, TUI, and agent turns

Decision:

- A Hermes-class terminal agent needs recall over prior local work, not only curated memory files.
- Search should operate over the redacted persisted transcript and leave audit evidence.
- Agent prompt turns should avoid matching the current search request against itself.

Implemented in this checkpoint:

- `SessionStore.search(query, limit=...)` scans persisted session JSON records and returns bounded snippets.
- Search results include session id, title, message role, timestamp, message index, metadata, and a redacted snippet.
- CLI addition: `aegisagent sessions --query "<text>"`.
- TUI addition: `/sessions search <text>`.
- Agent prompt addition: `search sessions for <text>`, `session search <text>`, and transcript-search variants emit a `sessions.search` tool result.
- CLI/TUI direct searches write `session.search` audit receipts.
- Agent session searches write normal `agent.tool.completed` and `agent.turn.completed` receipts.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_tui tests.test_cli -v
```

Still incomplete:

- SQLite/FTS indexing for large transcript corpora.
- Cross-session ranking beyond recency and substring match.
- Search filters by role, tool name, source, and date range.
