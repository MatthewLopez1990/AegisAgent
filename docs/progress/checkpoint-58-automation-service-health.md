# Checkpoint 58 - Automation Service Health

## Goal

Make the operator-loaded automation service easier to diagnose from the terminal without loading launchd, starting the worker, or touching external systems.

## Changes

- Added service health status to `aegisagent automations service-status`.
- Added wrapper readiness, worker-log presence, worker event count, last worker event, last event age, and stdout/stderr tail counts.
- Added operator advice for missing wrappers, not-loaded wrappers, observed worker logs, loaded services, and stderr output.
- Added the same health line to `/automations service-status`.
- Updated README and capability gap wording.

## Safety Notes

- Service status remains read-only.
- It does not call `launchctl bootstrap`, `launchctl kickstart`, or `launchctl bootout`.
- It does not start the foreground worker or replay missed automations.
- Worker logs and service tails remain workspace-local under `.aegisagent/automations/`.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v  # 61 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v          # 105 passed, 1 skipped
CLI smoke: automations service && automations service-status # health status shown
CLI smoke: automations worker && automations service-status  # worker event metrics shown
PTY smoke: /automations service-status                       # source=tui receipt recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
