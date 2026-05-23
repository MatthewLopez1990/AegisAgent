from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxStatus:
    backend: str
    available: bool
    host_execution_requires_approval: bool = True
    rationale: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def detect_sandbox() -> SandboxStatus:
    if shutil.which("docker"):
        return SandboxStatus("docker", True, rationale="docker available for isolated execution")
    return SandboxStatus("host-gated", False, rationale="docker unavailable; host execution remains approval-gated")
