import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from aegisagent.config import runtime_paths
from aegisagent.core.agent import AgentRuntime
from aegisagent.core.executor import GovernedExecutor
from aegisagent.core.lifecycle import update_from_github
from aegisagent.core.provider_config import ProviderUsageStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.subagents import AGENT_CONTRACT_VERSION
from aegisagent.core.tasks import TaskRunner, TaskStore
from aegisagent.core.workspace_tools import WorkspaceToolRunner
from aegisagent.security.audit import AuditLog
from aegisagent.tui.interactive import dispatch_interactive_command


class TerminalAgentSessionTests(unittest.TestCase):
    def test_session_messages_persist_under_workspace_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = SessionStore(paths)

            store.append("main", role="user", content="draft a safe migration plan", metadata={"source": "tui"})

            reloaded = SessionStore(paths)
            messages = reloaded.transcript("main")
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[0]["content"], "draft a safe migration plan")
            self.assertEqual(messages[0]["metadata"]["source"], "tui")
            self.assertTrue(paths.sessions_dir.exists())
            self.assertTrue(any(paths.sessions_dir.iterdir()))

    def test_session_search_returns_redacted_snippets(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = SessionStore(paths)
            store.append("main", role="user", content="remember api_key=sk-abcdefghijklmnopqrstuvwxyz123456 for search", metadata={"source": "test"})

            results = store.search("search")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["role"], "user")
            self.assertIn("[REDACTED]", results[0]["snippet"])
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", results[0]["snippet"])

    def test_plain_tui_prompt_dispatch_appends_user_and_assistant_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = SessionStore(paths)

            with contextlib.redirect_stdout(io.StringIO()):
                result = dispatch_interactive_command("summarize this workspace", paths)

            self.assertEqual(result, "agent turn")
            messages = store.transcript("main")
            self.assertEqual([message["role"] for message in messages], ["user", "tool", "assistant"])
            self.assertEqual(messages[0]["content"], "summarize this workspace")
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[0]["metadata"]["source"], "tui")
            self.assertEqual(messages[1]["metadata"]["tool"], "workspace.list_files")
            self.assertIn("Workspace summary", messages[2]["content"])
            self.assertEqual(messages[2]["metadata"]["provider"], "local/terminal-v0")

    def test_agent_runtime_persists_assistant_turn_and_audit_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "README.md").write_text("# demo\n", encoding="utf-8")

            result = AgentRuntime(paths).respond("draft a safe plan", source="cli")

            self.assertEqual(result.provider, "local/terminal-v0")
            self.assertEqual(result.mode, "local")
            self.assertIn("Initial governed plan", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["id"], result.receipt_id)
            self.assertEqual(receipt["event_type"], "agent.turn.completed")
            self.assertTrue(receipt["payload"]["model_invocation_performed"])
            self.assertFalse(receipt["payload"]["external_model_invocation_performed"])
            usage = ProviderUsageStore(paths).summary()
            self.assertEqual(usage["count"], 1)
            self.assertEqual(usage["recent"][0]["id"], result.usage_id)
            self.assertEqual(usage["recent"][0]["provider"], "local/terminal-v0")
            self.assertEqual(usage["recent"][0]["token_accounting"], "estimated_chars_div_4")
            self.assertFalse(usage["recent"][0]["fallback_used"])
            self.assertFalse(usage["recent"][0]["browser_auto_launch"])

    def test_agent_runtime_uses_typed_workspace_tool_for_workspace_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "README.md").write_text("# demo\n", encoding="utf-8")

            result = AgentRuntime(paths).respond("summarize this workspace", source="cli")

            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual([message["role"] for message in messages], ["user", "tool", "assistant"])
            self.assertEqual(messages[1]["metadata"]["tool"], "workspace.list_files")
            tool_payload = json.loads(messages[1]["content"])
            self.assertIn("README.md", tool_payload["files"])
            self.assertIn("workspace.list_files", result.assistant_message)
            receipts = AuditLog(paths).recent(2)
            self.assertEqual(receipts[0]["event_type"], "agent.tool.completed")
            self.assertEqual(receipts[0]["payload"]["tool"], "workspace.list_files")
            self.assertEqual(receipts[1]["event_type"], "agent.turn.completed")
            self.assertEqual(receipts[1]["payload"]["tool_count"], 1)

    def test_agent_runtime_surfaces_typed_search_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "src.py").write_text("class LocalTerminalProvider:\n    pass\n", encoding="utf-8")

            result = AgentRuntime(paths).respond("search for LocalTerminalProvider", source="cli")

            self.assertIn("workspace.search_text", result.assistant_message)
            self.assertIn("found 1", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "workspace.search_text")

    def test_agent_runtime_surfaces_session_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = SessionStore(paths)
            store.append("main", role="assistant", content="prior note about terminal receipts", metadata={"source": "test"})

            result = AgentRuntime(paths).respond("search sessions for terminal receipts", source="cli")

            self.assertIn("sessions.search", result.assistant_message)
            self.assertIn("found 1", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            tool_message = next(message for message in messages if message["role"] == "tool")
            self.assertEqual(tool_message["metadata"]["tool"], "sessions.search")
            receipt = AuditLog(paths).recent(2)[0]
            self.assertEqual(receipt["event_type"], "agent.tool.completed")
            self.assertEqual(receipt["payload"]["tool"], "sessions.search")

    def test_workspace_read_file_stays_inside_workspace_and_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "secret.txt").write_text("api_key=sk-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")
            runner = WorkspaceToolRunner(paths)

            blocked = runner.read_file("../outside.txt")
            allowed = runner.read_file("secret.txt")

            self.assertEqual(blocked.status, "blocked")
            self.assertEqual(allowed.status, "ok")
            payload = json.loads(allowed.content)
            self.assertEqual(payload["path"], "secret.txt")
            self.assertIn("[REDACTED]", payload["content"])
            self.assertTrue(allowed.metadata["redacted"])

    def test_workspace_replace_text_requires_approval_and_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            target = paths.workspace / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")
            runner = WorkspaceToolRunner(paths)

            preview = runner.replace_text("note.txt", "hello", "safe", approved=False)
            self.assertEqual(preview.status, "needs_approval")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello terminal\n")
            applied = runner.replace_text("note.txt", "hello", "safe", approved=True)
            blocked = runner.replace_text("../outside.txt", "x", "y", approved=True)

            self.assertEqual(applied.status, "ok")
            self.assertEqual(target.read_text(encoding="utf-8"), "safe terminal\n")
            self.assertTrue(applied.metadata["workspace_mutation_performed"])
            self.assertFalse(applied.metadata["browser_auto_launch"])
            self.assertEqual(blocked.status, "blocked")

    def test_workspace_git_stage_requires_approval_and_stages_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            target = paths.workspace / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")
            runner = WorkspaceToolRunner(paths)

            preview = runner.git_stage(["note.txt"], approved=False)
            self.assertEqual(preview.status, "needs_approval")
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            self.assertEqual(cached.stdout.strip(), "")

            applied = runner.git_stage(["note.txt"], approved=True)
            blocked = runner.git_stage(["../outside.txt"], approved=True)
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=paths.workspace, text=True, capture_output=True, check=True)

            self.assertEqual(applied.status, "ok")
            self.assertEqual(cached.stdout.strip(), "note.txt")
            self.assertFalse(applied.metadata["workspace_mutation_performed"])
            self.assertTrue(applied.metadata["git_index_mutation_performed"])
            self.assertFalse(applied.metadata["browser_auto_launch"])
            self.assertEqual(blocked.status, "blocked")

    def test_workspace_git_commit_requires_approval_and_commits_staged_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            target = paths.workspace / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            runner = WorkspaceToolRunner(paths)

            preview = runner.git_commit("Add note", approved=False)
            self.assertEqual(preview.status, "needs_approval")
            no_head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=paths.workspace, text=True, capture_output=True, check=False)
            self.assertNotEqual(no_head.returncode, 0)

            applied = runner.git_commit("Add note", approved=True)
            log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            empty = runner.git_commit("Nothing staged", approved=True)

            self.assertEqual(applied.status, "ok")
            self.assertEqual(log.stdout.strip(), "Add note")
            self.assertFalse(applied.metadata["workspace_mutation_performed"])
            self.assertTrue(applied.metadata["git_history_mutation_performed"])
            self.assertFalse(applied.metadata["browser_auto_launch"])
            self.assertEqual(empty.status, "blocked")

    def test_workspace_git_branch_requires_approval_for_ref_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            start_branch = subprocess.run(["git", "branch", "--show-current"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            runner = WorkspaceToolRunner(paths)

            listed = runner.git_branch()
            preview_create = runner.git_branch("create", "feature/aegis", approved=False)
            created = runner.git_branch("create", "feature/aegis", approved=True)
            preview_switch = runner.git_branch("switch", "feature/aegis", approved=False)
            still_start = subprocess.run(["git", "branch", "--show-current"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            switched = runner.git_branch("switch", "feature/aegis", approved=True)
            current = subprocess.run(["git", "branch", "--show-current"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            blocked = runner.git_branch("create", "../bad", approved=True)

            self.assertEqual(listed.status, "ok")
            self.assertIn(start_branch, json.loads(listed.content)["stdout"])
            self.assertEqual(preview_create.status, "needs_approval")
            self.assertEqual(created.status, "ok")
            self.assertEqual(preview_switch.status, "needs_approval")
            self.assertEqual(still_start, start_branch)
            self.assertEqual(switched.status, "ok")
            self.assertEqual(current, "feature/aegis")
            self.assertTrue(switched.metadata["git_ref_mutation_performed"])
            self.assertFalse(switched.metadata["browser_auto_launch"])
            self.assertEqual(blocked.status, "blocked")

    def test_workspace_git_remote_push_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "work"
            remote = Path(tmp) / "remote.git"
            workspace.mkdir()
            paths = runtime_paths(workspace)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-B", "main"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "init", "--bare", str(remote)], text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=paths.workspace, text=True, capture_output=True, check=True)
            runner = WorkspaceToolRunner(paths)

            listed = runner.git_remote()
            preview = runner.git_remote("push", "origin", "main", approved=False)
            missing = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=False)
            pushed = runner.git_remote("push", "origin", "main", approved=True)
            exists = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=True)
            blocked = runner.git_remote("push", "../bad", "main", approved=True)

            self.assertEqual(listed.status, "ok")
            self.assertIn("origin", json.loads(listed.content)["stdout"])
            self.assertEqual(preview.status, "needs_approval")
            self.assertNotEqual(missing.returncode, 0)
            self.assertEqual(pushed.status, "ok")
            self.assertTrue(exists.stdout.strip())
            self.assertTrue(pushed.metadata["git_remote_mutation_performed"])
            self.assertTrue(pushed.metadata["external_action_started"])
            self.assertFalse(pushed.metadata["browser_auto_launch"])
            self.assertEqual(blocked.status, "blocked")

    def test_workspace_git_remote_fetch_and_pull_require_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed"
            remote = Path(tmp) / "remote.git"
            workspace = Path(tmp) / "work"
            seed.mkdir()
            subprocess.run(["git", "init"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-B", "main"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=seed, text=True, capture_output=True, check=True)
            (seed / ".gitignore").write_text(".aegisagent/\n", encoding="utf-8")
            (seed / "note.txt").write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "init", "--bare", str(remote)], text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "clone", str(remote), str(workspace)], text=True, capture_output=True, check=True)
            paths = runtime_paths(workspace)
            old_remote_head = subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            (seed / "note.txt").write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Update"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)
            new_remote_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=seed, text=True, capture_output=True, check=True).stdout.strip()
            runner = WorkspaceToolRunner(paths)

            preview_fetch = runner.git_remote("fetch", "origin", "main", approved=False)
            self.assertEqual(preview_fetch.status, "needs_approval")
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), old_remote_head)

            fetched = runner.git_remote("fetch", "origin", "main", approved=True)
            self.assertEqual(fetched.status, "ok")
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), new_remote_head)
            self.assertTrue(fetched.metadata["git_ref_mutation_performed"])
            self.assertFalse(fetched.metadata["workspace_mutation_performed"])

            preview_pull = runner.git_remote("pull", "origin", "main", approved=False)
            self.assertEqual(preview_pull.status, "needs_approval")
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v1\n")

            preview_update = update_from_github(paths, remote="origin", branch="main", approved=False)
            self.assertEqual(preview_update.status, "needs_approval")
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v1\n")

            with patch.dict(os.environ, {"AEGIS_REPO_URL": str(remote.resolve())}):
                updated = update_from_github(paths, remote="origin", branch="main", approved=True)
            self.assertEqual(updated.status, "ok")
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v2\n")
            self.assertTrue(updated.metadata["workspace_mutation_performed"])
            self.assertTrue(updated.metadata["external_action_started"])
            self.assertFalse(updated.metadata["browser_auto_launch"])

            pulled = runner.git_remote("pull", "origin", "main", approved=True)
            self.assertEqual(pulled.status, "ok")
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v2\n")
            self.assertTrue(pulled.metadata["workspace_mutation_performed"])
            self.assertTrue(pulled.metadata["external_action_started"])
            self.assertFalse(pulled.metadata["browser_auto_launch"])

    def test_agent_runtime_surfaces_typed_file_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "README.md").write_text("# Demo\n\nhello terminal\n", encoding="utf-8")

            result = AgentRuntime(paths).respond("read file README.md", source="cli")

            self.assertIn("workspace.read_file", result.assistant_message)
            self.assertIn("README.md", result.assistant_message)
            self.assertIn("# Demo", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "workspace.read_file")

    def test_agent_runtime_surfaces_typed_git_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "tracked.txt").write_text("hello\n", encoding="utf-8")

            result = AgentRuntime(paths).respond("git status", source="cli")

            self.assertIn("git.status", result.assistant_message)
            self.assertIn("tracked.txt", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "git.status")

    def test_agent_runtime_surfaces_web_fetch_approval_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)

            result = AgentRuntime(paths).respond("fetch http://127.0.0.1:9/example", source="cli")

            self.assertIn("web.fetch", result.assistant_message)
            self.assertIn("needs_approval", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "web.fetch")
            self.assertFalse(messages[1]["metadata"]["network_request_performed"])
            self.assertFalse(messages[1]["metadata"]["browser_auto_launch"])
            receipts = AuditLog(paths).recent(2)
            self.assertEqual(receipts[0]["payload"]["tool"], "web.fetch")
            self.assertFalse(receipts[0]["payload"]["metadata"]["network_request_performed"])
            self.assertFalse(receipts[0]["payload"]["browser_auto_launch"])

    def test_workspace_git_diff_can_scope_to_workspace_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            target = paths.workspace / "tracked.txt"
            target.write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            target.write_text("hello\nchanged\n", encoding="utf-8")

            result = WorkspaceToolRunner(paths).git_diff("tracked.txt")

            self.assertEqual(result.status, "ok")
            payload = json.loads(result.content)
            self.assertEqual(payload["path"], "tracked.txt")
            self.assertIn("+changed", payload["stdout"])

    def test_workspace_run_tests_uses_allowlisted_typed_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            tests_dir = paths.workspace / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            result = WorkspaceToolRunner(paths).run_tests()
            blocked = WorkspaceToolRunner(paths).run_tests("python3 -c 'print(1)'")

            self.assertEqual(result.status, "ok")
            payload = json.loads(result.content)
            self.assertEqual(payload["returncode"], 0)
            self.assertIn("Ran 1 test", payload["stderr"])
            self.assertEqual(blocked.status, "blocked")
            self.assertFalse(result.metadata["browser_auto_launch"])

    def test_agent_runtime_surfaces_typed_test_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            tests_dir = paths.workspace / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )

            result = AgentRuntime(paths).respond("run tests", source="cli")

            self.assertIn("workspace.run_tests", result.assistant_message)
            self.assertIn("returned 0", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "workspace.run_tests")

    def test_agent_runtime_delegates_subagent_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)

            result = AgentRuntime(paths).respond("delegate this to many subagents", source="cli")

            self.assertIn("Subagent delegation", result.assistant_message)
            self.assertIn("planner", result.assistant_message)
            messages = SessionStore(paths).transcript(result.session_id)
            self.assertEqual(messages[1]["metadata"]["tool"], "subagents.delegate")
            self.assertGreaterEqual(messages[1]["metadata"]["event_count"], 10)
            self.assertEqual(messages[1]["metadata"]["contract_version"], AGENT_CONTRACT_VERSION)
            rows = messages[1]["metadata"]["worker_provider_metadata"]
            self.assertEqual(len(rows), 4)
            self.assertEqual({row["provider"] for row in rows}, {"local/terminal-v0"})
            self.assertTrue(all(row["usage_id"].startswith("usage-") for row in rows))
            self.assertFalse(any(row["external_model_invocation_performed"] for row in rows))
            tool = next(item for item in result.tool_results if item["name"] == "subagents.delegate")
            self.assertEqual(tool["metadata"]["worker_provider_metadata"], rows)
            self.assertEqual(tool["metadata"]["worker_usage_ids"], [row["usage_id"] for row in rows])
            self.assertEqual(tool["metadata"]["worker_providers"], ["local/terminal-v0"])
            self.assertEqual(tool["metadata"]["artifact_count"], 5)
            self.assertEqual(len(tool["metadata"]["artifact_ids"]), 5)
            self.assertTrue(any(artifact_id.startswith("artifact-coordinator-") for artifact_id in tool["metadata"]["artifact_ids"]))
            self.assertRegex(tool["metadata"]["synthesis_id"], r"^synthesis-")
            self.assertTrue(tool["metadata"]["synthesis_artifact_id"].startswith("artifact-coordinator-"))
            self.assertEqual(tool["metadata"]["artifact_graph_node_count"], 4)
            self.assertEqual(tool["metadata"]["artifact_graph_edge_count"], 5)
            self.assertEqual(len(tool["metadata"]["worker_artifact_ids"]), 4)
            self.assertEqual(tool["metadata"]["worker_input_artifacts_by_role"]["planner"], [])
            self.assertEqual(tool["metadata"]["worker_input_artifacts_by_role"]["researcher"], [])
            self.assertEqual(len(tool["metadata"]["worker_input_artifacts_by_role"]["implementer"]), 2)
            self.assertEqual(len(tool["metadata"]["worker_input_artifacts_by_role"]["reviewer"]), 3)
            receipts = AuditLog(paths).recent(3)
            self.assertTrue(any(receipt["event_type"] == "subagent.delegation.completed" for receipt in receipts))
            turn = next(receipt for receipt in receipts if receipt["event_type"] == "agent.turn.completed")
            self.assertEqual(turn["payload"]["delegated_worker_count"], 4)
            self.assertEqual(turn["payload"]["delegated_worker_providers"], ["local/terminal-v0"])
            self.assertEqual(turn["payload"]["delegated_artifact_count"], 5)


