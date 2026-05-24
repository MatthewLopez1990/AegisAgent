from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegisagent.config import RuntimePaths, ensure_runtime
from aegisagent.core.command_names import terminal_command_name
from aegisagent.models import utc_now
from aegisagent.security.audit import AuditLog
from aegisagent.security.redaction import redact_text


@dataclass(frozen=True, slots=True)
class FailureClassification:
    failure_class: str
    severity: str
    confidence: float
    signals: tuple[str, ...]
    review_gate: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "severity": self.severity,
            "confidence": self.confidence,
            "signals": list(self.signals),
            "review_gate": self.review_gate,
            "retryable": self.retryable,
        }


@dataclass
class ImprovementProposal:
    id: str
    summary: str
    target_subsystem: str
    operation: str
    failure_class: str
    severity: str
    review_gate: str
    proposed_action: str
    required_validation: list[str]
    signals: list[str]
    confidence: float
    status: str = "proposed"
    source: str = "terminal"
    review_rationale: str = ""
    handoff_task_id: str = ""
    handoff_status: str = "not_requested"
    handoff_at: str = ""
    handoff_count: int = 0
    implementation_status: str = "not_started"
    changed_files: list[str] = field(default_factory=list)
    verification_command: str = ""
    verification_result: str = ""
    evidence_at: str = ""
    evidence_count: int = 0
    implemented_at: str = ""
    candidate_id: str = ""
    candidate_status: str = "not_generated"
    candidate_at: str = ""
    candidate_count: int = 0
    candidate_verification_status: str = ""
    candidate_verification_count: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "target_subsystem": self.target_subsystem,
            "operation": self.operation,
            "failure_class": self.failure_class,
            "severity": self.severity,
            "review_gate": self.review_gate,
            "proposed_action": self.proposed_action,
            "required_validation": self.required_validation,
            "signals": self.signals,
            "confidence": self.confidence,
            "status": self.status,
            "source": self.source,
            "review_rationale": self.review_rationale,
            "handoff_task_id": self.handoff_task_id,
            "handoff_status": self.handoff_status,
            "handoff_at": self.handoff_at,
            "handoff_count": self.handoff_count,
            "implementation_status": self.implementation_status,
            "changed_files": self.changed_files,
            "verification_command": self.verification_command,
            "verification_result": self.verification_result,
            "evidence_at": self.evidence_at,
            "evidence_count": self.evidence_count,
            "implemented_at": self.implemented_at,
            "candidate_id": self.candidate_id,
            "candidate_status": self.candidate_status,
            "candidate_at": self.candidate_at,
            "candidate_count": self.candidate_count,
            "candidate_verification_status": self.candidate_verification_status,
            "candidate_verification_count": self.candidate_verification_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "terminal_first": True,
            "workspace_mutation_allowed_before_approval": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImprovementProposal":
        return cls(
            id=str(data["id"]),
            summary=str(data["summary"]),
            target_subsystem=str(data.get("target_subsystem") or "runtime"),
            operation=str(data.get("operation") or "unknown"),
            failure_class=str(data.get("failure_class") or "runtime_failure"),
            severity=str(data.get("severity") or "low"),
            review_gate=str(data.get("review_gate") or "maintainer_review_required"),
            proposed_action=str(data.get("proposed_action") or ""),
            required_validation=[str(item) for item in data.get("required_validation", [])],
            signals=[str(item) for item in data.get("signals", [])],
            confidence=float(data.get("confidence") or 0.0),
            status=str(data.get("status") or "proposed"),
            source=str(data.get("source") or "terminal"),
            review_rationale=str(data.get("review_rationale") or ""),
            handoff_task_id=str(data.get("handoff_task_id") or ""),
            handoff_status=str(data.get("handoff_status") or "not_requested"),
            handoff_at=str(data.get("handoff_at") or ""),
            handoff_count=int(data.get("handoff_count") or 0),
            implementation_status=str(data.get("implementation_status") or "not_started"),
            changed_files=[str(item) for item in data.get("changed_files", [])],
            verification_command=str(data.get("verification_command") or ""),
            verification_result=str(data.get("verification_result") or ""),
            evidence_at=str(data.get("evidence_at") or ""),
            evidence_count=int(data.get("evidence_count") or 0),
            implemented_at=str(data.get("implemented_at") or ""),
            candidate_id=str(data.get("candidate_id") or ""),
            candidate_status=str(data.get("candidate_status") or "not_generated"),
            candidate_at=str(data.get("candidate_at") or ""),
            candidate_count=int(data.get("candidate_count") or 0),
            candidate_verification_status=str(data.get("candidate_verification_status") or ""),
            candidate_verification_count=int(data.get("candidate_verification_count") or 0),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


@dataclass
class ImprovementCandidate:
    id: str
    proposal_id: str
    status: str
    title: str
    target_subsystem: str
    operation: str
    failure_class: str
    suggested_files: list[str]
    patch_plan: list[str]
    verification_commands: list[str]
    risk_notes: list[str]
    source: str = "terminal"
    last_verification_status: str = ""
    last_verification_command: str = ""
    last_verification_at: str = ""
    last_verification_id: str = ""
    verification_count: int = 0
    apply_task_id: str = ""
    apply_status: str = "not_requested"
    apply_at: str = ""
    apply_count: int = 0
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "status": self.status,
            "title": self.title,
            "target_subsystem": self.target_subsystem,
            "operation": self.operation,
            "failure_class": self.failure_class,
            "suggested_files": self.suggested_files,
            "patch_plan": self.patch_plan,
            "verification_commands": self.verification_commands,
            "risk_notes": self.risk_notes,
            "source": self.source,
            "last_verification_status": self.last_verification_status,
            "last_verification_command": self.last_verification_command,
            "last_verification_at": self.last_verification_at,
            "last_verification_id": self.last_verification_id,
            "verification_count": self.verification_count,
            "apply_task_id": self.apply_task_id,
            "apply_status": self.apply_status,
            "apply_at": self.apply_at,
            "apply_count": self.apply_count,
            "created_at": self.created_at,
            "terminal_first": True,
            "advisory_only": True,
            "workspace_mutation_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImprovementCandidate":
        return cls(
            id=str(data["id"]),
            proposal_id=str(data["proposal_id"]),
            status=str(data.get("status") or "candidate"),
            title=str(data.get("title") or ""),
            target_subsystem=str(data.get("target_subsystem") or "runtime"),
            operation=str(data.get("operation") or "unknown"),
            failure_class=str(data.get("failure_class") or "runtime_failure"),
            suggested_files=[str(item) for item in data.get("suggested_files", [])],
            patch_plan=[str(item) for item in data.get("patch_plan", [])],
            verification_commands=[str(item) for item in data.get("verification_commands", [])],
            risk_notes=[str(item) for item in data.get("risk_notes", [])],
            source=str(data.get("source") or "terminal"),
            last_verification_status=str(data.get("last_verification_status") or ""),
            last_verification_command=str(data.get("last_verification_command") or ""),
            last_verification_at=str(data.get("last_verification_at") or ""),
            last_verification_id=str(data.get("last_verification_id") or ""),
            verification_count=int(data.get("verification_count") or 0),
            apply_task_id=str(data.get("apply_task_id") or ""),
            apply_status=str(data.get("apply_status") or "not_requested"),
            apply_at=str(data.get("apply_at") or ""),
            apply_count=int(data.get("apply_count") or 0),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass
class CandidateVerificationRun:
    id: str
    candidate_id: str
    proposal_id: str
    command: str
    command_index: int
    status: str
    returncode: int | None
    stdout_preview: str
    stderr_preview: str
    duration_ms: int
    timeout_seconds: int
    source: str = "terminal"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "proposal_id": self.proposal_id,
            "command": self.command,
            "command_index": self.command_index,
            "status": self.status,
            "returncode": self.returncode,
            "stdout_preview": self.stdout_preview,
            "stderr_preview": self.stderr_preview,
            "duration_ms": self.duration_ms,
            "timeout_seconds": self.timeout_seconds,
            "source": self.source,
            "created_at": self.created_at,
            "terminal_first": True,
            "candidate_command_allowlisted": True,
            "workspace_mutation_requested": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateVerificationRun":
        return cls(
            id=str(data["id"]),
            candidate_id=str(data["candidate_id"]),
            proposal_id=str(data["proposal_id"]),
            command=str(data["command"]),
            command_index=int(data.get("command_index") or 0),
            status=str(data.get("status") or "failed"),
            returncode=data.get("returncode") if data.get("returncode") is None else int(data.get("returncode")),
            stdout_preview=str(data.get("stdout_preview") or ""),
            stderr_preview=str(data.get("stderr_preview") or ""),
            duration_ms=int(data.get("duration_ms") or 0),
            timeout_seconds=int(data.get("timeout_seconds") or 0),
            source=str(data.get("source") or "terminal"),
            created_at=str(data.get("created_at") or utc_now()),
        )


class ImprovementStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self.audit = AuditLog(paths)

    def propose_from_failure(
        self,
        failure_summary: str,
        *,
        target_subsystem: str = "runtime",
        operation: str = "unknown",
        source: str = "terminal",
    ) -> tuple[ImprovementProposal, str]:
        redacted = redact_text(failure_summary)
        classification = classify_failure(redacted.text)
        proposal = ImprovementProposal(
            id=uuid4().hex[:10],
            summary=redacted.text.strip(),
            target_subsystem=target_subsystem.strip() or "runtime",
            operation=operation.strip() or "unknown",
            failure_class=classification.failure_class,
            severity=classification.severity,
            review_gate=classification.review_gate,
            proposed_action=_proposed_action(classification.failure_class, target_subsystem, operation),
            required_validation=_required_validation(classification),
            signals=list(classification.signals),
            confidence=classification.confidence,
            source=source,
        )
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.proposed",
            {
                "id": proposal.id,
                "failure_class": proposal.failure_class,
                "severity": proposal.severity,
                "review_gate": proposal.review_gate,
                "target_subsystem": proposal.target_subsystem,
                "operation": proposal.operation,
                "source": source,
                "terminal_first": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return proposal, receipt["id"]

    def handoff(self, proposal_id: str, *, start_background: bool = False, source: str = "terminal") -> dict[str, Any]:
        from aegisagent.core.tasks import TaskRunner

        proposal = self.get(proposal_id)
        if proposal.status != "approved":
            proposal.handoff_status = "blocked"
            self.save(proposal)
            receipt = self.audit.append(
                "improvement.handoff_blocked",
                {
                    "id": proposal.id,
                    "status": proposal.status,
                    "reason": "proposal is not approved",
                    "source": source,
                    "terminal_first": True,
                    "workspace_mutation_allowed_before_approval": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {
                "status": "blocked",
                "reason": "proposal is not approved",
                "proposal": proposal.to_dict(),
                "task": None,
                "receipt": receipt["id"],
            }

        runner = TaskRunner(self.paths)
        prompt = _handoff_prompt(proposal)
        task = runner.submit(prompt, source=f"improvement:{proposal.id}")
        if start_background:
            task = runner.start_background(task.id)
        proposal.handoff_task_id = task.id
        proposal.handoff_status = task.status
        proposal.handoff_at = utc_now()
        proposal.handoff_count += 1
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.handoff_created",
            {
                "id": proposal.id,
                "task_id": task.id,
                "task_status": task.status,
                "background_started": bool(start_background),
                "source": source,
                "terminal_first": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "status": "handoff_created",
            "proposal": proposal.to_dict(),
            "task": task.to_dict(),
            "receipt": receipt["id"],
        }

    def generate_candidate(self, proposal_id: str, *, source: str = "terminal") -> dict[str, Any]:
        proposal = self.get(proposal_id)
        if proposal.status != "approved":
            receipt = self.audit.append(
                "improvement.candidate_blocked",
                {
                    "id": proposal.id,
                    "status": proposal.status,
                    "reason": "proposal is not approved",
                    "source": source,
                    "terminal_first": True,
                    "advisory_only": True,
                    "workspace_mutation_performed": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "blocked", "reason": "proposal is not approved", "proposal": proposal.to_dict(), "candidate": None, "receipt": receipt["id"]}
        candidate = ImprovementCandidate(
            id=uuid4().hex[:10],
            proposal_id=proposal.id,
            status="candidate",
            title=f"Repair candidate for {proposal.target_subsystem} {proposal.operation}",
            target_subsystem=proposal.target_subsystem,
            operation=proposal.operation,
            failure_class=proposal.failure_class,
            suggested_files=_suggested_candidate_files(proposal),
            patch_plan=_candidate_patch_plan(proposal),
            verification_commands=_candidate_verification_commands(proposal),
            risk_notes=_candidate_risk_notes(proposal),
            source=source,
        )
        self.save_candidate(candidate)
        proposal.candidate_id = candidate.id
        proposal.candidate_status = candidate.status
        proposal.candidate_at = utc_now()
        proposal.candidate_count += 1
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.candidate_generated",
            {
                "id": proposal.id,
                "candidate_id": candidate.id,
                "suggested_file_count": len(candidate.suggested_files),
                "verification_count": len(candidate.verification_commands),
                "source": source,
                "terminal_first": True,
                "advisory_only": True,
                "workspace_mutation_performed": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {"status": "candidate_generated", "proposal": proposal.to_dict(), "candidate": candidate.to_dict(), "receipt": receipt["id"]}

    def run_candidate_verification(
        self,
        candidate_id: str,
        *,
        command_index: int = 0,
        timeout_seconds: int = 60,
        source: str = "terminal",
    ) -> dict[str, Any]:
        candidate = self.get_candidate(candidate_id)
        timeout_seconds = max(1, int(timeout_seconds))
        if command_index < 0 or command_index >= len(candidate.verification_commands):
            receipt = self.audit.append(
                "improvement.verification_blocked",
                {
                    "candidate_id": candidate.id,
                    "proposal_id": candidate.proposal_id,
                    "command_index": command_index,
                    "reason": "verification command index is not available",
                    "source": source,
                    "terminal_first": True,
                    "candidate_command_allowlisted": False,
                    "workspace_mutation_requested": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "blocked", "reason": "verification command index is not available", "candidate": candidate.to_dict(), "run": None, "receipt": receipt["id"]}

        command = candidate.verification_commands[command_index]
        started = time.monotonic()
        try:
            completed = _run_verification_command(command, cwd=self.paths.workspace, timeout_seconds=timeout_seconds)
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "passed" if completed.returncode == 0 else "failed"
            run = CandidateVerificationRun(
                id=uuid4().hex[:10],
                candidate_id=candidate.id,
                proposal_id=candidate.proposal_id,
                command=command,
                command_index=command_index,
                status=status,
                returncode=completed.returncode,
                stdout_preview=_preview(completed.stdout),
                stderr_preview=_preview(completed.stderr),
                duration_ms=duration_ms,
                timeout_seconds=timeout_seconds,
                source=source,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            run = CandidateVerificationRun(
                id=uuid4().hex[:10],
                candidate_id=candidate.id,
                proposal_id=candidate.proposal_id,
                command=command,
                command_index=command_index,
                status="timeout",
                returncode=None,
                stdout_preview=_preview(exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
                stderr_preview=_preview(exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
                duration_ms=duration_ms,
                timeout_seconds=timeout_seconds,
                source=source,
            )

        self.save_candidate_verification(run)
        candidate.last_verification_status = run.status
        candidate.last_verification_command = run.command
        candidate.last_verification_at = run.created_at
        candidate.last_verification_id = run.id
        candidate.verification_count += 1
        self.save_candidate(candidate)
        proposal = self.get(candidate.proposal_id)
        proposal.candidate_verification_status = run.status
        proposal.candidate_verification_count += 1
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.verification_run",
            {
                "id": run.id,
                "candidate_id": candidate.id,
                "proposal_id": candidate.proposal_id,
                "command": run.command,
                "command_index": command_index,
                "status": run.status,
                "returncode": run.returncode,
                "duration_ms": run.duration_ms,
                "timeout_seconds": timeout_seconds,
                "source": source,
                "terminal_first": True,
                "candidate_command_allowlisted": True,
                "workspace_mutation_requested": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {"status": run.status, "candidate": candidate.to_dict(), "run": run.to_dict(), "receipt": receipt["id"]}

    def apply_candidate(self, candidate_id: str, *, start_background: bool = False, source: str = "terminal") -> dict[str, Any]:
        from aegisagent.core.tasks import TaskRunner

        candidate = self.get_candidate(candidate_id)
        proposal = self.get(candidate.proposal_id)
        reason = ""
        if proposal.status != "approved":
            reason = "proposal is not approved"
        elif candidate.last_verification_status != "passed":
            reason = "candidate must have a passing verification receipt"
        if reason:
            receipt = self.audit.append(
                "improvement.candidate_apply_blocked",
                {
                    "candidate_id": candidate.id,
                    "proposal_id": proposal.id,
                    "proposal_status": proposal.status,
                    "candidate_verification_status": candidate.last_verification_status,
                    "reason": reason,
                    "source": source,
                    "terminal_first": True,
                    "verified_candidate_required": True,
                    "workspace_mutation_allowed_before_approval": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "blocked", "reason": reason, "proposal": proposal.to_dict(), "candidate": candidate.to_dict(), "task": None, "receipt": receipt["id"]}

        runner = TaskRunner(self.paths)
        task = runner.submit(_candidate_apply_prompt(proposal, candidate), source=f"improvement-candidate:{candidate.id}")
        if start_background:
            task = runner.start_background(task.id)
        candidate.apply_task_id = task.id
        candidate.apply_status = task.status
        candidate.apply_at = utc_now()
        candidate.apply_count += 1
        candidate.status = "apply_queued" if task.status == "queued" else f"apply_{task.status}"
        self.save_candidate(candidate)
        proposal.handoff_task_id = task.id
        proposal.handoff_status = task.status
        proposal.handoff_at = candidate.apply_at
        proposal.handoff_count += 1
        proposal.candidate_status = candidate.status
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.candidate_apply_created",
            {
                "candidate_id": candidate.id,
                "proposal_id": proposal.id,
                "task_id": task.id,
                "task_status": task.status,
                "background_started": bool(start_background),
                "last_verification_id": candidate.last_verification_id,
                "last_verification_command": candidate.last_verification_command,
                "source": source,
                "terminal_first": True,
                "verified_candidate_required": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {"status": "candidate_apply_created", "proposal": proposal.to_dict(), "candidate": candidate.to_dict(), "task": task.to_dict(), "receipt": receipt["id"]}

    def review_candidate_diff(self, candidate_id: str, *, source: str = "terminal") -> dict[str, Any]:
        candidate = self.get_candidate(candidate_id)
        proposal = self.get(candidate.proposal_id)
        files = [_candidate_file_diff(self.paths, path) for path in candidate.suggested_files]
        changed_count = sum(1 for item in files if item["has_changes"])
        missing_count = sum(1 for item in files if item["status"] == "missing")
        error_count = sum(1 for item in files if item["status"] == "error")
        receipt = self.audit.append(
            "improvement.candidate_diff_reviewed",
            {
                "candidate_id": candidate.id,
                "proposal_id": proposal.id,
                "reviewed_file_count": len(files),
                "changed_file_count": changed_count,
                "missing_file_count": missing_count,
                "error_file_count": error_count,
                "source": source,
                "terminal_first": True,
                "advisory_only": True,
                "workspace_mutation_performed": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {
            "status": "candidate_diff_reviewed",
            "proposal": proposal.to_dict(),
            "candidate": candidate.to_dict(),
            "files": files,
            "reviewed_file_count": len(files),
            "changed_file_count": changed_count,
            "missing_file_count": missing_count,
            "error_file_count": error_count,
            "terminal_first": True,
            "advisory_only": True,
            "workspace_mutation_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def record_evidence(
        self,
        proposal_id: str,
        *,
        changed_files: list[str],
        verification_command: str,
        verification_result: str,
        task_id: str = "",
        source: str = "terminal",
    ) -> dict[str, Any]:
        proposal = self.get(proposal_id)
        files = _clean_changed_files(changed_files)
        command = redact_text(verification_command).text.strip()
        result = redact_text(verification_result).text.strip()
        reason = ""
        if proposal.status not in {"approved", "implemented"}:
            reason = "proposal is not approved"
        elif not proposal.handoff_task_id and not task_id.strip():
            reason = "implementation handoff task is required"
        elif not files:
            reason = "changed files are required"
        elif not command:
            reason = "verification command is required"
        elif not result:
            reason = "verification result is required"
        if reason:
            receipt = self.audit.append(
                "improvement.evidence_blocked",
                {
                    "id": proposal.id,
                    "status": proposal.status,
                    "reason": reason,
                    "source": source,
                    "terminal_first": True,
                    "workspace_mutation_allowed_before_approval": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "blocked", "reason": reason, "proposal": proposal.to_dict(), "receipt": receipt["id"]}

        if task_id.strip():
            proposal.handoff_task_id = redact_text(task_id).text.strip()
        proposal.changed_files = files
        proposal.verification_command = command
        proposal.verification_result = result
        proposal.implementation_status = "evidence_recorded"
        proposal.evidence_at = utc_now()
        proposal.evidence_count += 1
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.evidence_recorded",
            {
                "id": proposal.id,
                "task_id": proposal.handoff_task_id,
                "changed_file_count": len(files),
                "verification_command": command,
                "verification_result": result,
                "source": source,
                "terminal_first": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {"status": "evidence_recorded", "proposal": proposal.to_dict(), "receipt": receipt["id"]}

    def mark_implemented(self, proposal_id: str, *, source: str = "terminal") -> dict[str, Any]:
        proposal = self.get(proposal_id)
        reason = ""
        if proposal.status not in {"approved", "implemented"}:
            reason = "proposal is not approved"
        elif not proposal.changed_files or not proposal.verification_command or not proposal.verification_result:
            reason = "changed-file evidence and verification result are required"
        if reason:
            receipt = self.audit.append(
                "improvement.implemented_blocked",
                {
                    "id": proposal.id,
                    "status": proposal.status,
                    "reason": reason,
                    "source": source,
                    "terminal_first": True,
                    "workspace_mutation_allowed_before_approval": False,
                    "external_action_started": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {
                "status": "blocked",
                "reason": reason,
                "proposal": proposal.to_dict(),
                "receipt": receipt["id"],
            }
        proposal.status = "implemented"
        proposal.implementation_status = "implemented"
        proposal.implemented_at = utc_now()
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.implemented",
            {
                "id": proposal.id,
                "task_id": proposal.handoff_task_id,
                "changed_file_count": len(proposal.changed_files),
                "verification_command": proposal.verification_command,
                "source": source,
                "terminal_first": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return {"status": "implemented", "proposal": proposal.to_dict(), "receipt": receipt["id"]}

    def save(self, proposal: ImprovementProposal) -> None:
        proposal.updated_at = utc_now()
        self.paths.improvements_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.improvements_dir / f"{proposal.id}.json").write_text(json.dumps(proposal.to_dict(), indent=2) + "\n", encoding="utf-8")

    def save_candidate(self, candidate: ImprovementCandidate) -> None:
        _candidate_dir(self.paths).mkdir(parents=True, exist_ok=True)
        (_candidate_dir(self.paths) / f"{candidate.id}.json").write_text(json.dumps(candidate.to_dict(), indent=2) + "\n", encoding="utf-8")

    def get_candidate(self, candidate_id: str) -> ImprovementCandidate:
        path = _candidate_dir(self.paths) / f"{candidate_id}.json"
        if not path.exists():
            raise KeyError(f"improvement candidate not found: {candidate_id}")
        return ImprovementCandidate.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_candidate_verification(self, run: CandidateVerificationRun) -> None:
        _candidate_dir(self.paths).mkdir(parents=True, exist_ok=True)
        path = _candidate_verification_log(self.paths)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run.to_dict()) + "\n")

    def get(self, proposal_id: str) -> ImprovementProposal:
        path = self.paths.improvements_dir / f"{proposal_id}.json"
        if not path.exists():
            raise KeyError(f"improvement proposal not found: {proposal_id}")
        return ImprovementProposal.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.paths.improvements_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append(self.get(path.stem).to_dict())
            if len(rows) >= limit:
                break
        return rows

    def review(self, proposal_id: str, *, decision: str, rationale: str = "", source: str = "terminal") -> tuple[ImprovementProposal, str]:
        status = {"approve": "approved", "approved": "approved", "reject": "rejected", "rejected": "rejected", "review": "reviewing", "reviewing": "reviewing"}.get(decision)
        if not status:
            raise ValueError("decision must be approve, reject, or review")
        proposal = self.get(proposal_id)
        proposal.status = status
        proposal.review_rationale = redact_text(rationale).text
        self.save(proposal)
        receipt = self.audit.append(
            "improvement.reviewed",
            {
                "id": proposal.id,
                "status": proposal.status,
                "review_gate": proposal.review_gate,
                "source": source,
                "terminal_first": True,
                "workspace_mutation_allowed_before_approval": False,
                "external_action_started": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        return proposal, receipt["id"]


def classify_failure(summary: str) -> FailureClassification:
    lowered = summary.lower()
    matched_class = "runtime_failure"
    matched_signals: list[str] = []
    for failure_class, phrases in _FAILURE_CLASS_RULES:
        signals = [_signal_label(phrase) for phrase in phrases if phrase in lowered]
        if signals:
            matched_class = failure_class
            matched_signals = _dedupe(signals)
            break
    if not matched_signals:
        matched_signals = ["unclassified_failure"]
    retryable = any(signal in _RETRYABLE_SIGNALS for signal in matched_signals)
    return FailureClassification(
        failure_class=matched_class,
        severity=_severity(matched_class, matched_signals),
        confidence=_confidence(matched_class, matched_signals),
        signals=tuple(matched_signals),
        review_gate=_review_gate(matched_class),
        retryable=retryable,
    )


def improvement_summary(paths: RuntimePaths) -> dict[str, Any]:
    proposals = ImprovementStore(paths).list(limit=1000)
    by_status: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for proposal in proposals:
        status = str(proposal["status"])
        by_status[status] = by_status.get(status, 0) + 1
        failure_class = str(proposal["failure_class"])
        by_class[failure_class] = by_class.get(failure_class, 0) + 1
    open_count = sum(1 for proposal in proposals if proposal["status"] in {"proposed", "reviewing"})
    return {
        "proposals": proposals,
        "proposal_count": len(proposals),
        "open_review_count": open_count,
        "by_status": dict(sorted(by_status.items())),
        "failure_classes": dict(sorted(by_class.items())),
        "terminal_first": True,
        "workspace_mutation_allowed_before_approval": False,
        "external_action_started": False,
        "browser_auto_launch": False,
        "next_actions": _summary_next_actions(proposals, open_count),
    }


def format_improvement(proposal: ImprovementProposal | dict[str, Any], *, receipt: str = "") -> str:
    payload = proposal.to_dict() if isinstance(proposal, ImprovementProposal) else proposal
    lines = [
        "AEGIS IMPROVEMENT PROPOSAL",
        f"proposal   {payload['id']}  {payload['status']}",
        f"class      {payload['failure_class']}  severity={payload['severity']} gate={payload['review_gate']}",
        f"target     {payload['target_subsystem']} / {payload['operation']}",
        f"summary    {payload['summary']}",
        f"action     {payload['proposed_action']}",
        "safety     terminal_first=true workspace_mutation_allowed_before_approval=false external_action_started=false",
        "",
        "validation",
    ]
    lines.extend(f"- {item}" for item in payload["required_validation"])
    if payload.get("review_rationale"):
        lines.extend(["", f"review     {payload['review_rationale']}"])
    if payload.get("handoff_task_id"):
        lines.extend(["", f"handoff    {payload['handoff_task_id']}  {payload.get('handoff_status', 'unknown')}"])
    if payload.get("candidate_id"):
        lines.extend(["", f"candidate  {payload['candidate_id']}  {payload.get('candidate_status', 'candidate')}"])
        if payload.get("candidate_verification_status"):
            lines.append(f"candidate check {payload['candidate_verification_status']} count={payload.get('candidate_verification_count', 0)}")
    if payload.get("implementation_status") and payload["implementation_status"] != "not_started":
        lines.extend(["", f"evidence   {payload['implementation_status']}"])
        if payload.get("changed_files"):
            lines.extend(f"file       {item}" for item in payload["changed_files"])
        if payload.get("verification_command"):
            lines.append(f"verify     {payload['verification_command']}")
        if payload.get("verification_result"):
            lines.append(f"result     {payload['verification_result']}")
    if receipt:
        lines.extend(["", f"receipt    {receipt}"])
    return "\n".join(lines)


def format_improvements(payload: dict[str, Any]) -> str:
    command = terminal_command_name()
    lines = [
        "AEGIS IMPROVEMENTS",
        (
            "safety      "
            f"terminal_first={str(payload['terminal_first']).lower()} "
            f"workspace_mutation_allowed_before_approval={str(payload['workspace_mutation_allowed_before_approval']).lower()} "
            f"external_action_started={str(payload['external_action_started']).lower()} "
            f"browser_auto_launch={str(payload['browser_auto_launch']).lower()}"
        ),
        f"counts      total={payload['proposal_count']} open_review={payload['open_review_count']}",
        f"status      {payload['by_status']}",
        "",
    ]
    if not payload["proposals"]:
        lines.extend(
            [
                "No improvement proposals yet.",
                f"create: {command} improve propose \"policy denied a needed safe git read\" --target policy --operation evaluate",
                "tui:    /improve propose policy denied a needed safe git read",
            ]
        )
    else:
        for proposal in payload["proposals"]:
            handoff = f" | handoff: {proposal['handoff_task_id']} ({proposal['handoff_status']})" if proposal.get("handoff_task_id") else ""
            lines.extend(
                [
                    f"[{proposal['status']}] {proposal['id']}  {proposal['failure_class']}  {proposal['summary']}",
                    f"  gate: {proposal['review_gate']} | target: {proposal['target_subsystem']} / {proposal['operation']}{handoff}",
                    "",
                ]
            )
        lines.extend(
            [
                "commands",
                f"- show: {command} improve show <id>",
                f"- approve: {command} improve approve <id> --rationale <text>",
                f"- implement: {command} improve implement <id>",
                f"- candidate: {command} improve candidate <id>",
                f"- verify: {command} improve verify <candidate-id>",
                f"- apply: {command} improve apply <candidate-id>",
                f"- evidence: {command} improve evidence <id> --files <paths> --validation <command> --result <result>",
                f"- complete: {command} improve complete <id>",
                f"- reject: {command} improve reject <id> --rationale <text>",
            ]
        )
    lines.extend(["", "next"])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    return "\n".join(lines).rstrip()


def _summary_next_actions(proposals: list[dict[str, Any]], open_count: int) -> list[str]:
    if not proposals:
        return ["Capture failures or capability gaps as reviewed proposals before implementing self-edits."]
    actions: list[str] = []
    if open_count:
        actions.append("Review proposed improvements before allowing workspace mutation.")
    if any(proposal["status"] == "approved" and not proposal.get("handoff_task_id") for proposal in proposals):
        actions.append("Hand approved proposals to governed tasks before implementation work starts.")
    if any(proposal["status"] == "approved" and not proposal.get("candidate_id") for proposal in proposals):
        actions.append("Generate advisory repair candidates before editing workspace files.")
    if any(proposal.get("candidate_id") and not proposal.get("candidate_verification_count") for proposal in proposals):
        actions.append("Run a candidate verification receipt before using the plan as implementation evidence.")
    if any(proposal.get("candidate_verification_status") == "passed" and not proposal.get("handoff_task_id") for proposal in proposals):
        actions.append("Apply verified candidates into governed task handoffs before editing workspace files.")
    if any(proposal.get("handoff_task_id") and not proposal.get("changed_files") for proposal in proposals):
        actions.append("Record changed files and verification results before marking proposals implemented.")
    if any(proposal["status"] == "rejected" for proposal in proposals):
        actions.append("Keep rejected proposals as audit evidence; create a new proposal if the issue remains.")
    return actions or ["No open self-improvement actions."]


def _handoff_prompt(proposal: ImprovementProposal) -> str:
    validation = "\n".join(f"- {item}" for item in proposal.required_validation)
    return "\n".join(
        [
            f"Implement approved improvement proposal {proposal.id}.",
            "",
            f"Summary: {proposal.summary}",
            f"Target: {proposal.target_subsystem} / {proposal.operation}",
            f"Failure class: {proposal.failure_class}",
            f"Severity: {proposal.severity}",
            f"Review gate: {proposal.review_gate}",
            f"Proposed action: {proposal.proposed_action}",
            "",
            "Required validation:",
            validation,
            "",
            "Constraints:",
            "- preserve terminal-first behavior",
            "- do not launch a browser unless explicitly requested",
            "- do not include raw secret values in artifacts, prompts, or receipts",
            "- record changed files and verification commands before marking work done",
            "- keep workspace mutation governed by normal operator and policy controls",
        ]
    )


def _candidate_apply_prompt(proposal: ImprovementProposal, candidate: ImprovementCandidate) -> str:
    suggested_files = "\n".join(f"- {item}" for item in candidate.suggested_files)
    patch_plan = "\n".join(f"- {item}" for item in candidate.patch_plan)
    verification = "\n".join(f"- {item}" for item in candidate.verification_commands)
    risks = "\n".join(f"- {item}" for item in candidate.risk_notes)
    command = terminal_command_name()
    return "\n".join(
        [
            f"Apply verified improvement candidate {candidate.id} for proposal {proposal.id}.",
            "",
            f"Summary: {proposal.summary}",
            f"Target: {proposal.target_subsystem} / {proposal.operation}",
            f"Failure class: {proposal.failure_class}",
            f"Review gate: {proposal.review_gate}",
            f"Last verification: {candidate.last_verification_status} via {candidate.last_verification_id}",
            f"Last verification command: {candidate.last_verification_command}",
            "",
            "Suggested files:",
            suggested_files,
            "",
            "Patch plan:",
            patch_plan,
            "",
            "Verification commands:",
            verification,
            "",
            "Risk notes:",
            risks,
            "",
            "Constraints:",
            "- preserve terminal-first behavior",
            "- do not launch a browser unless explicitly requested",
            "- do not include raw secret values in artifacts, prompts, or receipts",
            "- keep workspace mutation governed by normal operator and policy controls",
            f"- record changed files and verification output with `{command} improve evidence` before completion",
            "- do not mark the proposal implemented until changed-file evidence is recorded",
        ]
    )


def _clean_changed_files(changed_files: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in changed_files:
        for part in str(item).replace("\n", ",").split(","):
            value = redact_text(part).text.strip()
            if value and value not in cleaned:
                cleaned.append(value)
    return cleaned


def format_candidate(candidate: ImprovementCandidate | dict[str, Any], *, receipt: str = "") -> str:
    payload = candidate.to_dict() if isinstance(candidate, ImprovementCandidate) else candidate
    lines = [
        "AEGIS IMPROVEMENT CANDIDATE",
        f"candidate  {payload['id']}  {payload['status']}",
        f"proposal   {payload['proposal_id']}",
        f"target     {payload['target_subsystem']} / {payload['operation']}",
        "safety     terminal_first=true advisory_only=true workspace_mutation_performed=false external_action_started=false",
        "",
        "suggested files",
    ]
    lines.extend(f"- {item}" for item in payload["suggested_files"])
    lines.extend(["", "patch plan"])
    lines.extend(f"- {item}" for item in payload["patch_plan"])
    lines.extend(["", "verification"])
    lines.extend(f"{index}. {item}" for index, item in enumerate(payload["verification_commands"]))
    if payload.get("last_verification_status"):
        lines.extend(
            [
                "",
                (
                    "last check "
                    f"{payload['last_verification_status']}  "
                    f"{payload.get('last_verification_id', '')}  "
                    f"{payload.get('last_verification_at', '')}"
                ).rstrip(),
                f"verify     {payload.get('last_verification_command', '')}",
            ]
        )
    if payload.get("apply_task_id"):
        lines.extend(["", f"apply     {payload['apply_task_id']}  {payload.get('apply_status', 'unknown')}"])
    lines.extend(["", "risk notes"])
    lines.extend(f"- {item}" for item in payload["risk_notes"])
    if receipt:
        lines.extend(["", f"receipt    {receipt}"])
    return "\n".join(lines)


def format_verification_run(payload: dict[str, Any], *, receipt: str = "") -> str:
    run = payload["run"]
    lines = [
        "AEGIS IMPROVEMENT VERIFICATION",
        f"run        {run['id']}  {run['status']}",
        f"candidate  {run['candidate_id']}",
        f"proposal   {run['proposal_id']}",
        f"command    [{run['command_index']}] {run['command']}",
        f"result     returncode={run['returncode']} duration_ms={run['duration_ms']} timeout={run['timeout_seconds']}s",
        "safety     terminal_first=true candidate_command_allowlisted=true workspace_mutation_requested=false external_action_started=false browser_auto_launch=false",
    ]
    if run.get("stdout_preview"):
        lines.extend(["", "stdout", run["stdout_preview"]])
    if run.get("stderr_preview"):
        lines.extend(["", "stderr", run["stderr_preview"]])
    if receipt:
        lines.extend(["", f"receipt    {receipt}"])
    return "\n".join(lines)


def format_candidate_diff_review(payload: dict[str, Any]) -> str:
    candidate = payload["candidate"]
    lines = [
        "AEGIS CANDIDATE DIFF REVIEW",
        f"candidate  {candidate['id']}  {candidate['status']}",
        f"proposal   {candidate['proposal_id']}",
        (
            "safety     terminal_first=true advisory_only=true "
            "workspace_mutation_performed=false external_action_started=false browser_auto_launch=false"
        ),
        (
            "counts     "
            f"reviewed={payload['reviewed_file_count']} "
            f"changed={payload['changed_file_count']} "
            f"missing={payload['missing_file_count']} "
            f"errors={payload['error_file_count']}"
        ),
        "",
    ]
    for item in payload["files"]:
        state = "changed" if item["has_changes"] else item["status"]
        lines.append(f"[{state}] {item['path']} lines={item['line_count']} truncated={str(item['truncated']).lower()}")
        if item.get("message"):
            lines.append(f"  {item['message']}")
        if item.get("preview"):
            lines.append(item["preview"])
    lines.extend(
        [
            "",
            "next       review changed diffs before `improve apply`; record evidence only after implementation verification",
            f"receipt    {payload['receipt']}",
        ]
    )
    return "\n".join(lines)


def _candidate_dir(paths: RuntimePaths):
    return paths.improvements_dir / "candidates"


def _candidate_verification_log(paths: RuntimePaths):
    return _candidate_dir(paths) / "verification.jsonl"


def _run_verification_command(command: str, *, cwd, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    tokens = shlex.split(command)
    if not tokens:
        raise ValueError("verification command is empty")
    env = dict(os.environ)
    while tokens and _is_env_assignment(tokens[0]):
        key, value = tokens.pop(0).split("=", 1)
        env[key] = _verification_env_value(key, value, cwd=cwd, base=env.get(key, ""))
    _ensure_package_pythonpath(env)
    if tokens and tokens[0] in {"python", "python3"}:
        tokens[0] = sys.executable
    return subprocess.run(
        tokens,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )


def _is_env_assignment(token: str) -> bool:
    if "=" not in token:
        return False
    key, _value = token.split("=", 1)
    return key.replace("_", "").isalnum() and key[0].isalpha()


def _verification_env_value(key: str, value: str, *, cwd, base: str) -> str:
    if key != "PYTHONPATH":
        return value
    parts = [part for part in value.split(os.pathsep) if part]
    resolved: list[str] = []
    for part in parts:
        path = Path(part)
        if not path.is_absolute():
            path = Path(cwd) / path
        resolved.append(str(path))
    if base:
        resolved.append(base)
    return os.pathsep.join(resolved)


def _ensure_package_pythonpath(env: dict[str, str]) -> None:
    src_root = Path(__file__).resolve().parents[2]
    repo_root = src_root.parent
    current = [part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part]
    for path in (str(repo_root), str(src_root)):
        if path not in current:
            current.insert(0, path)
    env["PYTHONPATH"] = os.pathsep.join(current)


def _preview(text: str, *, limit: int = 600) -> str:
    redacted = redact_text(text or "").text.strip()
    if len(redacted) <= limit:
        return redacted
    return redacted[:limit].rstrip() + "\n...<truncated>"


def _candidate_file_diff(paths: RuntimePaths, relative_path: str, *, max_bytes: int = 4000) -> dict[str, Any]:
    raw_path = redact_text(relative_path).text.strip()
    try:
        target = (paths.workspace / raw_path).resolve()
        rel = target.relative_to(paths.workspace)
    except (OSError, ValueError):
        return _diff_payload(raw_path, status="blocked", message="path is outside the workspace")
    rel_text = str(rel)
    if not target.exists() or not target.is_file():
        return _diff_payload(rel_text, status="missing", message="suggested file does not exist in this workspace")
    diff = _run_git_diff_preview(paths.workspace, ["diff", "--", rel_text], max_bytes=max_bytes)
    if diff["status"] == "ok" and diff["preview"]:
        diff.update({"path": rel_text, "mode": "tracked"})
        return diff
    status = subprocess.run(["git", "status", "--short", "--", rel_text], cwd=paths.workspace, text=True, capture_output=True, timeout=10, check=False)
    if status.returncode == 0 and status.stdout.startswith("??"):
        no_index = _run_git_diff_preview(paths.workspace, ["diff", "--no-index", "--", "/dev/null", rel_text], max_bytes=max_bytes)
        no_index.update({"path": rel_text, "mode": "untracked"})
        if no_index["status"] == "error" and no_index["preview"]:
            no_index["status"] = "ok"
        return no_index
    diff.update({"path": rel_text, "mode": "tracked"})
    return diff


def _run_git_diff_preview(workspace: Path, args: list[str], *, max_bytes: int) -> dict[str, Any]:
    try:
        result = subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _diff_payload(".", status="error", message=str(exc))
    output = result.stdout or ""
    error = result.stderr or ""
    redacted_output = redact_text(output[:max_bytes])
    redacted_error = redact_text(error[:600])
    status = "ok" if result.returncode in {0, 1} else "error"
    message = "" if status == "ok" else redacted_error.text
    if status == "ok" and not redacted_output.text:
        message = "no tracked diff for this suggested file"
    return _diff_payload(
        ".",
        status=status,
        preview=redacted_output.text,
        message=message,
        line_count=len(redacted_output.text.splitlines()),
        truncated=len(output) > max_bytes,
        has_changes=bool(redacted_output.text.strip()),
        redacted=redacted_output.redacted or redacted_error.redacted,
    )


def _diff_payload(
    path: str,
    *,
    status: str,
    preview: str = "",
    message: str = "",
    line_count: int = 0,
    truncated: bool = False,
    has_changes: bool = False,
    redacted: bool = False,
) -> dict[str, Any]:
    return {
        "path": path,
        "status": status,
        "preview": preview,
        "message": message,
        "line_count": line_count,
        "truncated": truncated,
        "has_changes": has_changes,
        "redacted": redacted,
        "mode": "",
    }


def _suggested_candidate_files(proposal: ImprovementProposal) -> list[str]:
    target = proposal.target_subsystem.lower()
    operation = proposal.operation.lower()
    files = ["tests/test_cli.py", "tests/test_tui.py"]
    if "connector" in target:
        files.insert(0, "src/aegisagent/core/connectors.py")
    elif "policy" in target:
        files.insert(0, "src/aegisagent/security/policy.py")
    elif "automation" in target or "schedule" in target:
        files.insert(0, "src/aegisagent/core/automation.py")
    elif "improve" in target or "repair" in operation:
        files.insert(0, "src/aegisagent/core/improvement.py")
    elif "task" in target:
        files.insert(0, "src/aegisagent/core/tasks.py")
    elif "model" in target or "provider" in target:
        files.insert(0, "src/aegisagent/core/provider_config.py")
    elif "tui" in target or "terminal" in target:
        files.insert(0, "src/aegisagent/tui/interactive.py")
    else:
        files.insert(0, "src/aegisagent/core/agent.py")
    return _clean_changed_files(files)


def _candidate_patch_plan(proposal: ImprovementProposal) -> list[str]:
    command = terminal_command_name()
    return [
        f"Inspect {proposal.target_subsystem} / {proposal.operation} around the failure summary.",
        f"Implement the smallest governed change matching: {proposal.proposed_action}",
        "Keep the terminal-first/no-browser contract visible in human and JSON output.",
        "Add a focused regression that covers the failing class and the safety flags.",
        f"Record changed files and verification output with `{command} improve evidence` before completion.",
    ]


def _candidate_verification_commands(proposal: ImprovementProposal) -> list[str]:
    target = proposal.target_subsystem.lower()
    commands = ["PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v"]
    if "policy" in target:
        commands.insert(0, "PYTHONPATH=src python3 -m unittest tests.test_policy -v")
    elif "automation" in target or "schedule" in target:
        commands.insert(0, "PYTHONPATH=src python3 -m unittest tests.test_cli tests.test_tui -v")
    elif "task" in target:
        commands.insert(0, "PYTHONPATH=src python3 -m unittest tests.test_terminal_agent_slice -v")
    commands.append("PYTHONPATH=src python3 -m aegisagent audit verify")
    commands.append("git diff --check")
    return commands


def _candidate_risk_notes(proposal: ImprovementProposal) -> list[str]:
    notes = [
        "Candidate is advisory and does not mutate workspace files.",
        "Treat diagnostic context as untrusted evidence.",
        "Do not broaden tool, network, browser, or filesystem access without explicit review.",
    ]
    if proposal.failure_class == "context_safety":
        notes.append("Security review is required before prompt-handling or taint-boundary changes.")
    if proposal.failure_class == "policy_or_permission":
        notes.append("Policy changes must preserve deny-by-default behavior.")
    return notes


def _proposed_action(failure_class: str, target: str, operation: str) -> str:
    if failure_class == "context_safety":
        return f"Quarantine untrusted {target} {operation} evidence and require security review before repair."
    if failure_class == "policy_or_permission":
        return f"Review whether {target} {operation} needs safer scoped capability, clearer denial, or documentation."
    if failure_class == "model_invocation":
        return "Verify provider routing, authentication, fallback behavior, and receipt capture."
    if failure_class == "data_contract":
        return f"Tighten parsing and validation around {target} {operation}, then add malformed-input coverage."
    if failure_class == "persistence_state":
        return "Inspect local state transitions, migrations, and rollback behavior before changing durable records."
    if failure_class == "configuration":
        return "Validate local configuration defaults and produce a clear terminal remediation."
    return f"Investigate {target} {operation}, add focused regression coverage, and record verification evidence."


def _required_validation(classification: FailureClassification) -> list[str]:
    validation = [
        "capture changed files or generated candidate id",
        "run a focused regression or verification command",
        "record the verification result before marking implemented",
        "treat diagnostic context as untrusted evidence",
    ]
    if classification.failure_class == "context_safety":
        validation.extend(["verify secrets are not persisted in repair artifacts", "obtain security review before policy or prompt-handling changes"])
    elif classification.failure_class == "policy_or_permission":
        validation.append("confirm the repair does not broaden access without explicit approval")
    elif classification.failure_class == "model_invocation":
        validation.append("verify provider fallback and auth errors are captured without raw secrets")
    elif classification.failure_class == "data_contract":
        validation.append("include malformed or missing-field input in regression coverage")
    elif classification.failure_class == "persistence_state":
        validation.append("verify local state remains recoverable after retry or rollback")
    elif classification.retryable:
        validation.append("cover retry and timeout behavior with bounded local verification")
    return validation


def _review_gate(failure_class: str) -> str:
    return {
        "context_safety": "security_review_required",
        "policy_or_permission": "policy_review_required",
        "model_invocation": "provider_review_required",
        "data_contract": "contract_review_required",
        "persistence_state": "state_review_required",
        "configuration": "operator_review_required",
        "tool_execution": "maintainer_review_required",
    }.get(failure_class, "maintainer_review_required")


def _severity(failure_class: str, signals: list[str]) -> str:
    if failure_class == "context_safety" or any(signal in _HIGH_SEVERITY_SIGNALS for signal in signals):
        return "high"
    if failure_class in {"policy_or_permission", "persistence_state", "model_invocation"}:
        return "medium"
    if failure_class == "runtime_failure" and signals == ["unclassified_failure"]:
        return "low"
    return "medium"


def _confidence(failure_class: str, signals: list[str]) -> float:
    if failure_class == "runtime_failure" and signals == ["unclassified_failure"]:
        return 0.35
    if len(signals) >= 2:
        return 0.9
    return 0.75


def _signal_label(phrase: str) -> str:
    return phrase.replace(" ", "_").replace("-", "_").strip("_")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


_FAILURE_CLASS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("context_safety", ("prompt injection", "ignore previous instructions", "quarantine", "taint", "untrusted", "exfiltration", "leak secret", "raw secret", "credential", "api key")),
    ("policy_or_permission", ("not allowlisted", "allowlist", "permission", "denied", "forbidden", "unauthorized", "policy", "approval", "sandbox", "escapes workspace", "requires approved")),
    ("model_invocation", ("model", "provider", "rate limit", "context length", "token limit", "authentication", "api error")),
    ("data_contract", ("json", "schema", "parse", "validation", "missing field", "typeerror", "valueerror", "decode")),
    ("persistence_state", ("sqlite", "database", "migration", "state", "checkpoint", "corrupt", "rollback")),
    ("configuration", ("config", "environment", "env var", "not configured", "missing setting")),
    ("tool_execution", ("connector", "tool", "subprocess", "command", "returncode", "exit code", "timeout", "network")),
)
_HIGH_SEVERITY_SIGNALS = {"exfiltration", "leak_secret", "raw_secret", "credential", "api_key", "escapes_workspace"}
_RETRYABLE_SIGNALS = {"timeout", "network", "rate_limit", "api_error"}
