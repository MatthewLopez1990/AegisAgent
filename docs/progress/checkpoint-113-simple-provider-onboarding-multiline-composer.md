# Checkpoint 113 - Simple provider onboarding and multiline composer

Status: install and model-provider setup are simpler from the terminal, and the live TUI composer supports multiline prompts.

## Changes

- Reworked the README quick start around install, `aegis`, `aegis connect local`, `aegis connect openai`, and `aegis update --approved`.
- Added a top-level `aegis connect <provider>` shortcut that routes to the existing guarded model-provider connection flow.
- Changed `aegis model doctor` to plain text by default, with JSON still available through `--json`.
- Added model-help examples for local, OpenAI, and OpenAI-compatible providers.
- Made the installer output mirror the shorter first-run path and update output include verification.
- Baked the installer-selected `AEGIS_PYTHON` value into generated shims so installs using a specific Python 3.12 path keep working later.
- Hardened install/update branch validation with `git check-ref-format --branch`.
- Made `health` fail closed when the audit chain is broken and made audit verification report malformed entries instead of raising.
- Added live TUI composer controls for `Ctrl+V` newline insertion, `Home`/`End`, and `Ctrl+U` clear-before-cursor.
- Preserved explicit composer newlines as real wrapped rows aligned under the prompt.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest -v ...` focused onboarding and composer tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed: 227 tests, 2 expected FastAPI skips.
- `cd web && npm run verify` passed.
- `sh -n scripts/install.sh && sh -n scripts/update.sh` passed.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` passed.
- `PYTHONPATH=src python3 -m aegisagent audit verify` passed.
- `PYTHONPATH=src python3 -m aegisagent health` passed.
- `git diff --check` passed.
