# Checkpoint 62 - Provider Fallback

## Goal

Make ready external model routes more resilient in the terminal by falling back to the built-in local provider after an attempted external call fails, while keeping unsafe or unready routes fail-closed.

## Changes

- Added `FallbackModelProvider` around ready OpenAI-compatible API-key routes.
- Successful external responses still return the external provider response directly.
- Attempted external failures such as HTTP or transport errors now produce a terminal-visible local fallback answer.
- Blocked or unready routes, including missing env handles and unsafe base URLs, still fail closed and do not fall back silently.
- `agent.turn.completed` receipts now include `primary_provider`, `fallback_used`, and `fallback_provider`.
- Provider usage records now include primary/fallback metadata alongside route status and external invocation state.
- Updated README and capability wording so provider routing reflects fallback behavior and the remaining gap is multi-provider fallback ordering.

## Safety Notes

- The fallback path does not open a browser.
- Raw API keys remain in environment variables and are not written to audit or usage records.
- The transcript explicitly names the failed primary provider and the local fallback provider.
- Local fallback is only used after a route is ready enough to attempt and the attempted call fails.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/model_provider.py src/aegisagent/core/agent.py src/aegisagent/core/provider_config.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 86 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 107 passed, 1 skipped
CLI smoke: loopback HTTP 503 route falls back to local/terminal-v0 and records fallback metadata
CLI smoke: successful loopback OpenAI-compatible route still returns external provider response
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
