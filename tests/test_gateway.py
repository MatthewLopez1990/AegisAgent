from __future__ import annotations

import tempfile
import unittest

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

            missing = client.get("/setup/nope")
            self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
