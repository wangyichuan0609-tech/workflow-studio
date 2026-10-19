from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from onboarding import (
    REQUIREMENTS_AGENT_ID,
    REVIEW_AGENT_ID,
    TUTORIAL_MARKER,
    TUTORIAL_PROJECT_ID,
    TUTORIAL_WORKFLOW_ID,
    TutorialManager,
)
from server import WorkflowStore
from studio_service import StudioService
from studio_state import StudioState


class TutorialManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = StudioState(self.root / "app-data" / "state.sqlite3")
        self.service = StudioService(self.state)
        self.tutorial = TutorialManager(self.state, self.service, "0.6.0")

    def tearDown(self):
        self.state.close()
        self.temporary.cleanup()

    def test_fresh_database_invites_but_existing_database_does_not(self):
        self.assertEqual(self.state.get_setting("onboarding.invitation"), "pending")
        upgraded_path = self.root / "existing" / "state.sqlite3"
        upgraded_path.parent.mkdir(parents=True)
        upgraded_path.touch()
        upgraded = StudioState(upgraded_path)
        try:
            self.assertEqual(upgraded.get_setting("onboarding.invitation"), "dismissed")
        finally:
            upgraded.close()

    def test_tutorial_is_seeded_only_after_import_and_syncs_only_previewed_files(self):
        started = self.tutorial.start("zh")
        self.assertEqual(started["stepId"], "connection")
        project_root = self.tutorial.project_root
        self.assertEqual(
            [path.relative_to(project_root).as_posix() for path in project_root.rglob("*") if path.is_file()],
            [TUTORIAL_MARKER],
        )
        store = WorkflowStore(project_root)
        project = self.tutorial.project()
        self.service.import_project(TUTORIAL_PROJECT_ID, project, store)
        self.assertEqual(self.state.list_resources(TUTORIAL_PROJECT_ID), [])

        self.tutorial.seed_after_import(TUTORIAL_PROJECT_ID)
        self.assertEqual(
            {item["resource_id"] for item in self.state.list_resources(TUTORIAL_PROJECT_ID, "agent")},
            {REQUIREMENTS_AGENT_ID, REVIEW_AGENT_ID},
        )
        self.assertEqual(self.tutorial.status(connection_ready=True)["stepId"], "test-requirements")

        for agent_id in (REQUIREMENTS_AGENT_ID, REVIEW_AGENT_ID):
            agent = self.state.get_resource(TUTORIAL_PROJECT_ID, "agent", agent_id)
            self.state.record_resource_test(
                TUTORIAL_PROJECT_ID,
                "agent",
                agent_id,
                agent["studio_revision"],
                "passed",
                "smoke test passed",
                result={"passed": True},
            )
            self.service.publish(TUTORIAL_PROJECT_ID, "agent", agent_id, store)

        workflow = self.state.get_resource(
            TUTORIAL_PROJECT_ID, "workflow", TUTORIAL_WORKFLOW_ID
        )
        condition = self.tutorial.handoff_condition("zh")
        payload = {
            **workflow["payload"],
            "nodes": [
                {
                    "id": "requirements-node",
                    "type": "agent",
                    "agentId": REQUIREMENTS_AGENT_ID,
                    "label": "需求澄清员",
                    "role": "澄清需求",
                    "position": {"x": 80, "y": 120},
                },
                {
                    "id": "review-node",
                    "type": "agent",
                    "agentId": REVIEW_AGENT_ID,
                    "label": "方案审校员",
                    "role": "审校需求包",
                    "position": {"x": 360, "y": 120},
                },
            ],
            "edges": [
                {
                    "id": "requirements-to-review",
                    "source": "requirements-node",
                    "target": "review-node",
                    "condition": condition,
                }
            ],
        }
        saved = self.service.save_draft(
            TUTORIAL_PROJECT_ID,
            "workflow",
            TUTORIAL_WORKFLOW_ID,
            payload,
            workflow["studio_revision"],
        )
        self.assertEqual(saved["resourceStatus"], "draft")
        self.assertTrue(
            self.service.test_workflow(
                TUTORIAL_PROJECT_ID, TUTORIAL_WORKFLOW_ID, store
            )["valid"]
        )
        self.service.publish(
            TUTORIAL_PROJECT_ID, "workflow", TUTORIAL_WORKFLOW_ID, store
        )
        self.assertEqual(self.tutorial.status(connection_ready=True)["stepId"], "batch-sync")

        preview = self.service.preview(TUTORIAL_PROJECT_ID)
        self.assertTrue(preview["canSync"])
        expected_files = {
            path
            for item in preview["items"]
            for path in item["targetFiles"]
        }
        result = self.service.sync(TUTORIAL_PROJECT_ID, store)
        self.assertEqual(len(result["failed"]), 0)
        actual_files = {
            path.relative_to(project_root).as_posix()
            for path in project_root.rglob("*")
            if path.is_file() and path.name != TUTORIAL_MARKER
        }
        self.assertEqual(actual_files, expected_files)
        completed = self.tutorial.status(connection_ready=True)
        self.assertEqual(completed["status"], "completed")

        # A post-sync read-only refresh must neither stale an unchanged Agent
        # test nor revoke a tutorial completion that was already recorded.
        self.service.import_project(TUTORIAL_PROJECT_ID, project, store)
        for agent_id in (REQUIREMENTS_AGENT_ID, REVIEW_AGENT_ID):
            agent = self.state.get_resource(TUTORIAL_PROJECT_ID, "agent", agent_id)
            self.assertEqual(agent["test_status"], "passed")
        refreshed = self.tutorial.status(connection_ready=True)
        self.assertEqual(refreshed["status"], "completed")
        self.assertEqual(refreshed["completedAt"], completed["completedAt"])

        cleaned = self.tutorial.cleanup(preserve_completion=True)
        self.assertFalse(project_root.exists())
        self.assertEqual(cleaned["status"], "not_started")
        self.assertEqual(cleaned["invitation"], "completed")
        self.assertTrue(self.state.get_setting("onboarding.completed"))

    def test_cleanup_rejects_real_paths_symlinks_and_bad_markers(self):
        self.tutorial.start("zh")
        session = self.state.get_tutorial_session()
        real_project = self.root / "real-project"
        real_project.mkdir()
        (real_project / "keep.txt").write_text("keep", encoding="utf-8")
        self.state.save_tutorial_session({**session, "root_path": str(real_project)})
        with self.assertRaises(PermissionError):
            self.tutorial.cleanup()
        self.assertTrue((real_project / "keep.txt").exists())

        self.state.save_tutorial_session(session)
        marker = self.tutorial.project_root / TUTORIAL_MARKER
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.tutorial.cleanup()

        marker.unlink()
        self.tutorial.project_root.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / TUTORIAL_MARKER).write_text("{}", encoding="utf-8")
        self.tutorial.project_root.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(PermissionError):
            self.tutorial.cleanup()

        self.tutorial.project_root.unlink()
        shutil.rmtree(outside)
        self.tutorial.base_dir.rmdir()
        redirected_base = self.root / "redirected-base"
        redirected_root = redirected_base / "a2a-workflow"
        redirected_root.mkdir(parents=True)
        (redirected_root / TUTORIAL_MARKER).write_text(
            json.dumps(self.tutorial._marker_payload(session)), encoding="utf-8"
        )
        self.tutorial.base_dir.symlink_to(redirected_base, target_is_directory=True)
        with self.assertRaises(PermissionError):
            self.tutorial.cleanup()
        self.assertTrue(redirected_root.exists())


if __name__ == "__main__":
    unittest.main()
