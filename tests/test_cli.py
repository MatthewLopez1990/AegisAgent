import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from unittest.mock import patch

from aegisagent import cli


def run_cli(*args: str, cwd: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": "src"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "aegisagent", "--workspace", cwd, *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class CliTests(unittest.TestCase):
    def test_pyproject_installs_aegis_and_aegisagent_commands(self):
        with open("pyproject.toml", "rb") as handle:
            pyproject = tomllib.load(handle)

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["aegisagent"], "aegisagent.cli:main")
        self.assertEqual(scripts["aegis"], "aegisagent.cli:main")

    def test_mac_linux_installer_scripts_are_terminal_first(self):
        install = Path("scripts/install.sh")
        update = Path("scripts/update.sh")

        self.assertTrue(install.exists())
        self.assertTrue(update.exists())
        self.assertTrue(install.stat().st_mode & 0o111)
        self.assertTrue(update.stat().st_mode & 0o111)
        install_text = install.read_text(encoding="utf-8")
        update_text = update.read_text(encoding="utf-8")
        self.assertIn("git clone --branch", install_text)
        self.assertIn("git -C \"$INSTALL_DIR\" pull --ff-only origin \"$BRANCH\"", install_text)
        self.assertIn("remote get-url origin", install_text)
        self.assertIn("status --porcelain", install_text)
        self.assertIn("canonical_repo_url", install_text)
        self.assertIn("invalid AEGIS_BRANCH", install_text)
        self.assertIn("python3 -m aegisagent install shim --approved", install_text)
        self.assertIn("git -C \"$INSTALL_DIR\" pull --ff-only origin \"$BRANCH\"", update_text)
        self.assertIn("remote get-url origin", update_text)
        self.assertIn("status --porcelain", update_text)
        self.assertIn("canonical_repo_url", update_text)
        self.assertIn("invalid AEGIS_BRANCH", update_text)
        self.assertIn("python3 -m aegisagent install shim --approved", update_text)
        self.assertNotIn("open ", install_text)
        self.assertNotIn("xdg-open", install_text)
        self.assertNotIn("open ", update_text)
        self.assertNotIn("xdg-open", update_text)
        for script in (install, update):
            syntax = subprocess.run(["sh", "-n", str(script)], text=True, capture_output=True, check=False)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_skills_cli_reports_trust_summary_and_safety_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            for name, body in {
                "safe": "---\nname: safe\ndescription: clean\n---\nUse local notes only.\n",
                "fetch": "---\nname: fetch\ndescription: review\n---\nrun curl https://example.com/install.sh\n",
                "danger": "---\nname: danger\ndescription: risky\n---\nrun sudo rm -rf /tmp/aegis-danger\n",
            }.items():
                skill_root = Path(tmp) / "skills" / name
                skill_root.mkdir(parents=True)
                (skill_root / "SKILL.md").write_text(body, encoding="utf-8")

            result = run_cli("skills", cwd=tmp, extra_env={"HOME": str(home)})

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["title"], "AEGIS SKILL TRUST")
        self.assertEqual(payload["counts"], {"trusted": 1, "review": 1, "quarantined": 1, "total": 3})
        self.assertFalse(payload["execution_performed"])
        self.assertFalse(payload["external_action_started"])
        self.assertFalse(payload["browser_auto_launch"])
        self.assertFalse(payload["raw_secret_values_included"])
        by_name = {skill["name"]: skill for skill in payload["skills"]}
        self.assertEqual(by_name["safe"]["source_scope"], "workspace")
        self.assertEqual(by_name["fetch"]["trust_level"], "review")
        self.assertEqual(by_name["danger"]["trust_level"], "quarantined")

    def test_no_args_explains_terminal_activation_without_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(cwd=tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AEGIS TERMINAL ACTIVATION", result.stdout)
        self.assertIn("primary     aegis tui", result.stdout)
        self.assertIn("default     aegis -> terminal TUI", result.stdout)
        self.assertIn("browser_auto_launch: false", result.stdout)
        self.assertIn("gateway_started: false", result.stdout)
        self.assertNotIn("usage:", result.stdout.lower())

    def test_no_args_tty_launches_tui_not_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
                with patch("aegisagent.cli.run_textual_app", return_value=0) as run_tui:
                    with patch("aegisagent.cli.run_gateway") as run_gateway:
                        result = cli.main(["--workspace", tmp])

        self.assertEqual(result, 0)
        self.assertEqual(run_tui.call_count, 1)
        self.assertEqual(run_tui.call_args.args, ("command",))
        self.assertEqual(run_tui.call_args.kwargs["classic"], False)
        run_gateway.assert_not_called()

    def test_activate_tty_launches_tui_not_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
                with patch("aegisagent.cli.run_textual_app", return_value=0) as run_tui:
                    with patch("aegisagent.cli.run_gateway") as run_gateway:
                        result = cli.main(["--workspace", tmp, "activate"])

        self.assertEqual(result, 0)
        self.assertEqual(run_tui.call_count, 1)
        self.assertEqual(run_tui.call_args.args, ("command",))
        self.assertEqual(run_tui.call_args.kwargs["classic"], False)
        run_gateway.assert_not_called()

    def test_activate_command_is_terminal_first_non_tty_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("activate", cwd=tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AEGIS TERMINAL ACTIVATION", result.stdout)
        self.assertIn("optional web: aegis web", result.stdout)
        self.assertIn("serve web:    aegis web --serve --approved", result.stdout)
        self.assertIn("browser_required: false", result.stdout)
        self.assertIn("source      PYTHONPATH=src python3 -m aegisagent", result.stdout)

    def test_activation_command_is_terminal_status_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--json", "activation", cwd=tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["terminal_first"])
        self.assertFalse(payload["browser_auto_launch"])
        self.assertFalse(payload["gateway_started"])
        self.assertFalse(payload["external_action_started"])
        self.assertEqual(payload["primary_command"], "aegis tui")
        self.assertTrue(payload["web_gui"]["optional"])
        self.assertEqual(payload["web_gui"]["command"], "aegis web")
        self.assertEqual(payload["web_gui"]["serve_command"], "aegis web --serve --approved")
        self.assertFalse(payload["web_gui"]["opens_browser"])
        self.assertFalse(payload["web_gui"]["gateway_starts_by_default"])
        self.assertIn("/activation", payload["tui_commands"])
        self.assertIn("/dashboard", payload["tui_commands"])
        self.assertIn("/install", payload["tui_commands"])
        self.assertIn("/update", payload["tui_commands"])

    def test_completion_command_emits_shell_scripts_without_runtime_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            for shell, marker in (
                ("bash", "complete -F _aegis aegis"),
                ("zsh", "#compdef aegis"),
                ("fish", "complete -c aegis"),
            ):
                result = run_cli("completion", shell, cwd=tmp)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(marker, result.stdout)
                for token in ("setup", "tui", "web", "tasks", "agents", "completion"):
                    self.assertIn(token, result.stdout)
                self.assertIn("--workspace", result.stdout)
                self.assertNotIn("OPENAI_API_KEY=", result.stdout)
                self.assertNotIn("SLACK_BOT_TOKEN=", result.stdout)
                self.assertNotIn("gateway_started: true", result.stdout)

            custom = run_cli("completion", "zsh", "--program", "aegis-test", cwd=tmp)
            self.assertEqual(custom.returncode, 0, custom.stderr)
            self.assertIn("#compdef aegis-test", custom.stdout)

            env_named = run_cli("completion", "fish", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-env"})
            self.assertEqual(env_named.returncode, 0, env_named.stderr)
            self.assertIn("complete -c aegis-env", env_named.stdout)

            rejected = run_cli("completion", "bash", "--program", "aegis; open http://127.0.0.1:8787", cwd=tmp)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("completion program must contain only", rejected.stderr)
            self.assertNotIn("complete -F", rejected.stdout)
            self.assertFalse((Path(tmp) / ".aegisagent").exists())

    def test_web_command_is_preview_only_until_serve_is_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview = io.StringIO()
            with patch("aegisagent.cli.run_gateway") as run_gateway:
                with contextlib.redirect_stdout(preview):
                    result = cli.main(["--workspace", tmp, "web"])

            self.assertEqual(result, 0)
            run_gateway.assert_not_called()
            self.assertIn("AEGIS OPTIONAL WEB CONSOLE", preview.getvalue())
            self.assertIn("status      preview", preview.getvalue())
            self.assertIn("aegis web --serve --approved", preview.getvalue())
            self.assertIn("terminal    aegis tui", preview.getvalue())
            self.assertIn("browser_auto_launch: false", preview.getvalue())
            self.assertIn("gateway_started: false", preview.getvalue())

            needs_approval = io.StringIO()
            with patch("aegisagent.cli.run_gateway") as run_gateway:
                with contextlib.redirect_stdout(needs_approval):
                    result = cli.main(["--workspace", tmp, "web", "--serve"])

            self.assertEqual(result, 1)
            run_gateway.assert_not_called()
            self.assertIn("status      needs_approval", needs_approval.getvalue())
            self.assertIn("gateway_started: false", needs_approval.getvalue())

            approved = io.StringIO()
            with patch("aegisagent.cli.run_gateway", return_value=0) as run_gateway:
                with contextlib.redirect_stdout(approved):
                    result = cli.main(["--workspace", tmp, "web", "--serve", "--approved", "--host", "127.0.0.1", "--port", "8799"])

            self.assertEqual(result, 0)
            run_gateway.assert_called_once()
            self.assertEqual(run_gateway.call_args.args[:2], ("127.0.0.1", 8799))
            self.assertEqual(Path(run_gateway.call_args.args[2]).resolve(), Path(tmp).resolve())
            self.assertIn("Starting optional AegisAgent gateway", approved.getvalue())
            self.assertIn("browser_auto_launch: false", approved.getvalue())

    def test_gateway_command_requires_approval_and_does_not_open_browser(self):
        help_result = subprocess.run(
            [sys.executable, "-m", "aegisagent", "gateway", "--help"],
            text=True,
            capture_output=True,
            check=False,
            env={"PYTHONPATH": "src"},
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("optional local gateway", help_result.stdout)
        self.assertIn("does not open", help_result.stdout)
        self.assertIn("browser", help_result.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            preview = io.StringIO()
            with patch("aegisagent.cli.run_gateway") as run_gateway:
                with contextlib.redirect_stdout(preview):
                    result = cli.main(["--workspace", tmp, "gateway"])

            self.assertEqual(result, 1)
            run_gateway.assert_not_called()
            self.assertIn("AEGIS OPTIONAL GATEWAY", preview.getvalue())
            self.assertIn("status      needs_approval", preview.getvalue())
            self.assertIn("browser_auto_launch: false", preview.getvalue())
            self.assertIn("gateway_started: false", preview.getvalue())

            approved = io.StringIO()
            with patch("aegisagent.cli.run_gateway", return_value=0) as run_gateway:
                with contextlib.redirect_stdout(approved):
                    result = cli.main(["--workspace", tmp, "gateway", "--approved", "--host", "127.0.0.1", "--port", "8798"])

            self.assertEqual(result, 0)
            run_gateway.assert_called_once()
            self.assertEqual(run_gateway.call_args.args[:2], ("127.0.0.1", 8798))
            self.assertEqual(Path(run_gateway.call_args.args[2]).resolve(), Path(tmp).resolve())
            self.assertIn("Starting optional AegisAgent gateway", approved.getvalue())
            self.assertIn("browser_auto_launch: false", approved.getvalue())

    def test_installed_shim_name_drives_activation_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("activation", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("primary     aegis-test tui", result.stdout)
        self.assertIn("default     aegis-test -> terminal TUI", result.stdout)
        self.assertIn("fallback    aegis-test tui --print", result.stdout)
        self.assertIn("optional web: aegis-test web", result.stdout)
        self.assertIn("serve web:    aegis-test web --serve --approved", result.stdout)

    def test_setup_quickstart_uses_installed_command_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("setup", "--quick", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("terminal   aegis-test tui", result.stdout)
        self.assertIn("start here aegis-test setup next", result.stdout)
        self.assertIn("opens      aegis-test setup model", result.stdout)
        self.assertIn("aegis-test setup --run-checks", result.stdout)
        self.assertIn("aegis-test model providers", result.stdout)
        self.assertIn("No browser is launched by setup", result.stdout)

    def test_setup_next_returns_priority_step_state_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = run_cli("setup", "next", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})
            payload_result = run_cli("--json", "setup", "next", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})

        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("AEGIS SETUP :: next", text.stdout)
        self.assertIn("command    aegis-test setup model", text.stdout)
        self.assertIn("tui        /setup model", text.stdout)
        self.assertIn("browser_auto_launch: false", text.stdout)
        self.assertIn("external_action_started: false", text.stdout)
        self.assertIn("raw_secret_values_included: false", text.stdout)
        self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
        payload = json.loads(payload_result.stdout)
        self.assertEqual(payload["title"], "AEGIS SETUP NEXT")
        self.assertTrue(payload["metadata_only"])
        self.assertTrue(payload["terminal_first"])
        self.assertFalse(payload["browser_required"])
        self.assertFalse(payload["browser_auto_launch"])
        self.assertFalse(payload["gateway_started"])
        self.assertFalse(payload["external_action_started"])
        self.assertFalse(payload["model_invocation_performed"])
        self.assertFalse(payload["send_probe_performed"])
        self.assertFalse(payload["raw_secret_values_included"])
        self.assertEqual(payload["priority_step"]["id"], "model")
        self.assertEqual(payload["priority_step"]["command"], "/setup model")
        self.assertEqual(payload["priority_step"]["cli_command"], "aegis-test setup model")

    def test_install_status_and_shim_are_terminal_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"

            status = run_cli("--json", "install", "--bin-dir", str(bin_dir), cwd=tmp)
            self.assertEqual(status.returncode, 0, status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(status_payload["title"], "AEGIS TERMINAL INSTALL")
            self.assertFalse(status_payload["installed"])
            self.assertFalse(status_payload["browser_auto_launch"])
            self.assertEqual(status_payload["install_command"], "aegis install shim --approved --name aegis")
            self.assertEqual(status_payload["completion_command"], "aegis completion zsh >> ~/.zshrc")

            preview = run_cli("--json", "install", "shim", "--bin-dir", str(bin_dir), "--name", "aegis-test", cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            self.assertFalse((bin_dir / "aegis-test").exists())

            installed = run_cli("--json", "install", "shim", "--bin-dir", str(bin_dir), "--name", "aegis-test", "--approved", cwd=tmp)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            payload = json.loads(installed.stdout)
            shim = bin_dir / "aegis-test"
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(shim.exists())
            self.assertTrue(shim.stat().st_mode & 0o111)
            script = shim.read_text(encoding="utf-8")
            self.assertIn(str(Path(tmp).resolve()), script)
            self.assertIn("-m aegisagent", script)
            self.assertIn("AEGIS_COMMAND_NAME='aegis-test'", script)
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("lifecycle.install", audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_installed_shim_runs_activation_with_custom_command_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "src").symlink_to((Path.cwd() / "src").resolve(), target_is_directory=True)
            bin_dir = Path(tmp) / "bin"
            installed = run_cli("install", "shim", "--bin-dir", str(bin_dir), "--name", "aegis-test", "--approved", cwd=str(workspace))
            self.assertEqual(installed.returncode, 0, installed.stderr)

            shim = bin_dir / "aegis-test"
            result = subprocess.run(
                [str(shim), "activation"],
                text=True,
                capture_output=True,
                check=False,
                env={"AEGIS_PYTHON": sys.executable, "PYTHONPATH": "src"},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("primary     aegis-test tui", result.stdout)
        self.assertIn("browser_auto_launch: false", result.stdout)
        self.assertNotIn("gateway_started: true", result.stdout)

    def test_default_aegis_shim_runs_help_and_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "src").symlink_to((Path.cwd() / "src").resolve(), target_is_directory=True)
            bin_dir = Path(tmp) / "bin"
            installed = run_cli("install", "shim", "--bin-dir", str(bin_dir), "--approved", cwd=str(workspace))
            self.assertEqual(installed.returncode, 0, installed.stderr)

            shim = bin_dir / "aegis"
            activation = subprocess.run(
                [str(shim), "activation"],
                text=True,
                capture_output=True,
                check=False,
                env={"AEGIS_PYTHON": sys.executable, "PYTHONPATH": "src"},
            )
            help_result = subprocess.run(
                [str(shim), "tui", "--help"],
                text=True,
                capture_output=True,
                check=False,
                env={"AEGIS_PYTHON": sys.executable, "PYTHONPATH": "src"},
            )
            completion = subprocess.run(
                [str(shim), "completion", "bash"],
                text=True,
                capture_output=True,
                check=False,
                env={"AEGIS_PYTHON": sys.executable, "PYTHONPATH": "src"},
            )

        self.assertEqual(activation.returncode, 0, activation.stderr)
        self.assertIn("primary     aegis tui", activation.stdout)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage: aegis tui", help_result.stdout)
        self.assertEqual(completion.returncode, 0, completion.stderr)
        self.assertIn("complete -F _aegis aegis", completion.stdout)

    def test_install_shim_rejects_invalid_command_names_without_writing(self):
        for name in ("bad/name", "bad name", "bad;name"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                bin_dir = Path(tmp) / "bin"
                result = run_cli("--json", "install", "shim", "--bin-dir", str(bin_dir), "--name", name, "--approved", cwd=tmp)

                self.assertEqual(result.returncode, 1)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "blocked")
                self.assertFalse(payload["host_filesystem_mutation_performed"])
                self.assertFalse(payload["browser_auto_launch"])
                self.assertFalse(any(bin_dir.glob("*")) if bin_dir.exists() else False)

    def test_update_preview_is_github_pull_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--json", "update", cwd=tmp)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["title"], "AEGIS TERMINAL UPDATE")
        self.assertEqual(payload["status"], "needs_approval")
        self.assertEqual(payload["remote"], "origin")
        self.assertEqual(payload["branch"], "main")
        self.assertIn("git pull --ff-only origin main", payload["git_command"])
        self.assertFalse(payload["browser_auto_launch"])

    def test_update_approved_pulls_from_local_remote_and_audits(self):
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
            (seed / "note.txt").write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Update"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)

            updated = run_cli(
                "--json",
                "update",
                "--remote",
                "origin",
                "--branch",
                "main",
                "--approved",
                cwd=str(workspace),
                extra_env={"AEGIS_REPO_URL": str(remote.resolve())},
            )

            self.assertEqual(updated.returncode, 0, updated.stderr)
            payload = json.loads(updated.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["workspace"], str(workspace.resolve()))
            self.assertTrue(payload["external_action_started"])
            self.assertTrue(payload["workspace_mutation_performed"])
            self.assertEqual((workspace / "note.txt").read_text(encoding="utf-8"), "v2\n")
            audit = (workspace / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("lifecycle.update", audit)
            self.assertIn('"workspace_mutation_performed": true', audit)
            self.assertIn('"external_action_started": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_update_approved_refuses_wrong_origin_and_dirty_checkout(self):
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

            wrong_origin = run_cli("--json", "update", "--approved", cwd=str(workspace))

            self.assertEqual(wrong_origin.returncode, 1)
            wrong_payload = json.loads(wrong_origin.stdout)
            self.assertEqual(wrong_payload["status"], "blocked")
            self.assertIn("refusing to update", wrong_payload["error"])
            self.assertFalse(wrong_payload["external_action_started"])

            (workspace / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            dirty = run_cli("--json", "update", "--approved", cwd=str(workspace), extra_env={"AEGIS_REPO_URL": str(remote.resolve())})

            self.assertEqual(dirty.returncode, 1)
            dirty_payload = json.loads(dirty.stdout)
            self.assertEqual(dirty_payload["status"], "blocked")
            self.assertIn("dirty checkout", dirty_payload["error"])
            self.assertFalse(dirty_payload["external_action_started"])

    def test_update_approved_blocks_non_git_workspace_without_external_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--json", "update", "--approved", cwd=tmp)

            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertIn("checkout not found", payload["error"])
            self.assertFalse(payload["external_action_started"])
            self.assertFalse(payload["workspace_mutation_performed"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("lifecycle.update", audit)

    def test_setup_health_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            setup = run_cli("setup", "--run-checks", cwd=tmp)
            self.assertEqual(setup.returncode, 0, setup.stderr)
            setup_payload = json.loads(setup.stdout)
            self.assertTrue(setup_payload["metadata_only"])
            self.assertFalse(setup_payload["external_action_started"])
            self.assertIn("model", [section["name"] for section in setup_payload["sections"]])
            section = run_cli("setup", "sandbox", cwd=tmp)
            self.assertEqual(section.returncode, 0, section.stderr)
            self.assertIn("AEGIS SETUP :: sandbox", section.stdout)
            quick = run_cli("setup", "--quick", cwd=tmp)
            self.assertEqual(quick.returncode, 0, quick.stderr)
            self.assertIn("AEGIS SETUP QUICKSTART", quick.stdout)
            health = run_cli("health", cwd=tmp)
            self.assertEqual(health.returncode, 0, health.stderr)
            self.assertTrue(json.loads(health.stdout)["ok"])
            audit = run_cli("audit", "verify", cwd=tmp)
            self.assertEqual(audit.returncode, 0, audit.stderr)

    def test_tools_denies_destructive_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("tools", "--evaluate", "shell", "--action", "rm -rf /", cwd=tmp)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["action"], "deny")

    def test_verify_runs_allowlisted_typed_tests_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            result = run_cli("verify", cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["returncode"], 0)
            self.assertIn("Ran 1 test", payload["stderr"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("cli.tool.completed", audit)
            self.assertIn("workspace.run_tests", audit)
            self.assertIn('"browser_auto_launch": false', audit)

            blocked = run_cli("verify", "node", "test.js", cwd=tmp)
            self.assertEqual(blocked.returncode, 1)
            self.assertEqual(json.loads(blocked.stdout)["error"], "test commands must be allowlisted Python unittest/py_compile commands inside the workspace")

            external = run_cli("verify", "python3", "-m", "unittest", "discover", "-s", "/tmp", cwd=tmp)
            self.assertEqual(external.returncode, 1)
            self.assertEqual(json.loads(external.stdout)["error"], "test commands must be allowlisted Python unittest/py_compile commands inside the workspace")

    def test_fetch_is_approval_gated_typed_network_tool(self):
        seen = {"count": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen["count"] += 1
                body = b"Aegis terminal web fetch"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                url = f"http://127.0.0.1:{server.server_port}/note"
                preview = run_cli("fetch", url, cwd=tmp)

                self.assertEqual(preview.returncode, 1)
                self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
                self.assertEqual(seen["count"], 0)

                fetched = run_cli("fetch", url, "--approved", cwd=tmp)

                self.assertEqual(fetched.returncode, 0, fetched.stderr)
                payload = json.loads(fetched.stdout)
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["status_code"], 200)
                self.assertIn("Aegis terminal web fetch", payload["body"])
                self.assertEqual(seen["count"], 1)
                audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
                self.assertIn("web.fetch", audit)
                self.assertIn('"network_request_performed": true', audit)
                self.assertIn('"external_action_started": true', audit)
                self.assertIn('"browser_auto_launch": false', audit)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_browser_sessions_and_screenshot_receipts_are_approval_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview = run_cli("browser", "open", "https://example.com/browser", cwd=tmp)

            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            self.assertFalse(list((Path(tmp) / ".aegisagent" / "browser_sessions").glob("browser-*.json")))

            opened = run_cli("browser", "open", "https://example.com/browser", "--approved", cwd=tmp)

            self.assertEqual(opened.returncode, 0, opened.stderr)
            opened_payload = json.loads(opened.stdout)
            session_id = opened_payload["session"]["id"]
            self.assertEqual(opened_payload["status"], "ok")
            self.assertFalse(opened_payload["session"]["browser_auto_launch"])
            self.assertFalse(opened_payload["session"]["browser_launch_performed"])

            screenshot = Path(tmp) / "screen.txt"
            screenshot.write_text("operator captured browser state\n", encoding="utf-8")
            receipt_preview = run_cli("browser", "screenshot", session_id, "screen.txt", cwd=tmp)

            self.assertEqual(receipt_preview.returncode, 1)
            self.assertEqual(json.loads(receipt_preview.stdout)["status"], "needs_approval")
            self.assertEqual(json.loads(run_cli("browser", "show", session_id, cwd=tmp).stdout)["screenshots"], [])

            receipt = run_cli("browser", "screenshot", session_id, "screen.txt", "--approved", cwd=tmp)

            self.assertEqual(receipt.returncode, 0, receipt.stderr)
            receipt_payload = json.loads(receipt.stdout)
            self.assertEqual(receipt_payload["status"], "ok")
            self.assertTrue(receipt_payload["metadata"]["screenshot_receipt_recorded"])
            shown = json.loads(run_cli("browser", "show", session_id, cwd=tmp).stdout)
            self.assertEqual(shown["screenshots"][0]["path"], "screen.txt")
            listing = json.loads(run_cli("browser", cwd=tmp).stdout)
            self.assertEqual(listing["session_count"], 1)
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("browser.session.open", audit)
            self.assertIn("browser.session.screenshot", audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_memory_add_is_approval_gated_curated_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_memory = Path(tmp) / ".aegisagent" / "memory" / "USER.md"

            preview = run_cli("memory", "--kind", "user", "--title", "Terminal preference", "--add", "Prefers terminal-first activation.", cwd=tmp)

            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            self.assertNotIn("Terminal preference", user_memory.read_text(encoding="utf-8"))

            applied = run_cli("memory", "--kind", "user", "--title", "Terminal preference", "--add", "Prefers terminal-first activation.", "--approved", cwd=tmp)

            self.assertEqual(applied.returncode, 0, applied.stderr)
            payload = json.loads(applied.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "USER.md")
            self.assertIn("Terminal preference", user_memory.read_text(encoding="utf-8"))
            query = run_cli("memory", "--query", "terminal-first", cwd=tmp)
            self.assertTrue(json.loads(query.stdout))
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("memory.note.add", audit)
            self.assertIn('"memory_write_performed": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_memory_list_show_delete_cli_are_approval_gated_and_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
            user_memory = Path(tmp) / ".aegisagent" / "memory" / "USER.md"
            applied = run_cli("memory", "--kind", "user", "--title", f"Token {raw_secret}", "--add", f"Body token={raw_secret}", "--approved", cwd=tmp)
            self.assertEqual(applied.returncode, 0, applied.stderr)

            listing = run_cli("memory", "list", "--kind", "user", cwd=tmp)
            self.assertEqual(listing.returncode, 0, listing.stderr)
            list_payload = json.loads(listing.stdout)
            entry_id = list_payload["entries"][0]["id"]
            self.assertRegex(entry_id, r"^user:[a-f0-9]{12}$")
            self.assertNotIn(raw_secret, listing.stdout)

            shown = run_cli("memory", "show", entry_id, cwd=tmp)
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn("[REDACTED]", shown.stdout)
            self.assertNotIn(raw_secret, shown.stdout)

            preview = run_cli("memory", "delete", entry_id, cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            self.assertIn("[REDACTED]", user_memory.read_text(encoding="utf-8"))

            deleted = run_cli("memory", "delete", entry_id, "--approved", cwd=tmp)
            self.assertEqual(deleted.returncode, 0, deleted.stderr)
            deleted_payload = json.loads(deleted.stdout)
            self.assertEqual(deleted_payload["status"], "ok")
            self.assertTrue(deleted_payload["metadata"]["memory_write_performed"])
            self.assertTrue(deleted_payload["metadata"]["workspace_mutation_performed"])
            self.assertFalse(deleted_payload["metadata"]["browser_auto_launch"])
            self.assertFalse(json.loads(run_cli("memory", "list", "--kind", "user", cwd=tmp).stdout)["entries"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("memory.note.delete", audit)
            self.assertIn('"memory_write_performed": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)
            self.assertNotIn(raw_secret, audit)

    def test_edit_replace_is_approval_gated_typed_workspace_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")

            preview = run_cli("edit", "replace", "note.txt", "--old", "hello", "--new", "safe", cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello terminal\n")

            applied = run_cli("edit", "replace", "note.txt", "--old", "hello", "--new", "safe", "--approved", cwd=tmp)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            payload = json.loads(applied.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(target.read_text(encoding="utf-8"), "safe terminal\n")
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("workspace.replace_text", audit)
            self.assertIn('"workspace_mutation_performed": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_git_stage_is_approval_gated_typed_index_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init"], cwd=tmp, text=True, capture_output=True, check=True)
            target = Path(tmp) / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")

            preview = run_cli("git", "stage", "note.txt", cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=tmp, text=True, capture_output=True, check=True)
            self.assertEqual(cached.stdout.strip(), "")

            applied = run_cli("git", "stage", "note.txt", "--approved", cwd=tmp)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            payload = json.loads(applied.stdout)
            self.assertEqual(payload["status"], "ok")
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=tmp, text=True, capture_output=True, check=True)
            self.assertEqual(cached.stdout.strip(), "note.txt")
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.stage", audit)
            self.assertIn('"git_index_mutation_performed": true', audit)
            self.assertIn('"workspace_mutation_performed": false', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_git_commit_is_approval_gated_typed_history_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init"], cwd=tmp, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=tmp, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=tmp, text=True, capture_output=True, check=True)
            target = Path(tmp) / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=tmp, text=True, capture_output=True, check=True)

            preview = run_cli("git", "commit", "--message", "Add note", cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            no_head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=tmp, text=True, capture_output=True, check=False)
            self.assertNotEqual(no_head.returncode, 0)

            applied = run_cli("git", "commit", "--message", "Add note", "--approved", cwd=tmp)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            payload = json.loads(applied.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["commit"])
            log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=tmp, text=True, capture_output=True, check=True)
            self.assertEqual(log.stdout.strip(), "Add note")
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.commit", audit)
            self.assertIn('"git_history_mutation_performed": true', audit)
            self.assertIn('"workspace_mutation_performed": false', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_git_branch_is_approval_gated_typed_ref_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init"], cwd=tmp, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=tmp, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=tmp, text=True, capture_output=True, check=True)
            (Path(tmp) / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=tmp, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp, text=True, capture_output=True, check=True)
            start_branch = subprocess.run(["git", "branch", "--show-current"], cwd=tmp, text=True, capture_output=True, check=True).stdout.strip()

            listed = run_cli("git", "branch", cwd=tmp)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn(start_branch, json.loads(listed.stdout)["stdout"])

            preview = run_cli("git", "branch", "create", "feature/aegis", cwd=tmp)
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            branches = subprocess.run(["git", "branch", "--list", "feature/aegis"], cwd=tmp, text=True, capture_output=True, check=True)
            self.assertEqual(branches.stdout.strip(), "")

            created = run_cli("git", "branch", "create", "feature/aegis", "--approved", cwd=tmp)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertEqual(json.loads(created.stdout)["operation"], "create")
            preview_switch = run_cli("git", "branch", "switch", "feature/aegis", cwd=tmp)
            self.assertEqual(preview_switch.returncode, 1)
            self.assertEqual(subprocess.run(["git", "branch", "--show-current"], cwd=tmp, text=True, capture_output=True, check=True).stdout.strip(), start_branch)

            switched = run_cli("git", "branch", "switch", "feature/aegis", "--approved", cwd=tmp)
            self.assertEqual(switched.returncode, 0, switched.stderr)
            self.assertEqual(subprocess.run(["git", "branch", "--show-current"], cwd=tmp, text=True, capture_output=True, check=True).stdout.strip(), "feature/aegis")
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.branch", audit)
            self.assertIn('"git_ref_mutation_performed": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_git_remote_push_is_approval_gated_typed_remote_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "work"
            remote = Path(tmp) / "remote.git"
            workspace.mkdir()
            subprocess.run(["git", "init"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-B", "main"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=workspace, text=True, capture_output=True, check=True)
            (workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "init", "--bare", str(remote)], text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=workspace, text=True, capture_output=True, check=True)

            listed = run_cli("git", "remote", cwd=str(workspace))
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn("origin", json.loads(listed.stdout)["stdout"])

            preview = run_cli("git", "remote", "push", "origin", "main", cwd=str(workspace))
            self.assertEqual(preview.returncode, 1)
            self.assertEqual(json.loads(preview.stdout)["status"], "needs_approval")
            missing = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=False)
            self.assertNotEqual(missing.returncode, 0)

            pushed = run_cli("git", "remote", "push", "origin", "main", "--approved", cwd=str(workspace))
            self.assertEqual(pushed.returncode, 0, pushed.stderr)
            payload = json.loads(pushed.stdout)
            self.assertEqual(payload["operation"], "push")
            exists = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=True)
            self.assertTrue(exists.stdout.strip())
            audit = (workspace / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.remote", audit)
            self.assertIn('"git_remote_mutation_performed": true', audit)
            self.assertIn('"external_action_started": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_git_remote_fetch_and_pull_are_approval_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed"
            remote = Path(tmp) / "remote.git"
            workspace = Path(tmp) / "work"
            seed.mkdir()
            subprocess.run(["git", "init"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-B", "main"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=seed, text=True, capture_output=True, check=True)
            (seed / "note.txt").write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "init", "--bare", str(remote)], text=True, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "clone", str(remote), str(workspace)], text=True, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "main"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=workspace, text=True, capture_output=True, check=True)
            old_remote_head = subprocess.run(["git", "rev-parse", "origin/main"], cwd=workspace, text=True, capture_output=True, check=True).stdout.strip()
            (seed / "note.txt").write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Update"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)
            new_remote_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=seed, text=True, capture_output=True, check=True).stdout.strip()

            preview_fetch = run_cli("git", "remote", "fetch", "origin", "main", cwd=str(workspace))
            self.assertEqual(preview_fetch.returncode, 1)
            self.assertEqual(json.loads(preview_fetch.stdout)["status"], "needs_approval")
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=workspace, text=True, capture_output=True, check=True).stdout.strip(), old_remote_head)

            fetched = run_cli("git", "remote", "fetch", "origin", "main", "--approved", cwd=str(workspace))
            self.assertEqual(fetched.returncode, 0, fetched.stderr)
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=workspace, text=True, capture_output=True, check=True).stdout.strip(), new_remote_head)
            self.assertEqual((workspace / "note.txt").read_text(encoding="utf-8"), "v1\n")

            preview_pull = run_cli("git", "remote", "pull", "origin", "main", cwd=str(workspace))
            self.assertEqual(preview_pull.returncode, 1)
            self.assertEqual(json.loads(preview_pull.stdout)["status"], "needs_approval")
            self.assertEqual((workspace / "note.txt").read_text(encoding="utf-8"), "v1\n")

            pulled = run_cli("git", "remote", "pull", "origin", "main", "--approved", cwd=str(workspace))
            self.assertEqual(pulled.returncode, 0, pulled.stderr)
            self.assertEqual((workspace / "note.txt").read_text(encoding="utf-8"), "v2\n")
            audit = (workspace / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.remote", audit)
            self.assertIn('"git_ref_mutation_performed": true', audit)
            self.assertIn('"workspace_mutation_performed": true', audit)
            self.assertIn('"external_action_started": true', audit)

    def test_chat_runs_one_local_agent_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("chat", "draft a safe plan", "--json", cwd=tmp)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["provider"], "local/terminal-v0")
            self.assertIn("Initial governed plan", payload["assistant_message"])

    def test_chat_routes_ready_openai_compatible_provider_without_browser(self):
        seen: dict[str, object] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                seen["path"] = self.path
                seen["authorization"] = self.headers.get("Authorization")
                seen["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
                payload = {
                    "choices": [{"message": {"content": "external route response"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base_url = f"http://127.0.0.1:{server.server_port}/v1"
                configured = run_cli(
                    "model",
                    "configure",
                    "openai/test-model",
                    "--mode",
                    "api_key",
                    "--api-key-env",
                    "AEGIS_TEST_OPENAI_KEY",
                    "--base-url",
                    base_url,
                    cwd=tmp,
                    extra_env={"AEGIS_TEST_OPENAI_KEY": "test-key"},
                )
                self.assertEqual(configured.returncode, 0, configured.stderr)

                result = run_cli("chat", "draft a safe plan", "--json", cwd=tmp, extra_env={"AEGIS_TEST_OPENAI_KEY": "test-key"})
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["provider"], "openai/test-model")
                self.assertEqual(payload["mode"], "api_key")
                self.assertEqual(payload["assistant_message"], "external route response")
                self.assertTrue(payload["usage_id"].startswith("usage-"))
                self.assertEqual(seen["path"], "/v1/chat/completions")
                self.assertEqual(seen["authorization"], "Bearer test-key")
                self.assertEqual(seen["body"]["model"], "test-model")

                usage = run_cli("model", "usage", cwd=tmp)
                self.assertEqual(usage.returncode, 0, usage.stderr)
                usage_payload = json.loads(usage.stdout)
                self.assertEqual(usage_payload["count"], 1)
                self.assertEqual(usage_payload["total_tokens"], 14)
                self.assertEqual(usage_payload["external_calls"], 1)
                self.assertEqual(usage_payload["recent"][0]["provider"], "openai/test-model")
                self.assertEqual(usage_payload["recent"][0]["token_accounting"], "provider_reported")
                self.assertFalse(usage_payload["browser_auto_launch"])

                audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
                self.assertIn('"external_model_invocation_performed": true', audit)
                self.assertIn('"browser_auto_launch": false', audit)
                self.assertNotIn("test-key", audit)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_chat_falls_back_to_local_after_external_route_failure_without_browser(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = b'{"error":"temporary upstream outage"}'
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base_url = f"http://127.0.0.1:{server.server_port}/v1"
                configured = run_cli(
                    "model",
                    "configure",
                    "openai/failing-model",
                    "--mode",
                    "api_key",
                    "--api-key-env",
                    "AEGIS_TEST_OPENAI_KEY",
                    "--base-url",
                    base_url,
                    cwd=tmp,
                    extra_env={"AEGIS_TEST_OPENAI_KEY": "test-key"},
                )
                self.assertEqual(configured.returncode, 0, configured.stderr)

                result = run_cli("chat", "draft a safe plan", "--json", cwd=tmp, extra_env={"AEGIS_TEST_OPENAI_KEY": "test-key"})
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["provider"], "local/terminal-v0")
                self.assertEqual(payload["mode"], "local")
                self.assertIn("External provider route failed", payload["assistant_message"])
                self.assertIn("Fallback provider: local/terminal-v0", payload["assistant_message"])
                self.assertIn("Initial governed plan", payload["assistant_message"])

                usage = run_cli("model", "usage", cwd=tmp)
                self.assertEqual(usage.returncode, 0, usage.stderr)
                usage_payload = json.loads(usage.stdout)
                self.assertEqual(usage_payload["count"], 1)
                self.assertEqual(usage_payload["external_calls"], 1)
                self.assertTrue(usage_payload["recent"][0]["fallback_used"])
                self.assertEqual(usage_payload["recent"][0]["primary_provider"], "openai/failing-model")
                self.assertEqual(usage_payload["recent"][0]["fallback_provider"], "local/terminal-v0")
                self.assertIn("fallback_local_after_http_503", usage_payload["recent"][0]["provider_route_status"])

                audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
                self.assertIn('"fallback_used": true', audit)
                self.assertIn('"browser_auto_launch": false', audit)
                self.assertNotIn("test-key", audit)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_model_provider_config_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            providers = run_cli("model", "providers", cwd=tmp)
            self.assertEqual(providers.returncode, 0, providers.stderr)
            payload = json.loads(providers.stdout)
            self.assertEqual(payload["active_provider"], "local/terminal-v0")
            self.assertFalse(payload["browser_required"])
            self.assertFalse(payload["external_action_started"])

            configured = run_cli(
                "model",
                "configure",
                "openai/gpt-5.5",
                "--mode",
                "api_key",
                "--api-key-env",
                "AEGIS_TEST_OPENAI_KEY",
                cwd=tmp,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            route = json.loads(configured.stdout)["route"]
            self.assertEqual(route["name"], "openai/gpt-5.5")
            self.assertEqual(route["status"], "env_missing")

            doctor = run_cli("model", "doctor", cwd=tmp)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            checks = json.loads(doctor.stdout)["checks"]
            self.assertTrue(next(check for check in checks if check["name"] == "metadata_only")["ok"])
            self.assertFalse(next(check for check in checks if check["name"] == "api_key_env")["ok"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("provider.configured", audit)
            self.assertIn("provider.doctor", audit)

    def test_connectors_are_metadata_only_and_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            listing = run_cli("connectors", cwd=tmp)
            self.assertEqual(listing.returncode, 0, listing.stderr)
            payload = json.loads(listing.stdout)
            self.assertFalse(payload["external_delivery_performed"])
            self.assertFalse(payload["browser_auto_launch"])
            self.assertIn("slack", [item["name"] for item in payload["connectors"]])

            configured = run_cli("connectors", "configure", "slack", "--token-env", "AEGIS_TEST_SLACK_TOKEN", "--enable", cwd=tmp)
            self.assertEqual(configured.returncode, 0, configured.stderr)
            connector = json.loads(configured.stdout)["connector"]
            self.assertEqual(connector["name"], "slack")
            self.assertEqual(connector["status"], "enabled_missing_handles")
            self.assertFalse(connector["external_delivery_performed"])

            doctor = run_cli("connectors", "doctor", cwd=tmp)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            doctor_payload = json.loads(doctor.stdout)
            self.assertFalse(doctor_payload["external_delivery_performed"])
            self.assertFalse(next(check for check in doctor_payload["checks"] if check["name"] == "slack")["ok"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("connector.configured", audit)
            self.assertIn("connector.doctor", audit)

    def test_tasks_submit_run_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            submitted = run_cli("tasks", "--submit", "draft a safe plan", cwd=tmp)
            self.assertEqual(submitted.returncode, 0, submitted.stderr)
            task_id = json.loads(submitted.stdout)["id"]

            run = run_cli("tasks", "--run", task_id, cwd=tmp)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "completed")
            listing = run_cli("tasks", cwd=tmp)
            self.assertIn(task_id, listing.stdout)

            cancelled_candidate = run_cli("tasks", "--submit", "cancel me", cwd=tmp)
            cancel_id = json.loads(cancelled_candidate.stdout)["id"]
            cancelled = run_cli("tasks", "--cancel", cancel_id, cwd=tmp)
            self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
            self.assertEqual(json.loads(cancelled.stdout)["status"], "cancelled")

    def test_tasks_background_can_be_run_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = run_cli("tasks", "--background", "background safe plan", cwd=tmp, extra_env={"AEGISAGENT_TASK_NO_SPAWN": "1"})
            self.assertEqual(started.returncode, 0, started.stderr)
            payload = json.loads(started.stdout)
            self.assertEqual(payload["status"], "queued")

            run = run_cli("tasks", "--run", payload["id"], cwd=tmp)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "completed")
            events = run_cli("tasks", "--events", payload["id"], cwd=tmp)
            self.assertEqual(events.returncode, 0, events.stderr)
            event_names = [event["event"] for event in json.loads(events.stdout)["events"]]
            self.assertIn("background.queued", event_names)
            self.assertIn("completed", event_names)
            output = run_cli("tasks", "--output", payload["id"], cwd=tmp)
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertIn("AEGIS TASK OUTPUT", output.stdout)
            self.assertIn("Initial governed plan", output.stdout)

    def test_tasks_background_worker_logs_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = run_cli("tasks", "--background", "background log plan", cwd=tmp, extra_env={"AEGISAGENT_TASK_SLEEP": "0.1"})
            self.assertEqual(started.returncode, 0, started.stderr)
            task_id = json.loads(started.stdout)["id"]
            deadline = time.time() + 5
            status = "running"
            while time.time() < deadline and status != "completed":
                shown = run_cli("tasks", "--show", task_id, cwd=tmp)
                self.assertEqual(shown.returncode, 0, shown.stderr)
                status = json.loads(shown.stdout)["status"]
                time.sleep(0.05)

            self.assertEqual(status, "completed")
            logs = run_cli("tasks", "--logs", task_id, cwd=tmp)

            self.assertEqual(logs.returncode, 0, logs.stderr)
            self.assertIn("AEGIS TASK WORKER LOGS", logs.stdout)
            self.assertIn('"status": "completed"', logs.stdout)

    def test_tasks_recover_stale_marks_dead_worker_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            submitted = run_cli("tasks", "--submit", "stale cli plan", cwd=tmp)
            self.assertEqual(submitted.returncode, 0, submitted.stderr)
            payload = json.loads(submitted.stdout)
            task_path = Path(tmp) / ".aegisagent" / "tasks" / f"{payload['id']}.json"
            payload["status"] = "running"
            payload["pid"] = 99999999
            task_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            recovered = run_cli("tasks", "--recover-stale", cwd=tmp)

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            recovered_payload = json.loads(recovered.stdout)
            self.assertEqual(recovered_payload["recovered"][0]["id"], payload["id"])
            self.assertEqual(recovered_payload["recovered"][0]["status"], "failed")
            events = run_cli("tasks", "--events", payload["id"], cwd=tmp)
            event_names = [event["event"] for event in json.loads(events.stdout)["events"]]
            self.assertIn("recovered.stale", event_names)

    def test_tasks_listing_auto_recovers_stale_running_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            submitted = run_cli("tasks", "--submit", "stale list plan", cwd=tmp)
            self.assertEqual(submitted.returncode, 0, submitted.stderr)
            payload = json.loads(submitted.stdout)
            task_path = Path(tmp) / ".aegisagent" / "tasks" / f"{payload['id']}.json"
            payload["status"] = "running"
            payload["pid"] = 99999999
            task_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            listing = run_cli("tasks", cwd=tmp)

            self.assertEqual(listing.returncode, 0, listing.stderr)
            listed = json.loads(listing.stdout)["tasks"][0]
            self.assertEqual(listed["id"], payload["id"])
            self.assertEqual(listed["status"], "failed")
            self.assertIsNone(listed["pid"])

    def test_sessions_query_searches_transcripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            appended = run_cli("sessions", "--append", "main", "terminal transcript marker", cwd=tmp)
            self.assertEqual(appended.returncode, 0, appended.stderr)

            result = run_cli("sessions", "--query", "transcript marker", cwd=tmp)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["query"], "transcript marker")
            self.assertEqual(payload["results"][0]["role"], "user")
            self.assertIn("terminal transcript marker", payload["results"][0]["snippet"])

    def test_subagents_delegate_runs_bounded_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("subagents", "--delegate", "improve terminal orchestration", cwd=tmp)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["root"]["status"], "completed")
            self.assertEqual([worker["role"] for worker in payload["workers"]], ["planner", "researcher", "implementer", "reviewer"])
            listing = run_cli("subagents", cwd=tmp)
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertEqual(len(json.loads(listing.stdout)["records"]), 5)
            events = run_cli("subagents", "--events", payload["root"]["id"], cwd=tmp)
            self.assertEqual(events.returncode, 0, events.stderr)
            self.assertEqual(json.loads(events.stdout)["events"][0]["event"], "root.started")
            stopped = run_cli("subagents", "--stop", payload["root"]["id"], cwd=tmp)
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertEqual(len(json.loads(stopped.stdout)["stopped"]), 5)

    def test_agents_surface_wraps_bounded_subagent_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = run_cli("agents", cwd=tmp)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("AGENTS", status.stdout)
            self.assertIn("planner", status.stdout)
            self.assertIn("browser_auto_launch=false", status.stdout)

            profiles = run_cli("agents", "profiles", cwd=tmp)
            self.assertEqual(profiles.returncode, 0, profiles.stderr)
            self.assertIn("AGENT PROFILES", profiles.stdout)
            self.assertIn("reviewer", profiles.stdout)
            self.assertIn("deliverable:", profiles.stdout)

            contracts = run_cli("agents", "contracts", cwd=tmp)
            self.assertEqual(contracts.returncode, 0, contracts.stderr)
            self.assertIn("AGENT CONTRACTS", contracts.stdout)
            self.assertIn("context", contracts.stdout)
            self.assertIn("browser_auto_launch=false", contracts.stdout)

            delegated = run_cli("agents", "delegate", "improve terminal orchestration", cwd=tmp)
            self.assertEqual(delegated.returncode, 0, delegated.stderr)
            payload = json.loads(delegated.stdout)
            self.assertEqual(payload["root"]["status"], "completed")
            self.assertEqual([worker["role"] for worker in payload["workers"]], ["planner", "researcher", "implementer", "reviewer"])
            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("contract_version", audit)
            self.assertIn("Checkpoint plan", audit)

            background = run_cli("agents", "bg", "background agent work", cwd=tmp, extra_env={"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"})
            self.assertEqual(background.returncode, 0, background.stderr)
            job_id = json.loads(background.stdout)["id"]
            jobs = run_cli("agents", "jobs", cwd=tmp)
            self.assertIn(job_id, jobs.stdout)

    def test_capabilities_surface_shows_terminal_parity_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = run_cli("capabilities", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("AEGIS CAPABILITY MAP", status.stdout)
            self.assertIn("Terminal activation", status.stdout)
            self.assertIn("Agents and subagents", status.stdout)
            self.assertIn("terminal_first=true", status.stdout)
            self.assertIn("browser_auto_launch=false", status.stdout)
            self.assertIn("aegis-test tui", status.stdout)

            gaps = run_cli("capabilities", "--gaps", cwd=tmp)
            self.assertEqual(gaps.returncode, 0, gaps.stderr)
            self.assertIn("AEGIS CAPABILITY GAPS", gaps.stdout)
            self.assertIn("[partial] Automations and schedules", gaps.stdout)
            self.assertNotIn("[ready] Terminal activation", gaps.stdout)

            payload_result = run_cli("--json", "capabilities", "--gaps", cwd=tmp)
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertTrue(payload["terminal_first"])
            self.assertFalse(payload["browser_auto_launch"])
            self.assertEqual(payload["title"], "AEGIS CAPABILITY GAPS")
            self.assertTrue(all(item["status"] != "ready" for item in payload["capabilities"]))

    def test_dashboard_is_terminal_first_operator_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = run_cli("dashboard", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("AEGIS TERMINAL DASHBOARD", status.stdout)
            self.assertIn("activate    aegis-test tui", status.stdout)
            self.assertIn("browser_auto_launch=false", status.stdout)
            self.assertIn("gateway_started=false", status.stdout)
            self.assertIn("Agents and subagents", status.stdout)

            payload_result = run_cli("--json", "dashboard", cwd=tmp, extra_env={"AEGIS_COMMAND_NAME": "aegis-test"})
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertEqual(payload["title"], "AEGIS TERMINAL DASHBOARD")
            self.assertTrue(payload["terminal_first"])
            self.assertFalse(payload["browser_auto_launch"])
            self.assertFalse(payload["gateway_started"])
            self.assertTrue(payload["metadata_only"])
            self.assertEqual(payload["activation"]["primary_command"], "aegis-test tui")
            self.assertIn("contract_version", payload["agents"])

    def test_automations_are_durable_gated_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = run_cli("automations", cwd=tmp)
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertIn("AEGIS AUTOMATIONS", empty.stdout)
            self.assertIn("schedule_worker_started=false", empty.stdout)

            created = run_cli(
                "automations",
                "create",
                "daily-check",
                "--schedule",
                "daily 09:00",
                "--prompt",
                "summarize workspace risks",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertIn("AEGIS AUTOMATION", created.stdout)
            self.assertIn("external_action_started=false", created.stdout)
            job_id = next(line for line in created.stdout.splitlines() if line.startswith("job")).split()[1]

            listing = run_cli("automations", cwd=tmp)
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertIn(job_id, listing.stdout)
            self.assertIn("daily-check", listing.stdout)

            due = run_cli("automations", "due", "--now", "2026-05-23T10:00:00Z", cwd=tmp)
            self.assertEqual(due.returncode, 0, due.stderr)
            self.assertIn("AEGIS AUTOMATION DUE CHECK", due.stdout)
            self.assertIn("[due]", due.stdout)
            self.assertIn("schedule_worker_started=false", due.stdout)

            tick = run_cli("automations", "tick", "--now", "2026-05-23T10:00:00Z", cwd=tmp)
            self.assertEqual(tick.returncode, 0, tick.stderr)
            self.assertIn("AEGIS AUTOMATION TICK", tick.stdout)
            self.assertIn("triggered=1", tick.stdout)
            self.assertIn("task", tick.stdout)

            triggered = run_cli("automations", "trigger", job_id, cwd=tmp)
            self.assertEqual(triggered.returncode, 0, triggered.stderr)
            self.assertIn("task", triggered.stdout)
            self.assertIn("queued", triggered.stdout)
            self.assertIn("schedule_worker_started=false", triggered.stdout)

            paused = run_cli("automations", "pause", job_id, cwd=tmp)
            self.assertEqual(paused.returncode, 0, paused.stderr)
            self.assertIn("PAUSED", paused.stdout)

            resumed = run_cli("automations", "resume", job_id, cwd=tmp)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("ACTIVE", resumed.stdout)

            worker = run_cli("automations", "worker", "--now", "2099-01-01T10:00:00Z", "--interval", "0", "--max-ticks", "1", cwd=tmp)
            self.assertEqual(worker.returncode, 0, worker.stderr)
            self.assertIn("AEGIS AUTOMATION WORKER", worker.stdout)
            self.assertIn("schedule_worker_started=true", worker.stdout)
            self.assertIn("ticks=1", worker.stdout)
            self.assertIn("triggered=1", worker.stdout)
            self.assertIn("task", worker.stdout)
            run_id = next(line for line in worker.stdout.splitlines() if line.startswith("run")).split()[1]

            logs = run_cli("automations", "logs", run_id, cwd=tmp)
            self.assertEqual(logs.returncode, 0, logs.stderr)
            self.assertIn("AEGIS AUTOMATION WORKER LOGS", logs.stdout)
            self.assertIn(run_id, logs.stdout)
            self.assertIn("started", logs.stdout)
            self.assertIn("tick", logs.stdout)
            self.assertIn("stopped", logs.stdout)

            payload_result = run_cli("--json", "automations", "show", job_id, cwd=tmp)
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertEqual(payload["status"], "ACTIVE")
            self.assertFalse(payload["schedule_worker_started"])
            self.assertEqual(payload["trigger_count"], 3)
            self.assertTrue(payload["last_task_id"])

            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("automation.created", audit)
            self.assertIn("automation.due_checked", audit)
            self.assertIn("automation.due_run", audit)
            self.assertIn("automation.triggered", audit)
            self.assertIn("automation.status_changed", audit)
            self.assertIn("automation.worker_started", audit)
            self.assertIn("automation.worker_stopped", audit)
            self.assertIn("automation.worker_logs_viewed", audit)

    def test_automation_missed_runs_are_explicitly_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli(
                "automations",
                "create",
                "hourly-check",
                "--schedule",
                "every 1 hour",
                "--prompt",
                "summarize delayed workspace risks",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            job_id = next(line for line in created.stdout.splitlines() if line.startswith("job")).split()[1]

            missed = run_cli("automations", "missed", "--now", "2099-01-01T10:00:00Z", "--limit", "2", cwd=tmp)
            self.assertEqual(missed.returncode, 0, missed.stderr)
            self.assertIn("AEGIS AUTOMATION MISSED RUNS", missed.stdout)
            self.assertIn("missed=2", missed.stdout)
            self.assertIn(job_id, missed.stdout)
            self.assertIn("schedule_worker_started=false", missed.stdout)

            replay = run_cli("automations", "replay-missed", "--now", "2099-01-01T10:00:00Z", "--limit", "2", cwd=tmp)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("AEGIS AUTOMATION MISSED REPLAY", replay.stdout)
            self.assertIn("replayed=2", replay.stdout)
            self.assertIn("task", replay.stdout)
            self.assertIn("schedule_worker_started=false", replay.stdout)

            payload_result = run_cli("--json", "automations", "show", job_id, cwd=tmp)
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertEqual(payload["trigger_count"], 2)
            self.assertTrue(payload["last_task_id"])
            self.assertFalse(payload["schedule_worker_started"])

            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("automation.missed_checked", audit)
            self.assertIn("automation.missed_replayed", audit)
            self.assertIn("automation.triggered", audit)

    def test_automation_calendar_recurrence_labels(self):
        cases = [
            ("weekday-check", "weekdays 09:00", "2099-01-05T10:00:00Z", "weekday schedule is due"),
            ("weekend-check", "weekends 09:00", "2099-01-03T10:00:00Z", "weekend schedule is due"),
            ("monthly-check", "monthly 15 09:00", "2099-01-15T10:00:00Z", "monthly schedule is due"),
            ("month-end-check", "monthly last 09:00", "2099-02-28T10:00:00Z", "monthly schedule is due"),
        ]
        for name, schedule, now, reason in cases:
            with self.subTest(schedule=schedule), tempfile.TemporaryDirectory() as tmp:
                created = run_cli("automations", "create", name, "--schedule", schedule, "--prompt", "summarize calendar state", cwd=tmp)
                self.assertEqual(created.returncode, 0, created.stderr)

                due = run_cli("automations", "due", "--now", now, cwd=tmp)
                self.assertEqual(due.returncode, 0, due.stderr)
                self.assertIn("AEGIS AUTOMATION DUE CHECK", due.stdout)
                self.assertIn("[due]", due.stdout)
                self.assertIn(name, due.stdout)
                self.assertIn(reason, due.stdout)
                self.assertIn("schedule_worker_started=false", due.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli("automations", "create", "monthly-missed", "--schedule", "monthly 15 09:00", "--prompt", "summarize monthly misses", cwd=tmp)
            self.assertEqual(created.returncode, 0, created.stderr)

            missed = run_cli("automations", "missed", "--now", "2099-03-01T10:00:00Z", "--limit", "2", cwd=tmp)
            self.assertEqual(missed.returncode, 0, missed.stderr)
            self.assertIn("AEGIS AUTOMATION MISSED RUNS", missed.stdout)
            self.assertIn("monthly day 15 schedule missed 2 run(s)", missed.stdout)
            self.assertIn("missed=2", missed.stdout)
            self.assertIn("schedule_worker_started=false", missed.stdout)

    def test_automation_timezone_aware_recurrence_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli(
                "automations",
                "create",
                "denver-weekday",
                "--schedule",
                "weekdays 09:00 America/Denver",
                "--prompt",
                "summarize Denver weekday state",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            early = run_cli("automations", "due", "--now", "2099-01-05T15:59:00Z", cwd=tmp)
            self.assertEqual(early.returncode, 0, early.stderr)
            self.assertIn("[skip]", early.stdout)
            self.assertIn("weekday (America/Denver) time 09:00 has not arrived", early.stdout)

            due = run_cli("automations", "due", "--now", "2099-01-05T16:00:00Z", cwd=tmp)
            self.assertEqual(due.returncode, 0, due.stderr)
            self.assertIn("[due]", due.stdout)
            self.assertIn("weekday (America/Denver) schedule is due", due.stdout)
            self.assertIn("schedule_worker_started=false", due.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli(
                "automations",
                "create",
                "denver-monthly",
                "--schedule",
                "monthly 15 09:00 tz=America/Denver",
                "--prompt",
                "summarize Denver monthly state",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            missed = run_cli("automations", "missed", "--now", "2099-03-01T10:00:00Z", "--limit", "2", cwd=tmp)
            self.assertEqual(missed.returncode, 0, missed.stderr)
            self.assertIn("monthly day 15 schedule (America/Denver) missed 2 run(s)", missed.stdout)
            self.assertIn("missed=2", missed.stdout)
            self.assertIn("schedule_worker_started=false", missed.stdout)

    def test_automation_calendar_exceptions_skip_due_and_missed_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli(
                "automations",
                "create",
                "denver-exception",
                "--schedule",
                "weekdays 09:00 America/Denver except=2099-01-05",
                "--prompt",
                "summarize Denver exception state",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            excluded = run_cli("automations", "due", "--now", "2099-01-05T16:00:00Z", cwd=tmp)
            self.assertEqual(excluded.returncode, 0, excluded.stderr)
            self.assertIn("[skip]", excluded.stdout)
            self.assertIn("date 2099-01-05 (America/Denver) is excluded by schedule exception", excluded.stdout)
            self.assertIn("schedule_worker_started=false", excluded.stdout)

            due = run_cli("automations", "due", "--now", "2099-01-06T16:00:00Z", cwd=tmp)
            self.assertEqual(due.returncode, 0, due.stderr)
            self.assertIn("[due]", due.stdout)
            self.assertIn("weekday (America/Denver) schedule is due", due.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            created = run_cli(
                "automations",
                "create",
                "monthly-exception",
                "--schedule",
                "monthly 15 09:00 tz=America/Denver skip=2026-06-15",
                "--prompt",
                "summarize monthly exception state",
                cwd=tmp,
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            missed = run_cli("automations", "missed", "--now", "2026-08-01T10:00:00Z", "--limit", "2", cwd=tmp)
            self.assertEqual(missed.returncode, 0, missed.stderr)
            self.assertIn("monthly day 15 schedule (America/Denver) missed 1 run(s)", missed.stdout)
            self.assertNotIn("2026-06-15T15:00:00Z", missed.stdout)
            self.assertIn("2026-07-15T15:00:00Z", missed.stdout)
            self.assertIn("schedule_worker_started=false", missed.stdout)

    def test_automation_service_wrapper_is_generated_but_not_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = run_cli("automations", "service", "--interval", "15", cwd=tmp)
            self.assertEqual(service.returncode, 0, service.stderr)
            self.assertIn("AEGIS AUTOMATION SERVICE WRAPPER", service.stdout)
            self.assertIn("loaded=false", service.stdout)
            self.assertIn("schedule_worker_started=false", service.stdout)
            self.assertIn("launchctl bootstrap", service.stdout)
            self.assertIn("launchctl bootout", service.stdout)

            payload_result = run_cli("--json", "automations", "service", "--interval", "15", cwd=tmp)
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertFalse(payload["loaded"])
            self.assertFalse(payload["schedule_worker_started"])
            self.assertTrue(Path(payload["plist_path"]).exists())
            script_path = Path(payload["script_path"])
            self.assertTrue(script_path.exists())
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("automations worker --interval 15 --max-ticks 0", script)
            self.assertIn(f"--workspace {Path(tmp).resolve()}", script)

            status = run_cli("automations", "service-status", cwd=tmp)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("AEGIS AUTOMATION SERVICE STATUS", status.stdout)
            self.assertIn("loaded=false", status.stdout)
            self.assertIn("plist       exists=true", status.stdout)
            self.assertIn("script      exists=true", status.stdout)
            self.assertIn("health     status=wrapper_ready_not_loaded worker_events=0", status.stdout)
            self.assertIn("advice      load and start the wrapper manually when ready", status.stdout)
            self.assertIn("schedule_worker_started=false", status.stdout)

            status_payload_result = run_cli("--json", "automations", "service-status", cwd=tmp)
            self.assertEqual(status_payload_result.returncode, 0, status_payload_result.stderr)
            status_payload = json.loads(status_payload_result.stdout)
            self.assertFalse(status_payload["loaded"])
            self.assertTrue(status_payload["plist_exists"])
            self.assertTrue(status_payload["script_exists"])
            self.assertEqual(status_payload["health_status"], "wrapper_ready_not_loaded")
            self.assertEqual(status_payload["worker_event_count"], 0)
            self.assertEqual(status_payload["stderr_tail_count"], 0)
            self.assertFalse(status_payload["schedule_worker_started"])

            worker = run_cli("automations", "worker", "--interval", "0", "--max-ticks", "1", cwd=tmp)
            self.assertEqual(worker.returncode, 0, worker.stderr)
            worker_status = run_cli("--json", "automations", "service-status", cwd=tmp)
            self.assertEqual(worker_status.returncode, 0, worker_status.stderr)
            worker_payload = json.loads(worker_status.stdout)
            self.assertEqual(worker_payload["health_status"], "wrapper_ready_worker_observed")
            self.assertEqual(worker_payload["worker_event_count"], 3)
            self.assertEqual(worker_payload["last_worker_event"], "stopped")
            self.assertTrue(worker_payload["worker_log_exists"])

            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("automation.service_wrapper_generated", audit)
            self.assertIn("automation.service_status_checked", audit)

    def test_improve_surface_tracks_reviewed_proposals_without_auto_editing(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = run_cli("improve", cwd=tmp)
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertIn("AEGIS IMPROVEMENTS", empty.stdout)
            self.assertIn("workspace_mutation_allowed_before_approval=false", empty.stdout)

            proposed = run_cli(
                "improve",
                "propose",
                "Prompt injection tried to leak secret credential from a tool result",
                "--target",
                "connectors",
                "--operation",
                "read",
                cwd=tmp,
            )
            self.assertEqual(proposed.returncode, 0, proposed.stderr)
            self.assertIn("AEGIS IMPROVEMENT PROPOSAL", proposed.stdout)
            self.assertIn("context_safety", proposed.stdout)
            self.assertIn("security_review_required", proposed.stdout)
            self.assertIn("external_action_started=false", proposed.stdout)
            proposal_id = next(line for line in proposed.stdout.splitlines() if line.startswith("proposal")).split()[1]

            blocked = run_cli("improve", "implement", proposal_id, cwd=tmp)
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            self.assertIn("Improvement handoff blocked", blocked.stdout)
            self.assertIn("proposal is not approved", blocked.stdout)

            candidate_blocked = run_cli("improve", "candidate", proposal_id, cwd=tmp)
            self.assertEqual(candidate_blocked.returncode, 0, candidate_blocked.stderr)
            self.assertIn("Improvement candidate blocked", candidate_blocked.stdout)

            approved = run_cli("improve", "approve", proposal_id, "--rationale", "reviewed safe plan", cwd=tmp)
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertIn("approved", approved.stdout)

            candidate = run_cli("improve", "candidate", proposal_id, cwd=tmp)
            self.assertEqual(candidate.returncode, 0, candidate.stderr)
            self.assertIn("AEGIS IMPROVEMENT CANDIDATE", candidate.stdout)
            self.assertIn("advisory_only=true", candidate.stdout)
            self.assertIn("workspace_mutation_performed=false", candidate.stdout)
            candidate_id = next(line for line in candidate.stdout.splitlines() if line.startswith("candidate")).split()[1]

            candidate_payload = json.loads(run_cli("--json", "improve", "candidate-show", candidate_id, cwd=tmp).stdout)
            self.assertEqual(candidate_payload["proposal_id"], proposal_id)
            self.assertTrue(candidate_payload["advisory_only"])
            self.assertFalse(candidate_payload["workspace_mutation_performed"])
            self.assertIn("src/aegisagent/core/connectors.py", candidate_payload["suggested_files"])

            suggested_file = Path(tmp) / "src" / "aegisagent" / "core" / "connectors.py"
            suggested_file.parent.mkdir(parents=True, exist_ok=True)
            suggested_file.write_text("CONNECTORS = []\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=tmp, text=True, capture_output=True, check=False)

            diff_review = run_cli("improve", "diff", candidate_id, cwd=tmp)
            self.assertEqual(diff_review.returncode, 0, diff_review.stderr)
            self.assertIn("AEGIS CANDIDATE DIFF REVIEW", diff_review.stdout)
            self.assertIn("workspace_mutation_performed=false", diff_review.stdout)
            self.assertIn("[changed] src/aegisagent/core/connectors.py", diff_review.stdout)
            self.assertIn("diff --git", diff_review.stdout)

            diff_payload = json.loads(run_cli("--json", "improve", "diff", candidate_id, cwd=tmp).stdout)
            self.assertEqual(diff_payload["candidate"]["id"], candidate_id)
            self.assertGreaterEqual(diff_payload["changed_file_count"], 1)
            self.assertFalse(diff_payload["workspace_mutation_performed"])

            verified = run_cli("improve", "verify", candidate_id, "--command-index", "1", "--timeout", "20", cwd=tmp)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("AEGIS IMPROVEMENT VERIFICATION", verified.stdout)
            self.assertIn("passed", verified.stdout)
            self.assertIn("PYTHONPATH=src python3 -m aegisagent audit verify", verified.stdout)

            verified_payload = json.loads(run_cli("--json", "improve", "candidate-show", candidate_id, cwd=tmp).stdout)
            self.assertEqual(verified_payload["last_verification_status"], "passed")
            self.assertEqual(verified_payload["verification_count"], 1)
            self.assertTrue(verified_payload["last_verification_id"])

            apply_result = run_cli("improve", "apply", candidate_id, cwd=tmp)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn("apply", apply_result.stdout)
            self.assertIn("task", apply_result.stdout)
            self.assertIn("watch", apply_result.stdout)
            task_id = next(line for line in apply_result.stdout.splitlines() if line.startswith("task")).split()[1]

            applied_candidate = json.loads(run_cli("--json", "improve", "candidate-show", candidate_id, cwd=tmp).stdout)
            self.assertEqual(applied_candidate["apply_task_id"], task_id)
            self.assertEqual(applied_candidate["apply_status"], "queued")
            self.assertEqual(applied_candidate["apply_count"], 1)

            payload_result = run_cli("--json", "improve", "show", proposal_id, cwd=tmp)
            self.assertEqual(payload_result.returncode, 0, payload_result.stderr)
            payload = json.loads(payload_result.stdout)
            self.assertEqual(payload["status"], "approved")
            self.assertEqual(payload["handoff_task_id"], task_id)
            self.assertEqual(payload["handoff_status"], "queued")
            self.assertEqual(payload["handoff_count"], 1)
            self.assertEqual(payload["candidate_id"], candidate_id)
            self.assertEqual(payload["candidate_status"], "apply_queued")
            self.assertEqual(payload["candidate_verification_status"], "passed")
            self.assertEqual(payload["candidate_verification_count"], 1)
            self.assertFalse(payload["workspace_mutation_allowed_before_approval"])
            self.assertFalse(payload["raw_secret_values_included"])

            task = json.loads(run_cli("tasks", "--show", task_id, cwd=tmp).stdout)
            self.assertEqual(task["source"], f"improvement-candidate:{candidate_id}")
            self.assertIn("Apply verified improvement candidate", task["prompt"])
            self.assertIn("Patch plan:", task["prompt"])
            self.assertIn("preserve terminal-first behavior", task["prompt"])

            completion_blocked = run_cli("improve", "complete", proposal_id, cwd=tmp)
            self.assertEqual(completion_blocked.returncode, 0, completion_blocked.stderr)
            self.assertIn("Improvement completion blocked", completion_blocked.stdout)

            evidence = run_cli(
                "improve",
                "evidence",
                proposal_id,
                "--files",
                "src/aegisagent/core/improvement.py,tests/test_cli.py",
                "--validation",
                "PYTHONPATH=src python3 -m unittest tests.test_cli -v",
                "--result",
                "passed",
                cwd=tmp,
            )
            self.assertEqual(evidence.returncode, 0, evidence.stderr)
            self.assertIn("evidence   evidence_recorded", evidence.stdout)
            self.assertIn("src/aegisagent/core/improvement.py", evidence.stdout)

            completed = run_cli("improve", "complete", proposal_id, cwd=tmp)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("implemented", completed.stdout)

            final_payload = json.loads(run_cli("--json", "improve", "show", proposal_id, cwd=tmp).stdout)
            self.assertEqual(final_payload["status"], "implemented")
            self.assertEqual(final_payload["implementation_status"], "implemented")
            self.assertEqual(final_payload["changed_files"], ["src/aegisagent/core/improvement.py", "tests/test_cli.py"])
            self.assertEqual(final_payload["verification_result"], "passed")

            audit = (Path(tmp) / ".aegisagent" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("improvement.proposed", audit)
            self.assertIn("improvement.reviewed", audit)
            self.assertIn("improvement.handoff_blocked", audit)
            self.assertIn("improvement.candidate_blocked", audit)
            self.assertIn("improvement.candidate_generated", audit)
            self.assertIn("improvement.candidate_diff_reviewed", audit)
            self.assertIn("improvement.verification_run", audit)
            self.assertIn("improvement.candidate_apply_created", audit)
            self.assertIn("improvement.implemented_blocked", audit)
            self.assertIn("improvement.evidence_recorded", audit)
            self.assertIn("improvement.implemented", audit)

    def test_subagents_stream_prints_timeline_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("subagents", "--stream", "improve live terminal feedback", cwd=tmp)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SUBAGENT LIVE", result.stdout)
            self.assertIn("root.started", result.stdout)
            self.assertIn("worker.completed", result.stdout)
            self.assertIn('"status": "completed"', result.stdout)

    def test_subagents_background_job_can_be_run_and_inspected(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = run_cli("subagents", "--background", "background terminal work", cwd=tmp, extra_env={"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"})

            self.assertEqual(started.returncode, 0, started.stderr)
            payload = json.loads(started.stdout)
            self.assertEqual(payload["status"], "queued")
            job_id = payload["id"]
            # The detached job is fast, but run the worker entrypoint explicitly so the test is deterministic.
            run = run_cli("subagents", "--run-job", job_id, cwd=tmp)
            self.assertEqual(run.returncode, 0, run.stderr)
            job = run_cli("subagents", "--job", job_id, cwd=tmp)
            self.assertEqual(job.returncode, 0, job.stderr)
            self.assertEqual(json.loads(job.stdout)["status"], "completed")
            jobs = run_cli("subagents", "--jobs", cwd=tmp)
            self.assertEqual(jobs.returncode, 0, jobs.stderr)
            self.assertTrue(json.loads(jobs.stdout)["jobs"])

    def test_subagents_background_job_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = run_cli("subagents", "--background", "cancel terminal work", cwd=tmp, extra_env={"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"})
            job_id = json.loads(started.stdout)["id"]

            cancelled = run_cli("subagents", "--cancel", job_id, cwd=tmp)

            self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
            payload = json.loads(cancelled.stdout)
            self.assertEqual(payload["status"], "cancelled")
            self.assertIn("Cancelled by operator", payload["summary"])

    def test_subagents_recover_stale_marks_dead_worker_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = run_cli("subagents", "--background", "recover stale subagent work", cwd=tmp, extra_env={"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"})
            payload = json.loads(started.stdout)
            job_id = payload["id"]
            job_path = Path(tmp) / ".aegisagent" / "jobs" / f"{job_id}.json"
            payload["status"] = "running"
            payload["pid"] = 99999999
            job_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            recovered = run_cli("subagents", "--recover-stale", cwd=tmp)

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            recovered_payload = json.loads(recovered.stdout)
            self.assertEqual(recovered_payload["recovered"][0]["id"], job_id)
            self.assertEqual(recovered_payload["recovered"][0]["status"], "failed")
            job = run_cli("subagents", "--job", job_id, cwd=tmp)
            self.assertEqual(json.loads(job.stdout)["status"], "failed")

    def test_tui_default_launches_interactive_terminal_not_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("aegisagent.cli.run_textual_app", return_value=0) as run_tui:
                with patch("aegisagent.cli.run_gateway") as run_gateway:
                    result = cli.main(["--workspace", tmp, "tui"])

        self.assertEqual(result, 0)
        self.assertEqual(run_tui.call_count, 1)
        self.assertEqual(run_tui.call_args.args, ("command",))
        self.assertEqual(run_tui.call_args.kwargs["classic"], False)
        run_gateway.assert_not_called()

    def test_tui_help_explains_terminal_activation_and_print_fallback(self):
        result = subprocess.run(
            [sys.executable, "-m", "aegisagent", "tui", "--help"],
            text=True,
            capture_output=True,
            check=False,
            env={"PYTHONPATH": "src"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: aegis tui", result.stdout)
        self.assertIn("--print", result.stdout)
        self.assertIn("--classic", result.stdout)
        self.assertNotIn("Textual", result.stdout)
        self.assertNotIn("gateway", result.stdout.lower())
        self.assertNotIn("web gui", result.stdout.lower())

    def test_tui_print_is_static_terminal_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("aegisagent.cli.run_textual_app") as run_tui:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = cli.main(
                        [
                            "--workspace",
                            tmp,
                            "tui",
                            "--print",
                            "--width",
                            "80",
                            "--height",
                            "24",
                        ]
                    )

        self.assertEqual(result, 0)
        run_tui.assert_not_called()
        self.assertIn("AEGIS SHIELD", output.getvalue())
        self.assertIn("aegis>", output.getvalue())


if __name__ == "__main__":
    unittest.main()
