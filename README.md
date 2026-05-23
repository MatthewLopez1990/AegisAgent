# AegisAgent

AegisAgent is a security-first autonomous agent platform scaffold. It keeps Hermes/OpenClaw-style capability classes, but puts governance in the primary product surface: policy decisions, approvals, sandbox posture, secret redaction, and append-only audit receipts are visible by default.

## What Is Implemented

- Python package and CLI: `aegisagent`, `aegisagent activate`, `aegisagent activation`, `aegisagent dashboard`, `aegisagent setup`, `capabilities`, `health`, `audit verify`, `tools`, `skills`, `memory`, `sessions`, `chat`, `model`, `connectors`, `browser`, `tasks`, `automations`, `improve`, `agents`, `subagents`, `verify`, `fetch`, `edit`, `git`, `gateway`, and `tui`. Editable installs also expose the shorter `aegis` command.
- Security kernel: default-gated network and host writes, destructive shell blocklist, secret redaction, policy decisions with receipt IDs, Docker-preferred sandbox detection, and append-only JSONL plus SQLite audit storage.
- Runtime stores: workspace-local `.aegisagent/` state, curated `MEMORY.md` / `USER.md`, SQLite memory search, approval-gated curated memory notes, skill discovery and quarantine markers, bounded subagent queue.
- Prompt-first TUI: curses-backed interactive terminal UI with slash palette, first-launch setup wizard, panel deck, composer, local agent turns, setup/tools/audit commands, and static `--print` frames for CI and docs.
- Guided setup: `aegisagent setup --quick`, `aegisagent setup --full`, `aegisagent setup model`, `setup secrets`, `setup sandbox`, `setup tools`, `setup connectors`, `setup memory`, `/setup <section>`, and `/setup run-checks` provide a numbered terminal-first onboarding path with metadata-only verification.
- Local agent runtime: `aegisagent chat` and normal TUI prompt input append user/tool/assistant messages to persistent sessions, write audit receipts, use the built-in local provider by default, and route to a configured OpenAI-compatible API-key provider only when the active route is ready. Missing or unsafe external routes fail closed without opening a browser or reading raw secrets.
- Model route setup and usage: `aegisagent model providers`, `aegisagent model configure <name> --mode api_key --api-key-env <ENV_NAME> --base-url <URL>`, `aegisagent model doctor`, `aegisagent model usage`, `/model providers`, `/model doctor`, `/model usage`, `/setup model`, and `/setup run-checks` expose durable provider-route metadata, environment readiness checks, terminal-visible usage accounting, and audit receipts without reading raw secrets or launching a browser. `model doctor` is metadata-only; terminal chat is the explicit model invocation path. If a ready external route is attempted and fails, Aegis answers through the local terminal fallback and records the primary route, fallback provider, and failure status.
- Connector readiness: `aegisagent connectors`, `aegisagent connectors configure slack --token-env SLACK_BOT_TOKEN --enable`, `aegisagent connectors doctor`, `/connectors`, and `/connectors doctor` expose Slack, Teams, webhook, MCP, browser, and Open WebUI adapter metadata without sending messages, launching a browser, or starting external delivery. `aegisagent browser open <url> --approved`, `aegisagent browser screenshot <session-id> <path> --approved`, `/browser open <url> | approve`, and `/browser screenshot <session-id> | <path> | approve` create explicit browser session records and screenshot receipts without auto-launching a browser.
- Terminal dashboard and capability map: `aegisagent dashboard`, `/dashboard`, `aegisagent capabilities`, `aegisagent capabilities --gaps`, `/capabilities`, and `/gaps` show runtime posture, activation status, model/connectors, agent contracts, implemented capability classes, partial gaps, and terminal-first/browser-off safety fields.
- Terminal install and update: `aegisagent install`, `aegisagent install shim --approved`, `aegisagent update`, `aegisagent update --approved`, `/install`, and `/update` provide macOS/Linux terminal lifecycle commands. The install shim writes `~/.local/bin/aegis` by default, and update runs `git pull --ff-only origin main` only after explicit approval.
- Session transcript search: `aegisagent sessions --query "<text>"`, `/sessions search <text>`, and prompts such as `search sessions for receipt` search redacted prior terminal transcripts with audit receipts.
- Governed task queue: `aegisagent tasks --submit "<request>"`, `aegisagent tasks --background "<request>"`, `aegisagent tasks --events <task-id>`, `aegisagent tasks --output <task-id>`, `aegisagent tasks --logs <task-id>`, `aegisagent tasks --recover-stale`, `aegisagent tasks --run <task-id>`, `/tasks submit <request>`, `/tasks bg <request>`, `/tasks start <task-id>`, `/tasks run <task-id>`, `/tasks events <task-id>`, `/tasks output <task-id>`, `/tasks logs <task-id>`, `/tasks watch <task-id>`, `/tasks unwatch`, `/tasks recover`, `/tasks cancel <task-id>`, and `/q <request>` persist top-level agent work with receipts before execution, live terminal progress in the TUI, recorded assistant/tool output, detached worker stdout/stderr logs, and stale worker recovery. Normal task list/show/watch paths automatically mark dead detached workers failed with audit receipts, and TUI task watch refreshes without blocking the composer.
- Durable automation records: `aegisagent automations`, `aegisagent automations create <name> --schedule "<schedule>" --prompt "<prompt>"`, `aegisagent automations due`, `aegisagent automations missed`, `aegisagent automations replay-missed`, `aegisagent automations tick`, `aegisagent automations worker --max-ticks 5`, `aegisagent automations logs [run-id]`, `aegisagent automations service`, `aegisagent automations service-status`, `aegisagent automations trigger <id>`, `aegisagent automations pause <id>`, `aegisagent automations resume <id>`, `/automations`, `/automations create <name> | <schedule> | <prompt>`, `/automations due`, `/automations missed`, `/automations replay`, `/automations tick`, `/automations worker`, `/automations logs [run-id]`, `/automations service`, `/automations service-status`, `/automations trigger <id>`, `/automations pause <id>`, and `/automations resume <id>` persist gated schedule records, check due and missed state from the terminal, explicitly replay missed windows, queue governed tasks, inspect foreground worker logs, generate an operator-loaded launchd wrapper, and inspect service state with health metrics and audit receipts. Schedules support `now`, `hourly`, `every N minutes/hours/days`, `daily 09:00`, `weekdays 09:00`, `weekends 09:00`, `weekly Monday 09:00`, `monthly 15 09:00`, and `monthly last 09:00`, with optional IANA timezone suffixes such as `America/Denver` or `tz=America/Denver`, plus local-date exceptions such as `except=2026-12-25,2026-12-26` or `skip=2026-12-25`. No hidden daemon scheduler is started; the worker is an explicit foreground terminal command and reports `schedule_worker_started=true` only while that operator-started run is active.
- Governed self-improvement loop: `aegisagent improve`, `aegisagent improve propose "<failure>" --target <subsystem> --operation <operation>`, `aegisagent improve approve <id>`, `aegisagent improve candidate <id>`, `aegisagent improve diff <candidate-id>`, `aegisagent improve verify <candidate-id>`, `aegisagent improve apply <candidate-id>`, `aegisagent improve evidence <id> --files <paths> --validation <command> --result <result>`, `aegisagent improve complete <id>`, `/improve`, `/improve propose <failure>`, `/improve approve <id>`, `/improve candidate <id>`, `/improve diff <candidate-id>`, `/improve verify <candidate-id>`, `/improve apply <candidate-id>`, `/improve evidence <id> | <files> | <command> | <result>`, and `/improve complete <id>` persist reviewed improvement proposals with failure classification, required validation, audit receipts, advisory repair candidates, read-only candidate diff reviews, automated candidate verification receipts, verified candidate apply-review handoffs into governed tasks, changed-file evidence, and implemented-state receipts. This does not auto-edit the workspace; proposals report `workspace_mutation_allowed_before_approval=false`.
- Typed workspace and network tools: workspace prompts and TUI slash commands can call audited non-shell tools including `workspace.list_files`, `workspace.search_text`, `workspace.read_file`, `git.status`, `git.diff`, `git.stage`, `git.commit`, `git.branch`, `git.remote`, `workspace.run_tests`, `workspace.replace_text`, and `web.fetch` before the assistant response. `aegisagent verify`, `/test`, `/verify`, and prompts such as `run tests` execute allowlisted Python unittest/py_compile commands without shell parsing. `aegisagent fetch <url> --approved` and `/web fetch <url> | approve` perform approval-gated terminal URL fetches without opening a browser. `aegisagent git stage <path> --approved` and `/git stage <path> | approve` provide approval-gated git index staging. `aegisagent git commit --message "<message>" --approved` and `/git commit <message> | approve` provide approval-gated git history commits for staged changes. `aegisagent git branch create <name> --approved`, `aegisagent git branch switch <name> --approved`, `/git branch create <name> | approve`, and `/git branch switch <name> | approve` provide approval-gated branch ref changes. `aegisagent git remote` lists remotes read-only, while `aegisagent git remote fetch <remote> [branch] --approved`, `aegisagent git remote pull <remote> <branch> --approved`, `aegisagent git remote push <remote> <branch> --approved`, `/git remote fetch <remote> [branch] | approve`, `/git remote pull <remote> <branch> | approve`, and `/git remote push <remote> <branch> | approve` provide approval-gated remote operations. `aegisagent edit replace ... --approved` and `/edit replace <path> | <old> | <new> | approve` provide explicit approval-gated exact text replacement inside the workspace.
- Hermes-style agent orchestration: `aegisagent agents`, `aegisagent agents profiles`, `aegisagent agents contracts`, `aegisagent agents delegate "<task>"`, `aegisagent agents bg "<task>"`, `/agents`, `/agents profiles`, `/agents contracts`, `/agents delegate <task>`, `/agents bg <task>`, `/agents monitor <job-id>`, and `/agents recover` expose planner/researcher/implementer/reviewer agent profiles backed by the same governed local subagent runtime, with visible role contracts, deliverables, budgets, terminal-first status, no browser auto-launch, isolated sessions, per-worker receipts, background jobs, and stale worker recovery.
- Local subagent orchestration: `aegisagent subagents --delegate "<task>"`, `aegisagent subagents --stream "<task>"`, `aegisagent subagents --background "<task>"`, `aegisagent subagents --cancel <job-id>`, `aegisagent subagents --recover-stale`, `aegisagent subagents --jobs`, `aegisagent subagents --events <root-id>`, `aegisagent subagents --stop <id>`, `/subagents <task>`, `/subagents monitor <job-id>`, `/subagents unwatch`, `/subagents recover`, and delegation prompts create bounded planner/researcher/implementer/reviewer workers with isolated sessions, per-worker receipts, readable terminal summaries, timeline events, streaming terminal output, cancellable background jobs, nonblocking TUI job monitoring, stale worker recovery, and persisted cascade stop.
- Gateway: optional FastAPI/WebSocket app exposing health, tools, policy evaluation, and streaming policy receipts.

