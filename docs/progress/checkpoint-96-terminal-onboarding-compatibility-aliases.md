# Checkpoint 96 - Terminal Onboarding Compatibility Aliases

## Changes

- Added conservative setup aliases that map older onboarding wording onto existing terminal-first setup sections: `model-auth` to `model`, `connections` to `connectors`, `skills` and `plugins` to `memory`, and `check`, `checks`, `verify`, and `doctor` to metadata-only setup checks.
- Added `aegis setup init`, `aegis setup --init`, and `aegis setup first-task` as explicit terminal setup entry points.
- Added matching TUI slash aliases, palette entries, and command-lane entries for the supported setup shortcuts.
- Updated the README and operator reference so install, start, update, and alias usage are clear from the terminal-user path.
- Kept unsupported historical setup lanes out of the advertised surface until real matching sections exist.

## Safety Boundary

- Aliases do not start the web gateway, launch a browser, deliver connector messages, store raw secrets, or invoke a model.
- Canonical commands remain `aegis`, `aegis tui`, `aegis setup next`, `aegis setup model`, `aegis setup --run-checks`, and `/setup next`.
- Older `Aegis-Agent` wording is treated as compatibility input only when it maps directly to behavior already implemented by this repo.

## Verification

- Focused CLI and TUI alias tests assert canonical output, metadata-only setup checks, and no runtime side effects for invalid aliases.
- Completion tests assert setup aliases and `--init` appear in generated bash, zsh, and fish completion scripts.
- README and operator-reference coverage assert the installed-user terminal path stays visible before source-development instructions.
