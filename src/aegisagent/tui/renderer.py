from __future__ import annotations

import shutil
from dataclasses import dataclass

from aegisagent.core.tools import DEFAULT_TOOLS, enabled_counts
from aegisagent.security.sandbox import detect_sandbox
from aegisagent.tui.theme import FOOTER_KEYS


@dataclass(frozen=True)
class TuiState:
    view: str = "command"
    composer: str = "/setup next"
    session: str = "main"
    branch: str = "main"
    model: str = "local/terminal-v0"
    provider_verified: bool = True


def _line(width: int, char: str = "-") -> str:
    return char * max(1, width)


def _clip(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "."


def _row(left: str, right: str, width: int) -> str:
    gap = max(1, width - len(left) - len(right))
    return _clip(left + (" " * gap) + right, width)


def _pad(text: str, width: int) -> str:
    return _clip(text, width).ljust(width)


def _panel_line(text: str, width: int) -> str:
    if width < 4:
        return _clip(text, width)
    return "|" + _pad(" " + text, width - 2) + "|"


def _panel_rule(width: int, char: str = "-") -> str:
    if width < 4:
        return char * width
    return "+" + (char * (width - 2)) + "+"


def _blank_panel(width: int) -> str:
    return _panel_line("", width)


def render(state: TuiState | None = None, *, width: int | None = None, height: int | None = None, no_color: bool = False) -> str:
    state = state or TuiState()
    if width is None or height is None:
        size = shutil.get_terminal_size((120, 40))
        width = width or size.columns
        height = height or size.lines
    if width < 80 or height < 24:
        return "AegisAgent needs at least 80x24. Resize the terminal to continue.\n"
    if state.view == "setup":
        return render_setup(width, height)
    if state.view == "tools":
        return render_tools(width, height)
    if state.view == "activation":
        return render_activation(width, height)
    if state.view == "help":
        return render_help(width, height)
    return render_command(state, width, height)


def render_command(state: TuiState, width: int, height: int) -> str:
    content_height = max(8, height - 6)
    right_width = 40 if width >= 112 else 0
    left_width = width - right_width - (3 if right_width else 0)
    sandbox_label = "docker" if detect_sandbox().available else "gated"
    status = f"policy:enforced sandbox:{sandbox_label} net:ask audit:live"
    if width < 100:
        status = "policy:on net:ask audit:live"
    left = [
        _panel_rule(left_width),
        _panel_line(_row(f"session: {state.session} / branch: {state.branch}", "idle", max(1, left_width - 4)), left_width),
        _panel_rule(left_width),
        _panel_line("Aegis is active in this terminal.", left_width),
        _panel_line("No command has run in this frame.", left_width),
        _blank_panel(left_width),
        _panel_line("Start: /setup next | /activation | /help", left_width),
        _panel_line("Verify: /setup run-checks | /audit | /dashboard", left_width),
        _panel_line("Work: type a request, or use /commands for slash lanes.", left_width),
        _blank_panel(left_width),
        _panel_line("Security: writes and network ask first.", left_width),
        _panel_line("Receipts appear after real actions. Secrets stay redacted.", left_width),
        _blank_panel(left_width),
        _panel_line("Optional web is preview-only until explicitly approved.", left_width),
    ]
    header = [
        _row("AEGIS SHIELD prompt-first governed agent", status, width),
        _line(width),
    ]
    while len(left) < content_height:
        left.append(_blank_panel(left_width) if right_width else "")
    if right_width:
        posture = _posture_panel(right_width, content_height)
        merged = []
        for left_line, right_line in zip(left[:content_height], posture):
            merged.append(_pad(left_line, left_width) + " | " + _pad(right_line, right_width))
        lines = header + merged
    else:
        lines = header + left[:content_height]
    lines.extend([
        _line(width),
        _row(FOOTER_KEYS, f"{width}x{height} ready", width),
        _line(width),
        _row(f"aegis> {state.composer}", "enter to send", width),
    ])
    return "\n".join(_clip(line, width) for line in lines[:height])


def _posture_panel(width: int, height: int) -> list[str]:
    sandbox = detect_sandbox()
    rows = [
        _panel_rule(width),
        _panel_line(_row("security posture", "low risk", max(1, width - 4)), width),
        _panel_rule(width),
        _panel_line("provider   local fallback; run /model doctor", width),
        _blank_panel(width),
        _panel_line("tools      shell, git, files gated", width),
        _blank_panel(width),
        _panel_line("workspace  current folder scoped", width),
        _blank_panel(width),
        _panel_line(f"sandbox    {sandbox.backend}", width),
        _blank_panel(width),
        _panel_line("network    disabled until approved", width),
        _blank_panel(width),
        _panel_line("secrets    handles only / no raw echo", width),
        _blank_panel(width),
        _panel_line("audit      run /audit for chain status", width),
        _blank_panel(width),
        _panel_line("approval   none pending", width),
        _panel_line("next       /setup next", width),
    ]
    rows.extend([_blank_panel(width)] * max(0, height - len(rows)))
    return rows[:height]


def render_activation(width: int, height: int) -> str:
    rows = [
        _row("AEGIS TERMINAL ACTIVATION", "terminal-first browser-off", width),
        _line(width),
        _panel_rule(width),
        _panel_line("installed command   aegis tui", width),
        _panel_line("from source         PYTHONPATH=src python3 -m aegisagent tui", width),
        _panel_line("print-only preview  aegis tui --print", width),
        _panel_line("default             aegis -> terminal TUI", width),
        _panel_rule(width),
        _blank_panel(width),
        _panel_line("safety              terminal_first=true  browser_required=false", width),
        _panel_line("                    browser_auto_launch=false  gateway_started=false", width),
        _blank_panel(width),
        _panel_line("next                /setup next -> /setup run-checks -> type a request", width),
        _panel_line("inside TUI          /activation  /dashboard  /tasks  /agents", width),
        _blank_panel(width),
        _panel_line("optional web        /web prints instructions only; no browser auto-start", width),
    ]
    while len(rows) < height - 4:
        rows.append(_blank_panel(width))
    rows.extend([
        _line(width),
        _row("Enter send | / commands | Tab complete | ? help | q quit", f"{width}x{height} ready", width),
        _line(width),
        _row("aegis> /activation", "enter to send", width),
    ])
    return "\n".join(_clip(line, width) for line in rows[:height])


def render_tools(width: int, height: int) -> str:
    counts = enabled_counts()
    header = [
        _row("AEGIS CONTROL tools, skills, scopes", f"{counts['enabled']} enabled {counts['ask']} ask {counts['blocked']} blocked audit live", width),
        _line(width),
        "tools  skills  providers  policies  audit",
        "",
    ]
    content_h = max(8, height - len(header) - 4)
    inspector_w = 36 if width >= 112 else 0
    matrix_w = width - inspector_w - (3 if inspector_w else 0)
    matrix = [
        _row("name             status     scope                  approval       risk", "receipt", matrix_w),
        _line(matrix_w),
    ]
    for tool in DEFAULT_TOOLS:
        receipt = tool.name.encode("utf-8").hex()[:4]
        matrix.append(_row(f"{tool.name:<16} {tool.status:<10} {tool.scope:<22} {tool.approval:<14} {tool.risk}", receipt, matrix_w))
    matrix.extend([""] * max(0, content_h - len(matrix)))
    if inspector_w:
        inspector = _tools_inspector(inspector_w, content_h)
        body = [
            _pad(left, matrix_w) + " | " + _pad(right, inspector_w)
            for left, right in zip(matrix[:content_h], inspector)
        ]
    else:
        body = matrix[:content_h]
    lines = header + body
    lines.extend([_line(width), _row(FOOTER_KEYS, "provider local fallback  sandbox gated  secrets handles-only", width), _row("aegis> /policy shell require-approval risky", "draft command", width)])
    return "\n".join(_clip(line, width) for line in lines[:height])


def render_setup(width: int, height: int) -> str:
    header = [
        _row("AEGIS SETUP secure defaults, provider first", "least privilege audit on tools ask", width),
        _line(width),
    ]
    body_h = max(8, height - len(header) - 3)
    if width >= 96:
        step_w = 30
        detail_w = width - step_w - 3
        steps = _setup_steps(step_w, body_h)
        detail = _setup_detail(detail_w, body_h)
        body = [
            _pad(left, step_w) + " | " + _pad(right, detail_w)
            for left, right in zip(steps, detail)
        ]
        lines = header + body
    else:
        lines = header + _setup_narrow(width, body_h)
    while len(lines) < height - 4:
        lines.append("")
    lines.extend([_line(width), _row("Arrow keys choose  Enter select  Back previous  ? why this matters", "safe setup mode", width), _row("setup> select macOS Keychain", "step 2 of 6", width)])
    return "\n".join(_clip(line, width) for line in lines[:height])


def render_help(width: int, height: int) -> str:
    lines = [
        _row("AEGIS HELP keyboard and command model", "prompt-first, browser-off", width),
        _line(width),
        _row("key", "action", width),
        _line(width),
        _row("Enter", "send prompt, run selected slash command, or confirm highlighted item", width),
        _row("Tab / Shift+Tab", "move focus or accept slash palette completion", width),
        _row("Arrow keys", "history, palette selection, or setup option movement", width),
        _row("/", "open slash command palette", width),
        _row("?", "show help and current keyboard controls", width),
        _row("Esc", "clear input or leave transient overlay", width),
        _row("q / /exit", "exit the terminal UI cleanly", width),
        "",
        "starter lanes",
        _row("/setup run-checks", "metadata-only readiness check", width),
        _row("/dashboard", "operator posture and active route summary", width),
        _row("/tools", "tool policy matrix and approval posture", width),
        _row("/agents bg <task>", "start bounded background agent work", width),
        _row("/git status", "read-only typed git inspection", width),
        _row("aegis completion zsh|bash|fish", "print shell completion outside the TUI", width),
        _row("/web", "print optional web console instructions only", width),
    ]
    while len(lines) < height - 4:
        lines.append("")
    lines.extend([
        _line(width),
        _row(FOOTER_KEYS, f"{width}x{height} ready", width),
        _row("aegis> /help", "enter to send", width),
    ])
    return "\n".join(_clip(line, width) for line in lines[:height])


def _tools_inspector(width: int, height: int) -> list[str]:
    rows = [
        _panel_rule(width),
        _panel_line(_row("policy inspector", "shell", max(1, width - 4)), width),
        _panel_rule(width),
        _panel_line("backend   host-gated", width),
        _panel_line("cwd       workspace only", width),
        _blank_panel(width),
        _panel_line("network   off unless approved", width),
        _panel_line("deny      sudo, rm -rf /", width),
        _panel_line("confirm   install, push, fetch", width),
        _blank_panel(width),
        _panel_line("logs      stdout redacted", width),
        _panel_line("          stderr kept", width),
        _blank_panel(width),
        _panel_line("recent receipts        chain ok", width),
        _panel_line("7368 shell read-only", width),
        _panel_line("6d65 memory write ask", width),
        _panel_line("6769 git repo scoped", width),
    ]
    rows.extend([_blank_panel(width)] * max(0, height - len(rows)))
    return rows[:height]


def _setup_steps(width: int, height: int) -> list[str]:
    rows = [
        _panel_rule(width),
        _panel_line(_row("steps", "2/6", max(1, width - 4)), width),
        _panel_rule(width),
        _panel_line("next /setup next", width),
        _blank_panel(width),
        _panel_line("  1 choose model", width),
        _panel_line("    provider", width),
        _blank_panel(width),
        _panel_line("> 2 connect secrets", width),
        _panel_line("    vault", width),
        _blank_panel(width),
        _panel_line("  3 choose execution", width),
        _panel_line("    sandbox", width),
        _blank_panel(width),
        _panel_line("  4 enable tools", width),
        _blank_panel(width),
        _panel_line("  5 import skills", width),
        _blank_panel(width),
        _panel_line("  6 run security check", width),
    ]
    rows.extend([_blank_panel(width)] * max(0, height - len(rows)))
    return rows[:height]


def _setup_detail(width: int, height: int) -> list[str]:
    rows = [
        _panel_rule(width),
        _panel_line(_row("connect secrets vault", "required for providers", max(1, width - 4)), width),
        _panel_rule(width),
        _panel_line("next command: aegis setup next or /setup next", width),
        _blank_panel(width),
        _panel_line("aegis Store API keys outside the transcript; secret values never echo.", width),
        _blank_panel(width),
    ]
    card_w = max(24, (width - 5) // 2)
    rows.extend(_card_pair(card_w, "macOS Keychain", "recommended local vault", "status: available", "1Password CLI", "team vault integration", "status: needs signin"))
    rows.extend(_card_pair(card_w, "environment file", "~/.aegis/.env, chmod 600", "status: acceptable", "enterprise gateway", "SSO and policy service", "status: configure later"))
    preview_h = max(6, height - len(rows))
    rows.extend(_security_preview(width, preview_h))
    rows.extend([_blank_panel(width)] * max(0, height - len(rows)))
    return rows[:height]


def _card_pair(width: int, left_title: str, left_detail: str, left_status: str, right_title: str, right_detail: str, right_status: str) -> list[str]:
    left = [_panel_rule(width), _panel_line(left_title, width), _panel_line(left_detail, width), _panel_line(left_status, width), _panel_rule(width)]
    right = [_panel_rule(width), _panel_line(right_title, width), _panel_line(right_detail, width), _panel_line(right_status, width), _panel_rule(width)]
    return [_pad(a, width) + " " + _pad(b, width) for a, b in zip(left, right)]


def _security_preview(width: int, height: int) -> list[str]:
    rows = [
        _panel_rule(width),
        _panel_line(_row("security preview", "safe defaults", max(1, width - 4)), width),
        _panel_line("provider key: redacted at source       shell: ask before write", width),
        _panel_line("network: blocked by default           audit: append-only receipts", width),
        _panel_line("sandbox: docker preferred             workspace: current folder only", width),
    ]
    rows.extend([_blank_panel(width)] * max(0, height - len(rows) - 1))
    rows.append(_panel_rule(width))
    return rows[:height]


def _setup_narrow(width: int, height: int) -> list[str]:
    lines = [
        _row("steps 2/6", "connect secrets vault", width),
        "",
        "next command: aegis setup next or /setup next",
        "",
        "aegis Store API keys outside the transcript. I will never print secret values.",
        "",
        "> 2 connect secrets vault",
        "  macOS Keychain       status: available",
        "  1Password CLI       status: needs signin",
        "  environment file    status: acceptable",
        "  enterprise gateway  status: configure later",
        "",
        "security preview",
        "provider key redacted at source",
        "network blocked by default",
        "audit append-only receipts",
        "workspace current folder only",
    ]
    lines.extend([""] * max(0, height - len(lines)))
    return [_clip(line, width) for line in lines[:height]]
