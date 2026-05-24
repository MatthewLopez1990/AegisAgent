# AegisAgent

AegisAgent is a terminal-first autonomous agent console with visible governance. The normal user command is:

```bash
aegis
```

It is built for a secure Hermes-style workflow: prompt-first TUI, slash commands, typed tools, local memory, task queues, subagents, automations, audit receipts, and explicit approval gates.

AegisAgent does not open a browser during install, setup, update, launch, health checks, or normal terminal use. The web console is optional and must be started separately.

## Operating Model

- Aegis is terminal-first. Install, setup, health checks, updates, and normal agent work are driven by the `aegis` terminal command.
- The web console is optional. It is not started by install, setup, update, health checks, or normal TUI use.
- Read-only inspection can run without approval.
- Workspace writes, shell mutations, network fetches, browser records, external sends, git stage/commit/branch, git remote fetch/pull/push, and `aegis update` require explicit approval.
- TUI approval uses `| approve`. CLI approval uses `--approved`.
- Secrets are configured as environment-variable handles only. Aegis stores names such as `OPENAI_API_KEY` or `SLACK_BOT_TOKEN`, not raw secret values.

## Quick Start

Install on macOS or Linux:

```bash
python3 --version
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
command -v aegis
```

Start the agent:

```bash
aegis
```

If your shell cannot find `aegis`, add the install bin directory to your path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to `~/.zshrc`, `~/.bashrc`, or your shell profile, then open a new terminal.

## First Session

Inside the TUI, start with:

```text
/setup next
/setup model
/setup run-checks
/dashboard
```

Then type normal work into the prompt:

```text
summarize this workspace
read file README.md
git status
run tests
```

If you prefer setup outside the TUI:

```bash
aegis setup next
aegis setup model
aegis setup --run-checks
aegis
```

`aegis setup next` tells you the next concrete setup action. On a fresh install that is usually the model route. Run checks after you review or configure the concrete setup step.

## Install Details

The installer:

- clones this repo into `~/.aegis-agent`
- installs the terminal command at `~/.local/bin/aegis`
- performs the expected GitHub clone and local shim write because you explicitly ran the installer in Terminal
- keeps install terminal-only; it does not open a browser
- does not start the web gateway, call model providers, send connector messages, or prompt for raw secrets
- prints the PATH export for `~/.local/bin`

Prerequisites:

- `git`
- `python3` 3.12 or newer
- `curl`
- a POSIX shell such as `sh`, `bash`, or `zsh`

Optional installer environment variables:

```bash
AEGIS_INSTALL_DIR="$HOME/.aegis-agent"
AEGIS_BIN_DIR="$HOME/.local/bin"
AEGIS_COMMAND_NAME="aegis"
AEGIS_BRANCH="main"
AEGIS_REPO_URL="https://github.com/MatthewLopez1990/AegisAgent.git"
```

## Verify Install

After first setup, verify the installed command:

```bash
aegis activation
aegis health
aegis audit verify
aegis tui --print --width 100 --height 32
```

## Update From GitHub

Update the installed checkout from GitHub:

```bash
aegis update --approved
```

That command performs a guarded fast-forward pull from `origin/main` inside the checkout used by the active `aegis` command. It refuses to update if the checkout has local changes or if the remote does not match `MatthewLopez1990/AegisAgent`.

After updating:

```bash
aegis health
aegis audit verify
```

The direct script is for recovery or debugging only after an installer-created checkout exists. Treat it as manual operator approval because it performs a remote git fetch/pull and refreshes the local shim:

```bash
~/.aegis-agent/scripts/update.sh
```

To refresh the local command shim from a source checkout:

```bash
PYTHONPATH=src python3 -m aegisagent install shim --approved --bin-dir "$HOME/.local/bin" --name aegis
```

## Essential Commands

| Command | Purpose |
| --- | --- |
| `aegis` | Start the normal terminal agent. |
| `aegis setup next` | Show the next setup action. |
| `aegis setup model` | Review or configure the model route. |
| `aegis setup --run-checks` | Run metadata-only readiness checks. |
| `aegis health` | Check runtime, audit, sandbox, tools, memory, provider, and connector posture. |
| `aegis dashboard` | Show operator status. |
| `aegis capabilities --gaps` | Show remaining product gaps. |
| `aegis activation` | Show terminal startup and browser-off safety details. |
| `aegis update --approved` | Pull the latest GitHub `main` into the installed checkout. |
| `aegis completion zsh` | Print shell completion. Also supports `bash` and `fish`. |

More examples live in [docs/operator-reference.md](docs/operator-reference.md).

## Shell Completion

Choose one shell and print completion:

```bash
aegis completion zsh
aegis completion bash
aegis completion fish
```

Install completion for one shell:

```bash
aegis completion zsh >> ~/.zshrc
aegis completion bash >> ~/.bashrc
mkdir -p ~/.config/fish/completions
aegis completion fish > ~/.config/fish/completions/aegis.fish
```

## Useful TUI Slash Commands

```text
/commands
/setup next
/setup model
/setup run-checks
/dashboard
/capabilities
/gaps
/tools
/git status
/git diff [path]
/test
/verify
/web
/exit
```

Approval-gated TUI commands use `| approve`. CLI commands use `--approved`.

Examples:

```text
/git stage README.md | approve
/git commit Update README | approve
/git remote pull origin main | approve
```

## Security Model

AegisAgent fails closed for destructive commands and secret echo.

- Read-only local inspection, such as `/read`, `aegis git status`, and `aegis git diff`, can run without approval.
- Explicit approval is required for workspace writes, shell mutations, network fetches, browser session or screenshot records, external delivery, connector sends, elevated actions, unrecognized tools, git stage/commit/branch, git remote fetch/pull/push, and `aegis update`.
- TUI approval uses `| approve`. CLI approval uses `--approved`.
- Setup and config commands may write Aegis metadata, but secrets are stored as environment-variable handles only.
- Raw secret values must not be written to Aegis config, connector metadata, examples, prompts, task text, or audit notes.
- Audit payloads are redacted before persistence, and `aegis audit verify` checks the chained receipt hash.

Configure secret handles like this:

```bash
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
```

## Optional Web Console

The web console is not required for install, setup, update, health checks, or normal agent work.

Preview the web instructions:

```bash
aegis web
```

Start the local gateway only when you explicitly want it:

```bash
python3 -m pip install -e '.[gateway]'
aegis web --serve --approved --host 127.0.0.1 --port 8787
```

In another terminal, run the web frontend:

```bash
cd ~/.aegis-agent
cd web
npm install
npm run dev -- --port 5173
```

`aegis web` is preview-only. `aegis web --serve --approved` starts the local gateway after explicit approval and still does not launch a browser.

## Source Checkout For Development

Use this path if you are developing AegisAgent instead of installing the user command:

```bash
git clone https://github.com/MatthewLopez1990/AegisAgent.git
cd AegisAgent
PYTHONPATH=src python3 -m aegisagent
```

Source-checkout commands:

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

AegisAgent is still an early terminal-first foundation, not a complete Hermes-class agent.

- Implemented: install/update lifecycle, terminal activation, TUI, setup checks, health checks, policy/audit receipts, typed workspace tools, governed git operations, task queues, automations, model-route metadata, connector metadata, and local agent/subagent orchestration.
- Partial: web console parity, external model routing, connectors, self-improvement, and agent delegation depth.
- Next: deeper live browser control, richer model-backed multi-agent execution, broader integrations, and stronger packaged release flows.
