# Checkpoint 92: Skill Checksum Manifest

## Goal

Advance skill provenance from passive marker scanning to optional local checksum-manifest verification without adding dependencies or executing skills.

## Changes

- Added optional `aegis-skill-trust.json` sidecar support beside `SKILL.md`.
- Verifies `algorithm: sha256-bundle-v1` and `bundle_sha256` against the scanned skill bundle.
- Excludes trust manifests and `.sig` files from the signable bundle digest to avoid circular signatures.
- Reports manifest status, manifest SHA-256, declared bundle hash, signature status, issuer key id, and issuer public-key hash as redacted metadata.
- Keeps missing manifests acceptable.
- Quarantines invalid or mismatched manifests.
- Marks declared signatures as `declared_unverified` and keeps the skill in `review` until trusted-key verification exists.
- Fails closed on symlinked or unreadable bundle content.
- Audits redacted skill verification records without descriptions, absolute roots, raw signature values, browser use, network use, model calls, sends, or execution.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_cli.CliTests.test_skills_cli_surfaces_checksum_manifest_status tests.test_cli.CliTests.test_skills_cli_signature_metadata_is_unverified_and_redacted tests.test_tui.TuiRendererTests.test_interactive_dispatch_skills_surfaces_manifest_metadata -v
```

Additional verification:

```bash
PYTHONPATH=src python3 -m py_compile src/aegisagent/core/skills.py src/aegisagent/cli.py src/aegisagent/tui/interactive.py src/aegisagent/core/tools.py src/aegisagent/core/capabilities.py tests/test_memory_skills_subagents.py tests/test_cli.py tests/test_tui.py
sh -n scripts/install.sh && sh -n scripts/update.sh && git diff --check
PYTHONPATH=src python3 -m unittest discover -s tests -v
cd web && npm run verify
aegis skills --limit 1
```

Result: focused verification passed, full backend suite passed with 187 tests and 2 existing FastAPI skips, web build/smoke passed, shell/diff checks passed, and installed `aegis skills` smoke passed.

## Remaining Work

- Add trusted-key cryptographic signature verification.
- Add an approved skill execution policy flow after trust metadata is mature.
- Add a manifest authoring command once the manifest schema is stable.
