# Checkpoint 110: Simpler Install And Model Onboarding

## Scope

Make the README, installer next steps, setup wizard, TUI setup copy, operator
reference, and model-provider command path agree on a shorter terminal-first
onboarding flow:

1. Install or repair the `aegis` command.
2. Update from GitHub when needed.
3. Choose either local no-account mode or OpenAI with `OPENAI_API_KEY`.
4. Run readiness checks.
5. Start `aegis`.

## Safety Boundary

- Install and update remain explicit terminal commands.
- Updates still require approval and guarded fast-forward pulls from the
  expected GitHub repository.
- Model provider setup stores environment-variable handles only, never raw key
  values.
- Custom OpenAI-compatible providers require an explicit `--base-url` so
  non-OpenAI providers do not silently use the OpenAI API URL.
- TUI `/model connect` supports the same provider, model, env-handle, and
  base-URL options as the CLI while preserving browser-off setup.

## Verification

Focused verification completed:

- README install/start/update/model expectations.
- Local install smoke with command lookup, health, audit, update, and model
  connection commands.
- Installer script safety checks.
- Setup quickstart and setup-next output.
- Model provider config, custom provider base-URL requirement, and no raw key
  persistence.
- TUI command view and `/model connect` dispatch.

Full checkpoint verification completed:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed: 215 tests,
  2 skipped for missing optional FastAPI test client.
- `npm run verify` in `web` passed: Vite build plus smoke check.
- `PYTHONPATH=src python3 -m aegisagent capabilities --gaps` passed and now
  advertises the simpler local/OpenAI/model-doctor route.
- `PYTHONPATH=src python3 -m aegisagent audit verify` passed with a valid audit
  chain.
- `git diff --check` passed.
