# Checkpoint 66 - Typed Git Commit

## Goal

Add approval-gated typed git commit creation so terminal coding workflows can move from staged changes to a repository history update without raw `git commit` shell commands.

## Changes

- Added `git.commit` to `WorkspaceToolRunner`.
- The tool requires a non-empty commit message and at least one staged file.
- Without approval the tool returns `needs_approval` and does not create a commit.
- With explicit approval the tool runs `git commit -m <message>` through argv, not shell parsing.
- Added `aegisagent git commit --message "<message>" --approved`.
- Added `/git commit <message> | approve`.
- Updated README and capability map to reflect approval-gated typed commits.

## Safety Notes

- Workspace file contents are not modified by the tool.
- Git history mutation is false until explicit approval is present.
- The tool records `workspace_mutation_performed=false`, `git_history_mutation_performed`, `external_action_started=false`, and `browser_auto_launch=false`.
- The tool refuses to commit when no staged files are present.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 99 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 120 passed, 1 skipped
CLI smoke: unapproved `aegisagent git commit` previews without creating HEAD
CLI smoke: approved `aegisagent git commit` creates the temp-repo commit
TUI smoke: `/git commit ... | approve` commits through typed tool dispatch
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
