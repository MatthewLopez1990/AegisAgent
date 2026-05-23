import unittest

from aegisagent.security.policy import classify_shell_command, decide_tool


class PolicyTests(unittest.TestCase):
    def test_read_only_shell_is_allowed(self):
        decision = decide_tool("shell", "rg --files")
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.risk, "low")

    def test_network_requires_approval(self):
        decision = decide_tool("network", "fetch https://example.com")
        self.assertEqual(decision.action, "ask")
        self.assertEqual(decision.risk, "high")

    def test_destructive_command_is_denied(self):
        decision = decide_tool("shell", "rm -rf /")
        self.assertEqual(decision.action, "deny")
        self.assertEqual(decision.risk, "critical")

    def test_git_push_requires_approval(self):
        classification = classify_shell_command("git push origin main")
        self.assertTrue(classification.requires_approval)
        self.assertEqual(classification.tool, "git")


if __name__ == "__main__":
    unittest.main()
