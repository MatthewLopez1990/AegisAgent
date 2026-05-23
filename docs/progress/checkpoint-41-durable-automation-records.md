# Checkpoint 41 - Durable Automation Records

## Goal

Move automations from an in-memory stub to a durable, terminal-visible, audit-backed surface without starting a scheduler or external action.

## Changes

- Replaced the old in-memory automation registry with workspace-local JSON records under `.aegisagent/automations/`.
- Added automation safety fields:
  - `terminal_first=true`
  - `external_action_started=false`
  - `schedule_worker_started=false`
  - `browser_auto_launch=false`
- Added CLI commands:
  - `aegisagent automations`
  - `aegisagent automations create <name> --schedule <schedule> --prompt <prompt>`
  - `aegisagent automations show <id>`
  - `aegisagent automations pause <id>`
  - `aegisagent automations resume <id>`
  - `aegisagent automations delete <id>`
- Added TUI slash commands:
  - `/automations`
  - `/automations create <name> | <schedule> | <prompt>`
  - `/automations pause <id>`
  - `/automations resume <id>`
  - `/automations delete <id>`
- Updated the capability map so automations are now `partial` instead of `planned`.

## Security Posture

This checkpoint stores schedule intent only. It does not start a scheduler, run prompts in the background, send messages, open a browser, or invoke an external model. Create, pause, resume, and delete actions write audit receipts.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent automations
PYTHONPATH=src python3 -m aegisagent automations create daily-check --schedule "daily 09:00" --prompt "summarize workspace risks"
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
