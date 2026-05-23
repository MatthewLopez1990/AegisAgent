# Checkpoint 50 - Automation Worker

## Goal

Move automations closer to multi-day Hermes-style operation by adding an explicit foreground scheduler worker that can keep checking due records from the terminal without starting a hidden daemon or browser.

## Changes

- Added `aegisagent automations worker`.
- Added `aegisagent automations worker --interval <seconds> --max-ticks <count>`.
- Added `aegisagent automations daemon` as an alias for the same explicit worker command.
- Added `/automations worker` for a single visible TUI scheduler pass.
- Worker runs call the existing due/tick path and queue governed tasks for due automations.
- Worker output reports tick count, triggered task count, receipt ids, and task watch hints.
- Added `automation.worker_started` and `automation.worker_stopped` audit receipts.

## Safety Notes

- Automation records still report `schedule_worker_started=false`; creating a record never starts a worker.
- The worker reports `schedule_worker_started=true` only for the explicit operator-started foreground run.
- The worker never opens a browser and records `browser_auto_launch=false`.
- The TUI slash command runs one pass so the composer is not trapped in a long loop.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 56 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 100 passed, 1 skipped optional FastAPI client
PYTHONPATH=src python3 -m aegisagent automations worker --interval 0 --max-ticks 1
PTY smoke: /automations worker                                           # source=tui-worker receipts recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify                        # ok, count=225
git diff --check                                                         # clean
```
