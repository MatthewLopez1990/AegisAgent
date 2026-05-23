from __future__ import annotations

import hashlib
import re
import shlex
from dataclasses import dataclass

from aegisagent.models import PolicyDecision
from aegisagent.security.redaction import redact_text

DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-[^\n]*r[^\n]*f\s+(/|\$HOME|~|\.)"),
    re.compile(r"\bsudo\s+rm\b"),
    re.compile(r"\bdd\s+if=.*\bof=/dev/"),
    re.compile(r"\bmkfs(\.|$|\s)"),
    re.compile(r"\bdiskutil\s+erase"),
    re.compile(r"\bchmod\s+-R\s+777\b"),
    re.compile(r"\bkeychain\b.*\bdump\b", re.I),
]

WRITE_VERBS = {"rm", "mv", "cp", "touch", "mkdir", "rmdir", "chmod", "chown", "tee", "sed", "python", "python3", "node", "npm", "pip", "git"}
NETWORK_VERBS = {"curl", "wget", "ssh", "scp", "rsync", "ftp", "nc", "ncat", "telnet"}
GIT_READ = {"status", "diff", "log", "show", "rev-parse"}


@dataclass(frozen=True)
class CommandClassification:
    command: str
    tool: str
    risk: str
    requires_approval: bool
    denied: bool
    rationale: str


def receipt_id_for(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def classify_shell_command(command: str) -> CommandClassification:
    redacted = redact_text(command).text
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return CommandClassification(redacted, "shell", "critical", True, True, "destructive command blocked")

    try:
        tokens = shlex.split(command)
    except ValueError:
        return CommandClassification(redacted, "shell", "medium", True, False, "shell parse failed; ask before execution")
    if not tokens:
        return CommandClassification(redacted, "shell", "low", False, False, "empty command")

    verb = tokens[0]
    if verb in NETWORK_VERBS:
        return CommandClassification(redacted, "network", "high", True, False, "network access is gated")
    if verb == "git":
        if _git_command_is_read_only(tokens):
            return CommandClassification(redacted, "shell", "low", False, False, "read-only shell command")
        return CommandClassification(redacted, "git", "medium", True, False, "git mutation or network operation requires approval")
    if verb in {"ls", "pwd", "cat", "sed", "awk", "rg", "grep", "find"}:
        if ">" in tokens or ">>" in tokens:
            return CommandClassification(redacted, "shell", "medium", True, False, "shell write redirection requires approval")
        return CommandClassification(redacted, "shell", "low", False, False, "read-only shell command")
    if verb in WRITE_VERBS:
        return CommandClassification(redacted, "shell", "medium", True, False, "host write or execution requires approval")
    return CommandClassification(redacted, "shell", "medium", True, False, "unknown command requires approval")


def _git_command_is_read_only(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return True
    subcommand = tokens[1]
    if subcommand in GIT_READ:
        return True
    if subcommand == "branch":
        return len(tokens) == 2 or all(token in {"--list", "-l", "--show-current"} for token in tokens[2:])
    if subcommand == "remote":
        return len(tokens) == 2 or all(token in {"-v", "--verbose"} for token in tokens[2:])
    return False


def decide_tool(tool: str, action: str, *, approved: bool = False, scope: str = "workspace") -> PolicyDecision:
    receipt = receipt_id_for(tool, action, str(approved), scope)
    if tool == "secrets" and action in {"echo", "print", "dump"}:
        return PolicyDecision("deny", "critical", "secret echo is never allowed", receipt, tool, scope)
    if tool == "network" and not approved:
        return PolicyDecision("ask", "high", "network is blocked until approved", receipt, tool, scope)
    if tool == "shell":
        classification = classify_shell_command(action)
        if classification.denied:
            return PolicyDecision("deny", "critical", classification.rationale, receipt, tool, scope, metadata={"command": classification.command})
        if classification.requires_approval and not approved:
            return PolicyDecision("ask", classification.risk, classification.rationale, receipt, tool, scope, metadata={"command": classification.command})
        return PolicyDecision("allow", classification.risk, classification.rationale, receipt, tool, scope, metadata={"command": classification.command})
    if approved or tool in {"browser", "skills", "memory"}:
        return PolicyDecision("allow", "low", "tool allowed within scoped policy", receipt, tool, scope)
    return PolicyDecision("ask", "medium", "tool requires explicit approval", receipt, tool, scope)
