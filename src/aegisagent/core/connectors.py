from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any
from urllib.parse import urlparse
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
    delivery_status_code: int | None = None
    delivered_at: str = ""
    destination_fingerprint: str = ""
    payload_sha256: str = ""

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
            "delivery_status_code": self.delivery_status_code,
            "delivered_at": self.delivered_at,
            "destination_fingerprint": self.destination_fingerprint,
            "payload_sha256": self.payload_sha256,
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
        if token_env:
            _validate_env_handle(token_env, "token_env")
        if url_env:
            _validate_env_handle(url_env, "url_env")
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
            "delivered_count": sum(1 for envelope in outbox if envelope["status"] == "delivered"),
            "live_delivery_connectors": ["webhook"],
            "external_action_started": False,
            "external_delivery_performed": False,
            "browser_auto_launch": False,
            "next": f"Use `{command} connectors configure webhook --url-env AEGIS_WEBHOOK_URL --enable`, then approve each webhook send explicitly.",
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
        if route.name == "webhook" and _connector_ready(route):
            try:
                envelope = _with_webhook_metadata(os.environ.get(route.url_env, "") if route.url_env else "", envelope)
            except ValueError as exc:
                blocked = ConnectorEnvelope(**{**envelope.to_dict(), "status": "blocked", "reason": str(exc)})
                receipt = self.audit.append(
                    "connector.delivery.blocked",
                    {
                        **_audit_envelope(blocked),
                        "reason": str(exc),
                        "external_action_started": False,
                        "external_delivery_performed": False,
                        "browser_auto_launch": False,
                        "raw_secret_values_included": False,
                        "url_included": False,
                    },
                )
                return {"status": "blocked", "reason": str(exc), "envelope": {**blocked.to_dict(), "receipt": receipt["id"]}, "receipt": receipt["id"]}
        if not approved:
            receipt = self.audit.append(
                "connector.delivery.needs_approval",
                {
                    **_audit_envelope(envelope),
                    "external_action_started": False,
                    "external_delivery_performed": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                    "url_included": False,
                },
            )
            return {"status": "needs_approval", "envelope": {**envelope.to_dict(), "receipt": receipt["id"]}, "receipt": receipt["id"]}
        if not _connector_ready(route):
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
        if route.name == "webhook":
            return self._send_webhook(route, envelope)
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
            delivery_ready=_connector_ready(route),
        )

    def _send_webhook(self, route: ConnectorRoute, envelope: ConnectorEnvelope) -> dict[str, Any]:
        webhook_url = os.environ.get(route.url_env, "") if route.url_env else ""
        try:
            response = _post_webhook(webhook_url, envelope)
        except ValueError as exc:
            blocked = ConnectorEnvelope(**{**envelope.to_dict(), "status": "blocked", "approved": True, "delivery_ready": True, "reason": str(exc)})
            receipt = self.audit.append(
                "connector.delivery.blocked",
                {
                    **_audit_envelope(blocked),
                    "reason": str(exc),
                    "external_action_started": False,
                    "external_delivery_performed": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                    "url_included": False,
                },
            )
            return {"status": "blocked", "reason": str(exc), "envelope": {**blocked.to_dict(), "receipt": receipt["id"]}, "receipt": receipt["id"]}
        except (OSError, HTTPException) as exc:
            reason = _safe_error(exc)
            failed = ConnectorEnvelope(
                **{
                    **envelope.to_dict(),
                    "status": "delivery_failed",
                    "approved": True,
                    "delivery_ready": True,
                    "reason": reason,
                }
            )
            receipt = self.audit.append(
                "connector.delivery.failed",
                {
                    **_audit_envelope(failed),
                    "reason": reason,
                    "external_action_started": True,
                    "external_delivery_performed": False,
                    "browser_auto_launch": False,
                    "raw_secret_values_included": False,
                    "url_included": False,
                },
            )
            failed = ConnectorEnvelope(**{**failed.to_dict(), "receipt": receipt["id"]})
            self._append_outbox(failed)
            return {"status": "delivery_failed", "reason": reason, "envelope": failed.to_dict(), "receipt": receipt["id"]}

        status = "delivered" if 200 <= response["status_code"] < 300 else "delivery_failed"
        reason = "" if status == "delivered" else f"webhook returned HTTP {response['status_code']}"
        delivered = ConnectorEnvelope(
            **{
                **envelope.to_dict(),
                "status": status,
                "approved": True,
                "delivery_ready": True,
                "external_delivery_performed": status == "delivered",
                "reason": reason,
                "delivery_status_code": response["status_code"],
                "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if status == "delivered" else "",
            }
        )
        receipt = self.audit.append(
            "connector.delivery.sent" if status == "delivered" else "connector.delivery.failed",
            {
                **_audit_envelope(delivered),
                "delivery_status_code": response["status_code"],
                "reason": reason,
                "external_action_started": True,
                "external_delivery_performed": status == "delivered",
                "browser_auto_launch": False,
                "raw_secret_values_included": False,
                "url_included": False,
                "redirects_followed": False,
            },
        )
        delivered = ConnectorEnvelope(**{**delivered.to_dict(), "receipt": receipt["id"]})
        self._append_outbox(delivered)
        return {"status": status, "envelope": delivered.to_dict(), "receipt": receipt["id"], "delivery_status_code": response["status_code"]}

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
    if missing:
        return "enabled_missing_handles"
    if name == "webhook":
        return "enabled_ready_webhook_delivery"
    return "enabled_ready_metadata_only"


