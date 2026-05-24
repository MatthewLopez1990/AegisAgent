# Checkpoint 93: Skill Manifest Authoring

## Goal

Let operators create checksum-only skill trust manifests from the terminal without hand-calculating bundle hashes.

## Changes

- Added `aegis skills manifest <skill-name>` preview mode.
- Added approval-gated `aegis skills manifest <skill-name> --approved` writes.
- Added `/skills manifest <skill-name> | approve` TUI parity.
- Reused the existing skill bundle hash scanner and deterministic manifest JSON shape.
- Blocks unsafe selectors, ambiguous skill names, symlinked manifest paths, unsafe bundles, and different existing manifests.
- Returns `already_current` when the existing manifest exactly matches the current bundle.
- Writes new manifests with exclusive create semantics instead of following existing paths.
- Audits manifest previews/writes with redacted skill id, scope, relative path, bundle hash, manifest hashes, approval, force, and mutation booleans.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_skill_loader_authors_manifest_preview_and_approved_write tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_skill_loader_manifest_author_blocks_existing_manifest_without_force tests.test_memory_skills_subagents.MemorySkillsSubagentTests.test_skill_loader_manifest_author_blocks_different_existing_manifest_even_with_force tests.test_cli.CliTests.test_skills_manifest_cli_is_approval_gated_and_audited tests.test_tui.TuiRendererTests.test_interactive_dispatch_skills_manifest_preview_apply_flow tests.test_policy.PolicyTests.test_skill_manifest_preview_allowed_but_apply_is_gated -v
```

Additional verification:

```bash
PYTHONPATH=src python3 -m py_compile src/aegisagent/core/skills.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/security/policy.py src/aegisagent/core/tools.py src/aegisagent/core/capabilities.py tests/test_memory_skills_subagents.py tests/test_cli.py tests/test_tui.py tests/test_policy.py
sh -n scripts/install.sh && sh -n scripts/update.sh && git diff --check
PYTHONPATH=src python3 -m unittest discover -s tests -v
cd web && npm run verify
aegis skills manifest ghost
```

Result: focused tests passed, full backend suite passed with 193 tests and 2 existing FastAPI skips, web build/smoke passed, shell/diff checks passed, and installed `aegis skills manifest ghost` returned a clean blocked JSON response.

## Remaining Work

- Add trusted-key cryptographic signature verification.
- Add manifest replacement with compare-and-swap if operators need managed rotation.
- Add policy-integrated skill execution approvals after trust metadata is mature.
