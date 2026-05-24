# Checkpoint 100 - Model-Backed Subagent Workers

Date: 2026-05-24

## Scope

Move planner, researcher, implementer, and reviewer workers from static role summaries to active-provider model turns while preserving bounded concurrency, isolated sessions, audit receipts, terminal monitors, and local fallback.

## Implemented

- Worker execution now calls the active model provider route directly from the subagent orchestration layer.
- Local provider worker prompts return role-specific contributions for planner, researcher, implementer, and reviewer contracts.
- Worker records persist provider, mode, route status, fallback state, primary provider, and scoped usage ids.
- Delegation receipts include worker providers, provider modes, route statuses, usage ids, fallback count, and model invocation flags.
- Parent agent turns surface worker provider metadata on the `subagents.delegate` tool result without changing the parent turn provider or usage id.
- `/model usage` keeps top-level turn accounting separate from scoped subagent worker usage.

## Safety Boundary

- No browser auto-launch.
- No connector delivery.
- No raw secret persistence.
- External model calls only run through configured provider routes.
- Failed attempted external routes fall back to the local provider with fallback metadata.
- Audit receipts and usage ledger rows record provider/fallback state.

## Verification

- Focused subagent/model tests cover local worker provider metadata.
- CLI delegation tests cover OpenAI-compatible loopback worker routing.
- Prompt-turn tests cover delegated worker metadata on the parent tool result.
- Full Python, web, audit, capability, and terminal smoke checks are expected before commit.

## Docs Updated

- README install, first-run, use, update, models, agents, and safety sections.
- Capability map wording for agents/subagents and model provider routing.

## Remaining

- Add worker-to-worker artifacts and richer role-specific tool budgets.
- Add deeper nested delegation controls beyond the current bounded profile set.
- Add multi-provider fallback ordering and subscription bridge readiness.
