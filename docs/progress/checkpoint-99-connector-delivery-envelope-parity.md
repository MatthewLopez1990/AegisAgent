# Checkpoint 99 - Connector Delivery Envelope Parity

Date: 2026-05-24

## Scope

This checkpoint moves connector readiness beyond metadata by adding terminal
delivery envelopes. Operators can draft redacted Slack, Teams, webhook, or Open
WebUI-style packets, preview approval requirements, and record an approved
packet in a local outbox once the connector handle is metadata-ready.

This is not live connector delivery.

## Implemented

- Added `ConnectorEnvelope` records and a durable `connector_outbox.jsonl`.
- Added `aegis connectors draft`, `aegis connectors send`, and
  `aegis connectors outbox`.
- Added `/connectors draft`, `/connectors send`, and `/connectors outbox`.
- Added read-only `GET /connectors/outbox` for the optional gateway.
- Kept the Web GUI read-only and added smoke coverage that rejects connector
  mutation routes or POST controls.
- Updated README, operator reference, and capability map to describe the outbox
  as approval-bound but not delivery-capable.

## Safety Boundary

- No Slack, Teams, webhook, Open WebUI, or MCP network delivery is performed.
- No browser launch, gateway auto-start, external delivery, or raw-secret
  persistence is introduced.
- Unapproved `send` returns `needs_approval` and exits non-zero in the CLI.
- Approved `send` records `approved_pending_adapter` only when configured
  handles are present; it still records `external_delivery_performed=false`.
- The optional gateway exposes read-only outbox inspection only. Connector
  mutation remains terminal-only until the Web approval model exists.

## Verification

Focused verification completed:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_connector_outbound_packets_are_approval_bound_and_redacted tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization tests.test_tui.TuiRendererTests.test_interactive_dispatch_model_providers_is_terminal_only tests.test_gateway.GatewayTests.test_connector_and_setup_routes_are_metadata_only -v  # 3 passed, 1 existing optional gateway skip
cd web && npm run smoke  # passed
python3 -m py_compile src/aegisagent/core/connectors.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/gateway.py  # passed
```

Full checkpoint verification completed:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v  # 206 passed, 2 skipped
cd web && npm run verify  # build + smoke passed
PYTHONPATH=src python3 -m aegisagent connectors draft slack --target '#ops' --message 'status token=sk-...'  # passed, redacted
PYTHONPATH=src python3 -m aegisagent connectors send slack --target '#ops' --message 'status'  # returned needs_approval, no outbox write
PYTHONPATH=src python3 -m aegisagent connectors outbox  # passed, drafted packet only
PYTHONPATH=src python3 -m aegisagent capabilities --gaps  # passed, remaining gaps still visible
PYTHONPATH=src python3 -m aegisagent audit verify  # passed
git diff --check  # passed
```
