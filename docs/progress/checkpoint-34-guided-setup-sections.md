# Checkpoint 34: Guided Setup Sections

Status: setup is now a terminal-first onboarding surface with actionable sections

## Why

- A Hermes-style agent should not leave setup as a static frame or scattered commands.
- The user specifically pushed for clearer first-launch onboarding and easy setup instructions.
- Setup must remain safe: metadata-only checks, no browser launch, no raw secret capture, and no external model invocation.

## Implemented

- Added `SetupGuide`, shared by CLI and TUI.
- Added CLI setup surfaces:
  - `aegisagent setup --quick`
  - `aegisagent setup --full`
  - `aegisagent setup model`
  - `aegisagent setup secrets`
  - `aegisagent setup sandbox`
  - `aegisagent setup tools`
  - `aegisagent setup connectors`
  - `aegisagent setup memory`
  - `aegisagent setup --run-checks`
- Added TUI/static setup commands:
  - `/setup model`
  - `/setup secrets`
  - `/setup sandbox`
  - `/setup tools`
  - `/setup connectors`
  - `/setup memory`
  - `/setup run-checks`
- `/setup run-checks` now returns one metadata-only payload covering provider, memory, sandbox, tools, connectors, and section readiness.
- README setup examples now show the guided section commands.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent setup --quick
PYTHONPATH=src python3 -m aegisagent setup --run-checks
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

## Next

- Add connector-specific setup metadata for Slack, Teams, webhooks, and MCP.
- Wire guarded external provider invocation once the active route passes readiness.
