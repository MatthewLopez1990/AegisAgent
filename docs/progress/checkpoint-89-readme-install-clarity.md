# Checkpoint 89 - README install and usage clarity

## What changed

- Rebuilt the README around the installed-user path: install, first session, verify install, update, essential commands, and safety.
- Added an operating model section that states terminal-first behavior, optional web, approval gates, and secret-handle configuration.
- Clarified macOS/Linux install behavior, PATH handling, update behavior, and source-checkout development.
- Moved long command examples into `docs/operator-reference.md` so the README stays readable.
- Documented the terminal command to refresh the local shim from a source checkout.

## Verification

- README command audit against `scripts/install.sh`, `scripts/update.sh`, and `src/aegisagent/core/lifecycle.py`.
- `python3 --version`
- `sh -n scripts/install.sh && sh -n scripts/update.sh`
- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_mac_linux_installer_scripts_are_terminal_first tests.test_cli.CliTests.test_install_status_and_shim_are_terminal_only -v`
- `git diff --check`
