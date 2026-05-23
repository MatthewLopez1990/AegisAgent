import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aegisagent.config import runtime_paths
from aegisagent.security.audit import AuditLog


class AuditTests(unittest.TestCase):
    def test_append_and_verify_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(runtime_paths(tmp))
            audit.append("tool.call", {"command": "rg --files"})
            audit.append("policy.decision", {"action": "allow"})
            result = audit.verify()
            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 2)

    def test_verify_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            audit = AuditLog(paths)
            audit.append("tool.call", {"command": "rg --files"})
            line = paths.audit_jsonl.read_text(encoding="utf-8").splitlines()[0]
            data = json.loads(line)
            data["payload"]["command"] = "rm -rf /"
            paths.audit_jsonl.write_text(json.dumps(data) + "\n", encoding="utf-8")
            self.assertFalse(audit.verify()["ok"])

    def test_secret_payloads_are_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(runtime_paths(tmp))
            entry = audit.append("secret.test", {"token": "abc123"})
            self.assertEqual(entry["payload"]["token"], "[REDACTED]")

    def test_parallel_appends_keep_hash_chain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)

            def append(index: int) -> None:
                AuditLog(paths).append("parallel.test", {"index": index})

            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(append, range(24)))

            result = AuditLog(paths).verify()
            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 24)


if __name__ == "__main__":
    unittest.main()
