# Checkpoint 104 - Approved Artifact Reuse

Date: 2026-05-24

## Scope

Add explicit, approval-gated reuse of selected prior role artifacts as bounded context for a later delegation. This checkpoint keeps artifact browsing read-only by default and does not implement automatic artifact graph synthesis.

## Implemented

- Added `--use-artifact <artifact-id>` plus `--approved` for `aegis agents delegate`, `aegis agents stream`, `aegis subagents --delegate`, and `aegis subagents --stream`.
- Added TUI pipe syntax for `/agents delegate ... | use-artifact <id> | approve`, `/agents live ... | use-artifact <id> | approve`, `/subagents ... | use-artifact <id> | approve`, and `/subagents live ... | use-artifact <id> | approve`.
- Reused artifact ids are deduplicated, capped, recorded on the root session, and copied into worker `input_artifacts` before same-run predecessor artifacts.
- Reuse audit receipts record approval, artifact ids, roles, kinds, hashes, byte counts, and no-browser/no-secret safety flags.
- Delegation results now expose separate reused and generated artifact counts while keeping generated worker artifacts as the main `artifacts` list.
- Reused artifacts are passed as summary metadata only. Artifact bodies and filesystem paths are not sent as model context by reuse.

## Safety Boundary

- Supplying reusable artifact ids without explicit approval blocks before workers start.
- Artifact reuse validates stored artifact bytes and SHA-256 before passing metadata to workers.
- Background jobs do not silently accept reuse flags; reuse is limited to foreground delegate and stream commands until job payloads persist approved artifact ids.
- This is approved context handoff only. Final synthesis over artifact graphs remains future work.

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_cross_delegation_artifact_reuse_requires_approval_and_audits_safety_flags tests.test_cli.CliTests.test_subagents_cli_reuses_artifact_only_after_approval_and_audits_safety_flags tests.test_cli.CliTests.test_agents_delegate_routes_workers_to_ready_provider_without_browser tests.test_cli.CliTests.test_agents_surface_wraps_bounded_subagent_runtime tests.test_tui.TuiRendererTests.test_interactive_dispatch_runs_subagent_delegation tests.test_tui.TuiRendererTests.test_interactive_dispatch_agents_surface -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `cd web && npm run verify`
- CLI smoke: approved and unapproved `aegis agents delegate --use-artifact` paths plus `aegis audit verify`.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps`
- `PYTHONPATH=src python3 -m aegisagent audit verify`
- `git diff --check`

## Remaining

- Add richer role-specific tool budgets.
- Add higher-depth delegation controls.
- Add final synthesis over artifact graphs.