## Quick Start

```bash
PYTHONPATH=src python3 -m aegisagent
PYTHONPATH=src python3 -m aegisagent activate
PYTHONPATH=src python3 -m aegisagent activation
PYTHONPATH=src python3 -m aegisagent dashboard
PYTHONPATH=src python3 -m aegisagent install
PYTHONPATH=src python3 -m aegisagent install shim --approved
PYTHONPATH=src python3 -m aegisagent update
PYTHONPATH=src python3 -m aegisagent update --approved
PYTHONPATH=src python3 -m aegisagent setup --run-checks
PYTHONPATH=src python3 -m aegisagent setup --quick
PYTHONPATH=src python3 -m aegisagent setup model
PYTHONPATH=src python3 -m aegisagent setup sandbox
PYTHONPATH=src python3 -m aegisagent capabilities
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent audit verify
PYTHONPATH=src python3 -m aegisagent tools --matrix
PYTHONPATH=src python3 -m aegisagent verify
PYTHONPATH=src python3 -m aegisagent fetch https://example.com --approved
PYTHONPATH=src python3 -m aegisagent browser open https://example.com --approved
PYTHONPATH=src python3 -m aegisagent browser sessions
PYTHONPATH=src python3 -m aegisagent memory --kind user --title "Terminal preference" --add "Prefers terminal-first activation." --approved
PYTHONPATH=src python3 -m aegisagent git stage <path> --approved
PYTHONPATH=src python3 -m aegisagent git commit --message "Describe staged changes" --approved
PYTHONPATH=src python3 -m aegisagent git branch create codex/example --approved
PYTHONPATH=src python3 -m aegisagent git remote fetch origin codex/example --approved
PYTHONPATH=src python3 -m aegisagent git remote pull origin codex/example --approved
PYTHONPATH=src python3 -m aegisagent git remote push origin codex/example --approved
PYTHONPATH=src python3 -m aegisagent edit replace README.md --old "old text" --new "new text" --approved
PYTHONPATH=src python3 -m aegisagent chat "summarize this workspace"
PYTHONPATH=src python3 -m aegisagent chat "read file README.md" --json
PYTHONPATH=src python3 -m aegisagent chat "git status" --json
PYTHONPATH=src python3 -m aegisagent model providers
PYTHONPATH=src python3 -m aegisagent model doctor
PYTHONPATH=src python3 -m aegisagent model usage
PYTHONPATH=src python3 -m aegisagent connectors
PYTHONPATH=src python3 -m aegisagent connectors doctor
PYTHONPATH=src python3 -m aegisagent sessions --query "audit receipt"
PYTHONPATH=src python3 -m aegisagent tasks --submit "draft a safe plan"
PYTHONPATH=src python3 -m aegisagent tasks --background "draft a safe plan"
PYTHONPATH=src python3 -m aegisagent automations
PYTHONPATH=src python3 -m aegisagent automations create daily-check --schedule "daily 09:00" --prompt "summarize workspace risks"
PYTHONPATH=src python3 -m aegisagent automations create weekday-check --schedule "weekdays 09:00" --prompt "summarize weekday risks"
PYTHONPATH=src python3 -m aegisagent automations create denver-check --schedule "weekdays 09:00 America/Denver" --prompt "summarize Denver weekday risks"
PYTHONPATH=src python3 -m aegisagent automations create holiday-aware-check --schedule "weekdays 09:00 America/Denver except=2026-12-25" --prompt "summarize weekday risks except holidays"
PYTHONPATH=src python3 -m aegisagent automations create month-end-check --schedule "monthly last 09:00" --prompt "summarize monthly state"
PYTHONPATH=src python3 -m aegisagent automations due
PYTHONPATH=src python3 -m aegisagent automations missed
PYTHONPATH=src python3 -m aegisagent automations replay-missed
PYTHONPATH=src python3 -m aegisagent automations tick
PYTHONPATH=src python3 -m aegisagent automations worker --max-ticks 5
PYTHONPATH=src python3 -m aegisagent automations logs <run-id>
PYTHONPATH=src python3 -m aegisagent automations service
PYTHONPATH=src python3 -m aegisagent automations service-status
PYTHONPATH=src python3 -m aegisagent automations trigger <automation-id>
PYTHONPATH=src python3 -m aegisagent improve
PYTHONPATH=src python3 -m aegisagent improve propose "policy denied a needed safe git read" --target policy --operation evaluate
PYTHONPATH=src python3 -m aegisagent improve candidate <proposal-id>
PYTHONPATH=src python3 -m aegisagent improve diff <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve verify <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve apply <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve implement <proposal-id>
PYTHONPATH=src python3 -m aegisagent improve evidence <proposal-id> --files "src/aegisagent/core/policy.py,tests/test_policy.py" --validation "PYTHONPATH=src python3 -m unittest tests.test_policy -v" --result "passed"
PYTHONPATH=src python3 -m aegisagent improve complete <proposal-id>
PYTHONPATH=src python3 -m aegisagent agents
PYTHONPATH=src python3 -m aegisagent agents profiles
PYTHONPATH=src python3 -m aegisagent agents contracts
PYTHONPATH=src python3 -m aegisagent agents delegate "improve terminal orchestration"
PYTHONPATH=src python3 -m aegisagent subagents --delegate "improve terminal orchestration"
PYTHONPATH=src python3 -m aegisagent tui
PYTHONPATH=src python3 -m aegisagent tui --view activation --print
```

