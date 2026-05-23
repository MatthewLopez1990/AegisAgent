# Checkpoint 85 - Progressive Setup Next

## What changed

- Added `aegis setup next` and `/setup next` as the first concrete setup action.
- Added setup priority metadata to the quickstart payload while preserving the existing `steps` shape.
- Added a JSON setup-next payload with terminal-first, metadata-only, no-browser invariants.
- Updated setup TUI cards and palette entries so the next action is visible without reading docs.
- Replaced the remaining `/setup` fallback activation copy with the installed command name.

## Boundary

The web GUI remains read-only for setup at this checkpoint. A later checkpoint can hydrate the web setup panel from gateway metadata, but first-run setup remains terminal-owned.

## Verification

Planned before commit:

- Focused CLI and TUI setup-next tests.
- Full Python unit test suite.
- Web verification.
- Shell syntax and diff checks.
- Installed `aegis setup next` smoke.
