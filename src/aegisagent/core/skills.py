from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegisagent.security.redaction import redact_text

SKILL_TRUST_SCHEMA_VERSION = 1
SKILL_TRUST_SCANNER_VERSION = "2026-05-24"
SKILL_TRUST_RULE_SET_VERSION = "aegis-skill-rules-v1"
MAX_SKILL_FILE_BYTES = 512_000
SKILL_TRUST_MANIFEST = "aegis-skill-trust.json"

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
    manifest_status: str = "missing"
    signature_status: str = "missing"
    manifest_path: str = ""
    manifest_sha256: str = ""
    declared_bundle_sha256: str = ""
    signature_algorithm: str = ""
    issuer_key_id: str = ""
    issuer_public_key_sha256: str = ""
    truncated: bool = False
    symlink_detected: bool = False
    inside_allowed_root: bool = True
    readable: bool = True

    def to_dict(self) -> dict:
        display_path = redact_text(str(self.path)).text
        display_relative_path = redact_text(self.relative_path).text
        display_allowed_root = redact_text(str(self.allowed_root)).text
        display_manifest_path = redact_text(self.manifest_path).text
        trust = {
            "schema_version": SKILL_TRUST_SCHEMA_VERSION,
            "scanner_version": SKILL_TRUST_SCANNER_VERSION,
            "rule_set_version": SKILL_TRUST_RULE_SET_VERSION,
            "skill_id": self.skill_id,
            "source_scope": self.source_scope,
            "relative_path": display_relative_path,
            "allowed_root": display_allowed_root,
            "skill_file_sha256": self.skill_file_sha256,
            "bundle_sha256": self.bundle_sha256,
            "manifest": {
                "status": self.manifest_status,
                "path": display_manifest_path,
                "sha256": self.manifest_sha256,
                "signature_status": self.signature_status,
                "checksum_algorithm": "sha256-bundle-v1",
                "declared_bundle_sha256": self.declared_bundle_sha256,
                "signature_algorithm": self.signature_algorithm,
                "issuer_key_id": self.issuer_key_id,
                "issuer_public_key_sha256": self.issuer_public_key_sha256,
                "verification_performed": False,
            },
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
            "path": display_path,
            "description": self.description,
            "quarantined": self.quarantined,
            "findings": list(self.findings),
            "trust_level": self.trust_level,
            "trust_score": self.trust_score,
            "source_scope": self.source_scope,
            "skill_id": self.skill_id,
            "relative_path": display_relative_path,
            "manifest_status": self.manifest_status,
            "signature_status": self.signature_status,
            "manifest_sha256": self.manifest_sha256,
            "readable": self.readable,
            "execution_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "trust": trust,
        }


def skill_audit_payload(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "counts": summary["counts"],
        "trust_schema_version": SKILL_TRUST_SCHEMA_VERSION,
        "scanner_version": SKILL_TRUST_SCANNER_VERSION,
        "rule_set_version": SKILL_TRUST_RULE_SET_VERSION,
        "audited_skill_count": len(summary.get("skills", [])),
        "skill_verifications": [_skill_verification_record(skill) for skill in summary.get("skills", [])],
        "execution_performed": summary["execution_performed"],
        "external_action_started": summary["external_action_started"],
        "browser_auto_launch": summary["browser_auto_launch"],
        "model_invocation_performed": summary["model_invocation_performed"],
        "network_request_performed": summary["network_request_performed"],
        "send_probe_performed": summary["send_probe_performed"],
        "raw_secret_values_included": summary["raw_secret_values_included"],
    }


