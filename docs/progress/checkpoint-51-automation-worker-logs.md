# Checkpoint 51 - Automation Worker Logs

## Goal

Make explicit foreground automation worker runs inspectable after they finish, without adding a hidden daemon, browser launch, or unaudited scheduler side channel.

## Changes

- Added durable `.aegisagent/automations/worker.jsonl` events for foreground worker runs.
- Added a per-run `run_id` to worker output and `automation.worker_started` / `automation.worker_stopped` audit payloads.
- Worker runs now persist `started`, `tick`, and `stopped` events with checked, due, triggered, task id, timestamp, source, and receipt metadata.
- Added `aegisagent automations logs [run-id]`.
- Added `/automations logs [run-id]`.
- Added `automation.worker_logs_viewed` audit receipts for log inspection.
- Updated the capability map and README to make worker logs part of the terminal automation surface.

## Safety Notes

- Creating, listing, checking, and viewing automation records still report `schedule_worker_started=false`.
- The foreground worker still reports `schedule_worker_started=true` only during an explicit operator-started run.
- Viewing logs never starts work, opens a browser, or triggers due automations.
- Worker log events are terminal-first JSONL records under the existing workspace-local runtime directory.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 56 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 100 passed, 1 skipped optional FastAPI client
CLI smoke: automations worker --now 2026-05-23T10:00:00Z && logs <run-id> # started/tick/stopped events shown
PTY smoke: /automations worker && /automations logs                      # source=tui-worker/source=tui receipts recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify                        # ok, count=225
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
```
