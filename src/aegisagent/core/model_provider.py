from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.core.command_names import terminal_command_name
from aegisagent.security.redaction import redact_text


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    session_id: str
    transcript: list[dict[str, Any]]
    workspace: Path
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    context_artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    provider: str
    mode: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalTerminalProvider:
    name = "local/terminal-v0"
    mode = "local"

    def __init__(self, paths: RuntimePaths):
        self.paths = paths

    def complete(self, request: ModelRequest) -> ModelResponse:
        prompt = request.prompt.strip()
        lower = prompt.lower()
        snapshot = self._workspace_snapshot()

        lines = [
            "Aegis local agent turn",
            f"- Session: {request.session_id}",
            f"- Workspace: {request.workspace}",
        ]
        if snapshot["files"]:
            lines.append(f"- Visible files: {snapshot['file_count']} workspace paths sampled; examples: {', '.join(snapshot['files'][:5])}")
        else:
            lines.append("- Visible files: no non-state workspace files found in the local sample.")

        if _is_role_worker_prompt(lower):
            role = _role_from_prompt(lower)
            task = _task_from_role_prompt(prompt)
            contribution = _local_role_contribution(role, task)
            lines.extend(
                [
                    "",
                    "Subagent worker contribution:",
                    contribution,
                ]
            )
        elif "summar" in lower and "workspace" in lower:
            lines.extend(
                [
                    "",
                    "Workspace summary:",
                    "This is a terminal-first AegisAgent scaffold with a CLI/TUI surface, governed shell execution, append-only audit receipts, persistent sessions, and an optional web GUI kept separate from the primary terminal path.",
                ]
            )
            workspace_listing = _first_tool_result(request.tool_results, "workspace.list_files")
            if workspace_listing:
                files = workspace_listing.get("metadata", {}).get("file_count", 0)
                lines.append(f"The agent inspected the workspace through `workspace.list_files` and sampled {files} file paths before answering.")
        elif "subagent" in lower or "sub-agent" in lower or "delegate" in lower or "many agents" in lower:
            delegation = _first_tool_result(request.tool_results, "subagents.delegate")
            lines.extend(["", "Subagent delegation:"])
            if delegation:
                lines.append(str(delegation.get("content", "")).strip())
            else:
                lines.append("No delegation tool result was attached to this turn.")
        elif "plan" in lower:
            lines.extend(
                [
                    "",
                    "Initial governed plan:",
                    "1. Inspect the relevant files with read-only commands.",
                    "2. Make the smallest scoped code change that advances the agent loop.",
                    "3. Verify with unit tests, audit-chain validation, and a terminal smoke run.",
                ]
            )
        elif "search sessions for" in lower or "session search" in lower or "search transcript" in lower:
            session_result = _first_tool_result(request.tool_results, "sessions.search")
            lines.extend(["", "Session search:"])
            if session_result:
                payload = _tool_json(session_result)
                results = payload.get("results", [])
                if isinstance(results, list):
                    lines.append(f"`sessions.search` searched for `{payload.get('query', '')}` and found {len(results)} matching transcript messages.")
                    for match in results[:5]:
                        if not isinstance(match, dict):
                            continue
                        lines.append(
                            f"  {match.get('session_id', '')} [{match.get('role', '')}] "
                            f"{str(match.get('snippet', '')).strip()}"
                        )
                else:
                    lines.append("The session search result was not in the expected shape.")
            else:
                lines.append("No session search tool result was attached.")
        elif "search" in lower or "find text" in lower or "grep" in lower:
            search_result = _first_tool_result(request.tool_results, "workspace.search_text")
            if search_result:
                metadata = search_result.get("metadata", {})
                lines.extend(
                    [
                        "",
                        "Workspace search:",
                        f"`workspace.search_text` searched for `{metadata.get('query', '')}` and found {metadata.get('match_count', 0)} matching file samples.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        "Workspace search:",
                        "No typed search directive was detected. Use phrasing such as `search for LocalTerminalProvider` to invoke `workspace.search_text`.",
                    ]
                )
        elif "read file" in lower or "open file" in lower or "show file" in lower:
            read_result = _first_tool_result(request.tool_results, "workspace.read_file")
            lines.extend(["", "Workspace file read:"])
            if read_result:
                payload = _tool_json(read_result)
                metadata = read_result.get("metadata", {})
                status = read_result.get("status", "")
                if status == "ok":
                    lines.append(
                        f"`workspace.read_file` read `{payload.get('path', metadata.get('path', ''))}` "
                        f"({metadata.get('bytes', 0)} bytes sampled; truncated={str(metadata.get('truncated', False)).lower()}; redacted={str(metadata.get('redacted', False)).lower()})."
                    )
                    preview = str(payload.get("content", "")).strip().splitlines()[:8]
                    if preview:
                        lines.append("Preview:")
                        lines.extend(f"  {line}" for line in preview)
                else:
                    lines.append(str(payload.get("error", "The requested file could not be read.")))
            else:
                lines.append("No typed file path was detected. Use `read file README.md` or `/read README.md`.")
        elif "git status" in lower or "repo status" in lower or "working tree" in lower:
            status_result = _first_tool_result(request.tool_results, "git.status")
            lines.extend(["", "Git status:"])
            if status_result:
                payload = _tool_json(status_result)
                stdout = str(payload.get("stdout", "")).strip()
                stderr = str(payload.get("stderr", "")).strip()
                lines.append(f"`git.status` returned {payload.get('returncode', status_result.get('status'))}.")
                if stdout:
                    lines.extend(f"  {line}" for line in stdout.splitlines()[:12])
                if stderr:
                    lines.append(f"  stderr: {stderr}")
            else:
                lines.append("No git status tool result was attached.")
        elif "git diff" in lower or "show diff" in lower or "repo diff" in lower:
            diff_result = _first_tool_result(request.tool_results, "git.diff")
            lines.extend(["", "Git diff:"])
            if diff_result:
                payload = _tool_json(diff_result)
                stdout = str(payload.get("stdout", "")).strip()
                stderr = str(payload.get("stderr", "")).strip()
                path = payload.get("path", diff_result.get("metadata", {}).get("path", "."))
                lines.append(f"`git.diff` inspected `{path}` and returned {payload.get('returncode', diff_result.get('status'))}.")
                if stdout:
                    lines.extend(f"  {line}" for line in stdout.splitlines()[:16])
                else:
                    lines.append("  No unstaged diff output was reported.")
                if stderr:
                    lines.append(f"  stderr: {stderr}")
            else:
                lines.append("No git diff tool result was attached.")
        elif "run tests" in lower or "run the tests" in lower or "verify tests" in lower or "test suite" in lower or "unittest" in lower or "py_compile" in lower:
            test_result = _first_tool_result(request.tool_results, "workspace.run_tests")
            lines.extend(["", "Test run:"])
            if test_result:
                payload = _tool_json(test_result)
                stdout = str(payload.get("stdout", "")).strip()
                stderr = str(payload.get("stderr", "")).strip()
                command = str(payload.get("command", test_result.get("metadata", {}).get("command", ""))).strip()
                returncode = payload.get("returncode", test_result.get("metadata", {}).get("returncode"))
                lines.append(f"`workspace.run_tests` ran `{command}` and returned {returncode}.")
                if stdout:
                    lines.extend(f"  {line}" for line in stdout.splitlines()[-10:])
                if stderr:
                    lines.extend(f"  stderr: {line}" for line in stderr.splitlines()[-10:])
            else:
                lines.append("No typed test result was attached.")
        elif "fetch" in lower or "get url" in lower or "read url" in lower:
            fetch_result = _first_tool_result(request.tool_results, "web.fetch")
            lines.extend(["", "Web fetch:"])
            if fetch_result:
                payload = _tool_json(fetch_result)
                metadata = fetch_result.get("metadata", {})
                status = str(fetch_result.get("status", payload.get("status", "")))
                lines.append(
                    f"`web.fetch` for `{payload.get('url', metadata.get('url', ''))}` returned {status}; "
                    f"network_request_performed={str(metadata.get('network_request_performed', False)).lower()}; "
                    f"browser_auto_launch={str(metadata.get('browser_auto_launch', False)).lower()}."
                )
                if status == "needs_approval":
                    command = terminal_command_name()
                    lines.append(f"Approve explicitly with `/web fetch <url> | approve` or `{command} fetch <url> --approved`.")
                elif payload.get("body"):
                    preview = str(payload.get("body", "")).strip().splitlines()[:8]
                    lines.append("Preview:")
                    lines.extend(f"  {line}" for line in preview)
            else:
                lines.append("No typed URL was detected. Use `/web fetch <url> | approve` for an approved terminal fetch.")
        else:
            lines.extend(
                [
                    "",
                    "I recorded the request and can continue from the terminal shell. Use `/run <read-only command>` for governed local inspection, `/tools` for policy state, and `/sessions` to review the transcript.",
                ]
            )

        lines.extend(
            [
                "",
                "Provider note: this response used the built-in local provider. No browser surface, network call, API key, or external model route was used.",
            ]
        )
        return ModelResponse(
            provider=self.name,
            mode=self.mode,
            content="\n".join(lines),
            metadata={
                "external_model_invocation_performed": False,
                "provider_route_status": "local",
                "workspace_file_count": snapshot["file_count"],
            },
        )

    def _workspace_snapshot(self) -> dict[str, Any]:
        files: list[str] = []
        for path in sorted(self.paths.workspace.rglob("*")):
            if len(files) >= 12:
                break
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(self.paths.workspace)
            except ValueError:
                continue
            if rel.name == ".DS_Store":
                continue
            if rel.parts and rel.parts[0] in {".aegisagent", ".git", "node_modules", "__pycache__", ".pytest_cache"}:
                continue
            files.append(str(rel))
        return {"file_count": len(files), "files": files}


