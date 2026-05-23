# Checkpoint 60 - External Model Routing

## Goal

Move the terminal agent loop beyond the deterministic local provider by routing chat turns through a configured OpenAI-compatible API-key provider when the active route is ready, while preserving terminal-first safety and fail-closed behavior.

## Changes

- Added `OpenAICompatibleProvider` for API-key routes.
- Added active-route selection for `AgentRuntime`.
- `aegisagent chat` and normal TUI prompt turns keep `local/terminal-v0` by default.
- If the active route is `mode=api_key`, its env handle is present, and its base URL is safe, terminal chat calls `/chat/completions`.
- HTTPS is required for external provider URLs; loopback `http://127.0.0.1`, `localhost`, and `::1` are allowed for local development/testing.
- Base URLs with embedded credentials are blocked.
- Failed external calls return a terminal-visible failed-closed answer instead of opening a browser or leaking raw secrets.
- `agent.turn.completed` receipts now record `external_model_invocation_performed`, `provider_route_status`, `browser_auto_launch=false`, and `raw_secret_values_included=false`.
- Static TUI fallback now labels the default provider as `local/terminal-v0 ready` and reports the actual rendered terminal size instead of a hard-coded provider/size.
- Updated README and capability gap wording.

## Reference Blend

The prior `MatthewLopez1990/Aegis-Agent` repo uses a broad provider registry with OpenAI-compatible routes, custom endpoints, subscription bridges, aliases, fallbacks, and usage tracking. This checkpoint ports the smallest useful part into the current repo: explicit provider-route invocation through the terminal loop, not browser activation or hidden setup flows.

## Safety Notes

- Provider setup and doctor remain metadata-only.
- Raw API key values stay in environment variables and are not persisted or written to audit logs.
- Browser auto-launch remains false.
- Missing env handles, credential-bearing URLs, and non-HTTPS external URLs fail closed.
- Local deterministic provider remains the default and fallback.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/model_provider.py src/aegisagent/core/agent.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/tui/renderer.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 85 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 106 passed, 1 skipped
CLI smoke: local chat uses local/terminal-v0
CLI smoke: configured loopback OpenAI-compatible route returns external response
PTY smoke: prompt turn with default route stays terminal-first
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
