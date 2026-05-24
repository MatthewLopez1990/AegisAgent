# Checkpoint 94 - README Terminal Onboarding

## Changes

- Rewrote the README around the installed-user path: prerequisite checks, one-line macOS/Linux installer, command discovery, setup checks, first TUI launch, and GitHub update.
- Made `aegis update --approved` the primary update path and kept `~/.aegis-agent/scripts/update.sh` as recovery-only.
- Kept optional web console instructions separate from normal terminal use and repeated the no-browser guarantee only where it affects install/update/launch expectations.
- Added a README regression test that checks ordering and the exact terminal install/update commands.

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_readme_leads_with_installed_user_terminal_flow tests.test_cli.CliTests.test_mac_linux_installer_scripts_are_terminal_first -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `cd web && npm run verify`
- `PYTHONPATH=src python3 -m aegisagent tui --print --width 100 --height 32`
- `PYTHONPATH=src python3 -m aegisagent audit verify`
- `git diff --check`
