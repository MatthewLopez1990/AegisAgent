# Checkpoint 91: Skill Trust Metadata

## Goal

Make skill discovery safer and clearer from the terminal without introducing skill execution.

## Changes

- Added deterministic passive trust metadata for local `SKILL.md` discovery:
  - stable `skill_id`
  - content and bundle SHA-256 hashes
  - source scope, relative path, allowed root, file size, truncation, and path-safety flags
  - redacted descriptions, findings, and evidence snippets
  - `trusted`, `review`, and `quarantined` posture with safety flags showing no execution, network, model, browser, or send action occurred
- Updated `aegis skills` to emit the shared `AEGIS SKILL TRUST` summary and append a redacted `skills.discover` audit receipt.
- Updated `/skills` to show the same trust summary, capped to 10 skills for TUI readability.
- Updated setup checks and the capability map so skills are visible as passive trust metadata rather than raw discovery only.
- Split policy behavior so passive skill discovery is allowed while future skill execution or mutation is approval-gated.
- Updated README and operator reference with install-era skill usage and safety expectations.

## Verification

```bash
PYTHONPATH=src python3 -m unittest tests.test_memory_skills_subagents tests.test_cli.CliTests.test_skills_cli_reports_trust_summary_and_safety_flags tests.test_tui.TuiRendererTests.test_interactive_dispatch_skills_reports_trust_summary tests.test_policy.PolicyTests.test_skill_discovery_is_passive_but_execution_is_gated -v
```

Result: passed.

## Remaining Work

- Add signed skill bundle verification.
- Add explicit operator approval flows before any future skill execution.
- Add richer provenance for multi-file skill bundles and external marketplace sources.
