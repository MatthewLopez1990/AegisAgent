# Checkpoint 19 - Typed File and Git Tools

Status: read-only file and git inspection tools are terminal-facing

Decision:

- The terminal agent should not need raw shell for common read-only inspection.
- File and git inspection should be typed, workspace-scoped, redacted, and audited.
- Prompt turns and slash commands should use the same tool runner so behavior stays consistent.

Implemented in this checkpoint:

- `WorkspaceToolRunner` exposes `workspace.read_file`, `git.status`, and `git.diff`.
- File reads reject paths outside the workspace and skip protected state directories.
- File, git status, and git diff output are redacted before display or persistence.
- Prompt turns summarize `workspace.read_file`, `git.status`, and `git.diff` tool results.
- TUI slash additions: `/read <path>`, `/git status`, and `/git diff [path]`.
- Direct TUI tool calls append session tool messages and write `tui.tool.completed` receipts.
- Git diff can be scoped to a workspace path without shell interpolation.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice tests.test_tui -v
```

Still incomplete:

- Rich file editing and patch application as governed typed tools.
- Structured git branch/commit/push workflows with approvals.
- Model-backed reasoning over larger file sets beyond local deterministic summaries.
