# Checkpoint 74 - Agent Role Contracts

## Goal

Move the multi-agent surface closer to the prior Aegis-Agent/Hermes-style terminal workflow by making subagent role expectations visible, auditable, and reusable instead of leaving planner/researcher/implementer/reviewer behavior as hidden prompt text.

## Comparison Notes

- The referenced `MatthewLopez1990/Aegis-Agent` repo is reachable at commit `f3b4396958421b9cb40eecb38573fd771ae592a3` on `main`.
- That repo's terminal direction includes a prompt-first Aegis Shield surface, setup/readiness guidance, richer task/session continuity, and feature-parity dashboards.
- This checkpoint targets the current repo's active `Agents and subagents` gap: stronger role-specific context contracts and tool budgets.

## Changes

- Added `AGENT_CONTRACT_VERSION` and first-class contracts for planner, researcher, implementer, and reviewer roles.
- Added context contract, deliverable, and tool-budget fields to every agent profile.
- Added `aegisagent agents contracts` and `/agents contracts`.
- Updated `aegisagent agents profiles` to show deliverables and budgets.
- Persisted contract metadata into each subagent session message.
- Added contract version and worker contracts to delegation start/completion audit receipts.
- Updated capability-map copy and README command references.

## Safety Notes

- Role contracts are terminal-visible metadata only; they do not grant extra tools or bypass approvals.
- Delegation still runs through bounded local subagents with `max_concurrency=8`, `max_depth=2`, and `max_children=5`.
- Contract output carries `terminal_first=true` and `browser_auto_launch=false`.
- Audit receipts now include the contract version so future delegation summaries can be tied to the role policy used at run time.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/subagents.py src/aegisagent/core/capabilities.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py tests/test_cli.py tests/test_tui.py tests/test_memory_skills_subagents.py` passed.
- Focused tests passed:
  - `tests.test_cli.CliTests.test_agents_surface_wraps_bounded_subagent_runtime`
  - `tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_agents_surface`
  - `tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_local_subagent_orchestrator_persists_workers_and_receipts`
- `PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_memory_skills_subagents tests.test_terminal_agent_slice -v` passed: 128 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 139 tests, 1 skipped.
- CLI smoke passed:
  - `PYTHONPATH=src python3 -m aegisagent agents contracts`
  - `PYTHONPATH=src python3 -m aegisagent agents delegate "blend prior Aegis terminal contracts"`
- TUI dispatch smoke passed for `/agents contracts`.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` now shows role contracts under `Agents and subagents`.
