from __future__ import annotations

from aegisagent.config import RuntimePaths
from aegisagent.tui.interactive import run_interactive_tui
from aegisagent.tui.renderer import TuiState, render


def run_textual_app(view: str = "command", *, paths: RuntimePaths | None = None, classic: bool = False) -> int:
    if paths is not None and not classic and run_interactive_tui(paths, view=view):
        return 0
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Static
    except Exception:
        print(render(TuiState(view=view)))
        return 0

    class AegisConsole(App):
        CSS = """
        Screen { background: #0b0f14; color: #d9e2ee; }
        #surface { padding: 1; }
        """
        BINDINGS = [("q", "quit", "Quit"), ("?", "help", "Help")]

        def compose(self) -> ComposeResult:
            yield Static(render(TuiState(view=view)), id="surface")

    AegisConsole().run()
    return 0
