# AegisAgent

AegisAgent is a terminal-first agent console. Install it, run `aegis`, then type
normal requests or slash commands in the terminal UI.

It is being built toward a secure Hermes-style workflow: prompt-first chat,
slash commands, typed local tools, memory, task queues, subagents, automations,
audit receipts, and explicit approval gates.

AegisAgent does not open a browser during install, setup, update, launch, health
checks, or normal terminal use. The web console is optional and must be started
separately.

This project is `AegisAgent`. Older `Aegis-Agent` references are historical
design inputs, not the install target.

## Quick Start

Install on macOS or Linux:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

Make sure your shell can find the command:

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v aegis
```

Start the agent:

```bash
aegis
```

Optional: connect OpenAI with one command after exporting your key:

```bash
export OPENAI_API_KEY="..."
aegis model connect openai
```

Update this installed checkout from GitHub later:

```bash
aegis update --approved
```

Inside the terminal UI, type a normal request:

```text
review this workspace
summarize README.md
run tests
```

Or type a slash command for a direct action:

```text
/setup next
/agents delegate review this workspace
/tasks submit draft a safe implementation plan
```

## Install On macOS Or Linux

Check prerequisites:

```bash
python3 --version
git --version
```

This works on macOS and Linux. You need `git`, `curl`, and `python3` 3.12 or
newer. The installer clones GitHub into `~/.aegis-agent` and writes the command
shim to `~/.local/bin/aegis`.

Verify the command:

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v aegis
aegis activation
```

If `command -v aegis` prints nothing, add this line to `~/.zshrc`, `~/.bashrc`,
or your shell profile, then open a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Optional installer settings are environment variables:

```bash
AEGIS_INSTALL_DIR="$HOME/.aegis-agent"
AEGIS_BIN_DIR="$HOME/.local/bin"
AEGIS_COMMAND_NAME="aegis"
AEGIS_BRANCH="main"
AEGIS_REPO_URL="https://github.com/MatthewLopez1990/AegisAgent.git"
```

## Connect A Model Route

Aegis works immediately with the built-in local terminal provider. No account,
browser login, or API key is required:

```bash
aegis model connect local
aegis model doctor
```

To use OpenAI, keep the key in your shell and let Aegis store only the
environment-variable name:

```bash
export OPENAI_API_KEY="..."
aegis model connect openai
aegis model doctor
aegis chat "summarize this workspace"
```

`aegis model connect openai` defaults to `openai/gpt-5.5` and the
`OPENAI_API_KEY` environment handle. Use `--model` or `--api-key-env` only when
you need a non-default route:

```bash
aegis model connect openai --model gpt-5.5 --api-key-env OPENAI_API_KEY
```

Advanced compatibility commands still work:

```bash
aegis model providers
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model configure openai/gpt-5.5 --mode subscription_cli
```

The subscription CLI bridge is metadata-only for now. Auth login/logout do not
launch a browser; use `aegis model connect openai` for the supported external
provider path.

## Start The Agent

Run these once after install:

```bash
export PATH="$HOME/.local/bin:$PATH"
aegis activation
aegis setup next
aegis setup model
aegis setup --run-checks
```

Then start the terminal UI with either command:

```bash
aegis
aegis tui
```

`aegis` starts the terminal UI when your shell is interactive. Use `aegis tui`
when you want the explicit command.

## Use The Agent

Type normal requests at the prompt:

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
/agents delegate review this workspace
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

From the installed `aegis` command, run:

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

## Use Model-Backed Agents

Run model-backed role workers:

```bash
aegis agents
aegis agents contracts
aegis agents delegate "review this workspace"
aegis agents bg "compare implementation options"
aegis agents artifacts
aegis agents artifacts show <artifact-id>
aegis agents artifacts search "Checkpoint plan"
aegis agents delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis model usage
```

`aegis agents delegate` runs planner, researcher, implementer, and reviewer
workers through the active provider route, records isolated sessions, scoped
usage metadata, durable role artifacts, input-artifact handoff metadata, and
audit receipts, and falls back locally if an attempted external route fails.
Later-stage workers receive prior worker artifact summaries while preserving the
same bounded role contracts and approval model.

Artifact browsing is read-only by default. `aegis agents artifacts` lists
durable role artifacts, `show` reads redacted artifact content, and `search`
matches ids, roles, titles, summaries, and redacted artifact text. Separately,
selected prior artifacts can be reused by a later delegation only after explicit
approval:

```bash
aegis agents delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis subagents --delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
```

In the terminal UI, use the same approval style as other gated actions:

```text
/agents delegate continue from this prior artifact | use-artifact <artifact-id> | approve
/subagents continue from this prior artifact | use-artifact <artifact-id> | approve
```

Aegis records reused artifact ids in session metadata and audit receipts, then
passes artifact ids, roles, titles, and summaries as bounded context to staged
workers. This is approved context reuse, not final synthesis over an artifact
graph, and artifact bodies are not sent as model context by reuse.

## Common Commands

```bash
aegis                         # start the terminal UI
aegis activation              # print terminal readiness card
aegis commands                # show slash-command lanes
aegis setup next              # show the next setup action
aegis model connect openai    # connect OpenAI by environment handle
aegis setup --run-checks      # run metadata-only readiness checks
aegis model doctor            # check configured model route
aegis tasks --submit "do work"
aegis tasks --events <id>
aegis memory search <query>
aegis connectors outbox
aegis agents artifacts
aegis audit verify
aegis update --approved
```

The canonical command is `aegis`. The Python package also exposes `aegisagent`
for source and package workflows. Older compatibility aliases are documented in
[docs/operator-reference.md](docs/operator-reference.md).

Common setup aliases from older terminal habits still map to the current setup
surface when they are read-only:

```bash
aegis setup model-auth
aegis setup connections
aegis setup verify
```

## Safety Model

Aegis stores environment variable names for secrets, not raw secret values. It
does not open a browser during normal terminal use. File, git, browser, and
external-state mutations require explicit approval. Audit receipts record model
routes, tool actions, fallbacks, and redaction state.

Connector metadata follows the same pattern:

```bash
export SLACK_BOT_TOKEN="..."
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
```

Connector delivery is not live yet. The terminal can draft redacted connector
packets and record an explicit approval packet in the outbox, but no Slack,
Teams, webhook, or Open WebUI network delivery is performed by these commands:

```bash
aegis connectors draft slack --target "#ops" --message "Status update"
aegis connectors send slack --target "#ops" --message "Status update"
aegis connectors send slack --target "#ops" --message "Status update" --approved
aegis connectors outbox
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
workspace tools, governed git operations, task queues, automations,
OpenAI-compatible model routing for chat and role workers, scoped model usage
ledger rows, connector metadata with a redacted approval-bound outbox, memory
review controls, passive skill trust metadata, and local agent/subagent
orchestration with provider fallback metadata, durable role artifacts,
artifact list/show/search, stage-to-stage handoff metadata, and
approval-gated reuse of selected prior artifacts as bounded summary context.

Partial: web console parity, live connectors, self-improvement, richer browser
automation, multi-provider fallback ordering, subscription bridge readiness,
richer role-specific tool budgets, and higher-depth delegation controls.

Next: richer role-specific tool budgets, higher-depth delegation controls, final
synthesis over artifact graphs, live browser control behind explicit approval,
broader integrations, signed skill trust, and packaged release flows.
