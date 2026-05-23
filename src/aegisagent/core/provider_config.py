from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from aegisagent.config import DEFAULT_CONFIG, RuntimePaths, ensure_runtime
from aegisagent.security.audit import AuditLog


LOCAL_PROVIDER = "local/terminal-v0"


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    name: str
    mode: str
    status: str
    api_key_env: str = ""
    base_url: str = ""
    browser_required: bool = False
    external_model_invocation_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "status": self.status,
            "api_key_env": self.api_key_env,
            "base_url": self.base_url,
            "browser_required": self.browser_required,
            "external_model_invocation_performed": self.external_model_invocation_performed,
        }


class ProviderStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self.audit = AuditLog(paths)

    @property
    def config_path(self):
        return self.paths.state_dir / "config.json"

    def configure(
        self,
        name: str,
        *,
        mode: str,
        api_key_env: str = "",
        base_url: str = "",
        active: bool = True,
        source: str = "cli",
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("provider name is required")
        if mode not in {"local", "api_key", "subscription_cli", "not_configured"}:
            raise ValueError(f"unsupported provider mode: {mode}")
        config = self._load_config()
        providers = config.setdefault("providers", {})
        routes = providers.setdefault("routes", {})
        routes[name] = {
            "name": name,
            "mode": mode,
            "api_key_env": api_key_env,
            "base_url": base_url,
            "browser_required": False,
        }
        if active:
            providers["active"] = name
            providers["default"] = name
        self._save_config(config)
        receipt = self.audit.append(
            "provider.configured",
            {
                "name": name,
                "mode": mode,
                "api_key_env": api_key_env,
                "base_url_configured": bool(base_url),
                "active": active,
                "source": source,
                "external_action_started": False,
                "model_invocation_performed": False,
                "raw_secret_values_included": False,
            },
        )
        return {"route": self.route(name).to_dict(), "active_provider": self.active_provider(), "receipt": receipt["id"]}

    def active_provider(self) -> str:
        config = self._load_config()
        providers = config.get("providers", {})
        return str(providers.get("active") or providers.get("default") or LOCAL_PROVIDER)

    def route(self, name: str) -> ProviderRoute:
        route = self._routes().get(name)
        if not route:
            raise KeyError(f"provider route not found: {name}")
        return route

    def routes(self) -> list[ProviderRoute]:
        return list(self._routes().values())

    def summary(self) -> dict[str, Any]:
        routes = [route.to_dict() for route in self.routes()]
        return {
            "active_provider": self.active_provider(),
            "mode": self.route(self.active_provider()).mode if self.active_provider() in {route["name"] for route in routes} else "unknown",
            "routes": routes,
            "browser_required": False,
            "external_action_started": False,
            "model_invocation_performed": False,
            "next": "Use `aegisagent model configure <name> --mode api_key --api-key-env OPENAI_API_KEY` or keep `local/terminal-v0` active.",
        }

    def doctor(self) -> dict[str, Any]:
        route = self.route(self.active_provider())
        checks = [
            {
                "name": "metadata_only",
                "ok": True,
                "detail": "Doctor checks read local config and environment names only; no model call or browser launch is performed.",
            },
            {"name": "browser_not_required", "ok": not route.browser_required, "detail": "Terminal activation remains primary."},
        ]
        if route.mode == "local":
            checks.append({"name": "local_provider", "ok": True, "detail": "Built-in local terminal provider is ready."})
        elif route.mode == "api_key":
            checks.append(
                {
                    "name": "api_key_env",
                    "ok": bool(route.api_key_env and os.environ.get(route.api_key_env)),
                    "detail": f"{route.api_key_env or 'api key env'} {'is present' if route.api_key_env and os.environ.get(route.api_key_env) else 'is not present'}; no secret value was read.",
                }
            )
        elif route.mode == "subscription_cli":
            checks.append({"name": "subscription_bridge", "ok": True, "detail": "Route is configured as a local subscription CLI bridge; execution is not wired yet."})
        else:
            checks.append({"name": "provider_configured", "ok": False, "detail": "No external provider route has been configured."})
        receipt = self.audit.append(
            "provider.doctor",
            {
                "active_provider": route.name,
                "mode": route.mode,
                "checks": [{"name": check["name"], "ok": check["ok"]} for check in checks],
                "external_action_started": False,
                "model_invocation_performed": False,
                "raw_secret_values_included": False,
            },
        )
        return {"active_provider": route.name, "route": route.to_dict(), "checks": checks, "receipt": receipt["id"]}

    def _routes(self) -> dict[str, ProviderRoute]:
        config = self._load_config()
        providers = config.setdefault("providers", {})
        raw_routes = dict(providers.setdefault("routes", {}))
        raw_routes.setdefault(LOCAL_PROVIDER, {"name": LOCAL_PROVIDER, "mode": "local"})
        legacy_default = str(providers.get("default") or "")
        legacy_mode = str(providers.get("mode") or "")
        if legacy_default and legacy_default != LOCAL_PROVIDER and legacy_default not in raw_routes:
            raw_routes[legacy_default] = {"name": legacy_default, "mode": legacy_mode or "not_configured"}
        routes: dict[str, ProviderRoute] = {}
        for name, payload in raw_routes.items():
            item = payload if isinstance(payload, dict) else {}
            mode = str(item.get("mode") or "not_configured")
            api_key_env = str(item.get("api_key_env") or "")
            routes[name] = ProviderRoute(
                name=name,
                mode=mode,
                status=_route_status(mode, api_key_env),
                api_key_env=api_key_env,
                base_url=str(item.get("base_url") or ""),
                browser_required=bool(item.get("browser_required", False)),
            )
        return routes

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return json.loads(json.dumps(DEFAULT_CONFIG))
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = json.loads(json.dumps(DEFAULT_CONFIG))
        if not isinstance(data, dict):
            data = json.loads(json.dumps(DEFAULT_CONFIG))
        providers = data.setdefault("providers", {})
        providers.setdefault("active", LOCAL_PROVIDER)
        providers.setdefault("default", providers["active"])
        providers.setdefault("routes", {})
        return data

    def _save_config(self, config: dict[str, Any]) -> None:
        self.config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _route_status(mode: str, api_key_env: str) -> str:
    if mode == "local":
        return "active"
    if mode == "api_key":
        return "env_present_unverified" if api_key_env and os.environ.get(api_key_env) else "env_missing"
    if mode == "subscription_cli":
        return "configured_metadata_only"
    return "not_configured"


class ProviderUsageStore:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        ensure_runtime(paths)
        self.usage_dir = self.paths.state_dir / "providers"
        self.usage_path = self.usage_dir / "usage.jsonl"

    def record(
        self,
        *,
        provider: str,
        mode: str,
        status: str,
        session_id: str,
        source: str,
        prompt_chars: int,
        assistant_chars: int,
        external_model_invocation_performed: bool,
        provider_route_status: str = "",
        primary_provider: str = "",
        fallback_used: bool = False,
        fallback_provider: str = "",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        receipt_id: str = "",
        redacted: bool = False,
    ) -> dict[str, Any]:
        self.usage_dir.mkdir(parents=True, exist_ok=True)
        prompt_estimate = _estimate_tokens(prompt_chars)
        completion_estimate = _estimate_tokens(assistant_chars)
        payload = {
            "id": f"usage-{uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "mode": mode,
            "status": status,
            "session_id": session_id,
            "source": source,
            "prompt_chars": prompt_chars,
            "assistant_chars": assistant_chars,
            "prompt_tokens": prompt_tokens if prompt_tokens is not None else prompt_estimate,
            "completion_tokens": completion_tokens if completion_tokens is not None else completion_estimate,
            "total_tokens": total_tokens if total_tokens is not None else prompt_estimate + completion_estimate,
            "token_accounting": "provider_reported" if total_tokens is not None or prompt_tokens is not None or completion_tokens is not None else "estimated_chars_div_4",
            "external_model_invocation_performed": external_model_invocation_performed,
            "provider_route_status": provider_route_status or status,
            "primary_provider": primary_provider,
            "fallback_used": fallback_used,
            "fallback_provider": fallback_provider,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
            "redacted": redacted,
            "receipt_id": receipt_id,
        }
        with self.usage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.usage_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.usage_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records[-limit:]

    def summary(self, *, limit: int = 20) -> dict[str, Any]:
        records = self.list(limit=10_000)
        total_tokens = sum(int(record.get("total_tokens") or 0) for record in records)
        external_calls = sum(1 for record in records if record.get("external_model_invocation_performed"))
        providers = sorted({str(record.get("provider", "")) for record in records if record.get("provider")})
        return {
            "usage_path": str(self.usage_path),
            "count": len(records),
            "total_tokens": total_tokens,
            "external_calls": external_calls,
            "providers": providers,
            "browser_auto_launch": False,
            "raw_secret_values_included": False,
            "recent": records[-limit:],
        }


def _estimate_tokens(chars: int) -> int:
    return max(0, (max(0, chars) + 3) // 4)