def _skill_verification_record(skill: dict[str, Any]) -> dict[str, Any]:
    trust = skill.get("trust", {})
    manifest = trust.get("manifest", {})
    return {
        "skill_id": skill.get("skill_id", ""),
        "source_scope": skill.get("source_scope", ""),
        "relative_path": skill.get("relative_path", ""),
        "trust_level": skill.get("trust_level", ""),
        "trust_score": skill.get("trust_score", 0),
        "quarantined": skill.get("quarantined", False),
        "skill_file_sha256": trust.get("skill_file_sha256", ""),
        "bundle_sha256": trust.get("bundle_sha256", ""),
        "manifest": {
            "status": manifest.get("status", "missing"),
            "path": manifest.get("path", ""),
            "sha256": manifest.get("sha256", ""),
            "checksum_algorithm": manifest.get("checksum_algorithm", ""),
        },
        "signature": {
            "status": manifest.get("signature_status", "missing"),
            "algorithm": manifest.get("signature_algorithm", ""),
            "issuer_key_id": manifest.get("issuer_key_id", ""),
            "issuer_public_key_sha256": manifest.get("issuer_public_key_sha256", ""),
            "verification_performed": manifest.get("verification_performed", False),
        },
        "finding_rule_ids": [finding.get("rule_id", "") for finding in skill.get("findings", [])],
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

    def author_manifest(self, skill_name: str, *, approved: bool = False, force: bool = False) -> dict[str, Any]:
        clean_name = redact_text(skill_name.strip()).text
        selector = skill_name.strip()
        if not _valid_skill_selector(selector):
            return _manifest_author_result("blocked", clean_name, "skill selector must be a skill folder name or source:relative/path", approved=approved)
        matches = [skill for skill in self.discover() if _skill_matches_selector(skill, selector)]
        if not matches:
            return _manifest_author_result("blocked", clean_name, "skill was not found", approved=approved)
        if len(matches) > 1:
            return _manifest_author_result("blocked", clean_name, "skill name is ambiguous across configured roots", approved=approved)
        skill = matches[0]
        skill_dict = skill.to_dict()
        manifest_path = skill.path / SKILL_TRUST_MANIFEST
        display_manifest_path = redact_text(_relative_path(manifest_path, skill.allowed_root)).text
        if skill.symlink_detected or not skill.inside_allowed_root or not skill.readable:
            return _manifest_author_result("blocked", clean_name, "skill path is not safe to write a manifest", skill=skill_dict, path=display_manifest_path, approved=approved)
        if any(finding.get("type") in {"bundle_integrity", "path_escape", "unreadable_skill", "oversized_skill"} for finding in skill.findings):
            return _manifest_author_result("blocked", clean_name, "skill bundle has integrity findings that must be fixed before manifest authoring", skill=skill_dict, path=display_manifest_path, approved=approved)
        manifest = _manifest_payload(skill.bundle_sha256)
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        existing_manifest_sha256 = ""
        if manifest_path.is_symlink():
            return _manifest_author_result("blocked", clean_name, "manifest path is a symlink and will not be written", skill=skill_dict, path=display_manifest_path, approved=approved, force=force)
        if manifest_path.exists():
            try:
                existing_bytes = manifest_path.read_bytes()
                existing = existing_bytes.decode("utf-8", errors="replace")
                existing_manifest_sha256 = hashlib.sha256(existing_bytes).hexdigest()
            except OSError:
                existing = ""
            if existing == manifest_text:
                return {
                    **_manifest_author_result("already_current", clean_name, "manifest already matches the current bundle", skill=skill_dict, path=display_manifest_path, approved=approved, force=force),
                    "manifest": manifest,
                    "manifest_sha256": manifest_sha256,
                    "previous_manifest_sha256": existing_manifest_sha256,
                    "manifest_write_performed": False,
                }
        if manifest_path.exists():
            return {
                **_manifest_author_result("blocked", clean_name, "manifest already exists and differs; remove it manually before creating a new checksum manifest", skill=skill_dict, path=display_manifest_path, approved=approved, force=force),
                "manifest": manifest,
                "manifest_sha256": manifest_sha256,
                "previous_manifest_sha256": existing_manifest_sha256,
                "manifest_write_performed": False,
            }
        if not approved:
            return {
                **_manifest_author_result("needs_approval", clean_name, "manifest preview only; rerun with --approved to write it", skill=skill_dict, path=display_manifest_path, approved=approved, force=force),
                "manifest": manifest,
                "manifest_sha256": manifest_sha256,
                "manifest_write_performed": False,
            }
        try:
            fd = os.open(manifest_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(manifest_text)
        except OSError as exc:
            return _manifest_author_result("blocked", clean_name, f"manifest write failed: {exc}", skill=skill_dict, path=display_manifest_path, approved=approved, force=force)
        refreshed = SkillLoader([skill.allowed_root]).discover()
        refreshed_skill = next((item for item in refreshed if item.name == skill.name), skill)
        return {
            **_manifest_author_result("ok", clean_name, "manifest written", skill=refreshed_skill.to_dict(), path=display_manifest_path, approved=approved, force=force),
            "manifest": manifest,
            "manifest_sha256": manifest_sha256,
            "previous_manifest_sha256": existing_manifest_sha256,
            "manifest_write_performed": True,
            "workspace_mutation_performed": True,
            "host_filesystem_mutation_performed": False,
            "external_action_started": False,
            "browser_auto_launch": False,
            "execution_performed": False,
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


def _manifest_payload(bundle_sha256: str) -> dict[str, Any]:
    return {
        "algorithm": "sha256-bundle-v1",
        "bundle_sha256": bundle_sha256,
        "kind": "aegis.skill.trust",
        "schema_version": 1,
    }


def _manifest_author_result(
    status: str,
    skill_name: str,
    message: str,
    *,
    skill: dict[str, Any] | None = None,
    path: str = "",
    approved: bool,
    force: bool = False,
) -> dict[str, Any]:
    skill_data = skill or {}
    trust = skill_data.get("trust", {}) if isinstance(skill_data, dict) else {}
    return {
        "status": status,
        "skill_name": redact_text(skill_name).text,
        "message": redact_text(message).text,
        "path": redact_text(path).text,
        "skill": skill_data,
        "skill_id": skill_data.get("skill_id", "") if isinstance(skill_data, dict) else "",
        "source_scope": skill_data.get("source_scope", "") if isinstance(skill_data, dict) else "",
        "relative_path": skill_data.get("relative_path", "") if isinstance(skill_data, dict) else "",
        "bundle_sha256": trust.get("bundle_sha256", "") if isinstance(trust, dict) else "",
        "previous_manifest_sha256": "",
        "approved": approved,
        "force": force,
        "manifest_write_performed": False,
        "workspace_mutation_performed": False,
        "host_filesystem_mutation_performed": False,
        "external_action_started": False,
        "browser_auto_launch": False,
        "execution_performed": False,
        "raw_secret_values_included": False,
    }


def _valid_skill_selector(selector: str) -> bool:
    if not selector or selector.startswith("/") or "\\" in selector:
        return False
    parts = selector.split(":", 1)
    path_part = parts[1] if len(parts) == 2 else selector
    if len(parts) == 2 and parts[0] not in {"workspace", "user"}:
        return False
    if not path_part or path_part.startswith("/") or path_part in {".", ".."}:
        return False
    return all(part not in {"", ".", ".."} for part in path_part.split("/"))


def _skill_matches_selector(skill: Skill, selector: str) -> bool:
    if ":" in selector:
        scope, relative = selector.split(":", 1)
        return skill.source_scope == scope and skill.relative_path == relative
    return skill.name == selector


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
    manifest_status = "missing"
    signature_status = "missing"
    manifest_path = ""
    manifest_hash = ""
    manifest_details: dict[str, str] = {}
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
            raw_full = skill_file.read_bytes()
            file_size_bytes = len(raw_full)
            skill_hash = hashlib.sha256(raw_full).hexdigest()
            raw = raw_full
            if len(raw_full) > MAX_SKILL_FILE_BYTES:
                raw = raw_full[:MAX_SKILL_FILE_BYTES]
                truncated = True
                extra_findings.append(_path_finding("file.truncated", "oversized_skill", 25, "skill file exceeded scanner byte limit", 0))
            body = raw.decode("utf-8", errors="replace")
            bundle_hash, bundle_findings = _bundle_sha256(path, root)
            extra_findings.extend(bundle_findings)
            manifest_status, signature_status, manifest_path, manifest_hash, manifest_details, manifest_findings = _verify_trust_manifest(path, root, bundle_hash)
            extra_findings.extend(manifest_findings)
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
        manifest_status=manifest_status,
        signature_status=signature_status,
        manifest_path=manifest_path,
        manifest_sha256=manifest_hash,
        declared_bundle_sha256=manifest_details.get("declared_bundle_sha256", ""),
        signature_algorithm=manifest_details.get("signature_algorithm", ""),
        issuer_key_id=manifest_details.get("issuer_key_id", ""),
        issuer_public_key_sha256=manifest_details.get("issuer_public_key_sha256", ""),
        truncated=truncated,
        symlink_detected=symlink_detected,
        inside_allowed_root=inside_allowed_root,
        readable=readable,
    )


def _bundle_sha256(path: Path, root: Path) -> tuple[str, list[dict[str, Any]]]:
    digest = hashlib.sha256()
    findings: list[dict[str, Any]] = []
    ignored_dirs = {".git", "__pycache__", ".venv", "node_modules"}
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        current_path = Path(current)
        next_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            dir_path = current_path / dirname
            if dir_path.is_symlink():
                findings.append(_path_finding("bundle.symlink_dir", "bundle_integrity", 50, "skill bundle contains a symlinked directory that was not hashed", 0))
                continue
            if dirname in ignored_dirs:
                findings.append(_path_finding("bundle.ignored_dir", "bundle_integrity", 25, "skill bundle contains an ignored generated directory that was not hashed", 0))
                continue
            next_dirnames.append(dirname)
        dirnames[:] = next_dirnames
        for filename in sorted(filenames):
            file_path = current_path / filename
            if file_path.name == SKILL_TRUST_MANIFEST or file_path.name.endswith(".sig"):
                continue
            if file_path.is_symlink():
                findings.append(_path_finding("bundle.symlink_file", "bundle_integrity", 50, "skill bundle contains a symlinked file that was not hashed", 0))
                continue
            try:
                relative = file_path.relative_to(root).as_posix()
                data = file_path.read_bytes()
            except (OSError, ValueError):
                findings.append(_path_finding("bundle.unreadable_file", "bundle_integrity", 50, "skill bundle contains an unreadable file that was not hashed", 0))
                continue
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(data).hexdigest().encode("ascii"))
            digest.update(b"\n")
    return digest.hexdigest(), findings


def _verify_trust_manifest(path: Path, root: Path, bundle_hash: str) -> tuple[str, str, str, str, dict[str, str], list[dict[str, Any]]]:
    manifest_path = path / SKILL_TRUST_MANIFEST
    relative = _relative_path(manifest_path, root)
    if manifest_path.is_symlink():
        return "invalid", "missing", relative, "", {}, [_path_finding("manifest.symlink", "path_escape", 50, "skill trust manifest is symlinked", 0)]
    if not manifest_path.exists():
        return "missing", "missing", "", "", {}, []
    try:
        manifest_path.resolve(strict=False).relative_to(root)
    except ValueError:
        return "invalid", "missing", relative, "", {}, [_path_finding("manifest.outside_root", "path_escape", 50, "skill trust manifest resolves outside the allowed root", 0)]
    try:
        raw_bytes = manifest_path.read_bytes()
        manifest_hash = hashlib.sha256(raw_bytes).hexdigest()
        raw = raw_bytes.decode("utf-8")
        manifest = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "invalid", "missing", relative, "", {}, [_path_finding("manifest.invalid_json", "manifest_integrity", 35, "skill trust manifest is not valid JSON", 0)]
    if not isinstance(manifest, dict):
        return "invalid", "missing", relative, manifest_hash, {}, [_path_finding("manifest.invalid_shape", "manifest_integrity", 35, "skill trust manifest must be a JSON object", 0)]
    algorithm = str(manifest.get("algorithm") or "")
    declared = str(manifest.get("bundle_sha256") or "")
    signature = manifest.get("signature")
    issuer = manifest.get("issuer")
    signature_algorithm = _signature_algorithm(signature)
    issuer_key_id = _issuer_key_id(issuer)
    issuer_public_key_sha256 = _issuer_public_key_sha256(issuer)
    details = {
        "declared_bundle_sha256": declared if _is_sha256(declared) else "",
        "signature_algorithm": signature_algorithm,
        "issuer_key_id": issuer_key_id,
        "issuer_public_key_sha256": issuer_public_key_sha256,
    }
    findings: list[dict[str, Any]] = []
    signature_status = "declared_unverified" if signature_algorithm else "missing"
    if manifest.get("schema_version") not in {None, 1}:
        findings.append(_path_finding("manifest.unsupported_schema", "manifest_integrity", 35, "skill trust manifest schema version is unsupported", 0))
    if manifest.get("kind") not in {None, "aegis.skill.trust"}:
        findings.append(_path_finding("manifest.unsupported_kind", "manifest_integrity", 35, "skill trust manifest kind is unsupported", 0))
    if algorithm != "sha256-bundle-v1":
        findings.append(_path_finding("manifest.unsupported_algorithm", "manifest_integrity", 35, "skill trust manifest algorithm is unsupported", 0))
    if not _is_sha256(declared):
        findings.append(_path_finding("manifest.invalid_bundle_sha256", "manifest_integrity", 35, "skill trust manifest bundle_sha256 must be a SHA-256 hex digest", 0))
    elif declared != bundle_hash:
        findings.append(_path_finding("manifest.bundle_mismatch", "manifest_integrity", 45, "skill trust manifest bundle hash does not match scanned files", 0))
    signature_present = signature is not None and signature != ""
    if signature_present and signature_algorithm != "ed25519":
        signature_status = "invalid"
        findings.append(_path_finding("manifest.unsupported_signature", "manifest_integrity", 25, "skill trust manifest signature algorithm is unsupported", 0))
    elif signature_algorithm == "ed25519":
        findings.append(_path_finding("manifest.signature_unverified", "manifest_integrity", 25, "skill trust manifest signature is declared but not cryptographically verified", 0))
    blocking_findings = [finding for finding in findings if finding["rule_id"] != "manifest.signature_unverified"]
    if blocking_findings:
        return "mismatch" if any(finding["rule_id"] == "manifest.bundle_mismatch" for finding in blocking_findings) else "invalid", signature_status, relative, manifest_hash, details, findings
    if signature_algorithm:
        return "checksum_valid_signature_unverified", signature_status, relative, manifest_hash, details, findings
    return "checksum_valid", "missing", relative, manifest_hash, details, []


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


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _signature_algorithm(signature: Any) -> str:
    if isinstance(signature, dict):
        return redact_text(str(signature.get("algorithm") or "")).text.lower()
    if isinstance(signature, str) and signature.strip():
        return "unknown"
    return ""


def _issuer_key_id(issuer: Any) -> str:
    if not isinstance(issuer, dict):
        return ""
    return redact_text(str(issuer.get("key_id") or "")).text


def _issuer_public_key_sha256(issuer: Any) -> str:
    if not isinstance(issuer, dict):
        return ""
    value = str(issuer.get("public_key_sha256") or "")
    return value.lower() if _is_sha256(value) else ""


def _source_scope(root: Path) -> str:
    home = Path.home()
    try:
        root.resolve().relative_to(home / ".aegisagent")
        return "user"
    except ValueError:
        return "workspace"
