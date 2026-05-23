# Checkpoint 43 - Automation Task Trigger

## Goal

Move automation records closer to long-running Hermes-style operation by letting an operator trigger an automation into the governed task queue from the terminal.

## Changes

- Added trigger metadata to automation records:
  - `last_triggered_at`
  - `last_task_id`
  - `trigger_count`
- Added CLI commands:
  - `aegisagent automations trigger <id>`
  - `aegisagent automations run <id>`
  - `aegisagent automations trigger <id> --background`
- Added TUI slash commands:
  - `/automations trigger <id>`
  - `/automations run <id>`
- Triggering an active automation queues a governed task from the stored prompt.
- Triggering with `--background` starts the queued task in a detached governed worker.
- Paused automations block trigger attempts and write a blocked audit receipt.

## Security Posture

This is still not a daemon scheduler. It is an explicit terminal operator action. The trigger records:

- `terminal_first=true`
- `manual_trigger=true`
- `external_action_started=false`
- `schedule_worker_started=false`
- `raw_secret_values_included=false`

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent automations create daily-check --schedule "daily 09:00" --prompt "summarize workspace risks"
PYTHONPATH=src python3 -m aegisagent automations trigger <id>
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
