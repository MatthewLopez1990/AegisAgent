# Checkpoint 112 - Composer Path Completion

## Scope

- Added live TUI composer `@path` completion for workspace files and directories.
- Added wrapped composer rendering so long prompts stay visible above the footer instead of clipping to one line.
- Updated help, README, operator reference, footer copy, and PLAN.md to distinguish TUI composer completion from shell completion.
- Tightened workspace list/search traversal so symlink files are not followed.
- Tightened `/add-dir` so hidden, internal, symlink, and outside-workspace directories are blocked.

## Safety

- `@path` completion only lists local directory metadata.
- Completion rejects absolute paths, `..` traversal, hidden paths, skipped internal roots, and symlinks.
- `/add-dir` now follows the same hidden/internal/symlink boundary for context directory registration.
- Completion does not read file bodies, call a model, open a browser, start the gateway, use the network, write audit/session records, or mutate the workspace.
- The submitted request still goes through the normal Aegis tool and approval policy.

## Verification

- Focused tests cover workspace-scoped suggestions, escape rejection, no file-body reads during completion, symlink suppression, fake-curses Tab completion, wrapped composer layout, and help text.
- Full verification:
  - `PYTHONPATH=src python3 -m unittest discover -s tests -v`
  - `npm run verify` in `web/`
  - `PYTHONPATH=src python3 -m aegisagent capabilities --gaps`
  - `PYTHONPATH=src python3 -m aegisagent audit verify`
  - `git diff --check`

Result: passed. Python reported 223 tests passing with 2 FastAPI-client skips.
