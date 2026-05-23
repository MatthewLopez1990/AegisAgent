# Checkpoint 38 - First-Launch Setup Wizard

## Goal

Make the terminal TUI feel like the primary product on first launch by opening a setup wizard inside the terminal, not a browser or generic help screen.

## Changes

- Added private setup UI state at `.aegisagent/setup-ui-state.json`.
- Default curses launch now opens the `SETUP WIZARD` panel unless the operator hides it.
- Added terminal slash commands:
  - `/setup first-task`
  - `/setup hide`
  - `/setup reset`
  - `/setup json`
- Expanded the setup panel with model, secrets, sandbox, connectors, memory, first-task, checks, and hide actions.
- `/setup hide` and `/setup reset` write audit receipts and keep:
  - `terminal_first: true`
  - `browser_auto_launch: false`
  - `external_action_started: false`
  - `raw_secret_values_included: false`

## Prior Aegis-Agent Blend

The previous `MatthewLopez1990/Aegis-Agent` TUI opened a setup wizard by default until dismissed, with `/setup hide` and `/setup reset` controlling that behavior. This checkpoint ports that interaction model into the current repo while keeping the current security-first metadata checks.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_cli -v
PYTHONPATH=src python3 -m aegisagent activate
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
