# Checkpoint 75 - Terminal Dashboard

## Goal

Blend another useful prior Aegis-Agent pattern into this repo: a single terminal-first operator dashboard that answers what is ready, what is running, what is gated, and what should happen next without opening a browser or starting the web gateway.

## Changes

- Added `aegisagent.core.dashboard` as a read-only aggregation surface.
- Added `aegisagent dashboard` with text and `--json` output.
- Added `/dashboard` to the TUI slash command list and command lanes.
- Dashboard output includes activation command, safety flags, audit/sandbox/tool posture, task/session/automation/improvement/subagent counts, model and connector routes, top capability gaps, and agent contract version.
- Updated README quick start and command references.

## Safety Notes

- Dashboard is metadata-only and read-only.
- It does not start the web gateway, open a browser, invoke a model, send connector traffic, or mutate the workspace.
- The dashboard payload carries `terminal_first=true`, `browser_required=false`, `browser_auto_launch=false`, `gateway_started=false`, and `external_action_started=false`.
- It keeps `/web` as the explicit opt-in browser instruction path.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/dashboard.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py tests/test_cli.py tests/test_tui.py` passed.
- Focused tests passed:
  - `tests.test_cli.CliTests.test_dashboard_is_terminal_first_operator_surface`
  - `tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_dashboard_surface`
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v` passed: 87 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 141 tests, 1 skipped.
- CLI smoke passed:
  - `PYTHONPATH=src python3 -m aegisagent dashboard`
  - `PYTHONPATH=src python3 -m aegisagent --json dashboard`
- TUI dispatch smoke passed for `/dashboard`.
