from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegisagent.security.redaction import redact_text

SKILL_TRUST_SCHEMA_VERSION = 1
SKILL_TRUST_SCANNER_VERSION = "2026-05-24"
SKILL_TRUST_RULE_SET_VERSION = "aegis-skill-rules-v1"
MAX_SKILL_FILE_BYTES = 512_000

RISKY_SKILL_MARKERS: dict[str, tuple[str, int, str]] = {
    "../": ("path_escape_hint", 25, "relative parent path reference"),
    ".env": ("secret_access", 30, "environment secret file reference"),
    "authorization:": ("raw_secret_assignment", 35, "authorization header pattern"),
    "chmod 777": ("permissive_permissions", 25, "world-writable permission change"),
    "curl ": ("network_fetch", 20, "network fetch command"),
    "curl -fsSL": ("pipe_to_shell_risk", 35, "curl installer pattern"),
    "eval(": ("dynamic_execution", 35, "dynamic code evaluation"),
    "exec(": ("dynamic_execution", 35, "dynamic code execution"),
    "keychain dump": ("secret_access", 45, "credential store access"),
    "npm install": ("package_install", 30, "package install command"),
    "OPENAI_API_KEY=": ("raw_secret_assignment", 35, "raw secret assignment pattern"),
    "os.system": ("shell_execution", 35, "host shell execution"),
    "pip install": ("package_install", 30, "package install command"),
    "rm -rf": ("destructive_shell", 50, "destructive shell deletion"),
    "security find-generic-password": ("secret_access", 45, "credential store access"),
    "SLACK_BOT_TOKEN=": ("raw_secret_assignment", 35, "raw secret assignment pattern"),
    "subprocess": ("shell_execution", 35, "host process execution"),
    "sudo ": ("privileged_shell", 35, "privileged host command"),
    "wget ": ("network_fetch", 20, "network fetch command"),
}


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    description: str
    quarantined: bool
    findings: tuple[dict[str, Any], ...]
    trust_level: str
    trust_score: int
    source_scope: str
    skill_id: str
    relative_path: str
    allowed_root: Path
    skill_file_sha256: str
    bundle_sha256: str
    file_size_bytes: int
    truncated: bool = False
    symlink_detected: bool = False
    inside_allowed_root: bool = True
    readable: bool = True

    def to_dict(self) -> dict:
        trust = {
            "schema_version": SKILL_TRUST_SCHEMA_VERSION,
            "scanner_version": SKILL_TRUST_SCANNER_VERSION,
            "rule_set_version": SKILL_TRUST_RULE_SET_VERSION,
            "skill_id": self.skill_id,
            "source_scope": self.source_scope,
            "relative_path": self.relative_path,
            "allowed_root": str(self.allowed_root),
            "skill_file_sha256": self.skill_file_sha256,
            "bundle_sha256": self.bundle_sha256,
            "readable": self.readable,
            "truncated": self.truncated,
            "file_size_bytes": self.file_size_bytes,
            "inside_allowed_root": self.inside_allowed_root,
            "symlink_detected": self.symlink_detected,
            "risk_markers": list(self.findings),
            "risk_level": _risk_level(self.findings),
            "trust_status": self.trust_level,
            "trust_score": self.trust_score,
            "execution_allowed": False,
            "execution_performed": False,
            "outside_path_read": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "model_invocation_performed": False,
            "network_request_performed": False,
            "send_probe_performed": False,
            "raw_secret_values_included": False,
        }
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "quarantined": self.quarantined,
            "findings": list(self.findings),
            "trust_level": self.trust_level,
            "trust_score": self.trust_score,
            "source_scope": self.source_scope,
            "skill_id": self.skill_id,
            "relative_path": self.relative_path,
            "readable": self.readable,
            "execution_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "trust": trust,
        }


class SkillLoader:
    def __init__(self, roots: list[Path]):
        self.roots = roots

    def discover(self) -> list[Skill]:
        skills: list[Skill] = []
        for root in self.roots:
            if not root.exists() or root.is_symlink():
                continue
            root_resolved = root.resolve()
            for skill_file in _skill_files(root_resolved):
                skills.append(_load_skill(skill_file, root_resolved, _source_scope(root_resolved)))
        return skills

    def trust_summary(self, *, limit: int | None = None) -> dict[str, Any]:
        skills = self.discover()
        counts = {
            "trusted": sum(1 for skill in skills if skill.trust_level == "trusted"),
            "review": sum(1 for skill in skills if skill.trust_level == "review"),
            "quarantined": sum(1 for skill in skills if skill.trust_level == "quarantined"),
            "total": len(skills),
        }
        visible_skills = skills if limit is None else skills[: max(0, limit)]
        return {
            "title": "AEGIS SKILL TRUST",
            "counts": counts,
            "skills": [skill.to_dict() for skill in visible_skills],
            "limit": limit,
            "execution_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "model_invocation_performed": False,
            "network_request_performed": False,
            "send_probe_performed": False,
            "raw_secret_values_included": False,
        }


