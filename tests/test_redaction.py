import unittest

from aegisagent.security.redaction import redact_mapping, redact_text


class RedactionTests(unittest.TestCase):
    def test_redacts_known_secret_patterns(self):
        result = redact_text("api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
        self.assertTrue(result.redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", result.text)

    def test_secret_keys_are_replaced(self):
        clean, redacted = redact_mapping({"token": "abc123", "nested": {"password": "pass"}})
        self.assertTrue(redacted)
        self.assertEqual(clean["token"], "[REDACTED]")
        self.assertEqual(clean["nested"]["password"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