class GovernedShellRunnerTests(unittest.TestCase):
    def test_read_only_command_executes_with_audit_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "example.txt").write_text("hello\n", encoding="utf-8")
            runner = GovernedExecutor(paths)

            result = runner.run_shell("rg --files")

            self.assertTrue(result.executed)
            self.assertEqual(result.returncode, 0)
            self.assertIn("example.txt", result.stdout)
            self.assertEqual(result.decision["action"], "allow")
            self.assertTrue(result.receipt_id)
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["id"], result.receipt_id)
            self.assertEqual(receipt["event_type"], "executor.shell.completed")
            self.assertTrue(receipt["payload"]["executed"])

    def test_destructive_command_is_blocked_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            target = paths.workspace / "blocked-target"
            target.mkdir()
            (target / "keep.txt").write_text("do not remove\n", encoding="utf-8")
            runner = GovernedExecutor(paths)

            result = runner.run_shell("rm -rf blocked-target")

            self.assertFalse(result.executed)
            self.assertIsNone(result.returncode)
            self.assertIn(result.decision["action"], {"ask", "deny"})
            self.assertTrue(target.exists())
            self.assertTrue((target / "keep.txt").exists())
            self.assertTrue(result.receipt_id)
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["id"], result.receipt_id)
            self.assertEqual(receipt["event_type"], "executor.shell.blocked")
            self.assertFalse(receipt["payload"]["executed"])


