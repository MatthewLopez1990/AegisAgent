from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aegisagent import __version__
from aegisagent.config import ensure_runtime, runtime_paths
from aegisagent.core.activation import format_terminal_activation, terminal_activation_payload
from aegisagent.core.agent import AgentRuntime
from aegisagent.core.automation import AutomationRegistry, automation_summary, format_automation, format_automations, format_due_automations, format_due_run, format_missed_automations, format_missed_replay, format_service_status, format_service_wrapper, format_worker_logs, format_worker_run
from aegisagent.core.browser_sessions import BrowserSessionStore, browser_summary
from aegisagent.core.capabilities import capability_map, format_capabilities
from aegisagent.core.command_names import terminal_command_name
from aegisagent.core.completion import SUPPORTED_SHELLS, build_completion_script
from aegisagent.core.connectors import DEFAULT_CONNECTORS, ConnectorStore
from aegisagent.core.dashboard import dashboard_payload, format_dashboard
from aegisagent.core.executor import GovernedExecutor
from aegisagent.core.improvement import ImprovementStore, format_candidate, format_candidate_diff_review, format_improvement, format_improvements, format_verification_run, improvement_summary
from aegisagent.core.lifecycle import format_install_status, format_update_status, install_status_payload, install_terminal_shim, update_from_github
from aegisagent.core.memory import MemoryStore, memory_files
from aegisagent.core.provider_config import ProviderStore, ProviderUsageStore, format_provider_connect
from aegisagent.core.setup_flow import (
    SETUP_SECTION_CHOICES,
    SETUP_SECTIONS,
    SetupGuide,
    format_setup_first_task,
    format_setup_next,
    format_setup_quickstart,
    format_setup_section,
    normalize_setup_section,
)
from aegisagent.core.sessions import SessionStore
from aegisagent.core.skills import SkillLoader, skill_audit_payload
from aegisagent.core.subagents import (
    LocalSubagentOrchestrator,
    SubagentQueue,
    SubagentStore,
    agent_contracts_payload,
    agent_status,
    format_agent_contracts,
    format_agent_profiles,
    format_agent_status,
    format_artifact,
    format_artifact_graph,
    format_artifact_search,
    format_artifacts,
    format_background_job,
    format_background_jobs,
    format_event_line,
    format_synthesis,
)
from aegisagent.core.tasks import TaskRunner, format_task_outputs, format_task_worker_logs
from aegisagent.core.tools import ToolRegistry, enabled_counts
from aegisagent.core.web_tools import WebToolRunner
from aegisagent.core.workspace_tools import WorkspaceToolRunner
from aegisagent.gateway import run_gateway
from aegisagent.security.audit import AuditLog
from aegisagent.security.policy import decide_tool
from aegisagent.security.sandbox import detect_sandbox
from aegisagent.tui.interactive import command_catalog_payload, render_command_lanes
from aegisagent.tui.renderer import TuiState, render
from aegisagent.tui.textual_app import run_textual_app


def _add_model_arguments(model_parser: argparse.ArgumentParser) -> None:
    model_parser.add_argument("model_command", nargs="?", default="providers", choices=["providers", "doctor", "configure", "connect", "usage", "auth"], help="Provider command to run.")
    model_parser.add_argument("name", nargs="?", help="Provider name for configure/connect, or auth status/methods/doctor.")
    model_parser.add_argument("--mode", choices=["local", "api_key", "subscription_cli", "not_configured"], default="api_key")
    model_parser.add_argument("--api-key-env", default="", help="Environment variable name that will hold the provider key; the value is never read into config.")
    model_parser.add_argument("--base-url", default="", help="Optional provider base URL metadata; no network call is made.")
    model_parser.add_argument("--model", default="", help="Model name for `model connect openai`. Defaults to gpt-5.5.")
    model_parser.add_argument("--inactive", action="store_true", help="Save the route without making it active.")
    model_parser.add_argument("--limit", type=int, default=20, help="Limit recent model usage rows.")


