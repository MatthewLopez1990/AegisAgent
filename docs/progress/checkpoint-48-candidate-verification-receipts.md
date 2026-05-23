# Checkpoint 48 - Candidate Verification Receipts

## Goal

Let advisory repair candidates run their prescribed verification commands from the terminal and persist bounded evidence without auto-applying code changes or opening a browser.

## Changes

- Added `aegisagent improve verify <candidate-id>`.
- Added `aegisagent improve verify <candidate-id> --command-index <n> --timeout <seconds>`.
- Added `/improve verify <candidate-id> [command-index]` to the prompt-first TUI.
- Persisted candidate verification runs to `.aegisagent/improvements/candidates/verification.jsonl`.
- Updated candidate records with last verification status, command, timestamp, receipt id, and count.
- Updated proposal records with candidate verification status and count for summary/action visibility.
- Added `improvement.verification_run` and `improvement.verification_blocked` audit receipts.
- Kept verification bounded to commands already listed on the candidate.

## Safety Notes

- Candidate verification does not mark a proposal implemented.
- Candidate verification does not authorize workspace mutation.
- Candidate verification reports `terminal_first=true`, `candidate_command_allowlisted=true`, `workspace_mutation_requested=false`, `external_action_started=false`, and `browser_auto_launch=false`.
- Output is redacted and truncated before persistence.

## Verification

Completed gates:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v  # 56 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v         # 100 passed, 1 skipped optional FastAPI client
PYTHONPATH=src python3 -m aegisagent improve verify <candidate-id>  # passed policy candidate command
PTY smoke: /improve verify <candidate-id> 2                         # source=tui receipt recorded
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify                   # ok, count=225
git diff --check                                                    # clean
```
