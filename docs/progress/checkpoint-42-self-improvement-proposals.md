# Checkpoint 42 - Self-Improvement Proposals

## Goal

Turn the multi-day Hermes-class buildout into a terminal-visible improvement loop with durable proposals, failure classification, review gates, and audit receipts.

## Changes

- Added durable improvement proposal records under `.aegisagent/improvements/`.
- Added failure classification for:
  - context safety
  - policy or permission
  - model invocation
  - data contract
  - persistence state
  - configuration
  - tool execution
  - runtime fallback
- Added proposal safety fields:
  - `terminal_first=true`
  - `workspace_mutation_allowed_before_approval=false`
  - `external_action_started=false`
  - `browser_auto_launch=false`
  - `raw_secret_values_included=false`
- Added CLI commands:
  - `aegisagent improve`
  - `aegisagent improve propose <failure> --target <subsystem> --operation <operation>`
  - `aegisagent improve show <id>`
  - `aegisagent improve review <id>`
  - `aegisagent improve approve <id>`
  - `aegisagent improve reject <id>`
- Added TUI slash commands:
  - `/improve`
  - `/improve propose <failure>`
  - `/improve show <id>`
  - `/improve approve <id>`
  - `/improve reject <id>`
- Updated the capability map so self-improvement is now `partial` instead of `planned`.

## Security Posture

This checkpoint does not auto-edit the workspace. It records an improvement candidate and the validation gates required before any future implementation can proceed. Review actions write audit receipts and preserve the terminal-first/no-browser contract.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent improve
PYTHONPATH=src python3 -m aegisagent improve propose "policy denied a needed safe git read" --target policy --operation evaluate
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
