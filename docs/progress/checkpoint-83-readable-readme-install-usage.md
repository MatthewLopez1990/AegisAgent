# Checkpoint 83 - Readable README Install and Usage

## Scope
- Rewrote the README around the user path: install, run, update, source checkout, and first TUI commands.
- Added a clear macOS/Linux terminal install command that pulls from GitHub and explains where the shim and checkout are written.
- Added explicit update instructions for installed users (`aegis update --approved`) and source-checkout users (`git pull --ff-only origin main`).
- Moved the broad command surface out of the opening flow and into a reference section.
- Clarified that browser/web usage is optional and never part of normal install, activation, update, or health checks.
- Updated installed shim activation so custom installed command names are reflected in `activation` output.

## Verification
- Checked source activation output still reports the source command path.
- Checked installed-style activation output with `AEGIS_COMMAND_NAME=aegis` reports `aegis`, `aegis tui`, and `aegis tui --print`.
- Re-ran focused CLI/TUI activation and install lifecycle tests.
