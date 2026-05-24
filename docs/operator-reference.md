# AegisAgent Operator Reference

This reference lists common terminal and TUI commands after AegisAgent is installed. Start with the README for the shortest install and first-run path.

## Terminal Install And Update

Install from GitHub on macOS or Linux:

```bash
/bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh)"
export PATH="$HOME/.local/bin:$PATH"
command -v aegis
aegis health
```

Choose one model route:

```bash
aegis model connect local
aegis model doctor
```

or:

```bash
export OPENAI_API_KEY="..."
aegis model connect openai
aegis model doctor
```

Update an installed checkout from GitHub:

```bash
aegis update --approved
aegis health
aegis audit verify
```

Use `aegis install` or `/install` to inspect or reinstall the terminal shim for
the current checkout. Use `aegis update` or `/update` without approval to preview the
exact `git pull --ff-only origin main` action before mutating the checkout.

## Core Lifecycle

```bash
aegis
aegis init
aegis tui
aegis activate
aegis activation
aegis commands
aegis commands setup
aegis commands --group Build --json
aegis setup next
aegis setup model
aegis setup --run-checks
aegis health
aegis audit verify
aegis dashboard
aegis capabilities
aegis capabilities --gaps
aegis update --approved
```

`aegisagent` is also installed by the Python package and routes to the same CLI.

## Aliases And Shortcuts

Implemented aliases map to existing terminal-only behavior. They do not start
the web gateway, launch a browser, deliver connector messages, or store raw
secrets.

```bash
aegis                       same terminal-first default as aegis tui in a TTY
aegis tui                   explicit TUI launch
aegis activate              launch TUI in a TTY, activation card outside a TTY
aegis activation            print activation/readiness card
aegisagent                  package-installed alias for the same CLI

aegis setup init            setup quickstart
aegis setup initialize      setup quickstart
aegis setup model-auth      model setup section
aegis setup 1..6            hidden compatibility aliases for model through memory
aegis setup check           metadata-only setup checks
aegis setup checks          metadata-only setup checks
aegis setup verify          metadata-only setup checks
aegis setup doctor          metadata-only setup checks
aegis setup connections     connector setup section
aegis setup skills          memory and skills setup section
aegis setup plugins         memory and skills setup section
aegis setup first-task      safe first terminal task guidance
aegis task list             singular alias for task queue list
aegis task submit <request> singular alias for task submit
aegis task status <id>      singular alias for tasks show
aegis task timeline <id>    singular alias for tasks events
aegis task recover          singular alias for tasks recover-stale
aegis models providers      alias for model providers
aegis model auth status     read-only model auth status
aegis model auth methods    read-only auth method inventory
aegis model auth doctor     metadata-only auth doctor checks
aegis memory search <query> alias for memory --query
aegis memory index          alias for memory --index
```

```text
/task                       exact root alias for /tasks
/model                      exact root alias for /model providers
/memory                     canonical memory index/search root
/menu                       grouped command lanes
/commands json              machine-readable terminal command catalog
/activate                   activation card alias
/q <request>                quick task submit
/setup continue             next setup step
/setup model-auth           model setup section
/setup check|checks|verify  setup run-checks
/setup doctor               setup run-checks
/setup connections          connector setup section
/setup skills|plugins       memory and skills setup section
/setup dismiss              hide first-launch setup wizard
/tasks background <req>     same as /tasks bg <req>
/tasks live <id>            same watch surface as /tasks watch <id>
/agents stream <task>       same as /agents live <task>
/improve handoff <id>       same as /improve implement <id>
/improve candidate-diff     same as /improve diff
/improve apply-candidate    same as /improve apply
/improve implemented        same as /improve complete
```

Old-agent idioms are accepted only where they preserve the same governed Aegis
behavior. Prefer the canonical command in runbooks.

Root shortcuts do not create singular subcommand families; use `/tasks watch`,
`/model doctor`, and `/memory add` for those workflows.

## TUI Slash Commands

