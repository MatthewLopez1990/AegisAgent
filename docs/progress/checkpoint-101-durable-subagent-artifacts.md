# Checkpoint 101 - Durable Subagent Artifacts

Date: 2026-05-24

## Scope

Make model-backed planner, researcher, implementer, and reviewer workers pass durable, audit-visible role artifacts forward between stages without granting new tools, bypassing approvals, starting a browser, or delivering connector messages.

## Implemented

- `SubagentRecord` persists `artifacts` and `input_artifacts` for worker records.
- Delegation now runs in artifact-aware stages: planner/researcher first, implementer receives their artifact summaries, and reviewer receives planner, researcher, and implementer artifact summaries.
- Provider requests carry prior artifact summaries through `ModelRequest.context_artifacts`.
- Delegation JSON exposes `artifact_count` and compact artifact metadata rows.
- Worker and delegation receipts include artifact ids, input artifact ids, and handoff metadata.
- Root/session metadata records artifact ids while preserving isolated worker sessions and scoped usage rows.
- Human delegation output shows an artifact count and a compact artifact section.

## Safety Boundary

- No browser auto-launch.
- No connector delivery.
- No raw secret persistence.
- Artifacts do not grant tools, bypass approvals, or expand subagent depth/concurrency limits.
- External model calls still run only through configured provider routes, with local fallback metadata recorded.

## Remaining

- Add artifact list/show/search commands.
- Add explicit approval for reusing artifacts across separate delegations.
- Add richer role-specific tool budgets.
- Add higher-depth delegation controls and final synthesis over artifact graphs.
- Add multi-provider fallback ordering and subscription bridge readiness.
