from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aegisagent.config import DEFAULT_CONFIG, RuntimePaths, ensure_runtime
from aegisagent.core.command_names import terminal_command_name
from aegisagent.security.audit import AuditLog
from aegisagent.security.redaction import redact_mapping


DEFAULT_CONNECTORS: dict[str, dict[str, Any]] = {
    "slack": {
        "kind": "messaging",
        "status": "not_configured",
        "token_env": "SLACK_BOT_TOKEN",
        "approval": "ask_send",
        "description": "Slack app or bot delivery adapter.",
    },
    "teams": {
        "kind": "messaging",
        "status": "not_configured",
        "token_env": "TEAMS_BOT_TOKEN",
        "approval": "ask_send",
        "description": "Microsoft Teams delivery adapter.",
    },
    "webhook": {
        "kind": "webhook",
        "status": "not_configured",
        "url_env": "AEGIS_WEBHOOK_URL",
        "approval": "ask_send",
        "description": "Outbound webhook delivery adapter.",
    },
    "mcp": {
        "kind": "external_tools",
        "status": "not_configured",
        "approval": "ask_connect",
        "description": "MCP server registry and tool adapter.",
    },
    "browser": {
        "kind": "local_browser",
        "status": "available_local_only",
        "approval": "manual_open",
        "description": "Local browser smoke and optional GUI surface. Never auto-launched by setup.",
    },
    "openwebui": {
        "kind": "messaging",
        "status": "not_configured",
        "url_env": "OPENWEBUI_BASE_URL",
        "approval": "ask_send",
        "description": "Open WebUI-style channel adapter.",
    },
}


@dataclass(frozen=True, slots=True)
class ConnectorRoute:
    name: str
    kind: str
    status: str
    enabled: bool
    approval: str
    description: str
    token_env: str = ""
    url_env: str = ""
    external_delivery_performed: bool = False
    browser_auto_launch: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "enabled": self.enabled,
            "approval": self.approval,
            "description": self.description,
            "token_env": self.token_env,
            "url_env": self.url_env,
            "external_delivery_performed": self.external_delivery_performed,
            "browser_auto_launch": self.browser_auto_launch,
        }


@dataclass(frozen=True, slots=True)
class ConnectorEnvelope:
    id: str
    connector: str
    target: str
    message: str
    status: str
    created_at: str
    source: str
    requires_approval: bool = True
    approved: bool = False
    delivery_ready: bool = False
    external_delivery_performed: bool = False
    browser_auto_launch: bool = False
    raw_secret_values_included: bool = False
    receipt: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "connector": self.connector,
            "target": self.target,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at,
            "source": self.source,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "delivery_ready": self.delivery_ready,
            "external_delivery_performed": self.external_delivery_performed,
            "browser_auto_launch": self.browser_auto_launch,
            "raw_secret_values_included": self.raw_secret_values_included,
            "receipt": self.receipt,
            "reason": self.reason,
        }


class ConnectorStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self.audit = AuditLog(paths)

    @property
    def config_path(self):
        return self.paths.state_dir / "config.json"

    @property
    def outbox_path(self):
        return self.paths.state_dir / "connector_outbox.jsonl"

    def configure(
        self,
        name: str,
        *,
        token_env: str = "",
        url_env: str = "",
        enabled: bool = False,
        source: str = "cli",
    ) -> dict[str, Any]:
        if name not in DEFAULT_CONNECTORS:
            raise KeyError(f"unknown connector: {name}")
        config = self._load_config()
        connectors = config.setdefault("connectors", {})
        routes = connectors.setdefault("routes", {})
        base = dict(DEFAULT_CONNECTORS[name])
        existing = dict(routes.get(name, {}))
        existing.update(
            {
                "name": name,
                "kind": base["kind"],
                "enabled": enabled,
                "token_env": token_env or existing.get("token_env") or base.get("token_env", ""),
                "url_env": url_env or existing.get("url_env") or base.get("url_env", ""),
                "approval": base["approval"],
                "description": base["description"],
                "browser_auto_launch": False,
            }
        )
        routes[name] = existing
        self._save_config(config)
        route = self.route(name)
        receipt = self.audit.append(
            "connector.configured",
            {
                "name": name,
                "enabled": enabled,
                "token_env": route.token_env,
                "url_env": route.url_env,
                "approval": route.approval,
                "source": source,
                "external_action_started": False,
                "external_delivery_performed": False,
                "raw_secret_values_included": False,
                "browser_auto_launch": False,
            },
        )
        return {"connector": route.to_dict(), "receipt": receipt["id"]}

    def route(self, name: str) -> ConnectorRoute:
        route = self._routes().get(name)
        if not route:
            raise KeyError(f"connector not found: {name}")
        return route

    def routes(self) -> list[ConnectorRoute]:
        return list(self._routes().values())

    def summary(self) -> dict[str, Any]:
        routes = [route.to_dict() for route in self.routes()]
        command = terminal_command_name()
        outbox = self.outbox(limit=1000)
        return {
            "connectors": routes,
            "enabled_count": sum(1 for route in routes if route["enabled"]),
            "outbox_count": len(outbox),
            "approved_pending_adapter_count": sum(1 for envelope in outbox if envelope["status"] == "approved_pending_adapter"),
            "external_action_started": False,
            "external_delivery_performed": False,
            "browser_auto_launch": False,
            "next": f"Use `{command} connectors draft slack --target '#ops' --message 'status'`, then approve a send only when the adapter is configured.",
        }

    def doctor(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for route in self.routes():
            ok = True
            detail = "Connector disabled; no external action can start."
            if route.enabled:
                env_names = [name for name in (route.token_env, route.url_env) if name]
                missing = [name for name in env_names if not os.environ.get(name)]
                ok = not missing
                detail = "Configured handles are present." if ok else f"Missing handle environment variables: {', '.join(missing)}"
            checks.append({"name": route.name, "ok": ok, "status": route.status, "detail": detail})
        receipt = self.audit.append(
            "connector.doctor",
            {
                "checks": [{"name": check["name"], "ok": check["ok"]} for check in checks],
                "external_action_started": False,
                "external_delivery_performed": False,
                "raw_secret_values_included": False,
                "browser_auto_launch": False,
            },
        )
        return {
            "checks": checks,
            "connectors": [route.to_dict() for route in self.routes()],
            "external_action_started": False,
            "external_delivery_performed": False,
            "browser_auto_launch": False,
            "receipt": receipt["id"],
        }

    def draft(self, name: str, *, target: str, message: str, source: str = "cli") -> dict[str, Any]:
        route = self._messaging_route(name)
        envelope = self._envelope(route, target=target, message=message, status="drafted", source=source)
        receipt = self.audit.append(
            "connector.delivery.drafted",
            {
                **_audit_envelope(envelope),
                "external_action_started": False,
                "external_delivery_performed": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        envelope = ConnectorEnvelope(**{**envelope.to_dict(), "receipt": receipt["id"]})
        self._append_outbox(envelope)
        return {"status": "drafted", "envelope": envelope.to_dict(), "receipt": receipt["id"]}

    def send(self, name: str, *, target: str, message: str, approved: bool = False, source: str = "cli") -> dict[str, Any]:
        route = self._messaging_route(name)
        envelope = self._envelope(route, target=target, message=message, status="needs_approval", source=source)
        if not approved:
            receipt = self.audit.append(
                "connector.delivery.needs_approval",
                {
                    **_audit_envelope(envelope),
                    "external_action_started": False,
                    "external_delivery_performed": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "needs_approval", "envelope": {**envelope.to_dict(), "receipt": receipt["id"]}, "receipt": receipt["id"]}
        if route.status != "enabled_ready_metadata_only":
            reason = f"connector {name} is {route.status}; configure required handles before approval can be recorded"
            blocked = ConnectorEnvelope(**{**envelope.to_dict(), "status": "blocked", "approved": False, "reason": reason})
            receipt = self.audit.append(
                "connector.delivery.blocked",
                {
                    **_audit_envelope(blocked),
                    "reason": reason,
                    "external_action_started": False,
                    "external_delivery_performed": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                },
            )
            return {"status": "blocked", "reason": reason, "envelope": {**blocked.to_dict(), "receipt": receipt["id"]}, "receipt": receipt["id"]}
        approved_envelope = ConnectorEnvelope(
            **{
                **envelope.to_dict(),
                "status": "approved_pending_adapter",
                "approved": True,
                "delivery_ready": True,
                "reason": "Outbound adapter is not implemented yet; approval packet is recorded for future delivery wiring.",
            }
        )
        receipt = self.audit.append(
            "connector.delivery.approved_pending_adapter",
            {
                **_audit_envelope(approved_envelope),
                "external_action_started": False,
                "external_delivery_performed": False,
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
            },
        )
        approved_envelope = ConnectorEnvelope(**{**approved_envelope.to_dict(), "receipt": receipt["id"]})
        self._append_outbox(approved_envelope)
        return {"status": "approved_pending_adapter", "envelope": approved_envelope.to_dict(), "receipt": receipt["id"]}

    def outbox(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.outbox_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.outbox_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows[-limit:]

    def _messaging_route(self, name: str) -> ConnectorRoute:
        route = self.route(name)
        if route.kind not in {"messaging", "webhook"}:
            raise ValueError(f"connector {name} does not support outbound messaging packets")
        return route

    def _envelope(self, route: ConnectorRoute, *, target: str, message: str, status: str, source: str) -> ConnectorEnvelope:
        clean, _redacted = redact_mapping({"target": target.strip(), "message": message.strip()})
        if not clean["target"]:
            raise ValueError("connector message target is required")
        if not clean["message"]:
            raise ValueError("connector message body is required")
        return ConnectorEnvelope(
            id=f"conn-{uuid4().hex[:12]}",
            connector=route.name,
            target=clean["target"],
            message=clean["message"],
            status=status,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source=source,
            delivery_ready=route.status == "enabled_ready_metadata_only",
        )

    def _append_outbox(self, envelope: ConnectorEnvelope) -> None:
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope.to_dict(), sort_keys=True) + "\n")

    def _routes(self) -> dict[str, ConnectorRoute]:
        config = self._load_config()
        routes = dict(config.setdefault("connectors", {}).setdefault("routes", {}))
        for name, payload in DEFAULT_CONNECTORS.items():
            routes.setdefault(name, {"name": name, **payload, "enabled": False})
        result: dict[str, ConnectorRoute] = {}
        for name, payload in routes.items():
            item = payload if isinstance(payload, dict) else {}
            base = DEFAULT_CONNECTORS.get(name, {})
            enabled = bool(item.get("enabled", False))
            token_env = str(item.get("token_env") or base.get("token_env", ""))
            url_env = str(item.get("url_env") or base.get("url_env", ""))
            result[name] = ConnectorRoute(
                name=name,
                kind=str(item.get("kind") or base.get("kind") or "connector"),
                status=_connector_status(name, enabled, token_env, url_env),
                enabled=enabled,
                approval=str(item.get("approval") or base.get("approval") or "ask"),
                description=str(item.get("description") or base.get("description") or ""),
                token_env=token_env,
                url_env=url_env,
                browser_auto_launch=bool(item.get("browser_auto_launch", False)),
            )
        return result

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return json.loads(json.dumps(DEFAULT_CONFIG))
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = json.loads(json.dumps(DEFAULT_CONFIG))
        if not isinstance(data, dict):
            data = json.loads(json.dumps(DEFAULT_CONFIG))
        data.setdefault("connectors", {}).setdefault("routes", {})
        return data

    def _save_config(self, config: dict[str, Any]) -> None:
        self.config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _connector_status(name: str, enabled: bool, token_env: str, url_env: str) -> str:
    if name == "browser" and not enabled:
        return "available_local_only"
    if not enabled:
        return "not_configured"
    missing = [env_name for env_name in (token_env, url_env) if env_name and not os.environ.get(env_name)]
    return "enabled_missing_handles" if missing else "enabled_ready_metadata_only"


def _audit_envelope(envelope: ConnectorEnvelope) -> dict[str, Any]:
    return {
        "id": envelope.id,
        "connector": envelope.connector,
        "target": envelope.target,
        "status": envelope.status,
        "requires_approval": envelope.requires_approval,
        "approved": envelope.approved,
        "delivery_ready": envelope.delivery_ready,
        "source": envelope.source,
    }
