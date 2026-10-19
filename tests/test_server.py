import base64
import json
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from server import (
    AIRequestCancelled, CodexProjectRegistry, MANAGED_END, MANAGED_START, OpenAIAssistant,
    WorkflowHandler, WorkflowServer, WorkflowStore, slugify,
)


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = WorkflowStore(self.root)
        agent = self.root / "agents" / "writer"
        agent.mkdir(parents=True)
        (agent / "AGENT.md").write_text(
            "---\nname: Writer\ndescription: Writes the final answer.\n---\n\n# Writer\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def workflow(self):
        return {
            "id": "demo",
            "name": "Demo",
            "description": "A test workflow",
            "nodes": [
                {
                    "id": "a",
                    "agentId": "agents-writer",
                    "label": "Writer",
                    "role": "Draft",
                    "entrypoint": "agents/writer/AGENT.md",
                    "position": {"x": 10, "y": 20},
                },
                {
                    "id": "b",
                    "agentId": "agents-writer",
                    "label": "Reviewer",
                    "role": "Review",
                    "entrypoint": "agents/writer/AGENT.md",
                    "position": {"x": 250, "y": 20},
                },
            ],
            "edges": [{"id": "e", "source": "a", "target": "b", "condition": "draft ready"}],
        }

    def test_discovers_markdown_agent(self):
        agents = self.store.discover_agents()
        self.assertEqual(agents[0]["name"], "Writer")
        self.assertEqual(agents[0]["entrypoint"], "agents/writer/AGENT.md")

    def test_rejects_cycles(self):
        workflow = self.workflow()
        workflow["edges"].append({"id": "back", "source": "b", "target": "a"})
        errors, _ = self.store.validate(workflow)
        self.assertTrue(any("cycle" in error for error in errors))

    def test_save_generates_codex_files_and_preserves_manual_agents_text(self):
        (self.root / "AGENTS.md").write_text("# Manual instructions\n\nKeep this.\n", encoding="utf-8")
        result = self.store.save_workflow("demo", self.workflow())
        self.assertEqual(len(result["syncedFiles"]), 4)
        manifest = json.loads((self.root / ".codex/workflows/demo.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], 1)
        skill = (self.root / ".agents/skills/workflow-demo/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: workflow-demo", skill)
        self.assertIn("Writer", skill)
        agents_md = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# Manual instructions", agents_md)
        self.assertIn(MANAGED_START, agents_md)
        self.assertIn(MANAGED_END, agents_md)

    def test_slugify_is_path_safe(self):
        self.assertEqual(slugify("../../My Flow"), "my-flow")

    def test_agent_edit_generates_callable_project_skill(self):
        self.store.save_action("draft-document", {
            "id": "draft-document", "name": "Draft document", "description": "Write a draft through a fixed executor.",
            "executor": "script", "inputs": {}, "steps": ["run draft script"], "success": {"exitCode": 0},
            "outputs": {"file": "string"}, "timeoutSeconds": 60,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        })
        result = self.store.save_agent(
            "agents-writer",
            {
                "name": "Editorial Writer",
                "description": "Drafts a clear final response.",
                "model": "inherit",
                "instructions": "Use upstream evidence.",
                "allowedActions": ["draft-document"],
                "skills": ["fact-check"],
            },
        )
        self.assertEqual(len(result["syncedFiles"]), 5)
        source = (self.root / "agents/writer/AGENT.md").read_text(encoding="utf-8")
        self.assertIn("name: \"Editorial Writer\"", source)
        self.assertIn("# Writer", source)
        skill = (self.root / ".agents/skills/agent-agents-writer/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Use upstream evidence.", skill)
        self.assertIn("$fact-check", skill)
        self.assertIn("draft-document", skill)

    def test_skill_library_reads_and_updates_project_skill(self):
        skill_root = self.root / "tools" / "fact-check"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: fact-check\ndescription: Check claims against project sources.\n---\n\n# Fact check\n",
            encoding="utf-8",
        )
        skill = self.store.discover_skills()[0]
        result = self.store.save_skill(
            skill["id"],
            {"name": "fact-check", "description": "Verify important claims.", "instructions": "# Verify\n\nReturn sources."},
        )
        self.assertEqual(result["skill"]["name"], "fact-check")
        self.assertEqual(
            result["syncedFiles"],
            ["tools/fact-check/SKILL.md", "tools/fact-check/agents/openai.yaml"],
        )
        self.assertIn("Return sources.", (skill_root / "SKILL.md").read_text(encoding="utf-8"))
        metadata = (skill_root / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "fact-check"', metadata)
        self.assertIn('short_description: "Verify important claims."', metadata)

    def test_ai_agent_draft_only_writes_after_explicit_publish(self):
        draft = {
            "kind": "agent",
            "name": "Brief Analyst",
            "description": "Turns a request into a concise brief.",
            "instructions": "Identify the goal, constraints, and expected output.",
            "model": "inherit",
            "actions": [{"id": "brief", "name": "Brief", "instruction": "Create the brief."}],
            "skills": [],
            "targetAgentId": "",
        }
        self.assertFalse((self.root / "agents/brief-analyst/AGENT.md").exists())
        result = self.store.publish_ai_draft(draft)
        self.assertEqual(result["kind"], "agent")
        self.assertTrue((self.root / "agents/brief-analyst/AGENT.md").exists())
        self.assertTrue((self.root / ".agents/skills/agent-agents-brief-analyst/SKILL.md").exists())

    def test_ai_can_update_existing_agent_without_creating_a_duplicate(self):
        result = self.store.publish_ai_draft({
            "kind": "agent", "name": "Updated Writer", "description": "Updated role.",
            "instructions": "Use the confirmed style.", "model": "inherit",
            "actions": [{"id": "write", "name": "Write", "instruction": "Draft the answer."}],
            "skills": [], "targetAgentId": "agents-writer",
        })
        self.assertEqual(result["agent"]["id"], "agents-writer")
        self.assertEqual(result["agent"]["name"], "Updated Writer")
        self.assertEqual(len(self.store.discover_agents()), 1)

    def test_ai_action_publish_creates_independent_project_action(self):
        result = self.store.publish_ai_draft({
            "kind": "action", "name": "Verify", "description": "Verify the draft.",
            "instructions": "Check important claims.", "model": "inherit",
            "actions": [], "allowedActions": [],
            "actionJson": json.dumps({
                "id": "verify", "name": "Verify", "description": "Verify the draft.", "executor": "api",
                "inputs": {"document": "string"}, "steps": ["call verification endpoint"],
                "success": {"verified": True}, "outputs": {"verified": "boolean"}, "timeoutSeconds": 30,
                "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": ["verification-api"],
            }),
            "skills": [], "targetAgentId": "",
        })
        self.assertEqual(result["action"]["id"], "verify")
        self.assertEqual(result["action"]["credentialRefs"], ["verification-api"])
        self.assertTrue((self.root / ".workflow-studio/actions/verify.json").exists())

    def test_ai_action_publish_does_not_overwrite_unrelated_existing_action(self):
        original = {
            "id": "verify", "name": "Original", "executor": "api", "inputs": {}, "steps": [],
            "success": {}, "outputs": {}, "timeoutSeconds": 30,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        }
        self.store.save_action("verify", original)
        draft = {
            "kind": "action", "name": "Replacement", "description": "", "instructions": "",
            "actions": [], "allowedActions": [], "skills": [], "targetAgentId": "",
            "actionJson": json.dumps({**original, "name": "Replacement"}),
        }
        with self.assertRaises(FileExistsError):
            self.store.publish_ai_draft(draft)
        self.assertEqual(self.store.get_action("verify")["name"], "Original")

    def test_action_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "credentialRefs"):
            self.store.save_action("unsafe", {
                "id": "unsafe", "name": "Unsafe", "executor": "api", "inputs": {"apiKey": "secret-value"},
                "steps": [], "success": {}, "outputs": {}, "timeoutSeconds": 30,
                "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
            })

    def test_action_connection_round_trips_for_api_and_mcp(self):
        api = self.store.save_action("api-request", {
            "id": "api-request", "name": "API Request", "executor": "api",
            "connection": {"kind": "http", "endpoint": "https://example.com", "healthCheck": {"method": "GET", "path": "/health", "expectedStatuses": [200]}},
            "inputs": {}, "steps": [], "success": {}, "outputs": {}, "timeoutSeconds": 10,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": ["example-api"],
        })["action"]
        mcp = self.store.save_action("mcp-tool", {
            "id": "mcp-tool", "name": "MCP Tool", "executor": "mcp",
            "connection": {"kind": "mcp", "transport": "streamable-http", "endpoint": "http://127.0.0.1:3000/mcp"},
            "inputs": {}, "steps": [{"type": "mcp.call_tool", "tool": "demo"}], "success": {}, "outputs": {}, "timeoutSeconds": 10,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        })["action"]
        self.assertEqual(api["schemaVersion"], 2)
        self.assertEqual(self.store.get_action("api-request")["connection"]["healthCheck"]["method"], "GET")
        self.assertEqual(mcp["connection"]["transport"], "streamable-http")

    def test_action_create_only_precondition_prevents_stale_overwrite(self):
        original = {
            "id": "shared", "name": "Original", "executor": "api", "inputs": {}, "steps": [],
            "success": {}, "outputs": {}, "timeoutSeconds": 10,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        }
        self.store.save_action("shared", original)
        with self.assertRaises(FileExistsError):
            self.store.save_action("shared", {**original, "name": "Stale draft"}, allow_overwrite=False)
        self.assertEqual(self.store.get_action("shared")["name"], "Original")

    def test_action_connection_rejects_embedded_query_credentials_and_mismatch(self):
        common = {
            "id": "unsafe", "name": "Unsafe", "executor": "api", "inputs": {}, "steps": [],
            "success": {}, "outputs": {}, "timeoutSeconds": 10,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        }
        with self.assertRaisesRegex(ValueError, "\u67e5\u8be2\u53c2\u6570"):
            self.store.save_action("unsafe", {**common, "connection": {"kind": "http", "endpoint": "https://example.com?api_key=secret"}})
        with self.assertRaisesRegex(ValueError, "API Action"):
            self.store.save_action("unsafe", {**common, "connection": {"kind": "mcp", "transport": "streamable-http", "endpoint": "https://example.com/mcp"}})
        with self.assertRaisesRegex(ValueError, "本地路径"):
            self.store.save_action("unsafe", {**common, "connection": {"kind": "http", "endpoint": "https://example.com", "healthCheck": {"path": "//metadata.invalid/latest"}}})
        with self.assertRaisesRegex(ValueError, "查询参数"):
            self.store.save_action("unsafe", {**common, "connection": {"kind": "http", "endpoint": "https://example.com", "healthCheck": {"path": "/health?token=secret"}}})

    def test_action_connection_rejects_auth_like_query_credentials(self):
        common = {
            "id": "unsafe", "name": "Unsafe", "executor": "api", "inputs": {}, "steps": [],
            "success": {}, "outputs": {}, "timeoutSeconds": 10,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        }
        for query_name in ("auth", "key", "signature", "cookie"):
            with self.subTest(location="endpoint", query_name=query_name):
                with self.assertRaisesRegex(ValueError, "查询参数"):
                    self.store.save_action("unsafe", {
                        **common,
                        "connection": {"kind": "http", "endpoint": f"https://example.com?{query_name}=secret"},
                    })
            with self.subTest(location="healthCheck", query_name=query_name):
                with self.assertRaisesRegex(ValueError, "查询参数"):
                    self.store.save_action("unsafe", {
                        **common,
                        "connection": {
                            "kind": "http",
                            "endpoint": "https://example.com",
                            "healthCheck": {"path": f"/health?{query_name}=secret"},
                        },
                    })

    def test_connection_target_rejects_private_and_link_local_addresses(self):
        for address in ("10.12.0.8", "169.254.169.254"):
            address_info = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))]
            with self.subTest(address=address):
                with patch("server.socket.getaddrinfo", return_value=address_info):
                    with self.assertRaises(ValueError):
                        WorkflowStore._validate_connection_target("https://service.example/health")

    def test_connection_target_allows_public_and_loopback_addresses(self):
        cases = (
            ("https://service.example/health", "93.184.216.34", 443),
            ("http://localhost:3000/mcp", "127.0.0.1", 3000),
        )
        for endpoint, address, port in cases:
            address_info = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]
            with self.subTest(endpoint=endpoint, address=address):
                with patch("server.socket.getaddrinfo", return_value=address_info):
                    self.assertEqual(WorkflowStore._validate_connection_target(endpoint), address)

    def test_connection_check_uses_one_timeout_budget_across_all_addresses(self):
        clock = [10.0]
        attempts = []

        class FailingOpener:
            def open(self, _request, timeout):
                attempts.append(timeout)
                clock[0] += 3.0
                raise urllib.error.URLError("unreachable")

        request = urllib.request.Request("https://service.example/health", method="HEAD")
        with patch.object(
            WorkflowStore, "_validated_connection_targets",
            return_value=["93.184.216.34", "1.1.1.1", "8.8.8.8"],
        ), patch("server.urllib.request.build_opener", return_value=FailingOpener()), patch(
            "server.time.monotonic", side_effect=lambda: clock[0]
        ):
            with self.assertRaisesRegex(TimeoutError, "超时"):
                WorkflowStore._connection_request(request, 5)

        self.assertEqual(len(attempts), 2)
        self.assertAlmostEqual(attempts[0], 5.0)
        self.assertAlmostEqual(attempts[1], 2.0)

    @patch.object(WorkflowStore, "_connection_request", return_value=(204, {"content-type": "application/json"}, b""))
    def test_api_connection_check_is_a_read_only_health_probe(self, request):
        before = set(self.root.rglob("*"))
        result = self.store.check_action_connection({
            "id": "api", "name": "API", "executor": "api",
            "connection": {"kind": "http", "endpoint": "https://example.com", "healthCheck": {"method": "HEAD", "path": "/health", "expectedStatuses": [204]}},
            "inputs": {}, "steps": [], "success": {}, "outputs": {}, "timeoutSeconds": 5,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        })
        self.assertTrue(result["connected"])
        self.assertEqual(request.call_args.args[0].method, "HEAD")
        self.assertEqual(set(self.root.rglob("*")), before)

    @patch.object(WorkflowStore, "_connection_request")
    def test_mcp_connection_check_only_performs_initialize(self, request):
        response = {"jsonrpc": "2.0", "id": "workflow-studio-connection-check", "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "Demo MCP", "version": "1"}, "capabilities": {}}}
        request.return_value = (200, {"content-type": "application/json"}, json.dumps(response).encode())
        result = self.store.check_action_connection({
            "id": "mcp", "name": "MCP", "executor": "mcp",
            "connection": {"kind": "mcp", "transport": "streamable-http", "endpoint": "http://127.0.0.1:3000/mcp"},
            "inputs": {}, "steps": [], "success": {}, "outputs": {}, "timeoutSeconds": 5,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        })
        sent = json.loads(request.call_args.args[0].data.decode())
        self.assertTrue(result["connected"])
        self.assertEqual(sent["method"], "initialize")
        self.assertNotIn("tools/call", request.call_args.args[0].data.decode())

    def test_mcp_sse_probe_stops_after_initialize_event_without_waiting_for_eof(self):
        release = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                notification = 'data: {"jsonrpc":"2.0","method":"notifications/initialized"}\n\n'
                result = (
                    'data: {"jsonrpc":"2.0",\n'
                    'data: "id":"workflow-studio-connection-check","result":{"protocolVersion":"2025-06-18","serverInfo":{"name":"SSE MCP"}}}\n\n'
                )
                self.wfile.write((notification + result).encode())
                self.wfile.flush()
                release.wait(2)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            result = self.store.check_action_connection({
                "id": "mcp", "name": "MCP", "executor": "mcp",
                "connection": {"kind": "mcp", "transport": "streamable-http", "endpoint": f"http://127.0.0.1:{server.server_port}/mcp"},
                "inputs": {}, "steps": [], "success": {}, "outputs": {}, "timeoutSeconds": 2,
                "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
            })
        finally:
            release.set()
            server.shutdown()
            server.server_close()
        self.assertTrue(result["connected"])
        self.assertLess(time.monotonic() - started, 1.5)

    def test_connection_timeout_includes_slow_sse_body(self):
        release = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                while not release.wait(0.04):
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/mcp", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(TimeoutError, "超时"):
                WorkflowStore._connection_request(request, 0.2, "missing-initialize-id")
            self.assertLess(time.monotonic() - started, 0.7)
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(1)

    def test_workflow_action_node_requires_agent_allowlist(self):
        self.store.save_action("verify", {
            "id": "verify", "name": "Verify", "description": "Verify deterministically.", "executor": "api",
            "inputs": {}, "steps": ["call API"], "success": {}, "outputs": {}, "timeoutSeconds": 30,
            "errorHandling": {"strategy": "stop", "retries": 0}, "credentialRefs": [],
        })
        agent = self.store.get_agent("agents-writer")
        agent["allowedActions"] = ["verify"]
        self.store.save_agent("agents-writer", agent)
        workflow = self.workflow()
        workflow["nodes"].append({
            "id": "verify-node", "type": "action", "actionId": "verify", "agentId": "agents-writer",
            "label": "Verify", "position": {"x": 500, "y": 20},
        })
        workflow["edges"].append({"id": "to-verify", "source": "b", "target": "verify-node", "condition": "ready"})
        errors, _ = self.store.validate(workflow)
        self.assertEqual(errors, [])
        self.store.save_workflow("mixed", workflow)
        generated = (self.root / ".agents/skills/workflow-mixed/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Action `verify`", generated)
        workflow["nodes"][-1]["agentId"] = "missing-agent"
        errors, _ = self.store.validate(workflow)
        self.assertTrue(any("已授权它的 Agent" in error for error in errors))

    def test_ai_skill_publish_generates_valid_codex_metadata(self):
        result = self.store.publish_ai_draft({
            "kind": "skill", "name": "release-check", "description": "Check release readiness.",
            "instructions": "# Release check\n\nVerify tests and list blockers.", "model": "inherit",
            "actions": [], "skills": [], "targetAgentId": "",
        })
        self.assertEqual(result["skill"]["name"], "release-check")
        yaml = (self.root / ".agents/skills/release-check/agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "release-check"', yaml)
        self.assertIn('default_prompt: "Use $release-check', yaml)

    @patch("server.subprocess.run")
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_unpublished_agent_test_is_read_only(self, _which, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="Draft output", stderr="")
        before = set(path.relative_to(self.root) for path in self.root.rglob("*"))
        result = self.store.smoke_test_agent_draft({"draft": {"kind": "agent", "instructions": "Respond clearly."}, "input": "hello"})
        after = set(path.relative_to(self.root) for path in self.root.rglob("*"))
        self.assertTrue(result["passed"])
        self.assertEqual(before, after)
        command = run.call_args.args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("read-only", command)
        # An inherited stdin pipe makes `codex exec` wait for more input until the timeout.
        self.assertIs(run.call_args.kwargs.get("stdin"), subprocess.DEVNULL)

    @patch("server.subprocess.run")
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_unpublished_agent_timeout_is_reported_to_the_background_queue(self, _which, run):
        run.side_effect = subprocess.TimeoutExpired(["codex", "exec"], 90)
        with self.assertRaises(TimeoutError):
            self.store.smoke_test_agent_draft(
                {"draft": {"kind": "agent", "instructions": "Respond clearly."}}
            )

    @patch("server.subprocess.run")
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_agent_timeout_keeps_codex_output_for_diagnosis(self, _which, run):
        run.side_effect = subprocess.TimeoutExpired(
            ["codex", "exec"], 90, output=b"", stderr=b"stream disconnected - retrying turn"
        )
        with self.assertRaises(TimeoutError) as raised:
            self.store.smoke_test_agent_draft(
                {"draft": {"kind": "agent", "instructions": "Respond clearly."}}
            )
        self.assertIn("stream disconnected", str(raised.exception))
        self.assertIn("超时", str(raised.exception))

    @patch("server.subprocess.run")
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_agent_smoke_test_is_ephemeral_and_read_only(self, _which, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="READY Writer loaded", stderr="")
        result = self.store.smoke_test_agent("agents-writer")
        self.assertTrue(result["passed"])
        command = run.call_args.args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("read-only", command)
        self.assertIs(run.call_args.kwargs.get("stdin"), subprocess.DEVNULL)


class CodexProjectRegistryTests(unittest.TestCase):
    def test_lists_titles_without_paths_until_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "project"
            project_root.mkdir()
            database = root / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE projects (id TEXT, name TEXT, position INTEGER);"
                "CREATE TABLE project_roots (project_id TEXT, position INTEGER, path TEXT);"
            )
            connection.execute("INSERT INTO projects VALUES ('p1', 'Project One', 0)")
            connection.execute("INSERT INTO project_roots VALUES ('p1', 0, ?)", (str(project_root),))
            connection.commit()
            connection.close()
            registry = CodexProjectRegistry(project_root, root)
            public = registry.list_projects()
            self.assertEqual(public[0]["title"], "Project One")
            self.assertNotIn("path", public[0])
            self.assertEqual(registry.select("p1")["path"], str(project_root.resolve()))


class WorkflowServerProjectIsolationTests(unittest.TestCase):
    PROJECT_A = "project-a"
    PROJECT_B = "project-b"
    WORKFLOW_ID = "shared-workflow"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project_roots = {
            self.PROJECT_A: self.root / "project-a-root",
            self.PROJECT_B: self.root / "project-b-root",
        }
        for project_id, project_root in self.project_roots.items():
            project_root.mkdir()
            WorkflowStore(project_root).save_workflow(
                self.WORKFLOW_ID,
                self.workflow_payload(f"Workflow from {project_id}"),
            )

        codex_home = self.root / "codex-home"
        codex_home.mkdir()
        connection = sqlite3.connect(codex_home / "state_5.sqlite")
        connection.executescript(
            "CREATE TABLE projects (id TEXT, name TEXT, position INTEGER);"
            "CREATE TABLE project_roots (project_id TEXT, position INTEGER, path TEXT);"
        )
        for position, (project_id, project_root) in enumerate(self.project_roots.items()):
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?)",
                (project_id, project_id, position),
            )
            connection.execute(
                "INSERT INTO project_roots VALUES (?, 0, ?)",
                (project_id, str(project_root)),
            )
        connection.commit()
        connection.close()

        web_root = Path(__file__).resolve().parents[1] / "web"
        self.server = WorkflowServer(
            ("127.0.0.1", 0),
            WorkflowStore(self.project_roots[self.PROJECT_A]),
            web_root,
            state_path=self.root / "studio-state.sqlite3",
        )
        self.server.registry = CodexProjectRegistry(
            self.project_roots[self.PROJECT_A], codex_home
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        for project_id in self.project_roots:
            status, _payload = self.request_json(
                "POST", f"/api/codex/projects/{project_id}/import"
            )
            self.assertEqual(status, 200)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)
        self.temporary.cleanup()

    def workflow_payload(self, name):
        return {
            "id": self.WORKFLOW_ID,
            "name": name,
            "description": f"Sentinel for {name}",
            "nodes": [],
            "edges": [],
            "updatedAt": "2026-09-21T00:00:00Z",
        }

    def request_json(self, method, path, body=None, project_id=None, headers=None):
        request_headers = {"Content-Type": "application/json", "Origin": self.origin}
        if project_id is not None:
            request_headers["X-Workflow-Studio-Project-Id"] = project_id
        request_headers.update({key: str(value) for key, value in (headers or {}).items()})
        data = None
        if body is not None or method in {"POST", "PUT"}:
            data = json.dumps(body or {}).encode()
        request = urllib.request.Request(
            self.origin + path,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())
        with response:
            return response.status, json.loads(response.read().decode())

    def get_workflow(self, project_id, header_project_id=None):
        return self.request_json(
            "GET",
            f"/api/projects/{project_id}/workflows/{self.WORKFLOW_ID}",
            project_id=header_project_id,
        )

    def test_same_workflow_id_stays_isolated_across_interleaved_syncs(self):
        status, synced_a = self.request_json(
            "POST", f"/api/codex/projects/{self.PROJECT_A}/sync"
        )
        self.assertEqual(status, 200)
        self.assertEqual(synced_a["project"]["id"], self.PROJECT_A)
        self.assertEqual(synced_a["workflows"][0]["name"], "Workflow from project-a")

        status, synced_b = self.request_json(
            "POST", f"/api/codex/projects/{self.PROJECT_B}/sync"
        )
        self.assertEqual(status, 200)
        self.assertEqual(synced_b["project"]["id"], self.PROJECT_B)
        self.assertEqual(synced_b["workflows"][0]["name"], "Workflow from project-b")

        status, detail_a = self.get_workflow(self.PROJECT_A, self.PROJECT_A)
        self.assertEqual(status, 200)
        self.assertEqual(detail_a["projectId"], self.PROJECT_A)
        self.assertEqual(detail_a["workflow"]["name"], "Workflow from project-a")

        status, detail_b = self.get_workflow(self.PROJECT_B, self.PROJECT_B)
        self.assertEqual(status, 200)
        self.assertEqual(detail_b["projectId"], self.PROJECT_B)
        self.assertEqual(detail_b["workflow"]["name"], "Workflow from project-b")

    def test_project_path_and_header_mismatch_is_rejected(self):
        status, payload = self.get_workflow(self.PROJECT_A, self.PROJECT_B)
        self.assertEqual(status, 409)
        self.assertTrue(payload["projectChanged"])

        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_A]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Workflow from project-a",
        )
        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_B]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Workflow from project-b",
        )

    def test_syncing_project_b_does_not_change_project_a_request_context(self):
        status, before = self.get_workflow(self.PROJECT_A)
        self.assertEqual(status, 200)

        status, _synced_b = self.request_json(
            "POST", f"/api/codex/projects/{self.PROJECT_B}/sync"
        )
        self.assertEqual(status, 200)

        updated_a = dict(before["workflow"])
        updated_a["name"] = "Project A after Project B sync"
        status, saved_a = self.request_json(
            "PUT",
            f"/api/projects/{self.PROJECT_A}/workflows/{self.WORKFLOW_ID}",
            body=updated_a,
            project_id=self.PROJECT_A,
            headers={"If-Match": before["revision"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(saved_a["projectId"], self.PROJECT_A)

        # Autosave is Studio-only; the Codex project is unchanged until the
        # resource is published and explicitly synced.
        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_A]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Workflow from project-a",
        )

        status, _published = self.request_json(
            "POST",
            f"/api/projects/{self.PROJECT_A}/workflows/{self.WORKFLOW_ID}/publish",
            body={},
            project_id=self.PROJECT_A,
        )
        self.assertEqual(status, 200)
        status, synced = self.request_json(
            "POST",
            f"/api/projects/{self.PROJECT_A}/workflows/{self.WORKFLOW_ID}/sync",
            body={},
            project_id=self.PROJECT_A,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(synced["succeeded"]), 1)

        status, detail_b = self.get_workflow(self.PROJECT_B)
        self.assertEqual(status, 200)
        self.assertEqual(detail_b["workflow"]["name"], "Workflow from project-b")
        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_A]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Project A after Project B sync",
        )
        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_B]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Workflow from project-b",
        )

    def test_stale_if_match_is_rejected_and_keeps_newer_content(self):
        status, initial = self.get_workflow(self.PROJECT_A)
        self.assertEqual(status, 200)
        stale_revision = initial["revision"]

        newer = dict(initial["workflow"])
        newer["name"] = "Newer Project A content"
        status, saved = self.request_json(
            "PUT",
            f"/api/projects/{self.PROJECT_A}/workflows/{self.WORKFLOW_ID}",
            body=newer,
            headers={"If-Match": stale_revision},
        )
        self.assertEqual(status, 200)
        self.assertNotEqual(saved["revision"], stale_revision)

        stale = dict(initial["workflow"])
        stale["name"] = "Stale content that must not win"
        status, conflict = self.request_json(
            "PUT",
            f"/api/projects/{self.PROJECT_A}/workflows/{self.WORKFLOW_ID}",
            body=stale,
            headers={"If-Match": stale_revision},
        )
        self.assertEqual(status, 409)
        self.assertTrue(conflict["revisionConflict"])
        self.assertEqual(conflict["currentRevision"], saved["revision"])

        status, current = self.get_workflow(self.PROJECT_A)
        self.assertEqual(status, 200)
        self.assertEqual(current["revision"], saved["revision"])
        self.assertEqual(current["workflow"]["name"], "Newer Project A content")
        self.assertEqual(
            WorkflowStore(self.project_roots[self.PROJECT_A]).get_workflow(
                self.WORKFLOW_ID
            )["name"],
            "Workflow from project-a",
        )


