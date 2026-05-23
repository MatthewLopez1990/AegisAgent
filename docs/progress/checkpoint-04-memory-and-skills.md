# Checkpoint 04 - Memory And Skills

Status: scaffolded

Implemented:

- Curated workspace memory files: `.aegisagent/memory/MEMORY.md` and `.aegisagent/memory/USER.md`.
- SQLite memory table with FTS5 search when available and fallback `LIKE` search.
- CLI indexing/search through `aegisagent memory`.
- AgentSkills-compatible `SKILL.md` discovery.
- Basic risky-marker quarantine for dangerous skill bodies.

Remaining production work:

- Signed skill bundle verification.
- Per-scope bundled/global/workspace skill priority rules.
- Rich session transcript ingestion.
