# Checkpoint 72 - Browser Session Receipts

## Goal

Make browser work explicit, terminal-visible, and auditable without returning to surprise browser launch.

## Changes

- Added workspace-local browser session records under `.aegisagent/browser_sessions/`.
- Added `aegisagent browser sessions`, `aegisagent browser open <url> --approved`, `aegisagent browser show <session-id>`, and `aegisagent browser screenshot <session-id> <path> --approved`.
- Added `/browser`, `/browser open <url> | approve`, and `/browser screenshot <session-id> | <path> | approve`.
- Added screenshot receipts that attach an existing workspace file to a browser session record.
- Updated the tool matrix so browser is `gated` with `ask open`, not `auto`.
- Updated README and the capability map to show browser sessions/evidence as partial capability and live browser control as the next explicit gap.

## Safety Notes

- Unapproved browser open returns `needs_approval` and creates no session file.
- Approved browser open creates a session record but does not launch a browser.
- Session records carry `browser_auto_launch=false` and `browser_launch_performed=false`.
- Screenshot receipts require an existing workspace file and explicit approval.
- Browser session and screenshot commands emit audit receipts with `browser_auto_launch=false`.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/config.py src/aegisagent/security/audit.py src/aegisagent/core/browser_sessions.py src/aegisagent/core/capabilities.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py tests/test_cli.py tests/test_tui.py` passed.
- Focused tests passed:
  - `tests.test_cli.CliTests.test_browser_sessions_and_screenshot_receipts_are_approval_gated`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_browser_sessions_require_approval`
  - `tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization`
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v` passed: 83 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 137 tests, 1 skipped.
- CLI/TUI smoke passed:
  - CLI unapproved browser open returned `needs_approval` and created no session record.
  - CLI approved browser open created a session with `browser_auto_launch=false` and `browser_launch_performed=false`.
  - CLI unapproved screenshot left the session unchanged; approved screenshot attached `screen.txt`.
  - TUI unapproved browser open created no session record.
  - TUI approved browser open created a session with `browser_auto_launch=false` and `browser_launch_performed=false`.
  - TUI approved screenshot receipt attached `screen-tui.txt`, and `/browser` listed the session.
  - Audit contained `browser.session.open`, `browser.session.screenshot`, and `browser_auto_launch=false`.
- Static TUI frame checks passed at `80x24`, `120x40`, and `200x60`.
- `PYTHONPATH=src python3 -m aegisagent tools --matrix` shows `browser` as gated with `ask open`.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` shows browser sessions/evidence as partial and live browser control as future work.
