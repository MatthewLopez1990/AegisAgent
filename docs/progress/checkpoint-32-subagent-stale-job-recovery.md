# Checkpoint 32: Subagent Stale Job Recovery

Status: subagent background job supervision now repairs dead worker records

## Why

- Background jobs should not stay `running` forever if their detached worker process is gone.
- Normal list, inspect, and monitor actions are supervision paths, so they should reconcile stale process state automatically.
- This keeps subagent background work aligned with the governed top-level task queue.

## Implemented

- Added `LocalSubagentOrchestrator.recover_stale_background(...)`.
- `background_job(...)` and `background_jobs(...)` now recover stale running records before returning data.
- Completed, failed, and cancelled background jobs now clear their worker pid.
- CLI `aegisagent subagents --recover-stale` returns recovered job records as JSON.
- TUI `/subagents recover` prints recovered jobs, while `/subagents jobs`, `/subagents job <id>`, and `/subagents monitor <id>` auto-recover stale running records.
- README command lists now include the subagent recovery path.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_memory_skills_subagents tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

## Next

- Add stdout/stderr capture for subagent detached workers if future workers produce useful raw logs.
- Route model-backed subagent workers through the same recovery and monitor surfaces.
