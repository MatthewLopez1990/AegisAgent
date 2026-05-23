# Checkpoint 81 - Web Gateway Hydration

## Scope
- Hydrated the Web GUI from gateway parity routes instead of static-only console fixtures.
- Added offline and partial-hydration fallbacks so the web shell stays usable when `127.0.0.1:8787` is unavailable or incomplete.
- Wired dashboard, tools, connectors, capabilities, tasks, automations, improvements, agent status/contracts, subagents/jobs, browser sessions, model usage, audit, and sessions into the Web panels.
- Preserved the terminal-first boundary: the Web GUI exposes no mutation controls, browser launches, remote git operations, or task execution paths.

## Verification
- Expanded Web smoke coverage for gateway-live/offline-fallback labels, route labels, approval-boundary copy, and no web mutation controls.
- Added Web `test` and `verify` scripts so local checks have a single terminal command.
- Pinned `/tools` gateway contract shape for Web hydration when optional FastAPI test dependencies are installed.
- Added `httpx` to the dev extra so FastAPI `TestClient` route contracts run in gateway-enabled dev environments.
- Ran frontend build/smoke, browser smoke against a live gateway, the ordinary backend unit suite, and a gateway-enabled backend suite.
