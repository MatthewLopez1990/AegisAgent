# AegisAgent

AegisAgent is a terminal-first autonomous agent console with visible governance. It is designed to feel like a secure Hermes-style agent: prompt-first TUI, slash commands, local memory, typed tools, subagents, task queues, automations, provider metadata, connector metadata, audit receipts, and explicit approvals.

The normal product is the terminal command:

```bash
aegis
```

AegisAgent does not open a browser during install, setup, update, launch, health checks, or normal terminal use. The web console is optional and must be started separately.

## Install On macOS Or Linux

Prerequisites:

- `git`
- `python3` 3.12 or newer
- `curl`
- a POSIX shell such as `sh`, `bash`, or `zsh`

Run this in Terminal:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

What that does:

- clones the GitHub repo into `~/.aegis-agent`
- installs the command shim at `~/.local/bin/aegis`
- keeps the install terminal-only
- prints the PATH command if `~/.local/bin` is not already on your shell path

If `aegis` is not found after install, run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then open a new terminal, or add that export line to `~/.zshrc`, `~/.bashrc`, or your shell profile.

## First Run

After install, start here:

```bash
aegis setup next
aegis setup --run-checks
aegis
```

`aegis setup next` shows the next concrete setup action. On a fresh install it starts with the model route:

```bash
aegis setup model
```

Inside the terminal UI, use the same setup path:

```text
/setup next
/setup run-checks
/dashboard
/capabilities
```

You can also type normal requests directly into the composer:

```text
summarize this workspace
read file README.md
git status
run tests
```

## Update From GitHub

To update the installed agent from GitHub down to the computer it is running on:

```bash
aegis update --approved
```

That command runs a guarded fast-forward pull from `origin/main` inside `~/.aegis-agent`. It refuses to update if the checkout has local changes or if the remote does not match `MatthewLopez1990/AegisAgent`.

You can also run the update script directly:

```bash
~/.aegis-agent/scripts/update.sh
```

For a source checkout, update with normal git:

```bash
git pull --ff-only origin main
PYTHONPATH=src python3 -m aegisagent health
```

## Common Commands

| Command | Use |
| --- | --- |
| `aegis` | Start the terminal UI in a real terminal, or print activation details outside one. |
| `aegis activation` | Show terminal startup commands and browser-off safety flags. |
| `aegis setup next` | Show the next concrete setup step. |
| `aegis setup model` | Inspect model-provider setup commands. |
| `aegis setup --run-checks` | Run metadata-only setup verification. |
| `aegis health` | Check runtime, audit, sandbox, tools, memory, provider, and connector posture. |
| `aegis dashboard` | Show the terminal operator dashboard. |
| `aegis capabilities` | Show implemented and partial capability areas. |
| `aegis capabilities --gaps` | Show remaining gaps only. |
| `aegis update --approved` | Pull the latest GitHub `main` into the installed checkout. |
| `aegis tui --print` | Print a static terminal frame for docs, CI, or non-interactive terminals. |

## Useful TUI Slash Commands

```text
/commands
/setup next
/setup model
/setup sandbox
/setup tools
/setup connectors
/setup run-checks
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
/agents
/agents delegate <task>
/subagents bg <task>
/automations
/improve
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

Approval-gated TUI commands use `| approve`. CLI commands use `--approved`. This is intentional: network calls, writes, git mutations, browser records, external delivery, and elevated actions should be explicit operator choices.

## Source Checkout

Use this path if you are developing AegisAgent instead of installing the user command:

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

Source-checkout commands:

```bash
PYTHONPATH=src python3 -m aegisagent activation
PYTHONPATH=src python3 -m aegisagent setup next
PYTHONPATH=src python3 -m aegisagent setup --run-checks
PYTHONPATH=src python3 -m aegisagent tui
```

## Optional Web Console

The web console is not required for install, setup, update, health checks, or normal agent work.

Start it only when you explicitly want the browser UI:

```bash
python3 -m pip install -e '.[gateway]'
aegis web
aegis web --serve --approved --host 127.0.0.1 --port 8787
```

In another terminal:

```bash
cd web
npm install
npm run dev -- --port 5173
```

`aegis web` is preview-only. It prints the web commands and does not start a server or open a browser. `aegis web --serve --approved` starts the local gateway only after explicit approval; it still does not launch a browser.

## More CLI Examples

Model and connector metadata:

```bash
aegis model providers
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model doctor
aegis model usage
aegis connectors
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
```

Tasks, agents, and subagents:

```bash
aegis chat "summarize this workspace"
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

## Verify A Source Checkout

Backend tests:

```bash
PYTHONPATH=src python3 -Wd -m unittest discover -s tests -v
```

Terminal checks:

```bash
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
PYTHONPATH=src python3 -m aegisagent tui --print --width 100 --height 32
```

Web checks:

```bash
cd web
npm run verify
```

## Security Contract

AegisAgent fails closed for destructive commands and secret echo. Network calls, shell writes, external delivery, elevated actions, browser actions, and unrecognized tool calls require explicit approval. Audit payloads are redacted before persistence, and `aegis audit verify` checks the chained receipt hash.

## Current Status

AegisAgent is still an early terminal-first foundation, not a complete Hermes-class agent. The implemented surface includes install/update lifecycle, terminal activation, TUI, setup checks, health checks, policy/audit receipts, typed workspace tools, governed git operations, task queues, automations, model-route metadata, connector metadata, and local agent/subagent orchestration. Remaining work includes deeper live browser control, richer model-backed multi-agent execution, broader integrations, and stronger packaged release flows.
