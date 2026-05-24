# Checkpoint 111 - Durable Agent Run Status

## Scope

- Bound detached agent jobs to their root delegation as soon as the coordinator root is created.
- Added root-level run status for `aegis subagents --status <root-id>`, `aegis agents status <root-id>`, `/subagents status <root-id>`, and `/agents status <root-id>`.
- Made `aegis agents monitor <job-id>` terminal-readable by default while preserving JSON output behind `--json`.
- Promoted stale background jobs to completed when their detached worker died after producing a completed root.
- Documented the install, provider, background monitor, status, update, and no-browser workflow in the README and operator reference.

## Safety

- Status and monitor views redact secret-like task and worker payloads before text or JSON output.
- Status reads append audit receipts with root id, phase, status, worker count, event count, and browser/external/raw-secret safety flags.
- No browser, connector delivery, or external action is started by status, monitor, install, update, or model route inspection.

## Verification

- Focused tests:
  - `tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_subagent_formatters_are_terminal_readable`
  - `tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_subagent_run_status_redacts_secret_task_payloads`
  - `tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_background_job_recovery_marks_dead_worker_failed`
  - `tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_background_job_recovery_promotes_completed_bound_root`
  - `tests.test_cli.CliTests.test_commands_catalog_is_terminal_only_and_filterable`
  - `tests.test_cli.CliTests.test_subagent_run_status_is_terminal_readable`
  - `tests.test_cli.CliTests.test_agents_surface_wraps_bounded_subagent_runtime`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_renders_command_lanes`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_watches_subagent_timeline`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_agents_surface`
  - `tests.test_tui.TuiRendererTests.test_interactive_dispatch_background_subagent_job`

Result: passed.

Full verification:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `npm run verify` in `web/`
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps`
- `PYTHONPATH=src python3 -m aegisagent audit verify`
- `git diff --check`

Result: passed. Python reported 218 tests passing with 2 FastAPI-client skips.
