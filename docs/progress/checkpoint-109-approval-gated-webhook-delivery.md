# Checkpoint 109: Approval-Gated Webhook Delivery

## Scope

Add the first live connector delivery adapter for outbound webhooks only. This
checkpoint does not add live Slack, Teams, Open WebUI, or MCP delivery.

## Safety Boundary

- Only the built-in `webhook` connector can perform live network delivery.
- Live delivery requires a configured URL environment handle and explicit
  approval on the send command.
- Slack, Teams, and Open WebUI sends remain metadata/outbox-only.
- HTTP and loopback/private network delivery are blocked by default; local
  loopback delivery is available only with `AEGIS_WEBHOOK_ALLOW_INSECURE_LOCAL=1`
  for tests and development.
- Audit and outbox receipts distinguish delivered webhook packets from pending
  adapter packets and record whether external delivery was actually performed.
- Receipts omit raw webhook URLs, include destination fingerprints and payload
  hashes, and keep browser auto-launch disabled.

## Verification

Completed verification for this checkpoint:

- Focused connector CLI/TUI tests with a local HTTP server passed as part of
  full test discovery.
- Connector metadata and command-catalog tests passed as part of full test
  discovery.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed: 215 tests,
  2 skipped for missing optional FastAPI test client.
- `npm run verify` passed in `web`: Vite build plus smoke check.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` passed and reports
  connector webhook delivery as approval-gated while other adapters remain
  metadata/outbox-only.
- `PYTHONPATH=src python3 -m aegisagent audit verify` passed with a valid audit
  chain.
- `PYTHONPATH=src python3 -m aegisagent commands connectors` passed and lists
  the approved webhook send command.
- `git diff --check` passed.
