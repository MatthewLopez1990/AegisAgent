# Checkpoint 67 - Typed Git Branch

## Goal

Add typed branch listing, creation, and switching so terminal coding workflows can manage implementation checkpoints without raw `git branch` or `git switch` shell commands.

## Changes

- Added `git.branch` to `WorkspaceToolRunner`.
- Branch listing is read-only and does not require approval.
- Branch creation and switching require explicit approval.
- Branch names are locally validated before any git ref mutation is attempted.
- Added `aegisagent git branch create <name> --approved`.
- Added `aegisagent git branch switch <name> --approved`.
- Added `/git branch`, `/git branch create <name> | approve`, and `/git branch switch <name> | approve`.
- Updated README and capability map to reflect approval-gated typed branch operations.

## Safety Notes

- Workspace file contents are not modified by the tool.
- Git ref mutation is false until explicit approval is present.
- The tool records `workspace_mutation_performed=false`, `git_ref_mutation_performed`, `external_action_started=false`, and `browser_auto_launch=false`.
- Unsafe branch names are blocked before execution.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 102 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 123 passed, 1 skipped
CLI smoke: `/git branch` lists branches without approval
CLI smoke: unapproved branch create/switch previews do not mutate refs
CLI smoke: approved branch create/switch mutates only the temp repo
TUI smoke: `/git branch`, `/git branch create ... | approve`, and `/git branch switch ... | approve`
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
