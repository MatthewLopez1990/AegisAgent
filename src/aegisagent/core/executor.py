from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

from aegisagent.config import RuntimePaths
from aegisagent.security.audit import AuditLog
from aegisagent.security.policy import classify_shell_command, decide_tool
from aegisagent.security.redaction import redact_text


@dataclass(frozen=True)
class CommandResult:
    executed: bool
    command: str
    returncode: int | None
    stdout: str
    stderr: str
    decision: dict[str, Any]
    receipt_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "executed": self.executed,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "decision": self.decision,
            "receipt_id": self.receipt_id,
        }


class GovernedExecutor:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.audit = AuditLog(paths)

    def run_shell(self, command: str, *, approved: bool = False, timeout: int = 20) -> CommandResult:
        classification = classify_shell_command(command)
        decision = decide_tool("shell", command, approved=approved).to_dict()
        if decision["action"] != "allow":
            receipt = self.audit.append(
                "executor.shell.blocked",
                {
                    "command": classification.command,
                    "decision": decision,
                    "executed": False,
                },
            )
            return CommandResult(False, classification.command, None, "", "", decision, receipt["id"])

        try:
            args = shlex.split(command)
        except ValueError as exc:
            decision = {**decision, "action": "deny", "rationale": f"shell parse failed: {exc}"}
            receipt = self.audit.append("executor.shell.blocked", {"command": classification.command, "decision": decision, "executed": False})
            return CommandResult(False, classification.command, None, "", "", decision, receipt["id"])

        try:
            completed = subprocess.run(
                args,
                cwd=self.paths.workspace,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = redact_text((exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "").text
            stderr = redact_text((exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "").text
            failed = {**decision, "action": "deny", "rationale": f"command timed out after {timeout}s"}
            receipt = self.audit.append(
                "executor.shell.blocked",
                {
                    "command": classification.command,
                    "decision": failed,
                    "executed": False,
                    "stdout_tail": stdout[-2000:],
                    "stderr_tail": stderr[-2000:],
                },
            )
            return CommandResult(False, classification.command, None, stdout, stderr, failed, receipt["id"])
        except FileNotFoundError as exc:
            failed = {**decision, "action": "deny", "rationale": f"command not found: {args[0]}"}
            receipt = self.audit.append(
                "executor.shell.blocked",
                {
                    "command": classification.command,
                    "decision": failed,
                    "executed": False,
                    "error": str(exc),
                },
            )
            return CommandResult(False, classification.command, None, "", str(exc), failed, receipt["id"])
        stdout = redact_text(completed.stdout[-8000:]).text
        stderr = redact_text(completed.stderr[-8000:]).text
        receipt = self.audit.append(
            "executor.shell.completed",
            {
                "command": classification.command,
                "decision": decision,
                "executed": True,
                "returncode": completed.returncode,
                "stdout_tail": stdout[-2000:],
                "stderr_tail": stderr[-2000:],
            },
        )
        return CommandResult(True, classification.command, completed.returncode, stdout, stderr, decision, receipt["id"])
