# Checkpoint 35: Connector Readiness Registry

Status: connector readiness is durable, inspectable, and policy-gated from the terminal

## Why

- Hermes-class agents need Slack, Teams, webhook, MCP, browser, and Open WebUI-style surfaces.
- Aegis should expose those surfaces without silently enabling external delivery.
- Setup should show connector readiness with the same metadata-only discipline as provider setup.

## Implemented

- Added `ConnectorStore` for workspace-local connector metadata in `.aegisagent/config.json`.
- Default connector metadata now covers:
  - Slack
  - Teams
  - webhook
  - MCP
  - browser
  - Open WebUI
- Added CLI commands:
  - `aegisagent connectors`
  - `aegisagent connectors configure slack --token-env SLACK_BOT_TOKEN --enable`
  - `aegisagent connectors doctor`
- Added TUI/static commands:
  - `/connectors`
  - `/connectors doctor`
- `/setup connectors` now uses connector readiness metadata instead of a generic placeholder.
- Connector configure and doctor operations write audit receipts with `external_action_started: false`, `external_delivery_performed: false`, `raw_secret_values_included: false`, and `browser_auto_launch: false`.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent connectors
PYTHONPATH=src python3 -m aegisagent connectors doctor
PYTHONPATH=src python3 -m aegisagent setup connectors
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

## Next

- Add connector-specific non-send actions such as listing configured metadata and validating handles.
- Add guarded send/run adapters only after explicit approval plumbing exists for each connector.
