# Checkpoint 68 - Typed Git Remote Push

## Goal

Add a typed remote inspection and push path so terminal coding workflows can cross the remote boundary with explicit approval and audit receipts instead of raw `git push` shell commands.

## Changes

- Added `git.remote` to `WorkspaceToolRunner`.
- Remote listing is read-only and does not require approval.
- Remote push requires an explicit safe remote name, explicit safe branch name, and approval.
- Without approval push returns `needs_approval` and does not contact the remote.
- With approval push runs `git push <remote> <branch>` through argv, not shell parsing.
- Added `aegisagent git remote` and `aegisagent git remote push <remote> <branch> --approved`.
- Added `/git remote` and `/git remote push <remote> <branch> | approve`.
- Updated README and capability map to reflect approval-gated typed remote pushes.

## Safety Notes

- Workspace file contents are not modified by the tool.
- Remote mutation is false until explicit approval is present.
- Approved push records `external_action_started=true`, `network_capable_git_operation=true`, `git_remote_mutation_performed`, and `browser_auto_launch=false`.
- Remote and branch names are validated before any push is attempted.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 105 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 126 passed, 1 skipped
CLI smoke: `aegisagent git remote` lists a local bare remote
CLI smoke: unapproved `aegisagent git remote push origin main` leaves the remote ref absent
CLI smoke: approved `aegisagent git remote push origin main --approved` creates the remote ref
TUI smoke: `/git remote`, `/git remote push origin main`, and `/git remote push origin main | approve`
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
