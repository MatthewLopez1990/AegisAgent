# Checkpoint 21 - Hermes-Style Terminal Affordances

Status: older Aegis terminal ergonomics blended into the current terminal-first implementation

Reference inspected:

- `MatthewLopez1990/Aegis-Agent` at `f3b4396`.
- Useful terminal patterns: short `aegis tui` activation, prompt-first shell, grouped command lanes, `/commands`, `/model providers`, `/new`, `/reset`, `/clear`, `/add-dir`, and explicit web launch instead of browser auto-start.

Implemented in this checkpoint:

- Package installs both `aegisagent` and `aegis` console scripts.
- Default curses view now opens with a compact prompt-first status strip instead of filling the first screen with dashboard cards.
- TUI slash additions:
  - `/commands [prefix]`
  - `/menu [prefix]`
  - `/clear`
  - `/new [title]`
  - `/reset [title]`
  - `/submit <request>`
  - `/add-dir <path>`
  - `/model providers`
- `/commands` renders grouped Operate/Govern/Setup/Build/Explore lanes inspired by the previous Aegis terminal deck.
- `/model providers` reports the active local provider route and confirms no browser is required.
- `/add-dir` records workspace-scoped context directories with audit receipts and rejects paths outside the workspace.
- `/setup` now prints both terminal activation commands: `aegisagent tui` and installed alias `aegis tui`.

Verified locally:

```bash
PYTHONPATH=src python3 -m unittest tests.test_tui tests.test_cli -v
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
rm -rf /tmp/aegisagent-venv && python3 -m venv /tmp/aegisagent-venv
/tmp/aegisagent-venv/bin/python -m pip install -e .
/tmp/aegisagent-venv/bin/aegis tui --help
/tmp/aegisagent-venv/bin/aegis tui
PYTHONPATH=src python3 -m aegisagent audit verify
git diff --check
```

Still incomplete:

- Full task queue controls such as `/tasks`, `/resume`, `/pause`, and `/cancel` beyond the existing subagent background job controls.
- Rich model-provider setup/auth routing.
- `@` path completion and multiline prompt editing.
- Global editable install on the Homebrew-managed system Python without a venv; PEP 668 blocks that unless the operator chooses a user/venv/pipx install path.
