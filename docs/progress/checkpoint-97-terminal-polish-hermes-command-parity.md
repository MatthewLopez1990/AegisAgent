# Checkpoint 97 - Terminal Polish And Hermes Command Parity

## Changes

- Added a terminal command catalog via `aegis commands` and `/commands json`, backed by the same command groups used by the live TUI.
- Added safe compatibility entrypoints from the earlier Aegis-Agent workflow: `aegis init`, `aegis setup initialize`, and hidden setup step aliases `1` through `6`.
- Polished the first-launch terminal surface with a compact setup card that keeps the composer-first path, setup commands, and browser-off boundary visible.
- Added a live TUI `?` key path that opens help immediately when the prompt is empty.
- Updated README and operator-reference command discovery around the installed terminal path.

## Safety Boundary

- This is terminal command discoverability and conservative compatibility, not broad Hermes completion.
- The command catalog is read-only and metadata-only; it does not start the web gateway, open a browser, invoke a model, deliver connector traffic, or store secrets.
- Compatibility aliases only route to existing AegisAgent setup behavior. Unsupported old surfaces such as remote control, live browser automation, plugin marketplace installs, and model login/logout are still not advertised.
- Approval-gated actions still require `--approved` or `| approve`.

## Verification

- Focused CLI tests cover command catalog filtering/JSON, setup aliases, hidden step aliases, completion output, README install/start guidance, and script browser-launch guards.
- Focused TUI tests cover command catalog rendering/JSON, first-launch copy, hidden setup step dispatch, and the `?` help key.
- Full checkpoint verification should include the Python suite, web verify, activation/setup/audit/TUI smoke checks, shell syntax checks, and `git diff --check`.
