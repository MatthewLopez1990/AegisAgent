# Checkpoint 40 - Terminal Capability Map

## Goal

Make the Hermes-class parity state visible from the terminal so the operator can see what is ready, partial, metadata-ready, and planned without opening the browser or digging through project notes.

## Changes

- Added a reusable core capability map with explicit status categories:
  - ready
  - partial
  - metadata-ready
  - planned
- Added CLI commands:
  - `aegisagent capabilities`
  - `aegisagent capabilities --gaps`
  - `aegisagent --json capabilities`
  - `aegisagent --json capabilities --gaps`
- Added TUI slash commands:
  - `/capabilities`
  - `/gaps`
- Updated TUI command lanes, help text, and the Hermes blend panel so the map is reachable from the prompt-first surface.
- The map reports safety fields directly:
  - `terminal_first=true`
  - `browser_auto_launch=false`
  - `browser_required=false`
  - `gateway_started=false`
  - `external_action_started=false`

## Current Gap Framing

The terminal now says plainly that AegisAgent is not a complete Hermes-class agent yet. It tracks implemented terminal activation, TUI, setup, policy/audit, and task queue surfaces while keeping typed tools, agents, memory, provider routing, connectors, gateway, automations, self-improvement, browser automation, and remote control in their accurate partial or planned buckets.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent capabilities
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
