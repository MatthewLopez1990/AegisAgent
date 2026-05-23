# Checkpoint 61 - Model Usage Ledger

## Goal

Move model routing closer to Hermes-style operational visibility by recording each terminal model turn in a provider usage ledger without changing terminal-first activation or opening a browser.

## Changes

- Added `ProviderUsageStore` under the provider config layer.
- Agent turns now record local and OpenAI-compatible provider usage rows after the audited assistant turn.
- Usage rows include provider, mode, status, session, source, prompt/assistant character counts, token accounting, external invocation state, provider route status, receipt id, and safety flags.
- OpenAI-compatible responses use provider-reported `usage` tokens when present; local and unreported responses use a bounded character-based estimate.
- Added `aegisagent model usage --limit <n>`.
- Added `/model usage` and slash-palette support in the terminal TUI.
- Updated README and capability map wording so model routing now reflects terminal-visible usage accounting.

## Safety Notes

- Usage records do not persist raw prompts, assistant text, API keys, or bearer headers.
- Usage records always report `browser_auto_launch=false` and `raw_secret_values_included=false`.
- `model providers` and `model doctor` remain metadata-only.
- Terminal chat remains the explicit invocation path for external providers.

## Verification

Completed gates:

```bash
python3 -m py_compile src/aegisagent/core/provider_config.py src/aegisagent/core/model_provider.py src/aegisagent/core/agent.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py
PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui tests.test_terminal_agent_slice -v # 85 passed
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v                                 # 106 passed, 1 skipped
CLI smoke: local chat writes `usage_id` and `model usage` shows local/terminal-v0
CLI smoke: loopback OpenAI-compatible route records provider-reported usage tokens
TUI smoke: `/model usage` prints the usage ledger without browser launch
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
PYTHONPATH=src python3 -m aegisagent tui --print --width 200 --height 60
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```