def _connector_ready(route: ConnectorRoute) -> bool:
    return route.status in {"enabled_ready_metadata_only", "enabled_ready_webhook_delivery"}


def _validate_env_handle(value: str, field: str) -> None:
    if "://" in value or "/" in value or "?" in value or "#" in value:
        raise ValueError(f"{field} must be an environment variable name, not a raw URL or secret")
    if not value.replace("_", "A").isalnum() or value[0].isdigit():
        raise ValueError(f"{field} must be an environment variable name")


def _audit_envelope(envelope: ConnectorEnvelope) -> dict[str, Any]:
    payload = {
        "id": envelope.id,
        "connector": envelope.connector,
        "target": envelope.target,
        "status": envelope.status,
        "requires_approval": envelope.requires_approval,
        "approved": envelope.approved,
        "delivery_ready": envelope.delivery_ready,
        "source": envelope.source,
    }
    if envelope.destination_fingerprint:
        payload["destination_fingerprint"] = envelope.destination_fingerprint
    if envelope.payload_sha256:
        payload["payload_sha256"] = envelope.payload_sha256
    if envelope.delivery_status_code is not None:
        payload["delivery_status_code"] = envelope.delivery_status_code
    return payload


def _with_webhook_metadata(webhook_url: str, envelope: ConnectorEnvelope) -> ConnectorEnvelope:
    parsed = urlparse(webhook_url)
    _validate_webhook_destination(parsed)
    canonical = _canonical_webhook_destination(parsed)
    payload_sha = hashlib.sha256(json.dumps({"connector": envelope.connector, "target": envelope.target, "message": envelope.message}, sort_keys=True).encode("utf-8")).hexdigest()
    return ConnectorEnvelope(
        **{
            **envelope.to_dict(),
            "destination_fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "payload_sha256": payload_sha,
        }
    )


def _post_webhook(webhook_url: str, envelope: ConnectorEnvelope) -> dict[str, Any]:
    parsed = urlparse(webhook_url)
    _validate_webhook_destination(parsed)
    if not envelope.destination_fingerprint or not envelope.payload_sha256:
        envelope = _with_webhook_metadata(webhook_url, envelope)
    expected_fingerprint = hashlib.sha256(_canonical_webhook_destination(parsed).encode("utf-8")).hexdigest()
    if envelope.destination_fingerprint != expected_fingerprint:
        raise ValueError("webhook destination fingerprint changed after approval")
    expected_payload = hashlib.sha256(json.dumps({"connector": envelope.connector, "target": envelope.target, "message": envelope.message}, sort_keys=True).encode("utf-8")).hexdigest()
    if envelope.payload_sha256 != expected_payload:
        raise ValueError("webhook payload hash changed after approval")
    body = json.dumps(
        {
            "id": envelope.id,
            "connector": envelope.connector,
            "target": envelope.target,
            "message": envelope.message,
            "source": envelope.source,
            "created_at": envelope.created_at,
        }
    ).encode("utf-8")
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    connection_cls = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
    port = parsed.port
    connection = connection_cls(parsed.hostname, port=port, timeout=5)
    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AegisAgent-Connector/1.0",
            },
        )
        response = connection.getresponse()
        response.read(2048)
        return {"status_code": int(response.status)}
    finally:
        connection.close()


def _validate_webhook_destination(parsed) -> None:
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("webhook URL handle must use http or https")
    if parsed.scheme == "http" and not _dev_insecure_webhook_allowed():
        raise ValueError("webhook URL handle must use https unless AEGIS_WEBHOOK_ALLOW_INSECURE_LOCAL=1")
    if not parsed.hostname:
        raise ValueError("webhook URL handle must include a host")
    if parsed.username or parsed.password:
        raise ValueError("webhook URL handle must not include credentials")
    if parsed.fragment:
        raise ValueError("webhook URL handle must not include fragments")
    _validate_public_webhook_host(parsed.hostname, parsed.port)


def _validate_public_webhook_host(hostname: str, port: int | None) -> None:
    allow_local = _dev_insecure_webhook_allowed()
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("webhook URL host could not be resolved") from exc
        addresses = []
        for info in infos:
            address = info[4][0]
            try:
                addresses.append(ipaddress.ip_address(address))
            except ValueError:
                continue
    if not addresses:
        raise ValueError("webhook URL host could not be resolved")
    for address in addresses:
        if _is_restricted_address(address) and not allow_local:
            raise ValueError("webhook URL host resolves to a restricted network")


def _is_restricted_address(address: ipaddress._BaseAddress) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _canonical_webhook_destination(parsed) -> str:
    host = (parsed.hostname or "").lower()
    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    port_text = "" if not port or port == default_port else f":{port}"
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{host}{port_text}{path}{query}"


def _dev_insecure_webhook_allowed() -> bool:
    return os.environ.get("AEGIS_WEBHOOK_ALLOW_INSECURE_LOCAL") == "1"


def _safe_error(exc: BaseException) -> str:
    redacted = redact_mapping({"error": str(exc)})[0]["error"]
    if len(redacted) > 180:
        redacted = redacted[:177] + "..."
    return redacted or exc.__class__.__name__