class OpenAICompatibleProvider:
    mode = "api_key"

    def __init__(self, paths: RuntimePaths, *, name: str, api_key_env: str, base_url: str = ""):
        self.paths = paths
        self.name = name
        self.api_key_env = api_key_env
        self.base_url = (base_url or _default_base_url(name)).rstrip("/")

    def complete(self, request: ModelRequest) -> ModelResponse:
        import os

        api_key = os.environ.get(self.api_key_env, "")
        if not api_key:
            return _blocked_external_response(self.name, "api_key_env_missing", f"{self.api_key_env or 'api key env'} is not present")
        url_check = _validate_base_url(self.base_url)
        if url_check:
            return _blocked_external_response(self.name, "base_url_blocked", url_check)
        endpoint = f"{self.base_url}/chat/completions"
        body = json.dumps(
            {
                "model": _model_name(self.name),
                "messages": _messages_for_request(request),
                "temperature": 0.2,
            }
        ).encode("utf-8")
        http_request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(http_request, timeout=30) as response:
                raw = response.read(1_000_000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", errors="replace")
            return _failed_external_response(self.name, f"http_{exc.code}", detail)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return _failed_external_response(self.name, "request_failed", str(exc))
        redacted = redact_text(raw)
        try:
            payload = json.loads(redacted.text)
        except json.JSONDecodeError:
            return _failed_external_response(self.name, "invalid_json", redacted.text[:600])
        content = _content_from_openai_payload(payload)
        if not content:
            return _failed_external_response(self.name, "empty_response", redacted.text[:600])
        usage = _usage_from_openai_payload(payload)
        return ModelResponse(
            provider=self.name,
            mode=self.mode,
            content=content,
            metadata={
                "external_model_invocation_performed": True,
                "provider_route_status": "completed",
                "base_url_host": urllib.parse.urlparse(self.base_url).netloc,
                "raw_secret_values_included": False,
                "redacted": redacted.redacted,
                **usage,
            },
        )


class FallbackModelProvider:
    def __init__(self, *, primary: OpenAICompatibleProvider, fallback: LocalTerminalProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.mode = primary.mode

    def complete(self, request: ModelRequest) -> ModelResponse:
        primary_response = self.primary.complete(request)
        primary_status = str(primary_response.metadata.get("provider_route_status", ""))
        if primary_status == "completed" or not primary_response.metadata.get("external_model_invocation_performed"):
            return primary_response
        fallback_response = self.fallback.complete(request)
        content = (
            "External provider route failed, so Aegis used the local terminal fallback.\n"
            f"- Primary provider: {self.primary.name}\n"
            f"- Primary status: {primary_status or 'failed'}\n"
            f"- Fallback provider: {fallback_response.provider}\n"
            "- Browser auto-launch: false\n"
            "- Raw secret values included: false\n"
            "\n"
            f"{fallback_response.content}"
        )
        return ModelResponse(
            provider=fallback_response.provider,
            mode=fallback_response.mode,
            content=content,
            metadata={
                **fallback_response.metadata,
                "external_model_invocation_performed": True,
                "provider_route_status": f"fallback_local_after_{primary_status or 'external_failure'}",
                "primary_provider": self.primary.name,
                "primary_provider_mode": self.primary.mode,
                "primary_provider_route_status": primary_status,
                "fallback_used": True,
                "fallback_provider": fallback_response.provider,
                "fallback_mode": fallback_response.mode,
                "raw_secret_values_included": False,
            },
        )


def provider_for_active_route(paths: RuntimePaths):
    from aegisagent.core.provider_config import LOCAL_PROVIDER, ProviderStore

    store = ProviderStore(paths)
    active = store.active_provider()
    try:
        route = store.route(active)
    except KeyError:
        return LocalTerminalProvider(paths), {"route": active, "status": "missing"}
    if route.name == LOCAL_PROVIDER or route.mode == "local":
        return LocalTerminalProvider(paths), {"route": route.name, "status": route.status}
    if route.mode == "api_key" and route.status == "env_present_unverified":
        primary = OpenAICompatibleProvider(paths, name=route.name, api_key_env=route.api_key_env, base_url=route.base_url)
        fallback = LocalTerminalProvider(paths)
        return FallbackModelProvider(primary=primary, fallback=fallback), {"route": route.name, "status": route.status, "fallback": fallback.name}
    return LocalTerminalProvider(paths), {"route": route.name, "status": route.status, "fallback": "local"}


def _first_tool_result(results: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for result in results:
        if result.get("name") == name:
            return result
    return None


def _is_role_worker_prompt(lower_prompt: str) -> bool:
    return "you are the " in lower_prompt and " subagent" in lower_prompt and "deliverable:" in lower_prompt


def _role_from_prompt(lower_prompt: str) -> str:
    for role in ("planner", "researcher", "implementer", "reviewer"):
        if f"you are the {role} subagent" in lower_prompt:
            return role
    return "worker"


def _task_from_role_prompt(prompt: str) -> str:
    marker = "for:"
    index = prompt.lower().rfind(marker)
    if index < 0:
        return prompt.strip()[:160]
    return prompt[index + len(marker) :].strip()[:240]


def _local_role_contribution(role: str, task: str) -> str:
    if role == "planner":
        return f"Checkpoint plan with acceptance evidence and risk gates. Keep terminal-first verification ahead of browser or gateway surfaces. Task: {task}"
    if role == "researcher":
        return f"Evidence summary with applicable patterns, gaps, and files to inspect. Prefer typed tools, durable sessions, and audit receipts. Task: {task}"
    if role == "implementer":
        return f"Minimal patch plus targeted tests and docs updates. Preserve policy gates, redaction, and no-surprise external actions. Task: {task}"
    if role == "reviewer":
        return f"Finding list or explicit no-finding statement with residual risks. Check claims against receipts, tests, and current workspace evidence. Task: {task}"
    return f"Concise completion summary for bounded local work. Task: {task}"


def _tool_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(result.get("content", "{}")))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _default_base_url(provider_name: str) -> str:
    if provider_name.startswith("openai/"):
        return "https://api.openai.com/v1"
    return "https://api.openai.com/v1"


def _validate_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.username or parsed.password:
        return "provider base URL must not include credentials"
    if parsed.query or parsed.fragment:
        return "provider base URL must not include query strings or fragments"
    if parsed.scheme == "https":
        return ""
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return ""
    return "provider base URL must be HTTPS unless it is a loopback development endpoint"


def _model_name(provider_name: str) -> str:
    return provider_name.split("/", 1)[1] if "/" in provider_name else provider_name


def _messages_for_request(request: ModelRequest) -> list[dict[str, str]]:
    safe_prompt = redact_text(request.prompt).text
    tool_summary = ""
    if request.tool_results:
        tool_summary = "\n\nTyped tool results:\n" + redact_text(json.dumps(request.tool_results[-6:], indent=2)[:8000]).text
    artifact_summary = ""
    if request.context_artifacts:
        artifact_summary = "\n\nContext artifacts:\n" + redact_text(json.dumps(_artifact_context(request.context_artifacts), indent=2)[:8000]).text
    recent = []
    for message in request.transcript[-8:]:
        role = str(message.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        recent.append({"role": role, "content": redact_text(str(message.get("content") or "")[:4000]).text})
    if not recent or recent[-1].get("content") != safe_prompt:
        recent.append({"role": "user", "content": safe_prompt})
    return [
        {
            "role": "system",
            "content": (
                "You are AegisAgent running in a terminal-first governed shell. "
                "Be concise, preserve safety constraints, do not claim browser access unless tool evidence says so, "
                "and use typed tool evidence when present."
            ),
        },
        *recent,
        {"role": "user", "content": f"Workspace: {request.workspace}{tool_summary}{artifact_summary}"},
    ]


def _artifact_context(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifacts[-8:]:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            {
                "id": str(artifact.get("id") or ""),
                "role": str(artifact.get("role") or ""),
                "title": str(artifact.get("title") or ""),
                "kind": str(artifact.get("kind") or ""),
                "summary": str(artifact.get("summary") or "")[:1200],
                "input_artifacts": [str(item) for item in artifact.get("input_artifacts", []) if item],
                "content_included": bool(artifact.get("content_included")),
            }
        )
    return rows


def _content_from_openai_payload(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first, dict) else {}
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text") if isinstance(first, dict) else ""
    return text if isinstance(text, str) else ""


def _usage_from_openai_payload(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    result: dict[str, int] = {}
    for source, target in (
        ("prompt_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        value = usage.get(source)
        if isinstance(value, int) and value >= 0:
            result[target] = value
    return result


def _blocked_external_response(provider: str, status: str, detail: str) -> ModelResponse:
    command = terminal_command_name()
    return ModelResponse(
        provider=provider,
        mode="api_key",
        content=(
            "External provider route is not ready, so Aegis did not send the prompt to a model.\n"
            f"- Provider: {provider}\n"
            f"- Status: {status}\n"
            f"- Detail: {redact_text(detail).text}\n"
            f"- Next: run `{command} model doctor` and keep using the local terminal provider until the route is ready."
        ),
        metadata={
            "external_model_invocation_performed": False,
            "provider_route_status": status,
            "raw_secret_values_included": False,
        },
    )


def _failed_external_response(provider: str, status: str, detail: str) -> ModelResponse:
    return ModelResponse(
        provider=provider,
        mode="api_key",
        content=(
            "External provider route failed closed after an attempted model call.\n"
            f"- Provider: {provider}\n"
            f"- Status: {status}\n"
            f"- Detail: {redact_text(detail).text[:600]}\n"
            "- No browser was opened and no raw secret value is included in this transcript."
        ),
        metadata={
            "external_model_invocation_performed": True,
            "provider_route_status": status,
            "raw_secret_values_included": False,
        },
    )