`aegisagent`, `aegisagent activate`, and `aegisagent tui` are the terminal-first activation paths. `aegisagent activation` is the non-launching status card for confirming the exact terminal command, source-checkout module command, and browser-off safety flags. `aegisagent dashboard` and `/dashboard` provide a read-only terminal operator dashboard for runtime posture, gaps, routes, and agent contracts without starting the web gateway. `aegisagent install` previews the macOS/Linux terminal install path, `aegisagent install shim --approved` writes the `aegis` command shim, and `aegisagent update --approved` pulls `origin/main` with `git pull --ff-only`; `/install` and `/update` expose the same lifecycle path inside the TUI. After `python3 -m pip install -e .`, `aegis` and `aegis tui` use the same terminal-first path. In a real terminal the default entrypoint launches the interactive curses UI; outside a TTY it prints a terminal activation card instead of generic help. These commands never start the web gateway or open a browser. First launch opens the setup wizard inside the terminal while keeping the composer live; `/setup hide` keeps later launches prompt-first, and `/setup reset` restores the wizard. Use `/activation`, `/dashboard`, `/install`, `/update`, `/commands`, `/menu`, `/capabilities`, `/gaps`, `/submit <request>`, `/tasks`, `/tasks submit <request>`, `/tasks bg <request>`, `/tasks start <task-id>`, `/tasks run <task-id>`, `/tasks events <task-id>`, `/tasks output <task-id>`, `/tasks logs <task-id>`, `/tasks watch <task-id>`, `/tasks unwatch`, `/tasks recover`, `/tasks cancel <task-id>`, `/automations`, `/automations create <name> | <schedule> | <prompt>`, `/automations due`, `/automations missed`, `/automations replay`, `/automations tick`, `/automations worker`, `/automations logs [run-id]`, `/automations service`, `/automations service-status`, `/automations trigger <id>`, `/automations pause <id>`, `/automations resume <id>`, `/improve`, `/improve propose <failure>`, `/improve approve <id>`, `/improve candidate <id>`, `/improve verify <candidate-id>`, `/improve apply <candidate-id>`, `/improve evidence <id> | <files> | <command> | <result>`, `/improve complete <id>`, `/q <request>`, `/clear`, `/new [title]`, `/reset [title]`, `/add-dir <path>`, `/model providers`, `/model doctor`, `/model usage`, `/setup`, `/setup first-task`, `/setup hide`, `/setup reset`, `/tools`, `/audit`, `/memory`, `/memory add <workspace|user> | <title> | <body> | approve`, `/skills`, `/read <path>`, `/web fetch <url> | approve`, `/browser`, `/browser open <url> | approve`, `/browser screenshot <session-id> | <path> | approve`, `/git status`, `/git diff [path]`, `/git stage <path> | approve`, `/git commit <message> | approve`, `/git branch create <name> | approve`, `/git branch switch <name> | approve`, `/git remote fetch <remote> [branch] | approve`, `/git remote pull <remote> <branch> | approve`, `/git remote push <remote> <branch> | approve`, `/test [command]`, `/verify [command]`, `/sessions search <query>`, `/agents`, `/agents profiles`, `/agents contracts`, `/agents delegate <task>`, `/agents bg <task>`, `/agents jobs`, `/agents monitor <job-id>`, `/agents unwatch`, `/agents recover`, `/subagents <task>`, `/subagents live <task>`, `/subagents bg <task>`, `/subagents jobs`, `/subagents job <id>`, `/subagents monitor <job-id>`, `/subagents unwatch`, `/subagents recover`, `/subagents cancel <job-id>`, `/subagents watch <root-id>`, `/subagents stop <id>`, `/policy shell <command>`, `/web`, `/exit`, and `/quit` inside the TUI.

