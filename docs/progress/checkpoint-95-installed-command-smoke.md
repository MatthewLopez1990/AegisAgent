# Checkpoint 95 - Installed Command Smoke

## Changes

- Added an end-to-end installed-user smoke test that builds a disposable local Git remote, runs `scripts/install.sh`, resolves the generated `aegis` shim through PATH, runs representative README terminal commands, pushes a fake upstream update, and verifies `aegis update --approved`.
- Added a bounded PTY smoke test for the installed `aegis` shim that launches the live terminal UI, runs `/activation`, verifies browser/gateway safety markers, and cleans up deterministically.
- Added fake `open` and `xdg-open` sentinels to the smoke environment so unexpected browser launch attempts fail the test.
- Hardened `scripts/install.sh` and `scripts/update.sh` to require `python3` 3.12 or newer, matching `pyproject.toml` and the README prerequisite.
- Added explicit terminal/no-browser safety lines to individual setup-section output, so `aegis setup model` carries the same activation guarantees as `aegis setup next`.

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_readme_installed_user_commands_smoke_without_browser_launch tests.test_cli.CliTests.test_mac_linux_installer_scripts_are_terminal_first -v`
- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_installed_shim_launches_live_tui_in_pty_without_browser -v`
- `sh -n scripts/install.sh && sh -n scripts/update.sh && git diff --check`
