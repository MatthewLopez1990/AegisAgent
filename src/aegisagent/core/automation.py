from __future__ import annotations

import json
import os
import plistlib
import re
import shlex
import stat
import subprocess
import sys
import time as time_module
import calendar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.core.command_names import terminal_command_name
from aegisagent.models import utc_now
from aegisagent.security.audit import AuditLog
from aegisagent.security.redaction import redact_text


@dataclass
class AutomationJob:
    id: str
    name: str
    schedule: str
    prompt: str
    status: str = "ACTIVE"
    source: str = "terminal"
    last_triggered_at: str = ""
    last_task_id: str = ""
    trigger_count: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule,
            "prompt": self.prompt,
            "status": self.status,
            "source": self.source,
            "last_triggered_at": self.last_triggered_at,
            "last_task_id": self.last_task_id,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutomationJob":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            schedule=str(data["schedule"]),
            prompt=str(data["prompt"]),
            status=str(data.get("status") or "ACTIVE"),
            source=str(data.get("source") or "terminal"),
            last_triggered_at=str(data.get("last_triggered_at") or ""),
            last_task_id=str(data.get("last_task_id") or ""),
            trigger_count=int(data.get("trigger_count") or 0),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


@dataclass(frozen=True, slots=True)
class AutomationWorkerLog:
    run_id: str
    event: str
    source: str
    tick_index: int = 0
    now: str = ""
    checked_count: int = 0
    due_count: int = 0
    triggered_count: int = 0
    task_ids: tuple[str, ...] = ()
    receipt_id: str = ""
    message: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "event": self.event,
            "source": self.source,
            "tick_index": self.tick_index,
            "now": self.now,
            "checked_count": self.checked_count,
            "due_count": self.due_count,
            "triggered_count": self.triggered_count,
            "task_ids": list(self.task_ids),
            "receipt_id": self.receipt_id,
            "message": self.message,
            "created_at": self.created_at,
            "terminal_first": True,
            "external_action_started": False,
            "browser_auto_launch": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutomationWorkerLog":
        return cls(
            run_id=str(data["run_id"]),
            event=str(data["event"]),
            source=str(data.get("source") or "terminal"),
            tick_index=int(data.get("tick_index") or 0),
            now=str(data.get("now") or ""),
            checked_count=int(data.get("checked_count") or 0),
            due_count=int(data.get("due_count") or 0),
            triggered_count=int(data.get("triggered_count") or 0),
            task_ids=tuple(str(item) for item in data.get("task_ids", [])),
            receipt_id=str(data.get("receipt_id") or ""),
            message=str(data.get("message") or ""),
            created_at=str(data.get("created_at") or utc_now()),
        )


