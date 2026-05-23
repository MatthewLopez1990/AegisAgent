from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

RISKY_SKILL_MARKERS = ("curl ", "wget ", "rm -rf", "sudo ", "chmod 777", "keychain dump")


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    description: str
    quarantined: bool
    findings: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "quarantined": self.quarantined,
            "findings": list(self.findings),
        }


class SkillLoader:
    def __init__(self, roots: list[Path]):
        self.roots = roots

    def discover(self) -> list[Skill]:
        skills: list[Skill] = []
        for root in self.roots:
            if not root.exists():
                continue
            for skill_file in sorted(root.glob("**/SKILL.md")):
                body = skill_file.read_text(encoding="utf-8", errors="replace")
                name = skill_file.parent.name
                description = _extract_description(body)
                findings = tuple(marker for marker in RISKY_SKILL_MARKERS if marker in body)
                skills.append(Skill(name, skill_file.parent, description, bool(findings), findings))
        return skills


def _extract_description(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    for line in body.splitlines():
        if line.strip() and not line.startswith("---") and not line.startswith("name:"):
            return line.strip("# ").strip()
    return "No description supplied."
