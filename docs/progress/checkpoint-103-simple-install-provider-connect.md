# Checkpoint 103 - Simple Install And Provider Connect

Date: 2026-05-24

## Scope

Make the installed-user path easier to follow from the README and terminal by keeping the one-line macOS/Linux installer, adding a beginner-friendly model provider connection command, and preserving the existing no-browser, no-raw-secret setup boundary.

## Implemented

- Added `aegis model connect openai` as the simple OpenAI provider path.
- Added `aegis model connect local` as the simple local-provider reset.
- Kept `aegis model configure ...` as the advanced/backward-compatible provider command.
- Added `/model connect openai` and `/model connect local` to the TUI command palette and setup command lanes.
- Hardened provider configuration so `--api-key-env` must be an environment variable handle, not a raw secret-looking value.
- Rejected credential-bearing provider base URLs at configuration time.
- Updated setup model guidance to teach `model connect` while preserving `/setup model` as the first-run setup step.
- Updated install/update scripts to honor `AEGIS_PYTHON` and print clearer post-install next commands.
- Updated README and operator reference docs around install, provider connection, update, and model-backed agents.

## Safety Boundary

- Provider connect writes metadata only.
- Raw API key values are not stored in config or audit receipts.
- No browser login, browser launch, model call, gateway start, connector delivery, or external action is performed by provider connect.
- Runtime fallback behavior remains unchanged: unready external routes use local, and failed external calls fall back locally.

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_model_provider_config_is_metadata_only tests.test_cli.CliTests.test_readme_leads_with_installed_user_terminal_flow tests.test_cli.CliTests.test_readme_installed_user_commands_smoke_without_browser_launch tests.test_tui.TuiRendererTests.test_slash_palette_and_normalization tests.test_tui.TuiRendererTests.test_interactive_dispatch_model_providers_is_terminal_only -v`
- `PYTHONPATH=src python3 -m aegisagent model connect openai`
- `PYTHONPATH=src python3 -m aegisagent --json model connect local`
- `PYTHONPATH=src python3 -m aegisagent model auth login`

## Remaining

- Add a real subscription bridge once the local bridge contract is defined.
- Add richer provider selection and fallback ordering beyond the single active route.
- Add optional interactive prompts for provider selection in the live TUI.
