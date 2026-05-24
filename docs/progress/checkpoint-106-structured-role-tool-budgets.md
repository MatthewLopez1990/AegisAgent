# Checkpoint 106 - Structured Role Tool Budgets

## Scope

Add structured role-specific budget policies to planner, researcher, implementer,
and reviewer subagent contracts while keeping browser launch, external delivery,
and mutation boundaries behind the existing typed approval policy.

## Implemented

- Added contract metadata for max tool calls, max artifacts, allowed tool groups,
  denied tool groups, edit/test/network flags, external-delivery denial, and
  approval escalation.
- Carried the budget policy into worker session metadata, role prompts, contract
  JSON, CLI/TUI contract views, dashboard posture, and worker completion audit
  receipts.
- Checked worker artifact count and safety flags fail-closed before recording a
  worker as completed.
- Simplified the README and installer next steps so new macOS/Linux users see
  install, model connect, run, and update commands up front.

## Safety

- Budget policy is contract metadata plus artifact/safety validation, not a
  separate tool sandbox claim.
- File, git, browser, connector, memory, and external-state mutations still use
  the typed approval path.
- The install/update path remains terminal-only and does not open a browser.

## Verification

- Focused subagent, CLI, and TUI tests.
- Full `python3 -m unittest discover -s tests -v`.
- Web verification.
- Capability, audit, CLI smoke, script syntax, and diff whitespace checks.

## Remaining

- Add higher-depth delegation controls.
- Add approved detached-job artifact reuse.
- Continue global backlog: live browser control behind explicit approval,
  broader integrations/live connector delivery, signed skill trust,
  multi-provider fallback ordering/subscription bridge readiness, and packaged
  release flows.
