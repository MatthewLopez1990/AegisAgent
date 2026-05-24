from __future__ import annotations

import os


def terminal_command_name() -> str:
    return os.environ.get("AEGIS_COMMAND_NAME", "aegis").strip() or "aegis"
