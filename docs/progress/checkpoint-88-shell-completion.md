# Checkpoint 88 - Shell completion and installed command copy

## What changed

- Added `aegis completion bash|zsh|fish` so installed users can print dependency-free shell completion scripts without starting runtime state.
- Defaulted visible terminal help and activation copy to the installed `aegis` command while preserving `PYTHONPATH=src python3 -m aegisagent` for source checkouts.
- Centralized installed command-name detection through `AEGIS_COMMAND_NAME`, so custom shims such as `aegis-test` render matching help, activation, setup, capability, automation, improvement, model, connector, and agent guidance.
- Added shell-completion discoverability to install status and TUI help without making it a first-run activation step.

## Safety boundary

- Completion runs before runtime initialization, audit setup, gateway setup, TUI launch, subprocess workers, or workspace state creation.
- Completion rejects unsafe command names and accepts only letters, numbers, dot, underscore, and dash.
- Optional web and gateway surfaces remain preview/approval gated and are not started by completion, activation, install status, or help output.

## Verification

- `python3 -m py_compile src/aegisagent/core/completion.py src/aegisagent/cli.py src/aegisagent/core/automation.py src/aegisagent/core/improvement.py src/aegisagent/core/model_provider.py src/aegisagent/core/provider_config.py src/aegisagent/core/connectors.py src/aegisagent/core/subagents.py src/aegisagent/core/capabilities.py`
- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_completion_command_emits_shell_scripts_without_runtime_side_effects tests.test_cli.CliTests.test_install_status_and_shim_are_terminal_only tests.test_cli.CliTests.test_default_aegis_shim_runs_help_and_completion tests.test_cli.CliTests.test_installed_shim_name_drives_activation_card tests.test_cli.CliTests.test_tui_help_explains_terminal_activation_and_print_fallback tests.test_tui.TuiRendererTests.test_interactive_dispatch_dashboard_surface -v`
- `PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v`
- `cd web && npm run verify`
- `sh -n scripts/install.sh && sh -n scripts/update.sh && git diff --check`
- Static completion scan for gateway/browser/network/secret launch patterns.
