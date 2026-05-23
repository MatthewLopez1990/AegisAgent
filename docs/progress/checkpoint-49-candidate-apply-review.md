# Checkpoint 49 - Candidate Apply Review

## Goal

Move verified repair candidates into a governed implementation review path without turning self-improvement into an auto-editor.

## Changes

- Added `aegisagent improve apply <candidate-id>`.
- Added `aegisagent improve apply <candidate-id> --background`.
- Added `/improve apply <candidate-id>` to the prompt-first TUI.
- Required a passing candidate verification receipt before apply handoff.
- Queued verified candidates into the durable task system with source `improvement-candidate:<candidate-id>`.
- Included suggested files, patch plan, verification commands, risk notes, and the last verification receipt in the task prompt.
- Stored apply task id, status, timestamp, and count on the candidate record.
- Updated the proposal handoff fields so status and task watching remain visible through existing proposal surfaces.
- Added `improvement.candidate_apply_created` and `improvement.candidate_apply_blocked` audit receipts.

## Safety Notes

- Apply review queues work; it does not apply patches by itself.
- Candidates still require changed-file evidence before completion.
- The command reports `terminal_first=true`, `verified_candidate_required=true`, `workspace_mutation_allowed_before_approval=false`, `external_action_started=false`, and `browser_auto_launch=false`.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v  # 56 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v         # 100 passed, 1 skipped optional FastAPI client
PYTHONPATH=src python3 -m aegisagent improve apply <candidate-id>   # blocked before verification, queued after passing verification
PTY smoke: /improve apply <candidate-id>                            # source=tui receipt recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify                   # ok, count=225
git diff --check                                                    # clean
```
