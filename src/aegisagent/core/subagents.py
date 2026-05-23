from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.core.sessions import SessionStore
from aegisagent.models import utc_now
from aegisagent.security.audit import AuditLog


@dataclass(frozen=True)
class SubagentLimits:
    max_concurrency: int = 8
    max_depth: int = 2
    max_children: int = 5


AGENT_CONTRACT_VERSION = "2026-05-23.role-contracts.v1"


AGENT_PROFILES: tuple[dict[str, str], ...] = (
    {
        "name": "planner",
        "role": "planner",
        "purpose": "Break work into terminal-first checkpoints and verification gates.",
        "context_contract": "Use the user objective, PLAN.md, capability gaps, and existing progress notes; do not assume web/browser is primary.",
        "deliverable": "Checkpoint plan with acceptance evidence and risk gates.",
        "tool_budget": "read-only repo inspection plus one concise plan artifact",
    },
    {
        "name": "researcher",
        "role": "researcher",
        "purpose": "Inspect workspace state and prior patterns before implementation.",
        "context_contract": "Compare current files with referenced Aegis/Hermes patterns and cite concrete local evidence.",
        "deliverable": "Evidence summary with applicable patterns, gaps, and files to inspect.",
        "tool_budget": "read-only search, file reads, and metadata-only external comparison",
    },
    {
        "name": "implementer",
        "role": "implementer",
        "purpose": "Make scoped code changes while preserving policy and audit controls.",
        "context_contract": "Edit only the scoped subsystem after planner/researcher context; preserve approval and redaction behavior.",
        "deliverable": "Minimal patch plus targeted tests and docs updates.",
        "tool_budget": "workspace edits, focused tests, no external delivery",
    },
    {
        "name": "reviewer",
        "role": "reviewer",
        "purpose": "Check safety, missing tests, dead controls, and overclaimed evidence.",
        "context_contract": "Review current diff, tests, safety flags, and user objective before any completion claim.",
        "deliverable": "Finding list or explicit no-finding statement with residual risks.",
        "tool_budget": "read-only diff/test review and final verification commands",
    },
)


def _profile_for(role: str) -> dict[str, str]:
    for profile in AGENT_PROFILES:
        if profile["role"] == role or profile["name"] == role:
            return profile
    return {
        "name": role,
        "role": role,
        "purpose": "Complete bounded local work.",
        "context_contract": "Use only the provided task and current workspace state.",
        "deliverable": "Concise completion summary.",
        "tool_budget": "bounded local work",
    }


def _profile_contract(role: str) -> dict[str, str]:
    profile = _profile_for(role)
    return {
        "role": profile["role"],
        "purpose": profile["purpose"],
        "context_contract": profile["context_contract"],
        "deliverable": profile["deliverable"],
        "tool_budget": profile["tool_budget"],
    }


def agent_contracts_payload(paths: RuntimePaths, *, limits: SubagentLimits | None = None) -> dict[str, Any]:
    resolved_limits = limits or SubagentLimits()
    ensure_runtime(paths)
    return {
        "surface": "agent_contracts",
        "contract_version": AGENT_CONTRACT_VERSION,
        "terminal_first": True,
        "browser_auto_launch": False,
        "external_action_started": False,
        "limits": {
            "max_concurrency": resolved_limits.max_concurrency,
            "max_depth": resolved_limits.max_depth,
            "max_children": resolved_limits.max_children,
        },
        "profiles": [_profile_contract(profile["role"]) for profile in AGENT_PROFILES],
        "next": [
            "Use `aegisagent agents delegate <task>` to run these contracts once.",
            "Use `/agents bg <task>` for a nonblocking contracted delegation.",
            "Review audit receipts for contract_version before trusting a delegation summary.",
        ],
    }


