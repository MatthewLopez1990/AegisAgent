# Checkpoint 59 - Candidate Diff Review

## Goal

Move repair candidates closer to implementation review by adding a read-only diff review path before verification or apply handoff.

## Changes

- Added `aegisagent improve diff <candidate-id>`.
- Added `aegisagent improve candidate-diff <candidate-id>` as an alias.
- Added `/improve diff <candidate-id>` to the prompt-first TUI.
- Diff review inspects candidate suggested files without shell interpolation.
- Tracked file diffs use `git diff -- <path>`.
- Untracked suggested files use a bounded `git diff --no-index` preview when available.
- Missing and unavailable files are reported explicitly.
- Diff previews are redacted and bounded.
- Added `improvement.candidate_diff_reviewed` audit receipts.
- Updated README and capability gap wording.

## Safety Notes

- Diff review is advisory and read-only.
- It does not apply patches, queue tasks, run model calls, start a browser, or perform external delivery.
- It reports `workspace_mutation_performed=false`.
- Apply handoff still requires a passing candidate verification receipt.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/improvement.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v  # 61 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v          # 105 passed, 1 skipped
CLI smoke: improve diff <candidate-id>                  # changed/missing counts shown
PTY smoke: /improve diff <candidate-id>                 # source=tui receipt recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
