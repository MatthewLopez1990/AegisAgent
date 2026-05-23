# Checkpoint 63 - Typed Test Tool

## Goal

Move terminal execution closer to Hermes-style typed tools by adding a governed verification/test tool that can be called from prompts, CLI, and TUI slash commands without shell parsing or browser launch.

## Changes

- Added `workspace.run_tests` to `WorkspaceToolRunner`.
- Default test command uses `python3 -m unittest discover -s tests -v` when a `tests/` directory exists.
- Explicit commands are allowlisted to Python `unittest` and `py_compile` forms.
- Test execution uses subprocess argv lists, not shell strings.
- Test execution sets `PYTHONDONTWRITEBYTECODE=1` to avoid routine bytecode churn.
- Added prompt-triggered typed test execution for requests such as `run tests`.
- Added `aegisagent verify [allowlisted command]`.
- Added `/test [allowlisted command]` and `/verify [allowlisted command]`.
- Updated README and capability map to include typed verification.

## Safety Notes

- Non-allowlisted commands are blocked before execution.
- Output is redacted and bounded before transcript/audit persistence.
- Tool metadata includes `external_action_started=false` and `browser_auto_launch=false`.
- This does not replace the governed shell path; it adds a safer typed path for normal verification.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/workspace_tools.py src/aegisagent/core/model_provider.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/capabilities.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 90 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 111 passed, 1 skipped
CLI smoke: `aegisagent verify python3 -m unittest tests.test_cli.CliTests.test_chat_runs_one_local_agent_turn -v`
TUI smoke: `/test python3 -m unittest tests.test_tui.TuiRendererTests.test_minimum_size_message -v`
Agent smoke: `aegisagent chat "run tests: python3 -m unittest tests.test_terminal_agent_slice.TerminalAgentSessionTests.test_agent_runtime_surfaces_typed_test_runs -v" --json`
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
