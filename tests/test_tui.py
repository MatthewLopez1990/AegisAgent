import unittest
import tempfile
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

from aegisagent.config import runtime_paths
from aegisagent.core.setup_state import setup_wizard_preferences
from aegisagent.core.subagents import BackgroundJobStore
from aegisagent.core.tasks import TaskRunner, TaskStore
from aegisagent.tui.interactive import _CursesAegisAgent, build_interactive_panels, dispatch_interactive_command, normalize_interactive_command, slash_palette_candidates
from aegisagent.tui.renderer import TuiState, render


class TuiRendererTests(unittest.TestCase):
    def test_minimum_size_message(self):
        output = render(width=79, height=24)
        self.assertIn("at least 80x24", output)

    def test_command_view_contains_prompt_and_security(self):
        output = render(TuiState(view="command"), width=120, height=40)
        self.assertIn("AEGIS SHIELD", output)
        self.assertIn("aegis>", output)
        self.assertIn("security posture", output)
        self.assertIn("model      local/terminal-v0 ready", output)
        self.assertIn("120x40 ready", output)
        self.assertNotIn("openai/gpt-5.5 verified", output)

    def test_activation_view_and_command_are_browser_off(self):
        output = render(TuiState(view="activation"), width=100, height=32)
        self.assertIn("AEGIS TERMINAL ACTIVATION", output)
        self.assertIn("aegisagent tui", output)
        self.assertIn("browser_auto_launch=false", output)
        self.assertIn("/activation", output)

        with tempfile.TemporaryDirectory() as tmp:
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                result = dispatch_interactive_command("/activation", runtime_paths(tmp))

        self.assertEqual(result, "activation")
        self.assertIn("AEGIS TERMINAL ACTIVATION", printed.getvalue())
        self.assertIn("browser_auto_launch: false", printed.getvalue())

    def test_setup_and_tools_views_fit_reference_sizes(self):
        for view, width, height, marker in [
            ("setup", 100, 32, "AEGIS SETUP"),
            ("tools", 132, 38, "AEGIS CONTROL"),
        ]:
            output = render(TuiState(view=view), width=width, height=height)
            lines = output.splitlines()
            self.assertLessEqual(len(lines), height)
            self.assertTrue(all(len(line) <= width for line in lines))
            self.assertIn(marker, output)

    def test_interactive_panel_model_has_terminal_agent_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            panels = build_interactive_panels(runtime_paths(tmp))
        titles = {panel.title for panel in panels}
        self.assertIn("AGENT STATUS", titles)
        self.assertIn("ACTIVE CONSOLE", titles)
        self.assertIn("SECURITY POSTURE", titles)
        commands = {item.command for panel in panels for item in panel.items if item.command}
        self.assertIn("/setup", commands)
        self.assertIn("/activation", commands)
        self.assertIn("/tools", commands)
        self.assertIn("/dashboard", commands)
        self.assertIn("/audit", commands)
        self.assertIn("/web", commands)

    def test_setup_panel_has_first_launch_wizard_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            panels = build_interactive_panels(runtime_paths(tmp), active_menu="setup")

        setup = next(panel for panel in panels if panel.panel_id == "focus")
        self.assertEqual(setup.title, "SETUP WIZARD")
        commands = {item.command for item in setup.items}
        self.assertIn("/setup model", commands)
        self.assertIn("/setup connectors", commands)
        self.assertIn("/setup first-task", commands)
        self.assertIn("/setup run-checks", commands)
        self.assertIn("/setup hide", commands)

    def test_default_curses_launch_opens_setup_wizard_until_hidden(self):
        class FakeCurses:
            A_BOLD = 0

            @staticmethod
            def color_pair(_number: int) -> int:
                return 0

        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            deck = _CursesAegisAgent(object(), paths, FakeCurses)
            self.assertEqual(deck.active_menu, "setup")
            self.assertIn("Aegis setup wizard is open by default.", deck.output_lines)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/setup hide", paths)

            self.assertEqual(result, "setup")
            self.assertFalse(setup_wizard_preferences(paths)["show_by_default"])
            hidden_deck = _CursesAegisAgent(object(), paths, FakeCurses)
            self.assertIsNone(hidden_deck.active_menu)
            self.assertNotIn("Aegis setup wizard is open by default.", hidden_deck.output_lines)
            self.assertIn('"browser_auto_launch": false', output.getvalue())

            reset = io.StringIO()
            with contextlib.redirect_stdout(reset):
                result = dispatch_interactive_command("/setup reset", paths)

            self.assertEqual(result, "setup")
            self.assertTrue(setup_wizard_preferences(paths)["show_by_default"])
            reset_deck = _CursesAegisAgent(object(), paths, FakeCurses)
            self.assertEqual(reset_deck.active_menu, "setup")
            self.assertIn("Aegis setup wizard is open by default.", reset_deck.output_lines)

    def test_slash_palette_and_normalization(self):
        self.assertEqual(normalize_interactive_command("//setup"), "/setup")
        matches = slash_palette_candidates("/se")
        self.assertTrue(any(command == "/setup" for command, _detail in matches))
        git_matches = slash_palette_candidates("/git")
        self.assertTrue(any(command == "/git status" for command, _detail in git_matches))
        self.assertTrue(any(command == "/git diff" for command, _detail in git_matches))
        self.assertTrue(any(command == "/git stage" for command, _detail in git_matches))
        self.assertTrue(any(command == "/git commit" for command, _detail in git_matches))
        self.assertTrue(any(command == "/git branch" for command, _detail in git_matches))
        self.assertTrue(any(command == "/git remote" for command, _detail in git_matches))
        edit_matches = slash_palette_candidates("/edit")
        self.assertTrue(any(command == "/edit replace" for command, _detail in edit_matches))
        web_matches = slash_palette_candidates("/web f")
        self.assertTrue(any(command == "/web fetch" for command, _detail in web_matches))
        browser_matches = slash_palette_candidates("/browser o")
        self.assertTrue(any(command == "/browser open" for command, _detail in browser_matches))
        test_matches = slash_palette_candidates("/te")
        self.assertTrue(any(command == "/test" for command, _detail in test_matches))
        verify_matches = slash_palette_candidates("/ver")
        self.assertTrue(any(command == "/verify" for command, _detail in verify_matches))
        command_matches = slash_palette_candidates("/com")
        self.assertTrue(any(command == "/commands" for command, _detail in command_matches))
        dashboard_matches = slash_palette_candidates("/dash")
        self.assertTrue(any(command == "/dashboard" for command, _detail in dashboard_matches))
        install_matches = slash_palette_candidates("/inst")
        self.assertTrue(any(command == "/install" for command, _detail in install_matches))
        update_matches = slash_palette_candidates("/upd")
        self.assertTrue(any(command == "/update" for command, _detail in update_matches))
        capability_matches = slash_palette_candidates("/cap")
        self.assertTrue(any(command == "/capabilities" for command, _detail in capability_matches))
        gap_matches = slash_palette_candidates("/g")
        self.assertTrue(any(command == "/gaps" for command, _detail in gap_matches))
        task_matches = slash_palette_candidates("/tasks wa")
        self.assertTrue(any(command == "/tasks watch" for command, _detail in task_matches))
        automation_matches = slash_palette_candidates("/auto")
        self.assertTrue(any(command == "/automations" for command, _detail in automation_matches))
        automation_create_matches = slash_palette_candidates("/automations c")
        self.assertTrue(any(command == "/automations create" for command, _detail in automation_create_matches))
        automation_due_matches = slash_palette_candidates("/automations d")
        self.assertTrue(any(command == "/automations due" for command, _detail in automation_due_matches))
        automation_missed_matches = slash_palette_candidates("/automations m")
        self.assertTrue(any(command == "/automations missed" for command, _detail in automation_missed_matches))
        automation_replay_matches = slash_palette_candidates("/automations re")
        self.assertTrue(any(command == "/automations replay" for command, _detail in automation_replay_matches))
        automation_tick_matches = slash_palette_candidates("/automations ti")
        self.assertTrue(any(command == "/automations tick" for command, _detail in automation_tick_matches))
        automation_worker_matches = slash_palette_candidates("/automations w")
        self.assertTrue(any(command == "/automations worker" for command, _detail in automation_worker_matches))
        automation_logs_matches = slash_palette_candidates("/automations l")
        self.assertTrue(any(command == "/automations logs" for command, _detail in automation_logs_matches))
        automation_service_matches = slash_palette_candidates("/automations s")
        self.assertTrue(any(command == "/automations service" for command, _detail in automation_service_matches))
        self.assertTrue(any(command == "/automations service-status" for command, _detail in automation_service_matches))
        automation_trigger_matches = slash_palette_candidates("/automations t")
        self.assertTrue(any(command == "/automations trigger" for command, _detail in automation_trigger_matches))
        improve_matches = slash_palette_candidates("/imp")
        self.assertTrue(any(command == "/improve" for command, _detail in improve_matches))
        improve_propose_matches = slash_palette_candidates("/improve p")
        self.assertTrue(any(command == "/improve propose" for command, _detail in improve_propose_matches))
        improve_implement_matches = slash_palette_candidates("/improve i")
        self.assertTrue(any(command == "/improve implement" for command, _detail in improve_implement_matches))
        improve_candidate_matches = slash_palette_candidates("/improve ca")
        self.assertTrue(any(command == "/improve candidate" for command, _detail in improve_candidate_matches))
        improve_diff_matches = slash_palette_candidates("/improve d")
        self.assertTrue(any(command == "/improve diff" for command, _detail in improve_diff_matches))
        improve_verify_matches = slash_palette_candidates("/improve v")
        self.assertTrue(any(command == "/improve verify" for command, _detail in improve_verify_matches))
        improve_apply_matches = slash_palette_candidates("/improve a")
        self.assertTrue(any(command == "/improve apply" for command, _detail in improve_apply_matches))
        improve_evidence_matches = slash_palette_candidates("/improve e")
        self.assertTrue(any(command == "/improve evidence" for command, _detail in improve_evidence_matches))
        improve_complete_matches = slash_palette_candidates("/improve c")
        self.assertTrue(any(command == "/improve complete" for command, _detail in improve_complete_matches))
        output_matches = slash_palette_candidates("/tasks ou")
        self.assertTrue(any(command == "/tasks output" for command, _detail in output_matches))
        log_matches = slash_palette_candidates("/tasks lo")
        self.assertTrue(any(command == "/tasks logs" for command, _detail in log_matches))
        unwatch_matches = slash_palette_candidates("/tasks un")
        self.assertTrue(any(command == "/tasks unwatch" for command, _detail in unwatch_matches))
        recover_matches = slash_palette_candidates("/tasks rec")
        self.assertTrue(any(command == "/tasks recover" for command, _detail in recover_matches))
        setup_model_matches = slash_palette_candidates("/setup m")
        self.assertTrue(any(command == "/setup model" for command, _detail in setup_model_matches))
        setup_sandbox_matches = slash_palette_candidates("/setup sa")
        self.assertTrue(any(command == "/setup sandbox" for command, _detail in setup_sandbox_matches))
        setup_connectors_matches = slash_palette_candidates("/setup c")
        self.assertTrue(any(command == "/setup connectors" for command, _detail in setup_connectors_matches))
        setup_first_task_matches = slash_palette_candidates("/setup f")
        self.assertTrue(any(command == "/setup first-task" for command, _detail in setup_first_task_matches))
        setup_hide_matches = slash_palette_candidates("/setup h")
        self.assertTrue(any(command == "/setup hide" for command, _detail in setup_hide_matches))
        model_doctor_matches = slash_palette_candidates("/model d")
        self.assertTrue(any(command == "/model doctor" for command, _detail in model_doctor_matches))
        model_usage_matches = slash_palette_candidates("/model u")
        self.assertTrue(any(command == "/model usage" for command, _detail in model_usage_matches))
        connector_matches = slash_palette_candidates("/conn")
        self.assertTrue(any(command == "/connectors" for command, _detail in connector_matches))
        connector_doctor_matches = slash_palette_candidates("/connectors d")
        self.assertTrue(any(command == "/connectors doctor" for command, _detail in connector_doctor_matches))
        subagent_monitor_matches = slash_palette_candidates("/subagents mon")
        self.assertTrue(any(command == "/subagents monitor" for command, _detail in subagent_monitor_matches))
        subagent_unwatch_matches = slash_palette_candidates("/subagents un")
        self.assertTrue(any(command == "/subagents unwatch" for command, _detail in subagent_unwatch_matches))
        agent_matches = slash_palette_candidates("/ag")
        self.assertTrue(any(command == "/agents" for command, _detail in agent_matches))
        agent_delegate_matches = slash_palette_candidates("/agents del")
        self.assertTrue(any(command == "/agents delegate" for command, _detail in agent_delegate_matches))
        agent_contract_matches = slash_palette_candidates("/agents con")
        self.assertTrue(any(command == "/agents contracts" for command, _detail in agent_contract_matches))
        agent_monitor_matches = slash_palette_candidates("/agents mon")
        self.assertTrue(any(command == "/agents monitor" for command, _detail in agent_monitor_matches))

    def test_interactive_dispatch_runs_local_agent_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                result = dispatch_interactive_command("draft a safe plan", paths)
            self.assertEqual(result, "agent turn")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("model_invocation_performed", audit)
            self.assertIn("external_model_invocation_performed", audit)
            self.assertIn("agent.turn.completed", audit)

    def test_interactive_dispatch_renders_command_lanes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/commands git", paths)

            self.assertEqual(result, "commands")
            self.assertIn("AEGIS SHIELD command lanes", output.getvalue())
            self.assertIn("/git status", output.getvalue())
            self.assertIn("/git diff", output.getvalue())

    def test_interactive_dispatch_model_providers_is_terminal_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/model providers", paths)

            self.assertEqual(result, "models")
            self.assertIn("local/terminal-v0", output.getvalue())
            self.assertIn('"browser_required": false', output.getvalue())
            self.assertIn('"external_action_started": false', output.getvalue())

            setup_model = io.StringIO()
            with contextlib.redirect_stdout(setup_model):
                result = dispatch_interactive_command("/setup model", paths)

            self.assertEqual(result, "setup")
            self.assertIn("AEGIS SETUP :: model", setup_model.getvalue())
            self.assertIn("aegisagent model configure", setup_model.getvalue())

            setup_sandbox = io.StringIO()
            with contextlib.redirect_stdout(setup_sandbox):
                result = dispatch_interactive_command("/setup sandbox", paths)

            self.assertEqual(result, "setup")
            self.assertIn("AEGIS SETUP :: sandbox", setup_sandbox.getvalue())

            setup_connectors = io.StringIO()
            with contextlib.redirect_stdout(setup_connectors):
                result = dispatch_interactive_command("/setup connectors", paths)

            self.assertEqual(result, "setup")
            self.assertIn("external_delivery", setup_connectors.getvalue())
            self.assertIn("slack", setup_connectors.getvalue())

            first_task = io.StringIO()
            with contextlib.redirect_stdout(first_task):
                result = dispatch_interactive_command("/setup first-task", paths)

            self.assertEqual(result, "setup")
            self.assertIn("AEGIS SETUP :: first-task", first_task.getvalue())
            self.assertIn("/subagents live", first_task.getvalue())
            self.assertIn('"browser_auto_launch": false', first_task.getvalue())

            connectors = io.StringIO()
            with contextlib.redirect_stdout(connectors):
                result = dispatch_interactive_command("/connectors", paths)

            self.assertEqual(result, "connectors")
            self.assertIn('"external_delivery_performed": false', connectors.getvalue())

            connector_doctor = io.StringIO()
            with contextlib.redirect_stdout(connector_doctor):
                result = dispatch_interactive_command("/connectors doctor", paths)

            self.assertEqual(result, "connectors")
            self.assertIn('"browser_auto_launch": false', connector_doctor.getvalue())

            doctor = io.StringIO()
            with contextlib.redirect_stdout(doctor):
                result = dispatch_interactive_command("/setup run-checks", paths)

            self.assertEqual(result, "setup")
            self.assertIn('"metadata_only"', doctor.getvalue())
            self.assertIn('"model_invocation_performed": false', (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8"))

            with contextlib.redirect_stdout(io.StringIO()):
                dispatch_interactive_command("draft a safe plan", paths)
            usage = io.StringIO()
            with contextlib.redirect_stdout(usage):
                result = dispatch_interactive_command("/model usage", paths)

            self.assertEqual(result, "models")
            self.assertIn('"count": 1', usage.getvalue())
            self.assertIn('"provider": "local/terminal-v0"', usage.getvalue())
            self.assertIn('"browser_auto_launch": false', usage.getvalue())

    def test_interactive_dispatch_task_queue_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/tasks submit draft a safe plan", paths)

            self.assertEqual(result, "tasks")
            self.assertIn("AEGIS TASK", output.getvalue())
            task_id = next(line for line in output.getvalue().splitlines() if line.startswith("task")).split()[1]
            run_output = io.StringIO()
            with contextlib.redirect_stdout(run_output):
                dispatch_interactive_command(f"/tasks run {task_id}", paths)
            self.assertIn("completed", run_output.getvalue())
            self.assertIn("Initial governed plan", run_output.getvalue())
            events_output = io.StringIO()
            with contextlib.redirect_stdout(events_output):
                dispatch_interactive_command(f"/tasks events {task_id}", paths)
            self.assertIn("AEGIS TASK EVENTS", events_output.getvalue())
            self.assertIn("model.completed", events_output.getvalue())
            watch_output = io.StringIO()
            with contextlib.redirect_stdout(watch_output):
                dispatch_interactive_command(f"/tasks watch {task_id}", paths)
            self.assertIn("AEGIS TASK", watch_output.getvalue())
            self.assertIn("AEGIS TASK EVENTS", watch_output.getvalue())
            self.assertIn("AEGIS TASK OUTPUT", watch_output.getvalue())
            self.assertIn("completed", watch_output.getvalue())
            output_only = io.StringIO()
            with contextlib.redirect_stdout(output_only):
                dispatch_interactive_command(f"/tasks output {task_id}", paths)
            self.assertIn("AEGIS TASK OUTPUT", output_only.getvalue())
            self.assertIn("Initial governed plan", output_only.getvalue())
            (paths.tasks_dir / f"{task_id}.stdout.log").write_text('{"status": "completed"}\n', encoding="utf-8")
            logs_only = io.StringIO()
            with contextlib.redirect_stdout(logs_only):
                dispatch_interactive_command(f"/tasks logs {task_id}", paths)
            self.assertIn("AEGIS TASK WORKER LOGS", logs_only.getvalue())
            self.assertIn('"status": "completed"', logs_only.getvalue())
            unwatch_output = io.StringIO()
            with contextlib.redirect_stdout(unwatch_output):
                result = dispatch_interactive_command("/tasks unwatch", paths)
            self.assertEqual(result, "tasks")
            self.assertIn("stops the nonblocking task monitor", unwatch_output.getvalue())

    def test_interactive_dispatch_background_task_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()

            with patch.dict("os.environ", {"AEGISAGENT_TASK_NO_SPAWN": "1"}), contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/tasks bg draft a later plan", paths)

            self.assertEqual(result, "tasks")
            self.assertIn("queued", output.getvalue())
            self.assertIn("watch: /tasks watch", output.getvalue())

    def test_interactive_dispatch_recovers_stale_task_queue_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            record = runner.submit("stale task from tui", source="test")
            record.status = "running"
            record.pid = 99999999
            TaskStore(paths).save(record)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/tasks recover", paths)

            self.assertEqual(result, "tasks")
            self.assertIn(record.id, output.getvalue())
            self.assertIn("failed", output.getvalue())

    def test_interactive_dispatch_list_auto_recovers_stale_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            runner = TaskRunner(paths)
            record = runner.submit("stale list task from tui", source="test")
            record.status = "running"
            record.pid = 99999999
            TaskStore(paths).save(record)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/tasks", paths)

            self.assertEqual(result, "tasks")
            self.assertIn(record.id, output.getvalue())
            self.assertIn("failed", output.getvalue())
            self.assertIn("recovered.stale", [event.event for event in runner.events(record.id)])

    def test_interactive_dispatch_add_dir_records_workspace_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "src").mkdir()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/add-dir src", paths)

            self.assertEqual(result, "add-dir")
            self.assertIn('"status": "ok"', output.getvalue())
            messages = (paths.sessions_dir / next(path.name for path in paths.sessions_dir.glob("main-*.json"))).read_text(encoding="utf-8")
            self.assertIn("session.add_dir", messages)

    def test_interactive_dispatch_reads_workspace_file_with_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            (paths.workspace / "secret.txt").write_text("token=sk-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/read secret.txt", paths)

            self.assertEqual(result, "read")
            self.assertIn("workspace.read_file", (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8"))
            self.assertIn("[REDACTED]", output.getvalue())
            self.assertIn("audit receipt:", output.getvalue())

    def test_interactive_dispatch_memory_add_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            preview = io.StringIO()

            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/memory add user | Terminal preference | Prefers terminal-first activation.", paths)

            self.assertEqual(result, "memory")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            self.assertNotIn("Terminal preference", (paths.memory_dir / "USER.md").read_text(encoding="utf-8"))

            applied = io.StringIO()
            with contextlib.redirect_stdout(applied):
                result = dispatch_interactive_command("/memory add user | Terminal preference | Prefers terminal-first activation. | approve", paths)

            self.assertEqual(result, "memory")
            self.assertIn('"status": "ok"', applied.getvalue())
            self.assertIn("Terminal preference", (paths.memory_dir / "USER.md").read_text(encoding="utf-8"))
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("memory.note.add", audit)
            self.assertIn('"memory_write_performed": true', audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_interactive_dispatch_web_fetch_requires_approval(self):
        seen = {"count": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen["count"] += 1
                body = b"Aegis TUI fetch"
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
                paths = runtime_paths(tmp)
                url = f"http://127.0.0.1:{server.server_port}/note"
                preview = io.StringIO()

                with contextlib.redirect_stdout(preview):
                    result = dispatch_interactive_command(f"/web fetch {url}", paths)

                self.assertEqual(result, "web fetch")
                self.assertIn('"status": "needs_approval"', preview.getvalue())
                self.assertEqual(seen["count"], 0)

                fetched = io.StringIO()
                with contextlib.redirect_stdout(fetched):
                    result = dispatch_interactive_command(f"/web fetch {url} | approve", paths)

                self.assertEqual(result, "web fetch")
                self.assertIn('"status": "ok"', fetched.getvalue())
                self.assertIn("Aegis TUI fetch", fetched.getvalue())
                self.assertEqual(seen["count"], 1)
                audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
                self.assertIn("web.fetch", audit)
                self.assertIn('"network_request_performed": true', audit)
                self.assertIn('"browser_auto_launch": false', audit)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_interactive_dispatch_browser_sessions_require_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            preview = io.StringIO()

            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/browser open https://example.com/browser", paths)

            self.assertEqual(result, "browser")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            self.assertFalse(list(paths.browser_sessions_dir.glob("browser-*.json")))

            opened = io.StringIO()
            with contextlib.redirect_stdout(opened):
                result = dispatch_interactive_command("/browser open https://example.com/browser | approve", paths)

            self.assertEqual(result, "browser")
            opened_payload = json.loads(opened.getvalue())
            session_id = opened_payload["session"]["id"]
            self.assertEqual(opened_payload["status"], "ok")
            self.assertFalse(opened_payload["session"]["browser_auto_launch"])

            (paths.workspace / "screen.txt").write_text("operator captured browser state\n", encoding="utf-8")
            screenshot = io.StringIO()
            with contextlib.redirect_stdout(screenshot):
                result = dispatch_interactive_command(f"/browser screenshot {session_id} | screen.txt | approve", paths)

            self.assertEqual(result, "browser")
            screenshot_payload = json.loads(screenshot.getvalue())
            self.assertEqual(screenshot_payload["status"], "ok")
            self.assertEqual(screenshot_payload["screenshot"]["path"], "screen.txt")
            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                result = dispatch_interactive_command("/browser", paths)
            self.assertEqual(result, "browser")
            self.assertIn(session_id, listing.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("browser.session.open", audit)
            self.assertIn("browser.session.screenshot", audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_interactive_dispatch_searches_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                dispatch_interactive_command("remember terminal search receipts", paths)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/sessions search terminal search", paths)

            self.assertEqual(result, "sessions")
            self.assertIn("terminal search receipts", output.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("session.search", audit)

    def test_interactive_dispatch_git_status_uses_typed_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "tracked.txt").write_text("hello\n", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/git status", paths)

            self.assertEqual(result, "git status")
            self.assertIn("tracked.txt", output.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("tui.tool.completed", audit)
            self.assertIn("git.status", audit)

    def test_interactive_dispatch_git_stage_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            preview = io.StringIO()

            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/git stage note.txt", paths)

            self.assertEqual(result, "git stage")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            self.assertEqual(cached.stdout.strip(), "")

            applied = io.StringIO()
            with contextlib.redirect_stdout(applied):
                result = dispatch_interactive_command("/git stage note.txt | approve", paths)

            self.assertEqual(result, "git stage")
            self.assertIn('"status": "ok"', applied.getvalue())
            cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            self.assertEqual(cached.stdout.strip(), "note.txt")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.stage", audit)
            self.assertIn('"git_index_mutation_performed": true', audit)

    def test_interactive_dispatch_git_commit_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            preview = io.StringIO()

            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/git commit Add note", paths)

            self.assertEqual(result, "git commit")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            no_head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=paths.workspace, text=True, capture_output=True, check=False)
            self.assertNotEqual(no_head.returncode, 0)

            applied = io.StringIO()
            with contextlib.redirect_stdout(applied):
                result = dispatch_interactive_command("/git commit Add note | approve", paths)

            self.assertEqual(result, "git commit")
            self.assertIn('"status": "ok"', applied.getvalue())
            log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            self.assertEqual(log.stdout.strip(), "Add note")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.commit", audit)
            self.assertIn('"git_history_mutation_performed": true', audit)

    def test_interactive_dispatch_git_branch_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            subprocess.run(["git", "init"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Aegis Test"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "aegis@example.invalid"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            (paths.workspace / "note.txt").write_text("hello terminal\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=paths.workspace, text=True, capture_output=True, check=True)
            start_branch = subprocess.run(["git", "branch", "--show-current"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/git branch", paths)

            self.assertEqual(result, "git branch")
            self.assertIn(start_branch, output.getvalue())
            preview = io.StringIO()
            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/git branch create feature/aegis", paths)

            self.assertEqual(result, "git branch")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            self.assertEqual(subprocess.run(["git", "branch", "--list", "feature/aegis"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), "")

            created = io.StringIO()
            with contextlib.redirect_stdout(created):
                result = dispatch_interactive_command("/git branch create feature/aegis | approve", paths)

            self.assertEqual(result, "git branch")
            self.assertIn('"operation": "create"', created.getvalue())
            switched = io.StringIO()
            with contextlib.redirect_stdout(switched):
                result = dispatch_interactive_command("/git branch switch feature/aegis | approve", paths)

            self.assertEqual(result, "git branch")
            self.assertEqual(subprocess.run(["git", "branch", "--show-current"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), "feature/aegis")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.branch", audit)
            self.assertIn('"git_ref_mutation_performed": true', audit)

    def test_interactive_dispatch_git_remote_push_requires_approval(self):
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
            listed = io.StringIO()

            with contextlib.redirect_stdout(listed):
                result = dispatch_interactive_command("/git remote", paths)

            self.assertEqual(result, "git remote")
            self.assertIn("origin", listed.getvalue())
            preview = io.StringIO()
            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/git remote push origin main", paths)

            self.assertEqual(result, "git remote")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            missing = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=False)
            self.assertNotEqual(missing.returncode, 0)

            pushed = io.StringIO()
            with contextlib.redirect_stdout(pushed):
                result = dispatch_interactive_command("/git remote push origin main | approve", paths)

            self.assertEqual(result, "git remote")
            self.assertIn('"operation": "push"', pushed.getvalue())
            exists = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "refs/heads/main"], text=True, capture_output=True, check=True)
            self.assertTrue(exists.stdout.strip())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.remote", audit)
            self.assertIn('"git_remote_mutation_performed": true', audit)

    def test_interactive_dispatch_git_remote_fetch_and_pull_require_approval(self):
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
            paths = runtime_paths(workspace)
            old_remote_head = subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip()
            (seed / "note.txt").write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "note.txt"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Update"], cwd=seed, text=True, capture_output=True, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=seed, text=True, capture_output=True, check=True)
            new_remote_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=seed, text=True, capture_output=True, check=True).stdout.strip()
            preview_fetch = io.StringIO()

            with contextlib.redirect_stdout(preview_fetch):
                result = dispatch_interactive_command("/git remote fetch origin main", paths)

            self.assertEqual(result, "git remote")
            self.assertIn('"status": "needs_approval"', preview_fetch.getvalue())
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), old_remote_head)
            fetched = io.StringIO()
            with contextlib.redirect_stdout(fetched):
                result = dispatch_interactive_command("/git remote fetch origin main | approve", paths)

            self.assertEqual(result, "git remote")
            self.assertEqual(subprocess.run(["git", "rev-parse", "origin/main"], cwd=paths.workspace, text=True, capture_output=True, check=True).stdout.strip(), new_remote_head)
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v1\n")
            pulled = io.StringIO()
            with contextlib.redirect_stdout(pulled):
                result = dispatch_interactive_command("/git remote pull origin main | approve", paths)

            self.assertEqual(result, "git remote")
            self.assertEqual((paths.workspace / "note.txt").read_text(encoding="utf-8"), "v2\n")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("git.remote", audit)
            self.assertIn('"workspace_mutation_performed": true', audit)

    def test_interactive_dispatch_runs_typed_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            tests_dir = paths.workspace / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/test", paths)

            self.assertEqual(result, "test")
            self.assertIn('"returncode": 0', output.getvalue())
            self.assertIn("Ran 1 test", output.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("workspace.run_tests", audit)
            self.assertIn('"browser_auto_launch": false', audit)

    def test_interactive_dispatch_edit_replace_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            target = paths.workspace / "note.txt"
            target.write_text("hello terminal\n", encoding="utf-8")
            preview = io.StringIO()

            with contextlib.redirect_stdout(preview):
                result = dispatch_interactive_command("/edit replace note.txt | hello | safe", paths)

            self.assertEqual(result, "edit")
            self.assertIn('"status": "needs_approval"', preview.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "hello terminal\n")
            applied = io.StringIO()
            with contextlib.redirect_stdout(applied):
                result = dispatch_interactive_command("/edit replace note.txt | hello | safe | approve", paths)

            self.assertEqual(result, "edit")
            self.assertIn('"status": "ok"', applied.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "safe terminal\n")
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("workspace.replace_text", audit)
            self.assertIn('"workspace_mutation_performed": true', audit)

    def test_interactive_dispatch_runs_subagent_delegation(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/subagents improve the terminal shell", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("SUBAGENT DELEGATION", output.getvalue())
            self.assertIn("planner", output.getvalue())
            self.assertNotIn('{"root"', output.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("subagent.delegation.completed", audit)

    def test_interactive_dispatch_agents_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            status = io.StringIO()
            with contextlib.redirect_stdout(status):
                result = dispatch_interactive_command("/agents", paths)

            self.assertEqual(result, "agents")
            self.assertIn("AGENTS", status.getvalue())
            self.assertIn("browser_auto_launch=false", status.getvalue())

            profiles = io.StringIO()
            with contextlib.redirect_stdout(profiles):
                result = dispatch_interactive_command("/agents profiles", paths)

            self.assertEqual(result, "agents")
            self.assertIn("AGENT PROFILES", profiles.getvalue())
            self.assertIn("reviewer", profiles.getvalue())
            self.assertIn("deliverable:", profiles.getvalue())

            contracts = io.StringIO()
            with contextlib.redirect_stdout(contracts):
                result = dispatch_interactive_command("/agents contracts", paths)

            self.assertEqual(result, "agents")
            self.assertIn("AGENT CONTRACTS", contracts.getvalue())
            self.assertIn("context", contracts.getvalue())
            self.assertIn("browser_auto_launch=false", contracts.getvalue())

            delegated = io.StringIO()
            with contextlib.redirect_stdout(delegated):
                result = dispatch_interactive_command("/agents delegate improve terminal orchestration", paths)

            self.assertEqual(result, "agents")
            self.assertIn("AGENT DELEGATION", delegated.getvalue())
            self.assertIn("planner", delegated.getvalue())

            background = io.StringIO()
            with patch.dict("os.environ", {"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"}), contextlib.redirect_stdout(background):
                result = dispatch_interactive_command("/agents bg improve background agents", paths)

            self.assertEqual(result, "agents")
            self.assertIn("AGENT BACKGROUND JOB", background.getvalue())
            self.assertIn("monitor: /agents monitor", background.getvalue())

    def test_interactive_dispatch_capabilities_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            status = io.StringIO()
            with contextlib.redirect_stdout(status):
                result = dispatch_interactive_command("/capabilities", paths)

            self.assertEqual(result, "capabilities")
            self.assertIn("AEGIS CAPABILITY MAP", status.getvalue())
            self.assertIn("terminal_first=true", status.getvalue())
            self.assertIn("browser_auto_launch=false", status.getvalue())
            self.assertIn("Agents and subagents", status.getvalue())

            gaps = io.StringIO()
            with contextlib.redirect_stdout(gaps):
                result = dispatch_interactive_command("/gaps", paths)

            self.assertEqual(result, "capabilities")
            self.assertIn("AEGIS CAPABILITY GAPS", gaps.getvalue())
            self.assertIn("[partial] Automations and schedules", gaps.getvalue())
            self.assertNotIn("[ready] Terminal activation", gaps.getvalue())

    def test_interactive_dispatch_dashboard_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/dashboard", runtime_paths(tmp))

            self.assertEqual(result, "dashboard")
            self.assertIn("AEGIS TERMINAL DASHBOARD", output.getvalue())
            self.assertIn("activate    aegisagent tui", output.getvalue())
            self.assertIn("browser_auto_launch=false", output.getvalue())
            self.assertIn("gateway_started=false", output.getvalue())
            self.assertIn("Agents and subagents", output.getvalue())

    def test_interactive_dispatch_install_and_update_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            install_output = io.StringIO()
            with contextlib.redirect_stdout(install_output):
                result = dispatch_interactive_command("/install", paths)

            self.assertEqual(result, "install")
            self.assertIn("AEGIS TERMINAL INSTALL", install_output.getvalue())
            self.assertIn("install shim --approved", install_output.getvalue())
            self.assertIn("browser_auto_launch: false", install_output.getvalue())

            update_output = io.StringIO()
            with contextlib.redirect_stdout(update_output):
                result = dispatch_interactive_command("/update", paths)

            self.assertEqual(result, "update")
            self.assertIn("AEGIS TERMINAL UPDATE", update_output.getvalue())
            self.assertIn("needs_approval", update_output.getvalue())
            self.assertIn("origin", update_output.getvalue())
            self.assertIn("main", update_output.getvalue())

    def test_interactive_dispatch_automations_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                result = dispatch_interactive_command("/automations", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATIONS", listing.getvalue())
            self.assertIn("schedule_worker_started=false", listing.getvalue())

            created = io.StringIO()
            with contextlib.redirect_stdout(created):
                result = dispatch_interactive_command("/automations create daily-check | daily 00:00 | summarize workspace risks", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION", created.getvalue())
            self.assertIn("external_action_started=false", created.getvalue())
            job_id = next(line for line in created.getvalue().splitlines() if line.startswith("job")).split()[1]

            due = io.StringIO()
            with contextlib.redirect_stdout(due):
                result = dispatch_interactive_command("/automations due", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION DUE CHECK", due.getvalue())
            self.assertIn("schedule_worker_started=false", due.getvalue())

            tick = io.StringIO()
            with contextlib.redirect_stdout(tick):
                result = dispatch_interactive_command("/automations tick", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION TICK", tick.getvalue())
            self.assertIn("task", tick.getvalue())

            triggered = io.StringIO()
            with contextlib.redirect_stdout(triggered):
                result = dispatch_interactive_command(f"/automations trigger {job_id}", paths)

            self.assertEqual(result, "automations")
            self.assertIn("task", triggered.getvalue())
            self.assertIn("queued", triggered.getvalue())

            worker_job = io.StringIO()
            with contextlib.redirect_stdout(worker_job):
                result = dispatch_interactive_command("/automations create worker-check | now | summarize worker status", paths)

            self.assertEqual(result, "automations")

            worker = io.StringIO()
            with contextlib.redirect_stdout(worker):
                result = dispatch_interactive_command("/automations worker", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION WORKER", worker.getvalue())
            self.assertIn("schedule_worker_started=true", worker.getvalue())
            self.assertIn("task", worker.getvalue())

            logs = io.StringIO()
            with contextlib.redirect_stdout(logs):
                result = dispatch_interactive_command("/automations logs", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION WORKER LOGS", logs.getvalue())
            self.assertIn("started", logs.getvalue())
            self.assertIn("tick", logs.getvalue())
            self.assertIn("stopped", logs.getvalue())

            missed_job = io.StringIO()
            with contextlib.redirect_stdout(missed_job):
                result = dispatch_interactive_command("/automations create missed-check | now | summarize missed state", paths)

            self.assertEqual(result, "automations")

            missed = io.StringIO()
            with contextlib.redirect_stdout(missed):
                result = dispatch_interactive_command("/automations missed", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION MISSED RUNS", missed.getvalue())
            self.assertIn("missed-check", missed.getvalue())
            self.assertIn("schedule_worker_started=false", missed.getvalue())

            replay = io.StringIO()
            with contextlib.redirect_stdout(replay):
                result = dispatch_interactive_command("/automations replay", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION MISSED REPLAY", replay.getvalue())
            self.assertIn("task", replay.getvalue())
            self.assertIn("schedule_worker_started=false", replay.getvalue())

            service = io.StringIO()
            with contextlib.redirect_stdout(service):
                result = dispatch_interactive_command("/automations service", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION SERVICE WRAPPER", service.getvalue())
            self.assertIn("loaded=false", service.getvalue())
            self.assertIn("launchctl bootstrap", service.getvalue())
            self.assertTrue((paths.automations_dir / "automation-worker.sh").exists())

            service_status = io.StringIO()
            with contextlib.redirect_stdout(service_status):
                result = dispatch_interactive_command("/automations service-status", paths)

            self.assertEqual(result, "automations")
            self.assertIn("AEGIS AUTOMATION SERVICE STATUS", service_status.getvalue())
            self.assertIn("loaded=false", service_status.getvalue())
            self.assertIn("plist       exists=true", service_status.getvalue())
            self.assertIn("script      exists=true", service_status.getvalue())
            self.assertIn("health     status=wrapper_ready_worker_observed", service_status.getvalue())
            self.assertIn("worker_events=3", service_status.getvalue())

            paused = io.StringIO()
            with contextlib.redirect_stdout(paused):
                result = dispatch_interactive_command(f"/automations pause {job_id}", paths)

            self.assertEqual(result, "automations")
            self.assertIn("PAUSED", paused.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("automation.created", audit)
            self.assertIn("automation.due_checked", audit)
            self.assertIn("automation.due_run", audit)
            self.assertIn("automation.triggered", audit)
            self.assertIn("automation.status_changed", audit)
            self.assertIn("automation.worker_started", audit)
            self.assertIn("automation.worker_stopped", audit)
            self.assertIn("automation.worker_logs_viewed", audit)
            self.assertIn("automation.missed_checked", audit)
            self.assertIn("automation.missed_replayed", audit)
            self.assertIn("automation.service_wrapper_generated", audit)
            self.assertIn("automation.service_status_checked", audit)

    def test_interactive_dispatch_improve_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                result = dispatch_interactive_command("/improve", paths)

            self.assertEqual(result, "improve")
            self.assertIn("AEGIS IMPROVEMENTS", listing.getvalue())
            self.assertIn("workspace_mutation_allowed_before_approval=false", listing.getvalue())

            proposed = io.StringIO()
            with contextlib.redirect_stdout(proposed):
                result = dispatch_interactive_command("/improve propose prompt injection tried to leak secret credential", paths)

            self.assertEqual(result, "improve")
            self.assertIn("AEGIS IMPROVEMENT PROPOSAL", proposed.getvalue())
            self.assertIn("context_safety", proposed.getvalue())
            proposal_id = next(line for line in proposed.getvalue().splitlines() if line.startswith("proposal")).split()[1]

            approved = io.StringIO()
            with contextlib.redirect_stdout(approved):
                result = dispatch_interactive_command(f"/improve approve {proposal_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn("approved", approved.getvalue())

            candidate = io.StringIO()
            with contextlib.redirect_stdout(candidate):
                result = dispatch_interactive_command(f"/improve candidate {proposal_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn("AEGIS IMPROVEMENT CANDIDATE", candidate.getvalue())
            self.assertIn("workspace_mutation_performed=false", candidate.getvalue())
            candidate_id = next(line for line in candidate.getvalue().splitlines() if line.startswith("candidate")).split()[1]

            candidate_show = io.StringIO()
            with contextlib.redirect_stdout(candidate_show):
                result = dispatch_interactive_command(f"/improve candidate show {candidate_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn(candidate_id, candidate_show.getvalue())

            diff_review = io.StringIO()
            with contextlib.redirect_stdout(diff_review):
                result = dispatch_interactive_command(f"/improve diff {candidate_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn("AEGIS CANDIDATE DIFF REVIEW", diff_review.getvalue())
            self.assertIn("workspace_mutation_performed=false", diff_review.getvalue())

            verification = io.StringIO()
            with contextlib.redirect_stdout(verification):
                result = dispatch_interactive_command(f"/improve verify {candidate_id} 1", paths)

            self.assertEqual(result, "improve")
            self.assertIn("AEGIS IMPROVEMENT VERIFICATION", verification.getvalue())
            self.assertIn("passed", verification.getvalue())

            applied = io.StringIO()
            with contextlib.redirect_stdout(applied):
                result = dispatch_interactive_command(f"/improve apply {candidate_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn("apply", applied.getvalue())
            self.assertIn("watch      /tasks watch", applied.getvalue())
            task_id = next(line for line in applied.getvalue().splitlines() if line.startswith("task")).split()[1]
            task_path = paths.tasks_dir / f"{task_id}.json"
            self.assertTrue(task_path.exists())

            evidence = io.StringIO()
            with contextlib.redirect_stdout(evidence):
                result = dispatch_interactive_command(
                    f"/improve evidence {proposal_id} | src/aegisagent/core/improvement.py,tests/test_tui.py | PYTHONPATH=src python3 -m unittest tests.test_tui -v | passed",
                    paths,
                )

            self.assertEqual(result, "improve")
            self.assertIn("evidence_recorded", evidence.getvalue())

            completed = io.StringIO()
            with contextlib.redirect_stdout(completed):
                result = dispatch_interactive_command(f"/improve complete {proposal_id}", paths)

            self.assertEqual(result, "improve")
            self.assertIn("implemented", completed.getvalue())
            audit = (paths.state_dir / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("improvement.proposed", audit)
            self.assertIn("improvement.reviewed", audit)
            self.assertIn("improvement.candidate_generated", audit)
            self.assertIn("improvement.candidate_diff_reviewed", audit)
            self.assertIn("improvement.verification_run", audit)
            self.assertIn("improvement.candidate_apply_created", audit)
            self.assertIn("improvement.evidence_recorded", audit)
            self.assertIn("improvement.implemented", audit)

    def test_interactive_dispatch_lists_subagents_readably(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                dispatch_interactive_command("/subagents improve the terminal shell", paths)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/subagents list", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("SUBAGENTS", output.getvalue())
            self.assertIn("coordinator", output.getvalue())
            self.assertIn("usage: /subagents", output.getvalue())

    def test_interactive_dispatch_watches_subagent_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                dispatch_interactive_command("/subagents improve the terminal shell", paths)
            root_line = next(line for line in output.getvalue().splitlines() if line.startswith("root"))
            root_id = root_line.split()[1]

            timeline = io.StringIO()
            with contextlib.redirect_stdout(timeline):
                result = dispatch_interactive_command(f"/subagents watch {root_id}", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("SUBAGENT TIMELINE", timeline.getvalue())
            self.assertIn("worker.started", timeline.getvalue())

    def test_interactive_dispatch_live_subagents_static_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/subagents live improve streaming", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("SUBAGENT LIVE", output.getvalue())
            self.assertIn("SUBAGENT TIMELINE", output.getvalue())
            self.assertIn("worker.completed", output.getvalue())

    def test_interactive_dispatch_background_subagent_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with patch.dict("os.environ", {"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"}), contextlib.redirect_stdout(output):
                result = dispatch_interactive_command("/subagents bg improve background shell", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("SUBAGENT BACKGROUND JOB", output.getvalue())
            self.assertIn("monitor: /subagents monitor", output.getvalue())
            job_line = next(line for line in output.getvalue().splitlines() if line.startswith("job"))
            job_id = job_line.split()[1]
            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                dispatch_interactive_command("/subagents jobs", paths)
            self.assertIn("SUBAGENT BACKGROUND JOBS", listing.getvalue())
            monitor = io.StringIO()
            with contextlib.redirect_stdout(monitor):
                dispatch_interactive_command(f"/subagents monitor {job_id}", paths)
            self.assertIn("SUBAGENT BACKGROUND JOB", monitor.getvalue())
            self.assertIn("Composer remains active", monitor.getvalue())
            unwatch = io.StringIO()
            with contextlib.redirect_stdout(unwatch):
                dispatch_interactive_command("/subagents unwatch", paths)
            self.assertIn("stops the nonblocking subagent monitor", unwatch.getvalue())

    def test_interactive_dispatch_recovers_stale_subagent_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with patch.dict("os.environ", {"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"}), contextlib.redirect_stdout(output):
                dispatch_interactive_command("/subagents bg recover background shell", paths)
            job_line = next(line for line in output.getvalue().splitlines() if line.startswith("job"))
            job_id = job_line.split()[1]
            store = BackgroundJobStore(paths)
            record = store.get(job_id)
            record.status = "running"
            record.pid = 99999999
            store.save(record)

            recovered = io.StringIO()
            with contextlib.redirect_stdout(recovered):
                result = dispatch_interactive_command("/subagents recover", paths)

            self.assertEqual(result, "subagents")
            self.assertIn(job_id, recovered.getvalue())
            self.assertIn("failed", recovered.getvalue())
            self.assertEqual(store.get(job_id).status, "failed")

    def test_interactive_dispatch_cancels_background_subagent_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = runtime_paths(tmp)
            output = io.StringIO()
            with patch.dict("os.environ", {"AEGISAGENT_BACKGROUND_NO_SPAWN": "1"}), contextlib.redirect_stdout(output):
                dispatch_interactive_command("/subagents bg cancel background shell", paths)
            job_line = next(line for line in output.getvalue().splitlines() if line.startswith("job"))
            job_id = job_line.split()[1]

            cancelled = io.StringIO()
            with contextlib.redirect_stdout(cancelled):
                result = dispatch_interactive_command(f"/subagents cancel {job_id}", paths)

            self.assertEqual(result, "subagents")
            self.assertIn("cancelled", cancelled.getvalue())
            self.assertIn("Cancelled by operator", cancelled.getvalue())


if __name__ == "__main__":
    unittest.main()
