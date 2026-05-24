# Checkpoint 108: Opt-In Depth-2 Delegation

## Scope

- Added an explicit `requested_depth` control to local subagent delegations.
- Kept the default topology flat: coordinator -> planner, researcher, implementer, reviewer.
- Added opt-in depth 2: coordinator -> planner, researcher, implementer; implementer -> reviewer.
- Carried depth through foreground, live/stream, and background jobs across `subagents`, `agents`, and TUI pipe syntax.
- Tightened capability, README, operator reference, and PLAN wording so depth 2 is described as a bounded topology, not recursive autonomous spawning or a global worker pool.

## Operator Commands

```bash
aegis agents delegate "review the current plan" --depth 2
aegis agents live "review the current plan" --depth 2
aegis agents bg "review the current plan" --depth 2
aegis subagents --delegate "review the current plan" --depth 2
aegis subagents --stream "review the current plan" --depth 2
aegis subagents --background "review the current plan" --depth 2
```

```text
/agents delegate review the current plan | depth 2
/agents live review the current plan | depth 2
/agents bg review the current plan | depth 2
/subagents review the current plan | depth 2
/subagents live review the current plan | depth 2
/subagents bg review the current plan | depth 2
```

## Verification

- `PYTHONPATH=src python3 -m py_compile src/aegisagent/core/subagents.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py`
- Focused depth/CLI/TUI suite: 11 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 213 tests passed, 2 skipped.
- `cd web && npm run verify`: build and smoke passed.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps`: rendered terminal capability gaps with opt-in depth-2 wording.
- `PYTHONPATH=src python3 -m aegisagent audit verify`: audit chain ok.
