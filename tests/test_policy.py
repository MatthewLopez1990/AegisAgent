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

    def test_git_network_and_mutations_require_approval(self):
        for command in ("git pull origin main", "git fetch origin main", "git add README.md", "git branch feature/aegis"):
            classification = classify_shell_command(command)
            self.assertTrue(classification.requires_approval, command)
            self.assertEqual(classification.tool, "git")

    def test_git_read_only_commands_are_allowed(self):
        for command in ("git status", "git diff", "git remote -v", "git branch --list"):
            classification = classify_shell_command(command)
            self.assertFalse(classification.requires_approval, command)
            self.assertEqual(classification.risk, "low")

    def test_skill_discovery_is_passive_but_execution_is_gated(self):
        discover = decide_tool("skills", "trust_summary")
        execute = decide_tool("skills", "execute danger")

        self.assertEqual(discover.action, "allow")
        self.assertEqual(discover.risk, "low")
        self.assertEqual(execute.action, "ask")
        self.assertEqual(execute.risk, "high")


if __name__ == "__main__":
    unittest.main()
