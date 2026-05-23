# Checkpoint 46 - Automation Due Tick

## Goal

Move durable automation records from manual-only triggers toward terminal-owned scheduled execution without starting a surprise daemon or browser surface.

## Implemented

- Added `aegisagent automations due` to evaluate active records against supported schedule labels.
- Added `aegisagent automations tick` / `run-due` to queue governed tasks for due automation records.
- Added `/automations due` and `/automations tick` to the prompt-first TUI slash palette and command lanes.
- Added deterministic `--now` support for CLI due checks.
- Added schedule support for `daily HH:MM`, `weekly <weekday> HH:MM`, `hourly`, `every N minutes|hours|days`, and one-shot `now|once|startup`.
- Kept `schedule_worker_started=false`; this checkpoint is an explicit operator tick, not a daemon.

## Safety

- Due checks only read automation metadata and write audit receipts.
- Ticks queue governed tasks through the existing task runner.
- The tick path records `manual_trigger=false`, `external_action_started=false`, `browser_auto_launch=false`, and `schedule_worker_started=false`.

## Verification

Run after this checkpoint:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
