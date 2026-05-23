# Checkpoint 47 - Repair Candidates

## Goal

Move self-improvement closer to Hermes-style repair planning by generating durable advisory repair candidates from approved proposals while preserving the no-auto-edit safety contract.

## Implemented

- Added `aegisagent improve candidate <proposal-id>`.
- Added `aegisagent improve candidate-show <candidate-id>`.
- Added `/improve candidate <proposal-id>` and `/improve candidate show <candidate-id>` to the TUI.
- Persisted candidate JSON records under `.aegisagent/improvements/candidates/`.
- Stored latest candidate id, status, timestamp, and count on the proposal record.
- Candidates include suggested files, patch plan, verification commands, and risk notes.

## Safety

- Candidate generation requires an approved proposal.
- Candidates are advisory only and do not mutate workspace files.
- Candidate receipts record `workspace_mutation_performed=false`, `external_action_started=false`, and `browser_auto_launch=false`.
- Evidence and completion still require explicit changed files and verification results.

## Verification

Run after this checkpoint:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
