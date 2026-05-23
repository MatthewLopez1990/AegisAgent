# Checkpoint 64 - Typed Edit Replace

## Goal

Add the first approval-gated typed file mutation so terminal work can move beyond read/test tools without relying on arbitrary shell writes.

## Changes

- Added `workspace.replace_text` to `WorkspaceToolRunner`.
- The tool stays inside the workspace and blocks skipped state/build directories.
- The old text must match exactly once to avoid broad or ambiguous edits.
- Without approval the tool returns a redacted preview and performs no mutation.
- With explicit approval the tool replaces one exact text span and records mutation metadata.
- Added `aegisagent edit replace <path> --old <text> --new <text> --approved`.
- Added `/edit replace <path> | <old text> | <new text> | approve`.
- Updated README and capability map to reflect approval-gated typed edits.

## Safety Notes

- Workspace mutation is false until explicit approval is present.
- Raw secret-like old/new text is redacted in tool output.
- The tool does not use shell parsing.
- The tool records `workspace_mutation_performed`, `external_action_started=false`, and `browser_auto_launch=false`.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 93 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 114 passed, 1 skipped
CLI smoke: unapproved `aegisagent edit replace` previews without changing the file
CLI smoke: approved `aegisagent edit replace` mutates the file and records metadata
TUI smoke: `/edit replace ... | approve` mutates through typed tool dispatch
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
