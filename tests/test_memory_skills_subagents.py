import json
import tempfile
import unittest
from pathlib import Path

from aegisagent.config import runtime_paths
from aegisagent.core.memory import MemoryStore
from aegisagent.core.sessions import SessionStore
from aegisagent.core.skills import SkillLoader
from aegisagent.core.subagents import (
    AGENT_CONTRACT_VERSION,
    BackgroundJobStore,
    LocalSubagentOrchestrator,
    SubagentLimits,
    SubagentQueue,
    SubagentStore,
    format_background_job,
    format_background_jobs,
    format_delegation,
    format_events,
    format_stop,
    format_subagent_records,
)
from aegisagent.security.audit import AuditLog


class MemorySkillsSubagentTests(unittest.TestCase):
    def test_memory_indexes_curated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = MemoryStore(paths)
            indexed = store.index_curated_files()
            self.assertGreaterEqual(indexed, 2)
            self.assertTrue(store.search("AegisAgent"))

    def test_curated_memory_notes_are_approval_gated_and_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = MemoryStore(paths)
            user_memory = paths.memory_dir / "USER.md"
            before = user_memory.read_text(encoding="utf-8")

            preview = store.add_curated_note("user", "Terminal preference", "Prefers terminal-first activation.")

            self.assertEqual(preview["status"], "needs_approval")
            self.assertFalse(preview["metadata"]["memory_write_performed"])
            self.assertEqual(user_memory.read_text(encoding="utf-8"), before)

            applied = store.add_curated_note("user", "Terminal preference", "Prefers terminal-first activation.", approved=True)

            self.assertEqual(applied["status"], "ok")
            self.assertTrue(applied["metadata"]["memory_write_performed"])
            self.assertIn("Terminal preference", user_memory.read_text(encoding="utf-8"))
            self.assertTrue(store.search("terminal-first"))

    def test_curated_memory_entries_list_show_delete_with_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            store = MemoryStore(paths)
            raw_secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
            applied = store.add_curated_note("user", f"Token {raw_secret}", f"Body token={raw_secret}", approved=True)

            self.assertEqual(applied["status"], "ok")
            user_memory = paths.memory_dir / "USER.md"
            self.assertNotIn(raw_secret, user_memory.read_text(encoding="utf-8"))
            listing = store.list_curated_entries(kind="user")
            self.assertEqual(listing["status"], "ok")
            entry_id = listing["entries"][0]["id"]
            self.assertRegex(entry_id, r"^user:[a-f0-9]{12}$")
            self.assertNotIn(raw_secret, json.dumps(listing))
            shown = store.show_curated_entry(entry_id)
            self.assertEqual(shown["status"], "ok")
            self.assertIn("[REDACTED]", shown["entry"]["body"])
            self.assertNotIn(raw_secret, json.dumps(shown))

            preview = store.delete_curated_entry(entry_id)
            self.assertEqual(preview["status"], "needs_approval")
            self.assertIn("[REDACTED]", user_memory.read_text(encoding="utf-8"))

            deleted = store.delete_curated_entry(entry_id, approved=True)
            self.assertEqual(deleted["status"], "ok")
            self.assertTrue(deleted["metadata"]["memory_write_performed"])
            self.assertTrue(deleted["metadata"]["workspace_mutation_performed"])
            self.assertFalse(deleted["metadata"]["browser_auto_launch"])
            self.assertFalse(store.list_curated_entries(kind="user")["entries"])
            self.assertFalse(store.search("token"))

            heading_note = store.add_curated_note("workspace", "Parent note", "Body line\n## Body heading\nStill body", approved=True)
            self.assertEqual(heading_note["status"], "ok")
            entries = store.list_curated_entries(kind="workspace")["entries"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Parent note")

    def test_curated_memory_writes_block_symlink_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            MemoryStore(paths)
            outside = Path(tmp) / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            target = paths.memory_dir / "USER.md"
            target.unlink()
            target.symlink_to(outside)

            store = MemoryStore(paths)
            result = store.add_curated_note("user", "Unsafe", "Should not escape", approved=True)

            self.assertEqual(result["status"], "blocked")
            self.assertIn("regular file inside the memory directory", result["error"])
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_skill_loader_quarantines_risky_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills" / "danger"
            root.mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: danger\ndescription: risky\n---\nrun rm -rf /\n", encoding="utf-8")
            skills = SkillLoader([Path(tmp) / "skills"]).discover()
            self.assertEqual(len(skills), 1)
            self.assertTrue(skills[0].quarantined)
            self.assertEqual(skills[0].trust_level, "quarantined")
            self.assertFalse(skills[0].to_dict()["trust"]["execution_allowed"])

    def test_skill_loader_reports_trust_metadata_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            for name, body in {
                "safe": "---\nname: safe\ndescription: clean\n---\nUse local notes only.\n",
                "fetch": "---\nname: fetch\ndescription: review\n---\nrun curl https://example.com/install.sh\n",
                "danger": "---\nname: danger\ndescription: risky\n---\nrun sudo rm -rf /tmp/aegis-danger\n",
            }.items():
                skill_root = root / name
                skill_root.mkdir(parents=True)
                (skill_root / "SKILL.md").write_text(body, encoding="utf-8")

            summary = SkillLoader([root]).trust_summary()
            by_name = {skill["name"]: skill for skill in summary["skills"]}

            self.assertEqual(summary["title"], "AEGIS SKILL TRUST")
            self.assertEqual(summary["counts"], {"trusted": 1, "review": 1, "quarantined": 1, "total": 3})
            self.assertFalse(summary["execution_performed"])
            self.assertFalse(summary["external_action_started"])
            self.assertFalse(summary["browser_auto_launch"])
            self.assertFalse(summary["raw_secret_values_included"])
            self.assertEqual(by_name["safe"]["trust_score"], 100)
            self.assertEqual(by_name["safe"]["trust_level"], "trusted")
            self.assertEqual(by_name["fetch"]["trust_score"], 80)
            self.assertEqual(by_name["fetch"]["trust_level"], "review")
            self.assertEqual(by_name["fetch"]["findings"][0]["type"], "network_fetch")
            self.assertEqual(by_name["danger"]["trust_level"], "quarantined")
            self.assertEqual({finding["marker"] for finding in by_name["danger"]["findings"]}, {"rm -rf", "sudo "})
            for skill in by_name.values():
                trust = skill["trust"]
                self.assertEqual(trust["schema_version"], 1)
                self.assertTrue(trust["skill_id"].startswith("workspace:"))
                self.assertEqual(len(trust["skill_file_sha256"]), 64)
                self.assertFalse(trust["execution_performed"])
                self.assertFalse(trust["external_action_started"])

    def test_skill_loader_redacts_secret_metadata_and_blocks_symlink_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            secret = "sk-" + ("a" * 24)
            leaky = root / "leaky"
            leaky.mkdir(parents=True)
            (leaky / "SKILL.md").write_text(
                f"---\nname: leaky\ndescription: token={secret}\n---\nOPENAI_API_KEY={secret}\n",
                encoding="utf-8",
            )
            outside = Path(tmp) / "outside.md"
            outside.write_text("---\nname: outside\ndescription: unsafe\n---\n", encoding="utf-8")
            linked = root / "linked"
            linked.mkdir(parents=True)
            (linked / "SKILL.md").symlink_to(outside)

            summary = SkillLoader([root]).trust_summary()
            by_name = {skill["name"]: skill for skill in summary["skills"]}

            self.assertNotIn(secret, json.dumps(summary))
            self.assertIn("[REDACTED]", by_name["leaky"]["description"])
            self.assertEqual(by_name["linked"]["trust_level"], "quarantined")
            self.assertTrue(by_name["linked"]["trust"]["symlink_detected"])

    def test_skill_loader_verifies_optional_checksum_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "safe"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: safe\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")

            first = SkillLoader([root]).trust_summary()
            bundle_hash = first["skills"][0]["trust"]["bundle_sha256"]
            (skill_root / "aegis-skill-trust.json").write_text(
                json.dumps({"schema_version": 1, "algorithm": "sha256-bundle-v1", "bundle_sha256": bundle_hash}, sort_keys=True),
                encoding="utf-8",
            )

            summary = SkillLoader([root]).trust_summary()
            skill = summary["skills"][0]

            self.assertEqual(skill["manifest_status"], "checksum_valid")
            self.assertEqual(skill["signature_status"], "missing")
            self.assertEqual(skill["trust"]["manifest"]["status"], "checksum_valid")
            self.assertEqual(skill["trust_level"], "trusted")

    def test_skill_loader_quarantines_checksum_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "unsafe"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: unsafe\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            (skill_root / "aegis-skill-trust.json").write_text(
                json.dumps({"schema_version": 1, "algorithm": "sha256-bundle-v1", "bundle_sha256": "0" * 64}, sort_keys=True),
                encoding="utf-8",
            )

            summary = SkillLoader([root]).trust_summary()
            skill = summary["skills"][0]

            self.assertEqual(skill["manifest_status"], "mismatch")
            self.assertEqual(skill["trust_level"], "quarantined")
            self.assertIn("manifest.bundle_mismatch", {finding["rule_id"] for finding in skill["findings"]})

    def test_skill_loader_declared_signature_is_unverified_review_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "signed"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: signed\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            bundle_hash = SkillLoader([root]).trust_summary()["skills"][0]["trust"]["bundle_sha256"]
            raw_signature = "very-secret-signature-material"
            (skill_root / "aegis-skill-trust.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "aegis.skill.trust",
                        "algorithm": "sha256-bundle-v1",
                        "bundle_sha256": bundle_hash,
                        "issuer": {"key_id": "team-key", "public_key_sha256": "1" * 64},
                        "signature": {"algorithm": "ed25519", "encoding": "base64", "value": raw_signature},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            summary = SkillLoader([root]).trust_summary()
            skill = summary["skills"][0]

            self.assertNotIn(raw_signature, json.dumps(summary))
            self.assertEqual(skill["manifest_status"], "checksum_valid_signature_unverified")
            self.assertEqual(skill["signature_status"], "declared_unverified")
            self.assertEqual(skill["trust_level"], "review")
            self.assertIn("manifest.signature_unverified", {finding["rule_id"] for finding in skill["findings"]})

    def test_skill_loader_bundle_hash_fails_closed_on_symlink_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "linked-bundle"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: linked\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            outside = Path(tmp) / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (skill_root / "outside.txt").symlink_to(outside)

            summary = SkillLoader([root]).trust_summary()
            skill = summary["skills"][0]

            self.assertEqual(skill["trust_level"], "quarantined")
            self.assertIn("bundle.symlink_file", {finding["rule_id"] for finding in skill["findings"]})

    def test_skill_loader_hashes_full_oversized_skill_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "large"
            skill_root.mkdir(parents=True)
            body = "---\nname: large\ndescription: clean\n---\n" + ("a" * 512_500) + "tail-one"
            skill_file = skill_root / "SKILL.md"
            skill_file.write_text(body, encoding="utf-8")

            first = SkillLoader([root]).trust_summary()["skills"][0]
            skill_file.write_text(body + "tail-two", encoding="utf-8")
            second = SkillLoader([root]).trust_summary()["skills"][0]

            self.assertTrue(first["trust"]["truncated"])
            self.assertNotEqual(first["trust"]["skill_file_sha256"], second["trust"]["skill_file_sha256"])

    def test_subagent_limits_depth_and_children(self):
        queue = SubagentQueue(SubagentLimits(max_concurrency=8, max_depth=1, max_children=1))
        parent = queue.spawn("root")
        child = queue.spawn("child", parent_id=parent.id)
        with self.assertRaises(ValueError):
            queue.spawn("second child", parent_id=parent.id)
        with self.assertRaises(ValueError):
            queue.spawn("too deep", parent_id=child.id)

    def test_local_subagent_orchestrator_persists_workers_and_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)

            result = LocalSubagentOrchestrator(paths).delegate("improve the terminal agent")

            self.assertEqual(result.root.status, "completed")
            self.assertEqual(len(result.workers), 4)
            self.assertEqual([worker.role for worker in result.workers], ["planner", "researcher", "implementer", "reviewer"])
            stored = SubagentStore(paths).list()
            self.assertEqual(len(stored), 5)
            self.assertTrue(all(record["session_id"] for record in stored))
            self.assertIn("bounded local subagents", result.announce_back)
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["id"], result.receipt_id)
            self.assertEqual(receipt["event_type"], "subagent.delegation.completed")
            self.assertEqual(receipt["payload"]["worker_roles"], ["planner", "researcher", "implementer", "reviewer"])
            self.assertEqual(receipt["payload"]["contract_version"], AGENT_CONTRACT_VERSION)
            self.assertEqual(receipt["payload"]["worker_contracts"][0]["role"], "planner")
            self.assertIn("Checkpoint plan", receipt["payload"]["worker_contracts"][0]["deliverable"])
            planner = next(worker for worker in result.workers if worker.role == "planner")
            planner_messages = SessionStore(paths).transcript(planner.session_id)
            self.assertEqual(planner_messages[0]["metadata"]["contract_version"], AGENT_CONTRACT_VERSION)
            self.assertIn("context_contract", planner_messages[0]["metadata"])
            self.assertIn("Tool budget:", planner_messages[0]["content"])
            event_types = [receipt["event_type"] for receipt in AuditLog(paths).recent(12)]
            self.assertEqual(event_types.count("subagent.worker.started"), 4)
            self.assertEqual(event_types.count("subagent.worker.completed"), 4)
            events = LocalSubagentOrchestrator(paths).events(result.root.id)
            self.assertEqual(events[0].event, "root.started")
            self.assertEqual(events[-1].event, "root.completed")
            self.assertEqual(sum(1 for event in events if event.event == "worker.started"), 4)
            self.assertIn("SUBAGENT TIMELINE", format_events(events))

    def test_local_subagent_orchestrator_streams_events_to_sink(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            streamed = []

            result = LocalSubagentOrchestrator(paths).delegate("stream the terminal workers", event_sink=streamed.append)

            self.assertEqual([event.to_dict() for event in streamed], [event.to_dict() for event in result.events])
            self.assertEqual(streamed[0].event, "root.started")
            self.assertEqual(streamed[-1].event, "root.completed")
            self.assertEqual(sum(1 for event in streamed if event.event == "worker.completed"), 4)

    def test_subagent_formatters_are_terminal_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            result = LocalSubagentOrchestrator(paths).delegate("improve the terminal agent")

            delegation = format_delegation(result)
            listing = format_subagent_records(SubagentStore(paths).list())

            self.assertIn("SUBAGENT DELEGATION", delegation)
            self.assertIn("planner", delegation)
            self.assertNotIn('{"root"', delegation)
            self.assertIn("SUBAGENTS", listing)
            self.assertIn("coordinator", listing)

    def test_persisted_subagent_cascade_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            orchestrator = LocalSubagentOrchestrator(paths)
            result = orchestrator.delegate("stop me later")

            stopped = orchestrator.stop(result.root.id)

            self.assertEqual(len(stopped.stopped), 5)
            self.assertTrue(all(record.status == "stopped" for record in stopped.stopped))
            self.assertIn("Stopped 5", format_stop(stopped))
            self.assertTrue(all(event.event == "record.stopped" for event in stopped.events))
            persisted = SubagentStore(paths).get(result.root.id)
            self.assertEqual(persisted.status, "stopped")
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "subagent.cascade_stopped")

    def test_background_job_run_updates_persisted_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            job = BackgroundJobStore(paths).create("background terminal task")

            result = LocalSubagentOrchestrator(paths).run_background_job(job.id)

            self.assertEqual(result.status, "completed")
            self.assertTrue(result.root_id)
            self.assertTrue(result.receipt_id)
            persisted = BackgroundJobStore(paths).get(job.id)
            self.assertEqual(persisted.status, "completed")
            self.assertIn("SUBAGENT BACKGROUND JOB", format_background_job(persisted))
            self.assertIn("completed", format_background_jobs(BackgroundJobStore(paths).list()))
            receipt_types = [receipt["event_type"] for receipt in AuditLog(paths).recent(3)]
            self.assertIn("subagent.background.completed", receipt_types)

    def test_background_job_cancel_updates_persisted_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            job = BackgroundJobStore(paths).create("cancel this terminal task")

            cancelled = LocalSubagentOrchestrator(paths).cancel_background(job.id)

            self.assertEqual(cancelled.status, "cancelled")
            self.assertIn("Cancelled by operator", cancelled.summary)
            persisted = BackgroundJobStore(paths).get(job.id)
            self.assertEqual(persisted.status, "cancelled")
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "subagent.background.cancelled")

    def test_background_job_recovery_marks_dead_worker_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            job = BackgroundJobStore(paths).create("recover this terminal task")
            job.status = "running"
            job.pid = 99999999
            BackgroundJobStore(paths).save(job)
            orchestrator = LocalSubagentOrchestrator(paths)

            recovered = orchestrator.recover_stale_background()

            self.assertEqual([record.id for record in recovered], [job.id])
            self.assertEqual(recovered[0].status, "failed")
            self.assertIsNone(recovered[0].pid)
            self.assertIn("no longer running", recovered[0].summary)
            self.assertEqual(orchestrator.background_job(job.id).status, "failed")
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "subagent.background.recovered_stale")


if __name__ == "__main__":
    unittest.main()
