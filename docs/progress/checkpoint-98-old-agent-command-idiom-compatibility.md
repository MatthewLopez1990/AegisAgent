# Checkpoint 98 - Old-Agent Command Idiom Compatibility

Date: 2026-05-24

## Scope

This checkpoint adds small compatibility aliases for older agent command habits
only where the alias maps directly to existing AegisAgent terminal behavior.

## Implemented

- Added `aegis task ...` as a singular CLI alias for the governed task queue.
- Added `aegis models ...` as a CLI alias for `aegis model ...`.
- Added read-only `aegis model auth status`, `methods`, and `doctor` forms.
- Added `aegis memory search <query>` and `aegis memory index`.
- Added TUI root shortcuts and catalog metadata for `/task`, `/model`, and
  `/memory`.
- Added TUI read-only model auth and memory search/index slash handling.
- Reworked README install, update, and use sections so a new macOS/Linux user
  can install from GitHub, start the terminal UI, and update the installed agent.

## Safety Boundary

These aliases do not add old login/logout flows, remote-control behavior,
browser startup, gateway startup, connector delivery, external model invocation,
or raw-secret storage. Canonical commands remain the primary commands for
documentation and automation.

Unsupported old commands such as `model auth login`, `model auth logout`,
`task pause`, `task resume`, and old external-memory management commands remain
rejected or explicitly unsupported.

## Verification

Focused coverage was added for:

- singular `task` CLI queue aliases
- `models` and read-only model auth aliases
- `memory search` and `memory index`
- TUI slash palette, command catalog, model auth, and memory search/index

Verification completed:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v     # 205 passed, 2 skipped
cd web && npm run verify                                     # build + smoke passed
PYTHONPATH=src python3 -m aegisagent activation              # passed
PYTHONPATH=src python3 -m aegisagent commands task           # passed
PYTHONPATH=src python3 -m aegisagent model auth status       # passed
PYTHONPATH=src python3 -m aegisagent models doctor           # passed
PYTHONPATH=src python3 -m aegisagent memory index            # passed
PYTHONPATH=src python3 -m aegisagent audit verify            # passed
PYTHONPATH=src python3 -m aegisagent tui --print --width 100 --height 32  # passed
sh -n scripts/install.sh                                     # passed
sh -n scripts/update.sh                                      # passed
git diff --check                                             # passed
```
