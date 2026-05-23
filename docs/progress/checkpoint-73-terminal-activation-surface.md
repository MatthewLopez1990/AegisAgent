# Checkpoint 73 - Terminal Activation Surface

## Goal

Make the terminal activation path explicit inside both CLI and TUI surfaces, and tighten the static TUI snapshot so Aegis reads as a prompt-first terminal agent rather than a browser-first console.

## Changes

- Added shared `aegisagent.core.activation` payload and formatter for terminal startup instructions.
- Added `aegisagent activation` as a non-launching readiness/status command.
- Kept `aegisagent activate` as the launch command: TTY launches the TUI, non-TTY prints the same activation card.
- Added `/activation` and `/activate` in the TUI dispatcher.
- Added `aegisagent tui --view activation --print` for terminal snapshot checks and docs.
- Updated the static command TUI frame with stable ASCII panels, clearer prompt-first copy, and browser-off startup language.
- Updated README quick start and TUI command references.

## Safety Notes

- `aegisagent activation` never starts the gateway, launches a browser, performs network I/O, or mutates the workspace.
- Activation payloads carry `terminal_first=true`, `browser_required=false`, `browser_auto_launch=false`, `gateway_started=false`, and `external_action_started=false`.
- `/activation` is read-only and uses the same shared formatter as the CLI.
- The optional web GUI remains explicit through `/web` or `aegisagent web`.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/activation.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/tui/renderer.py` passed.
- Focused activation/TUI tests passed:
  - `tests.test_cli.CliTests.test_no_args_explains_terminal_activation_without_web`
  - `tests.test_cli.CliTests.test_activate_command_is_terminal_first_non_tty_card`
  - `tests.test_cli.CliTests.test_activation_command_is_terminal_status_only`
  - `tests.test_cli.CliTests.test_tui_default_launches_interactive_terminal_not_web`
  - `tests.test_cli.CliTests.test_tui_help_explains_terminal_activation_and_print_fallback`
  - `tests.test_tui.TuiRendererTests.test_command_view_contains_prompt_and_security`
  - `tests.test_tui.TuiRendererTests.test_activation_view_and_command_are_browser_off`
  - `tests.test_tui.TuiRendererTests.test_setup_and_tools_views_fit_reference_sizes`
  - `tests.test_tui.TuiRendererTests.test_interactive_panel_model_has_terminal_agent_controls`
  - `tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization`
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v` passed: 85 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 139 tests, 1 skipped.
- Static activation snapshot passed:
  - `PYTHONPATH=src python3 -m aegisagent tui --view activation --print --width 100 --height 32`
- Static command snapshots passed:
  - `PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24`
  - `PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40`