class OpenAIAssistantTests(unittest.TestCase):
    def test_post_routes_require_same_origin_and_request_project_context(self):
        with tempfile.TemporaryDirectory() as directory:
            handler = lambda *args, **kwargs: WorkflowHandler(  # noqa: E731
                *args, directory=directory, **kwargs
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            project_stores = {"project-a": object(), "project-b": object()}
            project_locks = {project_id: threading.RLock() for project_id in project_stores}
            server.project_context = MagicMock(side_effect=lambda project_id: (
                {"id": project_id, "title": project_id, "path": directory},
                project_stores[project_id],
                project_locks[project_id],
            ))
            server.ai = SimpleNamespace(
                cancel_request=MagicMock(return_value={"cancelled": True}),
                chat=MagicMock(return_value={
                    "status": "clarifying", "message": "ok", "questions": [], "draft": {},
                }),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"

            def post(path, body, request_origin, project_id=None):
                headers = {"Content-Type": "text/plain", "Origin": request_origin}
                if project_id is not None:
                    headers["X-Workflow-Studio-Project-Id"] = project_id
                request = urllib.request.Request(
                    origin + path, data=json.dumps(body).encode(), headers=headers, method="POST"
                )
                return urllib.request.urlopen(request, timeout=2)

            try:
                with self.assertRaises(urllib.error.HTTPError) as cross_origin:
                    post("/api/ai/cancel", {"requestId": "request-123"}, "https://evil.example")
                self.assertEqual(cross_origin.exception.code, 403)
                server.ai.cancel_request.assert_not_called()

                with post("/api/ai/cancel", {"requestId": "request-123"}, origin) as response:
                    self.assertEqual(response.status, 200)
                server.ai.cancel_request.assert_called_once()

                with self.assertRaises(urllib.error.HTTPError) as missing_project:
                    post("/api/ai/chat", {"kind": "agent"}, origin)
                self.assertEqual(missing_project.exception.code, 409)
                server.ai.chat.assert_not_called()

                with post("/api/ai/chat", {"kind": "agent"}, origin, "project-a") as response:
                    self.assertEqual(response.status, 200)
                self.assertIs(server.ai.chat.call_args.args[1], project_stores["project-a"])

                with post("/api/projects/project-b/ai/chat", {"kind": "agent"}, origin) as response:
                    self.assertEqual(response.status, 200)
                self.assertIs(server.ai.chat.call_args.args[1], project_stores["project-b"])
                self.assertEqual(server.ai.chat.call_count, 2)
                self.assertEqual(
                    [call.args[0] for call in server.project_context.call_args_list],
                    ["project-a", "project-b"],
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(1)

    def test_cancel_before_request_registration_prevents_request_from_starting(self):
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
        request_id = "cancel-before-register"
        result = assistant.cancel_request({"requestId": request_id})
        self.assertTrue(result["cancelled"])
        with self.assertRaises(AIRequestCancelled):
            assistant._begin_request(request_id)

    def test_cancel_interrupts_waiting_for_api_response_headers(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(2)
        port = listener.getsockname()[1]
        request_received = threading.Event()
        release_server = threading.Event()

        def hold_response():
            connection, _address = listener.accept()
            try:
                connection.recv(4096)
                request_received.set()
                release_server.wait(2)
            finally:
                connection.close()
                listener.close()

        threading.Thread(target=hold_response, daemon=True).start()
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
        token = assistant._begin_request("cancel-before-headers")
        errors = []

        def send_request():
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/responses", data=b"{}",
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                assistant._request_json(request, token, 10)
            except Exception as error:  # noqa: BLE001 - asserted below
                errors.append(error)
            finally:
                assistant._finish_request(token)

        worker = threading.Thread(target=send_request)
        worker.start()
        self.assertTrue(request_received.wait(1))
        self.assertTrue(assistant.cancel_request({"requestId": token.request_id})["cancelled"])
        worker.join(1)
        release_server.set()
        self.assertFalse(worker.is_alive())
        self.assertTrue(any(isinstance(error, AIRequestCancelled) for error in errors))

    def test_model_request_rejects_redirect_without_following_it(self):
        redirected_requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path == "/responses":
                    body = b'{"redirected":true}'
                    self.send_response(307)
                    self.send_header("Location", "/redirected")
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                redirected_requests.append(self.path)
                body = b'{"output_text":"should not be reached"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
        token = assistant._begin_request(None)
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/responses",
                data=b"{}", headers={"Content-Type": "application/json"}, method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                assistant._request_json(request, token, 5)
            self.assertEqual(raised.exception.code, 307)
            self.assertEqual(redirected_requests, [])
        finally:
            assistant._finish_request(token)
            server.shutdown()
            server.server_close()
            thread.join(1)

    @patch.object(OpenAIAssistant, "_request_json")
    def test_usage_guide_chat_is_read_only_and_returns_plain_answer(self, request_json):
        request_json.return_value = {"output_text": "先创建 Action，再在 Agent 页面授权。"}
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model", base_url="https://models.example/v1")
        with tempfile.TemporaryDirectory() as directory:
            result = assistant.help_chat({"messages": [{"role": "user", "content": "怎么添加 Action？"}]}, WorkflowStore(Path(directory)))
        self.assertIn("Agent", result["message"])
        request = request_json.call_args.args[0]
        body = json.loads(request.data.decode())
        self.assertNotIn("tools", body)
        self.assertNotIn("server-secret", json.dumps(result))

    @patch.object(OpenAIAssistant, "_request_json")
    def test_global_usage_guide_omits_project_context(self, request_json):
        request_json.return_value = {"output_text": "先了解 Agent、Action、Skill 和 Workflow 的边界。"}
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model", base_url="https://models.example/v1")

        result = assistant.help_chat({"messages": [{"role": "user", "content": "Workflow 是什么？"}]}, None)

        self.assertIn("Agent", result["message"])
        request = request_json.call_args.args[0]
        body = json.loads(request.data.decode())
        instructions = body["instructions"]
        self.assertIn('"scope": "general"', instructions)
        self.assertIn('"project": null', instructions)
        self.assertIn('"resourceCounts": null', instructions)
        self.assertNotIn(str(Path.cwd()), instructions)
        self.assertNotIn("server-secret", json.dumps(result))

    @patch.object(OpenAIAssistant, "_run_codex")
    def test_global_codex_guide_uses_isolated_working_directory(self, run_codex):
        assistant = OpenAIAssistant()
        assistant.codex = "/fake/codex"
        captured = {}

        def run(command, timeout, token, timeout_message, input_text=None):
            captured["command"] = command
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("通用 Workflow 用法。", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        run_codex.side_effect = run
        token = assistant._begin_request(None)
        try:
            answer = assistant._help_with_codex("guide", [], None, token)
        finally:
            assistant._finish_request(token)

        command = captured["command"]
        working_directory = command[command.index("-C") + 1]
        attachment_directory = command[command.index("--add-dir") + 1]
        self.assertEqual(answer, "通用 Workflow 用法。")
        self.assertEqual(working_directory, attachment_directory)
        self.assertNotEqual(Path(working_directory).resolve(), Path.cwd().resolve())

    @patch.object(OpenAIAssistant, "_open_model_catalog")
    def test_model_discovery_uses_unsaved_form_values_without_exposing_key(
        self, open_model_catalog
    ):
        response = MagicMock()
        response.read.return_value = json.dumps({"data": [{"id": "model-b"}, {"id": "model-a"}]}).encode()
        response.__enter__.return_value = response
        open_model_catalog.return_value = response
        assistant = OpenAIAssistant()
        result = assistant.list_models({"apiKey": "temporary-secret", "baseUrl": "https://models.example/v1"})
        self.assertEqual(result["models"], ["model-a", "model-b"])
        self.assertNotIn("temporary-secret", json.dumps(result))
        self.assertEqual(
            open_model_catalog.call_args.args[0].full_url,
            "https://models.example/v1/models",
        )

    @patch.object(OpenAIAssistant, "_open_model_catalog")
    def test_browser_config_update_preserves_saved_key_when_field_is_blank(
        self, open_model_catalog
    ):
        response = MagicMock()
        response.read.return_value = json.dumps({"data": [{"id": "new-model"}]}).encode()
        response.__enter__.return_value = response
        open_model_catalog.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "AI Assistant Info.json"
            config.write_text(json.dumps({"api_key": "private-key", "base_url": "https://old.example/v1", "model": "old-model"}), encoding="utf-8")
            assistant = OpenAIAssistant(config_path=config)
            result = assistant.save_config({"apiKey": "", "baseUrl": "https://models.example/v1", "model": "new-model"})
            saved = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(saved["api_key"], "private-key")
        self.assertEqual(saved["model"], "new-model")
        self.assertTrue(result["status"]["configured"])
        self.assertNotIn("private-key", json.dumps(result))

    @patch.object(OpenAIAssistant, "_open_model_catalog")
    def test_project_config_is_reloaded_and_health_status_redacts_key(
        self, open_model_catalog
    ):
        response = MagicMock()
        response.read.return_value = json.dumps({"data": [{"id": "draft-model"}]}).encode()
        response.__enter__.return_value = response
        open_model_catalog.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "AI Assistant Info.json"
            config.write_text(json.dumps({"api_key": "", "base_url": "", "model": ""}), encoding="utf-8")
            with patch.object(OpenAIAssistant, "_codex_is_authenticated", return_value=False):
                assistant = OpenAIAssistant(config_path=config)
                self.assertFalse(assistant.status()["configured"])
                config.write_text(json.dumps({"api_key": "private-key", "base_url": "https://models.example/v1", "model": "draft-model"}), encoding="utf-8")
                status = assistant.status()
            self.assertTrue(status["configured"])
            self.assertTrue(status["connected"])
            self.assertEqual(status["credentialSource"], "file")
            self.assertEqual(status["baseUrl"], "https://models.example/v1")
            self.assertNotIn("private-key", json.dumps(status))
            self.assertEqual(
                open_model_catalog.call_args.args[0].full_url,
                "https://models.example/v1/models",
            )
            self.assertIn(
                "Mozilla/5.0",
                open_model_catalog.call_args.args[0].headers["User-agent"],
            )

    @patch.object(OpenAIAssistant, "_request_json")
    def test_responses_api_uses_server_key_and_strict_schema(self, request_json):
        answer = {
            "status": "clarifying", "message": "需要确认", "questions": ["期望输出是什么？"],
            "draft": {"kind": "agent", "name": "", "description": "", "instructions": "", "model": "inherit", "actions": [], "skills": [], "targetAgentId": ""},
        }
        request_json.return_value = {"id": "resp_1", "output_text": json.dumps(answer, ensure_ascii=False)}
        with tempfile.TemporaryDirectory() as directory:
            assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
            result = assistant.chat({"kind": "agent", "messages": [{"role": "user", "content": "做一个分析 Agent"}]}, WorkflowStore(Path(directory)))
        self.assertEqual(result["responseId"], "resp_1")
        request = request_json.call_args.args[0]
        body = json.loads(request.data.decode())
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(request.headers["Authorization"], "Bearer server-secret")
        self.assertNotIn("server-secret", json.dumps(result))

    @patch.object(OpenAIAssistant, "_request_json")
    def test_model_cannot_change_selected_draft_kind_or_edit_target(self, request_json):
        answer = {
            "status": "draft", "message": "done", "questions": [],
            "draft": {
                "kind": "skill", "name": "Injected", "description": "", "instructions": "",
                "model": "inherit", "actions": [], "allowedActions": [], "actionJson": "",
                "skills": [], "targetAgentId": "agents-writer",
            },
        }
        request_json.return_value = {"id": "resp_boundary", "output_text": json.dumps(answer)}
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
        with tempfile.TemporaryDirectory() as directory:
            result = assistant.chat({
                "kind": "action", "targetAgentId": "", "messages": [{"role": "user", "content": "create"}],
                "draft": {"kind": "skill", "targetAgentId": "agents-writer"},
            }, WorkflowStore(Path(directory)))

        self.assertEqual(result["draft"]["kind"], "action")
        self.assertEqual(result["draft"]["targetAgentId"], "")
        body = json.loads(request_json.call_args.args[0].data.decode())
        self.assertIn('"requestedKind": "action"', body["instructions"])
        self.assertIn('"targetAgentId": ""', body["instructions"])

    @patch.object(OpenAIAssistant, "_request_json")
    def test_responses_api_maps_text_image_and_pdf_attachments(self, request_json):
        answer = {
            "status": "clarifying", "message": "\u5df2\u8bfb\u53d6\u9644\u4ef6", "questions": ["\u662f\u5426\u7ee7\u7eed\uff1f"],
            "draft": {"kind": "agent", "name": "", "description": "", "instructions": "", "model": "inherit", "actions": [], "allowedActions": [], "actionJson": "", "skills": [], "targetAgentId": ""},
        }
        request_json.return_value = {"id": "resp_files", "output_text": json.dumps(answer, ensure_ascii=False)}
        attachments = [
            {"name": "notes.md", "type": "text/markdown", "data": base64.b64encode(b"# Notes").decode()},
            {"name": "screen.png", "type": "image/png", "data": base64.b64encode(b"png-bytes").decode()},
            {"name": "brief.pdf", "type": "application/pdf", "data": base64.b64encode(b"pdf-bytes").decode()},
        ]
        with tempfile.TemporaryDirectory() as directory:
            assistant = OpenAIAssistant(api_key="server-secret", model="test-model")
            assistant.chat({"kind": "agent", "messages": [{"role": "user", "content": "\u8bf7\u53c2\u8003", "attachments": attachments}]}, WorkflowStore(Path(directory)))
        body = json.loads(request_json.call_args.args[0].data.decode())
        content = body["input"][0]["content"]
        self.assertIn("# Notes", next(item["text"] for item in content if item["type"] == "input_text" and "notes.md" in item["text"]))
        self.assertTrue(any(item["type"] == "input_image" for item in content))
        self.assertTrue(any(item["type"] == "input_file" and item["filename"] == "brief.pdf" for item in content))

    @patch("server.urllib.request.urlopen")
    def test_agent_draft_test_uses_connected_api_without_tools(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({"output_text": "测试输出"}, ensure_ascii=False).encode()
        response.__enter__.return_value = response
        urlopen.return_value = response
        assistant = OpenAIAssistant(api_key="server-secret", model="test-model", base_url="https://models.example/v1")
        with tempfile.TemporaryDirectory() as directory:
            result = assistant.test_agent_draft({"draft": {"kind": "agent", "instructions": "Respond clearly."}, "input": "hello"}, WorkflowStore(Path(directory)))
        self.assertTrue(result["passed"])
        self.assertEqual(result["output"], "测试输出")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode())
        self.assertEqual(request.full_url, "https://models.example/v1/responses")
        self.assertNotIn("tools", body)

    @patch("server.urllib.request.urlopen")
    def test_agent_draft_api_timeout_is_reported_to_the_background_queue(self, urlopen):
        assistant = OpenAIAssistant(
            api_key="server-secret",
            model="test-model",
            base_url="https://models.example/v1",
        )
        for timeout_error in (
            socket.timeout("timed out"),
            urllib.error.URLError(socket.timeout("timed out")),
        ):
            with self.subTest(error=timeout_error.__class__.__name__):
                urlopen.side_effect = timeout_error
                with tempfile.TemporaryDirectory() as directory, self.assertRaises(TimeoutError):
                    assistant.test_agent_draft(
                        {
                            "draft": {
                                "kind": "agent",
                                "instructions": "Respond clearly.",
                            }
                        },
                        WorkflowStore(Path(directory)),
                    )

    @patch.dict("os.environ", {}, clear=True)
    @patch("server.subprocess.run")
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_authenticated_codex_is_a_read_only_ephemeral_fallback(self, _which, run):
        answer = {
            "status": "clarifying", "message": "先确认范围", "questions": ["是否只检查测试？"],
            "draft": {"kind": "agent", "name": "", "description": "", "instructions": "", "model": "inherit", "actions": [], "skills": [], "targetAgentId": ""},
        }

        def invoke(command, **_kwargs):
            if command[1:3] == ["login", "status"]:
                return SimpleNamespace(returncode=0, stdout="Logged in", stderr="")
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        run.side_effect = invoke
        assistant = OpenAIAssistant()
        with tempfile.TemporaryDirectory() as directory:
            result = assistant.chat({"kind": "agent", "messages": [{"role": "user", "content": "创建检查 Agent"}]}, WorkflowStore(Path(directory)))
        self.assertEqual(result["status"], "clarifying")
        command = run.call_args_list[-1].args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("read-only", command)
        self.assertIn("--output-schema", command)

    @patch.dict("os.environ", {}, clear=True)
    @patch("server.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="Not logged in", stderr=""))
    @patch("server.shutil.which", return_value="/bin/echo")
    def test_unauthed_codex_is_not_reported_as_configured(self, _which, _run):
        status = OpenAIAssistant().status()
        self.assertTrue(status["codexInstalled"])
        self.assertFalse(status["codexAuthenticated"])
        self.assertFalse(status["configured"])


if __name__ == "__main__":
    unittest.main()
