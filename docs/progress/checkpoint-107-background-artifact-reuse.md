# Checkpoint 107 - Background Artifact Reuse

## Scope

Carry the existing approved artifact reuse model through detached/background
agent jobs so durable terminal work can continue from approved prior context.

## Implemented

- Added reusable artifact ids and approval state to persisted background job
  records.
- Background job creation now uses the same dedupe, max-eight cap, approval
  requirement, and artifact integrity validation as foreground delegation.
- Background worker execution revalidates persisted artifact ids through the
  normal delegation path before passing metadata to planner, researcher,
  implementer, and reviewer workers.
- CLI and TUI background agent commands now accept approved artifact reuse:
  `aegis agents bg ... --use-artifact <id> --approved` and
  `/agents bg ... | use-artifact <id> | approve`.

## Safety

- Unapproved background artifact reuse fails before a job is queued.
- Reuse persists artifact ids only; raw artifact bodies and filesystem paths are
  not sent as model context by reuse.
- Background reuse does not add browser launch, connector delivery, unsandboxed
  tool grants, or raw secret storage.

## Verification

- Focused background reuse tests for core orchestration, CLI, and TUI.
- Full unit test discovery.
- Web verification, capability/audit checks, CLI smoke, and diff whitespace
  checks before commit.

## Remaining

- Add opt-in higher-depth delegation controls instead of merely advertising the
  `max_depth=2` queue limit.
- Continue global backlog: live browser control behind explicit approval,
  broader integrations/live connector delivery, signed skill trust,
  multi-provider fallback ordering/subscription bridge readiness, and packaged
  release flows.
