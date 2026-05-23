# Checkpoint 06 - TUI Implementation

Status: terminal-first foundation

Design target:

- Prompt-first transcript/composer surface.
- Right security posture panel when width allows.
- Setup wizard and tools matrix views matching the provided reference-image hierarchy.
- Keyboard-visible footer and 80x24 minimum-size handling.
- Terminal-first activation: `aegisagent tui` is the clean interactive path and is separate from the web gateway/browser surface.

Implemented:

- Standard-library renderer that works without optional dependencies.
- Curses-backed interactive TUI for real terminals.
- Slash palette, composer, history/palette navigation, clickable panel rows where terminal mouse events are available, and direct `/exit` / `/quit`.
- Static `--print` output remains available for CI, docs, and snapshot checks.
- Tests for 80x24, 100x32, 120x40, and 132x38-style frames.

Still incomplete:

- Real model loop.
- Sandboxed tool execution.
- Persistent conversation sessions.
- Full Hermes-class multi-agent orchestration.

Verification commands:

```bash
PYTHONPATH=src python3 -m aegisagent tui --help
PYTHONPATH=src python3 -m aegisagent tui --print --width 80 --height 24
PYTHONPATH=src python3 -m aegisagent tui --print --view setup --width 100 --height 32
PYTHONPATH=src python3 -m aegisagent tui --print --view tools --width 132 --height 38
```
