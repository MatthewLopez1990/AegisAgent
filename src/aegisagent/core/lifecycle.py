from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.core.workspace_tools import WorkspaceToolResult, WorkspaceToolRunner


_COMMAND_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_REPO_URL = "https://github.com/MatthewLopez1990/AegisAgent.git"


def install_terminal_shim(paths: RuntimePaths, *, bin_dir: str = "", name: str = "aegis", approved: bool = False) -> WorkspaceToolResult:
    clean_name = name.strip() or "aegis"
    if not _COMMAND_NAME_RE.fullmatch(clean_name):
        return _install_result(
            "blocked",
            {
                "status": "blocked",
                "error": "command name must contain only letters, numbers, dot, underscore, or dash",
                "command_name": clean_name,
                **_safety_metadata(approved=approved, mutation=False),
            },
        )
    target_dir = _target_bin_dir(bin_dir)
    target = target_dir / clean_name
    payload = install_status_payload(paths, bin_dir=bin_dir, name=clean_name)
    payload["approved"] = approved
    if not approved:
        payload.update(
            {
                "status": "needs_approval",
                "next": "rerun with --approved to write the macOS/Linux terminal shim",
                **_safety_metadata(approved=False, mutation=False),
            }
        )
        return _install_result("needs_approval", payload)

    target_dir.mkdir(parents=True, exist_ok=True)
    script = _shim_script(paths)
    existed = target.exists()
    target.write_text(script, encoding="utf-8")
    current_mode = target.stat().st_mode
    target.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    payload.update(
        {
            "status": "ok",
            "installed": True,
            "points_to_workspace": True,
            "replaced_existing": existed,
            "shim_path": str(target),
            "run_command": clean_name,
            "update_command": f"{clean_name} update --approved",
            **_safety_metadata(approved=True, mutation=True),
        }
    )
    return _install_result("ok", payload)


def install_status_payload(paths: RuntimePaths, *, bin_dir: str = "", name: str = "aegis") -> dict[str, Any]:
    clean_name = name.strip() or "aegis"
    target_dir = _target_bin_dir(bin_dir)
    target = target_dir / clean_name
    existing_text = ""
    if target.exists() and target.is_file():
        try:
            existing_text = target.read_text(encoding="utf-8")[:4096]
        except UnicodeDecodeError:
            existing_text = ""
    points_to_workspace = bool(existing_text and str(paths.workspace) in existing_text and "-m aegisagent" in existing_text)
    return {
        "title": "AEGIS TERMINAL INSTALL",
        "platform": "macOS/Linux shell",
        "workspace": str(paths.workspace),
        "bin_dir": str(target_dir),
        "command_name": clean_name,
        "shim_path": str(target),
        "installed": target.exists(),
        "points_to_workspace": points_to_workspace,
        "install_command": f"PYTHONPATH=src python3 -m aegisagent install shim --approved --name {clean_name}",
        "path_hint": f'export PATH="{target_dir}:$PATH"',
        "run_command": clean_name,
        "update_command": f"{clean_name} update --approved",
        "source_command": "PYTHONPATH=src python3 -m aegisagent",
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
    }


