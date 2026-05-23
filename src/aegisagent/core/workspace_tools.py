from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.security.redaction import redact_text

SKIPPED_DIRS = {".aegisagent", ".git", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


@dataclass(frozen=True, slots=True)
class WorkspaceToolResult:
    name: str
    status: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "content": self.content,
            "metadata": self.metadata,
        }


class WorkspaceToolRunner:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths

    def run_for_prompt(self, prompt: str) -> list[WorkspaceToolResult]:
        lower = prompt.lower()
        results: list[WorkspaceToolResult] = []
        if any(term in lower for term in ("workspace", "repo", "repository", "files", "codebase")):
            results.append(self.list_files(limit=40))
        read_path = _extract_path_after(prompt, ("read file ", "open file ", "show file "))
        if read_path:
            results.append(self.read_file(read_path))
        if "git status" in lower or "repo status" in lower or "working tree" in lower:
            results.append(self.git_status())
        if "git diff" in lower or "show diff" in lower or "repo diff" in lower:
            diff_path = _extract_path_after(prompt, ("git diff ", "show diff ", "repo diff "))
            results.append(self.git_diff(diff_path or None))
        search_query = _extract_search_query(prompt)
        if search_query:
            results.append(self.search_text(search_query, limit=12))
        if _should_run_tests(lower):
            results.append(self.run_tests(_extract_test_command(prompt)))
        return results

    def list_files(self, *, limit: int = 40) -> WorkspaceToolResult:
        files = [str(path.relative_to(self.paths.workspace)) for path in self._iter_workspace_files(limit=limit)]
        return WorkspaceToolResult(
            name="workspace.list_files",
            status="ok",
            content=json.dumps({"files": files}, indent=2),
            metadata={"file_count": len(files), "limit": limit},
        )

    def search_text(self, query: str, *, limit: int = 12) -> WorkspaceToolResult:
        needle = query.lower().strip()
        matches: list[dict[str, Any]] = []
        for path in self._iter_workspace_files(limit=300):
            if len(matches) >= limit:
                break
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle in line.lower():
                    redacted = redact_text(line.strip())
                    matches.append({"path": str(path.relative_to(self.paths.workspace)), "line": line_no, "text": redacted.text})
                    break
        return WorkspaceToolResult(
            name="workspace.search_text",
            status="ok",
            content=json.dumps({"query": query, "matches": matches}, indent=2),
            metadata={"query": query, "match_count": len(matches), "limit": limit},
        )

    def read_file(self, relative_path: str, *, max_bytes: int = 12000) -> WorkspaceToolResult:
        target = self._resolve_workspace_file(relative_path)
        if target is None:
            return WorkspaceToolResult(
                name="workspace.read_file",
                status="blocked",
                content=json.dumps({"path": relative_path, "error": "path must be an existing file inside the workspace"}, indent=2),
                metadata={"path": relative_path, "blocked": True},
            )
        try:
            source = target.read_bytes()
            raw = source[:max_bytes]
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return WorkspaceToolResult(
                name="workspace.read_file",
                status="blocked",
                content=json.dumps({"path": str(target.relative_to(self.paths.workspace)), "error": "binary or non-utf8 file"}, indent=2),
                metadata={"path": str(target.relative_to(self.paths.workspace)), "blocked": True},
            )
        redacted = redact_text(text)
        rel = str(target.relative_to(self.paths.workspace))
        return WorkspaceToolResult(
            name="workspace.read_file",
            status="ok",
            content=json.dumps({"path": rel, "content": redacted.text, "truncated": len(source) > max_bytes}, indent=2),
            metadata={"path": rel, "bytes": len(raw), "truncated": len(source) > max_bytes, "redacted": redacted.redacted},
        )

    def git_status(self) -> WorkspaceToolResult:
        result = _run_git(self.paths.workspace, ["status", "--short", "--branch"])
        stdout = redact_text(result.stdout)
        stderr = redact_text(result.stderr)
        return WorkspaceToolResult(
            name="git.status",
            status="ok" if result.returncode == 0 else "error",
            content=json.dumps({"stdout": stdout.text, "stderr": stderr.text, "returncode": result.returncode}, indent=2),
            metadata={"returncode": result.returncode, "line_count": len(stdout.text.splitlines()), "redacted": stdout.redacted or stderr.redacted},
        )

    def git_diff(self, relative_path: str | None = None, *, max_bytes: int = 20000) -> WorkspaceToolResult:
        rel = "."
        if relative_path:
            target = self._resolve_workspace_path(relative_path)
            if target is None:
                return WorkspaceToolResult(
                    name="git.diff",
                    status="blocked",
                    content=json.dumps({"path": relative_path, "error": "path must be inside the workspace"}, indent=2),
                    metadata={"path": relative_path, "blocked": True},
                )
            rel = str(target.relative_to(self.paths.workspace))
        result = _run_git(self.paths.workspace, ["diff", "--", rel])
        stdout = redact_text(result.stdout[:max_bytes])
        stderr = redact_text(result.stderr)
        return WorkspaceToolResult(
            name="git.diff",
            status="ok" if result.returncode == 0 else "error",
            content=json.dumps({"path": rel, "stdout": stdout.text, "stderr": stderr.text, "returncode": result.returncode, "truncated": len(result.stdout) > max_bytes}, indent=2),
            metadata={"path": rel, "returncode": result.returncode, "bytes": len(stdout.text), "truncated": len(result.stdout) > max_bytes, "redacted": stdout.redacted or stderr.redacted},
        )

    def git_stage(self, relative_paths: list[str], *, approved: bool = False, max_bytes: int = 12000) -> WorkspaceToolResult:
        rels: list[str] = []
        for raw_path in relative_paths:
            if not raw_path or raw_path in {".", "/"}:
                return WorkspaceToolResult(
                    name="git.stage",
                    status="blocked",
                    content=json.dumps({"path": raw_path, "error": "stage paths must be explicit workspace files"}, indent=2),
                    metadata={
                        "path": raw_path,
                        "blocked": True,
                        "approved": approved,
                        "workspace_mutation_performed": False,
                        "git_index_mutation_performed": False,
                        "external_action_started": False,
                        "browser_auto_launch": False,
                    },
                )
            target = self._resolve_workspace_path(raw_path)
            if target is None or (target.exists() and not target.is_file()):
                return WorkspaceToolResult(
                    name="git.stage",
                    status="blocked",
                    content=json.dumps({"path": raw_path, "error": "path must be an explicit file path inside the workspace"}, indent=2),
                    metadata={
                        "path": raw_path,
                        "blocked": True,
                        "approved": approved,
                        "workspace_mutation_performed": False,
                        "git_index_mutation_performed": False,
                        "external_action_started": False,
                        "browser_auto_launch": False,
                    },
                )
            rels.append(str(target.relative_to(self.paths.workspace)))
        if not rels:
            return WorkspaceToolResult(
                name="git.stage",
                status="blocked",
                content=json.dumps({"error": "at least one explicit workspace file path is required"}, indent=2),
                metadata={
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_index_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        redacted_paths = [redact_text(path).text for path in rels]
        if not approved:
            return WorkspaceToolResult(
                name="git.stage",
                status="needs_approval",
                content=json.dumps(
                    {
                        "paths": redacted_paths,
                        "status": "needs_approval",
                        "next": "rerun with explicit approval to mutate the git index",
                    },
                    indent=2,
                ),
                metadata={
                    "paths": rels,
                    "approved": False,
                    "workspace_mutation_performed": False,
                    "git_index_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        add_result = _run_git(self.paths.workspace, ["add", "--", *rels])
        status_result = _run_git(self.paths.workspace, ["status", "--short", "--", *rels])
        stdout = redact_text((add_result.stdout + status_result.stdout)[:max_bytes])
        stderr = redact_text((add_result.stderr + status_result.stderr)[:max_bytes])
        return WorkspaceToolResult(
            name="git.stage",
            status="ok" if add_result.returncode == 0 else "error",
            content=json.dumps(
                {
                    "paths": redacted_paths,
                    "status": "ok" if add_result.returncode == 0 else "error",
                    "stdout": stdout.text,
                    "stderr": stderr.text,
                    "returncode": add_result.returncode,
                    "truncated": len(add_result.stdout + status_result.stdout) > max_bytes or len(add_result.stderr + status_result.stderr) > max_bytes,
                },
                indent=2,
            ),
            metadata={
                "paths": rels,
                "approved": True,
                "returncode": add_result.returncode,
                "workspace_mutation_performed": False,
                "git_index_mutation_performed": add_result.returncode == 0,
                "external_action_started": False,
                "browser_auto_launch": False,
                "redacted": stdout.redacted or stderr.redacted,
            },
        )

    def git_commit(self, message: str, *, approved: bool = False, max_bytes: int = 12000) -> WorkspaceToolResult:
        clean_message = message.strip()
        if not clean_message:
            return WorkspaceToolResult(
                name="git.commit",
                status="blocked",
                content=json.dumps({"error": "commit message is required"}, indent=2),
                metadata={
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_history_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        staged_result = _run_git(self.paths.workspace, ["diff", "--cached", "--name-only"])
        staged_redacted = redact_text(staged_result.stdout)
        staged_files = [line for line in staged_redacted.text.splitlines() if line.strip()]
        if staged_result.returncode != 0:
            stderr = redact_text(staged_result.stderr)
            return WorkspaceToolResult(
                name="git.commit",
                status="error",
                content=json.dumps({"error": stderr.text, "returncode": staged_result.returncode}, indent=2),
                metadata={
                    "approved": approved,
                    "returncode": staged_result.returncode,
                    "workspace_mutation_performed": False,
                    "git_history_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "redacted": staged_redacted.redacted or stderr.redacted,
                },
            )
        if not staged_files:
            return WorkspaceToolResult(
                name="git.commit",
                status="blocked",
                content=json.dumps({"error": "no staged files to commit", "staged_files": []}, indent=2),
                metadata={
                    "blocked": True,
                    "approved": approved,
                    "staged_file_count": 0,
                    "workspace_mutation_performed": False,
                    "git_history_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        message_redacted = redact_text(clean_message)
        if not approved:
            return WorkspaceToolResult(
                name="git.commit",
                status="needs_approval",
                content=json.dumps(
                    {
                        "status": "needs_approval",
                        "message": message_redacted.text,
                        "staged_files": staged_files,
                        "next": "rerun with explicit approval to create a git commit",
                    },
                    indent=2,
                ),
                metadata={
                    "approved": False,
                    "staged_file_count": len(staged_files),
                    "workspace_mutation_performed": False,
                    "git_history_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "redacted": staged_redacted.redacted or message_redacted.redacted,
                },
            )
        commit_result = _run_git(self.paths.workspace, ["commit", "-m", clean_message])
        stdout = redact_text(commit_result.stdout[:max_bytes])
        stderr = redact_text(commit_result.stderr[:max_bytes])
        commit_id = ""
        if commit_result.returncode == 0:
            head_result = _run_git(self.paths.workspace, ["rev-parse", "--short", "HEAD"])
            commit_id = redact_text(head_result.stdout.strip()).text if head_result.returncode == 0 else ""
        return WorkspaceToolResult(
            name="git.commit",
            status="ok" if commit_result.returncode == 0 else "error",
            content=json.dumps(
                {
                    "status": "ok" if commit_result.returncode == 0 else "error",
                    "message": message_redacted.text,
                    "staged_files": staged_files,
                    "commit": commit_id,
                    "stdout": stdout.text,
                    "stderr": stderr.text,
                    "returncode": commit_result.returncode,
                    "truncated": len(commit_result.stdout) > max_bytes or len(commit_result.stderr) > max_bytes,
                },
                indent=2,
            ),
            metadata={
                "approved": True,
                "staged_file_count": len(staged_files),
                "commit": commit_id,
                "returncode": commit_result.returncode,
                "workspace_mutation_performed": False,
                "git_history_mutation_performed": commit_result.returncode == 0,
                "external_action_started": False,
                "browser_auto_launch": False,
                "redacted": staged_redacted.redacted or message_redacted.redacted or stdout.redacted or stderr.redacted,
            },
        )

    def git_branch(self, operation: str = "list", branch_name: str = "", *, approved: bool = False, max_bytes: int = 12000) -> WorkspaceToolResult:
        action = (operation or "list").strip().lower()
        if action in {"", "list", "status"}:
            result = _run_git(self.paths.workspace, ["branch", "--list"])
            stdout = redact_text(result.stdout[:max_bytes])
            stderr = redact_text(result.stderr[:max_bytes])
            return WorkspaceToolResult(
                name="git.branch",
                status="ok" if result.returncode == 0 else "error",
                content=json.dumps({"operation": "list", "stdout": stdout.text, "stderr": stderr.text, "returncode": result.returncode}, indent=2),
                metadata={
                    "operation": "list",
                    "returncode": result.returncode,
                    "workspace_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "redacted": stdout.redacted or stderr.redacted,
                },
            )
        if action not in {"create", "switch"}:
            return WorkspaceToolResult(
                name="git.branch",
                status="blocked",
                content=json.dumps({"operation": action, "error": "branch operation must be list, create, or switch"}, indent=2),
                metadata={
                    "operation": action,
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        clean_branch = branch_name.strip()
        if not _valid_branch_name(clean_branch):
            return WorkspaceToolResult(
                name="git.branch",
                status="blocked",
                content=json.dumps({"operation": action, "branch": clean_branch, "error": "branch name is invalid or unsafe"}, indent=2),
                metadata={
                    "operation": action,
                    "branch": clean_branch,
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        branch_redacted = redact_text(clean_branch)
        if not approved:
            return WorkspaceToolResult(
                name="git.branch",
                status="needs_approval",
                content=json.dumps(
                    {
                        "operation": action,
                        "branch": branch_redacted.text,
                        "status": "needs_approval",
                        "next": "rerun with explicit approval to mutate git refs",
                    },
                    indent=2,
                ),
                metadata={
                    "operation": action,
                    "branch": clean_branch,
                    "approved": False,
                    "workspace_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "redacted": branch_redacted.redacted,
                },
            )
        args = ["branch", clean_branch] if action == "create" else ["switch", clean_branch]
        result = _run_git(self.paths.workspace, args)
        stdout = redact_text(result.stdout[:max_bytes])
        stderr = redact_text(result.stderr[:max_bytes])
        current_result = _run_git(self.paths.workspace, ["branch", "--show-current"])
        current_branch = redact_text(current_result.stdout.strip()).text if current_result.returncode == 0 else ""
        return WorkspaceToolResult(
            name="git.branch",
            status="ok" if result.returncode == 0 else "error",
            content=json.dumps(
                {
                    "operation": action,
                    "branch": branch_redacted.text,
                    "current_branch": current_branch,
                    "stdout": stdout.text,
                    "stderr": stderr.text,
                    "returncode": result.returncode,
                    "truncated": len(result.stdout) > max_bytes or len(result.stderr) > max_bytes,
                },
                indent=2,
            ),
            metadata={
                "operation": action,
                "branch": clean_branch,
                "current_branch": current_branch,
                "approved": True,
                "returncode": result.returncode,
                "workspace_mutation_performed": False,
                "git_ref_mutation_performed": result.returncode == 0,
                "external_action_started": False,
                "browser_auto_launch": False,
                "redacted": branch_redacted.redacted or stdout.redacted or stderr.redacted,
            },
        )

    def git_remote(self, operation: str = "list", remote_name: str = "", branch_name: str = "", *, approved: bool = False, max_bytes: int = 12000) -> WorkspaceToolResult:
        action = (operation or "list").strip().lower()
        if action in {"", "list", "status"}:
            result = _run_git(self.paths.workspace, ["remote", "-v"])
            stdout = redact_text(result.stdout[:max_bytes])
            stderr = redact_text(result.stderr[:max_bytes])
            return WorkspaceToolResult(
                name="git.remote",
                status="ok" if result.returncode == 0 else "error",
                content=json.dumps({"operation": "list", "stdout": stdout.text, "stderr": stderr.text, "returncode": result.returncode}, indent=2),
                metadata={
                    "operation": "list",
                    "returncode": result.returncode,
                    "workspace_mutation_performed": False,
                    "git_remote_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "network_capable_git_operation": False,
                    "redacted": stdout.redacted or stderr.redacted,
                },
            )
        if action not in {"push", "fetch", "pull"}:
            return WorkspaceToolResult(
                name="git.remote",
                status="blocked",
                content=json.dumps({"operation": action, "error": "remote operation must be list, fetch, pull, or push"}, indent=2),
                metadata={
                    "operation": action,
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_remote_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "network_capable_git_operation": False,
                },
            )
        clean_remote = remote_name.strip()
        clean_branch = branch_name.strip()
        if not _valid_remote_name(clean_remote) or (action in {"pull", "push"} and not _valid_branch_name(clean_branch)) or (action == "fetch" and clean_branch and not _valid_branch_name(clean_branch)):
            return WorkspaceToolResult(
                name="git.remote",
                status="blocked",
                content=json.dumps({"operation": action, "remote": clean_remote, "branch": clean_branch, "error": "remote and branch names must be explicit and safe"}, indent=2),
                metadata={
                    "operation": action,
                    "remote": clean_remote,
                    "branch": clean_branch,
                    "blocked": True,
                    "approved": approved,
                    "workspace_mutation_performed": False,
                    "git_remote_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "network_capable_git_operation": True,
                },
            )
        remote_redacted = redact_text(clean_remote)
        branch_redacted = redact_text(clean_branch)
        if not approved:
            next_message = f"rerun with explicit approval to {action} this remote"
            if action in {"pull", "push"}:
                next_message = f"rerun with explicit approval to {action} this branch {'from' if action == 'pull' else 'to'} the remote"
            return WorkspaceToolResult(
                name="git.remote",
                status="needs_approval",
                content=json.dumps(
                    {
                        "operation": action,
                        "remote": remote_redacted.text,
                        "branch": branch_redacted.text,
                        "status": "needs_approval",
                        "next": next_message,
                    },
                    indent=2,
                ),
                metadata={
                    "operation": action,
                    "remote": clean_remote,
                    "branch": clean_branch,
                    "approved": False,
                    "workspace_mutation_performed": False,
                    "git_remote_mutation_performed": False,
                    "git_ref_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "network_capable_git_operation": True,
                    "redacted": remote_redacted.redacted or branch_redacted.redacted,
                },
            )
        if action == "fetch":
            args = ["fetch", clean_remote, clean_branch] if clean_branch else ["fetch", clean_remote]
        elif action == "pull":
            args = ["pull", "--ff-only", clean_remote, clean_branch]
        else:
            args = ["push", clean_remote, clean_branch]
        result = _run_git(self.paths.workspace, args)
        stdout = redact_text(result.stdout[:max_bytes])
        stderr = redact_text(result.stderr[:max_bytes])
        return WorkspaceToolResult(
            name="git.remote",
            status="ok" if result.returncode == 0 else "error",
            content=json.dumps(
                {
                    "operation": action,
                    "remote": remote_redacted.text,
                    "branch": branch_redacted.text,
                    "stdout": stdout.text,
                    "stderr": stderr.text,
                    "returncode": result.returncode,
                    "truncated": len(result.stdout) > max_bytes or len(result.stderr) > max_bytes,
                },
                indent=2,
            ),
            metadata={
                "operation": action,
                "remote": clean_remote,
                "branch": clean_branch,
                "approved": True,
                "returncode": result.returncode,
                "workspace_mutation_performed": action == "pull" and result.returncode == 0,
                "git_remote_mutation_performed": action == "push" and result.returncode == 0,
                "git_ref_mutation_performed": action in {"fetch", "pull"} and result.returncode == 0,
                "external_action_started": True,
                "browser_auto_launch": False,
                "network_capable_git_operation": True,
                "redacted": remote_redacted.redacted or branch_redacted.redacted or stdout.redacted or stderr.redacted,
            },
        )

    def run_tests(self, command: str = "", *, timeout: int = 60, max_bytes: int = 24000) -> WorkspaceToolResult:
        raw_command = command.strip() or self._default_test_command()
        argv = _allowed_test_argv(raw_command, self.paths.workspace)
        if not argv:
            return WorkspaceToolResult(
                name="workspace.run_tests",
                status="blocked",
                content=json.dumps(
                    {
                        "command": raw_command,
                        "error": "test commands must be allowlisted Python unittest/py_compile commands inside the workspace",
                        "allowed_examples": [
                            "python3 -m unittest discover -s tests -v",
                            "python3 -m unittest tests.test_cli -v",
                            "python3 -m py_compile src/aegisagent/cli.py",
                        ],
                    },
                    indent=2,
                ),
                metadata={"command": raw_command, "blocked": True, "external_action_started": False, "browser_auto_launch": False},
            )
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            result = subprocess.run(argv, cwd=self.paths.workspace, text=True, capture_output=True, timeout=timeout, check=False, env=env)
        except subprocess.TimeoutExpired as exc:
            stdout = redact_text((exc.stdout or "")[:max_bytes] if isinstance(exc.stdout, str) else "")
            stderr = redact_text((exc.stderr or "")[:max_bytes] if isinstance(exc.stderr, str) else str(exc))
            return WorkspaceToolResult(
                name="workspace.run_tests",
                status="timeout",
                content=json.dumps({"command": raw_command, "stdout": stdout.text, "stderr": stderr.text, "returncode": None, "timeout": timeout}, indent=2),
                metadata={"command": raw_command, "timeout": timeout, "returncode": None, "redacted": stdout.redacted or stderr.redacted, "external_action_started": False, "browser_auto_launch": False},
            )
        except OSError as exc:
            redacted = redact_text(str(exc))
            return WorkspaceToolResult(
                name="workspace.run_tests",
                status="error",
                content=json.dumps({"command": raw_command, "stdout": "", "stderr": redacted.text, "returncode": 1}, indent=2),
                metadata={"command": raw_command, "returncode": 1, "redacted": redacted.redacted, "external_action_started": False, "browser_auto_launch": False},
            )
        stdout = redact_text(result.stdout[:max_bytes])
        stderr = redact_text(result.stderr[:max_bytes])
        truncated = len(result.stdout) > max_bytes or len(result.stderr) > max_bytes
        return WorkspaceToolResult(
            name="workspace.run_tests",
            status="ok" if result.returncode == 0 else "failed",
            content=json.dumps(
                {
                    "command": raw_command,
                    "stdout": stdout.text,
                    "stderr": stderr.text,
                    "returncode": result.returncode,
                    "truncated": truncated,
                },
                indent=2,
            ),
            metadata={
                "command": raw_command,
                "returncode": result.returncode,
                "truncated": truncated,
                "redacted": stdout.redacted or stderr.redacted,
                "external_action_started": False,
                "browser_auto_launch": False,
            },
        )

    def _default_test_command(self) -> str:
        if (self.paths.workspace / "tests").is_dir():
            return "python3 -m unittest discover -s tests -v"
        return "python3 -m py_compile src/aegisagent/cli.py"

    def replace_text(self, relative_path: str, old_text: str, new_text: str, *, approved: bool = False) -> WorkspaceToolResult:
        target = self._resolve_workspace_file(relative_path)
        if target is None:
            return WorkspaceToolResult(
                name="workspace.replace_text",
                status="blocked",
                content=json.dumps({"path": relative_path, "error": "path must be an existing utf-8 file inside the workspace"}, indent=2),
                metadata={"path": relative_path, "blocked": True, "approved": approved, "workspace_mutation_performed": False},
            )
        if not old_text:
            return WorkspaceToolResult(
                name="workspace.replace_text",
                status="blocked",
                content=json.dumps({"path": str(target.relative_to(self.paths.workspace)), "error": "old text is required"}, indent=2),
                metadata={"path": str(target.relative_to(self.paths.workspace)), "blocked": True, "approved": approved, "workspace_mutation_performed": False},
            )
        try:
            original = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return WorkspaceToolResult(
                name="workspace.replace_text",
                status="blocked",
                content=json.dumps({"path": str(target.relative_to(self.paths.workspace)), "error": "binary or non-utf8 file"}, indent=2),
                metadata={"path": str(target.relative_to(self.paths.workspace)), "blocked": True, "approved": approved, "workspace_mutation_performed": False},
            )
        count = original.count(old_text)
        rel = str(target.relative_to(self.paths.workspace))
        if count != 1:
            return WorkspaceToolResult(
                name="workspace.replace_text",
                status="blocked",
                content=json.dumps({"path": rel, "error": "old text must match exactly once", "match_count": count}, indent=2),
                metadata={"path": rel, "blocked": True, "approved": approved, "match_count": count, "workspace_mutation_performed": False},
            )
        old_redacted = redact_text(old_text)
        new_redacted = redact_text(new_text)
        if not approved:
            return WorkspaceToolResult(
                name="workspace.replace_text",
                status="needs_approval",
                content=json.dumps(
                    {
                        "path": rel,
                        "status": "needs_approval",
                        "old_text": old_redacted.text,
                        "new_text": new_redacted.text,
                        "next": "rerun with explicit approval to perform the workspace mutation",
                    },
                    indent=2,
                ),
                metadata={
                    "path": rel,
                    "approved": False,
                    "match_count": count,
                    "redacted": old_redacted.redacted or new_redacted.redacted,
                    "workspace_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                },
            )
        updated = original.replace(old_text, new_text, 1)
        target.write_text(updated, encoding="utf-8")
        return WorkspaceToolResult(
            name="workspace.replace_text",
            status="ok",
            content=json.dumps(
                {
                    "path": rel,
                    "status": "ok",
                    "replacements": 1,
                    "old_text": old_redacted.text,
                    "new_text": new_redacted.text,
                },
                indent=2,
            ),
            metadata={
                "path": rel,
                "approved": True,
                "match_count": count,
                "replacements": 1,
                "redacted": old_redacted.redacted or new_redacted.redacted,
                "workspace_mutation_performed": True,
                "external_action_started": False,
                "browser_auto_launch": False,
            },
        )

    def _iter_workspace_files(self, *, limit: int) -> list[Path]:
        files: list[Path] = []
        for path in sorted(self.paths.workspace.rglob("*")):
            if len(files) >= limit:
                break
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(self.paths.workspace)
            except ValueError:
                continue
            if rel.name == ".DS_Store":
                continue
            if rel.parts and rel.parts[0] in SKIPPED_DIRS:
                continue
            files.append(path)
        return files

    def _resolve_workspace_file(self, relative_path: str) -> Path | None:
        target = self._resolve_workspace_path(relative_path)
        if target is None or not target.is_file():
            return None
        return target

    def _resolve_workspace_path(self, relative_path: str) -> Path | None:
        try:
            target = (self.paths.workspace / relative_path).resolve()
            target.relative_to(self.paths.workspace)
        except (OSError, ValueError):
            return None
        try:
            rel = target.relative_to(self.paths.workspace)
        except ValueError:
            return None
        if rel.parts and rel.parts[0] in SKIPPED_DIRS:
            return None
        return target


def _extract_search_query(prompt: str) -> str:
    lower = prompt.lower()
    for marker in ("search for ", "find text ", "grep for "):
        index = lower.find(marker)
        if index >= 0:
            return prompt[index + len(marker) :].strip().strip("'\"")[:80]
    return ""


def _extract_path_after(prompt: str, markers: tuple[str, ...]) -> str:
    lower = prompt.lower()
    for marker in markers:
        index = lower.find(marker)
        if index >= 0:
            value = prompt[index + len(marker) :].strip().strip("'\"")
            return value.split()[0] if value else ""
    return ""


def _should_run_tests(lower_prompt: str) -> bool:
    return any(term in lower_prompt for term in ("run tests", "run the tests", "verify tests", "test suite", "unittest", "py_compile"))


def _extract_test_command(prompt: str) -> str:
    lower = prompt.lower()
    for marker in ("run tests: ", "verify tests: ", "test command: ", "run test command: "):
        index = lower.find(marker)
        if index >= 0:
            return prompt[index + len(marker) :].strip().strip("'\"")[:240]
    return ""


def _allowed_test_argv(command: str, workspace: Path) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError:
        return []
    if not argv or any(token in {";", "&&", "||", "|", ">", ">>", "<"} for token in argv):
        return []
    if len(argv) >= 3 and argv[0] in {"python", "python3"} and argv[1] == "-m" and argv[2] == "unittest":
        if not _unittest_args_stay_in_workspace(argv[3:], workspace):
            return []
        return argv
    if len(argv) >= 4 and argv[0] in {"python", "python3"} and argv[1] == "-m" and argv[2] == "py_compile":
        for raw_path in argv[3:]:
            target = (workspace / raw_path).resolve()
            try:
                rel = target.relative_to(workspace)
            except ValueError:
                return []
            if rel.parts and rel.parts[0] in SKIPPED_DIRS:
                return []
            if target.suffix != ".py":
                return []
        return argv
    return []


def _unittest_args_stay_in_workspace(args: list[str], workspace: Path) -> bool:
    expect_path = False
    for token in args:
        if expect_path:
            if not _test_path_stays_in_workspace(token, workspace):
                return False
            expect_path = False
            continue
        if token in {"-s", "--start-directory", "-t", "--top-level-directory"}:
            expect_path = True
            continue
        if token.startswith("--start-directory=") or token.startswith("--top-level-directory="):
            raw_path = token.split("=", 1)[1]
            if not _test_path_stays_in_workspace(raw_path, workspace):
                return False
            continue
        if token.endswith(".py") or "/" in token or token.startswith("."):
            if not _test_path_stays_in_workspace(token, workspace):
                return False
    return not expect_path


def _test_path_stays_in_workspace(raw_path: str, workspace: Path) -> bool:
    target = (workspace / raw_path).resolve()
    try:
        rel = target.relative_to(workspace)
    except ValueError:
        return False
    return not (rel.parts and rel.parts[0] in SKIPPED_DIRS)


def _valid_branch_name(branch_name: str) -> bool:
    if not branch_name or branch_name.startswith("-"):
        return False
    if any(char.isspace() or ord(char) < 32 for char in branch_name):
        return False
    if branch_name in {".", "..", "HEAD"}:
        return False
    if (
        branch_name.startswith("/")
        or branch_name.endswith("/")
        or branch_name.endswith(".")
        or branch_name.endswith(".lock")
        or "//" in branch_name
        or ".." in branch_name
        or "@{" in branch_name
        or "\\" in branch_name
    ):
        return False
    return all(char not in "~^:?*[" for char in branch_name)


def _valid_remote_name(remote_name: str) -> bool:
    if not remote_name or remote_name.startswith("-"):
        return False
    if any(char.isspace() or ord(char) < 32 for char in remote_name):
        return False
    return all(char.isalnum() or char in {"-", "_", "."} for char in remote_name)


def _run_git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(["git", *args], returncode=1, stdout="", stderr=str(exc))
