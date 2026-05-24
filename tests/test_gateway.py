from __future__ import annotations

import tempfile
import unittest

from aegisagent.config import runtime_paths
from aegisagent.core.tasks import TaskRunner
from aegisagent.gateway import app_factory

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional gateway dependency
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class GatewayTests(unittest.TestCase):
    def test_connector_and_setup_routes_are_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(app_factory(tmp))

            connectors = client.get("/connectors")
            self.assertEqual(connectors.status_code, 200)
            connector_payload = connectors.json()
            self.assertFalse(connector_payload["external_delivery_performed"])
            self.assertFalse(connector_payload["browser_auto_launch"])
            self.assertIn("slack", [item["name"] for item in connector_payload["connectors"]])

            section = client.get("/setup/connectors")
            self.assertEqual(section.status_code, 200)
            section_payload = section.json()
            self.assertEqual(section_payload["name"], "connectors")
            self.assertTrue(any(check["name"] == "external_delivery" for check in section_payload["checks"]))

            doctor = client.get("/connectors/doctor")
            self.assertEqual(doctor.status_code, 200)
            doctor_payload = doctor.json()
            self.assertFalse(doctor_payload["external_delivery_performed"])
            self.assertFalse(doctor_payload["browser_auto_launch"])

            outbox = client.get("/connectors/outbox")
            self.assertEqual(outbox.status_code, 200)
            outbox_payload = outbox.json()
            self.assertFalse(outbox_payload["external_delivery_performed"])
            self.assertFalse(outbox_payload["browser_auto_launch"])
            self.assertEqual(outbox_payload["outbox"], [])

            for route in ("/connectors/draft", "/connectors/send"):
                response = client.post(route, json={"connector": "slack", "target": "#ops", "message": "hello"})
                self.assertEqual(response.status_code, 404, route)

            missing = client.get("/setup/nope")
            self.assertEqual(missing.status_code, 404)

    def test_read_only_terminal_parity_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            TaskRunner(paths).submit("summarize gateway parity", source="test")
            client = TestClient(app_factory(tmp))

            tools = client.get("/tools")
            self.assertEqual(tools.status_code, 200)
            tool_payload = tools.json()
            self.assertTrue(any(tool["name"] == "filesystem" for tool in tool_payload))
            for tool in tool_payload:
                for field in ("name", "status", "scope", "approval", "risk", "description"):
                    self.assertIn(field, tool)

            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            dashboard_payload = dashboard.json()
            self.assertEqual(dashboard_payload["title"], "AEGIS TERMINAL DASHBOARD")
            self.assertTrue(dashboard_payload["terminal_first"])
            self.assertFalse(dashboard_payload["browser_auto_launch"])

            capabilities = client.get("/capabilities")
            self.assertEqual(capabilities.status_code, 200)
            capability_payload = capabilities.json()
            self.assertEqual(capability_payload["title"], "AEGIS CAPABILITY MAP")
            self.assertIn("counts", capability_payload)

            gaps = client.get("/capabilities/gaps")
            self.assertEqual(gaps.status_code, 200)
            gap_payload = gaps.json()
            self.assertEqual(gap_payload["title"], "AEGIS CAPABILITY GAPS")
            self.assertTrue(all(row["status"] != "ready" for row in gap_payload["capabilities"]))

            tasks = client.get("/tasks")
            self.assertEqual(tasks.status_code, 200)
            task_payload = tasks.json()
            self.assertEqual(task_payload["task_count"], 1)
            self.assertFalse(task_payload["external_action_started"])

            for route, marker in [
                ("/audit", "ok"),
                ("/model/providers", "active_provider"),
                ("/model/doctor", "checks"),
                ("/model/usage", "recent"),
                ("/sessions", "sessions"),
                ("/automations", "automations"),
                ("/improvements", "proposals"),
                ("/agents/status", "profiles"),
                ("/agents/contracts", "profiles"),
                ("/subagents", "subagents"),
                ("/subagents/jobs", "jobs"),
                ("/browser/sessions", "sessions"),
            ]:
                response = client.get(route)
                self.assertEqual(response.status_code, 200, route)
                self.assertIn(marker, response.json(), route)


if __name__ == "__main__":
    unittest.main()
