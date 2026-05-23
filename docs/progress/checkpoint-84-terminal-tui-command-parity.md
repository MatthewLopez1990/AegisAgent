# Checkpoint 84 - Terminal TUI and Command Parity

## Scope
- Tightened the terminal-first TUI around the reference contract: setup now renders selectable-style vault cards, tools renders a policy inspector with recent receipts, and static help exposes the keyboard model.
- Added `tui --print --view help` so the keyboard/command model can be verified without launching curses.
- Fixed dead `/policy <tool>` panel commands by adding a generic terminal policy inspector while preserving the special `/policy shell <command>` path.
- Made installed command naming flow through setup, capabilities, dashboard, argparse help, and generated shims so installed users see `aegis` as the first-class command.
- Fixed the generated shim to export `AEGIS_COMMAND_NAME`; without export, `aegis activation` could still report `aegisagent`.
- Added focused tests for static render geometry at 80x24, 120x40, and 200x60, TUI help content, policy inspector commands, installed shim activation, invalid shim names, non-git update blocking, and TTY activation routing.

## Verification
- Ran focused TUI tests covering static geometry, setup/tools/help affordances, policy inspector commands, and interactive dispatch.
- Ran focused CLI tests covering installed shim activation, command-name copy, update blocking, invalid shim names, and TTY activation.
- Verified setup/dashboard output with `AEGIS_COMMAND_NAME=aegis` shows installed-command copy and keeps browser/web optional.
