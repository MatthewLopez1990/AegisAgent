# Checkpoint 65 - Typed Git Stage

## Goal

Add the first approval-gated typed git index mutation so terminal coding workflows can prepare changes without falling back to raw `git add` shell commands.

## Changes

- Added `git.stage` to `WorkspaceToolRunner`.
- The tool accepts explicit workspace file paths only and blocks skipped state/build directories.
- Without approval the tool returns `needs_approval` and does not mutate the git index.
- With explicit approval the tool runs `git add -- <paths>` through argv, not shell parsing.
- Added `aegisagent git stage <path> --approved`.
- Added `/git stage <path> [path...] | approve`.
- Updated README and capability map to reflect approval-gated typed git staging.

## Safety Notes

- Workspace file contents are not modified.
- Git index mutation is false until explicit approval is present.
- The tool records `workspace_mutation_performed=false`, `git_index_mutation_performed`, `external_action_started=false`, and `browser_auto_launch=false`.
- Paths stay inside the workspace and cannot target `.git`, `.aegisagent`, build output, caches, or dependency directories.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 96 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 117 passed, 1 skipped
CLI smoke: unapproved `aegisagent git stage` previews without changing the index
CLI smoke: approved `aegisagent git stage` stages only the explicit temp-repo path
TUI smoke: `/git stage ... | approve` stages through typed tool dispatch
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
