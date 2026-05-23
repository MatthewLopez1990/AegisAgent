# Checkpoint 57 - Calendar Exceptions

## Goal

Let terminal automation schedules skip explicit local calendar dates while keeping the schedule label readable and the due/missed/replay pipeline unchanged.

## Changes

- Added `except=YYYY-MM-DD[,YYYY-MM-DD...]` schedule suffix support.
- Added `skip=YYYY-MM-DD[,YYYY-MM-DD...]` as an alias for exceptions.
- Added `exceptions=YYYY-MM-DD[,YYYY-MM-DD...]` as a readable alias.
- Exceptions are evaluated as local dates in the schedule timezone.
- `automations due` reports excluded dates as skip reasons.
- `automations missed` omits excluded occurrences from replay candidates.
- Updated README schedule examples and capability gap wording.

## Safety Notes

- Exceptions only affect schedule evaluation.
- `automations due` and `automations missed` remain read-only checks.
- Replay still queues governed tasks only when explicitly requested.
- Invalid exception dates fail closed as schedule parsing errors.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v  # 61 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v          # 105 passed, 1 skipped
CLI smoke: weekdays 09:00 America/Denver except=2099-01-05 skips due on the exception date
CLI smoke: monthly 15 09:00 tz=America/Denver skip=2026-06-15 omits the skipped missed run
PTY smoke: /automations create ... except=... && /automations due
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
