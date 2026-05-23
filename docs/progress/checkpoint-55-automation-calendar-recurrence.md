# Checkpoint 55 - Automation Calendar Recurrence

## Goal

Make terminal automation schedules closer to real operator use by adding richer calendar recurrence labels while preserving the same due, missed, replay, and audit behavior.

## Changes

- Added due and missed-run support for `weekdays 09:00`.
- Added due and missed-run support for `business days 09:00`.
- Added due and missed-run support for `weekends 09:00`.
- Added due and missed-run support for `monthly 15 09:00` / `monthly day 15 09:00`.
- Added due and missed-run support for `monthly last 09:00` / `monthly last day 09:00`.
- Updated README schedule examples.
- Updated the capability map so the next automation gaps are calendar exceptions, timezone-aware recurrence, and deeper service health metrics.

## Safety Notes

- Recurrence checks remain terminal-visible metadata evaluation.
- `automations due` and `automations missed` do not queue work.
- `automations replay-missed`, `automations tick`, and `automations worker` still route through governed task creation and audit receipts.
- No browser, hidden daemon, or external action is started by adding the new labels.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v       # 59 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v              # 103 passed, 1 skipped optional FastAPI client
CLI smoke: create weekdays/monthly schedules and run automations due/missed # due/missed reasons shown
PTY smoke: /automations create weekday-check | weekdays 09:00 | ... && /automations due # source=tui receipts recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
python3 -m py_compile src/aegisagent/core/automation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
git diff --check
```
