# AegisAgent

AegisAgent is a terminal-first autonomous agent scaffold with visible governance. It keeps Hermes-style agent concepts, but the default surface is a local terminal UI where approvals, tool policy, sandbox posture, model routing, memory writes, and audit receipts are explicit.

It does not open a browser during install, launch, update, setup, or normal terminal use. The web console is optional and must be started separately.

## Install On macOS Or Linux

Prerequisites:

- `git`
- `python3` 3.12 or newer
- a POSIX shell (`sh`, `bash`, or `zsh`)

Run this from a terminal:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

The installer:

- clones AegisAgent from GitHub into `~/.aegis-agent`
- writes the terminal command shim to `~/.local/bin/aegis`
- prints the exact command to add `~/.local/bin` to your `PATH` if needed
- never launches a browser or starts the web gateway

If `aegis` is not found after install, add the shim directory to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then open a new terminal or run that export in the current terminal.

## Run The Agent

After installing, start AegisAgent with:

```bash
aegis
```

Useful first commands:

```bash
aegis activation
aegis health
aegis setup --run-checks
aegis dashboard
aegis tui
```

Inside the TUI, start with:

```text
/setup run-checks
/dashboard
/capabilities
/tasks
/agents
/activation
```

Prompt input also works directly in the terminal UI. For example:

```text
summarize this workspace
read file README.md
git status
run tests
```

## Update From GitHub

From an installed copy, update the agent from GitHub with:

```bash
aegis update --approved
```

That command runs a guarded `git pull --ff-only origin main` inside `~/.aegis-agent`. It refuses to update if the checkout is dirty or if `origin` does not point to the expected AegisAgent GitHub repository. Equivalent HTTPS and SSH GitHub origins for this repo are accepted.

You can also run the update script directly:

```bash
~/.aegis-agent/scripts/update.sh
```

For a source checkout, use normal git:

```bash
git pull --ff-only origin main
PYTHONPATH=src python3 -m aegisagent health
```

## Source Checkout Usage

If you are working from this repository instead of the installed shim:

```bash
git clone https://github.com/MatthewLopez1990/AegisAgent.git
cd AegisAgent
PYTHONPATH=src python3 -m aegisagent
```

Optional editable install:

```bash
python3 -m pip install -e .
aegis
aegisagent
```

The source-checkout module command is useful when you do not want to install a shim:

```bash
PYTHONPATH=src python3 -m aegisagent activation
PYTHONPATH=src python3 -m aegisagent tui
PYTHONPATH=src python3 -m aegisagent update --approved
```

## What The Main Commands Do

| Command | Purpose |
| --- | --- |
| `aegis` | Start the terminal UI in a real TTY, or print the activation card outside one. |
| `aegis activation` | Show the exact terminal startup commands and browser-off safety flags. |
| `aegis health` | Check runtime state, audit chain, sandbox availability, tools, and memory files. |
| `aegis setup --run-checks` | Run metadata-only setup readiness checks. |
| `aegis dashboard` | Show the terminal operator dashboard. |
| `aegis capabilities` | Show implemented and partial capability areas. |
| `aegis capabilities --gaps` | Show remaining gaps only. |
| `aegis update --approved` | Pull the latest GitHub `main` into the installed checkout. |
| `aegis tui --print` | Print a static TUI frame for docs, CI, or non-interactive terminals. |

## Common TUI Commands

The TUI uses slash commands for explicit operations:

```text
/commands
/setup
/setup run-checks
/setup model
/setup sandbox
/setup tools
/setup connectors
/dashboard
/capabilities
/gaps
/tools
/audit
/memory
/skills
/sessions search <query>
/tasks submit <request>
/tasks bg <request>
/tasks watch <task-id>
/automations
/improve
/agents
/agents delegate <task>
/subagents bg <task>
/read <path>
/git status
/git diff [path]
/git stage <path> | approve
/git commit <message> | approve
/git remote pull origin main | approve
/test
/verify
/web
/exit
```

Approval-gated commands require `| approve` in the TUI or `--approved` in the CLI. This is intentional: network access, writes, git mutations, external delivery, and browser control should be visible operator choices.

## Web Console Is Optional

Normal install and use are terminal-only. Start the optional web pieces only when you explicitly want the browser console:

```bash
python3 -m pip install -e '.[gateway]'
aegisagent gateway --host 127.0.0.1 --port 8787
```

In another terminal:

```bash
cd web
npm install
npm run dev -- --port 5173
```

The web UI reads gateway metadata when the gateway is running. It is not required for setup, launch, update, health checks, or normal agent work.

## Command Reference

Install and lifecycle:

```bash
aegis activation
aegis install
aegis install shim --approved
aegis update
aegis update --approved
scripts/install.sh
scripts/update.sh
```

Runtime checks:

```bash
aegis health
aegis setup --run-checks
aegis dashboard
aegis capabilities
aegis capabilities --gaps
aegis audit verify
aegis verify
```

Model and connector metadata:

```bash
aegis model providers
aegis model configure <name> --mode api_key --api-key-env <ENV_NAME> --base-url <URL>
aegis model doctor
aegis model usage
aegis connectors
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
```

Agent work:

```bash
aegis chat "summarize this workspace"
aegis sessions --query "audit receipt"
aegis tasks --submit "draft a safe plan"
aegis tasks --background "draft a safe plan"
aegis agents
aegis agents profiles
aegis agents contracts
aegis agents delegate "review the current plan"
aegis subagents --delegate "review the current plan"
```

Governed workspace tools:

```bash
aegis fetch https://example.com --approved
aegis browser open https://example.com --approved
aegis git stage <path> --approved
aegis git commit --message "Describe staged changes" --approved
aegis git branch create codex/example --approved
aegis git remote fetch origin main --approved
aegis git remote pull origin main --approved
aegis git remote push origin main --approved
aegis edit replace README.md --old "old text" --new "new text" --approved
```

Automations and self-improvement:

```bash
aegis automations
aegis automations create daily-check --schedule "daily 09:00" --prompt "summarize workspace risks"
aegis automations due
aegis automations missed
aegis automations replay-missed
aegis automations worker --max-ticks 5
aegis improve
aegis improve propose "policy denied a needed safe git read" --target policy --operation evaluate
aegis improve candidate <proposal-id>
aegis improve verify <candidate-id>
aegis improve apply <candidate-id>
```

## Verification For Contributors

Run the backend test suite:

```bash
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
```

Run terminal health checks:

```bash
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
PYTHONPATH=src python3 -m aegisagent tui --print --width 100 --height 32
```

Run web checks:

```bash
cd web
npm run verify
```

## Security Contract

AegisAgent fails closed for destructive commands and secret echo. Network calls, shell writes, external delivery, elevated actions, browser actions, and unrecognized tool calls require explicit approval. Audit payloads are redacted before persistence, and `aegis audit verify` checks the chained receipt hash.

## Current Status

This is still an early terminal-first foundation, not a complete Hermes-class agent. The implemented surface includes install/update lifecycle, terminal activation, TUI, setup checks, health checks, policy/audit receipts, typed workspace tools, governed git operations, task queues, automations, model-route metadata, connectors metadata, and local agent/subagent orchestration. The remaining work is deeper live browser control, richer model-backed multi-agent execution, broader integrations, and stronger packaged release flows.
