# Checkpoint 37 - Terminal Activation Default

## Goal

Make the terminal entrypoint impossible to confuse with the optional browser/Web surface.

## Changes

- `aegisagent` with no subcommand is now the primary activation path:
  - launches the terminal TUI when attached to a real TTY
  - prints a terminal activation card outside a TTY
  - never starts the gateway or opens a browser
- Added `aegisagent activate` as an explicit terminal-first alias with the same behavior.
- The activation card reports:
  - `terminal_first: true`
  - `browser_required: false`
  - `browser_auto_launch: false`
  - `gateway_started: false`
- README now lists `aegisagent`, `aegisagent activate`, and `aegisagent tui` as terminal activation paths.

## Prior Aegis-Agent Blend

The previous `MatthewLopez1990/Aegis-Agent` repo treats `aegis tui` as the operator's primary surface and keeps Web GUI usage separate. This checkpoint ports that activation discipline into this repo before deeper subsystem parity work.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent
PYTHONPATH=src python3 -m aegisagent activate
PYTHONPATH=src python3 -m aegisagent --json
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
