"""Curses-backed prompt-first TUI for AegisAgent."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
import io
import os
from pathlib import Path
import sys
import time
import textwrap
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.core.activation import format_terminal_activation, terminal_activation_payload
from aegisagent.core.agent import AgentRuntime
from aegisagent.core.automation import AutomationRegistry, automation_summary, format_automation, format_automations, format_due_automations, format_due_run, format_missed_automations, format_missed_replay, format_service_status, format_service_wrapper, format_worker_logs, format_worker_run
from aegisagent.core.browser_sessions import BrowserSessionStore, browser_summary
from aegisagent.core.capabilities import capability_map, format_capabilities
from aegisagent.core.connectors import ConnectorStore
from aegisagent.core.dashboard import dashboard_payload, format_dashboard
from aegisagent.core.executor import GovernedExecutor
from aegisagent.core.improvement import ImprovementStore, format_candidate, format_candidate_diff_review, format_improvement, format_improvements, format_verification_run, improvement_summary
from aegisagent.core.lifecycle import format_install_status, format_update_status, install_status_payload, install_terminal_shim, update_from_github
from aegisagent.core.memory import MemoryStore
from aegisagent.core.provider_config import ProviderStore, ProviderUsageStore, format_provider_connect
from aegisagent.core.sessions import SessionStore
from aegisagent.core.setup_flow import (
    SETUP_SECTIONS,
    SetupGuide,
    format_setup_first_task,
    format_setup_next,
    format_setup_quickstart,
    format_setup_section,
    normalize_setup_section,
    terminal_command_name,
)
from aegisagent.core.setup_state import setup_wizard_preferences, update_setup_wizard_preferences
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
    format_delegation,
    format_event_line,
    format_events,
    format_synthesis,
    format_stop,
    format_subagent_records,
)
from aegisagent.core.tasks import TaskRunner, TaskStore, format_task, format_task_events, format_task_outputs, format_task_worker_logs, format_tasks
from aegisagent.core.tools import ToolRegistry, enabled_counts
from aegisagent.core.web_tools import WebToolRunner
from aegisagent.core.workspace_tools import WorkspaceToolRunner, WorkspaceToolResult
from aegisagent.security.audit import AuditLog
from aegisagent.security.policy import decide_tool
from aegisagent.security.sandbox import detect_sandbox
from aegisagent.tui.renderer import TuiState, render


@dataclass(frozen=True)
class InteractiveItem:
    label: str
    detail: str
    command: str = ""
    status: str = ""
    menu: str = ""


@dataclass(frozen=True)
class InteractivePanel:
    panel_id: str
    title: str
    items: tuple[InteractiveItem, ...]


@dataclass(frozen=True)
class PanelBounds:
    panel_id: str
    y: int
    x: int
    h: int
    w: int


SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/help", "show terminal controls and available commands"),
    ("/activation", "show terminal activation commands and browser-off readiness"),
    ("/commands", "show Hermes-style slash command lanes"),
    ("/menu", "show grouped operate/govern/setup/build/explore lanes"),
    ("/dashboard", "show terminal-first operator dashboard"),
    ("/install", "show or install the macOS/Linux terminal command"),
    ("/update", "pull the latest GitHub main branch after approval"),
    ("/capabilities", "show Hermes-class capability parity map"),
    ("/gaps", "show remaining partial, metadata-ready, and planned work"),
    ("/setup", "open secure first-run setup"),
    ("/setup next", "show the next concrete setup action"),
    ("/setup model", "show model route setup steps"),
    ("/setup model-auth", "alias for model route setup steps"),
    ("/setup secrets", "show secret-handle setup steps"),
    ("/setup sandbox", "show sandbox readiness"),
    ("/setup tools", "show tool-policy setup steps"),
    ("/setup connectors", "show connector setup posture"),
    ("/setup connections", "alias for connector setup posture"),
    ("/setup memory", "show memory and skills setup steps"),
    ("/setup skills", "alias for memory and skills setup steps"),
    ("/setup plugins", "alias for memory and skills setup steps"),
    ("/setup first-task", "show a safe first terminal task"),
    ("/setup run-checks", "run metadata-only setup checks"),
    ("/setup check", "alias for metadata-only setup checks"),
    ("/setup checks", "alias for metadata-only setup checks"),
    ("/setup verify", "alias for metadata-only setup checks"),
    ("/setup doctor", "alias for metadata-only setup checks"),
    ("/setup init", "show the setup quickstart"),
    ("/setup hide", "hide the setup wizard on default TUI launch"),
    ("/setup reset", "show the setup wizard on default TUI launch"),
    ("/setup json", "print setup quickstart as machine-readable JSON"),
    ("/tools", "inspect governed tools matrix"),
    ("/audit", "verify append-only audit chain"),
    ("/clear", "clear the visible terminal output"),
    ("/new", "start a fresh named terminal session record"),
    ("/reset", "start a replacement terminal session record"),
    ("/submit", "submit a governed prompt from slash form"),
    ("/tasks", "list governed terminal tasks"),
    ("/tasks submit", "queue a governed task without running it immediately"),
    ("/tasks bg", "start a governed task in a detached worker"),
    ("/tasks run", "run a queued governed task"),
    ("/tasks start", "start a queued task in a detached worker"),
    ("/tasks events", "show progress events for a task"),
    ("/tasks watch", "live repaint task status and progress events"),
    ("/tasks output", "show recorded assistant and tool output"),
    ("/tasks logs", "show detached worker stdout and stderr"),
    ("/tasks unwatch", "stop the active nonblocking task monitor"),
    ("/tasks recover", "mark stale detached running tasks failed"),
    ("/tasks cancel", "cancel a queued governed task"),
    ("/task", "exact root alias for /tasks"),
    ("/automations", "list durable gated automation records"),
    ("/automations create", "create a gated automation record with name | schedule | prompt"),
    ("/automations due", "check which automation schedules are due"),
    ("/automations missed", "show missed automation schedule windows"),
    ("/automations replay", "explicitly queue missed automation runs"),
    ("/automations tick", "queue governed tasks for due automations"),
    ("/automations worker", "run one visible foreground scheduler pass"),
    ("/automations logs", "show durable automation worker log events"),
    ("/automations service", "generate a launchd wrapper without loading it"),
    ("/automations service-status", "inspect launchd wrapper presence and load state"),
    ("/automations trigger", "queue a governed task from an automation record"),
    ("/automations pause", "pause a durable automation record"),
    ("/automations resume", "resume a durable automation record"),
    ("/automations delete", "delete a durable automation record"),
    ("/improve", "show governed self-improvement proposals"),
    ("/improve propose", "create a reviewed improvement proposal"),
    ("/improve approve", "approve a proposal after review"),
    ("/improve implement", "queue governed implementation work for an approved proposal"),
    ("/improve handoff", "alias for /improve implement"),
    ("/improve candidate", "generate an advisory repair candidate for an approved proposal"),
    ("/improve diff", "review candidate file diffs without applying patches"),
    ("/improve verify", "run a candidate verification command and save a receipt"),
    ("/improve apply", "queue governed work from a verified candidate"),
    ("/improve evidence", "record changed files and verification for a handoff"),
    ("/improve complete", "mark a proposal implemented after evidence is recorded"),
    ("/improve reject", "reject a proposal with rationale"),
    ("/q", "quick alias for /tasks submit"),
    ("/add-dir", "record an extra workspace context directory"),
    ("/model providers", "show configured local model provider routes"),
    ("/model connect", "connect OpenAI with the default environment handle"),
    ("/model connect openai", "connect OpenAI using OPENAI_API_KEY"),
    ("/model connect local", "use the built-in local provider"),
    ("/model doctor", "run metadata-only model route checks"),
    ("/model usage", "show terminal model invocation usage ledger"),
    ("/model auth status", "show read-only model auth status"),
    ("/model auth methods", "show read-only model auth methods"),
    ("/model auth doctor", "run metadata-only model auth checks"),
    ("/models providers", "alias for model provider routes"),
    ("/connectors", "show connector readiness metadata"),
    ("/connectors doctor", "run metadata-only connector checks"),
    ("/connectors draft", "draft a redacted outbound connector packet"),
    ("/connectors send", "record an approved outbound connector packet"),
    ("/connectors outbox", "show connector packet outbox"),
    ("/memory", "index and search local memory"),
    ("/memory search", "search local memory by query"),
    ("/memory index", "index curated memory files"),
    ("/memory list", "list curated memory entries"),
    ("/memory show", "show one curated memory entry"),
    ("/memory delete", "delete one curated memory entry after approval"),
    ("/memory add", "append a governed note to curated memory after approval"),
    ("/skills", "show skill trust posture"),
    ("/skills manifest", "preview or write a skill checksum manifest"),
    ("/read", "read a workspace file through a typed non-shell tool"),
    ("/git status", "inspect git status through a typed non-shell tool"),
    ("/git diff", "inspect git diff through a typed non-shell tool"),
    ("/git stage", "stage explicit workspace files after operator approval"),
    ("/git commit", "commit staged files after operator approval"),
    ("/git branch", "list, create, or switch branches through a typed tool"),
    ("/git remote", "list remotes or fetch, pull, and push after approval"),
    ("/edit replace", "replace exact file text only after explicit approval"),
    ("/test", "run default allowlisted tests through a typed non-shell tool"),
    ("/verify", "run an allowlisted verification command through a typed tool"),
    ("/subagents", "show bounded subagent limits"),
    ("/subagents artifacts", "list durable role artifacts"),
    ("/subagents artifacts show", "show one durable role artifact"),
    ("/subagents artifacts search", "search durable role artifacts"),
    ("/subagents synthesis", "show coordinator final synthesis for a root delegation"),
    ("/subagents graph", "show coordinator artifact graph for a root delegation"),
    ("/subagents live", "delegate and stream local worker progress; add | depth 2 for opt-in nested review or | use-artifact <id> | approve"),
    ("/subagents bg", "start background subagent work; add | depth 2 for opt-in nested review or | use-artifact <id> | approve"),
    ("/subagents monitor", "live repaint background subagent job progress"),
    ("/subagents unwatch", "stop the active subagent job monitor"),
    ("/subagents recover", "mark stale background subagent jobs failed"),
    ("/agents", "show Hermes-style agent status backed by local subagents"),
    ("/agents profiles", "show planner/researcher/implementer/reviewer profiles"),
    ("/agents contracts", "show role context contracts, deliverables, and budgets"),
    ("/agents delegate", "run bounded local planner/researcher/implementer/reviewer agents; add | depth 2 for opt-in nested review or | use-artifact <id> | approve"),
    ("/agents artifacts", "list durable role artifacts"),
    ("/agents artifacts show", "show one durable role artifact"),
    ("/agents artifacts search", "search durable role artifacts"),
    ("/agents synthesis", "show coordinator final synthesis for a root delegation"),
    ("/agents graph", "show coordinator artifact graph for a root delegation"),
    ("/agents live", "delegate and stream Hermes-style local agent progress; add | depth 2 for opt-in nested review or | use-artifact <id> | approve"),
    ("/agents stream", "alias for /agents live"),
    ("/agents bg", "start background agent work; add | depth 2 for opt-in nested review or | use-artifact <id> | approve"),
    ("/agents jobs", "list background agent jobs"),
    ("/agents monitor", "live repaint background agent job progress"),
    ("/agents unwatch", "stop the active agent job monitor"),
    ("/agents recover", "mark stale background agent jobs failed"),
    ("/policy shell", "evaluate a shell action through policy"),
    ("/run", "execute a policy-allowed local command"),
    ("/sessions", "show persistent terminal transcript"),
    ("/sessions search", "search prior redacted terminal transcripts"),
    ("/web", "show optional web GUI launch command"),
    ("/web fetch", "fetch an http(s) URL after approval without opening a browser"),
    ("/browser", "list explicit browser session records"),
    ("/browser open", "create an approved browser session record without auto-launch"),
    ("/browser screenshot", "attach a screenshot receipt to a browser session"),
    ("/status", "show local runtime status"),
    ("/exit", "exit AegisAgent TUI"),
    ("/quit", "exit AegisAgent TUI"),
)


COMMAND_ROOT_SHORTCUTS: tuple[tuple[str, str, str], ...] = (
    ("/task", "/tasks", "exact root alias for task queue overview"),
    ("/model", "/model providers", "exact root alias for provider route readiness"),
    ("/memory", "/memory", "canonical memory index/search root"),
)


COMMAND_MENU_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Operate",
        (
            ("/submit <request>", "send a governed prompt turn"),
            ("/activation", "show terminal startup commands"),
            ("/dashboard", "show terminal operator posture"),
            ("/install", "show macOS/Linux terminal install command"),
            ("/update", "pull latest GitHub main after approval"),
            ("/tasks", "list governed terminal tasks"),
            ("/tasks submit <request>", "queue governed work"),
            ("/tasks bg <request>", "start governed work in detached worker"),
            ("/tasks run <id>", "run queued governed work"),
            ("/tasks start <id>", "start queued work in detached worker"),
            ("/tasks events <id>", "show queued/detached task progress"),
            ("/tasks watch <id>", "live repaint queued/detached task progress"),
            ("/tasks output <id>", "show assistant and tool output"),
            ("/tasks logs <id>", "show detached worker stdout/stderr"),
            ("/tasks unwatch", "stop active task monitor"),
            ("/tasks recover", "recover stale detached running tasks"),
            ("/tasks cancel <id>", "cancel queued governed work"),
            ("/task", "exact root alias for /tasks"),
            ("/automations", "list gated schedule records"),
            ("/automations create <name> | <schedule> | <prompt>", "persist a schedule record"),
            ("/automations due", "check due schedules without queueing work"),
            ("/automations missed", "show missed schedule windows"),
            ("/automations replay", "queue missed runs explicitly"),
            ("/automations tick", "queue governed tasks for due schedules"),
            ("/automations worker", "run one visible scheduler pass"),
            ("/automations logs", "show worker logs"),
            ("/automations service", "generate launchd wrapper"),
            ("/automations service-status", "inspect service wrapper"),
            ("/automations trigger <id>", "queue a governed task from a schedule record"),
            ("/automations pause <id>", "pause a schedule record"),
            ("/automations resume <id>", "resume a schedule record"),
            ("/improve", "show self-improvement proposals"),
            ("/improve propose <failure>", "classify and record an improvement proposal"),
            ("/improve implement <id>", "queue governed work for an approved proposal"),
            ("/improve candidate <id>", "generate advisory repair candidate"),
            ("/improve diff <candidate-id>", "review candidate diffs without editing"),
            ("/improve verify <candidate-id>", "run a candidate verification receipt"),
            ("/improve apply <candidate-id>", "queue verified candidate work"),
            ("/improve evidence <id> | <files> | <command> | <result>", "record implementation evidence"),
            ("/improve complete <id>", "mark evidence-backed proposal implemented"),
            ("/q <request>", "quick alias for task queue submit"),
            ("/new [title]", "create a fresh terminal session record"),
            ("/reset [title]", "create a replacement terminal session record"),
            ("/clear", "clear visible output without touching receipts"),
            ("/add-dir <path>", "record an additional context directory"),
            ("/sessions search <query>", "search prior redacted transcripts"),
        ),
    ),
    (
        "Govern",
        (
            ("/audit", "verify append-only receipt chain"),
            ("/tools", "inspect governed tool matrix"),
            ("/policy shell <command>", "evaluate shell policy before execution"),
            ("/run <command>", "run policy-allowed local shell inspection"),
            ("/status", "show runtime security posture"),
            ("/dashboard", "show terminal operator dashboard"),
            ("/capabilities", "show Hermes-class capability map"),
            ("/gaps", "show remaining Hermes-class backlog"),
        ),
    ),
    (
        "Setup",
        (
            ("/setup", "open secure first-run setup"),
            ("/setup next", "show the next concrete setup action"),
            ("/setup model", "show provider configuration steps"),
            ("/setup model-auth", "alias for provider configuration steps"),
            ("/setup secrets", "show safe secret-handle guidance"),
            ("/setup sandbox", "show sandbox and host-execution posture"),
            ("/setup tools", "show tool approval posture"),
            ("/setup connectors", "show connector readiness posture"),
            ("/setup connections", "alias for connector readiness posture"),
            ("/setup memory", "show memory and skills readiness"),
            ("/setup skills", "alias for memory and skills readiness"),
            ("/setup first-task", "show a safe starter task"),
            ("/setup run-checks", "run metadata-only setup checks"),
            ("/setup check", "alias for setup checks"),
            ("/setup checks", "alias for setup checks"),
            ("/setup verify", "alias for setup checks"),
            ("/setup doctor", "alias for setup checks"),
            ("/setup hide", "hide first-launch wizard"),
            ("/setup reset", "restore first-launch wizard"),
            ("/model providers", "show provider route readiness"),
            ("/model connect openai", "connect OpenAI with OPENAI_API_KEY"),
            ("/model connect local", "use the built-in local provider"),
            ("/model doctor", "run provider route readiness checks"),
            ("/model usage", "show local/external model usage ledger"),
            ("/model auth status", "show read-only model auth status"),
            ("/model auth methods", "show read-only model auth methods"),
            ("/model auth doctor", "run metadata-only model auth checks"),
            ("/models providers", "alias for provider route readiness"),
            ("/connectors", "show connector readiness metadata"),
            ("/connectors doctor", "run metadata-only connector checks"),
            ("/connectors draft <name> | <target> | <message>", "draft outbound connector packet"),
            ("/connectors send <name> | <target> | <message> | approve", "approval-bound connector packet"),
            ("/connectors outbox", "show approved/drafted connector packets"),
            ("/memory", "index and search local memory"),
            ("/memory search <query>", "search local memory by query"),
            ("/memory index", "index curated memory files"),
            ("/memory list", "review curated memory entries"),
            ("/memory show <entry-id>", "inspect redacted curated memory"),
            ("/memory delete <entry-id> | approve", "approval-gated curated memory delete"),
            ("/memory add <workspace|user> | <title> | <body> | approve", "approval-gated curated memory write"),
            ("/skills", "show skill trust posture"),
            ("/skills manifest <skill-name> | approve", "approval-gated skill checksum manifest write"),
            ("/web", "print optional browser GUI launch command"),
            ("/web fetch <url> | approve", "approval-gated terminal URL fetch"),
            ("/browser", "list explicit browser session records"),
            ("/browser open <url> | approve", "record browser intent without auto-launch"),
            ("/browser screenshot <session-id> | <path> | approve", "attach screenshot evidence"),
            ("/capabilities", "show implemented, partial, metadata-ready, and planned surfaces"),
            ("/gaps", "show remaining product gaps without opening a browser"),
            ("/automations", "list durable gated schedule records"),
            ("/automations due", "check schedule due state"),
            ("/automations missed", "show missed windows"),
            ("/automations replay", "queue missed runs"),
            ("/automations tick", "queue due schedule records"),
            ("/automations worker", "run visible scheduler pass"),
            ("/automations logs", "show foreground worker logs"),
            ("/automations service", "generate service wrapper"),
            ("/automations service-status", "inspect service wrapper"),
            ("/improve", "show governed improvement loop status"),
            ("/improve implement <id>", "queue approved self-improvement work"),
            ("/improve candidate <id>", "generate terminal repair candidate"),
            ("/improve diff <candidate-id>", "review candidate diffs"),
            ("/improve verify <candidate-id>", "run terminal verification receipt"),
            ("/improve apply <candidate-id>", "handoff verified repair plan"),
            ("/improve evidence <id> | <files> | <command> | <result>", "record implementation evidence"),
        ),
    ),
    (
        "Build",
        (
            ("/read <path>", "read workspace file through typed tool"),
            ("/git status", "inspect git status through typed tool"),
            ("/git diff [path]", "inspect git diff through typed tool"),
            ("/git stage <path> [path...] | approve", "approval-gated git index staging"),
            ("/git commit <message> | approve", "approval-gated git history commit"),
            ("/git branch create <name> | approve", "approval-gated branch creation"),
            ("/git branch switch <name> | approve", "approval-gated branch switch"),
            ("/git remote fetch <remote> [branch] | approve", "approval-gated remote fetch"),
            ("/git remote pull <remote> <branch> | approve", "approval-gated fast-forward pull"),
            ("/git remote push <remote> <branch> | approve", "approval-gated remote push"),
            ("/edit replace <path> | <old> | <new> | approve", "approval-gated exact text edit"),
            ("/web fetch <url> | approve", "approval-gated terminal URL fetch"),
            ("/browser open <url> | approve", "record browser intent without auto-launch"),
            ("/browser screenshot <session-id> | <path> | approve", "attach screenshot evidence"),
            ("/test [command]", "run allowlisted tests without shell parsing"),
            ("/verify [command]", "run allowlisted verification without shell parsing"),
            ("/subagents artifacts", "list durable role artifacts"),
            ("/subagents artifacts show <artifact-id>", "show one durable role artifact"),
            ("/subagents artifacts search <query>", "search durable role artifacts"),
            ("/subagents synthesis <root-id>", "show coordinator final synthesis"),
            ("/subagents graph <root-id>", "show coordinator artifact graph"),
            ("/subagents live <task>", "delegate and stream bounded workers"),
            ("/subagents live <task> | depth 2", "delegate with opt-in nested reviewer topology"),
            ("/subagents live <task> | use-artifact <id> | approve", "delegate and stream bounded workers with approved prior context"),
            ("/subagents bg <task>", "start background subagent work"),
            ("/subagents bg <task> | depth 2", "start background subagent work with opt-in nested reviewer topology"),
            ("/subagents bg <task> | use-artifact <id> | approve", "start background subagent work with approved prior context"),
            ("/subagents monitor <job-id>", "live repaint background subagent progress"),
            ("/subagents unwatch", "stop active subagent job monitor"),
            ("/subagents recover", "recover stale background subagent jobs"),
            ("/agents", "show Hermes-style agent status"),
            ("/agents contracts", "show role context contracts and budgets"),
            ("/agents delegate <task>", "delegate to named local agent profiles"),
            ("/agents delegate <task> | depth 2", "delegate with opt-in nested reviewer topology"),
            ("/agents delegate <task> | use-artifact <id> | approve", "delegate to named local agent profiles with approved prior context"),
            ("/agents artifacts", "list durable role artifacts"),
            ("/agents artifacts show <artifact-id>", "show one durable role artifact"),
            ("/agents artifacts search <query>", "search durable role artifacts"),
            ("/agents synthesis <root-id>", "show coordinator final synthesis"),
            ("/agents graph <root-id>", "show coordinator artifact graph"),
            ("/agents live <task>", "stream Hermes-style role-worker progress"),
            ("/agents live <task> | depth 2", "stream agents with opt-in nested reviewer topology"),
            ("/agents live <task> | use-artifact <id> | approve", "stream agents with approved prior context"),
            ("/agents stream <task>", "alias for /agents live <task>"),
            ("/agents bg <task>", "start background agent work"),
            ("/agents bg <task> | depth 2", "start background agent work with opt-in nested reviewer topology"),
            ("/agents bg <task> | use-artifact <id> | approve", "start background agent work with approved prior context"),
            ("/agents jobs", "list background agent jobs"),
            ("/agents monitor <job-id>", "live repaint background agent progress"),
            ("/agents unwatch", "stop active agent job monitor"),
            ("/agents recover", "recover stale background agent jobs"),
            ("/dashboard", "show terminal operator posture"),
            ("/capabilities", "show terminal-visible parity map"),
            ("/automations create <name> | <schedule> | <prompt>", "persist a gated schedule record"),
            ("/automations missed", "show missed schedule windows"),
            ("/automations replay", "queue missed runs explicitly"),
            ("/automations tick", "run one terminal scheduler tick"),
            ("/automations worker", "run visible foreground scheduler"),
            ("/automations logs", "show scheduler logs"),
            ("/automations service", "generate service wrapper"),
            ("/automations service-status", "inspect service wrapper"),
            ("/improve propose <failure>", "record a reviewed repair proposal"),
            ("/improve implement <id>", "handoff approved repair work to a task"),
            ("/improve candidate <id>", "generate advisory repair candidate"),
            ("/improve diff <candidate-id>", "read-only patch diff review"),
            ("/improve verify <candidate-id>", "run candidate verification"),
            ("/improve apply <candidate-id>", "queue verified candidate work"),
            ("/improve complete <id>", "close evidence-backed repair work"),
        ),
    ),
    (
        "Explore",
        (
            ("/tasks", "show durable task queue"),
            ("/tasks events <id>", "show top-level task timeline"),
            ("/tasks watch <id>", "live task monitor in the TUI"),
            ("/tasks output <id>", "show recorded worker output"),
            ("/tasks logs <id>", "show worker stdout/stderr logs"),
            ("/tasks unwatch", "stop active task monitor"),
            ("/tasks recover", "mark dead detached workers failed"),
            ("/subagents", "show or run bounded local subagents"),
            ("/subagents artifacts", "list durable role artifacts"),
            ("/subagents artifacts show <artifact-id>", "show one durable role artifact"),
            ("/subagents artifacts search <query>", "search durable role artifacts"),
            ("/subagents synthesis <root-id>", "show coordinator final synthesis"),
            ("/subagents graph <root-id>", "show coordinator artifact graph"),
            ("/subagents jobs", "list background jobs"),
            ("/subagents monitor <job-id>", "live subagent job monitor in the TUI"),
            ("/subagents unwatch", "stop active subagent job monitor"),
            ("/subagents recover", "mark dead background workers failed"),
            ("/subagents watch <root-id>", "show persisted subagent timeline"),
            ("/commands [prefix]", "filter command palette"),
            ("/commands completion", "show shell completion commands for aegis completion bash/zsh/fish"),
            ("/help", "show terminal controls"),
        ),
    ),
)


def run_interactive_tui(paths: RuntimePaths, *, view: str = "command") -> bool:
    """Run the real terminal UI when stdin/stdout are attached to a TTY."""
    if os.environ.get("AEGISAGENT_TUI_CLASSIC"):
        return False
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    try:
        import curses
    except ImportError:
        return False
    curses.wrapper(lambda stdscr: _CursesAegisAgent(stdscr, paths, curses, view=view).run())
    return True


def build_interactive_panels(paths: RuntimePaths, *, active_menu: str | None = None) -> tuple[InteractivePanel, ...]:
    audit = AuditLog(paths).verify()
    sandbox = detect_sandbox()
    counts = enabled_counts()
    memory_files = sorted(paths.memory_dir.glob("*.md")) if paths.memory_dir.exists() else []
    skill_summary = SkillLoader([paths.skills_dir, Path.home() / ".aegisagent" / "skills"]).trust_summary(limit=10)
    skill_counts = skill_summary["counts"]
    if skill_counts["quarantined"]:
        skill_badge = f"{skill_counts['quarantined']} quarantine"
    elif skill_counts["review"]:
        skill_badge = f"{skill_counts['review']} review"
    else:
        skill_badge = f"{skill_counts['trusted']} trusted"
    sessions = SessionStore(paths).list(limit=5)
    automations = automation_summary(paths)
    improvements = improvement_summary(paths)
    pending_label = "clear"
    if active_menu == "setup":
        focus = (
            InteractiveItem("Next step", "Show the next concrete setup action.", "/setup next", "next"),
            InteractiveItem("Model provider", "Use model connect openai, local fallback, or subscription metadata.", "/setup model", "ready"),
            InteractiveItem("Secrets handles", "Store env names, never raw token values.", "/setup secrets", "safe"),
            InteractiveItem("Sandbox", "Prefer Docker; keep host execution gated.", "/setup sandbox", "review"),
            InteractiveItem("Connectors", "Slack, Teams, webhook, MCP, browser, Open WebUI metadata.", "/setup connectors", "gated"),
            InteractiveItem("Memory + skills", "Local memory, sessions, and SKILL.md discovery.", "/setup memory", "local"),
            InteractiveItem("First task", "Try one safe terminal task from the composer.", "/setup first-task", "next"),
            InteractiveItem("Run checks", "Metadata-only safety verification.", "/setup run-checks", "ready"),
            InteractiveItem("Hide wizard", "Keep default launch prompt-first until reset.", "/setup hide", "optional"),
        )
        title = "SETUP WIZARD"
    elif active_menu == "tools":
        focus = tuple(
            InteractiveItem(tool["name"], f"{tool['scope']} | {tool['approval']}", f"/policy {tool['name']}", tool["risk"])
            for tool in ToolRegistry().list()[:8]
        )
        title = "TOOLS MATRIX"
    else:
        focus = (
            InteractiveItem("Start setup", "Walk model, secrets, sandbox, tools, and checks.", "/setup", "next"),
            InteractiveItem("Command lanes", "Browse Hermes-style terminal commands by group or prefix.", "/commands", "map"),
            InteractiveItem("Agent contracts", "Review planner, researcher, implementer, reviewer scopes.", "/agents contracts", "bounded"),
            InteractiveItem("Agents live/bg", "Use /agents live <task>; /agents bg <task>; /agents monitor <job-id>.", "/commands agents", "ready"),
            InteractiveItem("Plain prompt", "Type a request; Aegis answers through the local terminal provider.", "", "safe"),
            InteractiveItem("Policy check", "Try /policy shell rg --files.", "/policy shell rg --files", "allow"),
            InteractiveItem("Audit verify", "Check the receipt hash chain.", "/audit", "ready"),
        )
        title = "ACTIVE CONSOLE"
    return (
        InteractivePanel(
            "nav",
            "AGENT STATUS",
            (
                InteractiveItem("Chat", "Prompt-first transcript and composer.", "", "active", "overview"),
                InteractiveItem("Setup", "Secure first-run wizard.", "", "", "setup"),
                InteractiveItem("Tools", "Governed tool policy matrix.", "", "", "tools"),
                InteractiveItem("Dashboard", "Terminal operator posture.", "/dashboard", "local"),
                InteractiveItem("Audit", "Append-only receipt chain.", "/audit", "ok" if audit["ok"] else "broken"),
                InteractiveItem("Web", "Optional secondary GUI.", "/web", "optional"),
            ),
        ),
        InteractivePanel("focus", title, focus),
        InteractivePanel(
            "posture",
            "SECURITY POSTURE",
            (
                InteractiveItem("Policy", "Default ask for network, writes, and external delivery.", "/status", "enforced"),
                InteractiveItem("Sandbox", sandbox.rationale, "/setup sandbox", sandbox.backend),
                InteractiveItem("Audit", f"{audit['count']} receipts", "/audit", "chain ok" if audit["ok"] else "review"),
                InteractiveItem("Tools", f"{counts['enabled']} enabled / {counts['ask']} ask", "/tools", "gated"),
                InteractiveItem("Approvals", "Risky actions stop for operator decision.", "/help", pending_label),
            ),
        ),
        InteractivePanel(
            "memory",
            "MEMORY + SKILLS",
            (
                InteractiveItem("Memory files", "Curated MEMORY.md / USER.md.", "/memory", str(len(memory_files))),
                InteractiveItem(
                    "Skills",
                    f"{skill_counts['trusted']} trusted / {skill_counts['review']} review / {skill_counts['quarantined']} quarantined.",
                    "/skills",
                    skill_badge,
                ),
                InteractiveItem("Sessions", "Persistent terminal transcripts.", "/sessions", str(len(sessions))),
                InteractiveItem("Automations", "Durable gated schedule records.", "/automations", str(automations["count"])),
                InteractiveItem("Improvements", "Reviewed proposals and governed handoffs.", "/improve", str(improvements["proposal_count"])),
                InteractiveItem("Agents", "Planner, researcher, implementer, reviewer.", "/agents", "bounded"),
            ),
        ),
        InteractivePanel("commands", "SLASH PALETTE", tuple(InteractiveItem(cmd, detail, cmd) for cmd, detail in SLASH_COMMANDS[:8])),
    )


class _CursesAegisAgent:
    def __init__(self, stdscr: Any, paths: RuntimePaths, curses_module: Any, *, view: str = "command") -> None:
        self.stdscr = stdscr
        self.paths = paths
        self.curses = curses_module
        self.view = view
        self.input_buffer = ""
        self.cursor = 0
        self.palette_index = 0
        self.history: list[str] = []
        self.history_index: int | None = None
        self.should_exit = False
        show_setup = setup_wizard_preferences(paths)["show_by_default"]
        self.active_menu: str | None = "setup" if view == "setup" or (view == "command" and show_setup) else "tools" if view == "tools" else None
        self.output_lines = _initial_output_lines(paths, setup_open=self.active_menu == "setup")
        self.message = "Enter send | / palette | Tab complete | arrows history | q or /exit quit"
        self._panel_item_bounds: list[tuple[PanelBounds, InteractiveItem]] = []
        self._last_palette_top = 0
        self._last_palette_rows = 0
        self.task_monitor_id: str | None = None
        self._task_monitor_next_refresh = 0.0
        self.subagent_monitor_id: str | None = None
        self._subagent_monitor_next_refresh = 0.0

    def run(self) -> None:
        try:
            self.curses.curs_set(1)
        except Exception:
            pass
        self.stdscr.keypad(True)
        self._init_colors()
        try:
            self.curses.mousemask(self.curses.ALL_MOUSE_EVENTS)
        except Exception:
            pass
        while not self.should_exit:
            self.stdscr.timeout(200 if self.task_monitor_id or self.subagent_monitor_id else -1)
            self._refresh_task_monitor()
            self._refresh_subagent_monitor()
            self._render()
            key = self.stdscr.getch()
            if key == -1:
                continue
            if key in (3, 4):
                return
            if key in (ord("q"),) and not self.input_buffer:
                return
            if key == ord("?") and not self.input_buffer:
                self._run_command("/help")
                continue
            if key == 27:
                if self.input_buffer:
                    self.input_buffer = ""
                    self.cursor = 0
                    self.palette_index = 0
                    self.message = "Input cleared."
                    continue
                return
            if key in (10, 13, getattr(self.curses, "KEY_ENTER", 343)):
                self._submit_input()
                continue
            if key in (getattr(self.curses, "KEY_BACKSPACE", 263), 127, 8):
                self._backspace()
                continue
            if key == getattr(self.curses, "KEY_LEFT", 260):
                self.cursor = max(0, self.cursor - 1)
                continue
            if key == getattr(self.curses, "KEY_RIGHT", 261):
                self.cursor = min(len(self.input_buffer), self.cursor + 1)
                continue
            if key in (getattr(self.curses, "KEY_UP", 259), getattr(self.curses, "KEY_DOWN", 258)):
                self._move_history_or_palette(-1 if key == getattr(self.curses, "KEY_UP", 259) else 1)
                continue
            if key in (9, getattr(self.curses, "KEY_BTAB", -999999)):
                self._complete_palette()
                continue
            if key == getattr(self.curses, "KEY_MOUSE", -1):
                self._handle_mouse()
                continue
            if 32 <= key <= 126:
                self._insert(chr(key))

    def _init_colors(self) -> None:
        if not self.curses.has_colors():
            return
        self.curses.start_color()
        self.curses.use_default_colors()
        for pair, fg, bg in (
            (1, self.curses.COLOR_CYAN, -1),
            (2, self.curses.COLOR_MAGENTA, -1),
            (3, self.curses.COLOR_BLACK, self.curses.COLOR_CYAN),
            (4, self.curses.COLOR_WHITE, -1),
            (5, self.curses.COLOR_YELLOW, -1),
            (6, self.curses.COLOR_GREEN, -1),
            (7, self.curses.COLOR_BLACK, self.curses.COLOR_MAGENTA),
            (8, self.curses.COLOR_RED, -1),
        ):
            try:
                self.curses.init_pair(pair, fg, bg)
            except Exception:
                pass

    def _render(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        if height < 8 or width < 40:
            self._add(0, 0, "AegisAgent needs a larger terminal.", self._pair(5))
            self.stdscr.refresh()
            return
        header_h = 4
        prompt_y = height - 2
        footer_y = height - 1
        self._draw_header(width)
        palette = self._palette_candidates()
        palette_h = min(len(palette), max(0, min(8, prompt_y - header_h - 1))) if self.input_buffer.startswith("/") else 0
        output_bottom = prompt_y - 1 - palette_h
        if palette_h:
            panel_bottom = header_h
        elif self.active_menu:
            panel_bottom = self._draw_panel_deck(header_h, output_bottom, width)
        else:
            panel_bottom = self._draw_prompt_first_strip(header_h, output_bottom, width)
        output_top = min(output_bottom, panel_bottom + 1)
        self._draw_output(output_top, output_bottom, width)
        if palette_h:
            palette_top = output_bottom + 1
            self._draw_palette(palette, palette_top, prompt_y - 1, width)
            self._last_palette_top = palette_top
            self._last_palette_rows = palette_h
        else:
            self._last_palette_top = 0
            self._last_palette_rows = 0
        self._draw_prompt(prompt_y, width)
        self._draw_footer(footer_y, width)
        self.stdscr.refresh()

    def _draw_header(self, width: int) -> None:
        audit_ok = AuditLog(self.paths).verify()["ok"]
        sandbox = "docker" if detect_sandbox().available else "gated"
        title = "AEGIS SHIELD :: terminal-first governed agent"
        status = f"policy:enforced sandbox:{sandbox} net:ask audit:{'live' if audit_ok else 'review'}"
        self._add(0, 0, self._clip(title, width - 1), self._pair(1) | self.curses.A_BOLD)
        self._add(1, 0, self._clip(status, width - 1), self._pair(6) | self.curses.A_BOLD)
        self._add(2, 0, self._clip(f"workspace {self.paths.workspace}  ::  type / for commands", width - 1), self._pair(4))
        self._add(3, 0, "-" * max(1, width - 1), self._pair(2))

    def _draw_panel_deck(self, top: int, bottom: int, width: int) -> int:
        self._panel_item_bounds = []
        available_h = bottom - top
        if available_h < 8:
            return top
        panels = build_interactive_panels(self.paths, active_menu=self.active_menu)
        columns = 3 if width >= 120 else 2 if width >= 82 else 1
        rows = 2 if available_h >= 18 and columns > 1 else 1
        count = min(len(panels), columns * rows)
        panel_h = max(6, min(9, (available_h - (rows - 1)) // rows))
        panel_w = max(24, (width - (columns - 1)) // columns)
        used = top
        for index, panel in enumerate(panels[:count]):
            row = index // columns
            col = index % columns
            y = top + row * (panel_h + 1)
            x = col * (panel_w + 1)
            w = min(panel_w, width - x - 1)
            bound = PanelBounds(panel.panel_id, y, x, panel_h, w)
            self._box(bound, panel.title, self._pair(1 if panel.panel_id == "focus" else 4) | self.curses.A_BOLD)
            for offset, item in enumerate(panel.items[: max(0, panel_h - 2)]):
                marker = ">" if item.command or item.menu else " "
                status = f" [{item.status}]" if item.status else ""
                item_y = y + 1 + offset
                label = self._clip(f"{marker} {item.label}{status}", w - 2)
                attr = self._pair(6) | self.curses.A_BOLD if item.command or item.menu else self._pair(4)
                self._add(item_y, x + 1, label, attr)
                if item.command or item.menu:
                    self._panel_item_bounds.append((PanelBounds(panel.panel_id, item_y, x + 1, 1, w - 2), item))
            used = max(used, y + panel_h)
        return min(bottom, used)

    def _draw_prompt_first_strip(self, top: int, bottom: int, width: int) -> int:
        self._panel_item_bounds = []
        if bottom - top < 4:
            return top
        audit = AuditLog(self.paths).verify()
        counts = enabled_counts()
        sessions = SessionStore(self.paths).list(limit=1)
        session_label = sessions[0]["id"] if sessions else "main"
        rows = [
            f"session {session_label} | provider local/terminal-v0 | audit {'ok' if audit['ok'] else 'review'} ({audit['count']} receipts)",
            f"tools {counts['enabled']} on / {counts['ask']} ask | subagents opt-in depth<=2 | web optional, never auto-started",
            "try: /commands  /dashboard  /capabilities  /improve  /git status  /agents bg <task>",
        ]
        border = "-" * max(1, width - 1)
        self._add(top, 0, self._clip(border, width - 1), self._pair(2))
        for offset, line in enumerate(rows, start=1):
            attr = self._pair(6) | self.curses.A_BOLD if offset == 1 else self._pair(4)
            self._add(top + offset, 1, self._clip(line, width - 2), attr)
        self._add(top + len(rows) + 1, 0, self._clip(border, width - 1), self._pair(2))
        return min(bottom, top + len(rows) + 1)

    def _draw_output(self, top: int, bottom: int, width: int) -> None:
        if bottom <= top:
            return
        visible = _wrap_lines(self.output_lines, width - 2)[-(bottom - top) :]
        for offset, line in enumerate(visible):
            self._add(top + offset, 1, self._clip(line, width - 2), self._pair(4))

    def _draw_palette(self, palette: list[tuple[str, str]], top: int, bottom: int, width: int) -> None:
        self._add(top, 0, self._clip(" slash palette ", width - 1), self._pair(2) | self.curses.A_BOLD)
        for offset, (command, detail) in enumerate(palette[: max(0, bottom - top)], start=1):
            attr = self._pair(3) | self.curses.A_BOLD if offset - 1 == self.palette_index else self._pair(4)
            self._add(top + offset, 1, self._clip(f"{command:<22} {detail}", width - 2), attr)

    def _draw_prompt(self, y: int, width: int) -> None:
        prompt = "aegis> "
        self._add(y, 0, " " * max(1, width - 1), self._pair(1))
        self._add(y, 0, self._clip(prompt + self.input_buffer, width - 1), self._pair(1) | self.curses.A_BOLD)
        try:
            self.stdscr.move(y, min(width - 2, len(prompt) + self.cursor))
        except Exception:
            pass

    def _draw_footer(self, y: int, width: int) -> None:
        self._add(y, 0, " " * max(1, width - 1), self._pair(7))
        self._add(y, 1, self._clip(self.message, width - 2), self._pair(7))

    def _submit_input(self) -> None:
        command = self.input_buffer.strip()
        if not command:
            self.message = "Type a request or /command."
            return
        if command.startswith("/"):
            if command == "/":
                self.message = "Slash palette open; type more, use arrows, Tab, or click a row."
                return
            candidates = self._palette_candidates()
            exact = any(command == candidate for candidate, _detail in candidates)
            if candidates and not exact:
                command = candidates[min(self.palette_index, len(candidates) - 1)][0]
        self.history.append(command)
        self.history_index = None
        self.input_buffer = ""
        self.cursor = 0
        self.palette_index = 0
        self._run_command(command)

    def _run_command(self, command: str) -> None:
        normalized = normalize_interactive_command(command)
        if normalized in {"/exit", "/quit", "exit", "quit"}:
            self.should_exit = True
            return
        if normalized in {"/tasks unwatch", "/tasks stop-watch", "/tasks stop watch"}:
            self.task_monitor_id = None
            self._task_monitor_next_refresh = 0.0
            self.message = "Task monitor stopped."
            self.output_lines = [f"$ {normalized}", "", "Task monitor stopped. Composer remains active."]
            return
        if normalized in {"/subagents unwatch", "/subagents stop-watch", "/subagents stop watch", "/agents unwatch", "/agents stop-watch", "/agents stop watch"}:
            self.subagent_monitor_id = None
            self._subagent_monitor_next_refresh = 0.0
            self.message = "Agent job monitor stopped."
            self.output_lines = [f"$ {normalized}", "", "Agent job monitor stopped. Composer remains active."]
            return
        if normalized.startswith("/subagents live ") or normalized.startswith("/subagents stream ") or normalized.startswith("/agents live ") or normalized.startswith("/agents stream "):
            task = normalized.split(maxsplit=2)[2].strip()
            self._run_live_subagents(task, command=normalized.rsplit(task, 1)[0].strip() + f" {task}")
            return
        if normalized.startswith("/subagents monitor ") or normalized.startswith("/subagents live-job ") or normalized.startswith("/agents monitor "):
            self._start_subagent_monitor(normalized.split(maxsplit=2)[2].strip())
            return
        if normalized.startswith("/tasks watch ") or normalized.startswith("/tasks live "):
            self._start_task_monitor(normalized.split(maxsplit=2)[2].strip())
            return
        output = io.StringIO()
        with redirect_stdout(output):
            handled = dispatch_interactive_command(normalized, self.paths)
        text = output.getvalue().strip()
        self.output_lines = [f"$ {normalized}", ""] + (text.splitlines() if text else [handled or "Command complete."])
        if normalized in {"/setup hide", "/setup dismiss"}:
            self.active_menu = None
        elif normalized.startswith("/setup"):
            self.active_menu = "setup"
        elif normalized.startswith("/tools") or normalized.startswith("/policy"):
            self.active_menu = "tools"
        elif normalized.startswith("/status"):
            self.active_menu = None
        self.message = f"Opened: {normalized}"

    def _run_live_subagents(self, task: str, *, command: str = "/subagents live") -> None:
        try:
            task, artifact_ids, approved, requested_depth = _parse_artifact_reuse_directive(task)
        except ValueError as exc:
            self.output_lines = [f"$ {command}", "", f"Delegation blocked: {exc}"]
            self.message = "Delegation blocked."
            self._render()
            return
        if not task:
            self.output_lines = [f"$ {command}", "", f"Usage: {command} <task>"]
            self.message = "Add a task to stream agent work."
            self._render()
            return
        self.output_lines = [f"$ {command}", "", "SUBAGENT LIVE", "starting coordinator..."]
        self.message = "Streaming agent events..."
        self._render()

        def sink(event: Any) -> None:
            self.output_lines.append(format_event_line(event))
            self._render()

        try:
            result = LocalSubagentOrchestrator(self.paths).delegate(task, reusable_artifact_ids=artifact_ids, reuse_approved=approved, requested_depth=requested_depth, event_sink=sink)
        except (KeyError, ValueError) as exc:
            self.output_lines = [f"$ {command}", "", f"Delegation blocked: {exc}"]
            self.message = "Delegation blocked."
            self._render()
            return
        self.output_lines.extend(["", f"root      {result.root.id}  {result.root.status}", f"receipt   {result.receipt_id}"])
        self.message = f"Agents completed: {result.root.id}"
        self._render()

    def _start_subagent_monitor(self, job_id: str) -> None:
        if not job_id:
            self.output_lines = ["$ /subagents monitor", "", "Usage: /subagents monitor <job-id>"]
            self.message = "Add a background subagent job id to monitor."
            self._render()
            return
        command = f"/subagents monitor {job_id}"
        self.subagent_monitor_id = job_id
        self._subagent_monitor_next_refresh = 0.0
        self.output_lines = _subagent_job_monitor_lines(self.paths, job_id, command=command)
        status = _subagent_job_status(self.paths, job_id)
        if status in {"completed", "failed", "cancelled", "unknown"}:
            self.subagent_monitor_id = None
            self.message = f"Subagent job monitor opened final state: {status}"
        else:
            self.message = f"Monitoring subagent job {job_id}; composer remains active. Use /subagents unwatch to stop."
        self._render()

    def _refresh_subagent_monitor(self, *, force: bool = False) -> None:
        if not self.subagent_monitor_id:
            return
        now = time.monotonic()
        if not force and now < self._subagent_monitor_next_refresh:
            return
        job_id = self.subagent_monitor_id
        command = f"/subagents monitor {job_id}"
        self.output_lines = _subagent_job_monitor_lines(self.paths, job_id, command=command)
        status = _subagent_job_status(self.paths, job_id)
        if status in {"completed", "failed", "cancelled", "unknown"}:
            self.subagent_monitor_id = None
            self._subagent_monitor_next_refresh = 0.0
            self.message = f"Subagent job monitor stopped: {status}"
            return
        self.message = f"Monitoring agent job {job_id}; composer active. Use /agents unwatch to stop."
        self._subagent_monitor_next_refresh = now + 0.5

    def _start_task_monitor(self, task_id: str) -> None:
        if not task_id:
            self.output_lines = ["$ /tasks watch", "", "Usage: /tasks watch <task-id>"]
            self.message = "Add a task id to watch progress."
            self._render()
            return
        command = f"/tasks watch {task_id}"
        self.task_monitor_id = task_id
        self._task_monitor_next_refresh = 0.0
        self.output_lines = _task_watch_lines(self.paths, task_id, command=command)
        status = _task_status(self.paths, task_id)
        if status in {"completed", "failed", "cancelled", "unknown"}:
            self.task_monitor_id = None
            self.message = f"Task monitor opened final state: {status}"
        else:
            self.message = f"Monitoring {task_id}; composer remains active. Use /tasks unwatch to stop."
        self._render()

    def _refresh_task_monitor(self, *, force: bool = False) -> None:
        if not self.task_monitor_id:
            return
        now = time.monotonic()
        if not force and now < self._task_monitor_next_refresh:
            return
        task_id = self.task_monitor_id
        command = f"/tasks watch {task_id}"
        self.output_lines = _task_watch_lines(self.paths, task_id, command=command)
        status = _task_status(self.paths, task_id)
        if status in {"completed", "failed", "cancelled", "unknown"}:
            self.task_monitor_id = None
            self._task_monitor_next_refresh = 0.0
            self.message = f"Task monitor stopped: {status}"
            return
        self.message = f"Monitoring {task_id}; composer active. Use /tasks unwatch to stop."
        self._task_monitor_next_refresh = now + 0.5

    def _move_history_or_palette(self, delta: int) -> None:
        palette = self._palette_candidates()
        if self.input_buffer.startswith("/") and palette:
            self.palette_index = max(0, min(len(palette) - 1, self.palette_index + delta))
            self.message = f"Highlighted {palette[self.palette_index][0]}; Tab accepts it."
            return
        if not self.history:
            return
        if self.history_index is None:
            self.history_index = len(self.history) if delta < 0 else len(self.history) - 1
        self.history_index = max(0, min(len(self.history) - 1, self.history_index + delta))
        self.input_buffer = self.history[self.history_index]
        self.cursor = len(self.input_buffer)

    def _complete_palette(self) -> None:
        palette = self._palette_candidates()
        if not palette:
            self.message = "No slash command matches."
            return
        command = palette[min(self.palette_index, len(palette) - 1)][0]
        self.input_buffer = command + (" " if command in {"/policy shell", "/read", "/git diff", "/git stage", "/git commit", "/git branch", "/git remote", "/edit replace", "/test", "/verify", "/sessions search", "/submit", "/add-dir", "/memory add", "/memory search", "/memory show", "/memory delete", "/connectors draft", "/connectors send", "/web fetch", "/browser open", "/browser screenshot", "/tasks submit", "/tasks bg", "/tasks run", "/tasks start", "/tasks events", "/tasks output", "/tasks logs", "/tasks watch", "/tasks cancel", "/automations create", "/automations trigger", "/automations pause", "/automations resume", "/automations delete", "/improve propose", "/improve approve", "/improve implement", "/improve handoff", "/improve candidate", "/improve diff", "/improve verify", "/improve apply", "/improve evidence", "/improve complete", "/improve reject", "/model connect", "/subagents bg", "/subagents live", "/subagents monitor", "/subagents cancel", "/subagents synthesis", "/subagents graph", "/subagents artifacts show", "/subagents artifacts search", "/agents delegate", "/agents bg", "/agents live", "/agents monitor", "/agents cancel", "/agents synthesis", "/agents graph", "/agents artifacts show", "/agents artifacts search", "/q"} else "")
        self.cursor = len(self.input_buffer)
        self.message = f"Completed {command}; add args or press Enter."

    def _palette_candidates(self) -> list[tuple[str, str]]:
        return slash_palette_candidates(self.input_buffer)

    def _handle_mouse(self) -> None:
        try:
            _mouse_id, x, y, _z, _state = self.curses.getmouse()
        except Exception:
            return
        palette = self._palette_candidates()
        if palette and self._last_palette_top <= y <= self._last_palette_top + self._last_palette_rows:
            index = y - self._last_palette_top - 1
            if index >= 0:
                self.palette_index = max(0, min(len(palette) - 1, index))
                self._complete_palette()
            return
        for bound, item in self._panel_item_bounds:
            if bound.y <= y < bound.y + bound.h and bound.x <= x < bound.x + bound.w:
                if item.menu:
                    self.active_menu = None if item.menu == "overview" else item.menu
                    self.message = f"Menu: {item.label}"
                    if not item.command:
                        return
                if item.command:
                    self._run_command(item.command)
                return

    def _insert(self, text: str) -> None:
        self.input_buffer = self.input_buffer[: self.cursor] + text + self.input_buffer[self.cursor :]
        self.cursor += len(text)
        self.palette_index = 0

    def _backspace(self) -> None:
        if self.cursor <= 0:
            return
        self.input_buffer = self.input_buffer[: self.cursor - 1] + self.input_buffer[self.cursor :]
        self.cursor -= 1
        self.palette_index = 0

    def _box(self, bound: PanelBounds, title: str, attr: int) -> None:
        horizontal = "-" * max(0, bound.w - 2)
        self._add(bound.y, bound.x, "+" + horizontal + "+", attr)
        for row in range(1, bound.h - 1):
            self._add(bound.y + row, bound.x, "|", attr)
            self._add(bound.y + row, bound.x + bound.w - 1, "|", attr)
        self._add(bound.y + bound.h - 1, bound.x, "+" + horizontal + "+", attr)
        self._add(bound.y, bound.x + 2, self._clip(f" {title} ", bound.w - 4), attr)

    def _add(self, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            self.stdscr.addstr(y, x, text, attr)
        except Exception:
            pass

    def _clip(self, text: str, width: int) -> str:
        if width <= 0:
            return ""
        return text[:width].ljust(width)

    def _pair(self, number: int) -> int:
        try:
            return self.curses.color_pair(number)
        except Exception:
            return 0


def _parse_artifact_reuse_directive(raw: str) -> tuple[str, list[str], bool, int]:
    parts = [part.strip() for part in raw.split("|")]
    prompt = parts[0].strip() if parts else ""
    artifact_ids: list[str] = []
    approved = False
    requested_depth = 1
    for part in parts[1:]:
        lowered = part.lower()
        if lowered in {"approve", "approved"}:
            approved = True
            continue
        if lowered.startswith("use-artifact ") or lowered.startswith("artifact ") or lowered.startswith("artifacts "):
            values = part.split(maxsplit=1)[1] if " " in part else ""
            artifact_ids.extend(item.strip() for item in values.replace(",", " ").split() if item.strip())
            continue
        if lowered.startswith("depth "):
            value = part.split(maxsplit=1)[1] if " " in part else ""
            try:
                requested_depth = int(value)
            except ValueError as exc:
                raise ValueError("depth directive must be 1 or 2") from exc
            if requested_depth not in {1, 2}:
                raise ValueError("depth directive must be 1 or 2")
            continue
    return prompt, list(dict.fromkeys(artifact_ids)), approved, requested_depth


def _delegate_with_reuse(orchestrator: LocalSubagentOrchestrator, task: str) -> Any:
    prompt, artifact_ids, approved, requested_depth = _parse_artifact_reuse_directive(task)
    return orchestrator.delegate(prompt, reusable_artifact_ids=artifact_ids, reuse_approved=approved, requested_depth=requested_depth)


def _start_background_with_reuse(orchestrator: LocalSubagentOrchestrator, task: str) -> Any:
    prompt, artifact_ids, approved, requested_depth = _parse_artifact_reuse_directive(task)
    return orchestrator.start_background(prompt, reusable_artifact_ids=artifact_ids, reuse_approved=approved, requested_depth=requested_depth)


def dispatch_interactive_command(command: str, paths: RuntimePaths) -> str:
    audit = AuditLog(paths)
    normalized = normalize_interactive_command(command)
    if normalized != command:
        command = normalized
    if command in {"/help", "help", "?"}:
        print("AegisAgent TUI controls")
        print("- Enter sends the prompt, dispatches the selected slash command, or confirms the focused item.")
        print("- Type normally to run a local agent turn in the persistent terminal session.")
        print("- Type / to open slash commands; Tab accepts the highlighted command.")
        print("- Arrow keys move through history, setup cards, or slash palette candidates.")
        print("- Esc clears transient input or leaves the current overlay.")
        print("- Use /commands for grouped Hermes-style command lanes.")
        print("- Use /activation to show the exact terminal startup path.")
        print("- Use /dashboard for a terminal-only operator posture summary.")
        print("- Use /install and /update for macOS/Linux terminal lifecycle commands.")
        print("- Outside the TUI, use `aegis completion zsh|bash|fish` for shell completion.")
        print("- Use /capabilities or /gaps to inspect Hermes-class parity from the terminal.")
        print("- Use /automations to manage durable gated schedule records.")
        print("- Use /improve to track reviewed self-improvement proposals.")
        print("- Use /run <command> for policy-allowed local commands with audit receipts.")
        print("- Click or select panels in terminals that support mouse events.")
        print("- Web is optional: use /web only when you want the browser console.")
        print("- Exit with q, Esc, /exit, or /quit.")
        return "help"
    if _slash_invoked(command, "/activation") or _slash_invoked(command, "/activate"):
        print(format_terminal_activation(terminal_activation_payload(paths)))
        return "activation"
    if command.startswith("/commands") or command.startswith("/menu"):
        prefix = ""
        emit_json = False
        if command.startswith("/commands"):
            raw = command.removeprefix("/commands").strip()
            emit_json = raw == "json" or raw.endswith(" --json")
            prefix = raw.removesuffix("--json").strip()
            if prefix == "json":
                prefix = ""
        elif command.startswith("/menu"):
            prefix = command.removeprefix("/menu").strip()
        if emit_json:
            print_json(command_catalog_payload(paths, prefix=prefix))
        else:
            print(render_command_lanes(command_catalog_payload(paths, prefix=prefix)))
        return "commands"
    if _slash_invoked(command, "/dashboard"):
        print(format_dashboard(dashboard_payload(paths)))
        return "dashboard"
    if _slash_invoked(command, "/install"):
        raw = _slash_remainder(command, "/install")
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        tokens = parts[0].split()
        mode = tokens[0] if tokens else "status"
        name = tokens[1] if len(tokens) > 1 else "aegis"
        if mode not in {"status", "shim"}:
            print("Usage: /install [status] | /install shim [name] | approve")
        elif mode == "status":
            print(format_install_status(install_status_payload(paths, name=name)))
        else:
            result = install_terminal_shim(paths, name=name, approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "install"
    if _slash_invoked(command, "/update"):
        raw = _slash_remainder(command, "/update")
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        tokens = parts[0].split()
        remote_name = tokens[0] if tokens else "origin"
        branch_name = tokens[1] if len(tokens) > 1 else "main"
        result = update_from_github(paths, remote=remote_name, branch=branch_name, approved=approved)
        _print_workspace_tool(result, audit, paths, display_content=format_update_status(result))
        return "update"
    if command.startswith("/clear"):
        print("Visible output cleared. Session transcripts and audit receipts were not modified.")
        return "clear"
    if command.startswith("/new") or command.startswith("/reset"):
        title = command.split(maxsplit=1)[1] if " " in command else "main"
        session = SessionStore(paths).create(title)
        receipt = audit.append("session.created", {"session_id": session.id, "title": session.title, "source": "tui"})
        print_json({"session": {"id": session.id, "title": session.title}, "receipt": receipt["id"]})
        return "session"
    if command.startswith("/submit"):
        prompt = command.removeprefix("/submit").strip()
        if not prompt:
            print("Usage: /submit <request>")
            return "submit"
        turn = AgentRuntime(paths).respond(prompt, source="tui")
        print(turn.assistant_message)
        print(f"audit receipt: {turn.receipt_id}")
        return "agent turn"
    if command.startswith("/q"):
        task_prompt = command.removeprefix("/q").strip()
        if not task_prompt:
            print("Usage: /q <request>")
            return "tasks"
        record = TaskRunner(paths).submit(task_prompt, source="tui")
        print(format_task(record))
        print("")
        print(f"run: /tasks run {record.id}")
        return "tasks"
    if command.startswith("/tasks"):
        task_args = command.removeprefix("/tasks").strip()
        runner = TaskRunner(paths)
        if not task_args or task_args == "list":
            print(format_tasks(runner.list()))
        elif task_args.startswith("submit "):
            record = runner.submit(task_args.removeprefix("submit ").strip(), source="tui")
            print(format_task(record))
            print("")
            print(f"run: /tasks run {record.id}")
        elif task_args.startswith("bg "):
            record = runner.submit_background(task_args.removeprefix("bg ").strip(), source="tui")
            print(format_task(record))
            print("")
            print(f"watch: /tasks watch {record.id}")
        elif task_args.startswith("background "):
            record = runner.submit_background(task_args.removeprefix("background ").strip(), source="tui")
            print(format_task(record))
            print("")
            print(f"watch: /tasks watch {record.id}")
        elif task_args.startswith("start "):
            print(format_task(runner.start_background(task_args.removeprefix("start ").strip())))
        elif task_args.startswith("run "):
            print(format_task(runner.run(task_args.removeprefix("run ").strip())))
        elif task_args.startswith("show "):
            print(format_task(runner.get(task_args.removeprefix("show ").strip())))
        elif task_args.startswith("events ") or task_args.startswith("timeline "):
            task_id = task_args.split(maxsplit=1)[1] if " " in task_args else ""
            print(format_task_events(runner.events(task_id)))
        elif task_args.startswith("output ") or task_args.startswith("outputs "):
            task_id = task_args.split(maxsplit=1)[1] if " " in task_args else ""
            print(format_task_outputs(runner.outputs(task_id)))
        elif task_args.startswith("logs ") or task_args.startswith("log "):
            task_id = task_args.split(maxsplit=1)[1] if " " in task_args else ""
            print(format_task_worker_logs(runner.worker_logs(task_id)))
        elif task_args.startswith("watch ") or task_args.startswith("live "):
            task_id = task_args.split(maxsplit=1)[1] if " " in task_args else ""
            print("\n".join(_task_watch_lines(paths, task_id, command=f"/tasks watch {task_id}".rstrip())))
        elif task_args in {"unwatch", "stop-watch", "stop watch"}:
            print("No active task monitor in static dispatch. In the live TUI this stops the nonblocking task monitor.")
        elif task_args in {"recover", "recover-stale"}:
            recovered = runner.recover_stale_running()
            print(format_tasks([record.to_dict() for record in recovered]) if recovered else "No stale running tasks found.")
        elif task_args.startswith("cancel "):
            print(format_task(runner.cancel(task_args.removeprefix("cancel ").strip())))
        else:
            print("Usage: /tasks | /tasks submit <request> | /tasks bg <request> | /tasks start <id> | /tasks run <id> | /tasks show <id> | /tasks events <id> | /tasks output <id> | /tasks logs <id> | /tasks watch <id> | /tasks unwatch | /tasks recover | /tasks cancel <id>")
        return "tasks"
    if command.startswith("/add-dir"):
        raw_path = command.removeprefix("/add-dir").strip()
        if not raw_path:
            print("Usage: /add-dir <path>")
            return "add-dir"
        target = (paths.workspace / raw_path).expanduser().resolve() if not Path(raw_path).expanduser().is_absolute() else Path(raw_path).expanduser().resolve()
        try:
            target.relative_to(paths.workspace)
        except ValueError:
            print_json({"path": raw_path, "status": "blocked", "reason": "context directories must stay inside the workspace"})
            return "add-dir"
        if not target.is_dir():
            print_json({"path": str(target), "status": "blocked", "reason": "directory does not exist"})
            return "add-dir"
        rel = str(target.relative_to(paths.workspace))
        receipt = audit.append("session.context_dir_added", {"path": rel, "source": "tui"})
        SessionStore(paths).append("main", "tool", f"Context directory added: {rel}", metadata={"source": "tui", "tool": "session.add_dir", "path": rel, "receipt_id": receipt["id"]})
        print_json({"path": rel, "status": "ok", "receipt": receipt["id"]})
        return "add-dir"
    if command.startswith("/model connect") or command.startswith("/models connect"):
        raw = command.removeprefix("/model connect").removeprefix("/models connect").strip()
        parts = raw.split()
        provider = parts[0] if parts else "openai"
        try:
            payload = ProviderStore(paths).connect(provider, source="tui")
        except ValueError as exc:
            print_json({"status": "blocked", "error": str(exc), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
        else:
            print(format_provider_connect(payload))
        return "models"
    if command in {"/model auth status", "/model auth methods", "/models auth status", "/models auth methods"} or command.startswith("/model auth status") or command.startswith("/model auth methods") or command.startswith("/models auth status") or command.startswith("/models auth methods"):
        print_json(ProviderStore(paths).auth_status())
        return "models"
    if command in {"/model auth doctor", "/models auth doctor"} or command.startswith("/model auth doctor") or command.startswith("/models auth doctor"):
        print_json(ProviderStore(paths).doctor())
        return "models"
    if command.startswith("/model auth login") or command.startswith("/model auth logout") or command.startswith("/models auth login") or command.startswith("/models auth logout"):
        print_json(
            {
                "status": "unsupported",
                "reason": "Aegis does not browser-login or logout from model providers; connect by environment handle instead.",
                "next": "aegis model connect openai",
                "browser_auto_launch": False,
                "gateway_started": False,
                "external_action_started": False,
                "model_invocation_performed": False,
                "raw_secret_values_included": False,
            }
        )
        return "models"
    if command.startswith("/model auth") or command.startswith("/models auth"):
        print("Usage: /model auth status | /model auth methods | /model auth doctor")
        return "models"
    if command in {"/model doctor", "/models doctor", "/provider doctor"} or command.startswith("/model doctor") or command.startswith("/models doctor"):
        print_json(ProviderStore(paths).doctor())
        return "models"
    if command in {"/model usage", "/models usage", "/provider usage"} or command.startswith("/model usage") or command.startswith("/models usage"):
        limit_text = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) == 3 else ""
        limit = int(limit_text) if limit_text.isdigit() else 20
        print_json(ProviderUsageStore(paths).summary(limit=limit))
        return "models"
    if command in {"/model", "/models", "/provider", "/model providers", "/models providers"} or command.startswith("/model providers") or command.startswith("/models providers"):
        print_json(ProviderStore(paths).summary())
        return "models"
    if _slash_invoked(command, "/connectors draft"):
        raw = _slash_remainder(command, "/connectors draft")
        parts = [part.strip() for part in raw.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            print("Usage: /connectors draft <name> | <target> | <message>")
        else:
            try:
                print_json(ConnectorStore(paths).draft(parts[0], target=parts[1], message=parts[2], source="tui"))
            except (KeyError, ValueError) as exc:
                print_json({"status": "blocked", "reason": str(exc), "external_delivery_performed": False, "browser_auto_launch": False})
        return "connectors"
    if _slash_invoked(command, "/connectors send"):
        raw = _slash_remainder(command, "/connectors send")
        parts = [part.strip() for part in raw.split("|", 3)]
        approved = len(parts) == 4 and parts[3].lower() in {"approve", "approved", "yes"}
        if len(parts) < 3 or not all(parts[:3]):
            print("Usage: /connectors send <name> | <target> | <message> | approve")
        else:
            try:
                print_json(ConnectorStore(paths).send(parts[0], target=parts[1], message=parts[2], approved=approved, source="tui"))
            except (KeyError, ValueError) as exc:
                print_json({"status": "blocked", "reason": str(exc), "external_delivery_performed": False, "browser_auto_launch": False})
        return "connectors"
    if _slash_invoked(command, "/connectors outbox"):
        print_json(
            {
                "outbox": ConnectorStore(paths).outbox(limit=20),
                "external_action_started": False,
                "external_delivery_performed": False,
                "browser_auto_launch": False,
            }
        )
        return "connectors"
    if command in {"/connectors doctor", "/connector doctor"} or command.startswith("/connectors doctor"):
        print_json(ConnectorStore(paths).doctor())
        return "connectors"
    if command in {"/connectors", "/connector"} or command.startswith("/connectors list"):
        print_json(ConnectorStore(paths).summary())
        return "connectors"
    if command.startswith("/capabilities") or command.startswith("/capability map"):
        print(format_capabilities(capability_map(paths)))
        return "capabilities"
    if command.startswith("/gaps") or command.startswith("/capability gaps"):
        print(format_capabilities(capability_map(paths), gaps_only=True))
        return "capabilities"
    if command.startswith("/setup"):
        setup_args = command.removeprefix("/setup").strip()
        setup_args = normalize_setup_section(setup_args)
        setup_guide = SetupGuide(paths)
        if setup_args in {"hide", "dismiss"}:
            state = update_setup_wizard_preferences(paths, hidden=True)
            receipt = audit.append(
                "setup.ui_preferences",
                {
                    "hidden": True,
                    "source": "tui",
                    "terminal_first": True,
                    "browser_auto_launch": False,
                    "external_action_started": False,
                    "raw_secret_values_included": False,
                },
            )
            print("Aegis setup wizard is now hidden on default TUI launch.")
            print("The terminal composer remains primary. Use /setup reset to show it by default again.")
            print_json({"setup_wizard": state, "receipt": receipt["id"]})
            return "setup"
        if setup_args == "reset":
            state = update_setup_wizard_preferences(paths, hidden=False)
            receipt = audit.append(
                "setup.ui_preferences",
                {
                    "hidden": False,
                    "source": "tui",
                    "terminal_first": True,
                    "browser_auto_launch": False,
                    "external_action_started": False,
                    "raw_secret_values_included": False,
                },
            )
            print("Aegis setup wizard is now shown on default TUI launch.")
            print("It stays inside the terminal and does not start the Web GUI.")
            print_json({"setup_wizard": state, "receipt": receipt["id"]})
            return "setup"
        if setup_args == "first-task":
            print(format_setup_first_task(setup_guide.first_task_payload()))
            return "setup"
        if setup_args == "json":
            print_json(setup_guide.quickstart())
            return "setup"
        if setup_args in {"next", "continue"}:
            print(format_setup_next(setup_guide.priority()))
            return "setup"
        if setup_args == "model":
            print(format_setup_section(setup_guide.section("model")))
            return "setup"
        if setup_args in SETUP_SECTIONS:
            print(format_setup_section(setup_guide.section(setup_args)))
            return "setup"
        if setup_args == "run-checks":
            print_json(setup_guide.run_checks())
            return "setup"
        command_name = terminal_command_name()
        print(format_setup_quickstart(setup_guide.quickstart()))
        print(f"Terminal activation: {command_name} tui")
        print(f"Next setup step: {command_name} setup next")
        print(f"Fallback static frame: {command_name} tui --print")
        return "setup"
    if command.startswith("/tools"):
        print(render(TuiState(view="tools"), width=120, height=28))
        return "tools"
    if command.startswith("/audit"):
        print_json(audit.verify())
        return "audit"
    if _slash_invoked(command, "/memory search"):
        query = _slash_remainder(command, "/memory search")
        if not query:
            print("Usage: /memory search <query>")
        else:
            print_json(MemoryStore(paths).search(query, limit=20))
        return "memory"
    if _slash_invoked(command, "/memory index"):
        print_json({"indexed": MemoryStore(paths).index_curated_files()})
        return "memory"
    if command.startswith("/memory add"):
        raw = command.removeprefix("/memory add").strip()
        parts = [part.strip() for part in raw.split("|", 3)]
        approved = len(parts) >= 4 and parts[3].lower() in {"approve", "approved", "yes"}
        if len(parts) < 3 or not all(parts[:3]):
            print("Usage: /memory add <workspace|user> | <title> | <body> | approve")
        else:
            result = MemoryStore(paths).add_curated_note(parts[0], parts[1], parts[2], approved=approved)
            receipt = audit.append(
                "memory.note.add",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print_json({**result, "receipt": receipt["id"]})
        return "memory"
    if _slash_invoked(command, "/memory list") or _slash_invoked(command, "/memory review"):
        raw = _slash_remainder(command, "/memory list") if _slash_invoked(command, "/memory list") else _slash_remainder(command, "/memory review")
        tokens = raw.split()
        kind = tokens[0] if tokens and tokens[0] in {"workspace", "user"} else ""
        result = MemoryStore(paths).list_curated_entries(kind=kind, limit=50)
        audit.append(
            "memory.note.list",
            {
                "status": result["status"],
                "metadata": result.get("metadata", {}),
                "external_action_started": False,
                "browser_auto_launch": False,
            },
        )
        print_json(result)
        return "memory"
    if _slash_invoked(command, "/memory show"):
        entry_id = _slash_remainder(command, "/memory show")
        if not entry_id:
            print("Usage: /memory show <entry-id>")
        else:
            result = MemoryStore(paths).show_curated_entry(entry_id)
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
            print_json(result)
        return "memory"
    if _slash_invoked(command, "/memory delete"):
        raw = _slash_remainder(command, "/memory delete")
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        entry_id = parts[0]
        if not entry_id:
            print("Usage: /memory delete <entry-id> | approve")
        else:
            result = MemoryStore(paths).delete_curated_entry(entry_id, approved=approved)
            receipt = audit.append(
                "memory.note.delete",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print_json({**result, "receipt": receipt["id"]})
        return "memory"
    if command.startswith("/memory"):
        store = MemoryStore(paths)
        indexed = store.index_curated_files()
        print_json({"indexed": indexed, "results": store.search("AegisAgent", limit=5)})
        return "memory"
    if _slash_invoked(command, "/skills manifest"):
        raw = _slash_remainder(command, "/skills manifest")
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        tokens = parts[0].split()
        skill_name = tokens[0] if tokens else ""
        if not skill_name:
            print("Usage: /skills manifest <skill-name> | approve")
        else:
            result = SkillLoader([paths.skills_dir, Path.home() / ".aegisagent" / "skills"]).author_manifest(skill_name, approved=approved)
            receipt = audit.append(
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
            print_json({**result, "receipt": receipt["id"]})
        return "skills"
    if command.startswith("/skills"):
        loader = SkillLoader([paths.skills_dir, Path.home() / ".aegisagent" / "skills"])
        summary = loader.trust_summary(limit=10)
        receipt = AuditLog(paths).append("skills.discover", skill_audit_payload(loader.trust_summary()))
        print_json({**summary, "receipt": receipt["id"]})
        return "skills"
    if command.startswith("/read"):
        relative_path = command.removeprefix("/read").strip()
        if not relative_path:
            print("Usage: /read <workspace-file>")
            return "read"
        result = WorkspaceToolRunner(paths).read_file(relative_path)
        _print_workspace_tool(result, audit, paths)
        return "read"
    if command.startswith("/git status"):
        result = WorkspaceToolRunner(paths).git_status()
        _print_workspace_tool(result, audit, paths)
        return "git status"
    if command.startswith("/git diff"):
        relative_path = command.removeprefix("/git diff").strip() or None
        result = WorkspaceToolRunner(paths).git_diff(relative_path)
        _print_workspace_tool(result, audit, paths)
        return "git diff"
    if command.startswith("/git stage"):
        raw = command.removeprefix("/git stage").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        stage_paths = [part.strip().strip(",") for part in parts[0].split() if part.strip().strip(",")]
        if not stage_paths:
            print("Usage: /git stage <path> [path...] | approve")
        else:
            result = WorkspaceToolRunner(paths).git_stage(stage_paths, approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "git stage"
    if command.startswith("/git commit"):
        raw = command.removeprefix("/git commit").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        if not parts[0]:
            print("Usage: /git commit <message> | approve")
        else:
            result = WorkspaceToolRunner(paths).git_commit(parts[0], approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "git commit"
    if command.startswith("/git branch"):
        raw = command.removeprefix("/git branch").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        tokens = parts[0].split()
        operation = tokens[0] if tokens else "list"
        branch_name = tokens[1] if len(tokens) > 1 else ""
        if operation in {"create", "switch"} and not branch_name:
            print("Usage: /git branch [list] | /git branch create <name> | approve | /git branch switch <name> | approve")
        else:
            result = WorkspaceToolRunner(paths).git_branch(operation, branch_name, approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "git branch"
    if command.startswith("/git remote"):
        raw = command.removeprefix("/git remote").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        tokens = parts[0].split()
        operation = tokens[0] if tokens else "list"
        remote_name = tokens[1] if len(tokens) > 1 else ""
        branch_name = tokens[2] if len(tokens) > 2 else ""
        if (operation == "fetch" and not remote_name) or (operation in {"pull", "push"} and (not remote_name or not branch_name)):
            print("Usage: /git remote [list] | /git remote fetch <remote> [branch] | approve | /git remote pull <remote> <branch> | approve | /git remote push <remote> <branch> | approve")
        else:
            result = WorkspaceToolRunner(paths).git_remote(operation, remote_name, branch_name, approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "git remote"
    if command.startswith("/edit replace"):
        raw = command.removeprefix("/edit replace").strip()
        parts = [part.strip() for part in raw.split("|", 3)]
        if len(parts) < 3 or not all(parts[:3]):
            print("Usage: /edit replace <path> | <old text> | <new text> | approve")
        else:
            approved = len(parts) >= 4 and parts[3].lower() in {"approve", "approved", "yes"}
            result = WorkspaceToolRunner(paths).replace_text(parts[0], parts[1], parts[2], approved=approved)
            _print_workspace_tool(result, audit, paths)
        return "edit"
    if command.startswith("/test") or command.startswith("/verify"):
        if command.startswith("/test"):
            raw_command = command.removeprefix("/test").strip()
        else:
            raw_command = command.removeprefix("/verify").strip()
        result = WorkspaceToolRunner(paths).run_tests(raw_command)
        _print_workspace_tool(result, audit, paths)
        return "test"
    if command.startswith("/automations"):
        automation_args = command.removeprefix("/automations").strip()
        registry = AutomationRegistry(paths)
        if not automation_args or automation_args == "list":
            print(format_automations(automation_summary(paths)))
        elif automation_args.startswith("create "):
            raw = automation_args.removeprefix("create ").strip()
            parts = [part.strip() for part in raw.split("|", 2)]
            if len(parts) != 3 or not all(parts):
                print("Usage: /automations create <name> | <schedule> | <prompt>")
            else:
                job, receipt = registry.create(parts[0], parts[1], parts[2], source="tui")
                print(format_automation(job, receipt=receipt))
        elif automation_args.startswith("show "):
            print(format_automation(registry.get(automation_args.removeprefix("show ").strip())))
        elif automation_args in {"due", "check", "check-due"}:
            print(format_due_automations(registry.due(source="tui")))
        elif automation_args in {"missed", "missed-runs"}:
            print(format_missed_automations(registry.missed(source="tui")))
        elif automation_args in {"replay", "replay-missed", "replay missed"}:
            payload = registry.replay_missed(source="tui")
            print(format_missed_replay(payload))
            for result in payload["triggered"]:
                print(f"watch      /tasks watch {result['task']['id']}")
        elif automation_args in {"tick", "run-due", "run due"}:
            payload = registry.run_due(source="tui")
            print(format_due_run(payload))
            for result in payload["triggered"]:
                print(f"watch      /tasks watch {result['task']['id']}")
        elif automation_args in {"worker", "daemon", "work"}:
            payload = registry.worker(interval_seconds=0, max_ticks=1, source="tui-worker")
            print(format_worker_run(payload))
            for tick in payload["ticks"]:
                for result in tick["triggered"]:
                    print(f"watch      /tasks watch {result['task']['id']}")
        elif automation_args in {"logs", "worker-log", "worker logs"} or automation_args.startswith("logs "):
            run_id = automation_args.split(maxsplit=1)[1] if automation_args.startswith("logs ") else ""
            print(format_worker_logs(registry.worker_logs(limit=20, run_id=run_id, source="tui")))
        elif automation_args in {"service", "service-wrapper", "launchd"}:
            print(format_service_wrapper(registry.service_wrapper(source="tui")))
        elif automation_args in {"service-status", "service status", "status", "launchd-status"}:
            print(format_service_status(registry.service_status(source="tui")))
        elif automation_args.startswith("trigger ") or automation_args.startswith("run "):
            job_id = automation_args.split(maxsplit=1)[1] if " " in automation_args else ""
            payload = registry.trigger(job_id, source="tui")
            if payload["status"] == "blocked":
                print(f"Automation trigger blocked: {payload['reason']}")
                print(format_automation(payload["automation"], receipt=payload["receipt"]))
            else:
                print(format_automation(payload["automation"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      /tasks watch {payload['task']['id']}")
        elif automation_args.startswith("pause "):
            job, receipt = registry.set_status(automation_args.removeprefix("pause ").strip(), "PAUSED", source="tui")
            print(format_automation(job, receipt=receipt))
        elif automation_args.startswith("resume "):
            job, receipt = registry.set_status(automation_args.removeprefix("resume ").strip(), "ACTIVE", source="tui")
            print(format_automation(job, receipt=receipt))
        elif automation_args.startswith("delete "):
            payload = registry.delete(automation_args.removeprefix("delete ").strip(), source="tui")
            print(f"Deleted automation {payload['deleted']['id']} ({payload['deleted']['name']})")
            print(f"receipt    {payload['receipt']}")
        else:
            print("Usage: /automations | /automations create <name> | <schedule> | <prompt> | /automations due | /automations missed | /automations replay | /automations tick | /automations worker | /automations logs [run-id] | /automations service | /automations service-status | /automations trigger <id> | /automations show <id> | /automations pause <id> | /automations resume <id> | /automations delete <id>")
        return "automations"
    if command.startswith("/improve"):
        improve_args = command.removeprefix("/improve").strip()
        store = ImprovementStore(paths)
        if not improve_args or improve_args in {"status", "list"}:
            print(format_improvements(improvement_summary(paths)))
        elif improve_args.startswith("propose "):
            summary = improve_args.removeprefix("propose ").strip()
            if not summary:
                print("Usage: /improve propose <failure summary>")
            else:
                proposal, receipt = store.propose_from_failure(summary, source="tui")
                print(format_improvement(proposal, receipt=receipt))
        elif improve_args.startswith("show "):
            print(format_improvement(store.get(improve_args.removeprefix("show ").strip())))
        elif improve_args.startswith("approve "):
            proposal, receipt = store.review(improve_args.removeprefix("approve ").strip(), decision="approve", source="tui")
            print(format_improvement(proposal, receipt=receipt))
        elif improve_args.startswith("implement ") or improve_args.startswith("handoff "):
            proposal_id = improve_args.split(maxsplit=1)[1] if " " in improve_args else ""
            payload = store.handoff(proposal_id, source="tui")
            if payload["status"] == "blocked":
                print(f"Improvement handoff blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      /tasks watch {payload['task']['id']}")
        elif improve_args.startswith("candidate "):
            candidate_args = improve_args.removeprefix("candidate ").strip()
            if candidate_args.startswith("show "):
                print(format_candidate(store.get_candidate(candidate_args.removeprefix("show ").strip())))
            else:
                payload = store.generate_candidate(candidate_args, source="tui")
                if payload["status"] == "blocked":
                    print(f"Improvement candidate blocked: {payload['reason']}")
                    print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
                else:
                    print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
        elif improve_args.startswith("diff ") or improve_args.startswith("candidate-diff "):
            candidate_id = improve_args.split(maxsplit=1)[1] if " " in improve_args else ""
            if not candidate_id:
                print("Usage: /improve diff <candidate-id>")
            else:
                print(format_candidate_diff_review(store.review_candidate_diff(candidate_id, source="tui")))
        elif improve_args.startswith("verify "):
            verify_args = improve_args.removeprefix("verify ").strip().split()
            candidate_id = verify_args[0] if verify_args else ""
            command_index = int(verify_args[1]) if len(verify_args) > 1 and verify_args[1].isdigit() else 0
            if not candidate_id:
                print("Usage: /improve verify <candidate-id> [command-index]")
            else:
                payload = store.run_candidate_verification(candidate_id, command_index=command_index, source="tui")
                if payload["status"] == "blocked":
                    print(f"Improvement verification blocked: {payload['reason']}")
                    print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
                else:
                    print(format_verification_run(payload, receipt=payload["receipt"]))
        elif improve_args.startswith("apply ") or improve_args.startswith("apply-candidate "):
            candidate_id = improve_args.split(maxsplit=1)[1] if " " in improve_args else ""
            payload = store.apply_candidate(candidate_id, source="tui")
            if payload["status"] == "blocked":
                print(f"Improvement candidate apply blocked: {payload['reason']}")
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
            else:
                print(format_candidate(payload["candidate"], receipt=payload["receipt"]))
                print("")
                print(f"task       {payload['task']['id']}  {payload['task']['status']}")
                print(f"watch      /tasks watch {payload['task']['id']}")
        elif improve_args.startswith("evidence "):
            parts = [part.strip() for part in improve_args.removeprefix("evidence ").split("|", 3)]
            if len(parts) < 4 or not all(parts):
                print("Usage: /improve evidence <id> | <changed-files> | <verification-command> | <result>")
            else:
                payload = store.record_evidence(
                    parts[0],
                    changed_files=parts[1].split(","),
                    verification_command=parts[2],
                    verification_result=parts[3],
                    source="tui",
                )
                if payload["status"] == "blocked":
                    print(f"Improvement evidence blocked: {payload['reason']}")
                    print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
                else:
                    print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
        elif improve_args.startswith("complete ") or improve_args.startswith("implemented "):
            proposal_id = improve_args.split(maxsplit=1)[1] if " " in improve_args else ""
            payload = store.mark_implemented(proposal_id, source="tui")
            if payload["status"] == "blocked":
                print(f"Improvement completion blocked: {payload['reason']}")
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
            else:
                print(format_improvement(payload["proposal"], receipt=payload["receipt"]))
        elif improve_args.startswith("reject "):
            proposal, receipt = store.review(improve_args.removeprefix("reject ").strip(), decision="reject", source="tui")
            print(format_improvement(proposal, receipt=receipt))
        else:
            print("Usage: /improve | /improve propose <failure summary> | /improve show <id> | /improve approve <id> | /improve implement <id> | /improve candidate <id> | /improve diff <candidate-id> | /improve verify <candidate-id> | /improve apply <candidate-id> | /improve evidence <id> | <files> | <command> | <result> | /improve complete <id> | /improve reject <id>")
        return "improve"
    if command.startswith("/subagents"):
        task = command.removeprefix("/subagents").strip()
        orchestrator = LocalSubagentOrchestrator(paths)
        if task.startswith("synthesis "):
            root_id = task.removeprefix("synthesis ").strip()
            try:
                synthesis = orchestrator.synthesis(root_id)
            except KeyError as exc:
                print(f"Synthesis not found: {exc}")
            else:
                audit.append("subagent.synthesis.read", {"surface": "tui", "root_id": root_id, "synthesis_id": synthesis.get("id", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_synthesis(synthesis))
        elif task.startswith("graph ") or task.startswith("artifact-graph "):
            root_id = task.removeprefix("graph ").removeprefix("artifact-graph ").strip()
            try:
                graph = orchestrator.artifact_graph(root_id)
            except KeyError as exc:
                print(f"Artifact graph not found: {exc}")
            else:
                audit.append("subagent.artifact_graph.read", {"surface": "tui", "root_id": root_id, "synthesis_id": graph.get("synthesis_id", ""), "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_artifact_graph(graph))
        elif task in {"artifacts", "artifact list"}:
            store = SubagentStore(paths)
            rows = store.artifacts()
            audit.append("subagent.artifacts.listed", {"surface": "tui", "count": len(rows), "limit": 50, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            print(format_artifacts(rows))
        elif task.startswith("artifacts show ") or task.startswith("artifact "):
            artifact_id = task.removeprefix("artifacts show ").removeprefix("artifact ").strip()
            try:
                row = SubagentStore(paths).artifact(artifact_id)
            except KeyError as exc:
                print(f"Artifact not found: {exc}")
            else:
                audit.append("subagent.artifact.read", {"surface": "tui", "artifact_id": artifact_id, "path": row.get("path", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_artifact(row))
        elif task.startswith("artifacts search ") or task.startswith("search-artifacts ") or task.startswith("artifact search "):
            query = task.removeprefix("artifacts search ").removeprefix("search-artifacts ").removeprefix("artifact search ").strip()
            rows = SubagentStore(paths).search_artifacts(query)
            audit.append("subagent.artifacts.searched", {"surface": "tui", "query": query, "count": len(rows), "limit": 20, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            print(format_artifact_search(query, rows))
        elif task.startswith("bg ") or task.startswith("background "):
            job_task = task.split(maxsplit=1)[1] if " " in task else ""
            try:
                record = _start_background_with_reuse(orchestrator, job_task)
            except (KeyError, ValueError) as exc:
                print(f"Background delegation blocked: {exc}")
                return "subagents"
            print(format_background_job(record))
            print("")
            print(f"monitor: /subagents monitor {record.id}")
            print(f"inspect: /subagents job {record.id}")
        elif task in {"jobs", "background"}:
            print(format_background_jobs(orchestrator.background_jobs()))
        elif task.startswith("job "):
            print(format_background_job(orchestrator.background_job(task.removeprefix("job ").strip())))
        elif task.startswith("monitor "):
            job_id = task.removeprefix("monitor ").strip()
            print("\n".join(_subagent_job_monitor_lines(paths, job_id, command=f"/subagents monitor {job_id}".rstrip())))
        elif task in {"unwatch", "stop-watch", "stop watch"}:
            print("No active subagent job monitor in static dispatch. In the live TUI this stops the nonblocking subagent monitor.")
        elif task in {"recover", "recover-stale"}:
            recovered = orchestrator.recover_stale_background()
            print(format_background_jobs([record.to_dict() for record in recovered]) if recovered else "No stale running subagent jobs found.")
        elif task.startswith("cancel "):
            print(format_background_job(orchestrator.cancel_background(task.removeprefix("cancel ").strip())))
        elif task.startswith("live ") or task.startswith("stream "):
            try:
                result = _delegate_with_reuse(orchestrator, task.split(maxsplit=1)[1] if " " in task else "")
            except (KeyError, ValueError) as exc:
                print(f"Delegation blocked: {exc}")
                return "subagents"
            print("SUBAGENT LIVE")
            print(format_events(result.events))
            print("")
            print(f"root      {result.root.id}  {result.root.status}")
            print(f"receipt   {result.receipt_id}")
        elif task.startswith("stop "):
            result = orchestrator.stop(task.removeprefix("stop ").strip())
            print(format_stop(result))
        elif task.startswith("watch ") or task.startswith("events "):
            root_id = task.split(maxsplit=1)[1] if " " in task else ""
            print(format_events(orchestrator.events(root_id)))
        elif task in {"", "list"}:
            print(format_subagent_records(SubagentStore(paths).list()))
            print("")
            print("usage: /subagents <task> | depth 2 | use-artifact <id> | approve | /subagents live <task> | depth 2 | /subagents bg <task> | depth 2 | /subagents artifacts | /subagents artifacts show <artifact-id> | /subagents artifacts search <query> | /subagents jobs | /subagents job <job-id> | /subagents monitor <job-id> | /subagents unwatch | /subagents cancel <job-id>")
        else:
            if task.startswith("delegate "):
                task = task.removeprefix("delegate ").strip()
            try:
                result = _delegate_with_reuse(orchestrator, task)
            except (KeyError, ValueError) as exc:
                print(f"Delegation blocked: {exc}")
                return "subagents"
            print(format_delegation(result))
        return "subagents"
    if command.startswith("/agents"):
        task = command.removeprefix("/agents").strip()
        orchestrator = LocalSubagentOrchestrator(paths)
        if task in {"", "status"}:
            print(format_agent_status(agent_status(paths)))
        elif task == "profiles":
            print(format_agent_profiles())
        elif task == "contracts":
            print(format_agent_contracts(agent_contracts_payload(paths)))
        elif task.startswith("synthesis "):
            root_id = task.removeprefix("synthesis ").strip()
            try:
                synthesis = orchestrator.synthesis(root_id)
            except KeyError as exc:
                print(f"Synthesis not found: {exc}")
            else:
                audit.append("subagent.synthesis.read", {"surface": "agents_tui", "root_id": root_id, "synthesis_id": synthesis.get("id", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_synthesis(synthesis).replace("SUBAGENT SYNTHESIS", "AGENT SYNTHESIS", 1))
        elif task.startswith("graph ") or task.startswith("artifact-graph "):
            root_id = task.removeprefix("graph ").removeprefix("artifact-graph ").strip()
            try:
                graph = orchestrator.artifact_graph(root_id)
            except KeyError as exc:
                print(f"Artifact graph not found: {exc}")
            else:
                audit.append("subagent.artifact_graph.read", {"surface": "agents_tui", "root_id": root_id, "synthesis_id": graph.get("synthesis_id", ""), "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_artifact_graph(graph).replace("SUBAGENT ARTIFACT GRAPH", "AGENT ARTIFACT GRAPH", 1))
        elif task.startswith("delegate "):
            try:
                result = _delegate_with_reuse(orchestrator, task.removeprefix("delegate ").strip())
            except (KeyError, ValueError) as exc:
                print(f"Delegation blocked: {exc}")
                return "agents"
            print(format_delegation(result).replace("SUBAGENT DELEGATION", "AGENT DELEGATION", 1))
        elif task in {"artifacts", "artifact list"}:
            rows = SubagentStore(paths).artifacts()
            audit.append("subagent.artifacts.listed", {"surface": "agents_tui", "count": len(rows), "limit": 50, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            print(format_artifacts(rows).replace("SUBAGENT ARTIFACTS", "AGENT ARTIFACTS", 1))
        elif task.startswith("artifacts show ") or task.startswith("artifact "):
            artifact_id = task.removeprefix("artifacts show ").removeprefix("artifact ").strip()
            try:
                row = SubagentStore(paths).artifact(artifact_id)
            except KeyError as exc:
                print(f"Artifact not found: {exc}")
            else:
                audit.append("subagent.artifact.read", {"surface": "agents_tui", "artifact_id": artifact_id, "path": row.get("path", ""), "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
                print(format_artifact(row).replace("SUBAGENT ARTIFACT", "AGENT ARTIFACT", 1))
        elif task.startswith("artifacts search ") or task.startswith("search-artifacts ") or task.startswith("artifact search "):
            query = task.removeprefix("artifacts search ").removeprefix("search-artifacts ").removeprefix("artifact search ").strip()
            rows = SubagentStore(paths).search_artifacts(query)
            audit.append("subagent.artifacts.searched", {"surface": "agents_tui", "query": query, "count": len(rows), "limit": 20, "browser_auto_launch": False, "external_action_started": False, "raw_secret_values_included": False})
            print(format_artifact_search(query, rows).replace("SUBAGENT ARTIFACT SEARCH", "AGENT ARTIFACT SEARCH", 1))
        elif task.startswith("bg ") or task.startswith("background "):
            job_task = task.split(maxsplit=1)[1] if " " in task else ""
            try:
                record = _start_background_with_reuse(orchestrator, job_task)
            except (KeyError, ValueError) as exc:
                print(f"Background delegation blocked: {exc}")
                return "agents"
            print(format_background_job(record).replace("SUBAGENT BACKGROUND JOB", "AGENT BACKGROUND JOB", 1))
            print("")
            print(f"monitor: /agents monitor {record.id}")
            print(f"inspect: /agents job {record.id}")
        elif task in {"jobs", "background"}:
            print(format_background_jobs(orchestrator.background_jobs()).replace("SUBAGENT BACKGROUND JOBS", "AGENT BACKGROUND JOBS", 1))
        elif task.startswith("job "):
            print(format_background_job(orchestrator.background_job(task.removeprefix("job ").strip())).replace("SUBAGENT BACKGROUND JOB", "AGENT BACKGROUND JOB", 1))
        elif task.startswith("monitor "):
            job_id = task.removeprefix("monitor ").strip()
            print("\n".join(_subagent_job_monitor_lines(paths, job_id, command=f"/agents monitor {job_id}".rstrip())).replace("SUBAGENT BACKGROUND JOB", "AGENT BACKGROUND JOB", 1))
        elif task in {"unwatch", "stop-watch", "stop watch"}:
            print("No active agent job monitor in static dispatch. In the live TUI this stops the nonblocking agent monitor.")
        elif task in {"recover", "recover-stale"}:
            recovered = orchestrator.recover_stale_background()
            text = format_background_jobs([record.to_dict() for record in recovered]) if recovered else "No stale running agent jobs found."
            print(text.replace("SUBAGENT BACKGROUND JOBS", "AGENT BACKGROUND JOBS", 1))
        elif task.startswith("cancel "):
            print(format_background_job(orchestrator.cancel_background(task.removeprefix("cancel ").strip())).replace("SUBAGENT BACKGROUND JOB", "AGENT BACKGROUND JOB", 1))
        elif task.startswith("live ") or task.startswith("stream "):
            prompt = task.split(maxsplit=1)[1] if " " in task else ""
            try:
                result = _delegate_with_reuse(orchestrator, prompt)
            except (KeyError, ValueError) as exc:
                print(f"Delegation blocked: {exc}")
                return "agents"
            print("AGENTS LIVE")
            print(format_events(result.events))
            print("")
            print(f"root      {result.root.id}  {result.root.status}")
            print(f"receipt   {result.receipt_id}")
        else:
            try:
                result = _delegate_with_reuse(orchestrator, task)
            except (KeyError, ValueError) as exc:
                print(f"Delegation blocked: {exc}")
                return "agents"
            print(format_delegation(result).replace("SUBAGENT DELEGATION", "AGENT DELEGATION", 1))
        return "agents"
    if command.startswith("/sessions"):
        sessions = SessionStore(paths)
        query = command.removeprefix("/sessions").strip()
        if query.startswith("search "):
            search_query = query.removeprefix("search ").strip()
            results = sessions.search(search_query, limit=10)
            receipt = audit.append("session.search", {"query": search_query, "result_count": len(results), "limit": 10, "source": "tui"})
            print_json({"query": search_query, "results": results, "receipt": receipt["id"]})
        else:
            print_json({"sessions": sessions.list(), "main": sessions.transcript("main", limit=8)})
        return "sessions"
    if command.startswith("/status"):
        print_json({"workspace": str(paths.workspace), "sandbox": detect_sandbox().to_dict(), "audit": audit.verify(), "tools": enabled_counts()})
        return "status"
    if command.startswith("/browser screenshot"):
        raw = command.removeprefix("/browser screenshot").strip()
        parts = [part.strip() for part in raw.split("|", 2)]
        approved = len(parts) >= 3 and parts[2].lower() in {"approve", "approved", "yes"}
        if len(parts) < 2 or not parts[0] or not parts[1]:
            print("Usage: /browser screenshot <session-id> | <workspace-path> | approve")
        else:
            result = BrowserSessionStore(paths).record_screenshot(parts[0], parts[1], approved=approved, source="tui")
            receipt = audit.append(
                "browser.session.screenshot",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print_json({**result, "receipt": receipt["id"]})
        return "browser"
    if command.startswith("/browser open"):
        raw = command.removeprefix("/browser open").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        if not parts[0]:
            print("Usage: /browser open <http-url> | approve")
        else:
            result = BrowserSessionStore(paths).open_url(parts[0], approved=approved, source="tui")
            receipt = audit.append(
                "browser.session.open",
                {
                    "status": result["status"],
                    "metadata": result.get("metadata", {}),
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
            print_json({**result, "receipt": receipt["id"]})
        return "browser"
    if command.startswith("/browser"):
        print_json(browser_summary(paths))
        return "browser"
    if command.startswith("/web fetch"):
        raw = command.removeprefix("/web fetch").strip()
        parts = [part.strip() for part in raw.split("|", 1)]
        approved = len(parts) == 2 and parts[1].lower() in {"approve", "approved", "yes"}
        if not parts[0]:
            print("Usage: /web fetch <http-url> | approve")
        else:
            result = WebToolRunner(paths).fetch(parts[0], approved=approved)
            receipt = audit.append(
                "tui.tool.completed",
                {
                    "tool": result.name,
                    "status": result.status,
                    "metadata": result.metadata,
                    "external_action_started": result.metadata.get("external_action_started", False),
                    "browser_auto_launch": False,
                },
            )
            print(result.content)
            print(f"audit receipt: {receipt['id']}")
        return "web fetch"
    if command.startswith("/web"):
        command_name = terminal_command_name()
        print("Optional web console preview:")
        print(f"  {command_name} web")
        print(f"  {command_name} web --serve --approved --host 127.0.0.1 --port 8787")
        print("  cd web && npm install && npm run dev -- --port 5173")
        print("browser_auto_launch: false")
        print("gateway_started: false")
        print("Terminal-first path remains:")
        print(f"  {command_name} tui")
        return "web"
    if command.startswith("/policy shell"):
        action = command.removeprefix("/policy shell").strip() or "rg --files"
        decision = decide_tool("shell", action)
        audit.append("tui.policy", decision.to_dict())
        print_json(decision.to_dict())
        return decision.action
    if command.startswith("/run"):
        action = command.removeprefix("/run").strip()
        if not action:
            print("Usage: /run <read-only command>")
            return "run"
        result = GovernedExecutor(paths).run_shell(action)
        print_json(result.to_dict())
        SessionStore(paths).append(
            "main",
            "tool",
            f"$ {action}\n{result.stdout or result.stderr}",
            metadata={"source": "tui", "receipt_id": result.receipt_id, "executed": result.executed},
        )
        return "run"
    if command.startswith("/policy"):
        raw = command.removeprefix("/policy").strip()
        if not raw:
            print("Usage: /policy shell <command> or /policy <tool-name> [action]")
            return "policy"
        parts = raw.split(maxsplit=1)
        tool_name = parts[0]
        action = parts[1] if len(parts) > 1 else "inspect"
        registry = ToolRegistry()
        result = registry.evaluate(tool_name, action)
        receipt = audit.append(
            "tui.policy",
            {
                "tool": tool_name,
                "action": action,
                "decision": result,
                "external_action_started": False,
                "browser_auto_launch": False,
            },
        )
        payload = {
            "title": "AEGIS POLICY INSPECTOR",
            "tool": tool_name,
            "action": action,
            "known": result["known"],
            "decision": result["action"],
            "risk": result["risk"],
            "rationale": result["rationale"],
            "receipt": receipt["id"],
            "browser_auto_launch": False,
            "external_action_started": False,
        }
        if "tool_spec" in result:
            payload["tool_spec"] = result["tool_spec"]
        print_json(payload)
        return "policy"
    turn = AgentRuntime(paths).respond(command, source="tui")
    print(turn.assistant_message)
    print(f"audit receipt: {turn.receipt_id}")
    return "agent turn"


def _slash_invoked(command: str, verb: str) -> bool:
    if command == verb:
        return True
    if not command.startswith(verb):
        return False
    return command[len(verb) : len(verb) + 1] in {" ", "\t", "|"}


def _slash_remainder(command: str, verb: str) -> str:
    return command[len(verb) :].strip() if _slash_invoked(command, verb) else ""


def normalize_interactive_command(command: str) -> str:
    stripped = command.strip()
    if stripped.startswith("//"):
        return "/" + stripped.lstrip("/")
    setup_aliases = {
        "/setup check": "/setup run-checks",
        "/setup checks": "/setup run-checks",
        "/setup verify": "/setup run-checks",
        "/setup doctor": "/setup run-checks",
        "/setup model-auth": "/setup model",
        "/setup connections": "/setup connectors",
        "/setup skills": "/setup memory",
        "/setup plugins": "/setup memory",
        "/setup init": "/setup",
    }
    if stripped in setup_aliases:
        return setup_aliases[stripped]
    root_aliases = {
        "/task": "/tasks",
        "/model": "/model providers",
    }
    if stripped in root_aliases:
        return root_aliases[stripped]
    return stripped


def slash_palette_candidates(buffer: str, *, limit: int = 10) -> list[tuple[str, str]]:
    stripped = buffer.strip().lower()
    if not stripped.startswith("/"):
        return []
    return [entry for entry in SLASH_COMMANDS if entry[0].startswith(stripped)][:limit]


def _task_watch_lines(paths: RuntimePaths, task_id: str, *, command: str = "/tasks watch") -> list[str]:
    if not task_id:
        return [f"$ {command}", "", "Usage: /tasks watch <task-id>"]
    runner = TaskRunner(paths)
    try:
        record = runner.get(task_id)
    except KeyError as exc:
        return [f"$ {command}", "", "AEGIS TASK WATCH", str(exc)]
    text = "\n".join(
        [
            f"$ {command}",
            "",
            format_task(record),
            "",
            format_task_events(runner.events(task_id)),
            "",
            format_task_outputs(runner.outputs(task_id)),
            "",
            format_task_worker_logs(runner.worker_logs(task_id)),
        ]
    )
    return text.splitlines()


def _task_status(paths: RuntimePaths, task_id: str) -> str:
    try:
        return TaskStore(paths).get(task_id).status
    except KeyError:
        return "unknown"


def _subagent_job_monitor_lines(paths: RuntimePaths, job_id: str, *, command: str = "/subagents monitor") -> list[str]:
    if not job_id:
        return [f"$ {command}", "", "Usage: /subagents monitor <job-id>"]
    try:
        record = LocalSubagentOrchestrator(paths).background_job(job_id)
    except KeyError as exc:
        return [f"$ {command}", "", "SUBAGENT JOB MONITOR", str(exc)]
    lines = [f"$ {command}", "", format_background_job(record)]
    if record.root_id:
        events = LocalSubagentOrchestrator(paths).events(record.root_id)
        lines.extend(["", format_events(events)])
    else:
        lines.extend(["", "SUBAGENT TIMELINE", "No root id recorded yet. The background worker has not produced subagent events."])
    if record.status not in {"completed", "failed", "cancelled"}:
        lines.extend(["", "Composer remains active. Use /subagents unwatch to stop this monitor."])
    return "\n".join(lines).splitlines()


def _subagent_job_status(paths: RuntimePaths, job_id: str) -> str:
    try:
        return LocalSubagentOrchestrator(paths).background_job(job_id).status
    except KeyError:
        return "unknown"


def _initial_output_lines(paths: RuntimePaths, *, setup_open: bool = False) -> list[str]:
    sandbox = detect_sandbox()
    lines = [
        "AegisAgent terminal UI is active.",
        "This is now the primary surface. The browser GUI is optional and separate.",
        "Type normally to draft a governed task, or type / for slash commands.",
        "",
    ]
    if setup_open:
        lines.extend(
            [
                "Aegis setup wizard is open by default.",
                "The composer is still live: type a normal request or use one of these setup commands.",
                "",
                "Setup path:",
                "1. /setup model        connect OpenAI, use local fallback, or inspect subscription metadata",
                "2. /setup connectors   inspect Slack, Teams, webhook, MCP, browser, Open WebUI readiness",
                "3. /setup run-checks   run local metadata-only safety checks",
                "4. /setup first-task   try one safe starter task",
                "5. /setup hide         keep future default launches prompt-first",
                "",
                "First launch: setup is open; composer is live.",
                "Next: /setup next -> /setup run-checks -> /setup first-task",
                "Use /commands setup for setup lanes; /setup hide dismisses this panel.",
                "Web stays optional and off until explicitly approved.",
                "",
            ]
        )
    lines.extend(
        [
        "Start here:",
        "1. /setup        configure model route, secrets vault, sandbox, tools, and checks",
        "2. /tools        inspect policy-gated tool capabilities",
        "3. /capabilities show implemented, partial, and planned Hermes-class surfaces",
        "4. /policy shell rg --files    see an allow/ask/deny decision with receipt",
        "5. /audit        verify the append-only receipt chain",
        "",
        f"Workspace: {paths.workspace}",
        f"Sandbox: {sandbox.backend} ({sandbox.rationale})",
        "Hermes-class loops, real tools, and multi-agent execution are staged, operator-approved build targets.",
        ]
    )
    return lines


def _wrap_lines(lines: list[str], width: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=max(8, width), replace_whitespace=False) or [""])
    return wrapped


def command_catalog_payload(paths: RuntimePaths, *, prefix: str = "", group: str = "") -> dict[str, Any]:
    needle = prefix.lower().strip().lstrip("/")
    group_filter = group.lower().strip()
    aliases = [
        {"alias": alias, "command": command, "detail": detail, "terminal_first": True, "browser_auto_launch": False}
        for alias, command, detail in COMMAND_ROOT_SHORTCUTS
        if not needle or needle in alias.lower().lstrip("/") or needle in command.lower().lstrip("/") or needle in detail.lower()
    ]
    groups: list[dict[str, Any]] = []
    command_count = 0
    matched_count = 0
    for group_name, commands in COMMAND_MENU_GROUPS:
        command_count += len(commands)
        if group_filter and group_filter not in group_name.lower():
            continue
        rows = []
        for command, detail in commands:
            if needle and needle not in command.lower() and needle not in detail.lower() and needle not in group_name.lower():
                continue
            rows.append(
                {
                    "command": command,
                    "detail": detail,
                    "group": group_name,
                    "terminal_first": True,
                    "browser_auto_launch": False,
                    "approval_hint": "requires approval" if "approve" in command or "approval" in detail else "none",
                }
            )
        if rows:
            matched_count += len(rows)
            groups.append({"name": group_name, "count": len(rows), "commands": rows})
    return {
        "title": "AEGIS TERMINAL COMMAND CATALOG",
        "workspace": str(paths.workspace),
        "prefix": prefix,
        "group": group,
        "terminal_first": True,
        "browser_required": False,
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
        "plain_text_submits_task": True,
        "tab_completion": True,
        "aliases": aliases,
        "groups": groups,
        "counts": {"groups": len(groups), "commands": command_count, "matched": matched_count},
        "examples": ["aegis commands setup", "aegis commands --group Build", "/commands agents", "/commands json"],
    }


def render_command_lanes(payload: dict[str, Any]) -> str:
    lines = [
        str(payload["title"]),
        "Plain text submits a governed task. Slash commands dispatch directly. Tab completes in the live TUI.",
        (
            "safety terminal_first=true browser_auto_launch=false "
            "gateway_started=false external_action_started=false"
        ),
        "",
    ]
    matched = False
    if payload.get("aliases"):
        matched = True
        lines.append("[Root Shortcuts]")
        for alias in payload["aliases"]:
            lines.append(f"  {alias['alias']:<12} -> {alias['command']:<18} {alias['detail']}")
        lines.append("")
    for group in payload["groups"]:
        matched = True
        lines.append(f"[{group['name']}]")
        for row in group["commands"]:
            lines.append(f"  {row['command']:<30} {row['detail']}")
        lines.append("")
    if not matched:
        query = payload.get("prefix") or payload.get("group") or ""
        lines.extend([f"No command lane matched `{query}`.", "Try /commands, /commands git, /commands setup, or /menu build."])
    lines.extend(
        [
            "examples",
            "- aegis commands setup",
            "- aegis commands --group Build",
            "- /commands json",
        ]
    )
    return "\n".join(lines).rstrip()


def print_json(payload: dict) -> None:
    import json

    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_workspace_tool(result: WorkspaceToolResult, audit: AuditLog, paths: RuntimePaths, *, display_content: str | None = None) -> None:
    content = display_content if display_content is not None else result.content
    receipt = audit.append(
        "tui.tool.completed",
        {
            "tool": result.name,
            "status": result.status,
            "metadata": result.metadata,
            "external_action_started": result.metadata.get("external_action_started", False),
            "browser_auto_launch": result.metadata.get("browser_auto_launch", False),
        },
    )
    print(content)
    print(f"audit receipt: {receipt['id']}")
    SessionStore(paths).append(
        "main",
        "tool",
        content,
        metadata={"source": "tui", "tool": result.name, "receipt_id": receipt["id"], **result.metadata},
    )
