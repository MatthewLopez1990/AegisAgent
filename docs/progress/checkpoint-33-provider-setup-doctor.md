# Checkpoint 33: Provider Setup Doctor

Status: terminal model-provider setup now has durable metadata and readiness checks

## Why

- `/model providers` was previously hardcoded, so setup could describe external providers but could not persist a route choice.
- The terminal-first path needs a safe model setup surface before external invocation is wired.
- Provider setup must not read raw secrets, launch a browser, or call an external model during readiness checks.

## Implemented

- Added `ProviderStore` for workspace-local provider route metadata in `.aegisagent/config.json`.
- Added CLI commands:
  - `aegisagent model providers`
  - `aegisagent model configure <name> --mode api_key --api-key-env <ENV_NAME>`
  - `aegisagent model doctor`
- Added TUI/static commands:
  - `/model providers`
  - `/model doctor`
  - `/setup model`
  - `/setup run-checks`
- Provider configuration and doctor checks write audit receipts with `external_action_started: false`, `model_invocation_performed: false`, and `raw_secret_values_included: false`.
- The default config now keeps `local/terminal-v0` active and records `openai/gpt-5.5` as not configured.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_cli tests.test_terminal_agent_slice -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent model providers
PYTHONPATH=src python3 -m aegisagent model doctor
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

## Next

- Route an explicitly configured provider through a guarded external-model adapter.
- Add setup command sections beyond model readiness: sandbox, secrets, connectors, and tool policy.
