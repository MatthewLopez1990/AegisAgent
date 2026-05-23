# Checkpoint 17 - Background Subagent Jobs

Status: process-backed background subagent jobs implemented for CLI and TUI

Decision:

- Streaming subagents are useful, but a terminal-first agent also needs a way to start work and keep the composer usable.
- Background work should be process-backed and persisted, not only an in-memory thread tied to one TUI render loop.
- Operators should be able to start, list, and inspect jobs from terminal commands.

Implemented in this checkpoint:

- `RuntimePaths` now includes `.aegisagent/jobs`.
- `BackgroundJobRecord` stores job id, task, status, pid, root id, receipt id, summary, and timestamps.
- `BackgroundJobStore` persists job records under `.aegisagent/jobs`.
- `LocalSubagentOrchestrator.start_background(...)` launches a detached Python worker process through the same CLI entrypoint.
- `LocalSubagentOrchestrator.run_background_job(...)` runs a queued job, delegates subagents, and updates persisted status.
- CLI additions:
  - `aegisagent subagents --background "<task>"`
  - `aegisagent subagents --jobs`
  - `aegisagent subagents --job <job-id>`
- TUI additions:
  - `/subagents bg <task>`
  - `/subagents jobs`
  - `/subagents job <job-id>`
- Background job completion writes `subagent.background.completed`; start writes `subagent.background.started`.

Verified locally:

```bash
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
```

Still incomplete:

- In-place nonblocking TUI progress cards for active background jobs.
- Operator cancellation of a running process by job id.
- Model-backed worker loops and independent tool contexts.
- Background job retention/cleanup policy.
