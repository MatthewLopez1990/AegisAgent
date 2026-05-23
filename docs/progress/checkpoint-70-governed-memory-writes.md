# Checkpoint 70 - Governed Memory Writes

## Goal

Add an explicit terminal-first memory write path so Aegis can persist curated operator and workspace notes without raw file edits or silent memory mutation.

## Changes

- Added approval-gated curated memory notes through `MemoryStore.add_curated_note`.
- Supported `workspace` notes in `MEMORY.md` and `user` notes in `USER.md`.
- Redacts title/body before durable write and SQLite memory indexing.
- Added `aegisagent memory --kind <workspace|user> --title <title> --add <body> --approved`.
- Added `/memory add <workspace|user> | <title> | <body> | approve`.
- Unapproved memory writes return `needs_approval` and leave curated memory files unchanged.
- Approved memory writes append to the curated memory file, index the note for search, and emit audit metadata.
- Updated README and the terminal capability map so memory writes are no longer listed as the immediate next typed-tool gap.

## Safety Notes

- The memory write path only targets workspace-local `.aegisagent/memory/MEMORY.md` or `.aegisagent/memory/USER.md`.
- Writes require explicit approval and record `memory_write_performed`, `workspace_mutation_performed`, `external_action_started=false`, and `browser_auto_launch=false`.
- Title and body are bounded and redacted before persistence.

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/memory.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py` passed.
- `PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_cli tests.test_tui -v` passed: 90 tests.
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v` passed: 132 tests, 1 skipped.
- CLI smoke passed:
  - unapproved `aegisagent memory --kind user --title ... --add ...` returned `needs_approval`.
  - unapproved preview left `USER.md` unchanged.
  - approved rerun appended to `USER.md`.
  - `aegisagent memory --query terminal-first` found the approved note.
  - audit contained `memory.note.add` and `browser_auto_launch=false`.
- TUI smoke passed:
  - `/memory add user | Terminal preference | Prefers terminal-first activation.` returned `needs_approval`.
  - approved `/memory add ... | approve` appended to `USER.md`.
  - audit contained `memory_write_performed=true`.
- Static TUI frame checks passed at `80x24`, `120x40`, and `200x60`.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` shows the updated memory capability gap.