def agent_status(paths: RuntimePaths, *, limits: SubagentLimits | None = None) -> dict[str, Any]:
    resolved_limits = limits or SubagentLimits()
    ensure_runtime(paths)
    return {
        "surface": "agents",
        "backing_runtime": "local_subagents",
        "terminal_first": True,
        "browser_auto_launch": False,
        "external_action_started": False,
        "profiles": list(AGENT_PROFILES),
        "contract_version": AGENT_CONTRACT_VERSION,
        "limits": {
            "max_concurrency": resolved_limits.max_concurrency,
            "max_depth": resolved_limits.max_depth,
            "max_children": resolved_limits.max_children,
        },
        "persisted_subagents": len(SubagentStore(paths).list(limit=1000)),
        "background_jobs": len(BackgroundJobStore(paths).list(limit=1000)),
        "commands": [
            "aegisagent agents",
            "aegisagent agents profiles",
            "aegisagent agents contracts",
            "aegisagent agents delegate <task>",
            "aegisagent agents background <task>",
            "/agents",
            "/agents profiles",
            "/agents contracts",
            "/agents delegate <task>",
            "/agents bg <task>",
        ],
    }


@dataclass
class SubagentRecord:
    id: str
    parent_id: str | None
    task: str
    depth: int
    role: str = "worker"
    session_id: str = ""
    status: str = "queued"
    children: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "task": self.task,
            "depth": self.depth,
            "role": self.role,
            "session_id": self.session_id,
            "status": self.status,
            "children": self.children,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubagentRecord":
        return cls(
            id=str(data["id"]),
            parent_id=str(data["parent_id"]) if data.get("parent_id") else None,
            task=str(data["task"]),
            depth=int(data["depth"]),
            role=str(data.get("role") or "worker"),
            session_id=str(data.get("session_id") or ""),
            status=str(data.get("status") or "queued"),
            children=[str(child) for child in data.get("children", [])],
            summary=str(data.get("summary") or ""),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


@dataclass(frozen=True, slots=True)
class SubagentEvent:
    root_id: str
    event: str
    message: str
    role: str = ""
    worker_id: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, str]:
        return {
            "root_id": self.root_id,
            "event": self.event,
            "message": self.message,
            "role": self.role,
            "worker_id": self.worker_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubagentEvent":
        return cls(
            root_id=str(data["root_id"]),
            event=str(data["event"]),
            message=str(data["message"]),
            role=str(data.get("role") or ""),
            worker_id=str(data.get("worker_id") or ""),
            created_at=str(data.get("created_at") or utc_now()),
        )


class SubagentQueue:
    def __init__(self, limits: SubagentLimits | None = None):
        self.limits = limits or SubagentLimits()
        self.records: dict[str, SubagentRecord] = {}

    def spawn(self, task: str, *, parent_id: str | None = None, role: str = "worker", session_id: str = "") -> SubagentRecord:
        running = sum(1 for item in self.records.values() if item.status in {"queued", "running"})
        if running >= self.limits.max_concurrency:
            raise ValueError("subagent concurrency limit reached")
        depth = 0
        if parent_id:
            parent = self.records[parent_id]
            if len(parent.children) >= self.limits.max_children:
                raise ValueError("subagent child limit reached")
            depth = parent.depth + 1
            if depth > self.limits.max_depth:
                raise ValueError("subagent depth limit reached")
        record = SubagentRecord(id=uuid4().hex[:10], parent_id=parent_id, task=task, depth=depth, role=role, session_id=session_id)
        self.records[record.id] = record
        if parent_id:
            self.records[parent_id].children.append(record.id)
        return record

    def cascade_stop(self, record_id: str) -> list[str]:
        stopped: list[str] = []
        record = self.records[record_id]
        for child_id in list(record.children):
            stopped.extend(self.cascade_stop(child_id))
        record.status = "stopped"
        stopped.append(record_id)
        return stopped

    def list(self) -> list[dict]:
        return [record.to_dict() for record in self.records.values()]


class SubagentStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)

    def save(self, record: SubagentRecord) -> None:
        record.updated_at = utc_now()
        self.paths.subagents_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.subagents_dir / f"{record.id}.json").write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")

    def append_event(self, event: SubagentEvent) -> None:
        self.paths.subagents_dir.mkdir(parents=True, exist_ok=True)
        with (self.paths.subagents_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def events(self, root_id: str, limit: int = 100) -> list[SubagentEvent]:
        path = self.paths.subagents_dir / "events.jsonl"
        if not path.exists():
            return []
        rows: list[SubagentEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = SubagentEvent.from_dict(json.loads(line))
            if event.root_id == root_id:
                rows.append(event)
        return rows[-limit:]

    def get(self, record_id: str) -> SubagentRecord:
        path = self.paths.subagents_dir / f"{record_id}.json"
        if not path.exists():
            raise KeyError(f"subagent not found: {record_id}")
        return SubagentRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.subagents_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append(self.get(path.stem).to_dict())
            if len(rows) >= limit:
                break
        return rows

    def cascade_stop(self, record_id: str) -> list[SubagentRecord]:
        record = self.get(record_id)
        stopped: list[SubagentRecord] = []
        for child_id in record.children:
            stopped.extend(self.cascade_stop(child_id))
        record.status = "stopped"
        record.summary = record.summary or "Stopped by operator cascade."
        self.save(record)
        stopped.append(record)
        return stopped


@dataclass(frozen=True, slots=True)
class SubagentDelegationResult:
    root: SubagentRecord
    workers: list[SubagentRecord]
    receipt_id: str
    events: list[SubagentEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.to_dict(),
            "workers": [worker.to_dict() for worker in self.workers],
            "receipt_id": self.receipt_id,
            "announce_back": self.announce_back,
            "events": [event.to_dict() for event in self.events],
        }

    @property
    def announce_back(self) -> str:
        lines = [f"Delegated `{self.root.task}` to {len(self.workers)} bounded local subagents:"]
        for worker in self.workers:
            lines.append(f"- {worker.role}: {worker.summary}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class SubagentStopResult:
    stopped: list[SubagentRecord]
    receipt_id: str
    events: list[SubagentEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stopped": [record.to_dict() for record in self.stopped],
            "receipt_id": self.receipt_id,
            "summary": self.summary,
            "events": [event.to_dict() for event in self.events],
        }

    @property
    def summary(self) -> str:
        if not self.stopped:
            return "No subagents were stopped."
        return f"Stopped {len(self.stopped)} subagent records: {', '.join(record.id for record in self.stopped)}"


@dataclass
class BackgroundJobRecord:
    id: str
    task: str
    status: str = "queued"
    pid: int | None = None
    root_id: str = ""
    receipt_id: str = ""
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "status": self.status,
            "pid": self.pid,
            "root_id": self.root_id,
            "receipt_id": self.receipt_id,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackgroundJobRecord":
        return cls(
            id=str(data["id"]),
            task=str(data["task"]),
            status=str(data.get("status") or "queued"),
            pid=int(data["pid"]) if data.get("pid") is not None else None,
            root_id=str(data.get("root_id") or ""),
            receipt_id=str(data.get("receipt_id") or ""),
            summary=str(data.get("summary") or ""),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
            started_at=str(data.get("started_at") or ""),
            completed_at=str(data.get("completed_at") or ""),
        )


class BackgroundJobStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)

    def create(self, task: str) -> BackgroundJobRecord:
        record = BackgroundJobRecord(id=uuid4().hex[:10], task=task)
        self.save(record)
        return record

    def save(self, record: BackgroundJobRecord) -> None:
        record.updated_at = utc_now()
        self.paths.jobs_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.jobs_dir / f"{record.id}.json").write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")

    def get(self, job_id: str) -> BackgroundJobRecord:
        path = self.paths.jobs_dir / f"{job_id}.json"
        if not path.exists():
            raise KeyError(f"background job not found: {job_id}")
        return BackgroundJobRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append(self.get(path.stem).to_dict())
            if len(rows) >= limit:
                break
        return rows


class LocalSubagentOrchestrator:
    def __init__(self, paths: RuntimePaths, limits: SubagentLimits | None = None):
        self.paths = paths
        self.limits = limits or SubagentLimits()
        self.store = SubagentStore(paths)
        self.sessions = SessionStore(paths)
        self.audit = AuditLog(paths)

    def delegate(
        self,
        task: str,
        *,
        parent_session_id: str = "main",
        event_sink: Callable[[SubagentEvent], None] | None = None,
    ) -> SubagentDelegationResult:
        queue = SubagentQueue(self.limits)
        root_session = self.sessions.create(f"subagent root {task[:32]}")
        root = queue.spawn(task, role="coordinator", session_id=root_session.id)
        events: list[SubagentEvent] = []
        self._event(events, root.id, "root.started", f"coordinator accepted task: {task}", role=root.role, event_sink=event_sink)
        root.status = "running"
        self.sessions.append(root.session_id, "user", task, metadata={"source": "subagent", "role": root.role, "parent_session_id": parent_session_id})
        self.store.save(root)
        self.audit.append(
            "subagent.delegation.started",
            {
                "root_id": root.id,
                "task": task,
                "parent_session_id": parent_session_id,
                "limits": self.limits.__dict__,
                "contract_version": AGENT_CONTRACT_VERSION,
                "worker_contracts": [_profile_contract(role) for role in ("planner", "researcher", "implementer", "reviewer")],
            },
        )

        workers: list[SubagentRecord] = []
        for role in ("planner", "researcher", "implementer", "reviewer"):
            child_session = self.sessions.create(f"subagent {role} {task[:24]}")
            child = queue.spawn(task, parent_id=root.id, role=role, session_id=child_session.id)
            child.status = "running"
            contract = _profile_contract(role)
            self.sessions.append(
                child.session_id,
                "user",
                _role_prompt(role, task),
                metadata={
                    "source": "subagent",
                    "role": role,
                    "parent_session_id": root.session_id,
                    "contract_version": AGENT_CONTRACT_VERSION,
                    "context_contract": contract["context_contract"],
                    "deliverable": contract["deliverable"],
                    "tool_budget": contract["tool_budget"],
                },
            )
            self.store.save(child)
            self._event(events, root.id, "worker.started", f"{role} started", role=role, worker_id=child.id, event_sink=event_sink)
            self.audit.append(
                "subagent.worker.started",
                {
                    "root_id": root.id,
                    "worker_id": child.id,
                    "role": role,
                    "contract_version": AGENT_CONTRACT_VERSION,
                    "contract": contract,
                    "external_action_started": False,
                },
            )
            workers.append(child)

        max_workers = max(1, min(len(workers), self.limits.max_concurrency - 1))
        completed: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aegis-subagent") as executor:
            future_to_worker = {executor.submit(_role_summary, worker.role, task): worker for worker in workers}
            for future in as_completed(future_to_worker):
                worker = future_to_worker[future]
                completed[worker.id] = future.result()

        workers_by_id = {worker.id: worker for worker in workers}
        workers = []
        for worker_id in sorted(workers_by_id, key=lambda item: ("planner", "researcher", "implementer", "reviewer").index(workers_by_id[item].role)):
            child = workers_by_id[worker_id]
            child.summary = completed[child.id]
            child.status = "completed"
            self.sessions.append(child.session_id, "assistant", child.summary, metadata={"source": "subagent", "role": child.role})
            self.store.save(child)
            self._event(
                events,
                root.id,
                "worker.completed",
                f"{child.role} completed: {child.summary}",
                role=child.role,
                worker_id=child.id,
                event_sink=event_sink,
            )
            self.audit.append(
                "subagent.worker.completed",
                {
                    "root_id": root.id,
                    "worker_id": child.id,
                    "role": child.role,
                    "status": child.status,
                    "contract_version": AGENT_CONTRACT_VERSION,
                    "deliverable": _profile_contract(child.role)["deliverable"],
                    "external_action_started": False,
                },
            )
            workers.append(child)

        root.children = [worker.id for worker in workers]
        root.summary = f"{len(workers)} local subagents completed bounded analysis for: {task}"
        root.status = "completed"
        self.sessions.append(root.session_id, "assistant", root.summary, metadata={"source": "subagent", "role": root.role})
        self.store.save(root)
        self._event(events, root.id, "root.completed", root.summary, role=root.role, event_sink=event_sink)
        receipt = self.audit.append(
            "subagent.delegation.completed",
            {
                "root_id": root.id,
                "worker_ids": [worker.id for worker in workers],
                "worker_roles": [worker.role for worker in workers],
                "parent_session_id": parent_session_id,
                "status": root.status,
                "contract_version": AGENT_CONTRACT_VERSION,
                "worker_contracts": [_profile_contract(worker.role) for worker in workers],
                "external_action_started": False,
            },
        )
        return SubagentDelegationResult(root=root, workers=workers, receipt_id=receipt["id"], events=events)

    def stop(self, record_id: str) -> SubagentStopResult:
        stopped = self.store.cascade_stop(record_id)
        root_id = record_id
        events: list[SubagentEvent] = []
        for record in stopped:
            self._event(events, root_id, "record.stopped", f"{record.role} stopped", role=record.role, worker_id=record.id)
        receipt = self.audit.append(
            "subagent.cascade_stopped",
            {"record_id": record_id, "stopped_ids": [record.id for record in stopped], "external_action_started": False},
        )
        return SubagentStopResult(stopped=stopped, receipt_id=receipt["id"], events=events)

    def events(self, root_id: str, *, limit: int = 100) -> list[SubagentEvent]:
        return self.store.events(root_id, limit=limit)

    def start_background(self, task: str) -> BackgroundJobRecord:
        jobs = BackgroundJobStore(self.paths)
        record = jobs.create(task)
        if os.environ.get("AEGISAGENT_BACKGROUND_NO_SPAWN"):
            self.audit.append("subagent.background.queued", {"job_id": record.id, "task": task, "external_action_started": False})
            return record
        command = [
            sys.executable,
            "-m",
            "aegisagent",
            "--workspace",
            str(self.paths.workspace),
            "subagents",
            "--run-job",
            record.id,
        ]
        env = os.environ.copy()
        src_dir = _source_path()
        if src_dir:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")
        process = subprocess.Popen(command, cwd=self.paths.workspace, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        record.status = "running"
        record.pid = process.pid
        record.started_at = utc_now()
        jobs.save(record)
        self.audit.append("subagent.background.started", {"job_id": record.id, "pid": record.pid, "task": task, "external_action_started": False})
        return record

    def run_background_job(self, job_id: str) -> BackgroundJobRecord:
        jobs = BackgroundJobStore(self.paths)
        record = jobs.get(job_id)
        if record.status in {"completed", "cancelled"}:
            return record
        record.status = "running"
        record.started_at = record.started_at or utc_now()
        jobs.save(record)
        try:
            if os.environ.get("AEGISAGENT_BACKGROUND_SLEEP"):
                time.sleep(float(os.environ["AEGISAGENT_BACKGROUND_SLEEP"]))
                record = jobs.get(job_id)
                if record.status == "cancelled":
                    return record
            result = self.delegate(record.task)
            record.status = "completed"
            record.pid = None
            record.root_id = result.root.id
            record.receipt_id = result.receipt_id
            record.summary = result.announce_back
            record.completed_at = utc_now()
            jobs.save(record)
            self.audit.append(
                "subagent.background.completed",
                {"job_id": record.id, "root_id": record.root_id, "receipt_id": record.receipt_id, "external_action_started": False},
            )
        except Exception as exc:
            record.status = "failed"
            record.pid = None
            record.summary = str(exc)
            record.completed_at = utc_now()
            jobs.save(record)
            self.audit.append("subagent.background.failed", {"job_id": record.id, "error": str(exc), "external_action_started": False})
            raise
        return record

    def cancel_background(self, job_id: str) -> BackgroundJobRecord:
        jobs = BackgroundJobStore(self.paths)
        record = jobs.get(job_id)
        if record.status in {"completed", "failed", "cancelled"}:
            self.audit.append(
                "subagent.background.cancel_ignored",
                {"job_id": record.id, "status": record.status, "external_action_started": False},
            )
            return record

        signal_sent = False
        if record.pid and _pid_alive(record.pid):
            try:
                os.killpg(record.pid, signal.SIGTERM)
                signal_sent = True
            except ProcessLookupError:
                signal_sent = False
            except PermissionError:
                signal_sent = False

        record.status = "cancelled"
        record.pid = None
        record.completed_at = utc_now()
        record.summary = "Cancelled by operator before completion."
        jobs.save(record)
        self.audit.append(
            "subagent.background.cancelled",
            {"job_id": record.id, "pid": record.pid, "signal_sent": signal_sent, "external_action_started": False},
        )
        return record

    def recover_stale_background(self, job_id: str | None = None) -> list[BackgroundJobRecord]:
        jobs = BackgroundJobStore(self.paths)
        records = [jobs.get(job_id)] if job_id else [BackgroundJobRecord.from_dict(row) for row in jobs.list(limit=1000)]
        recovered: list[BackgroundJobRecord] = []
        for record in records:
            if record.status != "running" or not record.pid or _pid_alive(record.pid):
                continue
            stale_pid = record.pid
            record.status = "failed"
            record.pid = None
            record.summary = f"Detached subagent worker pid {stale_pid} is no longer running; job marked failed during recovery."
            record.completed_at = utc_now()
            receipt = self.audit.append("subagent.background.recovered_stale", {"job_id": record.id, "pid": stale_pid, "external_action_started": False})
            record.receipt_id = receipt["id"]
            jobs.save(record)
            recovered.append(record)
        return recovered

    def background_job(self, job_id: str, *, recover_stale: bool = True) -> BackgroundJobRecord:
        if recover_stale:
            self.recover_stale_background(job_id)
        return BackgroundJobStore(self.paths).get(job_id)

    def background_jobs(self, *, limit: int = 50, recover_stale: bool = True) -> list[dict[str, Any]]:
        if recover_stale:
            self.recover_stale_background()
        return BackgroundJobStore(self.paths).list(limit=limit)

    def _event(
        self,
        events: list[SubagentEvent],
        root_id: str,
        event: str,
        message: str,
        *,
        role: str = "",
        worker_id: str = "",
        event_sink: Callable[[SubagentEvent], None] | None = None,
    ) -> None:
        row = SubagentEvent(root_id=root_id, event=event, message=message, role=role, worker_id=worker_id)
        events.append(row)
        self.store.append_event(row)
        if event_sink:
            event_sink(row)


def format_delegation(result: SubagentDelegationResult) -> str:
    lines = [
        "SUBAGENT DELEGATION",
        f"root      {result.root.id}  {result.root.status}  {result.root.task}",
        f"receipt   {result.receipt_id}",
        "",
        "workers",
    ]
    for worker in result.workers:
        lines.append(f"- {worker.role:<11} {worker.id}  {worker.status:<9} {worker.summary}")
    return "\n".join(lines)


def format_agent_status(payload: dict[str, Any]) -> str:
    limits = payload["limits"]
    lines = [
        "AGENTS",
        f"runtime    {payload['backing_runtime']}",
        f"contracts  {payload['contract_version']}",
        f"limits     {limits['max_concurrency']} concurrency / depth {limits['max_depth']} / children {limits['max_children']}",
        f"records    {payload['persisted_subagents']} subagents / {payload['background_jobs']} background jobs",
        f"terminal   first={str(payload['terminal_first']).lower()} browser_auto_launch={str(payload['browser_auto_launch']).lower()}",
        "",
        "profiles",
    ]
    for profile in payload["profiles"]:
        lines.append(f"- {profile['name']:<12} {profile['purpose']}")
    lines.extend(["", "try", "- /agents contracts", "- /agents delegate improve terminal orchestration", "- /agents bg compare current TUI against prior Aegis-Agent"])
    return "\n".join(lines)


def format_agent_profiles() -> str:
    lines = ["AGENT PROFILES", "name         purpose"]
    for profile in AGENT_PROFILES:
        lines.append(f"{profile['name']:<12} {profile['purpose']}")
        lines.append(f"{'':<12} deliverable: {profile['deliverable']}")
        lines.append(f"{'':<12} budget: {profile['tool_budget']}")
    return "\n".join(lines)


def format_agent_contracts(payload: dict[str, Any]) -> str:
    limits = payload["limits"]
    lines = [
        "AGENT CONTRACTS",
        f"version    {payload['contract_version']}",
        f"limits     {limits['max_concurrency']} concurrency / depth {limits['max_depth']} / children {limits['max_children']}",
        f"terminal   first={str(payload['terminal_first']).lower()} browser_auto_launch={str(payload['browser_auto_launch']).lower()}",
        "",
    ]
    for profile in payload["profiles"]:
        lines.extend(
            [
                f"[{profile['role']}]",
                f"purpose    {profile['purpose']}",
                f"context    {profile['context_contract']}",
                f"deliver    {profile['deliverable']}",
                f"budget     {profile['tool_budget']}",
                "",
            ]
        )
    lines.extend(["next", *[f"- {item}" for item in payload["next"]]])
    return "\n".join(lines).rstrip()


def format_subagent_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return "SUBAGENTS\nNo persisted subagents yet. Use /subagents <task> to delegate bounded local work."
    lines = ["SUBAGENTS", "role         status     id          parent      task"]
    for record in records[:20]:
        parent = record.get("parent_id") or "-"
        task = str(record.get("task") or "")
        if len(task) > 42:
            task = task[:39] + "..."
        lines.append(f"{record.get('role', ''):<12} {record.get('status', ''):<10} {record.get('id', ''):<11} {parent:<11} {task}")
    return "\n".join(lines)


def format_stop(result: SubagentStopResult) -> str:
    return "SUBAGENT STOP\n" + result.summary + f"\nreceipt   {result.receipt_id}"


def format_background_job(record: BackgroundJobRecord) -> str:
    lines = [
        "SUBAGENT BACKGROUND JOB",
        f"job       {record.id}  {record.status}",
        f"task      {record.task}",
    ]
    if record.pid:
        lines.append(f"pid       {record.pid}")
    if record.root_id:
        lines.append(f"root      {record.root_id}")
    if record.receipt_id:
        lines.append(f"receipt   {record.receipt_id}")
    if record.summary:
        lines.extend(["", record.summary])
    return "\n".join(lines)


def format_background_jobs(records: list[dict[str, Any]]) -> str:
    if not records:
        return "SUBAGENT BACKGROUND JOBS\nNo background jobs yet. Use /subagents bg <task>."
    lines = ["SUBAGENT BACKGROUND JOBS", "status      job         pid        root        task"]
    for record in records[:20]:
        pid = str(record.get("pid") or "-")
        root = str(record.get("root_id") or "-")
        task = str(record.get("task") or "")
        if len(task) > 42:
            task = task[:39] + "..."
        lines.append(f"{record.get('status', ''):<11} {record.get('id', ''):<11} {pid:<10} {root:<11} {task}")
    return "\n".join(lines)


def format_events(events: list[SubagentEvent]) -> str:
    if not events:
        return "SUBAGENT TIMELINE\nNo events found for that subagent root."
    lines = ["SUBAGENT TIMELINE", "time                  event              role         message"]
    for event in events[-40:]:
        role = event.role or "-"
        lines.append(format_event_line(event))
    return "\n".join(lines)


def format_event_line(event: SubagentEvent) -> str:
    role = event.role or "-"
    return f"{event.created_at:<21} {event.event:<18} {role:<12} {event.message}"


def _source_path() -> Path | None:
    package_root = Path(__file__).resolve().parents[2]
    if package_root.name == "src":
        return package_root
    return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _role_prompt(role: str, task: str) -> str:
    contract = _profile_contract(role)
    return (
        f"You are the {role} subagent.\n"
        f"Purpose: {contract['purpose']}\n"
        f"Context contract: {contract['context_contract']}\n"
        f"Deliverable: {contract['deliverable']}\n"
        f"Tool budget: {contract['tool_budget']}\n"
        f"Work locally and produce a concise contribution for: {task}"
    )


def _role_summary(role: str, task: str) -> str:
    contract = _profile_contract(role)
    if role == "planner":
        return f"{contract['deliverable']} Keep browser surfaces optional. Task: {task}"
    if role == "researcher":
        return f"{contract['deliverable']} Prefer typed tools and audited receipts. Task: {task}"
    if role == "implementer":
        return f"{contract['deliverable']} Preserve policy gates. Task: {task}"
    if role == "reviewer":
        return f"{contract['deliverable']} Check claims against current evidence. Task: {task}"
    return f"Completed local bounded work for: {task}"
