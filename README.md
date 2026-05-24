# AegisAgent

AegisAgent is a terminal-first autonomous agent console with visible governance.
Install it, run `aegis`, and work from the terminal TUI.

It is built toward a secure Hermes-style workflow: prompt-first chat, slash
commands, typed tools, local memory, task queues, subagents, automations, audit
receipts, and explicit approval gates.

AegisAgent does not open a browser during install, setup, update, launch, health
checks, or normal terminal use. The web console is optional and must be started
separately.

This repository and package are `AegisAgent`. Older `Aegis-Agent` references
are historical design inputs, not the install target for this terminal command.

## Install On macOS Or Linux

Prerequisites:

- `git`
- `curl`
- `python3` 3.12 or newer
- `sh`, `bash`, or `zsh`

Install from GitHub:

```bash
python3 --version
git --version
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

Verify that your shell can find the command:

```bash
command -v aegis
aegis activation
```

If `command -v aegis` prints nothing, add the install bin directory to your
shell path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to `~/.zshrc`, `~/.bashrc`, or your shell profile, then open a new
terminal.

## Start The Agent

Run setup checks first:

```bash
aegis setup next
aegis setup model
aegis setup --run-checks
```

Then start the TUI:

```bash
aegis
aegis tui
```

In an interactive terminal, `aegis` opens the terminal UI. `aegis tui` is the
explicit equivalent. In a non-interactive shell, `aegis` prints the terminal
activation card instead of opening a web server.

On first launch, the TUI opens with the setup wizard visible. The prompt stays
active while the wizard is open, so you can type a task, use slash commands, or
move through the wizard cards. Use `/setup hide` when you want future launches
to open directly to the prompt, and `/setup reset` to show the wizard again.

Useful first commands inside the TUI:

```text
/setup next
/setup first-task
/commands
/dashboard
/setup hide
```

Then type normal requests into the prompt:

```text
summarize this workspace
read file README.md
git status
run tests
```

Approval-gated TUI commands use `| approve`:

```text
/git stage README.md | approve
/git commit Update README | approve
/git remote pull origin main | approve
```

## Update From GitHub

Update the installed checkout from GitHub:

```bash
aegis update --approved
```

That command performs a guarded fast-forward pull from `origin/main` inside the
checkout used by the active `aegis` command. It refuses to update if the
checkout has local changes or if the remote does not match the AegisAgent GitHub
repository.

After updating:

```bash
aegis health
aegis audit verify
```

Recovery script, if the `aegis` shim is broken but `~/.aegis-agent` exists:

```bash
~/.aegis-agent/scripts/update.sh
```

## What The Installer Does

The installer:

- clones `https://github.com/MatthewLopez1990/AegisAgent.git` into
  `~/.aegis-agent`
- writes the terminal command shim to `~/.local/bin/aegis`
- prints a PATH line you can add if your shell cannot find `aegis`
- stays terminal-only and does not open a browser
- does not start the web gateway
- does not call model providers
- does not ask for or store raw secret values

Optional installer settings:

```bash
AEGIS_INSTALL_DIR="$HOME/.aegis-agent"
AEGIS_BIN_DIR="$HOME/.local/bin"
AEGIS_COMMAND_NAME="aegis"
AEGIS_BRANCH="main"
AEGIS_REPO_URL="https://github.com/MatthewLopez1990/AegisAgent.git"
```

## Daily Commands

```bash
aegis                         # start the terminal UI
aegis tui                     # explicit terminal UI launch
aegis activate                # launch TUI in a TTY, activation card otherwise
aegis activation              # print terminal activation/readiness card
aegis setup next              # show the next setup action
aegis setup model             # review or configure the model route
aegis setup --run-checks      # run metadata-only readiness checks
aegis health                  # check runtime posture
aegis audit verify            # verify the append-only audit hash chain
aegis dashboard               # show operator status
aegis capabilities --gaps     # show remaining capability gaps
aegis update --approved       # pull latest main from GitHub
```

More commands are listed in [docs/operator-reference.md](docs/operator-reference.md).

## Compatibility Aliases

The canonical command is `aegis`. The Python package also exposes
`aegisagent` for source and package workflows.

Implemented setup aliases are intentionally small and terminal-only:

```bash
aegis setup init              # setup quickstart
aegis setup model-auth        # same setup section as model
aegis setup check             # same readiness receipt as --run-checks
aegis setup checks            # same readiness receipt as --run-checks
aegis setup verify            # same readiness receipt as --run-checks
aegis setup doctor            # same readiness receipt as --run-checks
aegis setup connections       # same setup section as connectors
aegis setup skills            # same setup section as memory
aegis setup plugins           # same setup section as memory
```

Inside the TUI, the matching slash commands work the same way:
`/setup model-auth`, `/setup verify`, `/setup connections`, and
`/setup skills` route to the canonical setup screens.

## Model And Secret Setup

Aegis stores environment variable names for secrets, not raw secret values.

Example:

```bash
export OPENAI_API_KEY="..."
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model doctor
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

Implemented: install/update lifecycle, terminal activation, TUI, setup checks,
health checks, policy/audit receipts, typed workspace tools, governed git
operations, task queues, automations, model-route metadata, connector metadata,
memory review controls, passive skill trust metadata, and local agent/subagent
orchestration.

Partial: web console parity, external model routing, connectors,
self-improvement, richer browser automation, and deeper agent delegation.

Next: stronger model-backed multi-agent execution, live browser control behind
explicit approval, broader integrations, signed skill trust, and packaged
release flows.
