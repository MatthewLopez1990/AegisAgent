# Checkpoint 36 - Web and Gateway Connector Parity

## Goal

Expose the checkpoint 35 connector posture through the gateway and Web GUI without changing the terminal-first activation model.

## Changes

- Added gateway routes:
  - `GET /connectors`
  - `GET /connectors/doctor`
  - `GET /setup`
  - `GET /setup/{section}`
  - `GET /setup/run-checks`
- Added Web GUI connector navigation and a connector readiness panel.
- Updated Web posture copy so `local/terminal-v0` remains the primary model route and browser access is manual/local rather than automatic.
- Kept connector state metadata-only:
  - `external_delivery_performed: false`
  - `browser_auto_launch: false`
  - setup and doctor checks do not send messages, launch browsers, or call external models.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_gateway tests.test_cli tests.test_tui -v
cd web && npm run smoke
cd web && npm run build
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

FastAPI remains an optional dependency. Gateway route tests are skipped when the optional gateway test client is not installed.
