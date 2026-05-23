# Checkpoint 39 - Hermes-Style Agents Surface

## Goal

Make the multi-agent runtime visible as an `agents` product surface, not only as the lower-level `subagents` implementation command.

## Changes

- Added agent profile metadata:
  - planner
  - researcher
  - implementer
  - reviewer
- Added CLI commands:
  - `aegisagent agents`
  - `aegisagent agents profiles`
  - `aegisagent agents delegate <task>`
  - `aegisagent agents stream <task>`
  - `aegisagent agents bg <task>`
  - `aegisagent agents jobs`
  - `aegisagent agents monitor <job-id>`
  - `aegisagent agents cancel <job-id>`
  - `aegisagent agents recover`
- Added TUI slash commands:
  - `/agents`
  - `/agents profiles`
  - `/agents delegate <task>`
  - `/agents live <task>`
  - `/agents bg <task>`
  - `/agents jobs`
  - `/agents monitor <job-id>`
  - `/agents unwatch`
  - `/agents recover`
- The new surface reuses the existing governed local subagent runtime:
  - isolated sessions
  - per-worker audit receipts
  - bounded concurrency/depth/children
  - background job cancellation and stale recovery
  - terminal-first status with `browser_auto_launch=false`

## Prior Aegis-Agent Blend

The previous `MatthewLopez1990/Aegis-Agent` exposed higher-level `agents` commands in the terminal. This checkpoint ports that product vocabulary into this repo while preserving the current local-only security model.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v
PYTHONPATH=src python3 -m aegisagent agents
PYTHONPATH=src python3 -m aegisagent agents profiles
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
