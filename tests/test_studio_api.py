from __future__ import annotations

import json
import stat
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from server import WorkflowServer, WorkflowStore


PROJECT_ID = "studio-api-project"
AGENT_ID = "agents-writer"


def snapshot_tree(root: Path) -> Dict[str, Any]:
    """Capture project contents and directory shape to detect any Codex write."""

    snapshot: Dict[str, Any] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", path.readlink().as_posix())
        elif path.is_dir():
            snapshot[relative] = ("directory",)
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def action_payload(action_id: str) -> Dict[str, Any]:
    return {
        "id": action_id,
        "name": action_id.replace("-", " ").title(),
        "description": "A deterministic Studio-only test action.",
        "executor": "manual",
        "inputs": {},
        "steps": ["Inspect the supplied input."],
        "success": {"reviewed": True},
        "outputs": {"reviewed": "boolean"},
        "timeoutSeconds": 30,
        "errorHandling": {"strategy": "stop", "retries": 0},
        "credentialRefs": [],
    }


class StaticProjectRegistry:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def list_projects(self):
        return [{"id": PROJECT_ID, "title": "Studio API project"}]

    def select(self, project_id: str):
        if project_id != PROJECT_ID:
            raise ValueError("Project not found.")
        return {
            "id": PROJECT_ID,
            "title": "Studio API project",
            "path": str(self.root),
        }


class StudioApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary.name)
        self.project_root = self.temporary_root / "project"
        agent_root = self.project_root / "agents" / "writer"
        agent_root.mkdir(parents=True)
        (agent_root / "AGENT.md").write_text(
            "---\n"
            "name: Writer\n"
            "description: Writes concise answers.\n"
            "---\n\n"
            "# Writer\n\nUse only the supplied evidence.\n",
            encoding="utf-8",
        )
        self.state_path = self.temporary_root / "studio-data" / "state.sqlite3"
        web_root = Path(__file__).resolve().parents[1] / "web"
        self.server = WorkflowServer(
            ("127.0.0.1", 0),
            WorkflowStore(self.project_root),
            web_root,
            state_path=self.state_path,
        )
        self.server.registry = StaticProjectRegistry(self.project_root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.release_agent_test = threading.Event()

    def tearDown(self):
        self.release_agent_test.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)
        self.temporary.cleanup()

    def request_json(self, method: str, path: str, body=None, headers=None):
        request_headers = {
            "Content-Type": "application/json",
            "Origin": self.origin,
            "X-Workflow-Studio-Project-Id": PROJECT_ID,
        }
        request_headers.update(headers or {})
        data = None
        if body is not None or method in {"POST", "PUT"}:
            data = json.dumps(body or {}).encode("utf-8")
        request = urllib.request.Request(
            self.origin + path,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def import_project(self):
        status, payload = self.request_json(
            "POST", f"/api/codex/projects/{PROJECT_ID}/import"
        )
        self.assertEqual(status, 200, payload)
        return payload

    def save_action(self, action_id: str):
        status, payload = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/actions/{action_id}",
            action_payload(action_id),
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["resource"]["resourceStatus"], "draft")
        return payload

    def publish_action(self, action_id: str):
        status, payload = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/actions/{action_id}/publish",
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["resource"]["resourceStatus"], "ready")
        return payload

    def test_project_details_require_explicit_authorization_and_import_is_read_only(self):
        before = snapshot_tree(self.project_root)

        status, denied = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agents"
        )

        self.assertEqual(status, 409)
        self.assertTrue(denied["authorizationRequired"])
        self.assertFalse(self.server.state.is_authorized(PROJECT_ID))

        imported = self.import_project()

        self.assertTrue(self.server.state.is_authorized(PROJECT_ID))
        self.assertEqual(imported["project"]["id"], PROJECT_ID)
        self.assertEqual([agent["id"] for agent in imported["agents"]], [AGENT_ID])
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertEqual(self.server.state.path, self.state_path.absolute())
        self.assertEqual(stat.S_IMODE(self.state_path.stat().st_mode), 0o600)

    def test_global_usage_help_works_before_project_authorization(self):
        answer = {"message": "Agent 负责推理，Action 负责确定性执行。"}
        with patch.object(self.server.ai, "help_chat", return_value=answer) as help_chat:
            status, payload = self.request_json(
                "POST",
                "/api/ai/help",
                {"messages": [{"role": "user", "content": "Agent 和 Action 有什么区别？"}]},
                headers={"X-Workflow-Studio-Project-Id": ""},
            )

        self.assertEqual(status, 200, payload)
        self.assertEqual(payload, answer)
        self.assertIsNone(help_chat.call_args.args[1])

        with patch.object(self.server.ai, "help_chat", return_value=answer) as scoped_help:
            status, denied = self.request_json(
                "POST",
                f"/api/projects/{PROJECT_ID}/ai/help",
                {"messages": [{"role": "user", "content": "当前项目有多少 Agent？"}]},
            )
            self.assertEqual(status, 409, denied)

            self.import_project()
            status, payload = self.request_json(
                "POST",
                f"/api/projects/{PROJECT_ID}/ai/help",
                {"messages": [{"role": "user", "content": "当前项目有多少 Agent？"}]},
            )

        self.assertEqual(status, 200, payload)
        self.assertEqual(payload, answer)
        self.assertIsNotNone(scoped_help.call_args.args[1])
        self.assertEqual(scoped_help.call_args.kwargs["studio_counts"]["agents"], 1)

    def test_put_publish_ai_publish_and_workflow_test_do_not_write_codex(self):
        self.import_project()
        before = snapshot_tree(self.project_root)

        self.save_action("studio-only")
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.publish_action("studio-only")
        self.assertEqual(snapshot_tree(self.project_root), before)

        workflow = {
            "id": "draft-flow",
            "name": "Draft flow",
            "description": "A Studio-only workflow draft.",
            "nodes": [
                {
                    "id": "writer-node",
                    "type": "agent",
                    "agentId": AGENT_ID,
                    "label": "Writer",
                }
            ],
            "edges": [],
        }
        status, saved = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/workflows/draft-flow",
            workflow,
        )
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["resource"]["resourceStatus"], "draft")

        status, tested = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/workflows/draft-flow/test",
        )
        self.assertEqual(status, 200, tested)
        self.assertTrue(tested["valid"])
        self.assertEqual(tested["workflowId"], "draft-flow")
        self.assertEqual(tested["layers"], [["writer-node"]])

        status, published_workflow = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/workflows/draft-flow/publish",
        )
        self.assertEqual(status, 200, published_workflow)
        self.assertEqual(published_workflow["resource"]["resourceStatus"], "ready")

        ai_action = action_payload("ai-inspect")
        status, ai_published = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/ai/publish",
            {
                "kind": "action",
                "name": "AI Inspect",
                "description": ai_action["description"],
                "actionJson": json.dumps(ai_action),
            },
        )
        self.assertEqual(status, 200, ai_published)
        self.assertEqual(ai_published["id"], "ai-inspect")
        self.assertEqual(ai_published["status"], "ready")

        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse(
            (self.project_root / ".workflow-studio/actions/studio-only.json").exists()
        )
        self.assertFalse(
            (self.project_root / ".codex/workflows/draft-flow.json").exists()
        )

    def test_direct_sync_cannot_bypass_publish_for_a_draft_resource(self):
        self.import_project()
        before = snapshot_tree(self.project_root)
        self.save_action("draft-sync-gate")

        status, blocked = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/actions/draft-sync-gate/sync",
        )

        self.assertEqual(status, 200, blocked)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blocked"][0]["blockedReasons"][0]["code"], "not-ready")
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse(
            (self.project_root / ".workflow-studio/actions/draft-sync-gate.json").exists()
        )

    def test_action_draft_endpoints_reject_embedded_credentials_before_sqlite(self):
        self.import_project()
        unsafe = action_payload("unsafe")
        unsafe["inputs"] = {"apiKey": "must-not-persist"}

        status, rejected = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/actions/unsafe",
            unsafe,
        )
        self.assertEqual(status, 400, rejected)
        self.assertIn("credentialRefs", rejected["error"])
        self.assertIsNone(
            self.server.state.get_resource(PROJECT_ID, "action", "unsafe")
        )

        status, rejected_ai = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/ai/draft",
            {"kind": "action", "actionJson": json.dumps(unsafe)},
        )
        self.assertEqual(status, 400, rejected_ai)
        self.assertIn("credentialRefs", rejected_ai["error"])
        self.assertIsNone(
            self.server.state.get_latest_ai_draft(PROJECT_ID, "action")
        )

        status, incomplete_secret = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/ai/draft",
            {"kind": "action", "actionJson": '{"name":"Partial","apiKey":"secret'},
        )
        self.assertEqual(status, 400, incomplete_secret)
        self.assertIn("credentialRefs", incomplete_secret["error"])

        status, harmless_partial = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/ai/draft",
            {"kind": "action", "actionJson": '{"name":"Partial"'},
        )
        self.assertEqual(status, 200, harmless_partial)
        self.assertEqual(
            harmless_partial["draft"]["actionJson"], '{"name":"Partial"'
        )

    def test_sync_preview_is_read_only_and_single_resource_sync_writes_codex(self):
        self.import_project()
        before = snapshot_tree(self.project_root)
        self.save_action("explicit-sync")
        self.publish_action("explicit-sync")
        target = self.project_root / ".workflow-studio" / "actions" / "explicit-sync.json"

        status, preview = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/sync/preview",
            {"resources": [{"kind": "action", "id": "explicit-sync"}]},
        )

        self.assertEqual(status, 200, preview)
        self.assertTrue(preview["canSync"])
        self.assertEqual(preview["order"], [{"kind": "action", "id": "explicit-sync"}])
        self.assertEqual(preview["items"][0]["operation"], "add")
        self.assertIn(
            ".workflow-studio/actions/explicit-sync.json",
            preview["items"][0]["targetFiles"],
        )
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse(target.exists())

        status, synced = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/actions/explicit-sync/sync",
        )

        self.assertEqual(status, 200, synced)
        self.assertEqual(
            [(item["kind"], item["id"]) for item in synced["succeeded"]],
            [("action", "explicit-sync")],
        )
        self.assertEqual(synced["failed"], [])
        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["id"], "explicit-sync")

        status, detail = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/actions/explicit-sync"
        )
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["resource"]["resourceStatus"], "synced")

    def test_sync_preview_does_not_retest_a_failed_workflow_delete(self):
        self.import_project()
        workflow_id = "delete-retry"
        workflow = {
            "id": workflow_id,
            "name": "Delete retry",
            "description": "A deletion whose previous sync attempt failed.",
            "nodes": [],
            "edges": [],
        }
        status, saved = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/workflows/{workflow_id}",
            workflow,
        )
        self.assertEqual(status, 200, saved)
        status, published = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/workflows/{workflow_id}/publish",
        )
        self.assertEqual(status, 200, published)
        self.server.studio.stage_delete(PROJECT_ID, "workflow", workflow_id)
        self.server.state.mark_sync_failed(
            PROJECT_ID, "workflow", workflow_id, "injected delete failure"
        )
        self.server.studio.test_workflow = MagicMock(
            side_effect=AssertionError("delete retries must not run Workflow Dry-run")
        )

        status, preview = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/sync/preview",
            {"resources": [{"kind": "workflow", "id": workflow_id}]},
        )

        self.assertEqual(status, 200, preview)
        self.assertEqual(preview["items"][0]["operation"], "delete")
        self.server.studio.test_workflow.assert_not_called()

    def test_latest_ai_draft_can_be_restored_after_publishing_and_project_navigation(self):
        self.import_project()
        before = snapshot_tree(self.project_root)
        status, partial = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/ai/draft",
            {
                "kind": "agent",
                "name": "",
                "description": "Partial Studio-only idea.",
                "instructions": "",
                "messages": [{"role": "user", "content": "must not persist"}],
                "attachments": [{"name": "secret.txt", "data": "must not persist"}],
            },
        )
        self.assertEqual(status, 200, partial)
        self.assertEqual(partial["draft"]["description"], "Partial Studio-only idea.")
        self.assertNotIn("messages", partial["draft"])
        self.assertNotIn("attachments", partial["draft"])
        self.assertIsNone(partial["resource"])
        self.assertEqual(snapshot_tree(self.project_root), before)

        draft = {
            "kind": "agent",
            "name": "Draft Cache",
            "description": "Persists outside the Codex project.",
            "instructions": "Return the Studio draft.",
            "model": "inherit",
            "allowedActions": [],
            "skills": [],
        }
        self.server.ai.chat = MagicMock(
            return_value={
                "status": "draft",
                "message": "Draft ready.",
                "questions": [],
                "draft": draft,
            }
        )
        status, generated = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/ai/chat",
            {"kind": "agent", "messages": [{"role": "user", "content": "draft"}]},
        )
        self.assertEqual(status, 200, generated)
        self.assertTrue(generated["draftSaved"])
        self.assertEqual(generated["studioResource"]["name"], "Draft Cache")
        self.assertEqual(generated["studioResource"]["resourceStatus"], "draft")
        self.assertNotIn("resource", generated["studioResource"])
        self.assertEqual(snapshot_tree(self.project_root), before)

        status, published = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/ai/publish",
            draft,
        )
        self.assertEqual(status, 200, published)
        self.assertEqual(published["resource"]["resourceStatus"], "ready")
        self.assertEqual(snapshot_tree(self.project_root), before)

        status, restored = self.request_json(
            "GET",
            f"/api/projects/{PROJECT_ID}/ai/draft?kind=agent",
        )
        self.assertEqual(status, 200, restored)
        self.assertEqual(restored["draft"]["name"], "Draft Cache")
        self.assertEqual(restored["draft"]["instructions"], "Return the Studio draft.")
        self.assertNotIn("resourceStatus", restored["draft"])
        self.assertEqual(restored["resource"]["resourceStatus"], "ready")
        self.assertEqual(restored["studioResource"]["id"], published["id"])
        self.assertEqual(snapshot_tree(self.project_root), before)

        time.sleep(0.002)
        newer_raw_draft = {
            **draft,
            "name": "Recovered unsaved AI edit",
            "targetAgentId": published["id"],
        }
        status, latest_only = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/ai/draft",
            newer_raw_draft,
        )
        self.assertEqual(status, 200, latest_only)
        self.assertEqual(latest_only["draft"]["name"], "Recovered unsaved AI edit")
        self.assertEqual(latest_only["resource"]["name"], "Draft Cache")
        self.assertEqual(snapshot_tree(self.project_root), before)

    def test_ai_publish_rejects_a_stale_studio_revision(self):
        self.import_project()
        draft = {
            "kind": "agent",
            "name": "Revision Locked",
            "description": "Initial AI description.",
            "instructions": "Return the checked revision.",
            "model": "inherit",
            "allowedActions": [],
            "skills": [],
        }
        self.server.ai.chat = MagicMock(
            return_value={
                "status": "draft",
                "message": "Draft ready.",
                "questions": [],
                "draft": draft,
            }
        )
        status, generated = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/ai/chat",
            {"kind": "agent", "messages": [{"role": "user", "content": "draft"}]},
        )
        self.assertEqual(status, 200, generated)
        resource = generated["studioResource"]
        stale_revision = resource["studioRevision"]
        changed = {**resource, "description": "Changed in another editor."}
        status, saved = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/agents/{resource['id']}",
            changed,
            headers={"If-Match": str(stale_revision)},
        )
        self.assertEqual(status, 200, saved)

        status, rejected = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/ai/publish",
            {**draft, "targetAgentId": resource["id"]},
            headers={"If-Match": str(stale_revision)},
        )

        self.assertEqual(status, 409, rejected)
        self.assertTrue(rejected["revisionConflict"])
        status, detail = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agents/{resource['id']}"
        )
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["resource"]["description"], "Changed in another editor.")

    def test_agent_test_returns_202_and_job_get_recovers_mocked_result_without_writes(self):
        self.import_project()
        before = snapshot_tree(self.project_root)
        agent = {
            "id": AGENT_ID,
            "name": "Writer",
            "description": "Writes the current Studio draft.",
            "path": "agents/writer",
            "entrypoint": "agents/writer/AGENT.md",
            "format": "AGENT.md",
            "model": "inherit",
            "tools": [],
            "instructions": "Return exactly the checked Studio draft.",
            "allowedActions": [],
            "legacyActions": [],
            "skills": [],
            "actionCount": 0,
            "skillCount": 0,
        }
        status, saved = self.request_json(
            "PUT",
            f"/api/projects/{PROJECT_ID}/agents/{AGENT_ID}",
            agent,
        )
        self.assertEqual(status, 200, saved)
        revision = saved["studioRevision"]

        executor_started = threading.Event()

        def mocked_test(payload, _store):
            executor_started.set()
            self.release_agent_test.wait(2)
            return {"passed": True, "summary": "Mock Agent test passed."}

        self.server.ai.test_agent_draft = MagicMock(side_effect=mocked_test)

        status, started = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/agents/{AGENT_ID}/test",
            {"input": "verify the draft"},
        )

        self.assertEqual(status, 202, started)
        self.assertTrue(started["jobId"])
        self.assertEqual(started["testedRevision"], revision)
        self.assertIn(started["status"], {"queued", "running"})
        self.assertTrue(executor_started.wait(1))
        self.assertEqual(snapshot_tree(self.project_root), before)

        self.release_agent_test.set()
        deadline = time.monotonic() + 3
        completed = None
        while time.monotonic() < deadline:
            status, payload = self.request_json(
                "GET",
                f"/api/projects/{PROJECT_ID}/agent-tests/{started['jobId']}",
            )
            self.assertEqual(status, 200, payload)
            if payload["job"]["status"] in {
                "passed",
                "failed",
                "timed_out",
                "cancelled",
                "interrupted",
            }:
                completed = payload["job"]
                break
            time.sleep(0.01)

        self.assertIsNotNone(completed, "Agent test job did not reach a terminal state.")
        self.assertEqual(completed["status"], "passed")
        self.assertTrue(completed["passed"])
        self.assertEqual(completed["summary"], "Mock Agent test passed.")

        self.server.ai.test_agent_draft.assert_called_once()
        executor_payload = self.server.ai.test_agent_draft.call_args.args[0]
        self.assertEqual(
            executor_payload["draft"]["instructions"],
            "Return exactly the checked Studio draft.",
        )
        self.assertEqual(executor_payload["input"], "verify the draft")
        self.assertEqual(snapshot_tree(self.project_root), before)

        status, detail = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agents/{AGENT_ID}"
        )
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["resource"]["testStatus"], "passed")
        self.assertEqual(detail["resource"]["testRevision"], revision)

        status, unseen = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agent-tests?unseen=1"
        )
        self.assertEqual(status, 200, unseen)
        self.assertEqual([job["jobId"] for job in unseen["jobs"]], [started["jobId"]])
        status, repeated = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agent-tests?unseen=1"
        )
        self.assertEqual(status, 200, repeated)
        self.assertEqual([job["jobId"] for job in repeated["jobs"]], [started["jobId"]])
        status, acknowledged = self.request_json(
            "POST",
            f"/api/projects/{PROJECT_ID}/agent-tests/{started['jobId']}/seen",
        )
        self.assertEqual(status, 200, acknowledged)
        self.assertTrue(acknowledged["job"]["seen"])
        status, empty = self.request_json(
            "GET", f"/api/projects/{PROJECT_ID}/agent-tests?unseen=1"
        )
        self.assertEqual(status, 200, empty)
        self.assertEqual(empty["jobs"], [])


if __name__ == "__main__":
    unittest.main()
