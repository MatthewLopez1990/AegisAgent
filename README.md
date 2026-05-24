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

Step 1: install the `aegis` terminal command on macOS or Linux:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

If your shell cannot find `aegis` right away, run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Step 2: verify the command:

```bash
command -v aegis
aegis health
```

Step 3: choose a model route.

Use the built-in local route with no account:

```bash
aegis model connect local
aegis model doctor
```

Or connect OpenAI with one environment-variable handle:

```bash
export OPENAI_API_KEY="..."
aegis model connect openai
aegis model doctor
```

Step 4: start Aegis:

```bash
aegis
```

Inside the terminal UI, type a normal request or slash command:

```text
review this workspace
summarize README.md
/setup next
/agents delegate review this workspace
```

Update the installed copy from GitHub later:

```bash
aegis update --approved
aegis health
aegis audit verify
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

Install:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
```

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

Aegis stores the provider choice and an environment-variable name only. It does
not store the raw key.

Choose one.

No account:

```bash
aegis model connect local
aegis model doctor
```

OpenAI:

```bash
export OPENAI_API_KEY="..."
aegis model connect openai
aegis model doctor
```

`aegis model connect openai` defaults to `openai/gpt-5.5` and the
`OPENAI_API_KEY` environment handle.

To keep OpenAI available in future terminals, add the export line to `~/.zshrc`,
`~/.bashrc`, or your shell profile, then open a new terminal:

```bash
export OPENAI_API_KEY="..."
```

Use these only for non-default providers or models:

```bash
aegis model providers
aegis model connect openai --model gpt-5.5 --api-key-env OPENAI_API_KEY
```

OpenAI-compatible endpoints need an environment-variable handle and their base
URL:

```bash
export OPENROUTER_API_KEY="..."
aegis model connect openrouter --base-url https://openrouter.ai/api/v1 --model openai/gpt-4o-mini
aegis model doctor
```

Auth login/logout do not launch a browser; use `aegis model connect openai` for
the supported external provider path.

## Start The Agent

Run these after install:

```bash
export PATH="$HOME/.local/bin:$PATH"
aegis activation
aegis setup next
aegis health
aegis setup --run-checks
```

Then start the terminal UI with either command:

```bash
aegis
aegis tui
```

`aegis` starts the terminal UI when your shell is interactive. Use `aegis tui`
when you want the explicit command. `aegis activation` only prints readiness.
These commands do not start the gateway, Vite, or a browser.

## Use The Agent

Type normal requests at the prompt:

```text
summarize this workspace
read file README.md
summarize @README.md
review @src/aegisagent/tui/interactive.py
git status
run tests
```

Inside the TUI composer, type `@` plus a partial workspace path and press `Tab`
to complete local file and directory references. Composer path completion only
lists local metadata. It does not open a browser, start the web gateway, call a
model, read file bodies, or mutate the workspace. The final request still
follows normal Aegis tool and approval policy.

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
aegis agents jobs
aegis agents monitor <job-id>
aegis agents status <root-id>
aegis agents synthesis <root-id>
aegis agents graph <root-id>
aegis agents cancel <job-id>
aegis agents recover
aegis agents artifacts
aegis agents artifacts show <artifact-id>
aegis agents artifacts search "Checkpoint plan"
aegis agents delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis agents bg "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis model usage
```

Use `delegate` when you want the run to finish before the command returns. Use
`bg` when you want a durable background job, then `jobs`, `monitor <job-id>`,
and `status <root-id>` to follow progress from the terminal. Monitor and status
commands are plain text by default, `--json` when requested, and do not launch a
browser.

`aegis agents delegate` runs planner, researcher, implementer, and reviewer
workers through the active provider route, records isolated sessions, scoped
usage metadata, durable role artifacts, input-artifact handoff metadata, and
audit receipts, and falls back locally if an attempted external route fails.
Later-stage workers receive prior worker artifact summaries while preserving the
same bounded role contracts and approval model. After the workers finish, the
coordinator writes a final synthesis artifact over the generated and approved
reused artifact graph so the delegation has one traceable final handoff.
Each role contract includes structured tool budget policy fields for allowed and
denied tool groups, max tool calls, max artifacts, edit/test/network flags, and
external-delivery denial. These budgets are contract and audit controls; file,
git, browser, connector, memory, and external-state mutations still go through
the typed approval policy.
Depth 2 is opt-in: `--depth 2` nests the reviewer under the implementer for a
bounded review topology. It is not arbitrary recursive spawning, autonomous
fan-out, or a global worker pool.

Artifact browsing is read-only by default. `aegis agents artifacts` lists
durable role artifacts, `show` reads redacted artifact content, and `search`
matches ids, roles, titles, summaries, and redacted artifact text. Separately,
selected prior artifacts can be reused by a later delegation only after explicit
approval:

```bash
aegis agents delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis agents bg "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis subagents --delegate "continue from this prior artifact" --use-artifact <artifact-id> --approved
aegis subagents --background "continue from this prior artifact" --use-artifact <artifact-id> --approved
```

In the terminal UI, use the same approval style as other gated actions:

```text
/agents delegate continue from this prior artifact | use-artifact <artifact-id> | approve
/agents bg continue from this prior artifact | use-artifact <artifact-id> | approve
/subagents continue from this prior artifact | use-artifact <artifact-id> | approve
/subagents bg continue from this prior artifact | use-artifact <artifact-id> | approve
```

Aegis records reused artifact ids in session metadata and audit receipts, then
passes artifact ids, roles, titles, and summaries as bounded context to staged
workers. Each completed delegation also writes a coordinator `final_synthesis`
artifact that merges planner, researcher, implementer, reviewer, and approved
reused artifact metadata over the artifact graph. Reuse still sends summary
metadata only; artifact bodies are not sent as model context by reuse.
Background artifact reuse persists approved artifact ids in the job record and
revalidates them when the job runs. It does not permit unapproved detached-job
reuse, connector delivery, browser launch, or raw artifact-body model reuse.

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
aegis agents bg "review this workspace"
aegis agents monitor <job-id>
aegis agents status <root-id>
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

Webhook delivery is the only live connector delivery path. Configure it with an
environment-variable URL handle, then approve each send explicitly:

```bash
export AEGIS_WEBHOOK_URL="https://example.invalid/aegis-hook"
aegis connectors configure webhook --url-env AEGIS_WEBHOOK_URL --enable
aegis connectors doctor
aegis connectors send webhook --target "ops-status" --message "Status update" --approved
aegis connectors outbox
```

Slack, Teams, and Open WebUI connector commands remain metadata/outbox-only;
approving those packets does not contact those services:

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
ledger rows, connector metadata with a redacted approval-bound outbox,
approval-gated webhook delivery, memory review controls, passive skill trust
metadata, and local agent/subagent
orchestration with provider fallback metadata, durable role artifacts,
artifact list/show/search, structured role-specific tool budget policies,
stage-to-stage handoff metadata, opt-in depth-2 reviewer nesting,
approval-gated reuse of selected prior artifacts as bounded summary context,
approval-gated detached-job artifact reuse, and coordinator final synthesis over
artifact graphs.

Partial: web console parity, live connectors, self-improvement, richer browser
automation, multi-provider fallback ordering, and subscription bridge readiness.

Next: richer execution backends, live browser control behind explicit approval,
broader integrations, signed skill trust, and packaged release flows.