def update_from_github(paths: RuntimePaths, *, remote: str = "origin", branch: str = "main", approved: bool = False) -> WorkspaceToolResult:
    clean_remote = remote.strip() or "origin"
    clean_branch = branch.strip() or "main"
    expected_repo_url = os.environ.get("AEGIS_REPO_URL", DEFAULT_REPO_URL).strip() or DEFAULT_REPO_URL
    preview = {
        "title": "AEGIS TERMINAL UPDATE",
        "platform": "macOS/Linux shell",
        "workspace": str(paths.workspace),
        "remote": clean_remote,
        "branch": clean_branch,
        "repo_url": expected_repo_url,
        "update_command": f"aegis update --approved --remote {clean_remote} --branch {clean_branch}",
        "git_command": f"git pull --ff-only {clean_remote} {clean_branch}",
        "status": "needs_approval" if not approved else "running",
        "next": "rerun with --approved to pull the latest GitHub branch into this checkout",
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
        "network_capable_git_operation": True,
        "workspace_mutation_performed": False,
    }
    if not approved:
        return WorkspaceToolResult(
            name="lifecycle.update",
            status="needs_approval",
            content=json.dumps(preview, indent=2),
            metadata={
                "remote": clean_remote,
                "branch": clean_branch,
                "repo_url": expected_repo_url,
                "approved": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "network_capable_git_operation": True,
                "workspace_mutation_performed": False,
            },
        )
    guard = _update_preflight(paths, remote=clean_remote, branch=clean_branch, expected_repo_url=expected_repo_url)
    if guard is not None:
        return guard
    result = WorkspaceToolRunner(paths).git_remote("pull", clean_remote, clean_branch, approved=True)
    payload = json.loads(result.content)
    payload.update(
        {
            "title": "AEGIS TERMINAL UPDATE",
            "status": result.status,
            "workspace": str(paths.workspace),
            "repo_url": expected_repo_url,
            "update_command": f"aegis update --approved --remote {clean_remote} --branch {clean_branch}",
            "git_command": f"git pull --ff-only {clean_remote} {clean_branch}",
            "browser_auto_launch": False,
            "gateway_started": False,
            "external_action_started": result.metadata.get("external_action_started", False),
            "workspace_mutation_performed": result.metadata.get("workspace_mutation_performed", False),
            "network_capable_git_operation": result.metadata.get("network_capable_git_operation", True),
        }
    )
    metadata = {
        **result.metadata,
        "remote": clean_remote,
        "branch": clean_branch,
        "approved": True,
        "browser_auto_launch": False,
        "network_capable_git_operation": True,
    }
    return WorkspaceToolResult(
        name="lifecycle.update",
        status=result.status,
        content=json.dumps(payload, indent=2),
        metadata=metadata,
    )


def format_install_status(payload: dict[str, Any]) -> str:
    rows = [
        payload.get("title", "AEGIS TERMINAL INSTALL"),
        f"platform    {payload.get('platform', 'macOS/Linux shell')}",
        f"workspace   {payload.get('workspace', '')}",
        f"shim        {payload.get('shim_path', '')}",
        f"installed   {str(payload.get('installed', False)).lower()}",
        f"current     {str(payload.get('points_to_workspace', False)).lower()}",
        f"install     {payload.get('install_command', '')}",
        f"path        {payload.get('path_hint', '')}",
        f"run         {payload.get('run_command', '')}",
        f"update      {payload.get('update_command', '')}",
        f"browser_auto_launch: {str(payload.get('browser_auto_launch', False)).lower()}",
        f"gateway_started: {str(payload.get('gateway_started', False)).lower()}",
        f"external_action_started: {str(payload.get('external_action_started', False)).lower()}",
    ]
    if payload.get("status"):
        rows.insert(1, f"status      {payload['status']}")
    if payload.get("next"):
        rows.append(f"next        {payload['next']}")
    return "\n".join(rows)


def format_update_status(result: WorkspaceToolResult) -> str:
    payload = json.loads(result.content)
    lines = [
        payload.get("title", "AEGIS TERMINAL UPDATE"),
        f"status      {payload.get('status', result.status)}",
        f"workspace   {payload.get('workspace', '')}",
        f"remote      {payload.get('remote', '')}",
        f"branch      {payload.get('branch', '')}",
        f"command     {payload.get('update_command', '')}",
        f"git         {payload.get('git_command', '')}",
        f"browser_auto_launch: {str(payload.get('browser_auto_launch', False)).lower()}",
        f"gateway_started: {str(payload.get('gateway_started', False)).lower()}",
        f"external_action_started: {str(payload.get('external_action_started', False)).lower()}",
    ]
    if payload.get("next"):
        lines.append(f"next        {payload['next']}")
    if payload.get("stdout"):
        lines.append("stdout")
        lines.append(payload["stdout"].rstrip())
    if payload.get("stderr"):
        lines.append("stderr")
        lines.append(payload["stderr"].rstrip())
    return "\n".join(lines)


def _install_result(status: str, payload: dict[str, Any]) -> WorkspaceToolResult:
    return WorkspaceToolResult(
        name="lifecycle.install",
        status=status,
        content=json.dumps(payload, indent=2),
        metadata={
            "command_name": payload.get("command_name", ""),
            "shim_path": payload.get("shim_path", ""),
            "approved": payload.get("approved", False),
            "workspace_mutation_performed": payload.get("workspace_mutation_performed", False),
            "host_filesystem_mutation_performed": payload.get("host_filesystem_mutation_performed", False),
            "external_action_started": False,
            "browser_auto_launch": False,
        },
    )