Typed non-shell inspection commands inside the TUI:

```text
/read README.md
/git status
/git diff src/aegisagent/core/workspace_tools.py
/git stage src/aegisagent/core/workspace_tools.py | approve
/git commit Add typed git workflow | approve
/git branch create codex/example | approve
/git branch switch codex/example | approve
/git remote fetch origin codex/example | approve
/git remote pull origin codex/example | approve
/git remote push origin codex/example | approve
/web fetch https://example.com | approve
/browser open https://example.com | approve
/browser screenshot browser-abc123 | screenshots/example.txt | approve
/memory add user | Terminal preference | Prefers terminal-first activation. | approve
/edit replace README.md | old text | new text | approve
/test
/verify python3 -m unittest tests.test_cli -v
/sessions search audit receipt
/commands git
/activation
/dashboard
/install
/install shim | approve
/update
/update | approve
/capabilities
/gaps
/model providers
/model doctor
/model usage
/connectors
/connectors doctor
/setup model
/setup secrets
/setup sandbox
/setup tools
/setup connectors
/setup memory
/setup first-task
/setup run-checks
/setup hide
/setup reset
/submit summarize this workspace
/tasks submit draft a safe plan
/tasks bg draft a safe plan
/tasks start <task-id>
/tasks run <task-id>
/tasks events <task-id>
/tasks output <task-id>
/tasks logs <task-id>
/tasks watch <task-id>
/tasks unwatch
/tasks recover
/automations
/automations create daily-check | daily 09:00 | summarize workspace risks
/automations due
/automations missed
/automations replay
/automations tick
/automations worker
/automations logs <run-id>
/automations service
/automations service-status
/automations trigger <automation-id>
/automations pause <automation-id>
/automations resume <automation-id>
/improve
/improve propose policy denied a needed safe git read
/improve approve <proposal-id>
/improve candidate <proposal-id>
/improve diff <candidate-id>
/improve verify <candidate-id>
/improve apply <candidate-id>
/improve implement <proposal-id>
/improve evidence <proposal-id> | src/aegisagent/core/policy.py,tests/test_policy.py | PYTHONPATH=src python3 -m unittest tests.test_policy -v | passed
/improve complete <proposal-id>
/agents
/agents profiles
/agents contracts
/agents delegate improve terminal orchestration
/agents bg improve terminal supervision
/agents monitor <job-id>
/agents unwatch
/agents recover
/subagents bg improve terminal supervision
/subagents monitor <job-id>
/subagents unwatch
/subagents recover
/q queue this for later
```

