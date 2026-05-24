import json
import tempfile
import unittest
from pathlib import Path

from aegisagent.config import runtime_paths
from aegisagent.core.memory import MemoryStore
from aegisagent.core.provider_config import ProviderUsageStore
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
    format_artifact,
    format_artifact_search,
    format_artifacts,
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

    def test_skill_loader_authors_manifest_preview_and_approved_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "safe"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: safe\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            loader = SkillLoader([root])

            preview = loader.author_manifest("safe")
            self.assertEqual(preview["status"], "needs_approval")
            self.assertFalse(preview["manifest_write_performed"])
            self.assertFalse((skill_root / "aegis-skill-trust.json").exists())

            written = loader.author_manifest("safe", approved=True)
            self.assertEqual(written["status"], "ok")
            self.assertTrue(written["manifest_write_performed"])
            self.assertTrue((skill_root / "aegis-skill-trust.json").exists())
            self.assertEqual(SkillLoader([root]).trust_summary()["skills"][0]["manifest_status"], "checksum_valid")

    def test_skill_loader_manifest_author_blocks_existing_manifest_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "safe"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("---\nname: safe\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            loader = SkillLoader([root])
            self.assertEqual(loader.author_manifest("safe", approved=True)["status"], "ok")
            existing = (skill_root / "aegis-skill-trust.json").read_text(encoding="utf-8")

            blocked = loader.author_manifest("safe", approved=True)
            forced = loader.author_manifest("safe", approved=True, force=True)

            self.assertEqual(blocked["status"], "already_current")
            self.assertEqual((skill_root / "aegis-skill-trust.json").read_text(encoding="utf-8"), existing)
            self.assertEqual(forced["status"], "already_current")

    def test_skill_loader_manifest_author_blocks_different_existing_manifest_even_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            skill_root = root / "safe"
            skill_root.mkdir(parents=True)
            manifest_path = skill_root / "aegis-skill-trust.json"
            (skill_root / "SKILL.md").write_text("---\nname: safe\ndescription: clean\n---\nUse local notes only.\n", encoding="utf-8")
            sentinel = '{"schema_version": 1, "kind": "aegis.skill.trust", "algorithm": "sha256-bundle-v1", "bundle_sha256": "' + ("0" * 64) + '"}\n'
            manifest_path.write_text(sentinel, encoding="utf-8")

            result = SkillLoader([root]).author_manifest("safe", approved=True, force=True)

            self.assertEqual(result["status"], "blocked")
            self.assertIn("differs", result["message"])
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), sentinel)

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
            self.assertEqual([worker.depth for worker in result.workers], [1, 1, 1, 1])
            self.assertEqual([worker.parent_id for worker in result.workers], [result.root.id] * 4)
            self.assertEqual(result.root.children, [worker.id for worker in result.workers])
            self.assertEqual(result.to_dict()["requested_depth"], 1)
            self.assertEqual(result.to_dict()["nested_worker_count"], 0)
            stored = SubagentStore(paths).list()
            self.assertEqual(len(stored), 5)
            self.assertTrue(all(record["session_id"] for record in stored))
            self.assertIn("bounded local subagents", result.announce_back)
            self.assertTrue(all(worker.model_invocation_performed for worker in result.workers))
            self.assertEqual({worker.provider for worker in result.workers}, {"local/terminal-v0"})
            self.assertEqual({worker.provider_mode for worker in result.workers}, {"local"})
            self.assertEqual({worker.provider_route_status for worker in result.workers}, {"local"})
            self.assertFalse(any(worker.external_model_invocation_performed for worker in result.workers))
            self.assertFalse(any(worker.fallback_used for worker in result.workers))
            self.assertTrue(all(worker.usage_id.startswith("usage-") for worker in result.workers))
            usage = ProviderUsageStore(paths).summary()
            self.assertEqual(usage["count"], 0)
            self.assertEqual(usage["worker_count"], 4)
            self.assertEqual(usage["worker_providers"], ["local/terminal-v0"])
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["id"], result.receipt_id)
            self.assertEqual(receipt["event_type"], "subagent.delegation.completed")
            self.assertEqual(receipt["payload"]["worker_roles"], ["planner", "researcher", "implementer", "reviewer"])
            self.assertEqual(receipt["payload"]["requested_depth"], 1)
            self.assertEqual(receipt["payload"]["actual_max_depth"], 1)
            self.assertEqual(receipt["payload"]["nested_worker_count"], 0)
            self.assertEqual(receipt["payload"]["worker_depths"], [1, 1, 1, 1])
            self.assertEqual(receipt["payload"]["worker_parent_ids"], [result.root.id] * 4)
            self.assertEqual(receipt["payload"]["worker_providers"], ["local/terminal-v0"] * 4)
            self.assertEqual(receipt["payload"]["worker_usage_ids"], [worker.usage_id for worker in result.workers])
            self.assertEqual(receipt["payload"]["artifact_count"], 5)
            self.assertEqual(receipt["payload"]["generated_artifact_count"], 5)
            self.assertEqual(receipt["payload"]["synthesis_artifact_count"], 1)
            self.assertRegex(receipt["payload"]["synthesis_id"], r"^synthesis-")
            self.assertRegex(receipt["payload"]["synthesis_artifact_id"], r"^artifact-coordinator-")
            self.assertEqual(receipt["payload"]["synthesis_usage_id"], "")
            self.assertEqual(receipt["payload"]["synthesis_input_artifact_count"], 4)
            self.assertEqual(receipt["payload"]["artifact_graph_node_count"], 4)
            self.assertEqual(receipt["payload"]["artifact_graph_edge_count"], 5)
            self.assertEqual(receipt["payload"]["artifact_ids"], [artifact["id"] for artifact in result.artifacts])
            self.assertEqual(receipt["payload"]["contract_version"], AGENT_CONTRACT_VERSION)
            self.assertEqual(receipt["payload"]["worker_contracts"][0]["role"], "planner")
            self.assertIn("Checkpoint plan", receipt["payload"]["worker_contracts"][0]["deliverable"])
            self.assertEqual(receipt["payload"]["worker_contracts"][0]["tool_budget_policy"]["budget_type"], "contract_metadata")
            self.assertEqual(receipt["payload"]["worker_contracts"][0]["tool_budget_policy"]["max_tool_calls"], 8)
            contracts_by_role = {contract["role"]: contract for contract in receipt["payload"]["worker_contracts"]}
            self.assertEqual(list(contracts_by_role), ["planner", "researcher", "implementer", "reviewer"])
            self.assertEqual(
                {role: contract["tool_budget_policy"]["max_tool_calls"] for role, contract in contracts_by_role.items()},
                {"planner": 8, "researcher": 12, "implementer": 16, "reviewer": 10},
            )
            self.assertFalse(contracts_by_role["planner"]["tool_budget_policy"]["may_edit"])
            self.assertFalse(contracts_by_role["researcher"]["tool_budget_policy"]["may_access_network"])
            self.assertTrue(contracts_by_role["implementer"]["tool_budget_policy"]["may_edit"])
            self.assertTrue(contracts_by_role["implementer"]["tool_budget_policy"]["may_run_tests"])
            self.assertFalse(contracts_by_role["reviewer"]["tool_budget_policy"]["may_edit"])
            self.assertTrue(contracts_by_role["reviewer"]["tool_budget_policy"]["may_run_tests"])
            self.assertIn("workspace_write", contracts_by_role["implementer"]["tool_budget_policy"]["allowed_tool_groups"])
            self.assertIn("workspace_write", contracts_by_role["reviewer"]["tool_budget_policy"]["denied_tool_groups"])
            self.assertEqual(len(result.artifacts), 5)
            self.assertEqual(result.root.final_synthesis["status"], "completed")
            self.assertFalse(result.root.final_synthesis["model_invocation_performed"])
            self.assertFalse(result.root.final_synthesis["external_model_invocation_performed"])
            self.assertEqual(result.root.final_synthesis["artifact_id"], result.root.artifacts[0]["id"])
            self.assertEqual(len(result.root.final_synthesis["artifact_graph"]["nodes"]), 4)
            artifact_rows = SubagentStore(paths).artifacts()
            self.assertEqual(len(artifact_rows), 5)
            planner_artifact = next(row for row in artifact_rows if row["role"] == "planner")
            synthesis_artifact = next(row for row in artifact_rows if row["role"] == "coordinator")
            self.assertEqual(synthesis_artifact["kind"], "final_synthesis")
            self.assertEqual(len(synthesis_artifact["artifact_graph"]["nodes"]), 4)
            self.assertEqual(len(synthesis_artifact["artifact_graph"]["edges"]), 5)
            shown_synthesis = SubagentStore(paths).artifact(synthesis_artifact["id"])
            self.assertIn("# Coordinator Final Synthesis", shown_synthesis["content"])
            self.assertIn("Artifact Graph", shown_synthesis["content"])
            shown_artifact = SubagentStore(paths).artifact(planner_artifact["id"])
            self.assertIn("# Planner Artifact", shown_artifact["content"])
            self.assertIn("Checkpoint plan", shown_artifact["content"])
            search_rows = SubagentStore(paths).search_artifacts("Checkpoint plan")
            self.assertTrue(any(row["id"] == planner_artifact["id"] for row in search_rows))
            self.assertIn("SUBAGENT ARTIFACTS", format_artifacts(artifact_rows))
            self.assertIn("SUBAGENT ARTIFACT", format_artifact(shown_artifact))
            self.assertIn("SUBAGENT ARTIFACT SEARCH", format_artifact_search("Checkpoint plan", search_rows))
            for worker in result.workers:
                self.assertEqual(len(worker.artifacts), 1)
                artifact = worker.artifacts[0]
                self.assertTrue(Path(artifact["path"]).exists())
                self.assertEqual(artifact["role"], worker.role)
                self.assertEqual(artifact["worker_id"], worker.id)
                self.assertEqual(artifact["raw_secret_values_included"], False)
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
            planner_artifact = next(worker.artifacts[0]["id"] for worker in result.workers if worker.role == "planner")
            researcher_artifact = next(worker.artifacts[0]["id"] for worker in result.workers if worker.role == "researcher")
            implementer_artifact = next(worker.artifacts[0]["id"] for worker in result.workers if worker.role == "implementer")
            self.assertEqual(next(worker.input_artifacts for worker in result.workers if worker.role == "planner"), [])
            self.assertEqual(next(worker.input_artifacts for worker in result.workers if worker.role == "researcher"), [])
            self.assertEqual(next(worker.input_artifacts for worker in result.workers if worker.role == "implementer"), [planner_artifact, researcher_artifact])
            self.assertEqual(next(worker.input_artifacts for worker in result.workers if worker.role == "reviewer"), [planner_artifact, researcher_artifact, implementer_artifact])
            planner = next(worker for worker in result.workers if worker.role == "planner")
            implementer = next(worker for worker in result.workers if worker.role == "implementer")
            planner_messages = SessionStore(paths).transcript(planner.session_id)
            implementer_messages = SessionStore(paths).transcript(implementer.session_id)
            self.assertEqual(planner_messages[0]["metadata"]["contract_version"], AGENT_CONTRACT_VERSION)
            self.assertIn("context_contract", planner_messages[0]["metadata"])
            self.assertIn("tool_budget_policy", planner_messages[0]["metadata"])

            self.assertEqual(planner_messages[0]["metadata"]["tool_budget_policy"]["max_tool_calls"], 8)
            self.assertFalse(planner_messages[0]["metadata"]["tool_budget_policy"]["may_edit"])
            self.assertIn("read", planner_messages[0]["metadata"]["tool_budget_policy"]["allowed_tool_groups"])
            self.assertIn("workspace_write", planner_messages[0]["metadata"]["tool_budget_policy"]["denied_tool_groups"])
            self.assertIn("Tool budget:", planner_messages[0]["content"])
            self.assertIn("Structured tool budget:", planner_messages[0]["content"])
            self.assertIn("max_tool_calls=8", planner_messages[0]["content"])
            self.assertIn("allowed=read, search, sessions, memory, audit", planner_messages[0]["content"])
            self.assertIn("may_edit=false", planner_messages[0]["content"])
            self.assertEqual(planner_messages[0]["metadata"]["input_artifacts"], [])
            self.assertEqual(implementer_messages[0]["metadata"]["input_artifacts"], [planner_artifact, researcher_artifact])
            self.assertTrue(implementer_messages[0]["metadata"]["tool_budget_policy"]["may_edit"])
            self.assertTrue(implementer_messages[0]["metadata"]["tool_budget_policy"]["may_run_tests"])
            self.assertIn("Structured tool budget:", implementer_messages[0]["content"])
            self.assertIn("max_tool_calls=16", implementer_messages[0]["content"])
            self.assertIn("allowed=read, search, workspace_write, tests, audit", implementer_messages[0]["content"])
            self.assertIn("may_edit=true", implementer_messages[0]["content"])
            self.assertIn("Checkpoint plan", planner_messages[-1]["content"])
            self.assertEqual(planner_messages[-1]["metadata"]["provider"], planner.provider)
            self.assertEqual(planner_messages[-1]["metadata"]["usage_id"], planner.usage_id)
            self.assertEqual(planner_messages[-1]["metadata"]["artifacts"][0]["id"], planner_artifact)
            event_types = [receipt["event_type"] for receipt in AuditLog(paths).recent(14)]
            self.assertEqual(event_types.count("subagent.worker.started"), 4)
            self.assertEqual(event_types.count("subagent.worker.completed"), 4)
            self.assertIn("subagent.coordinator.synthesis.completed", event_types)
            completed_receipts = [receipt for receipt in AuditLog(paths).recent(20) if receipt["event_type"] == "subagent.worker.completed"]
            self.assertEqual(len(completed_receipts), 4)
            self.assertTrue(all(receipt["payload"]["tool_budget_contract_checked"] for receipt in completed_receipts))
            self.assertTrue(all(receipt["payload"]["tool_budget_enforcement_scope"] == "artifact_cap_and_safety_flags" for receipt in completed_receipts))
            self.assertTrue(all(receipt["payload"]["tool_budget_policy"]["budget_type"] == "contract_metadata" for receipt in completed_receipts))
            self.assertFalse(any("tool_budget_enforced" in receipt["payload"] for receipt in completed_receipts))
            events = LocalSubagentOrchestrator(paths).events(result.root.id)
            self.assertEqual(events[0].event, "root.started")
            self.assertEqual(events[-1].event, "root.completed")
            self.assertEqual(sum(1 for event in events if event.event == "worker.started"), 4)
            self.assertIn("synthesis.completed", [event.event for event in events])
            self.assertIn("SUBAGENT TIMELINE", format_events(events))

    def test_local_subagent_orchestrator_depth_two_nests_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            orchestrator = LocalSubagentOrchestrator(paths)

            result = orchestrator.delegate("review implementation at depth two", requested_depth=2)

            self.assertEqual([worker.role for worker in result.workers], ["planner", "researcher", "implementer", "reviewer"])
            self.assertEqual([worker.depth for worker in result.workers], [1, 1, 1, 2])
            self.assertEqual(result.to_dict()["requested_depth"], 2)
            self.assertEqual(result.to_dict()["nested_worker_count"], 1)
            workers = {worker.role: worker for worker in result.workers}
            root = SubagentStore(paths).get(result.root.id)
            implementer = SubagentStore(paths).get(workers["implementer"].id)
            reviewer = SubagentStore(paths).get(workers["reviewer"].id)
            self.assertEqual(root.children, [workers["planner"].id, workers["researcher"].id, workers["implementer"].id])
            self.assertNotIn(workers["reviewer"].id, root.children)
            self.assertEqual(implementer.children, [workers["reviewer"].id])
            self.assertEqual(reviewer.parent_id, workers["implementer"].id)
            self.assertEqual(reviewer.depth, 2)
            planner_artifact = workers["planner"].artifacts[0]["id"]
            researcher_artifact = workers["researcher"].artifacts[0]["id"]
            implementer_artifact = workers["implementer"].artifacts[0]["id"]
            self.assertEqual(workers["reviewer"].input_artifacts, [planner_artifact, researcher_artifact, implementer_artifact])
            delegation = format_delegation(result)
            self.assertIn("depth     requested=2 nested_workers=1", delegation)
            receipt = AuditLog(paths).recent(1)[0]
            self.assertEqual(receipt["event_type"], "subagent.delegation.completed")
            self.assertEqual(receipt["payload"]["requested_depth"], 2)
            self.assertEqual(receipt["payload"]["actual_max_depth"], 2)
            self.assertEqual(receipt["payload"]["nested_worker_count"], 1)
            self.assertEqual(receipt["payload"]["worker_depths"], [1, 1, 1, 2])
            self.assertEqual(receipt["payload"]["worker_parent_ids"], [result.root.id, result.root.id, result.root.id, workers["implementer"].id])
            self.assertEqual(receipt["payload"]["tree_edges"][-1]["parent_id"], workers["implementer"].id)
            stopped = orchestrator.stop(result.root.id)
            self.assertEqual(len({record.id for record in stopped.stopped}), 5)
            self.assertEqual(len(stopped.stopped), 5)

            second = LocalSubagentOrchestrator(paths).delegate("stop nested implementer", requested_depth=2)
            second_workers = {worker.role: worker for worker in second.workers}
            nested_stop = LocalSubagentOrchestrator(paths).stop(second_workers["implementer"].id)
            self.assertEqual({record.id for record in nested_stop.stopped}, {second_workers["implementer"].id, second_workers["reviewer"].id})

    def test_local_subagent_orchestrator_rejects_depth_over_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)

            with self.assertRaisesRegex(ValueError, "exceeds limit 1"):
                LocalSubagentOrchestrator(paths, limits=SubagentLimits(max_depth=1)).delegate("too deep", requested_depth=2)

            self.assertEqual(SubagentStore(paths).list(), [])

    def test_cross_delegation_artifact_reuse_requires_approval_and_audits_safety_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            raw_secret = "sk-" + ("a" * 24)
            first = LocalSubagentOrchestrator(paths).delegate(f"seed artifact without leaking {raw_secret}")
            planner_artifact = next(worker.artifacts[0]["id"] for worker in first.workers if worker.role == "planner")

            with self.assertRaisesRegex(ValueError, "requires explicit approval"):
                LocalSubagentOrchestrator(paths).delegate("continue from prior", reusable_artifact_ids=[planner_artifact])

            blocked_audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("subagent.artifacts.reused", blocked_audit)

            second = LocalSubagentOrchestrator(paths).delegate("continue from prior", reusable_artifact_ids=[planner_artifact, planner_artifact], reuse_approved=True)

            self.assertEqual(second.root.input_artifacts, [planner_artifact])
            self.assertEqual(second.to_dict()["reused_artifact_ids"], [planner_artifact])
            self.assertEqual(second.to_dict()["reused_artifact_count"], 1)
            self.assertEqual(second.to_dict()["generated_artifact_count"], 5)
            self.assertEqual(second.to_dict()["root"]["final_synthesis"]["reused_artifact_ids"], [planner_artifact])
            self.assertEqual(len(second.artifacts), 5)
            for worker in second.workers:
                self.assertEqual(worker.input_artifacts[0], planner_artifact)
            self.assertIn("artifacts.reused", [event.event for event in second.events])

            audit_rows = [json.loads(line) for line in (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            reuse_receipt = next(row for row in audit_rows if row["event_type"] == "subagent.artifacts.reused")
            self.assertTrue(reuse_receipt["payload"]["approved"])
            self.assertEqual(reuse_receipt["payload"]["artifact_ids"], [planner_artifact])
            self.assertFalse(reuse_receipt["payload"]["browser_auto_launch"])
            self.assertFalse(reuse_receipt["payload"]["raw_secret_values_included"])
            self.assertFalse(reuse_receipt["payload"]["external_action_started"])
            self.assertFalse(reuse_receipt["payload"]["model_invocation_performed"])
            self.assertFalse(reuse_receipt["payload"]["artifacts"][0]["content_included"])
            completed = next(row for row in reversed(audit_rows) if row["event_type"] == "subagent.delegation.completed")
            self.assertEqual(completed["payload"]["artifact_count"], 5)
            self.assertEqual(completed["payload"]["generated_artifact_count"], 5)
            self.assertEqual(completed["payload"]["reused_artifact_ids"], [planner_artifact])
            self.assertEqual(completed["payload"]["synthesis_input_artifact_count"], 5)
            self.assertEqual(completed["payload"]["artifact_graph_node_count"], 5)
            self.assertEqual(completed["payload"]["artifact_graph_edge_count"], 9)
            self.assertFalse(completed["payload"]["browser_auto_launch"])
            self.assertFalse(completed["payload"]["raw_secret_values_included"])
            self.assertNotIn(raw_secret, json.dumps(audit_rows))

            artifact_row = SubagentStore(paths).artifact(planner_artifact, include_content=False)
            Path(artifact_row["path"]).write_text("tampered artifact\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "integrity validation failed"):
                LocalSubagentOrchestrator(paths).delegate("continue from tampered", reusable_artifact_ids=[planner_artifact], reuse_approved=True)

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

    def test_background_job_reuses_approved_artifacts_at_run_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            first = LocalSubagentOrchestrator(paths).delegate("seed reusable background context")
            planner_artifact = next(worker.artifacts[0]["id"] for worker in first.workers if worker.role == "planner")

            with self.assertRaisesRegex(ValueError, "requires explicit approval"):
                LocalSubagentOrchestrator(paths).start_background("background from prior", reusable_artifact_ids=[planner_artifact])

            blocked_audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertEqual(blocked_audit.count("subagent.artifacts.reused"), 0)

            job = BackgroundJobStore(paths).create(
                "background from prior",
                reusable_artifact_ids=[planner_artifact],
                reuse_approved=True,
            )
            result = LocalSubagentOrchestrator(paths).run_background_job(job.id)

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.reusable_artifact_ids, [planner_artifact])
            self.assertTrue(result.artifact_reuse_approved)
            root = SubagentStore(paths).get(result.root_id)
            self.assertEqual(root.input_artifacts, [planner_artifact])
            workers = [SubagentStore(paths).get(child_id) for child_id in root.children]
            self.assertTrue(all(worker.input_artifacts[0] == planner_artifact for worker in workers))
            self.assertIn("reuse     1 approved artifacts", format_background_job(result))
            listed_jobs = BackgroundJobStore(paths).list()
            self.assertEqual(listed_jobs[0]["requested_depth"], 1)
            self.assertEqual(listed_jobs[0]["reusable_artifact_count"], 1)
            self.assertIn("background from prior", format_background_jobs(listed_jobs))

            audit_rows = [json.loads(line) for line in (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            reuse_receipt = next(row for row in audit_rows if row["event_type"] == "subagent.artifacts.reused")
            self.assertEqual(reuse_receipt["payload"]["artifact_ids"], [planner_artifact])
            self.assertFalse(reuse_receipt["payload"]["browser_auto_launch"])
            self.assertFalse(reuse_receipt["payload"]["external_action_started"])
            self.assertFalse(reuse_receipt["payload"]["raw_secret_values_included"])
            self.assertFalse(reuse_receipt["payload"]["model_invocation_performed"])
            completed = next(row for row in reversed(audit_rows) if row["event_type"] == "subagent.background.completed")
            self.assertEqual(completed["payload"]["reusable_artifact_ids"], [planner_artifact])
            self.assertTrue(completed["payload"]["artifact_reuse_approved"])
            self.assertFalse(completed["payload"]["browser_auto_launch"])

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