def _update_preflight(paths: RuntimePaths, *, remote: str, branch: str, expected_repo_url: str) -> WorkspaceToolResult | None:
    if not (paths.workspace / ".git").exists():
        return _blocked_update_result(
            paths,
            remote=remote,
            branch=branch,
            expected_repo_url=expected_repo_url,
            error=f"AegisAgent checkout not found at {paths.workspace}",
        )

    remote_url = _git_stdout(paths.workspace, ["remote", "get-url", remote])
    if remote_url is None:
        return _blocked_update_result(
            paths,
            remote=remote,
            branch=branch,
            expected_repo_url=expected_repo_url,
            error=f"git remote {remote} is not configured",
        )

    if _canonical_repo_url(remote_url) != _canonical_repo_url(expected_repo_url):
        return _blocked_update_result(
            paths,
            remote=remote,
            branch=branch,
            expected_repo_url=expected_repo_url,
            error=f"refusing to update because {remote} is {remote_url}, expected {expected_repo_url}",
            current_repo_url=remote_url,
        )

    dirty = _git_stdout(paths.workspace, ["status", "--porcelain"])
    if dirty is None:
        return _blocked_update_result(
            paths,
            remote=remote,
            branch=branch,
            expected_repo_url=expected_repo_url,
            error="git status failed for this checkout",
            current_repo_url=remote_url,
        )
    if dirty.strip():
        return _blocked_update_result(
            paths,
            remote=remote,
            branch=branch,
            expected_repo_url=expected_repo_url,
            error=f"refusing to update dirty checkout at {paths.workspace}",
            current_repo_url=remote_url,
        )

    return None


def _blocked_update_result(
    paths: RuntimePaths,
    *,
    remote: str,
    branch: str,
    expected_repo_url: str,
    error: str,
    current_repo_url: str = "",
) -> WorkspaceToolResult:
    payload = {
        "title": "AEGIS TERMINAL UPDATE",
        "platform": "macOS/Linux shell",
        "status": "blocked",
        "workspace": str(paths.workspace),
        "remote": remote,
        "branch": branch,
        "repo_url": expected_repo_url,
        "current_repo_url": current_repo_url,
        "error": error,
        "update_command": f"aegis update --approved --remote {remote} --branch {branch}",
        "git_command": f"git pull --ff-only {remote} {branch}",
        "next": "fix the checkout state, then rerun the approved update",
        "browser_auto_launch": False,
        "gateway_started": False,
        "external_action_started": False,
        "network_capable_git_operation": True,
        "workspace_mutation_performed": False,
    }
    return WorkspaceToolResult(
        name="lifecycle.update",
        status="blocked",
        content=json.dumps(payload, indent=2),
        metadata={
            "remote": remote,
            "branch": branch,
            "repo_url": expected_repo_url,
            "current_repo_url": current_repo_url,
            "approved": True,
            "external_action_started": False,
            "browser_auto_launch": False,
            "network_capable_git_operation": True,
            "workspace_mutation_performed": False,
        },
    )


def _git_stdout(workspace: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _canonical_repo_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.startswith("git@github.com:"):
        return f"https://github.com/{cleaned[len('git@github.com:') :]}"
    if cleaned.startswith("ssh://git@github.com/"):
        return f"https://github.com/{cleaned[len('ssh://git@github.com/') :]}"
    if "://" not in cleaned:
        return str(Path(cleaned).expanduser().resolve())
    return cleaned


def _safety_metadata(*, approved: bool, mutation: bool) -> dict[str, Any]:
    return {
        "approved": approved,
        "workspace_mutation_performed": False,
        "host_filesystem_mutation_performed": mutation,
        "external_action_started": False,
        "browser_auto_launch": False,
    }


def _target_bin_dir(raw_bin_dir: str) -> Path:
    if raw_bin_dir.strip():
        return Path(raw_bin_dir).expanduser().resolve()
    return (Path(os.environ.get("HOME", "~")).expanduser() / ".local" / "bin").resolve()


def _shim_script(paths: RuntimePaths) -> str:
    workspace = str(paths.workspace)
    return "\n".join(
        [
            "#!/usr/bin/env sh",
            "set -eu",
            f"AEGIS_WORKSPACE={_shell_quote(workspace)}",
            'AEGIS_PYTHON="${AEGIS_PYTHON:-python3}"',
            'cd "$AEGIS_WORKSPACE"',
            'PYTHONPATH="$AEGIS_WORKSPACE/src${PYTHONPATH:+:$PYTHONPATH}" exec "$AEGIS_PYTHON" -m aegisagent "$@"',
            "",
        ]
    )


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
