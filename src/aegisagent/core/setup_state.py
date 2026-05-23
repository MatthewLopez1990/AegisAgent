from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from aegisagent.config import RuntimePaths, ensure_runtime


STATE_VERSION = 1


def setup_ui_state_path(paths: RuntimePaths) -> Path:
    return paths.state_dir / "setup-ui-state.json"


def setup_wizard_preferences(paths: RuntimePaths) -> dict[str, Any]:
    ensure_runtime(paths)
    state = _read_state(setup_ui_state_path(paths))
    wizard = state.get("wizard", {}) if isinstance(state.get("wizard"), dict) else {}
    hidden = bool(wizard.get("hidden", False))
    return {
        "show_by_default": not hidden,
        "hidden": hidden,
        "updated_at": wizard.get("updated_at"),
        "state_path": str(setup_ui_state_path(paths)),
        "terminal_first": True,
        "browser_auto_launch": False,
        "external_action_started": False,
        "raw_secret_values_included": False,
    }


def update_setup_wizard_preferences(paths: RuntimePaths, *, hidden: bool) -> dict[str, Any]:
    ensure_runtime(paths)
    path = setup_ui_state_path(paths)
    state = _read_state(path)
    state["wizard"] = {"hidden": hidden, "updated_at": int(time.time())}
    _write_state(path, state)
    return setup_wizard_preferences(paths)


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "wizard": {"hidden": False}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": STATE_VERSION, "wizard": {"hidden": False}}
    if not isinstance(payload, dict):
        return {"version": STATE_VERSION, "wizard": {"hidden": False}}
    wizard = payload.get("wizard") if isinstance(payload.get("wizard"), dict) else {"hidden": False}
    return {"version": STATE_VERSION, "wizard": wizard}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STATE_VERSION,
        "wizard": state.get("wizard") if isinstance(state.get("wizard"), dict) else {"hidden": False},
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    os.replace(tmp_path, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
