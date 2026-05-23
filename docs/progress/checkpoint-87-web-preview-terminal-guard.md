# Checkpoint 87 - Web Preview Terminal Guard

## What changed

- Changed `aegis web` from a gateway-starting command into a preview-only command.
- Added `aegis web --serve --approved` for the explicit optional local gateway path.
- Updated terminal activation copy so optional web instructions distinguish preview from server start.
- Updated `/web` inside the TUI to show the installed terminal command and no-browser/no-gateway flags.
- Replaced the static TUI's fake transcript and fake pending approval with a clean idle terminal state.
- Tightened static activation and footer copy around real slash-command actions.
- Added tests so default terminal activation and web preview cannot regress into a gateway-first path.

## Verification

Planned before commit:

- Focused CLI and TUI tests for activation and web preview.
- Installed command smoke for `aegis web` and activation output.
- Full Python test suite.
- Web verify.