Static terminal fallback for CI, docs, or snapshot checks:

```bash
PYTHONPATH=src python3 -m aegisagent tui --print --width 120 --height 40
```

Optional editable install:

```bash
python3 -m pip install -e .
aegisagent health
aegisagent tui
aegis tui
```

Optional gateway dependencies:

```bash
python3 -m pip install -e '.[gateway,tui]'
aegisagent gateway --host 127.0.0.1 --port 8787
```

Gateway readiness endpoints stay metadata-only:

```bash
curl http://127.0.0.1:8787/connectors
curl http://127.0.0.1:8787/connectors/doctor
curl http://127.0.0.1:8787/setup/connectors
curl http://127.0.0.1:8787/setup/run-checks
```

Web GUI:

```bash
cd web
npm install
npm run smoke
npm run dev -- --port 5173
```

The Web GUI mirrors the terminal security console. It may read local gateway metadata when the gateway is running, but setup and normal activation remain terminal-first.

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m aegisagent health
PYTHONPATH=src python3 -m aegisagent setup --run-checks
PYTHONPATH=src python3 -m aegisagent setup --quick
PYTHONPATH=src python3 -m aegisagent setup connectors
PYTHONPATH=src python3 -m aegisagent dashboard
PYTHONPATH=src python3 -m aegisagent capabilities
PYTHONPATH=src python3 -m aegisagent capabilities --gaps
PYTHONPATH=src python3 -m aegisagent audit verify
PYTHONPATH=src python3 -m aegisagent tui --help
PYTHONPATH=src python3 -m aegisagent verify
PYTHONPATH=src python3 -m aegisagent chat "draft a safe plan" --json
PYTHONPATH=src python3 -m aegisagent chat "read file README.md" --json
PYTHONPATH=src python3 -m aegisagent chat "git status" --json
PYTHONPATH=src python3 -m aegisagent chat "search sessions for audit receipt" --json
PYTHONPATH=src python3 -m aegisagent model providers
PYTHONPATH=src python3 -m aegisagent model doctor
PYTHONPATH=src python3 -m aegisagent model usage
PYTHONPATH=src python3 -m aegisagent connectors
PYTHONPATH=src python3 -m aegisagent connectors doctor
PYTHONPATH=src python3 -m aegisagent tasks --submit "draft a safe plan"
PYTHONPATH=src python3 -m aegisagent tasks --background "draft a safe plan"
PYTHONPATH=src python3 -m aegisagent automations
PYTHONPATH=src python3 -m aegisagent automations create daily-check --schedule "daily 09:00" --prompt "summarize workspace risks"
PYTHONPATH=src python3 -m aegisagent automations create weekday-check --schedule "weekdays 09:00" --prompt "summarize weekday risks"
PYTHONPATH=src python3 -m aegisagent automations create denver-check --schedule "weekdays 09:00 America/Denver" --prompt "summarize Denver weekday risks"
PYTHONPATH=src python3 -m aegisagent automations create holiday-aware-check --schedule "weekdays 09:00 America/Denver except=2026-12-25" --prompt "summarize weekday risks except holidays"
PYTHONPATH=src python3 -m aegisagent automations create month-end-check --schedule "monthly last 09:00" --prompt "summarize monthly state"
PYTHONPATH=src python3 -m aegisagent automations due
PYTHONPATH=src python3 -m aegisagent automations missed
PYTHONPATH=src python3 -m aegisagent automations replay-missed
PYTHONPATH=src python3 -m aegisagent automations tick
PYTHONPATH=src python3 -m aegisagent automations worker --max-ticks 5
PYTHONPATH=src python3 -m aegisagent automations logs <run-id>
PYTHONPATH=src python3 -m aegisagent automations service
PYTHONPATH=src python3 -m aegisagent automations service-status
PYTHONPATH=src python3 -m aegisagent automations trigger <automation-id>
PYTHONPATH=src python3 -m aegisagent improve
PYTHONPATH=src python3 -m aegisagent improve propose "policy denied a needed safe git read" --target policy --operation evaluate
PYTHONPATH=src python3 -m aegisagent improve candidate <proposal-id>
PYTHONPATH=src python3 -m aegisagent improve diff <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve verify <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve apply <candidate-id>
PYTHONPATH=src python3 -m aegisagent improve implement <proposal-id>
PYTHONPATH=src python3 -m aegisagent improve evidence <proposal-id> --files "src/aegisagent/core/policy.py,tests/test_policy.py" --validation "PYTHONPATH=src python3 -m unittest tests.test_policy -v" --result "passed"
PYTHONPATH=src python3 -m aegisagent improve complete <proposal-id>
PYTHONPATH=src python3 -m aegisagent agents
PYTHONPATH=src python3 -m aegisagent agents profiles
PYTHONPATH=src python3 -m aegisagent agents contracts
PYTHONPATH=src python3 -m aegisagent agents delegate "improve terminal orchestration"
PYTHONPATH=src python3 -m aegisagent subagents --delegate "improve terminal orchestration"
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --view setup --width 100 --height 32
PYTHONPATH=src python3 -m aegisagent tui --print --view tools --width 132 --height 38
cd web && npm run build
cd web && npm run smoke
PYTHONPATH=src python3 -m aegisagent audit verify
```

## Security Contract

AegisAgent fails closed for destructive commands and secret echo. Network, shell writes, external delivery, elevated actions, and unrecognized tool calls return `ask` unless explicitly approved. Audit payloads are redacted before persistence, and `audit verify` detects tampering through a chained hash over every receipt.

## Current Gap

This is still an early terminal-first foundation, not a complete Hermes-class agent. The next checkpoints are stronger setup readiness, governed live browser control, deeper memory governance, and broader model-backed multi-agent orchestration.
