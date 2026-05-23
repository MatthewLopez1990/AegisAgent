from __future__ import annotations

import shutil
from dataclasses import dataclass

from aegisagent.core.tools import DEFAULT_TOOLS, enabled_counts
from aegisagent.security.sandbox import detect_sandbox
from aegisagent.tui.theme import FOOTER_KEYS


@dataclass(frozen=True)
class TuiState:
    view: str = "command"
    composer: str = "/approve edit once --scope tui"
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
        _panel_line(_row(f"session: {state.session} / branch: {state.branch}", "streaming", max(1, left_width - 4)), left_width),
        _panel_rule(left_width),
        _panel_line("you   keep Aegis terminal-first and verify startup stays browser-off.", left_width),
        _panel_line("aegis I will inspect, ask before writes/network, and record receipts.", left_width),
        _blank_panel(left_width),
        _panel_line("tool: rg --files                                      allowed / read-only", left_width),
        _panel_line("scope=workspace  risk=low  policy=auto  audit=8f31c2", left_width),
        _panel_line("src/aegisagent/tui/renderer.py  tests/test_tui.py  docs/progress/", left_width),
        _blank_panel(left_width),
        _panel_line("approval required: edit file                                  ask", left_width),
        _panel_line("target=src/aegisagent/tui/renderer.py", left_width),
        _panel_line("[a] allow once   [s] scope down   [d] deny", left_width),
        _blank_panel(left_width),
        _panel_line("system checkpoint saved. rollback available. secrets redacted.", left_width),
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
        _panel_line("model      local/terminal-v0 ready", width),
        _blank_panel(width),
        _panel_line("tools      shell, git, files gated", width),
        _blank_panel(width),
        _panel_line("workspace  current folder scoped", width),
        _blank_panel(width),
        _panel_line(f"sandbox    {sandbox.backend}", width),
        _blank_panel(width),
        _panel_line("network    disabled until approved", width),
        _blank_panel(width),
        _panel_line("secrets    vault locked / no echo", width),
        _blank_panel(width),
        _panel_line("audit      append-only chain ok", width),
        _blank_panel(width),
        _panel_line("pending approval", width),
        _panel_line("write", width),
        _panel_line("press a, s, or d", width),
    ]
    rows.extend([_blank_panel(width)] * max(0, height - len(rows)))
    return rows[:height]


def render_activation(width: int, height: int) -> str:
    rows = [
        _row("AEGIS TERMINAL ACTIVATION", "terminal-first browser-off", width),
        _line(width),
        _panel_rule(width),
        _panel_line("primary     aegisagent tui", width),
        _panel_line("alias       aegis tui", width),
        _panel_line("source      PYTHONPATH=src python3 -m aegisagent", width),
        _panel_line("default     aegisagent -> terminal TUI", width),
        _panel_line("fallback    aegisagent tui --print", width),
        _panel_rule(width),
        _blank_panel(width),
        _panel_line("safety      terminal_first=true  browser_required=false", width),
        _panel_line("            browser_auto_launch=false  gateway_started=false", width),
        _blank_panel(width),
        _panel_line("inside TUI  /setup run-checks  /capabilities  /gaps", width),
        _panel_line("            /tasks  /agents  /browser  /activation", width),
        _blank_panel(width),
        _panel_line("optional    /web prints browser console instructions only", width),
    ]
    while len(rows) < height - 4:
        rows.append(_blank_panel(width))
    rows.extend([
        _line(width),
        _row("Tab pane  Enter select  / command  ? help  q quit", f"{width}x{height} ready", width),
        _line(width),
        _row("aegis> /activation", "enter to send", width),
    ])
    return "\n".join(_clip(line, width) for line in rows[:height])


def render_tools(width: int, height: int) -> str:
    counts = enabled_counts()
    lines = [
        _row("AEGIS CONTROL tools, skills, scopes", f"{counts['enabled']} enabled {counts['ask']} ask {counts['blocked']} blocked audit live", width),
        _line(width),
        "tools  skills  providers  policies  audit",
        "",
        _row("name             status     scope                  approval       risk", "receipt", width),
        _line(width),
    ]
    for tool in DEFAULT_TOOLS:
        receipt = tool.name.encode("utf-8").hex()[:4]
        lines.append(_row(f"{tool.name:<16} {tool.status:<10} {tool.scope:<22} {tool.approval:<14} {tool.risk}", receipt, width))
    while len(lines) < height - 4:
        lines.append("")
    lines.extend([_line(width), _row(FOOTER_KEYS, "provider connected sandbox isolated secrets locked", width), _row("aegis> /policy shell require-approval risky", "draft command", width)])
    return "\n".join(_clip(line, width) for line in lines[:height])


def render_setup(width: int, height: int) -> str:
    steps = [
        "1 choose model provider",
        "2 connect secrets vault",
        "3 choose execution sandbox",
        "4 enable tools",
        "5 import skills",
        "6 run security check",
    ]
    lines = [
        _row("AEGIS SETUP secure defaults, provider first", "least privilege audit on tools ask", width),
        _line(width),
        _row("steps 2/6", "connect secrets vault", width),
        "",
        "aegis Store API keys outside the transcript. I will never print secret values.",
        "",
    ]
    for step in steps:
        marker = ">" if step.startswith("2 ") else " "
        lines.append(f"{marker} {step}")
    lines.extend([
        "",
        "security preview",
        "provider key: redacted at source       shell: ask before write",
        "network: blocked by default           audit: append-only receipts",
        "sandbox: docker preferred             workspace: current folder only",
    ])
    while len(lines) < height - 4:
        lines.append("")
    lines.extend([_line(width), _row("Arrow keys choose  Enter select  Back previous  ? why this matters", "safe setup mode", width), _row("setup> select macOS Keychain", "step 2 of 6", width)])
    return "\n".join(_clip(line, width) for line in lines[:height])
