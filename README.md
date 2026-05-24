# AegisAgent

AegisAgent is a terminal-first agent console. Install it, run `aegis`, and work
from the terminal UI.

It is being built toward a secure Hermes-style workflow: prompt-first chat,
slash commands, typed local tools, memory, task queues, subagents, automations,
audit receipts, and explicit approval gates.

AegisAgent does not open a browser during install, setup, update, launch, health
checks, or normal terminal use. Setup does not launch a browser. The web console
is optional and must be started separately.

This project is `AegisAgent`. Older `Aegis-Agent` references are historical
design inputs, not the install target.

## Quick Start

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
export PATH="$HOME/.local/bin:$PATH"
aegis activation
aegis setup next
aegis setup --run-checks
aegis
```

`aegis` starts the terminal UI when your shell is interactive. Use `aegis tui`
when you want the explicit command.

## Install On macOS Or Linux

You need `git`, `curl`, and `python3` 3.12 or newer.

```bash
python3 --version
git --version
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

The installer clones GitHub into `~/.aegis-agent` and writes the command shim to
`~/.local/bin/aegis`.

Verify the install:

```bash
command -v aegis
aegis activation
```

If `command -v aegis` prints nothing, add this to `~/.zshrc`, `~/.bashrc`, or
your shell profile, then open a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Optional installer settings:

```bash
AEGIS_INSTALL_DIR="$HOME/.aegis-agent"
AEGIS_BIN_DIR="$HOME/.local/bin"
AEGIS_COMMAND_NAME="aegis"
AEGIS_BRANCH="main"
AEGIS_REPO_URL="https://github.com/MatthewLopez1990/AegisAgent.git"
```

## Start The Agent

Run the setup checks first:

```bash
aegis setup next
aegis setup model
aegis setup --run-checks
```

Start the UI:

```bash
aegis
aegis tui
```

Inside the UI, type normal requests:

```text
summarize this workspace
read file README.md
git status
run tests
```

Use slash commands for direct actions:

```text
/setup next
/setup first-task
/commands
/dashboard
/tasks submit draft a safe plan
/memory search terminal-first
/model auth status
```

Commands that mutate files, git state, browser session records, or external
state require explicit approval. In the TUI, approval uses `| approve`:

```text
/git stage README.md | approve
/git commit Update README | approve
/git remote pull origin main | approve
```

On first launch, the setup wizard is visible but the prompt remains active. Use
`/setup hide` to open future launches directly to the prompt, and `/setup reset`
to show the wizard again.

## Update From GitHub

Use this command to update the installed agent from GitHub onto the machine
running it:

```bash
aegis update --approved
```

It runs a guarded fast-forward pull from `origin/main` inside the installed
checkout. It refuses to update if local changes are present or if the remote is
not the AegisAgent GitHub repository.

If the `aegis` shim is broken but `~/.aegis-agent` still exists:

```bash
~/.aegis-agent/scripts/update.sh
```

After updating:

```bash
aegis health
aegis audit verify
```

## Common Terminal Commands

```bash
aegis                         # start the terminal UI
aegis tui                     # explicit terminal UI launch
aegis init                    # setup quickstart alias
aegis activation              # print terminal readiness card
aegis commands                # show slash-command lanes
aegis setup next              # show the next setup action
aegis setup model             # review model route setup
aegis setup --run-checks      # run metadata-only readiness checks
aegis model auth status       # show read-only model auth posture
aegis models doctor           # alias for model doctor checks
aegis task submit "do work"   # singular alias for task queue submit
aegis tasks --events <id>     # canonical task timeline
aegis memory search <query>   # search local memory
aegis memory index            # index curated memory files
aegis audit verify            # verify append-only audit hash chain
aegis update --approved       # pull latest main from GitHub
```

More commands are listed in [docs/operator-reference.md](docs/operator-reference.md).

## Compatibility Aliases

The canonical command is `aegis`. The Python package also exposes `aegisagent`
for source and package workflows.

These aliases are migration aids for older agent command habits. They normalize
to current AegisAgent terminal commands before dispatch. They do not mean the old
agent surface or Hermes command set is fully implemented.

Canonical commands remain the commands to teach, document, and automate. Use the
aliases only when an older idiom maps directly to existing terminal-only Aegis
behavior.

```bash
aegis task list
aegis task submit "draft a safe plan"
aegis task status <task-id>
aegis task timeline <task-id>
aegis task output <task-id>
aegis task logs <task-id>
aegis task recover
aegis models providers
aegis models doctor
aegis model auth status
aegis model auth methods
aegis model auth doctor
aegis memory search <query>
aegis memory index
aegis setup model-auth
aegis setup check
aegis setup verify
aegis setup connections
aegis setup skills
```

Unsupported old commands such as `model auth login`, `model auth logout`,
`task pause`, `task resume`, and old external-memory management commands are not
implemented.

Inside the TUI, root shortcuts are intentionally small:

```text
/task                       exact root alias for /tasks
/model                      exact root alias for /model providers
/memory                     canonical memory index/search root
```

Root shortcuts do not create singular slash subcommand families; use
`/tasks watch`, `/model doctor`, and `/memory add` for those workflows.

## Model And Secret Setup

Aegis stores environment variable names for secrets, not raw secret values.

```bash
export OPENAI_API_KEY="..."
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model doctor
aegis model auth status
```

Connector metadata follows the same pattern:

```bash
export SLACK_BOT_TOKEN="..."
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
```

## Optional Web Console

The web console is not part of normal install, setup, update, health checks, or
agent use.

Preview web instructions:

```bash
aegis web
```

Start the optional local gateway only when you explicitly want it:

```bash
python3 -m pip install -e '.[gateway]'
aegis web --serve --approved --host 127.0.0.1 --port 8787
```

In another terminal, run the web frontend from the installed checkout:

```bash
cd ~/.aegis-agent/web
npm install
npm run dev -- --port 5173
```

`aegis web --serve --approved` starts the local gateway after approval and still
does not launch a browser.

## Develop From Source

Use this path if you are editing AegisAgent instead of installing the user
command:

```bash
git clone https://github.com/MatthewLopez1990/AegisAgent.git
cd AegisAgent
PYTHONPATH=src python3 -m aegisagent
```

Source checkout equivalents:

```bash
PYTHONPATH=src python3 -m aegisagent activation
PYTHONPATH=src python3 -m aegisagent setup next
PYTHONPATH=src python3 -m aegisagent setup --run-checks
PYTHONPATH=src python3 -m aegisagent tui
```

Verify a source checkout:

```bash
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
PYTHONPATH=src python3 -m aegisagent tui --print --width 100 --height 32
cd web && npm run verify
```

Update a source checkout with normal git:

```bash
git pull --ff-only origin main
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
```

## Current Status

AegisAgent is still an early terminal-first foundation, not a complete
Hermes-class agent.

Implemented: install/update lifecycle, terminal activation, TUI, terminal
command catalog, setup checks, health checks, policy/audit receipts, typed
workspace tools, governed git operations, task queues, automations, model-route
metadata, connector metadata, memory review controls, passive skill trust
metadata, and local agent/subagent orchestration.

Partial: web console parity, external model routing, connectors,
self-improvement, richer browser automation, and deeper agent delegation.

Next: stronger model-backed multi-agent execution, live browser control behind
explicit approval, broader integrations, signed skill trust, and packaged
release flows.
