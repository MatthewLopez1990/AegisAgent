# Checkpoint 53 - Automation Service Wrapper

## Goal

Make the foreground automation worker installable by an operator without letting Aegis silently load or start a background scheduler.

## Changes

- Added `aegisagent automations service`.
- Added `/automations service`.
- Generates `.aegisagent/automations/automation-worker.sh`.
- Generates `.aegisagent/automations/com.aegisagent.automation.<workspace>.plist`.
- Prints exact `launchctl bootstrap`, `kickstart`, `bootout`, and `tail` commands for the operator.
- Added `automation.service_wrapper_generated` audit receipts.
- Updated the capability map and README so the next automation gaps are recurrence breadth and service status inspection.

## Safety Notes

- The service command writes wrapper files only; it does not load, start, stop, or unload launchd jobs.
- Generated wrapper output reports `loaded=false`, `schedule_worker_started=false`, and `browser_auto_launch=false`.
- The generated script still runs `aegisagent automations worker --max-ticks 0`, preserving the same explicit worker path.
- Service logs stay under the workspace-local `.aegisagent/automations/` directory.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 58 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 102 passed, 1 skipped optional FastAPI client
CLI smoke: automations service --interval 15                             # wrapper files generated, loaded=false
PTY smoke: /automations service                                          # source=tui receipt recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
git diff --check
```