def build_parser() -> argparse.ArgumentParser:
    prog = "aegis"
    if sys.argv:
        invoked = Path(sys.argv[0]).name
        if invoked in {"aegis", "aegisagent"}:
            prog = invoked
    env_command = os.environ.get("AEGIS_COMMAND_NAME", "").strip()
    if env_command:
        prog = env_command
    parser = argparse.ArgumentParser(prog=prog, description="Security-first autonomous agent console.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON where supported.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Compatibility alias for terminal setup quickstart.")
    sub.add_parser("activate", help="Launch the terminal-first AegisAgent TUI, or print activation instructions outside a TTY.")
    sub.add_parser("activation", help="Print terminal activation and browser-off readiness details.")
    completion = sub.add_parser("completion", help="Emit dependency-free shell completion for the terminal command.")
    completion.add_argument("shell", choices=SUPPORTED_SHELLS, help="Shell completion format to emit.")
    completion.add_argument("--program", default="", help="Installed command name. Defaults to the active terminal command.")

    setup = sub.add_parser("setup", help="Create local runtime files and show secure setup flow.")
    setup.add_argument("section", nargs="?", choices=SETUP_SECTION_CHOICES, help="Show one setup section or the next setup action.")
    setup.add_argument("--init", action="store_true", help="Show the terminal setup quickstart and initialize local runtime metadata.")
    setup.add_argument("--quick", action="store_true", help="Print the compact setup quickstart.")
    setup.add_argument("--full", action="store_true", help="Emit the full setup quickstart payload as JSON.")
    setup.add_argument("--run-checks", action="store_true")
    capabilities = sub.add_parser("capabilities", help="Show terminal-visible Hermes-class capability parity map.")
    capabilities.add_argument("--gaps", action="store_true", help="Show only partial, metadata-ready, and planned capabilities.")
    commands = sub.add_parser("commands", help="Show terminal TUI slash command lanes without launching a browser.")
    commands.add_argument("query", nargs="?", default="", help="Optional command, group, or detail filter.")
    commands.add_argument("--group", default="", help="Only show one command group, for example Build or Setup.")
    commands.add_argument("--json", action="store_true", help="Emit the command catalog as JSON.")
    sub.add_parser("dashboard", help="Show a terminal-first operator dashboard without starting web or browser surfaces.")
    install = sub.add_parser("install", help="Show or install macOS/Linux terminal command shims.")
    install.add_argument("install_command", nargs="?", default="status", choices=["status", "shim"], help="Preview install status or write a terminal shim.")
    install.add_argument("--bin-dir", default="", help="Directory for the terminal shim. Defaults to ~/.local/bin.")
    install.add_argument("--name", default="aegis", help="Command name to install. Defaults to aegis.")
    install.add_argument("--approved", action="store_true", help="Write the terminal shim after explicit operator approval.")
    update = sub.add_parser("update", help="Pull the latest AegisAgent code from GitHub into this checkout.")
    update.add_argument("--remote", default="origin", help="Git remote to pull from. Defaults to origin.")
    update.add_argument("--branch", default="main", help="Git branch to pull. Defaults to main.")
    update.add_argument("--approved", action="store_true", help="Run git pull --ff-only after explicit operator approval.")
    sub.add_parser("health", help="Show runtime health.")
    audit = sub.add_parser("audit", help="Audit log commands.")
    audit_sub = audit.add_subparsers(dest="audit_command")
    audit_sub.add_parser("verify", help="Verify append-only audit hash chain.")

    tools = sub.add_parser("tools", help="List tools or inspect policy.")
    tools.add_argument("--matrix", action="store_true")
    tools.add_argument("--evaluate")
    tools.add_argument("--action", default="")
    tools.add_argument("--approved", action="store_true")

    skills = sub.add_parser("skills", help="Discover workspace and user skills with passive trust metadata.")
    skills.add_argument("skills_command", nargs="?", choices=["manifest"], help="Optional skill operation.")
    skills.add_argument("skill_name", nargs="?", help="Skill folder name for manifest authoring.")
    skills.add_argument("--limit", type=int, default=0, help="Limit returned skill records. Defaults to all.")
    skills.add_argument("--approved", action="store_true", help="Write a skill manifest after explicit operator approval.")
    memory = sub.add_parser("memory", help="Index or search memory.")
    memory.add_argument("--index", action="store_true")
    memory.add_argument("--query", default="")
    memory.add_argument("--add", default="", help="Append an approval-gated note to curated memory.")
    memory.add_argument("--title", default="", help="Title for --add memory notes.")
    memory.add_argument("--kind", choices=["workspace", "user"], default="", help="Curated memory file to update or list.")
    memory.add_argument("--approved", action="store_true", help="Append the memory note after explicit operator approval.")
    memory.add_argument("--limit", type=int, default=20, help="Limit memory list or search results.")
    memory.add_argument("memory_command", nargs="?", choices=["list", "show", "delete", "search", "index"], help="Review, search, index, or delete curated memory entries.")
    memory.add_argument("memory_args", nargs="*", help="Memory entry id, for example user:abcdef123456.")

    sessions = sub.add_parser("sessions", help="Manage terminal sessions.")
    sessions.add_argument("--create", metavar="TITLE", help="Create a named session.")
    sessions.add_argument("--show", metavar="SESSION_ID", help="Show a session transcript.")
    sessions.add_argument("--append", nargs=2, metavar=("SESSION_ID", "TEXT"), help="Append a user message to a session.")
    sessions.add_argument("--query", metavar="TEXT", help="Search redacted session transcripts.")
    sessions.add_argument("--limit", type=int, default=20)

    run = sub.add_parser("run", help="Run a governed local shell command.")
    run.add_argument("shell_command", help="Command to evaluate and execute when policy allows.")
    run.add_argument("--approved", action="store_true", help="Allow policy-ask commands when they are not denied.")
    run.add_argument("--timeout", type=int, default=20)

    verify = sub.add_parser("verify", help="Run an allowlisted typed verification command without shell parsing.")
    verify.add_argument("verify_command", nargs=argparse.REMAINDER, help="Optional command, for example python3 -m unittest discover -s tests -v.")
    verify.add_argument("--timeout", type=int, default=60)

    fetch = sub.add_parser("fetch", help="Fetch an http(s) URL through an approval-gated typed network tool.")
    fetch.add_argument("url", help="Explicit http(s) URL to fetch.")
    fetch.add_argument("--approved", action="store_true", help="Perform the network fetch after explicit operator approval.")
    fetch.add_argument("--timeout", type=float, default=10.0)
    fetch.add_argument("--max-bytes", type=int, default=20000)

    edit = sub.add_parser("edit", help="Run approval-gated typed workspace edits.")
    edit.add_argument("edit_command", nargs="?", default="replace", choices=["replace"], help="Edit operation to run.")
    edit.add_argument("path", nargs="?", help="Workspace file path.")
    edit.add_argument("--old", default="", help="Exact old text to replace.")
    edit.add_argument("--new", default="", help="Replacement text.")
    edit.add_argument("--approved", action="store_true", help="Perform the mutation after explicit operator approval.")

    git = sub.add_parser("git", help="Run typed git workspace operations.")
    git.add_argument("git_command", nargs="?", default="status", choices=["status", "diff", "stage", "commit", "branch", "remote"], help="Git operation to run.")
    git.add_argument("git_args", nargs="*", help="Path, branch, or message arguments for the selected git operation.")
    git.add_argument("--message", "-m", default="", help="Commit message for typed git commit.")
    git.add_argument("--approved", action="store_true", help="Perform an approval-gated git mutation.")

    chat = sub.add_parser("chat", help="Run one terminal agent turn without launching curses.")
    chat.add_argument("prompt", help="Prompt to send to the local terminal agent runtime.")
    chat.add_argument("--session", default="main", help="Session id or main.")
    chat.add_argument("--json", action="store_true", help="Emit the turn result as JSON.")

    model = sub.add_parser("model", help="Inspect or configure terminal model provider routes.")
    _add_model_arguments(model)
    models = sub.add_parser("models", help="Compatibility alias for model provider routes.")
    _add_model_arguments(models)

    connectors = sub.add_parser("connectors", help="Inspect or configure connector readiness metadata.")
    connectors.add_argument("connector_command", nargs="?", default="list", choices=["list", "doctor", "configure", "draft", "send", "outbox"], help="Connector command to run.")
    connectors.add_argument("name", nargs="?", choices=tuple(DEFAULT_CONNECTORS), help="Connector name for configure.")
    connectors.add_argument("--token-env", default="", help="Environment variable name for a token handle; raw values are never stored.")
    connectors.add_argument("--url-env", default="", help="Environment variable name for a URL handle; raw values are never stored.")
    connectors.add_argument("--enable", action="store_true", help="Mark the connector metadata enabled; sends still require future explicit approval.")
    connectors.add_argument("--target", default="", help="Message target for draft/send, for example #ops or a webhook label.")
    connectors.add_argument("--message", default="", help="Message body for draft/send. Raw secrets are redacted before persistence.")
    connectors.add_argument("--approved", action="store_true", help="Record an approved outbound packet when the connector is metadata-ready.")
    connectors.add_argument("--limit", type=int, default=20, help="Limit outbox records.")

    browser = sub.add_parser("browser", help="Manage explicit browser session records without auto-launching a browser.")
    browser.add_argument("browser_command", nargs="?", default="sessions", choices=["sessions", "open", "screenshot", "show"], help="Browser session command.")
    browser.add_argument("browser_args", nargs="*", help="URL, session id, or screenshot path for the selected command.")
    browser.add_argument("--title", default="", help="Optional title for browser open records.")
    browser.add_argument("--note", default="", help="Optional note for screenshot receipts.")
    browser.add_argument("--approved", action="store_true", help="Create the browser session or screenshot receipt after explicit approval.")
    browser.add_argument("--limit", type=int, default=20)

    tasks = sub.add_parser("tasks", help="Manage governed terminal tasks.")
    tasks.add_argument("--submit", metavar="PROMPT", help="Queue a governed task without running it immediately.")
    tasks.add_argument("--background", metavar="PROMPT", help="Start a governed task in a detached worker process.")
    tasks.add_argument("--start", metavar="TASK_ID", help="Start one queued task in a detached worker process.")
    tasks.add_argument("--run", metavar="TASK_ID", help="Run one queued task.")
    tasks.add_argument("--show", metavar="TASK_ID", help="Show one task.")
    tasks.add_argument("--events", metavar="TASK_ID", help="Show task progress events.")
    tasks.add_argument("--output", metavar="TASK_ID", help="Show recorded task assistant/tool output.")
    tasks.add_argument("--logs", metavar="TASK_ID", help="Show detached worker stdout/stderr logs.")
    tasks.add_argument("--cancel", metavar="TASK_ID", help="Cancel one queued or running task.")
    tasks.add_argument("--recover-stale", action="store_true", help="Mark running detached tasks failed when their worker pid is gone.")
    tasks.add_argument("--reason", default="Cancelled by operator.", help="Cancellation reason.")
    tasks.add_argument("--limit", type=int, default=20)
    task = sub.add_parser("task", help="Compatibility alias for governed terminal tasks.")
    task.add_argument("task_command", nargs="?", default="list", choices=["list", "submit", "bg", "background", "start", "run", "show", "status", "events", "timeline", "output", "outputs", "log", "logs", "cancel", "recover", "recover-stale"], help="Task alias command.")
    task.add_argument("task_args", nargs="*", help="Prompt text or task id for the selected task command.")
    task.add_argument("--reason", default="Cancelled by operator.", help="Cancellation reason.")
    task.add_argument("--limit", type=int, default=20)

    automations = sub.add_parser("automations", help="Manage durable gated automation schedule records.")
    automations.add_argument("automation_command", nargs="?", default="list", choices=["list", "create", "show", "trigger", "run", "due", "missed", "replay-missed", "replay", "tick", "run-due", "worker", "daemon", "logs", "worker-log", "service", "service-status", "status", "pause", "resume", "delete"], help="Automation command to run.")
    automations.add_argument("automation_args", nargs="*", help="Automation name or id.")
    automations.add_argument("--schedule", default="", help="Schedule label, for example daily 09:00 or weekly Monday 14:00.")
    automations.add_argument("--prompt", default="", help="Prompt to run when a future approved scheduler is added.")
    automations.add_argument("--background", action="store_true", help="Start the triggered governed task in a detached worker.")
    automations.add_argument("--now", default="", help="UTC timestamp for deterministic due checks, for example 2026-05-23T10:00:00Z.")
    automations.add_argument("--interval", type=float, default=60.0, help="Worker interval in seconds.")
    automations.add_argument("--max-ticks", type=int, default=1, help="Worker tick count. Use 0 to run until interrupted.")
    automations.add_argument("--limit", type=int, default=20)

    improve = sub.add_parser("improve", help="Manage governed self-improvement proposals without auto-editing.")
    improve.add_argument("improve_command", nargs="?", default="status", choices=["status", "list", "propose", "show", "review", "approve", "reject", "implement", "handoff", "candidate", "candidate-show", "diff", "candidate-diff", "verify", "apply", "apply-candidate", "evidence", "complete", "implemented"], help="Self-improvement command to run.")
    improve.add_argument("improve_args", nargs="*", help="Failure summary or proposal id.")
    improve.add_argument("--target", default="runtime", help="Target subsystem for a proposal.")
    improve.add_argument("--operation", default="unknown", help="Operation or path being repaired.")
    improve.add_argument("--rationale", default="", help="Review rationale for approve/reject/review.")
    improve.add_argument("--background", action="store_true", help="Start the implementation handoff task in a detached worker.")
    improve.add_argument("--task", default="", help="Implementation task id for evidence records.")
    improve.add_argument("--files", default="", help="Comma-separated changed files for implementation evidence.")
    improve.add_argument("--validation", default="", help="Verification command used for implementation evidence.")
    improve.add_argument("--result", default="", help="Verification result summary used for implementation evidence.")
    improve.add_argument("--command-index", type=int, default=0, help="Candidate verification command index to run.")
    improve.add_argument("--timeout", type=int, default=60, help="Candidate verification timeout in seconds.")
    improve.add_argument("--limit", type=int, default=20)

    subagents = sub.add_parser("subagents", help="Show subagent constraints.")
    subagents.add_argument("--spawn")
    subagents.add_argument("--delegate", metavar="TASK", help="Run a bounded local subagent delegation.")
    subagents.add_argument("--stream", metavar="TASK", help="Run delegation and print timeline events as they happen.")
    subagents.add_argument("--background", metavar="TASK", help="Start a background subagent job and return immediately.")
    subagents.add_argument("--job", metavar="JOB_ID", help="Show one background subagent job.")
    subagents.add_argument("--jobs", action="store_true", help="List background subagent jobs.")
    subagents.add_argument("--cancel", metavar="JOB_ID", help="Cancel a queued or running background subagent job.")
    subagents.add_argument("--recover-stale", action="store_true", help="Mark running background subagent jobs failed when their worker pid is gone.")
    subagents.add_argument("--run-job", metavar="JOB_ID", help=argparse.SUPPRESS)
    subagents.add_argument("--stop", metavar="SUBAGENT_ID", help="Cascade stop a persisted subagent tree.")
    subagents.add_argument("--events", metavar="ROOT_ID", help="Show persisted subagent timeline events for a root id.")
    subagents.add_argument("--artifacts", action="store_true", help="List durable subagent role artifacts.")
    subagents.add_argument("--artifact", metavar="ARTIFACT_ID", help="Show one durable subagent role artifact.")
    subagents.add_argument("--artifact-search", metavar="QUERY", help="Search durable subagent role artifacts.")
    subagents.add_argument("--synthesis", metavar="ROOT_ID", help="Show coordinator final synthesis for a root delegation id.")
    subagents.add_argument("--artifact-graph", metavar="ROOT_ID", help="Show coordinator artifact graph for a root delegation id.")
    subagents.add_argument("--use-artifact", action="append", default=[], help="Approved prior artifact id to reuse as starting context for --delegate, --stream, or --background.")
    subagents.add_argument("--approved", action="store_true", help="Approve cross-delegation artifact reuse.")
    subagents.add_argument("--depth", type=int, default=1, choices=(1, 2), help="Requested delegation topology depth for --delegate, --stream, or --background.")

    agents = sub.add_parser("agents", help="Hermes-style agent surface backed by governed local subagents.")
    agents.add_argument("agent_command", nargs="?", default="status", choices=["status", "profiles", "contracts", "delegate", "stream", "live", "background", "bg", "jobs", "job", "monitor", "cancel", "recover", "artifacts", "artifact", "search-artifacts", "synthesis", "graph"], help="Agent command to run.")
    agents.add_argument("agent_args", nargs="*", help="Task text, job id, or root id for the selected agent command.")
    agents.add_argument("--use-artifact", action="append", default=[], help="Approved prior artifact id to reuse as starting context for delegate, stream, or background.")
    agents.add_argument("--approved", action="store_true", help="Approve cross-delegation artifact reuse.")
    agents.add_argument("--depth", type=int, default=1, choices=(1, 2), help="Requested delegation topology depth for delegate, stream, or background.")
    agents.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON for status, profiles, and artifact browsing.")

    tui = sub.add_parser("tui", help="Launch governed terminal TUI. This is the primary activation path.")
    tui.add_argument("--view", choices=["command", "setup", "tools", "activation", "help"], default="command")
    tui.add_argument("--print", action="store_true", help="Print a static terminal frame instead of launching the interactive TUI.")
    tui.add_argument("--classic", action="store_true", help="Use the static fallback instead of the curses terminal UI.")
    tui.add_argument("--width", type=int, default=None)
    tui.add_argument("--height", type=int, default=None)

    gateway = sub.add_parser(
        "gateway",
        help="Advanced: start the optional local gateway after approval; does not open a browser.",
        description="Advanced: start the optional local gateway after approval; does not open a browser.",
    )
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8787)
    gateway.add_argument("--approved", action="store_true", help="Allow the optional local gateway server to start.")

    web = sub.add_parser("web", help="Print optional web console instructions. Serving requires --serve --approved.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8787)
    web.add_argument("--serve", action="store_true", help="Start the optional local gateway after approval.")
    web.add_argument("--approved", action="store_true", help="Allow the optional gateway server to start.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "completion":
        program = args.program.strip() or terminal_command_name()
        try:
            script = build_completion_script(build_parser(), args.shell, program=program)
        except ValueError as exc:
            parser.error(str(exc))
        print(script, end="")
        return 0

    paths = runtime_paths(args.workspace)
    ensure_runtime(paths)
    audit = AuditLog(paths)

    if not args.command:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return run_textual_app("command", paths=paths, classic=False)
        payload = terminal_activation_payload(paths)
        print(json.dumps(payload, indent=2) if args.json else format_terminal_activation(payload))
        return 0

    if args.command == "activate":
        if sys.stdin.isatty() and sys.stdout.isatty():
            return run_textual_app("command", paths=paths, classic=False)
        payload = terminal_activation_payload(paths)
        print(json.dumps(payload, indent=2) if args.json else format_terminal_activation(payload))
        return 0

    if args.command == "activation":
        payload = terminal_activation_payload(paths)
        print(json.dumps(payload, indent=2) if args.json else format_terminal_activation(payload))
        return 0

    if args.command == "init":
        setup_guide = SetupGuide(paths)
        print(json.dumps(setup_guide.quickstart(), indent=2) if args.json else format_setup_quickstart(setup_guide.quickstart()))
        return 0

    if args.command == "setup":
        setup_guide = SetupGuide(paths)
        setup_section = normalize_setup_section(args.section)
        if setup_section == "next":
            print(json.dumps(setup_guide.next_payload(), indent=2) if args.json else format_setup_next(setup_guide.priority()))
        elif args.run_checks or setup_section == "run-checks" or (args.json and not setup_section and not args.full and not args.quick and not args.init):
            print(json.dumps(setup_guide.run_checks(), indent=2))
        elif setup_section == "first-task":
            payload = setup_guide.first_task_payload()
            print(json.dumps(payload, indent=2) if args.json else format_setup_first_task(payload))
        elif setup_section:
            if setup_section == "quickstart" or args.init:
                print(json.dumps(setup_guide.quickstart(), indent=2) if args.full or args.json else format_setup_quickstart(setup_guide.quickstart()))
            else:
                print(format_setup_section(setup_guide.section(setup_section)))
        elif args.full:
            print(json.dumps(setup_guide.quickstart(), indent=2))
        elif args.quick or args.init:
            print(format_setup_quickstart(setup_guide.quickstart()))
        else:
            print(format_setup_quickstart(setup_guide.quickstart()))
        return 0

    if args.command == "capabilities":
        payload = capability_map(paths)
        if args.json:
            json_payload = {**payload, "title": "AEGIS CAPABILITY GAPS", "capabilities": payload["gaps"]} if args.gaps else payload
            print(json.dumps(json_payload, indent=2))
        else:
            print(format_capabilities(payload, gaps_only=args.gaps))
        return 0

    if args.command == "commands":
        payload = command_catalog_payload(paths, prefix=args.query, group=args.group)
        print(json.dumps(payload, indent=2) if args.json else render_command_lanes(payload))
        return 0

    if args.command == "dashboard":
        payload = dashboard_payload(paths)
        print(json.dumps(payload, indent=2) if args.json else format_dashboard(payload))
        return 0

    if args.command == "install":
        if args.install_command == "status":
            payload = install_status_payload(paths, bin_dir=args.bin_dir, name=args.name)
            print(json.dumps(payload, indent=2) if args.json else format_install_status(payload))
            return 0
        result = install_terminal_shim(paths, bin_dir=args.bin_dir, name=args.name, approved=args.approved)
        audit.append(
            "lifecycle.install",
            {
                "status": result.status,
                "metadata": result.metadata,
                "external_action_started": False,
                "browser_auto_launch": False,
            },
        )
        print(result.content if args.json else format_install_status(json.loads(result.content)))
        return 0 if result.status == "ok" else 1

    if args.command == "update":
        result = update_from_github(paths, remote=args.remote, branch=args.branch, approved=args.approved)
        audit.append(
            "lifecycle.update",
            {
                "status": result.status,
                "metadata": result.metadata,
                "external_action_started": result.metadata.get("external_action_started", False),
                "browser_auto_launch": False,
            },
        )
        print(result.content if args.json else format_update_status(result))
        return 0 if result.status == "ok" else 1

    if args.command == "health":
        result = {
            "ok": True,
            "version": __version__,
            "workspace": str(paths.workspace),
            "audit_chain_ok": audit.verify()["ok"],
            "sandbox": detect_sandbox().to_dict(),
            "tools": enabled_counts(),
            "memory_files": [str(path) for path in memory_files(paths)],
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "audit":
        if args.audit_command == "verify":
            print(json.dumps(audit.verify(), indent=2))
            return 0 if audit.verify()["ok"] else 1
        parser.error("audit requires a subcommand")

    if args.command == "tools":
        registry = ToolRegistry()
        if args.evaluate:
            result = registry.evaluate(args.evaluate, args.action, approved=args.approved)
            audit.append("tool.evaluate", result)
            print(json.dumps(result, indent=2))
            return 0 if result["action"] != "deny" else 1
        if args.matrix and not args.json:
            print(render(TuiState(view="tools")))
        else:
            print(json.dumps(registry.list(), indent=2))
        return 0

    if args.command == "skills":
        loader = SkillLoader([paths.skills_dir, Path.home() / ".aegisagent" / "skills"])
        if args.skills_command == "manifest":
            if not args.skill_name:
                parser.error("skills manifest requires a skill name")
            result = loader.author_manifest(args.skill_name, approved=args.approved)
            audit.append(
                "skills.manifest",
                {
                    "status": result["status"],
                    "skill_name": result["skill_name"],
                    "path": result["path"],
                    "approved": result["approved"],
                    "force": result["force"],
                    "skill_id": result["skill_id"],
                    "source_scope": result["source_scope"],
                    "relative_path": result["relative_path"],
                    "bundle_sha256": result["bundle_sha256"],
                    "manifest_sha256": result.get("manifest_sha256", ""),
                    "previous_manifest_sha256": result.get("previous_manifest_sha256", ""),
                    "manifest_write_performed": result["manifest_write_performed"],
                    "workspace_mutation_performed": result["workspace_mutation_performed"],
                    "host_filesystem_mutation_performed": result["host_filesystem_mutation_performed"],
                    "external_action_started": result["external_action_started"],
                    "browser_auto_launch": result["browser_auto_launch"],
                    "execution_performed": result["execution_performed"],
                    "raw_secret_values_included": result["raw_secret_values_included"],
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] in {"ok", "needs_approval", "already_current"} else 1
        summary = loader.trust_summary(limit=args.limit or None)
        audit_summary = summary if not args.limit else loader.trust_summary()
        audit.append("skills.discover", skill_audit_payload(audit_summary))
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "memory":
        store = MemoryStore(paths)
        if args.add:
            result = store.add_curated_note(args.kind or "workspace", args.title, args.add, approved=args.approved)
            audit.append(
                "memory.note.add",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.memory_command == "list":
            result = store.list_curated_entries(kind=args.kind, limit=args.limit)
            audit.append(
                "memory.note.list",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.memory_command == "show":
            if not args.memory_args:
                parser.error("memory show requires an entry id, for example user:abcdef123456")
            result = store.show_curated_entry(args.memory_args[0])
            audit.append(
                "memory.note.show",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "entry": {key: value for key, value in result.get("entry", {}).items() if key != "body"},
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.memory_command == "delete":
            if not args.memory_args:
                parser.error("memory delete requires an entry id, for example user:abcdef123456")
            result = store.delete_curated_entry(args.memory_args[0], approved=args.approved)
            audit.append(
                "memory.note.delete",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.index or args.memory_command == "index":
            print(json.dumps({"indexed": store.index_curated_files()}, indent=2))
        elif args.memory_command == "search":
            query = " ".join(args.memory_args).strip() or args.query
            if not query:
                parser.error("memory search requires a query")
            print(json.dumps(store.search(query, limit=args.limit), indent=2))
        else:
            query = args.query or "AegisAgent"
            print(json.dumps(store.search(query, limit=args.limit), indent=2))
        return 0

    if args.command == "sessions":
        sessions = SessionStore(paths)
        if args.create:
            session = sessions.create(args.create)
            audit.append("session.created", {"session_id": session.id, "title": session.title})
            print(json.dumps(session.to_dict(), indent=2))
        elif args.show:
            print(json.dumps({"session_id": args.show, "messages": sessions.transcript(args.show, limit=args.limit)}, indent=2))
        elif args.append:
            session = sessions.append(args.append[0], "user", args.append[1], metadata={"source": "cli"})
            audit.append("session.message_appended", {"session_id": session.id, "role": "user"})
            print(json.dumps({"session_id": session.id, "message_count": len(session.messages)}, indent=2))
        elif args.query:
            results = sessions.search(args.query, limit=args.limit)
            audit.append("session.search", {"query": args.query, "result_count": len(results), "limit": args.limit})
            print(json.dumps({"query": args.query, "results": results}, indent=2))
        else:
            print(json.dumps({"sessions_dir": str(paths.sessions_dir), "sessions": sessions.list(limit=args.limit)}, indent=2))
        return 0

    if args.command == "run":
        result = GovernedExecutor(paths).run_shell(args.shell_command, approved=args.approved, timeout=args.timeout)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.executed and result.returncode == 0 else 1

    if args.command == "verify":
        result = WorkspaceToolRunner(paths).run_tests(" ".join(args.verify_command), timeout=args.timeout)
        audit.append(
            "cli.tool.completed",
            {
                "tool": result.name,
                "status": result.status,
                "metadata": result.metadata,
                "external_action_started": result.metadata.get("external_action_started", False),
                "browser_auto_launch": False,
            },
        )
        print(result.content)
        return 0 if result.status == "ok" else 1

    if args.command == "fetch":
        result = WebToolRunner(paths).fetch(args.url, approved=args.approved, timeout=args.timeout, max_bytes=args.max_bytes)
        audit.append(
            "cli.tool.completed",
            {
                "tool": result.name,
                "status": result.status,
                "metadata": result.metadata,
                "external_action_started": result.metadata.get("external_action_started", False),
                "browser_auto_launch": False,
            },
        )
        print(result.content)
        return 0 if result.status == "ok" else 1

    if args.command == "edit":
        if args.edit_command == "replace":
            if not args.path:
                parser.error("edit replace requires a workspace file path")
            result = WorkspaceToolRunner(paths).replace_text(args.path, args.old, args.new, approved=args.approved)
            audit.append(
                "cli.tool.completed",
                {
                    "tool": result.name,
                    "status": result.status,
                    "metadata": result.metadata,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(result.content)
            return 0 if result.status == "ok" else 1

    if args.command == "git":
        runner = WorkspaceToolRunner(paths)
        if args.git_command == "status":
            result = runner.git_status()
        elif args.git_command == "diff":
            result = runner.git_diff(args.git_args[0] if args.git_args else None)
        elif args.git_command == "stage":
            result = runner.git_stage(args.git_args, approved=args.approved)
        elif args.git_command == "commit":
            result = runner.git_commit(args.message or " ".join(args.git_args), approved=args.approved)
        elif args.git_command == "branch":
            branch_operation = args.git_args[0] if args.git_args else "list"
            branch_name = args.git_args[1] if len(args.git_args) > 1 else ""
            result = runner.git_branch(branch_operation, branch_name, approved=args.approved)
        elif args.git_command == "remote":
            remote_operation = args.git_args[0] if args.git_args else "list"
            remote_name = args.git_args[1] if len(args.git_args) > 1 else ""
            remote_branch = args.git_args[2] if len(args.git_args) > 2 else ""
            result = runner.git_remote(remote_operation, remote_name, remote_branch, approved=args.approved)
        else:
            parser.error("git requires status, diff, stage, commit, branch, or remote")
        audit.append(
            "cli.tool.completed",
            {
                "tool": result.name,
                "status": result.status,
                "metadata": result.metadata,
                "external_action_started": result.metadata.get("external_action_started", False),
                "browser_auto_launch": False,
            },
        )
        print(result.content)
        return 0 if result.status == "ok" else 1

    if args.command == "chat":
        result = AgentRuntime(paths).respond(args.prompt, session_id=args.session, source="cli")
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.assistant_message)
            print(f"audit receipt: {result.receipt_id}")
        return 0

    if args.command in {"model", "models"}:
        providers = ProviderStore(paths)
        if args.model_command == "providers":
            print(json.dumps(providers.summary(), indent=2))
        elif args.model_command == "doctor":
            print(json.dumps(providers.doctor(), indent=2))
        elif args.model_command == "usage":
            print(json.dumps(ProviderUsageStore(paths).summary(limit=args.limit), indent=2))
        elif args.model_command == "auth":
            auth_command = args.name or "status"
            if auth_command in {"status", "methods"}:
                print(json.dumps(providers.auth_status(), indent=2))
            elif auth_command == "doctor":
                print(json.dumps(providers.doctor(), indent=2))
            elif auth_command in {"login", "logout"}:
                print(
                    json.dumps(
                        {
                            "status": "unsupported",
                            "reason": "Aegis does not browser-login or logout from model providers; connect by environment handle instead.",
                            "next": f"{terminal_command_name()} model connect openai",
                            "browser_auto_launch": False,
                            "gateway_started": False,
                            "external_action_started": False,
                            "model_invocation_performed": False,
                            "raw_secret_values_included": False,
                        },
                        indent=2,
                    )
                )
            else:
                parser.error(f"{args.command} auth requires status, methods, or doctor")
        elif args.model_command == "configure":
            if not args.name:
                parser.error("model configure requires a provider name")
            try:
                payload = providers.configure(
                    args.name,
                    mode=args.mode,
                    api_key_env=args.api_key_env,
                    base_url=args.base_url,
                    active=not args.inactive,
                    source="cli",
                )
            except ValueError as exc:
                parser.error(str(exc))
            print(json.dumps(payload, indent=2))
        elif args.model_command == "connect":
            try:
                payload = providers.connect(
                    args.name or "openai",
                    model=args.model,
                    api_key_env=args.api_key_env,
                    base_url=args.base_url,
                    active=not args.inactive,
                    source="cli",
                )
            except ValueError as exc:
                parser.error(str(exc))
            print(json.dumps(payload, indent=2) if args.json else format_provider_connect(payload))
        return 0

    if args.command == "connectors":
        connectors = ConnectorStore(paths)
        if args.connector_command == "list":
            print(json.dumps(connectors.summary(), indent=2))
        elif args.connector_command == "doctor":
            print(json.dumps(connectors.doctor(), indent=2))
        elif args.connector_command == "outbox":
            print(
                json.dumps(
                    {
                        "outbox": connectors.outbox(limit=args.limit),
                        "external_action_started": False,
                        "external_delivery_performed": False,
                        "browser_auto_launch": False,
                    },
                    indent=2,
                )
            )
        elif args.connector_command in {"draft", "send"}:
            if not args.name:
                parser.error(f"connectors {args.connector_command} requires a connector name")
            if not args.target:
                parser.error(f"connectors {args.connector_command} requires --target")
            if not args.message:
                parser.error(f"connectors {args.connector_command} requires --message")
            try:
                if args.connector_command == "draft":
                    result = connectors.draft(args.name, target=args.target, message=args.message, source="cli")
                    print(json.dumps(result, indent=2))
                    return 0
                result = connectors.send(args.name, target=args.target, message=args.message, approved=args.approved, source="cli")
                print(json.dumps(result, indent=2))
                return 0 if result["status"] == "approved_pending_adapter" else 1
            except (KeyError, ValueError) as exc:
                print(
                    json.dumps(
                        {
                            "status": "blocked",
                            "reason": str(exc),
                            "external_action_started": False,
                            "external_delivery_performed": False,
                            "browser_auto_launch": False,
                            "raw_secret_values_included": False,
                        },
                        indent=2,
                    )
                )
                return 1
        elif args.connector_command == "configure":
            if not args.name:
                parser.error("connectors configure requires a connector name")
            print(
                json.dumps(
                    connectors.configure(
                        args.name,
                        token_env=args.token_env,
                        url_env=args.url_env,
                        enabled=args.enable,
                        source="cli",
                    ),
                    indent=2,
                )
            )
        return 0

    if args.command == "browser":
        store = BrowserSessionStore(paths)
        if args.browser_command == "sessions":
            print(json.dumps(browser_summary(paths, limit=args.limit), indent=2))
            return 0
        if args.browser_command == "show":
            if not args.browser_args:
                parser.error("browser show requires a session id")
            print(json.dumps(store.get(args.browser_args[0]), indent=2))
            return 0
        if args.browser_command == "open":
            if not args.browser_args:
                parser.error("browser open requires an http(s) URL")
            result = store.open_url(args.browser_args[0], title=args.title, approved=args.approved, source="cli")
            audit.append(
                "browser.session.open",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.browser_command == "screenshot":
            if len(args.browser_args) < 2:
                parser.error("browser screenshot requires a session id and workspace screenshot path")
            result = store.record_screenshot(args.browser_args[0], args.browser_args[1], note=args.note, approved=args.approved, source="cli")
            audit.append(
                "browser.session.screenshot",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "ok" else 1

    if args.command == "tasks":
        runner = TaskRunner(paths)
        if args.submit:
            print(json.dumps(runner.submit(args.submit, source="cli").to_dict(), indent=2))
        elif args.background:
            print(json.dumps(runner.submit_background(args.background, source="cli").to_dict(), indent=2))
        elif args.start:
            print(json.dumps(runner.start_background(args.start).to_dict(), indent=2))
        elif args.run:
            print(json.dumps(runner.run(args.run).to_dict(), indent=2))
        elif args.show:
            print(json.dumps(runner.get(args.show).to_dict(), indent=2))
        elif args.events:
            print(json.dumps({"task_id": args.events, "events": [event.to_dict() for event in runner.events(args.events)]}, indent=2))
        elif args.output:
            if args.json:
                print(json.dumps({"task_id": args.output, "outputs": [output.to_dict() for output in runner.outputs(args.output)]}, indent=2))
            else:
                print(format_task_outputs(runner.outputs(args.output)))
        elif args.logs:
            logs = runner.worker_logs(args.logs)
            if args.json:
                print(json.dumps(logs, indent=2))
            else:
                print(format_task_worker_logs(logs))
        elif args.cancel:
            print(json.dumps(runner.cancel(args.cancel, reason=args.reason).to_dict(), indent=2))
        elif args.recover_stale:
            print(json.dumps({"recovered": [record.to_dict() for record in runner.recover_stale_running()]}, indent=2))
        else:
            print(json.dumps({"tasks": runner.list(limit=args.limit)}, indent=2))
        return 0

    if args.command == "task":
        runner = TaskRunner(paths)
        task_command = args.task_command
        task_text = " ".join(args.task_args).strip()
        task_id = args.task_args[0] if args.task_args else ""
        if task_command == "list":
            print(json.dumps({"tasks": runner.list(limit=args.limit)}, indent=2))
        elif task_command == "submit":
            if not task_text:
                parser.error("task submit requires a prompt")
            print(json.dumps(runner.submit(task_text, source="cli").to_dict(), indent=2))
        elif task_command in {"bg", "background"}:
            if not task_text:
                parser.error(f"task {task_command} requires a prompt")
            print(json.dumps(runner.submit_background(task_text, source="cli").to_dict(), indent=2))
        elif task_command == "start":
            if not task_id:
                parser.error("task start requires a task id")
            print(json.dumps(runner.start_background(task_id).to_dict(), indent=2))
        elif task_command == "run":
            if not task_id:
                parser.error("task run requires a task id")
            print(json.dumps(runner.run(task_id).to_dict(), indent=2))
        elif task_command in {"show", "status"}:
            if not task_id:
                parser.error(f"task {task_command} requires a task id")
            print(json.dumps(runner.get(task_id).to_dict(), indent=2))
        elif task_command in {"events", "timeline"}:
            if not task_id:
                parser.error(f"task {task_command} requires a task id")
            print(json.dumps({"task_id": task_id, "events": [event.to_dict() for event in runner.events(task_id)]}, indent=2))
        elif task_command in {"output", "outputs"}:
            if not task_id:
                parser.error(f"task {task_command} requires a task id")
            if args.json:
                print(json.dumps({"task_id": task_id, "outputs": [output.to_dict() for output in runner.outputs(task_id)]}, indent=2))
            else:
                print(format_task_outputs(runner.outputs(task_id)))
        elif task_command in {"log", "logs"}:
            if not task_id:
                parser.error(f"task {task_command} requires a task id")
            logs = runner.worker_logs(task_id)
            if args.json:
                print(json.dumps(logs, indent=2))
            else:
                print(format_task_worker_logs(logs))
        elif task_command == "cancel":
            if not task_id:
                parser.error("task cancel requires a task id")
            print(json.dumps(runner.cancel(task_id, reason=args.reason).to_dict(), indent=2))
        elif task_command in {"recover", "recover-stale"}:
            print(json.dumps({"recovered": [record.to_dict() for record in runner.recover_stale_running()]}, indent=2))
        return 0

    if args.command == "automations":
        registry = AutomationRegistry(paths)
        command = args.automation_command
        automation_args = " ".join(args.automation_args).strip()
        if command == "list":
            payload = automation_summary(paths)
            if args.limit:
                payload["automations"] = payload["automations"][: args.limit]
            print(json.dumps(payload, indent=2) if args.json else format_automations(payload))
        elif command == "create":
            name = automation_args
            job, receipt = registry.create(name, args.schedule, args.prompt, source="cli")
            payload = {"automation": job.to_dict(), "receipt": receipt}
            print(json.dumps(payload, indent=2) if args.json else format_automation(job, receipt=receipt))
        elif command == "show":
            if not automation_args:
                parser.error("automations show requires an automation id")
            job = registry.get(automation_args)
            print(json.dumps(job.to_dict(), indent=2) if args.json else format_automation(job))
        elif command in {"trigger", "run"}:
            if not automation_args:
                parser.error(f"automations {command} requires an automation id")
            payload = registry.trigger(automation_args, start_background=args.background, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Automation trigger blocked: {payload['reason']}")
                print(format_automation(payload["automation"], receipt=payload["receipt"]))
            else:
                print(format_automation(payload["automation"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      {terminal_command_name()} tasks --events {payload['task']['id']}")
        elif command == "due":
            payload = registry.due(now=args.now or None, limit=args.limit, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_due_automations(payload))
        elif command == "missed":
            payload = registry.missed(now=args.now or None, limit=args.limit, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_missed_automations(payload))
        elif command in {"replay", "replay-missed"}:
            payload = registry.replay_missed(now=args.now or None, start_background=args.background, limit=args.limit, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_missed_replay(payload))
        elif command in {"tick", "run-due"}:
            payload = registry.run_due(now=args.now or None, start_background=args.background, limit=args.limit, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_due_run(payload))
        elif command in {"worker", "daemon"}:
            payload = registry.worker(now=args.now or None, interval_seconds=args.interval, max_ticks=args.max_ticks, start_background=args.background, limit=args.limit, source="cli-worker")
            print(json.dumps(payload, indent=2) if args.json else format_worker_run(payload))
        elif command in {"logs", "worker-log"}:
            payload = registry.worker_logs(limit=args.limit, run_id=automation_args, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_worker_logs(payload))
        elif command == "service":
            payload = registry.service_wrapper(interval_seconds=args.interval, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_service_wrapper(payload))
        elif command in {"service-status", "status"}:
            payload = registry.service_status(source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_service_status(payload))
        elif command == "pause":
            if not automation_args:
                parser.error("automations pause requires an automation id")
            job, receipt = registry.set_status(automation_args, "PAUSED", source="cli")
            payload = {"automation": job.to_dict(), "receipt": receipt}
            print(json.dumps(payload, indent=2) if args.json else format_automation(job, receipt=receipt))
        elif command == "resume":
            if not automation_args:
                parser.error("automations resume requires an automation id")
            job, receipt = registry.set_status(automation_args, "ACTIVE", source="cli")
            payload = {"automation": job.to_dict(), "receipt": receipt}
            print(json.dumps(payload, indent=2) if args.json else format_automation(job, receipt=receipt))
        elif command == "delete":
            if not automation_args:
                parser.error("automations delete requires an automation id")
            payload = registry.delete(automation_args, source="cli")
            print(json.dumps(payload, indent=2) if args.json else f"Deleted automation {payload['deleted']['id']} ({payload['deleted']['name']})\nreceipt    {payload['receipt']}")
        return 0

    if args.command == "improve":
        store = ImprovementStore(paths)
        command = args.improve_command
        improve_args = " ".join(args.improve_args).strip()
        if command in {"status", "list"}:
            payload = improvement_summary(paths)
            if args.limit:
                payload["proposals"] = payload["proposals"][: args.limit]
            print(json.dumps(payload, indent=2) if args.json else format_improvements(payload))
        elif command == "propose":
            if not improve_args:
                parser.error("improve propose requires a failure summary")
            proposal, receipt = store.propose_from_failure(improve_args, target_subsystem=args.target, operation=args.operation, source="cli")
            payload = {"proposal": proposal.to_dict(), "receipt": receipt}
            print(json.dumps(payload, indent=2) if args.json else format_improvement(proposal, receipt=receipt))
        elif command == "show":
            if not improve_args:
                parser.error("improve show requires a proposal id")
            proposal = store.get(improve_args)
            print(json.dumps(proposal.to_dict(), indent=2) if args.json else format_improvement(proposal))
        elif command in {"review", "approve", "reject"}:
            if not improve_args:
                parser.error(f"improve {command} requires a proposal id")
            decision = "review" if command == "review" else command
            proposal, receipt = store.review(improve_args, decision=decision, rationale=args.rationale, source="cli")
            payload = {"proposal": proposal.to_dict(), "receipt": receipt}
            print(json.dumps(payload, indent=2) if args.json else format_improvement(proposal, receipt=receipt))
        elif command in {"implement", "handoff"}:
            if not improve_args:
                parser.error(f"improve {command} requires a proposal id")
            payload = store.handoff(improve_args, start_background=args.background, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement handoff blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      {terminal_command_name()} tasks --events {payload['task']['id']}")
        elif command == "candidate":
            if not improve_args:
                parser.error("improve candidate requires a proposal id")
            payload = store.generate_candidate(improve_args, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement candidate blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
        elif command == "candidate-show":
            if not improve_args:
                parser.error("improve candidate-show requires a candidate id")
            candidate = store.get_candidate(improve_args)
            print(json.dumps(candidate.to_dict(), indent=2) if args.json else format_candidate(candidate))
        elif command in {"diff", "candidate-diff"}:
            if not improve_args:
                parser.error(f"improve {command} requires a candidate id")
            payload = store.review_candidate_diff(improve_args, source="cli")
            print(json.dumps(payload, indent=2) if args.json else format_candidate_diff_review(payload))
        elif command == "verify":
            if not improve_args:
                parser.error("improve verify requires a candidate id")
            payload = store.run_candidate_verification(improve_args, command_index=args.command_index, timeout_seconds=args.timeout, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement verification blocked: {payload['reason']}")
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
            else:
                print(format_verification_run(payload, receipt=payload["receipt"]))
        elif command in {"apply", "apply-candidate"}:
            if not improve_args:
                parser.error(f"improve {command} requires a candidate id")
            payload = store.apply_candidate(improve_args, start_background=args.background, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement candidate apply blocked: {payload['reason']}")
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
            else:
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      {terminal_command_name()} tasks --events {payload['task']['id']}")
        elif command == "evidence":
            if not improve_args:
                parser.error("improve evidence requires a proposal id")
            payload = store.record_evidence(
                improve_args,
                changed_files=args.files.split(","),
                verification_command=args.validation,
                verification_result=args.result,
                task_id=args.task,
                source="cli",
            )
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement evidence blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
        elif command in {"complete", "implemented"}:
            if not improve_args:
                parser.error(f"improve {command} requires a proposal id")
            payload = store.mark_implemented(improve_args, source="cli")
            if args.json:
                print(json.dumps(payload, indent=2))
            elif payload["status"] == "blocked":
                print(f"Improvement completion blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
        return 0

    if args.command == "subagents":
        orchestrator = LocalSubagentOrchestrator(paths)
        if args.delegate:
            try:
                result = orchestrator.delegate(args.delegate, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth)
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print(json.dumps(result.to_dict(), indent=2))
        elif args.stream:
            print("SUBAGENT LIVE")
            try:
                result = orchestrator.delegate(args.stream, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth, event_sink=lambda event: print(format_event_line(event), flush=True))
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print("")
            print(json.dumps({"root_id": result.root.id, "receipt_id": result.receipt_id, "status": result.root.status}, indent=2))
        elif args.background:
            try:
                record = orchestrator.start_background(args.background, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth)
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print(json.dumps(record.to_dict(), indent=2))
        elif args.run_job:
            record = orchestrator.run_background_job(args.run_job)
            print(json.dumps(record.to_dict(), indent=2))
        elif args.cancel:
            record = orchestrator.cancel_background(args.cancel)
            print(json.dumps(record.to_dict(), indent=2))
        elif args.job:
            print(json.dumps(orchestrator.background_job(args.job).to_dict(), indent=2))
        elif args.jobs:
            print(json.dumps({"jobs": orchestrator.background_jobs()}, indent=2))
        elif args.recover_stale:
            print(json.dumps({"recovered": [record.to_dict() for record in orchestrator.recover_stale_background()]}, indent=2))
        elif args.stop:
            result = orchestrator.stop(args.stop)
            print(json.dumps(result.to_dict(), indent=2))
        elif args.events:
            events = orchestrator.events(args.events)
            print(json.dumps({"root_id": args.events, "events": [event.to_dict() for event in events]}, indent=2))
        elif args.synthesis:
            try:
                synthesis = orchestrator.synthesis(args.synthesis)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.synthesis.read", {"root_id": args.synthesis, "synthesis_id": synthesis.get("id", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"synthesis": synthesis, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            print(json.dumps(payload, indent=2) if args.json else format_synthesis(synthesis))
        elif args.artifact_graph:
            try:
                graph = orchestrator.artifact_graph(args.artifact_graph)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.artifact_graph.read", {"root_id": args.artifact_graph, "synthesis_id": graph.get("synthesis_id", ""), "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"graph": graph, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            print(json.dumps(payload, indent=2) if args.json else format_artifact_graph(graph))
        elif args.artifacts:
            store = SubagentStore(paths)
            rows = store.artifacts()
            receipt = audit.append("subagent.artifacts.listed", {"count": len(rows), "limit": 50, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"artifacts": rows, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            print(json.dumps(payload, indent=2) if args.json else format_artifacts(rows))
        elif args.artifact:
            store = SubagentStore(paths)
            try:
                row = store.artifact(args.artifact)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.artifact.read", {"artifact_id": args.artifact, "path": row.get("path", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"artifact": row, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            print(json.dumps(payload, indent=2) if args.json else format_artifact(row))
        elif args.artifact_search:
            store = SubagentStore(paths)
            rows = store.search_artifacts(args.artifact_search)
            receipt = audit.append("subagent.artifacts.searched", {"query": args.artifact_search, "count": len(rows), "limit": 20, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"query": args.artifact_search, "artifacts": rows, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            print(json.dumps(payload, indent=2) if args.json else format_artifact_search(args.artifact_search, rows))
        elif args.spawn:
            queue = SubagentQueue()
            record = queue.spawn(args.spawn)
            SubagentStore(paths).save(record)
            audit.append("subagent.spawn", record.to_dict())
            print(json.dumps(record.to_dict(), indent=2))
        else:
            queue = SubagentQueue()
            print(
                json.dumps(
                    {
                        "max_concurrency": queue.limits.max_concurrency,
                        "max_depth": queue.limits.max_depth,
                        "max_children": queue.limits.max_children,
                        "records": SubagentStore(paths).list(),
                    },
                    indent=2,
                )
            )
        return 0

    if args.command == "agents":
        orchestrator = LocalSubagentOrchestrator(paths)
        command = args.agent_command
        agent_args = " ".join(args.agent_args).strip()
        if command == "status":
            payload = agent_status(paths)
            print(json.dumps(payload, indent=2) if args.json else format_agent_status(payload))
        elif command == "profiles":
            payload = {"profiles": agent_status(paths)["profiles"], "terminal_first": True, "browser_auto_launch": False}
            print(json.dumps(payload, indent=2) if args.json else format_agent_profiles())
        elif command == "contracts":
            payload = agent_contracts_payload(paths)
            print(json.dumps(payload, indent=2) if args.json else format_agent_contracts(payload))
        elif command == "delegate":
            if not agent_args:
                parser.error("agents delegate requires a task")
            try:
                result = orchestrator.delegate(agent_args, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth)
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print(json.dumps(result.to_dict(), indent=2))
        elif command in {"stream", "live"}:
            if not agent_args:
                parser.error(f"agents {command} requires a task")
            print("AGENTS LIVE")
            try:
                result = orchestrator.delegate(agent_args, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth, event_sink=lambda event: print(format_event_line(event), flush=True))
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print("")
            print(json.dumps({"root_id": result.root.id, "receipt_id": result.receipt_id, "status": result.root.status}, indent=2))
        elif command in {"background", "bg"}:
            if not agent_args:
                parser.error(f"agents {command} requires a task")
            try:
                record = orchestrator.start_background(agent_args, reusable_artifact_ids=args.use_artifact, reuse_approved=args.approved, requested_depth=args.depth)
            except (KeyError, ValueError) as exc:
                parser.error(str(exc))
            print(json.dumps(record.to_dict(), indent=2))
        elif command == "jobs":
            print(json.dumps({"jobs": orchestrator.background_jobs()}, indent=2))
        elif command in {"job", "monitor"}:
            if not agent_args:
                parser.error(f"agents {command} requires a job id")
            print(json.dumps(orchestrator.background_job(agent_args).to_dict(), indent=2))
        elif command == "cancel":
            if not agent_args:
                parser.error("agents cancel requires a job id")
            print(json.dumps(orchestrator.cancel_background(agent_args).to_dict(), indent=2))
        elif command == "recover":
            print(json.dumps({"recovered": [record.to_dict() for record in orchestrator.recover_stale_background()]}, indent=2))
        elif command == "synthesis":
            if not agent_args:
                parser.error("agents synthesis requires a root id")
            try:
                synthesis = orchestrator.synthesis(agent_args)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.synthesis.read", {"surface": "agents", "root_id": agent_args, "synthesis_id": synthesis.get("id", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"synthesis": synthesis, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            text = format_synthesis(synthesis).replace("SUBAGENT SYNTHESIS", "AGENT SYNTHESIS", 1)
            print(json.dumps(payload, indent=2) if args.json else text)
        elif command == "graph":
            if not agent_args:
                parser.error("agents graph requires a root id")
            try:
                graph = orchestrator.artifact_graph(agent_args)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.artifact_graph.read", {"surface": "agents", "root_id": agent_args, "synthesis_id": graph.get("synthesis_id", ""), "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"graph": graph, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            text = format_artifact_graph(graph).replace("SUBAGENT ARTIFACT GRAPH", "AGENT ARTIFACT GRAPH", 1)
            print(json.dumps(payload, indent=2) if args.json else text)
        elif command == "artifacts":
            artifact_args = args.agent_args
            store = SubagentStore(paths)
            if artifact_args and artifact_args[0] in {"show", "read", "artifact"}:
                artifact_id = " ".join(artifact_args[1:]).strip()
                if not artifact_id:
                    parser.error("agents artifacts show requires an artifact id")
                try:
                    row = store.artifact(artifact_id)
                except KeyError as exc:
                    parser.error(str(exc))
                receipt = audit.append("subagent.artifact.read", {"surface": "agents", "artifact_id": artifact_id, "path": row.get("path", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                payload = {"artifact": row, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
                text = format_artifact(row).replace("SUBAGENT ARTIFACT", "AGENT ARTIFACT", 1)
                print(json.dumps(payload, indent=2) if args.json else text)
            elif artifact_args and artifact_args[0] in {"search", "find"}:
                query = " ".join(artifact_args[1:]).strip()
                if not query:
                    parser.error("agents artifacts search requires a query")
                rows = store.search_artifacts(query)
                receipt = audit.append("subagent.artifacts.searched", {"surface": "agents", "query": query, "count": len(rows), "limit": 20, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                payload = {"query": query, "artifacts": rows, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
                text = format_artifact_search(query, rows).replace("SUBAGENT ARTIFACT SEARCH", "AGENT ARTIFACT SEARCH", 1)
                print(json.dumps(payload, indent=2) if args.json else text)
            elif artifact_args:
                parser.error("agents artifacts accepts: show <artifact-id>, search <query>, or no arguments")
            else:
                rows = store.artifacts()
                receipt = audit.append("subagent.artifacts.listed", {"surface": "agents", "count": len(rows), "limit": 50, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                payload = {"artifacts": rows, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
                text = format_artifacts(rows).replace("SUBAGENT ARTIFACTS", "AGENT ARTIFACTS", 1)
                print(json.dumps(payload, indent=2) if args.json else text)
        elif command == "artifact":
            if not agent_args:
                parser.error("agents artifact requires an artifact id")
            try:
                row = SubagentStore(paths).artifact(agent_args)
            except KeyError as exc:
                parser.error(str(exc))
            receipt = audit.append("subagent.artifact.read", {"surface": "agents", "artifact_id": agent_args, "path": row.get("path", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"artifact": row, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            text = format_artifact(row).replace("SUBAGENT ARTIFACT", "AGENT ARTIFACT", 1)
            print(json.dumps(payload, indent=2) if args.json else text)
        elif command == "search-artifacts":
            if not agent_args:
                parser.error("agents search-artifacts requires a query")
            rows = SubagentStore(paths).search_artifacts(agent_args)
            receipt = audit.append("subagent.artifacts.searched", {"surface": "agents", "query": agent_args, "count": len(rows), "limit": 20, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            payload = {"query": agent_args, "artifacts": rows, "receipt": receipt["id"], "browser_auto_launch": False, "external_action_started": False}
            text = format_artifact_search(agent_args, rows).replace("SUBAGENT ARTIFACT SEARCH", "AGENT ARTIFACT SEARCH", 1)
            print(json.dumps(payload, indent=2) if args.json else text)
        return 0

    if args.command == "tui":
        if args.print:
            print(render(TuiState(view=args.view), width=args.width, height=args.height))
            return 0
        return run_textual_app(args.view, paths=paths, classic=args.classic)

    if args.command == "gateway":
        if not args.approved:
            print("AEGIS OPTIONAL GATEWAY")
            print("status      needs_approval")
            print(f"command     {terminal_command_name()} gateway --approved --host {args.host} --port {args.port}")
            print("browser_auto_launch: false")
            print("gateway_started: false")
            print("next        rerun with --approved to start the optional local gateway")
            return 1
        print(f"Starting optional AegisAgent gateway on http://{args.host}:{args.port}")
        print("browser_auto_launch: false")
        return run_gateway(args.host, args.port, str(paths.workspace))

    if args.command == "web":
        command = terminal_command_name()
        payload = {
            "title": "AEGIS OPTIONAL WEB CONSOLE",
            "status": "serve_approved" if args.serve and args.approved else "needs_approval" if args.serve else "preview",
            "workspace": str(paths.workspace),
            "web_source": str(paths.web_dir),
            "terminal_first": True,
            "browser_required": False,
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": False,
            "serve_command": f"{command} web --serve --approved --host {args.host} --port {args.port}",
            "dev_command": f"cd {paths.web_dir} && npm install && npm run dev -- --port 5173",
            "terminal_command": f"{command} tui",
        }
        if not args.serve:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(str(payload["title"]))
                print(f"status      {payload['status']}")
                print(f"workspace   {payload['workspace']}")
                print(f"web source  {payload['web_source']}")
                print(f"serve       {payload['serve_command']}")
                print(f"dev ui      {payload['dev_command']}")
                print(f"terminal    {payload['terminal_command']}")
                print("browser_auto_launch: false")
                print("gateway_started: false")
                print("external_action_started: false")
                print("note        preview only; no server or browser was started")
            return 0
        if not args.approved:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(str(payload["title"]))
                print("status      needs_approval")
                print(f"serve       {payload['serve_command']}")
                print("browser_auto_launch: false")
                print("gateway_started: false")
                print("external_action_started: false")
                print("next        rerun with --serve --approved to start the optional local gateway")
            return 1
        print(f"Starting optional AegisAgent gateway on http://{args.host}:{args.port}")
        print("browser_auto_launch: false")
        return run_gateway(args.host, args.port, str(paths.workspace))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
