from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock

from onboarding import TUTORIAL_MARKER, TUTORIAL_PROJECT_ID
from server import WorkflowServer, WorkflowStore


class OnboardingApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        project = self.root / "ordinary-project"
        project.mkdir()
        self.server = WorkflowServer(
            ("127.0.0.1", 0),
            WorkflowStore(project),
            Path(__file__).resolve().parents[1] / "web",
            state_path=self.root / "app-data" / "state.sqlite3",
        )
        self.server.ai.connection_status = MagicMock(
            return_value={"configured": True, "connected": True, "activeProvider": "codex"}
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)
        self.temporary.cleanup()

    def request(self, method: str, path: str, body=None, project_id: str = ""):
        headers = {"Content-Type": "application/json", "Origin": self.origin}
        if project_id:
            headers["X-Workflow-Studio-Project-Id"] = project_id
        data = None
        if body is not None or method in {"POST", "PUT"}:
            data = json.dumps(body or {}).encode()
        request = urllib.request.Request(
            self.origin + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())
        with response:
            return response.status, json.loads(response.read().decode())

    def test_start_lists_isolated_project_and_import_seeds_only_studio(self):
        status, initial = self.request("GET", "/api/onboarding")
        self.assertEqual(status, 200)
        self.assertEqual(initial["invitation"], "pending")

        status, started = self.request(
            "POST", "/api/onboarding/start", {"language": "en"}
        )
        self.assertEqual(status, 200, started)
        self.assertEqual(started["stepId"], "connection")
        tutorial_root = self.server.tutorial.project_root
        self.assertEqual(
            [path.name for path in tutorial_root.iterdir() if path.is_file()],
            [TUTORIAL_MARKER],
        )

        status, catalog = self.request("GET", "/api/codex/projects")
        self.assertEqual(status, 200, catalog)
        tutorial = next(
            project for project in catalog["projects"] if project["id"] == TUTORIAL_PROJECT_ID
        )
        self.assertTrue(tutorial["tutorial"])
        self.assertTrue(tutorial["managedByStudio"])
        self.assertNotIn("path", tutorial)

        status, imported = self.request(
            "POST",
            f"/api/codex/projects/{TUTORIAL_PROJECT_ID}/import",
            project_id=TUTORIAL_PROJECT_ID,
        )
        self.assertEqual(status, 200, imported)
        self.assertEqual(
            {agent["id"] for agent in imported["agents"]},
            {"requirements-clarifier", "plan-reviewer"},
        )
        self.assertEqual(
            [workflow["id"] for workflow in imported["workflows"]],
            ["a2a-requirement-review"],
        )
        self.assertEqual(imported["onboarding"]["stepId"], "test-requirements")
        self.assertEqual(
            [path.name for path in tutorial_root.iterdir() if path.is_file()],
            [TUTORIAL_MARKER],
        )

    def test_cleanup_requires_confirmation(self):
        self.request("POST", "/api/onboarding/start", {"language": "zh"})
        status, denied = self.request("POST", "/api/onboarding/delete", {})
        self.assertEqual(status, 400)
        self.assertIn("二次确认", denied["error"])
        self.assertTrue(self.server.tutorial.project_root.exists())


if __name__ == "__main__":
    unittest.main()
