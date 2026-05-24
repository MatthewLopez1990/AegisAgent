# Checkpoint 90 - Memory review controls

## What changed

- Added terminal memory review controls:
  - `aegis memory list`
  - `aegis memory show <entry-id>`
  - `aegis memory delete <entry-id> --approved`
  - `/memory list`
  - `/memory show <entry-id>`
  - `/memory delete <entry-id> | approve`
- Curated memory entries now use stable content-derived IDs and bounded marker blocks so body headings do not become separate delete targets.
- Memory list/show output is redacted, and show/list/delete attempts are audited without logging note bodies.
- Approved delete removes the markdown block, deletes the matching SQLite memory row, rebuilds the FTS index, and records pre/post file hashes.
- Memory add/delete blocks symlink targets and only mutates the governed `MEMORY.md` or `USER.md` files inside `.aegisagent/memory`.

## Safety boundary

- `list`, `show`, `query`, and `index` are read-only.
- `add` and `delete` require explicit approval.
- Delete blocks if an entry has changed after it was written.
- Memory controls do not launch browsers, start gateways, call models, or perform network actions.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/memory.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py`
- `PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_curated_memory_entries_list_show_delete_with_redaction tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_curated_memory_writes_block_symlink_targets tests.test_cli.CliTests.test_memory_list_show_delete_cli_are_approval_gated_and_redacted tests.test_tui.TuiRendererTests.test_interactive_dispatch_memory_list_show_delete_are_approval_gated_and_redacted tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization -v`
