# Checkpoint 44 - Self-Improvement Handoff

## Goal

Let approved self-improvement proposals become governed terminal tasks without turning the proposal system into an auto-editor.

## Implemented

- Added `aegisagent improve implement <proposal-id>` and `aegisagent improve handoff <proposal-id>`.
- Added `/improve implement <proposal-id>` and `/improve handoff <proposal-id>` to the TUI slash palette and command lanes.
- Blocked handoff for proposals that are not approved, with an `improvement.handoff_blocked` receipt.
- Queued approved handoffs through the durable task runner, with an `improvement.handoff_created` receipt.
- Stored the latest handoff task id, status, timestamp, and count on each proposal.
- Updated the capability map and README so approved handoffs are visible from the terminal surface.

## Safety

- The handoff creates a governed task only; it does not directly mutate workspace files.
- The generated task prompt carries required validation, changed-file evidence, terminal-first, no-browser, and no-raw-secret constraints.
- The task source is recorded as `improvement:<proposal-id>` for traceability.

## Verification

Run after this checkpoint:

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
