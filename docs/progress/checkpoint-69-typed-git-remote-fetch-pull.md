# Checkpoint 69 - Typed Git Remote Fetch/Pull

## Goal

Add typed remote fetch and fast-forward pull paths so terminal coding workflows can inspect and update from upstream without raw `git fetch` or `git pull` shell commands.

## Changes

- Extended `git.remote` in `WorkspaceToolRunner`.
- Remote listing remains read-only and does not require approval.
- Remote fetch requires an explicit safe remote name and approval; an explicit branch is optional.
- Remote pull requires an explicit safe remote name, explicit safe branch name, and approval.
- Pull uses `git pull --ff-only <remote> <branch>` to avoid merge commits from the typed tool.
- Added `aegisagent git remote fetch <remote> [branch] --approved`.
- Added `aegisagent git remote pull <remote> <branch> --approved`.
- Added `/git remote fetch <remote> [branch] | approve` and `/git remote pull <remote> <branch> | approve`.
- Updated README and capability map to reflect approval-gated typed remote fetch/pull.

## Safety Notes

- Fetch does not mutate workspace files, but it may mutate local remote refs after approval.
- Pull may mutate workspace files after approval and records that separately.
- Unapproved fetch/pull returns `needs_approval` and does not contact the remote.
- Approved fetch/pull records `external_action_started=true`, `network_capable_git_operation=true`, `git_ref_mutation_performed`, and `browser_auto_launch=false`.

## Verification

- `python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v` passed: 108 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 129 tests, 1 skipped.
- CLI local bare-remote smoke passed:
  - unapproved fetch returned `needs_approval` and left `origin/main` unchanged.
  - approved fetch updated `origin/main` without mutating the workspace file.
  - unapproved pull returned `needs_approval` and left the workspace file unchanged.
  - approved pull fast-forwarded the workspace file from `v1` to `v2`.
- TUI dispatch local bare-remote smoke passed:
  - `/git remote fetch origin main` returned `needs_approval`.
  - `/git remote fetch origin main | approve` updated the remote ref only.
  - `/git remote pull origin main | approve` fast-forwarded the workspace file.
  - audit receipts included `git_ref_mutation_performed`, `workspace_mutation_performed`, and `browser_auto_launch=false`.
- Static TUI frame checks passed at `80x24`, `120x40`, and `200x60`.
- `PYTHONPATH=src python3 -m aegisagent health` passed with `ok=true`.
- `PYTHONPATH=src python3 -m aegisagent audit verify` passed with `ok=true`.
- `git diff --check` passed.
- `__pycache__` directories were removed after verification.