```text
/commands
/commands json
/setup next
/setup model
/setup model-auth
/setup sandbox
/setup tools
/setup connectors
/setup connections
/setup memory
/setup skills
/setup plugins
/setup first-task
/setup run-checks
/setup check
/setup verify
/setup doctor
/setup init
/dashboard
/capabilities
/gaps
/tools
/audit
/connectors
/connectors doctor
/connectors draft <name> | <target> | <message>
/connectors send <name> | <target> | <message> | approve
/connectors outbox
/memory
/memory search <query>
/memory index
/memory list
/memory show <entry-id>
/memory delete <entry-id> | approve
/skills
/skills manifest <skill-name> | approve
/sessions search <query>
/tasks submit <request>
/tasks bg <request>
/tasks watch <task-id>
/agents
/agents delegate <task>
/agents delegate <task> | use-artifact <artifact-id> | approve
/agents bg <task>
/agents monitor <job-id>
/agents status <root-id>
/agents synthesis <root-id>
/agents graph <root-id>
/subagents bg <task>
/subagents monitor <job-id>
/subagents status <root-id>
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

## Model And Connector Metadata

```bash
aegis model providers
aegis model connect local
export OPENAI_API_KEY="..."
aegis model connect openai
aegis model doctor
```

Advanced and compatibility provider commands:

```bash
aegis model connect openai --model gpt-5.5 --api-key-env OPENAI_API_KEY
export OPENROUTER_API_KEY="..."
aegis model connect openrouter --base-url https://openrouter.ai/api/v1 --model openai/gpt-4o-mini
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model configure openai/gpt-5.5 --mode subscription_cli
aegis model usage
aegis model auth status
aegis model auth methods
aegis model auth doctor
aegis models providers
aegis models doctor
aegis connectors
aegis connectors configure webhook --url-env AEGIS_WEBHOOK_URL --enable
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
aegis connectors send webhook --target "ops-status" --message "Status update" --approved
aegis connectors draft slack --target "#ops" --message "Status update"
aegis connectors send slack --target "#ops" --message "Status update" --approved
aegis connectors outbox
```

Connector `send` performs live network delivery only for the `webhook` connector
after explicit approval and a configured URL environment handle. Slack, Teams,
and Open WebUI sends remain approval-bound outbox packets only; they do not
contact those services.

## Tasks And Agents

```bash
aegis chat "summarize this workspace"
aegis tasks --submit "draft a safe plan"
aegis tasks --background "draft a safe plan"
aegis tasks --events <task-id>
aegis task submit "draft a safe plan"
aegis task status <task-id>
aegis task timeline <task-id>
aegis agents
aegis agents profiles
aegis agents contracts
aegis agents delegate "review the current plan"
aegis agents delegate "review the current plan" --depth 2
aegis agents delegate "continue from artifact" --use-artifact <artifact-id> --approved
aegis agents bg "review the current plan"
aegis agents bg "continue from artifact" --depth 2 --use-artifact <artifact-id> --approved
aegis agents jobs
aegis agents monitor <job-id>
aegis agents status <root-id>
aegis agents cancel <job-id>
aegis agents recover
aegis agents artifacts
aegis agents artifacts show <artifact-id>
aegis agents artifacts search "final synthesis"
aegis agents synthesis <root-id>
aegis agents graph <root-id>
aegis subagents --delegate "review the current plan"
aegis subagents --delegate "review the current plan" --depth 2
aegis subagents --delegate "continue from artifact" --use-artifact <artifact-id> --approved
aegis subagents --background "continue from artifact" --depth 2 --use-artifact <artifact-id> --approved
aegis subagents --job <job-id>
aegis subagents --status <root-id>
aegis subagents --synthesis <root-id>
aegis subagents --artifact-graph <root-id>
```

`agents monitor <job-id>` is the terminal-readable background-job view. It
shows the job record, root run status when available, the recent timeline, and
next commands. Add `--json` when a script needs the raw job record.

Completed delegations create a coordinator `final_synthesis` artifact that can
be inspected through the same read-only artifact list/show/search commands or
through the root-scoped synthesis and graph commands.

Agent delegation is explicit and bounded. By default each run is a flat
coordinator plus planner, researcher, implementer, and reviewer workers. Depth 2
is opt-in: `--depth 2` or `| depth 2` nests the reviewer under the implementer.
It is not arbitrary recursive spawning, autonomous fan-out, or a global worker
pool.

```text
/agents delegate review the current plan | depth 2
/agents live review the current plan | depth 2
/agents bg continue from artifact | depth 2 | use-artifact <artifact-id> | approve
/subagents improve terminal orchestration | depth 2
```

`aegis agents contracts` shows each worker role contract and structured budget
policy. JSON output exposes the budget version, allowed tool groups, denied tool
groups, limits, approval escalation, and receipt fields. These budgets narrow
role intent and audit expectations, with artifact cap and safety checks recorded
fail-closed; file, git, browser, connector, memory, and external-state mutations
still require the existing typed approval path.

Background artifact reuse persists approved artifact ids in the job record and
revalidates them when the job runs. It does not permit unapproved detached-job
reuse, unsandboxed tools, connector delivery, browser launch, or raw artifact-body
model reuse.

## Memory Review

List/show/search/index are read-only. Add and delete require explicit approval.

```bash
aegis memory list
aegis memory list --kind user
aegis memory show <entry-id>
aegis memory --query <text>
aegis memory --index
aegis memory search <text>
aegis memory index
aegis memory --kind user --title "<title>" --add "<body>" --approved
aegis memory delete <entry-id> --approved
```

## Skills And Trust Metadata

Skill handling is passive discovery only. Aegis reads `SKILL.md` files under the workspace `skills/` directory and `~/.aegisagent/skills` as text, redacts body-derived metadata, computes stable hashes, optionally checks `aegis-skill-trust.json` manifests with `algorithm: sha256-bundle-v1`, `bundle_sha256`, and optional `signature`, and reports trust/provenance posture without executing skills.

```bash
aegis skills
aegis skills --limit 10
aegis skills manifest <skill-name>
aegis skills manifest <skill-name> --approved
```

```text
/skills
/skills manifest <skill-name> | approve
```

The output includes `trusted`, `review`, and `quarantined` counts plus each visible skill's redacted `name`, `description`, `findings`, `skill_id`, content hashes, manifest status, signature status, and passive safety flags. Quarantine is marker-, path-safety-, and manifest-integrity-based. Missing manifests are acceptable; invalid or mismatched manifests quarantine the skill. Signatures are surfaced as declared/unverified until trusted-key signature verification lands. Policy-integrated skill execution approvals remain future work.

`aegis skills manifest <skill-name>` previews deterministic checksum-only manifest JSON. Add `--approved` to write `aegis-skill-trust.json`; this does not sign or execute skills.

## Governed Workspace Tools

```bash
aegis fetch https://example.com --approved
aegis browser open https://example.com --approved
aegis git status
aegis git diff README.md
aegis git stage README.md --approved
aegis git commit --message "Describe staged changes" --approved
aegis git branch create codex/example --approved
aegis git remote fetch origin main --approved
aegis git remote pull origin main --approved
aegis git remote push origin main --approved
aegis edit replace README.md --old "old text" --new "new text" --approved
```

## Automations And Self-Improvement

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

## Completion

```bash
aegis completion zsh
aegis completion bash
aegis completion fish
```
