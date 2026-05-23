# Checkpoint 71 - Approved Terminal Web Fetch

## Goal

Add a terminal-first web fetch capability that moves Aegis toward Hermes/OpenClaw tool parity without regressing into surprise browser launch or hidden network activity.

## Changes

- Added `WebToolRunner.fetch` as an approval-gated typed network tool.
- Added `aegisagent fetch <url> --approved`.
- Added `/web fetch <url> | approve` in the TUI.
- Added plain prompt approval previews for `fetch http(s)://...` requests through the agent runtime.
- Updated the local terminal provider so web-fetch previews are visible in the assistant response.
- Updated README and the capability map to show terminal web fetch as approved network execution and leave live browser sessions as the next browser-specific gap.

## Safety Notes

- Unapproved fetches return `needs_approval` and do not contact the URL.
- Approved fetches record `network_request_performed=true`, `external_action_started=true`, and `browser_auto_launch=false`.
- URLs must be explicit `http` or `https` URLs without embedded credentials.
- Response bodies and URLs are redacted before display and audit persistence.
- The optional `/web` browser GUI command remains separate from `/web fetch`; no gateway or browser is started for fetch.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/web_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py tests/test_cli.py tests/test_tui.py` passed.
- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/model_provider.py src/aegisagent/core/agent.py tests/test_terminal_agent_slice.py` passed.
- Focused fetch tests passed:
  - `tests.test_cli.CliTests.test_fetch_is_approval_gated_typed_network_tool`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_web_fetch_requires_approval`
  - `tests.test_terminal_agent_slice.TerminalAgentSessionTests.test_agent_runtime_surfaces_web_fetch_approval_preview`
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v` passed: 113 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 135 tests, 1 skipped.
- Local HTTP smoke passed:
  - CLI unapproved fetch returned `needs_approval` and made zero HTTP requests.
  - CLI approved fetch returned the local response body.
  - TUI approved `/web fetch ... | approve` returned the local response body.
  - Agent prompt `fetch <url>` returned a visible `web.fetch` approval preview and made no HTTP request.
- Static TUI frame checks passed at `80x24`, `120x40`, and `200x60`.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` shows web fetch as an approved typed network action and keeps browser sessions as a future explicit gap.