class AutomationRegistry:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self.audit = AuditLog(paths)

    def create(self, name: str, schedule: str, prompt: str, *, source: str = "terminal") -> tuple[AutomationJob, str]:
        if not name.strip():
            raise ValueError("automation name is required")
        if not schedule.strip():
            raise ValueError("automation schedule is required")
        if not prompt.strip():
            raise ValueError("automation prompt is required")
        redacted = redact_text(prompt)
        job = AutomationJob(
            id=uuid4().hex[:10],
            name=name.strip(),
            schedule=schedule.strip(),
            prompt=redacted.text,
            source=source,
        )
        self.save(job)
        receipt = self.audit.append(
            "automation.created",
            {
                "id": job.id,
                "name": job.name,
                "schedule": job.schedule,
                "status": job.status,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "raw_secret_values_included": False,
            },
        )
        return job, receipt["id"]

    def save(self, job: AutomationJob) -> None:
        job.updated_at = utc_now()
        self.paths.automations_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.automations_dir / f"{job.id}.json").write_text(json.dumps(job.to_dict(), indent=2) + "\n", encoding="utf-8")

    def get(self, job_id: str) -> AutomationJob:
        path = self.paths.automations_dir / f"{job_id}.json"
        if not path.exists():
            raise KeyError(f"automation not found: {job_id}")
        return AutomationJob.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.automations_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append(self.get(path.stem).to_dict())
            if len(rows) >= limit:
                break
        return rows

    def set_status(self, job_id: str, status: str, *, source: str = "terminal") -> tuple[AutomationJob, str]:
        if status not in {"ACTIVE", "PAUSED"}:
            raise ValueError("status must be ACTIVE or PAUSED")
        job = self.get(job_id)
        job.status = status
        self.save(job)
        receipt = self.audit.append(
            "automation.status_changed",
            {
                "id": job.id,
                "name": job.name,
                "status": job.status,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
            },
        )
        return job, receipt["id"]

    def delete(self, job_id: str, *, source: str = "terminal") -> dict[str, Any]:
        job = self.get(job_id)
        (self.paths.automations_dir / f"{job.id}.json").unlink()
        receipt = self.audit.append(
            "automation.deleted",
            {
                "id": job.id,
                "name": job.name,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
            },
        )
        return {"deleted": job.to_dict(), "receipt": receipt["id"]}

    def trigger(self, job_id: str, *, start_background: bool = False, source: str = "terminal", manual_trigger: bool = True, triggered_at: str | None = None) -> dict[str, Any]:
        job = self.get(job_id)
        if job.status != "ACTIVE":
            receipt = self.audit.append(
                "automation.trigger_blocked",
                {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "source": source,
                    "reason": "automation is not ACTIVE",
                    "terminal_first": True,
                    "external_action_started": False,
                    "schedule_worker_started": False,
                    "manual_trigger": manual_trigger,
                },
            )
            return {"automation": job.to_dict(), "status": "blocked", "reason": "automation is not ACTIVE", "receipt": receipt["id"]}

        from aegisagent.core.tasks import TaskRunner

        runner = TaskRunner(self.paths)
        task = runner.submit(job.prompt, source=f"automation:{job.id}")
        if start_background:
            task = runner.start_background(task.id)
        job.last_triggered_at = triggered_at or utc_now()
        job.last_task_id = task.id
        job.trigger_count += 1
        self.save(job)
        receipt = self.audit.append(
            "automation.triggered",
            {
                "id": job.id,
                "name": job.name,
                "task_id": task.id,
                "task_status": task.status,
                "source": source,
                "terminal_first": True,
                "manual_trigger": manual_trigger,
                "triggered_at": job.last_triggered_at,
                "background_started": bool(start_background),
                "external_action_started": False,
                "schedule_worker_started": False,
                "raw_secret_values_included": False,
            },
        )
        return {"automation": job.to_dict(), "task": task.to_dict(), "status": "triggered", "receipt": receipt["id"]}

    def due(self, *, now: str | None = None, limit: int = 50, source: str = "terminal") -> dict[str, Any]:
        now_dt = _parse_datetime(now or utc_now())
        checked: list[dict[str, Any]] = []
        for job in self.list(limit=1000):
            due, reason = _is_due(AutomationJob.from_dict(job), now_dt)
            checked.append({"automation": job, "due": due, "reason": reason})
            if len(checked) >= limit:
                break
        due_count = sum(1 for row in checked if row["due"])
        receipt = self.audit.append(
            "automation.due_checked",
            {
                "now": _format_datetime(now_dt),
                "checked_count": len(checked),
                "due_count": due_count,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
            },
        )
        return {
            "now": _format_datetime(now_dt),
            "checked": checked,
            "due_count": due_count,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def run_due(self, *, now: str | None = None, start_background: bool = False, limit: int = 50, source: str = "terminal") -> dict[str, Any]:
        due_payload = self.due(now=now, limit=limit, source=source)
        triggered: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in due_payload["checked"]:
            if not row["due"]:
                skipped.append(row)
                continue
            result = self.trigger(
                row["automation"]["id"],
                start_background=start_background,
                source=source,
                manual_trigger=False,
                triggered_at=due_payload["now"],
            )
            triggered.append(result)
        receipt = self.audit.append(
            "automation.due_run",
            {
                "now": due_payload["now"],
                "checked_count": len(due_payload["checked"]),
                "triggered_count": len(triggered),
                "skipped_count": len(skipped),
                "background_started": bool(start_background),
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
            },
        )
        return {
            "now": due_payload["now"],
            "checked": due_payload["checked"],
            "triggered": triggered,
            "skipped": skipped,
            "triggered_count": len(triggered),
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def worker(
        self,
        *,
        interval_seconds: float = 60,
        max_ticks: int = 1,
        now: str | None = None,
        start_background: bool = False,
        limit: int = 50,
        source: str = "terminal",
    ) -> dict[str, Any]:
        interval_seconds = max(0.0, float(interval_seconds))
        max_ticks = max(0, int(max_ticks))
        run_id = uuid4().hex[:10]
        started_receipt = self.audit.append(
            "automation.worker_started",
            {
                "run_id": run_id,
                "interval_seconds": interval_seconds,
                "max_ticks": max_ticks,
                "now": now or "",
                "background_started": bool(start_background),
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": True,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        self.append_worker_log(
            AutomationWorkerLog(
                run_id=run_id,
                event="started",
                source=source,
                receipt_id=started_receipt["id"],
                message=f"foreground worker started interval={interval_seconds}s max_ticks={max_ticks}",
            )
        )
        ticks: list[dict[str, Any]] = []
        started_at = time_module.monotonic()
        base_now = _parse_datetime(now) if now else None
        tick_count = 0
        while max_ticks == 0 or tick_count < max_ticks:
            tick_now = _format_datetime(base_now + timedelta(seconds=interval_seconds * tick_count)) if base_now else None
            payload = self.run_due(now=tick_now, start_background=start_background, limit=limit, source=source)
            ticks.append(payload)
            self.append_worker_log(
                AutomationWorkerLog(
                    run_id=run_id,
                    event="tick",
                    source=source,
                    tick_index=tick_count + 1,
                    now=payload["now"],
                    checked_count=len(payload["checked"]),
                    due_count=sum(1 for row in payload["checked"] if row["due"]),
                    triggered_count=payload["triggered_count"],
                    task_ids=tuple(result["task"]["id"] for result in payload["triggered"]),
                    receipt_id=payload["receipt"],
                    message="scheduler tick completed",
                )
            )
            tick_count += 1
            if max_ticks != 0 and tick_count >= max_ticks:
                break
            if interval_seconds:
                time_module.sleep(interval_seconds)
        stopped_receipt = self.audit.append(
            "automation.worker_stopped",
            {
                "tick_count": len(ticks),
                "run_id": run_id,
                "triggered_count": sum(int(tick["triggered_count"]) for tick in ticks),
                "duration_ms": int((time_module.monotonic() - started_at) * 1000),
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        self.append_worker_log(
            AutomationWorkerLog(
                run_id=run_id,
                event="stopped",
                source=source,
                tick_index=len(ticks),
                triggered_count=sum(int(tick["triggered_count"]) for tick in ticks),
                task_ids=tuple(result["task"]["id"] for tick in ticks for result in tick["triggered"]),
                receipt_id=stopped_receipt["id"],
                message="foreground worker stopped",
            )
        )
        return {
            "status": "worker_stopped",
            "run_id": run_id,
            "tick_count": len(ticks),
            "triggered_count": sum(int(tick["triggered_count"]) for tick in ticks),
            "ticks": ticks,
            "interval_seconds": interval_seconds,
            "max_ticks": max_ticks,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": True,
            "browser_auto_launch": False,
            "started_receipt": started_receipt["id"],
            "receipt": stopped_receipt["id"],
        }

    def append_worker_log(self, event: AutomationWorkerLog) -> None:
        self.paths.automations_dir.mkdir(parents=True, exist_ok=True)
        with _worker_log_path(self.paths).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def worker_logs(self, *, limit: int = 50, run_id: str = "", source: str = "terminal") -> dict[str, Any]:
        path = _worker_log_path(self.paths)
        events: list[dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = AutomationWorkerLog.from_dict(json.loads(line)).to_dict()
                if run_id and event["run_id"] != run_id:
                    continue
                events.append(event)
        events = events[-max(1, int(limit)) :]
        receipt = self.audit.append(
            "automation.worker_logs_viewed",
            {
                "run_id": run_id,
                "event_count": len(events),
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "events": events,
            "event_count": len(events),
            "run_id": run_id,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def missed(self, *, now: str | None = None, limit: int = 50, source: str = "terminal") -> dict[str, Any]:
        now_dt = _parse_datetime(now or utc_now())
        remaining = max(1, int(limit))
        checked: list[dict[str, Any]] = []
        for job_payload in self.list(limit=1000):
            job = AutomationJob.from_dict(job_payload)
            runs, reason = _missed_runs(job, now_dt, remaining)
            checked.append({"automation": job_payload, "missed": runs, "missed_count": len(runs), "reason": reason})
            remaining -= len(runs)
            if remaining <= 0:
                break
        missed_count = sum(row["missed_count"] for row in checked)
        receipt = self.audit.append(
            "automation.missed_checked",
            {
                "now": _format_datetime(now_dt),
                "checked_count": len(checked),
                "missed_count": missed_count,
                "limit": max(1, int(limit)),
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "now": _format_datetime(now_dt),
            "checked": checked,
            "missed_count": missed_count,
            "limit": max(1, int(limit)),
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def replay_missed(self, *, now: str | None = None, start_background: bool = False, limit: int = 10, source: str = "terminal") -> dict[str, Any]:
        missed_payload = self.missed(now=now, limit=limit, source=source)
        triggered: list[dict[str, Any]] = []
        for row in missed_payload["checked"]:
            for missed_at in row["missed"]:
                result = self.trigger(
                    row["automation"]["id"],
                    start_background=start_background,
                    source=source,
                    manual_trigger=False,
                    triggered_at=missed_at,
                )
                triggered.append(result)
        receipt = self.audit.append(
            "automation.missed_replayed",
            {
                "now": missed_payload["now"],
                "checked_count": len(missed_payload["checked"]),
                "missed_count": missed_payload["missed_count"],
                "replayed_count": len(triggered),
                "background_started": bool(start_background),
                "limit": missed_payload["limit"],
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "now": missed_payload["now"],
            "checked": missed_payload["checked"],
            "triggered": triggered,
            "missed_count": missed_payload["missed_count"],
            "replayed_count": len(triggered),
            "limit": missed_payload["limit"],
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def service_wrapper(self, *, interval_seconds: float = 60, source: str = "terminal") -> dict[str, Any]:
        interval_seconds = max(1.0, float(interval_seconds))
        self.paths.automations_dir.mkdir(parents=True, exist_ok=True)
        label = _service_label(self.paths)
        service_paths = _service_paths(self.paths)
        script_path = service_paths["script_path"]
        stdout_path = service_paths["stdout_path"]
        stderr_path = service_paths["stderr_path"]
        plist_path = service_paths["plist_path"]
        pythonpath = str(self.paths.workspace / "src")
        script = "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                f"cd {shlex.quote(str(self.paths.workspace))}",
                f"export PYTHONPATH={shlex.quote(pythonpath)}${{PYTHONPATH:+:$PYTHONPATH}}",
                (
                    f"exec {shlex.quote(sys.executable)} -m aegisagent "
                    f"--workspace {shlex.quote(str(self.paths.workspace))} "
                    f"automations worker --interval {interval_seconds:g} --max-ticks 0"
                ),
                "",
            ]
        )
        script_path.write_text(script, encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
        plist = {
            "Label": label,
            "ProgramArguments": [str(script_path)],
            "RunAtLoad": False,
            "KeepAlive": False,
            "WorkingDirectory": str(self.paths.workspace),
            "StandardOutPath": str(stdout_path),
            "StandardErrorPath": str(stderr_path),
        }
        with plist_path.open("wb") as handle:
            plistlib.dump(plist, handle, sort_keys=True)
        receipt = self.audit.append(
            "automation.service_wrapper_generated",
            {
                "label": label,
                "plist_path": str(plist_path),
                "script_path": str(script_path),
                "interval_seconds": interval_seconds,
                "loaded": False,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "label": label,
            "plist_path": str(plist_path),
            "script_path": str(script_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "interval_seconds": interval_seconds,
            "loaded": False,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
            "commands": {
                "load": f"launchctl bootstrap gui/$(id -u) {shlex.quote(str(plist_path))}",
                "start": f"launchctl kickstart gui/$(id -u)/{label}",
                "stop": f"launchctl bootout gui/$(id -u) {shlex.quote(str(plist_path))}",
                "logs": f"tail -f {shlex.quote(str(stdout_path))} {shlex.quote(str(stderr_path))}",
            },
        }

    def service_status(self, *, source: str = "terminal") -> dict[str, Any]:
        label = _service_label(self.paths)
        service_paths = _service_paths(self.paths)
        plist_path = service_paths["plist_path"]
        script_path = service_paths["script_path"]
        stdout_path = service_paths["stdout_path"]
        stderr_path = service_paths["stderr_path"]
        launchctl_target = f"gui/{os.getuid()}/{label}"
        launchctl_available = False
        launchctl_returncode: int | None = None
        launchctl_status = "unknown"
        launchctl_detail = "launchctl is not available"
        try:
            result = subprocess.run(
                ["launchctl", "print", launchctl_target],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            launchctl_available = True
            launchctl_returncode = result.returncode
            output = (result.stdout or result.stderr or "").strip()
            launchctl_status = "loaded" if result.returncode == 0 else "not_loaded"
            launchctl_detail = _single_line(output, default="launchctl returned no detail")
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            launchctl_detail = _single_line(str(exc), default="launchctl check failed")
        loaded = launchctl_status == "loaded"
        stdout_tail = _tail_lines(stdout_path)
        stderr_tail = _tail_lines(stderr_path)
        health = _service_health_summary(
            self.paths,
            plist_exists=plist_path.exists(),
            script_exists=script_path.exists(),
            loaded=loaded,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            now=_parse_datetime(utc_now()),
        )
        receipt = self.audit.append(
            "automation.service_status_checked",
            {
                "label": label,
                "plist_exists": plist_path.exists(),
                "script_exists": script_path.exists(),
                "loaded": loaded,
                "health_status": health["health_status"],
                "worker_event_count": health["worker_event_count"],
                "last_worker_event": health["last_worker_event"],
                "stdout_tail_count": health["stdout_tail_count"],
                "stderr_tail_count": health["stderr_tail_count"],
                "launchctl_available": launchctl_available,
                "launchctl_returncode": launchctl_returncode,
                "source": source,
                "terminal_first": True,
                "external_action_started": False,
                "schedule_worker_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "label": label,
            "plist_path": str(plist_path),
            "script_path": str(script_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "plist_exists": plist_path.exists(),
            "script_exists": script_path.exists(),
            "stdout_exists": stdout_path.exists(),
            "stderr_exists": stderr_path.exists(),
            "loaded": loaded,
            "launchctl_available": launchctl_available,
            "launchctl_target": launchctl_target,
            "launchctl_status": launchctl_status,
            "launchctl_returncode": launchctl_returncode,
            "launchctl_detail": launchctl_detail,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            **health,
            "terminal_first": True,
            "external_action_started": False,
            "schedule_worker_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }


def automation_summary(paths: RuntimePaths) -> dict[str, Any]:
    command = terminal_command_name()
    registry = AutomationRegistry(paths)
    jobs = registry.list(limit=1000)
    return {
        "automations": jobs,
        "count": len(jobs),
        "active": sum(1 for job in jobs if job["status"] == "ACTIVE"),
        "paused": sum(1 for job in jobs if job["status"] == "PAUSED"),
        "triggered": sum(1 for job in jobs if job["trigger_count"] > 0),
        "terminal_first": True,
        "external_action_started": False,
        "schedule_worker_started": False,
        "browser_auto_launch": False,
        "next": f"Use `{command} automations due` to check schedules, `automations missed` for missed windows, `automations service` for a launchd wrapper, or `automations worker` for an explicit foreground scheduler.",
    }


def format_automation(job: AutomationJob | dict[str, Any], *, receipt: str = "") -> str:
    payload = job.to_dict() if isinstance(job, AutomationJob) else job
    lines = [
        "AEGIS AUTOMATION",
        f"job        {payload['id']}  {payload['status']}",
        f"name       {payload['name']}",
        f"schedule   {payload['schedule']}",
        f"prompt     {payload['prompt']}",
        f"triggers   count={payload.get('trigger_count', 0)} last_task={payload.get('last_task_id') or '-'}",
        "safety     terminal_first=true external_action_started=false schedule_worker_started=false",
    ]
    if receipt:
        lines.append(f"receipt    {receipt}")
    return "\n".join(lines)


def format_automations(payload: dict[str, Any]) -> str:
    command = terminal_command_name()
    lines = [
        "AEGIS AUTOMATIONS",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      total={payload['count']} active={payload['active']} paused={payload['paused']} triggered={payload['triggered']}",
        "",
    ]
    if not payload["automations"]:
        lines.extend(
            [
                "No automation records yet.",
                f"create: {command} automations create daily-check --schedule \"daily 09:00\" --prompt \"summarize workspace risks\"",
                "tui:    /automations create daily-check | daily 09:00 | summarize workspace risks",
            ]
        )
    else:
        for job in payload["automations"]:
            lines.extend(
                [
                    f"[{job['status']}] {job['id']}  {job['name']}",
                    f"  schedule: {job['schedule']}",
                    f"  prompt: {job['prompt']}",
                    f"  triggers: {job['trigger_count']} last_task={job['last_task_id'] or '-'}",
                    "",
                ]
            )
        lines.extend(
            [
                "commands",
                f"- due: {command} automations due",
                f"- missed: {command} automations missed",
                f"- replay: {command} automations replay-missed",
                f"- tick: {command} automations tick",
                f"- worker: {command} automations worker --max-ticks 5",
                f"- logs: {command} automations logs <run-id>",
                f"- service: {command} automations service",
                f"- service status: {command} automations service-status",
                f"- trigger: {command} automations trigger <id>",
                f"- background: {command} automations trigger <id> --background",
                f"- pause: {command} automations pause <id>",
                f"- resume: {command} automations resume <id>",
                f"- delete: {command} automations delete <id>",
            ]
        )
    lines.extend(["", f"next       {payload['next']}"])
    return "\n".join(lines).rstrip()


def format_due_automations(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION DUE CHECK",
        f"now         {payload['now']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      checked={len(payload['checked'])} due={payload['due_count']}",
        "",
    ]
    if not payload["checked"]:
        lines.append("No automation records to check.")
    else:
        for row in payload["checked"]:
            job = row["automation"]
            status = "due" if row["due"] else "skip"
            lines.append(f"[{status}] {job['id']}  {job['name']}  {job['schedule']}")
            lines.append(f"  reason: {row['reason']}")
            lines.append(f"  last: {job['last_triggered_at'] or '-'}")
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_due_run(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION TICK",
        f"now         {payload['now']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      checked={len(payload['checked'])} triggered={payload['triggered_count']}",
        "",
    ]
    if not payload["triggered"]:
        lines.append("No due automation tasks were queued.")
    else:
        for result in payload["triggered"]:
            job = result["automation"]
            task = result["task"]
            lines.append(f"task       {task['id']}  {task['status']}  automation={job['id']}  {job['name']}")
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_worker_run(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION WORKER",
        f"run        {payload['run_id']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"loop        interval={payload['interval_seconds']}s max_ticks={payload['max_ticks']}",
        f"counts      ticks={payload['tick_count']} triggered={payload['triggered_count']}",
        "",
    ]
    for index, tick in enumerate(payload["ticks"], start=1):
        lines.append(f"tick       {index} now={tick['now']} checked={len(tick['checked'])} triggered={tick['triggered_count']}")
        for result in tick["triggered"]:
            job = result["automation"]
            task = result["task"]
            lines.append(f"task       {task['id']}  {task['status']}  automation={job['id']}  {job['name']}")
    lines.extend(["", f"started    {payload['started_receipt']}", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_worker_logs(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION WORKER LOGS",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      events={payload['event_count']}",
    ]
    if payload.get("run_id"):
        lines.append(f"run        {payload['run_id']}")
    lines.append("")
    if not payload["events"]:
        lines.append("No worker log events recorded.")
    else:
        for event in payload["events"]:
            tasks = ",".join(event["task_ids"]) if event["task_ids"] else "-"
            lines.append(
                f"{event['created_at']}  {event['event']}  run={event['run_id']} tick={event['tick_index']} "
                f"checked={event['checked_count']} due={event['due_count']} triggered={event['triggered_count']} tasks={tasks}"
            )
            if event.get("message"):
                lines.append(f"  {event['message']}")
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_missed_automations(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION MISSED RUNS",
        f"now         {payload['now']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      checked={len(payload['checked'])} missed={payload['missed_count']} limit={payload['limit']}",
        "",
    ]
    if not payload["checked"]:
        lines.append("No automation records to check.")
    else:
        for row in payload["checked"]:
            job = row["automation"]
            status = "missed" if row["missed"] else "clear"
            lines.append(f"[{status}] {job['id']}  {job['name']}  {job['schedule']}")
            lines.append(f"  reason: {row['reason']}")
            for missed_at in row["missed"]:
                lines.append(f"  missed: {missed_at}")
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_missed_replay(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION MISSED REPLAY",
        f"now         {payload['now']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      missed={payload['missed_count']} replayed={payload['replayed_count']} limit={payload['limit']}",
        "",
    ]
    if not payload["triggered"]:
        lines.append("No missed automation tasks were queued.")
    else:
        for result in payload["triggered"]:
            job = result["automation"]
            task = result["task"]
            lines.append(f"task       {task['id']}  {task['status']}  automation={job['id']}  {job['name']}  replay_at={job['last_triggered_at']}")
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def format_service_wrapper(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION SERVICE WRAPPER",
        f"label       {payload['label']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()} "
            f"loaded={str(payload['loaded']).lower()}"
        ),
        f"loop        interval={payload['interval_seconds']}s max_ticks=0",
        f"plist       {payload['plist_path']}",
        f"script      {payload['script_path']}",
        f"stdout      {payload['stdout_path']}",
        f"stderr      {payload['stderr_path']}",
        "",
        "operator commands",
        f"load        {payload['commands']['load']}",
        f"start       {payload['commands']['start']}",
        f"stop        {payload['commands']['stop']}",
        f"logs        {payload['commands']['logs']}",
        "",
        f"receipt    {payload['receipt']}",
    ]
    return "\n".join(lines)


def format_service_status(payload: dict[str, Any]) -> str:
    lines = [
        "AEGIS AUTOMATION SERVICE STATUS",
        f"label       {payload['label']}",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"schedule_worker_started={str(payload['schedule_worker_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()} "
            f"loaded={str(payload['loaded']).lower()}"
        ),
        f"launchctl   status={payload['launchctl_status']} available={str(payload['launchctl_available']).lower()} returncode={payload['launchctl_returncode']}",
        f"target      {payload['launchctl_target']}",
        f"detail      {payload['launchctl_detail']}",
        f"plist       exists={str(payload['plist_exists']).lower()} {payload['plist_path']}",
        f"script      exists={str(payload['script_exists']).lower()} {payload['script_path']}",
        f"stdout      exists={str(payload['stdout_exists']).lower()} {payload['stdout_path']}",
        f"stderr      exists={str(payload['stderr_exists']).lower()} {payload['stderr_path']}",
        (
            "health     "
            f"status={payload['health_status']} "
            f"worker_events={payload['worker_event_count']} "
            f"last_event={payload['last_worker_event'] or '-'} "
            f"age_seconds={payload['last_worker_event_age_seconds'] if payload['last_worker_event_age_seconds'] is not None else '-'} "
            f"stdout_tail={payload['stdout_tail_count']} "
            f"stderr_tail={payload['stderr_tail_count']}"
        ),
        f"advice      {payload['health_advice']}",
    ]
    if payload["stdout_tail"]:
        lines.extend(["", "stdout tail"])
        lines.extend(f"  {line}" for line in payload["stdout_tail"])
    if payload["stderr_tail"]:
        lines.extend(["", "stderr tail"])
        lines.extend(f"  {line}" for line in payload["stderr_tail"])
    lines.extend(["", f"receipt    {payload['receipt']}"])
    return "\n".join(lines)


def _worker_log_path(paths: RuntimePaths):
    return paths.automations_dir / "worker.jsonl"


def _service_paths(paths: RuntimePaths):
    label = _service_label(paths)
    return {
        "plist_path": paths.automations_dir / f"{label}.plist",
        "script_path": paths.automations_dir / "automation-worker.sh",
        "stdout_path": paths.automations_dir / "service.stdout.log",
        "stderr_path": paths.automations_dir / "service.stderr.log",
    }


def _service_label(paths: RuntimePaths) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", paths.workspace.name.lower()).strip("-") or "workspace"
    return f"com.aegisagent.automation.{slug}"


def _tail_lines(path, *, limit: int = 8) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


def _service_health_summary(
    paths: RuntimePaths,
    *,
    plist_exists: bool,
    script_exists: bool,
    loaded: bool,
    stdout_tail: list[str],
    stderr_tail: list[str],
    now: datetime,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    log_path = _worker_log_path(paths)
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                events.append(AutomationWorkerLog.from_dict(json.loads(line)).to_dict())
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
    last_event = events[-1] if events else {}
    last_created = _parse_optional_datetime(str(last_event.get("created_at") or ""))
    age_seconds = int((now - last_created).total_seconds()) if last_created else None
    stderr_count = len(stderr_tail)
    stdout_count = len(stdout_tail)
    if not plist_exists or not script_exists:
        health_status = "wrapper_missing"
        advice = "generate the service wrapper before checking load state"
    elif stderr_count:
        health_status = "stderr_output_present"
        advice = "inspect stderr tail before loading or restarting the worker"
    elif loaded and events:
        health_status = "loaded_worker_observed"
        advice = "worker service is loaded and worker events have been observed"
    elif loaded:
        health_status = "loaded_no_worker_events"
        advice = "service is loaded but no worker log events are recorded yet"
    elif events:
        health_status = "wrapper_ready_worker_observed"
        advice = "wrapper is ready and prior foreground worker events are available"
    else:
        health_status = "wrapper_ready_not_loaded"
        advice = "load and start the wrapper manually when ready"
    return {
        "health_status": health_status,
        "health_advice": advice,
        "worker_log_path": str(log_path),
        "worker_log_exists": log_path.exists(),
        "worker_event_count": len(events),
        "last_worker_event": str(last_event.get("event") or ""),
        "last_worker_run_id": str(last_event.get("run_id") or ""),
        "last_worker_event_at": str(last_event.get("created_at") or ""),
        "last_worker_event_age_seconds": age_seconds,
        "stdout_tail_count": stdout_count,
        "stderr_tail_count": stderr_count,
    }


def _single_line(value: str, *, default: str) -> str:
    for line in value.splitlines():
        if line.strip():
            return line.strip()[:240]
    return default


def _schedule_parts(schedule: str):
    parts = schedule.strip().split()
    timezone_name = "UTC"
    exception_dates: set[date] = set()
    base_parts: list[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered.startswith(("except=", "skip=", "exceptions=")):
            raw_dates = part.split("=", 1)[1]
            for raw_date in raw_dates.split(","):
                if not raw_date.strip():
                    continue
                try:
                    exception_dates.add(date.fromisoformat(raw_date.strip()))
                except ValueError:
                    return "", timezone_name, UTC, exception_dates, f"invalid exception date: {raw_date.strip()}"
            continue
        if lowered.startswith("tz="):
            timezone_name = part.split("=", 1)[1]
            continue
        if lowered.startswith("timezone="):
            timezone_name = part.split("=", 1)[1]
            continue
        if "/" in part or part.upper() == "UTC":
            timezone_name = part
            continue
        base_parts.append(part)
    base_schedule = " ".join(base_parts).strip().lower()
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return base_schedule, timezone_name, UTC, exception_dates, f"unsupported timezone: {timezone_name}"
    return base_schedule, timezone_name, tzinfo, exception_dates, ""


def _timezone_suffix(timezone_name: str) -> str:
    return "" if timezone_name == "UTC" else f" ({timezone_name})"


def _missed_runs(job: AutomationJob, now: datetime, limit: int) -> tuple[list[str], str]:
    if limit <= 0:
        return [], "missed run limit reached"
    if job.status != "ACTIVE":
        return [], f"status is {job.status}"
    schedule, timezone_name, tzinfo, exception_dates, schedule_error = _schedule_parts(job.schedule)
    if schedule_error:
        return [], schedule_error
    last = _parse_optional_datetime(job.last_triggered_at)
    created = _parse_optional_datetime(job.created_at) or now
    now = now.astimezone(tzinfo)
    last = last.astimezone(tzinfo) if last else None
    created = created.astimezone(tzinfo)
    base = last or created
    suffix = _timezone_suffix(timezone_name)
    if schedule in {"manual", "manual only", "on demand", "on-demand"}:
        return [], "manual-only schedule"
    if schedule in {"now", "once", "startup"}:
        if last:
            return [], "one-shot schedule already ran"
        if created > now:
            return [], "one-shot schedule has not arrived"
        return [_format_datetime(created)], "one-shot schedule was not run"
    if now <= base:
        return [], "schedule has no elapsed window"
    if schedule == "hourly":
        return _missed_interval_runs(base, now, timedelta(hours=1), limit, f"hourly interval{suffix}", exception_dates=exception_dates)
    every = re.match(r"^every\s+(\d+)\s+(minute|minutes|hour|hours|day|days)$", schedule)
    if every:
        count = int(every.group(1))
        unit = every.group(2)
        if "minute" in unit:
            delta = timedelta(minutes=count)
        elif "hour" in unit:
            delta = timedelta(hours=count)
        else:
            delta = timedelta(days=count)
        return _missed_interval_runs(base, now, delta, limit, f"every {count} {unit}{suffix}", exception_dates=exception_dates)
    daily = re.match(r"^daily(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if daily:
        scheduled = _time_from_match(daily)
        return _missed_daily_runs(base, now, scheduled, limit, suffix=suffix, exception_dates=exception_dates)
    weekdays = re.match(r"^(weekdays|business days)(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekdays:
        scheduled = time(int(weekdays.group(2)), int(weekdays.group(3)))
        return _missed_day_set_runs(base, now, {0, 1, 2, 3, 4}, scheduled, limit, f"weekday{suffix}", exception_dates=exception_dates)
    weekends = re.match(r"^weekends(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekends:
        scheduled = time(int(weekends.group(1)), int(weekends.group(2)))
        return _missed_day_set_runs(base, now, {5, 6}, scheduled, limit, f"weekend{suffix}", exception_dates=exception_dates)
    weekly = re.match(r"^weekly\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekly:
        scheduled = time(int(weekly.group(2)), int(weekly.group(3)))
        return _missed_weekly_runs(base, now, _WEEKDAYS[weekly.group(1)], scheduled, limit, f"{weekly.group(1)}{suffix}", exception_dates=exception_dates)
    monthly = re.match(r"^monthly(?:\s+day)?\s+(\d{1,2})(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if monthly:
        day = int(monthly.group(1))
        scheduled = time(int(monthly.group(2)), int(monthly.group(3)))
        return _missed_monthly_runs(base, now, day, scheduled, limit, suffix=suffix, exception_dates=exception_dates)
    monthly_last = re.match(r"^monthly\s+last(?:\s+day)?(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if monthly_last:
        scheduled = time(int(monthly_last.group(1)), int(monthly_last.group(2)))
        return _missed_monthly_runs(base, now, -1, scheduled, limit, suffix=suffix, exception_dates=exception_dates)
    return [], "unsupported schedule label for missed-run replay"


def _missed_interval_runs(base: datetime, now: datetime, delta: timedelta, limit: int, label: str, *, exception_dates: set[date] | None = None) -> tuple[list[str], str]:
    if delta.total_seconds() <= 0:
        return [], f"{label} has invalid interval"
    exception_dates = exception_dates or set()
    runs: list[str] = []
    candidate = base + delta
    while candidate <= now and len(runs) < limit:
        if candidate.date() not in exception_dates:
            runs.append(_format_datetime(candidate))
        candidate += delta
    if runs:
        return runs, f"{label} missed {len(runs)} run(s)"
    return [], f"{label} has no missed runs"


def _missed_daily_runs(base: datetime, now: datetime, scheduled: time, limit: int, *, suffix: str = "", exception_dates: set[date] | None = None) -> tuple[list[str], str]:
    exception_dates = exception_dates or set()
    runs: list[str] = []
    candidate = datetime.combine(base.date(), scheduled, tzinfo=base.tzinfo)
    if candidate <= base:
        candidate += timedelta(days=1)
    while candidate <= now and len(runs) < limit:
        if candidate.date() not in exception_dates:
            runs.append(_format_datetime(candidate))
        candidate += timedelta(days=1)
    if runs:
        return runs, f"daily schedule{suffix} missed {len(runs)} run(s)"
    return [], f"daily schedule{suffix} has no missed runs"


def _missed_day_set_runs(base: datetime, now: datetime, weekdays: set[int], scheduled: time, limit: int, label: str, *, exception_dates: set[date] | None = None) -> tuple[list[str], str]:
    exception_dates = exception_dates or set()
    runs: list[str] = []
    candidate = datetime.combine(base.date(), scheduled, tzinfo=base.tzinfo)
    if candidate <= base:
        candidate += timedelta(days=1)
    while candidate <= now and len(runs) < limit:
        if candidate.weekday() in weekdays and candidate.date() not in exception_dates:
            runs.append(_format_datetime(candidate))
        candidate += timedelta(days=1)
    if runs:
        return runs, f"{label} schedule missed {len(runs)} run(s)"
    return [], f"{label} schedule has no missed runs"


def _missed_weekly_runs(base: datetime, now: datetime, weekday: int, scheduled: time, limit: int, label: str, *, exception_dates: set[date] | None = None) -> tuple[list[str], str]:
    exception_dates = exception_dates or set()
    runs: list[str] = []
    days_until = (weekday - base.weekday()) % 7
    candidate = datetime.combine(base.date() + timedelta(days=days_until), scheduled, tzinfo=base.tzinfo)
    if candidate <= base:
        candidate += timedelta(days=7)
    while candidate <= now and len(runs) < limit:
        if candidate.date() not in exception_dates:
            runs.append(_format_datetime(candidate))
        candidate += timedelta(days=7)
    if runs:
        return runs, f"weekly {label} schedule missed {len(runs)} run(s)"
    return [], f"weekly {label} schedule has no missed runs"


def _missed_monthly_runs(base: datetime, now: datetime, day: int, scheduled: time, limit: int, *, suffix: str = "", exception_dates: set[date] | None = None) -> tuple[list[str], str]:
    if day == 0 or day < -1 or day > 31:
        return [], "monthly day must be 1-31 or last"
    exception_dates = exception_dates or set()
    runs: list[str] = []
    year = base.year
    month = base.month
    while len(runs) < limit:
        candidate = _monthly_candidate(year, month, day, scheduled, base.tzinfo)
        if candidate and candidate > base and candidate <= now and candidate.date() not in exception_dates:
            runs.append(_format_datetime(candidate))
        year, month = _next_month(year, month)
        if datetime(year, month, 1, tzinfo=base.tzinfo) > now:
            break
    label = "monthly last-day schedule" if day == -1 else f"monthly day {day} schedule"
    label = f"{label}{suffix}"
    if runs:
        return runs, f"{label} missed {len(runs)} run(s)"
    return [], f"{label} has no missed runs"


def _is_due(job: AutomationJob, now: datetime) -> tuple[bool, str]:
    if job.status != "ACTIVE":
        return False, f"status is {job.status}"
    schedule, timezone_name, tzinfo, exception_dates, schedule_error = _schedule_parts(job.schedule)
    if schedule_error:
        return False, schedule_error
    last = _parse_optional_datetime(job.last_triggered_at)
    created = _parse_optional_datetime(job.created_at) or now
    now = now.astimezone(tzinfo)
    last = last.astimezone(tzinfo) if last else None
    created = created.astimezone(tzinfo)
    suffix = _timezone_suffix(timezone_name)
    if now.date() in exception_dates:
        return False, f"date {now.date().isoformat()}{suffix} is excluded by schedule exception"
    if schedule in {"manual", "manual only", "on demand", "on-demand"}:
        return False, "manual-only schedule"
    if schedule in {"now", "once", "startup"}:
        return (not last, "one-shot schedule has not run" if not last else "one-shot schedule already ran")
    if schedule == "hourly":
        return _interval_due(last or created, now, timedelta(hours=1), f"hourly interval{suffix}")
    every = re.match(r"^every\s+(\d+)\s+(minute|minutes|hour|hours|day|days)$", schedule)
    if every:
        count = int(every.group(1))
        unit = every.group(2)
        if "minute" in unit:
            delta = timedelta(minutes=count)
        elif "hour" in unit:
            delta = timedelta(hours=count)
        else:
            delta = timedelta(days=count)
        return _interval_due(last or created, now, delta, f"every {count} {unit}{suffix}")
    daily = re.match(r"^daily(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if daily:
        scheduled = _time_from_match(daily)
        if now.time() < scheduled:
            return False, f"daily time {scheduled.strftime('%H:%M')}{suffix} has not arrived"
        if last and last.date() == now.date():
            return False, f"daily schedule{suffix} already ran today"
        return True, f"daily schedule{suffix} is due"
    weekdays = re.match(r"^(weekdays|business days)(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekdays:
        scheduled = time(int(weekdays.group(2)), int(weekdays.group(3)))
        return _day_set_due(now, last, {0, 1, 2, 3, 4}, scheduled, f"weekday{suffix}")
    weekends = re.match(r"^weekends(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekends:
        scheduled = time(int(weekends.group(1)), int(weekends.group(2)))
        return _day_set_due(now, last, {5, 6}, scheduled, f"weekend{suffix}")
    weekly = re.match(r"^weekly\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if weekly:
        weekday = _WEEKDAYS[weekly.group(1)]
        scheduled = time(int(weekly.group(2)), int(weekly.group(3)))
        if now.weekday() != weekday:
            return False, f"weekly schedule waits for {weekly.group(1)}{suffix}"
        if now.time() < scheduled:
            return False, f"weekly time {scheduled.strftime('%H:%M')}{suffix} has not arrived"
        if last and last.date() == now.date():
            return False, f"weekly schedule{suffix} already ran today"
        return True, f"weekly schedule{suffix} is due"
    monthly = re.match(r"^monthly(?:\s+day)?\s+(\d{1,2})(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if monthly:
        day = int(monthly.group(1))
        scheduled = time(int(monthly.group(2)), int(monthly.group(3)))
        return _monthly_due(now, last, day, scheduled, suffix=suffix)
    monthly_last = re.match(r"^monthly\s+last(?:\s+day)?(?:\s+at)?\s+(\d{1,2}):(\d{2})$", schedule)
    if monthly_last:
        scheduled = time(int(monthly_last.group(1)), int(monthly_last.group(2)))
        return _monthly_due(now, last, -1, scheduled, suffix=suffix)
    return False, "unsupported schedule label for due evaluation"


def _day_set_due(now: datetime, last: datetime | None, weekdays: set[int], scheduled: time, label: str) -> tuple[bool, str]:
    if now.weekday() not in weekdays:
        return False, f"{label} schedule waits for matching day"
    if now.time() < scheduled:
        return False, f"{label} time {scheduled.strftime('%H:%M')} has not arrived"
    if last and last.date() == now.date():
        return False, f"{label} schedule already ran today"
    return True, f"{label} schedule is due"


def _monthly_due(now: datetime, last: datetime | None, day: int, scheduled: time, *, suffix: str = "") -> tuple[bool, str]:
    if day == 0 or day < -1 or day > 31:
        return False, "monthly day must be 1-31 or last"
    expected_day = _last_day_of_month(now.year, now.month) if day == -1 else day
    if now.day != expected_day:
        label = "last day" if day == -1 else f"day {day}"
        return False, f"monthly schedule waits for {label}{suffix}"
    if now.time() < scheduled:
        return False, f"monthly time {scheduled.strftime('%H:%M')}{suffix} has not arrived"
    if last and last.date() == now.date():
        return False, f"monthly schedule{suffix} already ran today"
    return True, f"monthly schedule{suffix} is due"


def _interval_due(base: datetime, now: datetime, delta: timedelta, label: str) -> tuple[bool, str]:
    if delta.total_seconds() <= 0:
        return True, f"{label} is due"
    if now - base >= delta:
        return True, f"{label} elapsed"
    return False, f"{label} has not elapsed"


def _time_from_match(match: re.Match[str]) -> time:
    return time(int(match.group(1)), int(match.group(2)))


def _monthly_candidate(year: int, month: int, day: int, scheduled: time, tzinfo) -> datetime | None:
    actual_day = _last_day_of_month(year, month) if day == -1 else day
    if actual_day > _last_day_of_month(year, month):
        return None
    return datetime.combine(datetime(year, month, actual_day, tzinfo=tzinfo).date(), scheduled, tzinfo=tzinfo)


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _parse_optional_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return _parse_datetime(value)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
