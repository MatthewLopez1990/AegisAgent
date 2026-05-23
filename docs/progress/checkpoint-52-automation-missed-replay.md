# Checkpoint 52 - Automation Missed Replay

## Goal

Add an explicit missed-run policy so long-running terminal operators can see schedule windows that elapsed while no foreground worker was active, then replay those windows only by direct command.

## Changes

- Added `aegisagent automations missed`.
- Added `aegisagent automations replay-missed`.
- Added `/automations missed`.
- Added `/automations replay`.
- Missed-run detection supports one-shot, hourly, every-N-minute/hour/day, daily, and weekly schedule labels.
- Replay queues normal governed automation tasks with `manual_trigger=false` and the missed timestamp as `triggered_at`.
- Added `automation.missed_checked` and `automation.missed_replayed` audit receipts.
- Updated the capability map and README so the next automation gap is the installable service wrapper.

## Safety Notes

- Missed-run checks never queue work.
- Replay is explicit and terminal-visible; no hidden daemon or browser is started.
- Replay keeps `schedule_worker_started=false` because it is not the foreground scheduler loop.
- Replayed work still flows through the same governed task queue and audit trail as due ticks.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 57 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 101 passed, 1 skipped optional FastAPI client
CLI smoke: automations missed --now 2099-01-01T10:00:00Z && replay-missed --limit 2 # replayed=2
PTY smoke: /automations missed && /automations replay                    # source=tui receipts recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
git diff --check
```
