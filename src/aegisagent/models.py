from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

DecisionAction = Literal["allow", "ask", "deny"]
RiskLevel = Literal["low", "medium", "high", "critical"]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class PolicyDecision:
    action: DecisionAction
    risk: RiskLevel
    rationale: str
    receipt_id: str
    tool: str
    scope: str = "workspace"
    redacted: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "risk": self.risk,
            "rationale": self.rationale,
            "receipt_id": self.receipt_id,
            "tool": self.tool,
            "scope": self.scope,
            "redacted": self.redacted,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class AuditReceipt:
    event_type: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "event_type": self.event_type,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    group: str
    status: str
    scope: str
    approval: str
    risk: RiskLevel
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "group": self.group,
            "status": self.status,
            "scope": self.scope,
            "approval": self.approval,
            "risk": self.risk,
            "description": self.description,
        }
