# Checkpoint 79 - Lifecycle Security Hardening

## Scope
- Hardened terminal lifecycle commands after parallel GPT-5.5 xHigh review.
- Exact-matched `/activation`, `/dashboard`, `/install`, and `/update` so typo-prefixed commands cannot enter lifecycle handlers.
- Added `/dashboard`, `/install`, and `/update` to terminal activation guidance.
- Deduplicated lifecycle slash palette entries and exposed `/agents live` / `/agents stream`.
- Tightened raw shell policy so only explicit read-only git commands are allowed without approval.
- Restricted typed unittest verification paths to the workspace.
- Improved audit receipts so typed git/lifecycle operations preserve `external_action_started=true`.
- Expanded secret redaction to `api_key`, `authorization`, and bearer-style keys.
- Hardened install/update scripts with branch validation, origin checks, and dirty-checkout refusal.

## Verification
- Added approved CLI update coverage against a local bare remote.
- Added approved TUI install and update coverage without touching the real home directory.
- Added tests for exact slash lifecycle matching, slash command uniqueness, activation lifecycle commands, shell git approval policy, redaction, workspace-only verification paths, and installer script syntax/safety markers.
