# AegisAgent Operator Reference

This reference lists common terminal and TUI commands after AegisAgent is installed. Start with the README for install, first-run setup, update, and safety expectations.

## Core Lifecycle

```bash
aegis
aegis activation
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

## TUI Slash Commands

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
/memory list
/memory show <entry-id>
/memory delete <entry-id> | approve
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

## Model And Connector Metadata

```bash
aegis model providers
aegis model configure openai/gpt-5.5 --mode api_key --api-key-env OPENAI_API_KEY
aegis model doctor
aegis model usage
aegis connectors
aegis connectors configure slack --token-env SLACK_BOT_TOKEN --enable
aegis connectors doctor
```

## Tasks And Agents

```bash
aegis chat "summarize this workspace"
aegis tasks --submit "draft a safe plan"
aegis tasks --background "draft a safe plan"
aegis tasks --events <task-id>
aegis agents
aegis agents profiles
aegis agents contracts
aegis agents delegate "review the current plan"
aegis subagents --delegate "review the current plan"
```

## Memory Review

List/show/search/index are read-only. Add and delete require explicit approval.

```bash
aegis memory list
aegis memory list --kind user
aegis memory show <entry-id>
aegis memory --query <text>
aegis memory --index
aegis memory --kind user --title "<title>" --add "<body>" --approved
aegis memory delete <entry-id> --approved
```

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
