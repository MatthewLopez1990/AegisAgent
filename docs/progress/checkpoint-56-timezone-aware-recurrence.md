# Checkpoint 56 - Timezone-Aware Recurrence

## Goal

Let terminal operators write schedule labels in the timezone where the work actually happens while keeping persisted timestamps and task triggers canonical in UTC.

## Changes

- Added optional IANA timezone suffix parsing for schedule labels.
- Supported suffix forms include `America/Denver`, `tz=America/Denver`, and `timezone=America/Denver`.
- Timezone-aware due checks now work for daily, weekday, weekend, weekly, monthly, and month-end labels.
- Timezone-aware missed-run checks now emit UTC replay timestamps for local calendar occurrences.
- Updated README schedule examples and capability gap wording.

## Safety Notes

- Timezone parsing only changes schedule evaluation; it does not start workers or external actions.
- `automations due` and `automations missed` remain read-only checks.
- `automations replay-missed` still queues governed tasks through the existing audit path.
- Invalid timezone labels fail closed as unsupported schedule reasons.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 60 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 104 passed, 1 skipped optional FastAPI client
CLI smoke: create weekdays 09:00 America/Denver and run automations due around the local boundary # skip before 09:00, due at 09:00
CLI smoke: create monthly 15 09:00 tz=America/Denver and run automations missed # UTC replay timestamps emitted
PTY smoke: /automations create ... America/Denver && /automations due    # source=tui receipts recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
git diff --check
```