def _extract_description(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("description:"):
            return redact_text(line.split(":", 1)[1].strip()).text
    for line in body.splitlines():
        if line.strip() and not line.startswith("---") and not line.startswith("name:"):
            return redact_text(line.strip("# ").strip()).text
    return "No description supplied."


def _skill_findings(body: str, *, extra: tuple[dict[str, Any], ...] = ()) -> tuple[dict[str, Any], ...]:
    findings = list(extra)
    seen = {(finding.get("rule_id"), finding.get("line")) for finding in findings}
    for marker, (finding_type, severity, rationale) in sorted(RISKY_SKILL_MARKERS.items()):
        for index, line in enumerate(body.splitlines(), start=1):
            if marker in line:
                rule_id = f"marker.{finding_type}.{_stable_fragment(marker)}"
                key = (rule_id, index)
                if key in seen:
                    continue
                findings.append(
                    {
                        "rule_id": rule_id,
                        "marker": redact_text(marker).text,
                        "type": finding_type,
                        "severity": severity,
                        "line": index,
                        "evidence": redact_text(line.strip()[:160]).text,
                        "rationale": rationale,
                    }
                )
                seen.add(key)
    return tuple(findings)


def _trust_score(findings: tuple[dict[str, Any], ...], *, readable: bool, inside_allowed_root: bool, symlink_detected: bool, truncated: bool) -> int:
    if not readable or not inside_allowed_root or symlink_detected:
        return 0
    penalty = sum(int(finding["severity"]) for finding in findings)
    if truncated:
        penalty += 20
    return max(0, 100 - penalty)


def _trust_level(score: int, findings: tuple[dict[str, Any], ...], *, readable: bool, inside_allowed_root: bool, symlink_detected: bool) -> str:
    if not readable or not inside_allowed_root or symlink_detected:
        return "quarantined"
    if any(int(finding["severity"]) >= 35 for finding in findings) or score < 60:
        return "quarantined"
    if findings or score < 90:
        return "review"
    return "trusted"


def _skill_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(dirname for dirname in dirnames if not (current_path / dirname).is_symlink())
        if "SKILL.md" in filenames:
            found.append(current_path / "SKILL.md")
    return sorted(found)


def _load_skill(skill_file: Path, root: Path, source_scope: str) -> Skill:
    name = redact_text(skill_file.parent.name).text
    path = skill_file.parent
    relative_path = _relative_path(path, root)
    extra_findings: list[dict[str, Any]] = []
    readable = True
    inside_allowed_root = True
    symlink_detected = skill_file.is_symlink() or path.is_symlink()
    body = ""
    file_size_bytes = 0
    truncated = False
    skill_hash = ""
    bundle_hash = ""
    try:
        skill_file.resolve(strict=False).relative_to(root)
    except ValueError:
        inside_allowed_root = False
        readable = False
    if symlink_detected:
        readable = False
        extra_findings.append(_path_finding("path.symlink", "path_escape", 50, "symlinked skill files are not read", 0))
    if not inside_allowed_root:
        extra_findings.append(_path_finding("path.outside_root", "path_escape", 50, "skill file resolves outside the allowed root", 0))
    if readable:
        try:
            file_size_bytes = skill_file.stat().st_size
            raw = skill_file.read_bytes()
            if len(raw) > MAX_SKILL_FILE_BYTES:
                raw = raw[:MAX_SKILL_FILE_BYTES]
                truncated = True
                extra_findings.append(_path_finding("file.truncated", "oversized_skill", 25, "skill file exceeded scanner byte limit", 0))
            body = raw.decode("utf-8", errors="replace")
            skill_hash = hashlib.sha256(raw).hexdigest()
            bundle_hash = _bundle_sha256(path, root)
        except OSError:
            readable = False
            extra_findings.append(_path_finding("file.unreadable", "unreadable_skill", 50, "skill file could not be read", 0))
    description = _extract_description(body) if readable else "Blocked unreadable or unsafe skill file."
    findings = _skill_findings(body, extra=tuple(extra_findings))
    trust_score = _trust_score(findings, readable=readable, inside_allowed_root=inside_allowed_root, symlink_detected=symlink_detected, truncated=truncated)
    trust_level = _trust_level(trust_score, findings, readable=readable, inside_allowed_root=inside_allowed_root, symlink_detected=symlink_detected)
    skill_id = _skill_id(source_scope, relative_path, skill_hash or "unreadable")
    return Skill(
        name=name,
        path=path,
        description=description,
        quarantined=trust_level == "quarantined",
        findings=findings,
        trust_level=trust_level,
        trust_score=trust_score,
        source_scope=source_scope,
        skill_id=skill_id,
        relative_path=relative_path,
        allowed_root=root,
        skill_file_sha256=skill_hash,
        bundle_sha256=bundle_hash,
        file_size_bytes=file_size_bytes,
        truncated=truncated,
        symlink_detected=symlink_detected,
        inside_allowed_root=inside_allowed_root,
        readable=readable,
    )


def _bundle_sha256(path: Path, root: Path) -> str:
    digest = hashlib.sha256()
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(dirname for dirname in dirnames if not (current_path / dirname).is_symlink() and dirname not in {".git", "__pycache__", ".venv", "node_modules"})
        for filename in sorted(filenames):
            file_path = current_path / filename
            if file_path.is_symlink():
                continue
            try:
                relative = file_path.relative_to(root).as_posix()
                data = file_path.read_bytes()
            except (OSError, ValueError):
                continue
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(data).hexdigest().encode("ascii"))
            digest.update(b"\n")
    return digest.hexdigest()


def _path_finding(rule_id: str, finding_type: str, severity: int, rationale: str, line: int) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "marker": "",
        "type": finding_type,
        "severity": severity,
        "line": line,
        "evidence": "",
        "rationale": rationale,
    }


def _risk_level(findings: tuple[dict[str, Any], ...]) -> str:
    highest = max((int(finding["severity"]) for finding in findings), default=0)
    if highest >= 35:
        return "high"
    if highest >= 20:
        return "medium"
    return "low"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return redact_text(str(path)).text


def _skill_id(source_scope: str, relative_path: str, content_hash: str) -> str:
    return f"{source_scope}:{hashlib.sha256(f'{source_scope}:{relative_path}:{content_hash}'.encode('utf-8')).hexdigest()[:12]}"


def _stable_fragment(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _source_scope(root: Path) -> str:
    home = Path.home()
    try:
        root.resolve().relative_to(home / ".aegisagent")
        return "user"
    except ValueError:
        return "workspace"