class GovernedTaskQueueTests(unittest.TestCase):
    def test_task_queue_submit_run_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)

            queued = runner.submit("draft a safe plan", source="test")
            completed = runner.run(queued.id)

            self.assertEqual(queued.status, "queued")
            self.assertEqual(completed.status, "completed")
            self.assertIn("Initial governed plan", completed.assistant_preview)
            persisted = TaskStore(paths).get(queued.id)
            self.assertEqual(persisted.status, "completed")
            self.assertTrue(persisted.receipt_id)
            events = [event.event for event in runner.events(queued.id)]
            self.assertEqual(events, ["submitted", "started", "output.assistant", "model.completed", "completed"])
            outputs = runner.outputs(queued.id)
            self.assertEqual([output.kind for output in outputs], ["assistant"])
            self.assertIn("Initial governed plan", outputs[0].content)
            receipts = [receipt["event_type"] for receipt in AuditLog(paths).recent(5)]
            self.assertIn("task.submitted", receipts)
            self.assertIn("task.started", receipts)
            self.assertIn("task.completed", receipts)

    def test_task_queue_records_tool_and_assistant_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "README.md").write_text("# demo\n", encoding="utf-8")
            runner = TaskRunner(paths)

            queued = runner.submit("read file README.md", source="test")
            completed = runner.run(queued.id)

            self.assertEqual(completed.status, "completed")
            outputs = runner.outputs(queued.id)
            self.assertEqual([output.kind for output in outputs], ["tool", "assistant"])
            self.assertEqual(outputs[0].title, "workspace.read_file")
            self.assertIn('"path": "README.md"', outputs[0].content)
            self.assertIn("Workspace file read", outputs[1].content)
            events = [event.event for event in runner.events(queued.id)]
            self.assertIn("output.tool", events)
            self.assertIn("output.assistant", events)

    def test_task_queue_cancel_prevents_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            queued = runner.submit("do not run this", source="test")

            cancelled = runner.cancel(queued.id)
            ignored = runner.run(queued.id)

            self.assertEqual(cancelled.status, "cancelled")
            self.assertEqual(ignored.status, "cancelled")
            self.assertEqual([event.event for event in runner.events(queued.id)], ["submitted", "cancelled", "run.ignored"])
            self.assertEqual(SessionStore(paths).transcript("main"), [])

    def test_task_background_no_spawn_stays_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)

            with patch.dict(os.environ, {"AEGISAGENT_TASK_NO_SPAWN": "1"}):
                record = runner.submit_background("draft a safe plan", source="test")

            self.assertEqual(record.status, "queued")
            self.assertIsNone(record.pid)
            events = [event.event for event in runner.events(record.id)]
            self.assertEqual(events, ["submitted", "background.queued"])
            receipts = [receipt["event_type"] for receipt in AuditLog(paths).recent(3)]
            self.assertIn("task.background.queued", receipts)

    def test_task_background_cancel_running_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)

            with patch.dict(os.environ, {"AEGISAGENT_TASK_SLEEP": "5"}):
                record = runner.submit_background("slow terminal task", source="test")
            time.sleep(0.2)
            cancelled = runner.cancel(record.id)

            self.assertEqual(cancelled.status, "cancelled")
            self.assertIsNone(cancelled.pid)
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "task.cancelled")
            self.assertTrue(receipt["payload"]["signal_sent"])
            events = [event.event for event in runner.events(record.id)]
            self.assertIn("background.started", events)
            self.assertIn("cancelled", events)

    def test_task_background_worker_logs_are_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)

            with patch.dict(os.environ, {"AEGISAGENT_TASK_SLEEP": "0.1"}):
                record = runner.submit_background("background log task", source="test")
            deadline = time.time() + 5
            while time.time() < deadline:
                if TaskStore(paths).get(record.id).status == "completed":
                    break
                time.sleep(0.05)

            completed = TaskStore(paths).get(record.id)
            self.assertEqual(completed.status, "completed")
            logs = runner.worker_logs(record.id)
            deadline = time.time() + 5
            while time.time() < deadline and logs["stdout"]["bytes"] == 0:
                time.sleep(0.05)
                logs = runner.worker_logs(record.id)
            self.assertGreater(logs["stdout"]["bytes"], 0)
            self.assertIn('"status": "completed"', logs["stdout"]["content"])
            self.assertEqual(logs["stderr"]["content"], "")

    def test_task_recovery_marks_dead_running_worker_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            record = runner.submit("stale detached task", source="test")
            record.status = "running"
            record.pid = 99999999
            TaskStore(paths).save(record)

            recovered = runner.recover_stale_running()

            self.assertEqual([item.id for item in recovered], [record.id])
            persisted = TaskStore(paths).get(record.id)
            self.assertEqual(persisted.status, "failed")
            self.assertIsNone(persisted.pid)
            self.assertIn("no longer running", persisted.summary)
            events = [event.event for event in runner.events(record.id)]
            self.assertEqual(events, ["submitted", "recovered.stale"])
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "task.recovered_stale")

    def test_task_recovery_leaves_live_running_worker_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            record = runner.submit("live detached task", source="test")
            record.status = "running"
            record.pid = os.getpid()
            TaskStore(paths).save(record)

            recovered = runner.recover_stale_running()

            self.assertEqual(recovered, [])
            self.assertEqual(TaskStore(paths).get(record.id).status, "running")

    def test_task_list_and_get_recover_stale_running_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            listed_record = runner.submit("stale listed task", source="test")
            listed_record.status = "running"
            listed_record.pid = 99999999
            TaskStore(paths).save(listed_record)

            listed = runner.list()

            self.assertEqual(listed[0]["status"], "failed")
            self.assertIsNone(listed[0]["pid"])
            events = [event.event for event in runner.events(listed_record.id)]
            self.assertIn("recovered.stale", events)

            shown_record = runner.submit("stale shown task", source="test")
            shown_record.status = "running"
            shown_record.pid = 99999998
            TaskStore(paths).save(shown_record)

            shown = runner.get(shown_record.id)

            self.assertEqual(shown.status, "failed")
            self.assertIsNone(shown.pid)


if __name__ == "__main__":
    unittest.main()
