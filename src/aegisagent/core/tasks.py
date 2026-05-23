from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.models import utc_now
from aegisagent.security.audit import AuditLog
from aegisagent.security.redaction import redact_text

_DETACHED_PROCESSES: dict[int, subprocess.Popen[bytes]] = {}


@dataclass
class TaskRecord:
    id: str
    prompt: str
    status: str = "queued"
    session_id: str = "main"
    source: str = "terminal"
    pid: int | None = None
    receipt_id: str = ""
    assistant_preview: str = ""
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "status": self.status,
            "session_id": self.session_id,
            "source": self.source,
            "pid": self.pid,
            "receipt_id": self.receipt_id,
            "assistant_preview": self.assistant_preview,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        return cls(
            id=str(data["id"]),
            prompt=str(data["prompt"]),
            status=str(data.get("status") or "queued"),
            session_id=str(data.get("session_id") or "main"),
            source=str(data.get("source") or "terminal"),
            pid=int(data["pid"]) if data.get("pid") is not None else None,
            receipt_id=str(data.get("receipt_id") or ""),
            assistant_preview=str(data.get("assistant_preview") or ""),
            summary=str(data.get("summary") or ""),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
            started_at=str(data.get("started_at") or ""),
            completed_at=str(data.get("completed_at") or ""),
        )


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: str
    event: str
    message: str
    status: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "event": self.event,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskEvent":
        return cls(
            task_id=str(data["task_id"]),
            event=str(data["event"]),
            message=str(data["message"]),
            status=str(data.get("status") or ""),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass(frozen=True, slots=True)
class TaskOutput:
    task_id: str
    kind: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskOutput":
        return cls(
            task_id=str(data["task_id"]),
            kind=str(data["kind"]),
            title=str(data["title"]),
            content=str(data.get("content") or ""),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or utc_now()),
        )


class TaskStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)

    def create(self, prompt: str, *, session_id: str = "main", source: str = "terminal") -> TaskRecord:
        redacted = redact_text(prompt)
        record = TaskRecord(id=uuid4().hex[:10], prompt=redacted.text, session_id=session_id, source=source)
        self.save(record)
        return record

    def save(self, record: TaskRecord) -> None:
        record.updated_at = utc_now()
        self.paths.tasks_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.tasks_dir / f"{record.id}.json").write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")

    def append_event(self, event: TaskEvent) -> None:
        self.paths.tasks_dir.mkdir(parents=True, exist_ok=True)
        with (self.paths.tasks_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def append_output(self, output: TaskOutput) -> None:
        self.paths.tasks_dir.mkdir(parents=True, exist_ok=True)
        with (self.paths.tasks_dir / "outputs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output.to_dict(), sort_keys=True) + "\n")

    def events(self, task_id: str, limit: int = 100) -> list[TaskEvent]:
        path = self.paths.tasks_dir / "events.jsonl"
        if not path.exists():
            return []
        rows: list[TaskEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = TaskEvent.from_dict(json.loads(line))
            if event.task_id == task_id:
                rows.append(event)
        return rows[-limit:]

    def outputs(self, task_id: str, limit: int = 100) -> list[TaskOutput]:
        path = self.paths.tasks_dir / "outputs.jsonl"
        if not path.exists():
            return []
        rows: list[TaskOutput] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            output = TaskOutput.from_dict(json.loads(line))
            if output.task_id == task_id:
                rows.append(output)
        return rows[-limit:]

    def get(self, task_id: str) -> TaskRecord:
        path = self.paths.tasks_dir / f"{task_id}.json"
        if not path.exists():
            raise KeyError(f"task not found: {task_id}")
        return TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.tasks_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append(self.get(path.stem).to_dict())
            if len(rows) >= limit:
                break
        return rows


class TaskRunner:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.store = TaskStore(paths)
        self.audit = AuditLog(paths)

    def submit(self, prompt: str, *, session_id: str = "main", source: str = "terminal") -> TaskRecord:
        record = self.store.create(prompt, session_id=session_id, source=source)
        receipt = self.audit.append(
            "task.submitted",
            {"task_id": record.id, "session_id": session_id, "source": source, "prompt_chars": len(record.prompt), "external_action_started": False},
        )
        record.receipt_id = receipt["id"]
        self.store.save(record)
        self._event(record.id, "submitted", "Task queued for terminal execution.", status=record.status)
        return record

    def submit_background(self, prompt: str, *, session_id: str = "main", source: str = "terminal") -> TaskRecord:
        record = self.submit(prompt, session_id=session_id, source=source)
        return self.start_background(record.id)

    def start_background(self, task_id: str) -> TaskRecord:
        record = self.store.get(task_id)
        if record.status not in {"queued"}:
            self.audit.append("task.background.start_ignored", {"task_id": record.id, "status": record.status, "external_action_started": False})
            self._event(record.id, "background.start_ignored", f"Task was not queued; status is {record.status}.", status=record.status)
            return record
        if os.environ.get("AEGISAGENT_TASK_NO_SPAWN"):
            self.audit.append("task.background.queued", {"task_id": record.id, "external_action_started": False})
            self._event(record.id, "background.queued", "Background worker spawn skipped by test/runtime flag.", status=record.status)
            return record
        command = [
            sys.executable,
            "-m",
            "aegisagent",
            "--workspace",
            str(self.paths.workspace),
            "tasks",
            "--run",
            record.id,
        ]
        env = os.environ.copy()
        env["AEGISAGENT_TASK_WORKER"] = "1"
        src_dir = _source_path()
        if src_dir:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")
        stdout_path = _worker_log_path(self.paths, record.id, "stdout")
        stderr_path = _worker_log_path(self.paths, record.id, "stderr")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("ab") as stdout_handle, stderr_path.open("ab") as stderr_handle:
            process = subprocess.Popen(command, cwd=self.paths.workspace, env=env, stdout=stdout_handle, stderr=stderr_handle, start_new_session=True)
        _DETACHED_PROCESSES[process.pid] = process
        record.status = "running"
        record.pid = process.pid
        record.started_at = utc_now()
        self.store.save(record)
        self.audit.append("task.background.started", {"task_id": record.id, "pid": record.pid, "external_action_started": False})
        self._event(record.id, "background.started", f"Detached task worker started with pid {record.pid}.", status=record.status)
        return record

    def run(self, task_id: str) -> TaskRecord:
        from aegisagent.core.agent import AgentRuntime

        record = self.store.get(task_id)
        if record.status == "cancelled":
            self.audit.append("task.run_ignored", {"task_id": record.id, "status": record.status, "reason": "cancelled"})
            self._event(record.id, "run.ignored", "Cancelled task was not run.", status=record.status)
            return record
        if record.status == "completed":
            self.audit.append("task.run_ignored", {"task_id": record.id, "status": record.status, "reason": "already_completed"})
            self._event(record.id, "run.ignored", "Completed task was not run again.", status=record.status)
            return record
        if record.status == "running" and not os.environ.get("AEGISAGENT_TASK_WORKER"):
            self.audit.append("task.run_ignored", {"task_id": record.id, "status": record.status, "reason": "already_running"})
            self._event(record.id, "run.ignored", "Running task was not started again.", status=record.status)
            return record
        record.status = "running"
        record.started_at = record.started_at or utc_now()
        self.store.save(record)
        self.audit.append("task.started", {"task_id": record.id, "session_id": record.session_id, "external_action_started": False})
        self._event(record.id, "started", "Task runner entered AgentRuntime.", status=record.status)
        try:
            if os.environ.get("AEGISAGENT_TASK_SLEEP"):
                self._event(record.id, "waiting", f"Task worker sleeping for {os.environ['AEGISAGENT_TASK_SLEEP']} seconds.", status=record.status)
                time.sleep(float(os.environ["AEGISAGENT_TASK_SLEEP"]))
                record = self.store.get(task_id)
                if record.status == "cancelled":
                    self._event(record.id, "stopped", "Task observed cancellation before model turn.", status=record.status)
                    return record
            turn = AgentRuntime(self.paths).respond(record.prompt, session_id=record.session_id, source="task")
            self._record_outputs(record.id, turn)
        except Exception as exc:
            record.status = "failed"
            record.summary = str(exc)
            record.completed_at = utc_now()
            receipt = self.audit.append("task.failed", {"task_id": record.id, "error": str(exc), "external_action_started": False})
            record.receipt_id = receipt["id"]
            self.store.save(record)
            self._event(record.id, "failed", str(exc), status=record.status)
            return record
        self._event(record.id, "model.completed", f"Agent turn completed with receipt {turn.receipt_id}.", status="running")
        record.status = "completed"
        record.pid = None
        record.session_id = turn.session_id
        record.receipt_id = turn.receipt_id
        record.assistant_preview = _preview(turn.assistant_message)
        record.summary = f"Completed in session {turn.session_id}."
        record.completed_at = utc_now()
        self.store.save(record)
        self.audit.append(
            "task.completed",
            {"task_id": record.id, "session_id": turn.session_id, "turn_receipt_id": turn.receipt_id, "external_action_started": False},
        )
        self._event(record.id, "completed", record.summary, status=record.status)
        return record

    def cancel(self, task_id: str, *, reason: str = "Cancelled by operator.") -> TaskRecord:
        record = self.store.get(task_id)
        if record.status in {"completed", "failed", "cancelled"}:
            self.audit.append("task.cancel_ignored", {"task_id": record.id, "status": record.status})
            self._event(record.id, "cancel.ignored", f"Task is already {record.status}.", status=record.status)
            return record
        signal_sent = False
        if record.pid and _pid_alive(record.pid):
            try:
                os.killpg(record.pid, signal.SIGTERM)
                signal_sent = True
                _reap_child(record.pid)
            except (ProcessLookupError, PermissionError):
                signal_sent = False
        record.status = "cancelled"
        record.pid = None
        record.summary = reason
        record.completed_at = utc_now()
        receipt = self.audit.append("task.cancelled", {"task_id": record.id, "reason": reason, "signal_sent": signal_sent, "external_action_started": False})
        record.receipt_id = receipt["id"]
        self.store.save(record)
        self._event(record.id, "cancelled", reason, status=record.status)
        return record

    def recover_stale_running(self, task_id: str | None = None) -> list[TaskRecord]:
        records = [self.store.get(task_id)] if task_id else [TaskRecord.from_dict(row) for row in self.store.list(limit=1000)]
        recovered: list[TaskRecord] = []
        for record in records:
            if record.status != "running" or not record.pid or _pid_alive(record.pid):
                continue
            stale_pid = record.pid
            record.status = "failed"
            record.pid = None
            record.summary = f"Detached worker pid {stale_pid} is no longer running; task marked failed during recovery."
            record.completed_at = utc_now()
            receipt = self.audit.append("task.recovered_stale", {"task_id": record.id, "pid": stale_pid, "external_action_started": False})
            record.receipt_id = receipt["id"]
            self.store.save(record)
            self._event(record.id, "recovered.stale", record.summary, status=record.status)
            recovered.append(record)
        return recovered

    def get(self, task_id: str, *, recover_stale: bool = True) -> TaskRecord:
        if recover_stale:
            self.recover_stale_running(task_id)
        return self.store.get(task_id)

    def list(self, *, limit: int = 50, recover_stale: bool = True) -> list[dict[str, Any]]:
        if recover_stale:
            self.recover_stale_running()
        return self.store.list(limit=limit)

    def events(self, task_id: str, *, limit: int = 100) -> list[TaskEvent]:
        return self.store.events(task_id, limit=limit)

    def outputs(self, task_id: str, *, limit: int = 100) -> list[TaskOutput]:
        return self.store.outputs(task_id, limit=limit)

    def worker_logs(self, task_id: str, *, max_bytes: int = 12000) -> dict[str, Any]:
        _reap_finished_children()
        return {
            "task_id": task_id,
            "stdout": _read_worker_log(self.paths, task_id, "stdout", max_bytes=max_bytes),
            "stderr": _read_worker_log(self.paths, task_id, "stderr", max_bytes=max_bytes),
        }

    def _event(self, task_id: str, event: str, message: str, *, status: str = "") -> None:
        self.store.append_event(TaskEvent(task_id=task_id, event=event, message=message, status=status))

    def _record_outputs(self, task_id: str, turn: Any) -> None:
        for result in turn.tool_results:
            content = redact_text(str(result.get("content") or "")).text
            name = str(result.get("name") or "tool")
            self.store.append_output(
                TaskOutput(
                    task_id=task_id,
                    kind="tool",
                    title=name,
                    content=content,
                    metadata=dict(result.get("metadata") or {}),
                )
            )
            self._event(task_id, "output.tool", f"Recorded tool output: {name}.", status="running")
        assistant_content = redact_text(str(turn.assistant_message)).text
        self.store.append_output(
            TaskOutput(
                task_id=task_id,
                kind="assistant",
                title="assistant",
                content=assistant_content,
                metadata={"session_id": turn.session_id, "receipt_id": turn.receipt_id},
            )
        )
        self._event(task_id, "output.assistant", "Recorded assistant output.", status="running")


def format_task(record: TaskRecord | dict[str, Any]) -> str:
    payload = record.to_dict() if isinstance(record, TaskRecord) else record
    lines = [
        "AEGIS TASK",
        f"task      {payload.get('id', '')}",
        f"status    {payload.get('status', '')}",
        f"session   {payload.get('session_id', '')}",
        f"created   {payload.get('created_at', '')}",
        f"prompt    {payload.get('prompt', '')}",
    ]
    if payload.get("summary"):
        lines.append(f"summary   {payload.get('summary', '')}")
    if payload.get("pid"):
        lines.append(f"pid       {payload.get('pid', '')}")
    if payload.get("assistant_preview"):
        lines.append(f"preview   {payload.get('assistant_preview', '')}")
    if payload.get("receipt_id"):
        lines.append(f"receipt   {payload.get('receipt_id', '')}")
    return "\n".join(lines)


def format_tasks(records: list[dict[str, Any]]) -> str:
    if not records:
        return "AEGIS TASKS\n(no tasks)"
    lines = ["AEGIS TASKS"]
    for record in records:
        prompt = str(record.get("prompt", "")).replace("\n", " ")[:64]
        pid = str(record.get("pid") or "-")
        lines.append(f"{record.get('id', ''):<10} {record.get('status', ''):<10} {pid:<8} {record.get('session_id', ''):<18} {prompt}")
    return "\n".join(lines)


def format_task_events(events: list[TaskEvent]) -> str:
    if not events:
        return "AEGIS TASK EVENTS\nNo events found for that task."
    lines = ["AEGIS TASK EVENTS", "time                  event                    status      message"]
    for event in events[-80:]:
        lines.append(f"{event.created_at:<21} {event.event:<24} {event.status:<11} {event.message}")
    return "\n".join(lines)


def format_task_outputs(outputs: list[TaskOutput]) -> str:
    if not outputs:
        return "AEGIS TASK OUTPUT\nNo output has been recorded for that task."
    lines = ["AEGIS TASK OUTPUT"]
    for output in outputs[-20:]:
        lines.append(f"{output.created_at}  {output.kind:<9} {output.title}")
        preview = str(output.content).strip()
        if not preview:
            lines.append("  (empty)")
            continue
        for line in preview.splitlines()[:12]:
            lines.append(f"  {line[:160]}")
    return "\n".join(lines)


def format_task_worker_logs(logs: dict[str, Any]) -> str:
    lines = ["AEGIS TASK WORKER LOGS"]
    any_content = False
    for stream in ("stdout", "stderr"):
        payload = logs.get(stream, {})
        content = str(payload.get("content") or "")
        lines.append(f"{stream}  {payload.get('bytes', 0)} bytes  truncated={str(payload.get('truncated', False)).lower()}")
        if content.strip():
            any_content = True
            for line in content.strip().splitlines()[-20:]:
                lines.append(f"  {line[:160]}")
        else:
            lines.append("  (empty)")
    if not any_content:
        lines.append("No worker stdout/stderr has been recorded yet.")
    return "\n".join(lines)


def _preview(value: str, *, limit: int = 240) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _source_path() -> Path | None:
    package_root = Path(__file__).resolve().parents[2]
    if package_root.name == "src":
        return package_root
    return None


def _worker_log_path(paths: RuntimePaths, task_id: str, stream: str) -> Path:
    return paths.tasks_dir / f"{task_id}.{stream}.log"


def _read_worker_log(paths: RuntimePaths, task_id: str, stream: str, *, max_bytes: int) -> dict[str, Any]:
    path = _worker_log_path(paths, task_id, stream)
    if not path.exists():
        return {"path": str(path), "bytes": 0, "truncated": False, "content": ""}
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    sample = data[-max_bytes:] if truncated else data
    redacted = redact_text(sample.decode("utf-8", errors="replace")).text
    return {"path": str(path), "bytes": len(data), "truncated": truncated, "content": redacted}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reap_child(pid: int, *, timeout: float = 1.0) -> None:
    process = _DETACHED_PROCESSES.pop(pid, None)
    if process is not None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            waited, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if waited:
            return
        time.sleep(0.05)


def _reap_finished_children() -> None:
    for pid, process in list(_DETACHED_PROCESSES.items()):
        if process.poll() is None:
            continue
        try:
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            continue
        _DETACHED_PROCESSES.pop(pid, None)
