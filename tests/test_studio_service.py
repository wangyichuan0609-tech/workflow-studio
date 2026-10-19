from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

from resource_paths import (
    MAX_GENERATED_SKILL_NAME_LENGTH,
    generated_skill_invocation,
    generated_skill_name,
    generated_skill_paths,
)
from server import WorkflowStore
from studio_service import StudioService
from studio_state import StudioState


PROJECT_ID = "project-demo"


def snapshot_tree(root: Path) -> Dict[str, Any]:
    """Capture both contents and directory shape below a project root."""

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


def action_payload(action_id: str, name: str | None = None) -> Dict[str, Any]:
    return {
        "id": action_id,
        "name": name or action_id.replace("-", " ").title(),
        "description": "A deterministic project action.",
        "executor": "script",
        "inputs": {},
        "steps": ["run the action"],
        "success": {"exitCode": 0},
        "outputs": {},
        "timeoutSeconds": 30,
        "errorHandling": {"strategy": "stop", "retries": 0},
        "credentialRefs": [],
    }


class RecordingWorkflowStore(WorkflowStore):
    def __init__(self, root: Path):
        super().__init__(root)
        self.write_calls = []

    def save_action(self, action_id, payload, allow_overwrite=True):
        self.write_calls.append(("action", action_id))
        return super().save_action(action_id, payload, allow_overwrite=allow_overwrite)

    def save_agent(self, agent_id, payload):
        self.write_calls.append(("agent", agent_id))
        return super().save_agent(agent_id, payload)


class SelectiveActionFailureStore(RecordingWorkflowStore):
    def __init__(self, root: Path, failing_action_id: str):
        super().__init__(root)
        self.failing_action_id = failing_action_id

    def save_action(self, action_id, payload, allow_overwrite=True):
        if action_id == self.failing_action_id:
            self.write_calls.append(("action", action_id))
            raise OSError("injected action write failure")
        return super().save_action(action_id, payload, allow_overwrite=allow_overwrite)


class FailAfterAgentWriteStore(WorkflowStore):
    def save_agent(self, agent_id, payload):
        super().save_agent(agent_id, payload)
        raise OSError("injected failure after all agent files were written")


class FailAfterWorkflowWriteStore(WorkflowStore):
    def save_workflow(self, workflow_id, payload):
        super().save_workflow(workflow_id, payload)
        raise OSError("injected failure after all workflow files were written")


class StudioServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary.name)
        self.project_root = self.temporary_root / "project"
        agent_root = self.project_root / "agents" / "writer"
        agent_root.mkdir(parents=True)
        (agent_root / "AGENT.md").write_text(
            "---\n"
            "name: Writer\n"
            "description: Writes a concise answer.\n"
            "---\n\n"
            "# Writer\n\nUse the supplied evidence.\n",
            encoding="utf-8",
        )
        self.store = RecordingWorkflowStore(self.project_root)
        self.state = StudioState(self.temporary_root / "state.sqlite3")
        self.service = StudioService(self.state)

    def tearDown(self):
        self.state.close()
        self.temporary.cleanup()

    def import_project(self, store=None):
        return self.service.import_project(
            PROJECT_ID,
            {"id": PROJECT_ID, "title": "Demo", "path": str(self.project_root)},
            store or self.store,
        )

    def save_and_publish_action(self, action_id: str, store=None):
        selected_store = store or self.store
        self.service.save_draft(
            PROJECT_ID, "action", action_id, action_payload(action_id)
        )
        return self.service.publish(
            PROJECT_ID, "action", action_id, selected_store
        )

    def publish_changed_agent(self, allowed_actions=None, store=None):
        selected_store = store or self.store
        resource = self.state.get_resource(PROJECT_ID, "agent", "agents-writer")
        payload = copy.deepcopy(resource["payload"])
        payload["description"] = "Writes the final concise answer."
        payload["instructions"] = "Use only confirmed evidence."
        payload["allowedActions"] = list(allowed_actions or [])
        payload["skills"] = []
        draft = self.service.save_draft(
            PROJECT_ID, "agent", "agents-writer", payload
        )
        published = self.service.publish(
            PROJECT_ID, "agent", "agents-writer", selected_store
        )
        self.state.record_resource_test(
            PROJECT_ID,
            "agent",
            "agents-writer",
            published["studioRevision"],
            "passed",
            "Agent load test passed.",
        )
        return draft, published

    def publish_new_agent(self, agent_id="custom-id", name="Bar", store=None):
        selected_store = store or self.store
        self.service.save_draft(
            PROJECT_ID,
            "agent",
            agent_id,
            {
                "id": agent_id,
                "name": name,
                "description": "A new Studio Agent with an explicit identity.",
                "instructions": "Return the requested result.",
                "model": "inherit",
                "allowedActions": [],
                "legacyActions": [],
                "skills": [],
                "path": "agents/by-name",
                "entrypoint": "agents/by-name/AGENT.md",
                "format": "AGENT.md",
            },
        )
        published = self.service.publish(
            PROJECT_ID, "agent", agent_id, selected_store
        )
        self.state.record_resource_test(
            PROJECT_ID,
            "agent",
            agent_id,
            published["studioRevision"],
            "passed",
            "Agent draft passed.",
        )
        return published

    def test_import_is_read_only_and_records_synced_baseline(self):
        action_path = self.project_root / ".workflow-studio/actions/existing.json"
        action_path.parent.mkdir(parents=True)
        action_path.write_text(
            json.dumps(action_payload("existing"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        before = snapshot_tree(self.project_root)

        result = self.import_project()

        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertEqual(result["counts"]["created"], 2)
        agent = self.state.get_resource(PROJECT_ID, "agent", "agents-writer")
        action = self.state.get_resource(PROJECT_ID, "action", "existing")
        self.assertEqual(agent["status"], "synced")
        self.assertIsNotNone(agent["base_hash"])
        self.assertEqual(action["synced_manifest"], [
            ".workflow-studio/actions/existing.json"
        ])
        self.assertEqual(self.store.write_calls, [])

    def test_save_and_publish_only_update_studio_state(self):
        self.import_project()
        before = snapshot_tree(self.project_root)

        draft = self.service.save_draft(
            PROJECT_ID, "action", "studio-only", action_payload("studio-only")
        )
        published = self.service.publish(
            PROJECT_ID, "action", "studio-only", self.store
        )

        self.assertEqual(draft["resourceStatus"], "draft")
        self.assertEqual(published["resourceStatus"], "ready")
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse(
            (self.project_root / ".workflow-studio/actions/studio-only.json").exists()
        )
        self.assertEqual(self.store.write_calls, [])

    def test_single_resource_sync_is_the_first_project_write(self):
        self.import_project()
        published = self.save_and_publish_action("explicit-sync")
        target = self.project_root / ".workflow-studio/actions/explicit-sync.json"
        self.assertFalse(target.exists())

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "action", "id": "explicit-sync"}],
        )

        self.assertEqual([item["id"] for item in result["succeeded"]], ["explicit-sync"])
        self.assertEqual(result["failed"], [])
        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["id"], "explicit-sync")
        synced = self.state.get_resource(PROJECT_ID, "action", "explicit-sync")
        self.assertEqual(synced["status"], "synced")
        self.assertGreaterEqual(synced["studio_revision"], published["studioRevision"])

    def test_explicit_empty_selection_never_syncs_all_ready_resources(self):
        self.import_project()
        self.save_and_publish_action("stay-ready")
        before = snapshot_tree(self.project_root)

        preview = self.service.preview(PROJECT_ID, [])
        result = self.service.sync(PROJECT_ID, self.store, selected=[])

        self.assertEqual(preview["items"], [])
        self.assertEqual(result["results"], [])
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "action", "stay-ready")["status"],
            "ready",
        )

    def test_dependencies_block_single_sync_and_batch_runs_in_dependency_order(self):
        self.import_project()
        self.save_and_publish_action("summarize")
        self.publish_changed_agent(["summarize"])
        self.store.write_calls.clear()

        blocked = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "agent", "id": "agents-writer"}],
        )

        self.assertEqual(blocked["blocked"][0]["id"], "agents-writer")
        self.assertEqual(
            blocked["blocked"][0]["blockedReasons"][0]["code"],
            "unsynced-dependency",
        )
        self.assertEqual(self.store.write_calls, [])

        batch = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[
                {"kind": "agent", "id": "agents-writer"},
                {"kind": "action", "id": "summarize"},
            ],
        )

        self.assertEqual([item["id"] for item in batch["succeeded"]], [
            "summarize",
            "agents-writer",
        ])
        self.assertEqual(self.store.write_calls, [
            ("action", "summarize"),
            ("agent", "agents-writer"),
        ])

    def test_batch_continues_after_one_resource_fails(self):
        self.import_project()
        self.save_and_publish_action("bad")
        self.save_and_publish_action("good")
        failing_store = SelectiveActionFailureStore(self.project_root, "bad")

        result = self.service.sync(
            PROJECT_ID,
            failing_store,
            selected=[
                {"kind": "action", "id": "bad"},
                {"kind": "action", "id": "good"},
            ],
        )

        self.assertEqual([item["id"] for item in result["failed"]], ["bad"])
        self.assertEqual([item["id"] for item in result["succeeded"]], ["good"])
        self.assertFalse((self.project_root / ".workflow-studio/actions/bad.json").exists())
        self.assertTrue((self.project_root / ".workflow-studio/actions/good.json").exists())
        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "action", "bad")["status"],
            "sync_failed",
        )
        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "action", "good")["status"],
            "synced",
        )

    def test_sync_rejects_a_resource_changed_after_preview(self):
        self.import_project()
        self.save_and_publish_action("previewed")
        preview = self.service.preview(
            PROJECT_ID, [{"kind": "action", "id": "previewed"}]
        )
        before = snapshot_tree(self.project_root)
        current = self.state.get_resource(PROJECT_ID, "action", "previewed")
        changed = {**current["payload"], "description": "Changed after preview."}
        self.service.save_draft(PROJECT_ID, "action", "previewed", changed)
        self.service.publish(PROJECT_ID, "action", "previewed", self.store)

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=preview["items"],
        )

        self.assertEqual(result["succeeded"], [])
        self.assertEqual(
            result["blocked"][0]["blockedReasons"][0]["code"],
            "revision-changed",
        )
        self.assertEqual(snapshot_tree(self.project_root), before)

    def test_sync_reimports_codex_and_never_overwrites_an_external_conflict(self):
        action_path = self.project_root / ".workflow-studio/actions/external.json"
        action_path.parent.mkdir(parents=True)
        original = action_payload("external")
        action_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
        self.import_project()
        local = {**original, "description": "Changed in Studio."}
        self.service.save_draft(PROJECT_ID, "action", "external", local)
        self.service.publish(PROJECT_ID, "action", "external", self.store)
        preview = self.service.preview(
            PROJECT_ID, [{"kind": "action", "id": "external"}]
        )

        external = {**original, "description": "Changed directly in Codex."}
        action_path.write_text(json.dumps(external, indent=2) + "\n", encoding="utf-8")
        result = self.service.sync(
            PROJECT_ID, self.store, selected=preview["items"]
        )

        self.assertEqual(result["succeeded"], [])
        self.assertEqual(result["blocked"][0]["resourceStatus"], "conflict")
        self.assertEqual(json.loads(action_path.read_text(encoding="utf-8")), external)
        conflicted = self.state.get_resource(PROJECT_ID, "action", "external")
        self.assertEqual(conflicted["status"], "conflict")
        self.assertTrue(conflicted["conflicts"])

    def _synced_writer_with_external_description(self, studio_change):
        # A previous sync leaves Studio's agent JSON next to AGENT.md.
        self.store.save_agent(
            "agents-writer",
            {"name": "Writer", "description": "Writes a concise answer.", "instructions": ""},
        )
        self.import_project()
        resource = self.state.get_resource(PROJECT_ID, "agent", "agents-writer")
        self.service.save_draft(
            PROJECT_ID, "agent", "agents-writer",
            {**copy.deepcopy(resource["payload"]), **studio_change},
            expected_revision=resource["studio_revision"],
        )
        entrypoint = self.project_root / "agents/writer/AGENT.md"
        entrypoint.write_text(
            entrypoint.read_text(encoding="utf-8").replace(
                "Writes a concise answer.", "Edited directly in Codex."
            ),
            encoding="utf-8",
        )
        self.import_project()
        return self.state.get_resource(PROJECT_ID, "agent", "agents-writer")

    def test_external_agent_md_edit_conflicts_with_same_studio_field(self):
        resource = self._synced_writer_with_external_description(
            {"description": "Changed in Studio."}
        )
        self.assertEqual(resource["status"], "conflict")
        self.assertTrue(resource["conflicts"])

    def test_external_agent_md_edit_merges_with_other_studio_fields(self):
        resource = self._synced_writer_with_external_description(
            {"instructions": "Use only confirmed evidence."}
        )
        self.assertNotEqual(resource["status"], "conflict")
        self.assertEqual(resource["payload"]["description"], "Edited directly in Codex.")
        self.assertEqual(resource["payload"]["instructions"], "Use only confirmed evidence.")

    def test_new_agent_sync_honours_studio_id_in_every_target(self):
        self.import_project()
        self.publish_new_agent("custom-id", "Bar")

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "agent", "id": "custom-id"}],
        )

        self.assertEqual([item["id"] for item in result["succeeded"]], ["custom-id"])
        self.assertTrue((self.project_root / "custom-id/AGENT.md").exists())
        self.assertTrue(
            (self.project_root / ".workflow-studio/agents/custom-id.json").exists()
        )
        self.assertTrue(
            (self.project_root / ".agents/skills/agent-custom-id/SKILL.md").exists()
        )
        self.assertFalse(
            (self.project_root / ".workflow-studio/agents/agents-bar.json").exists()
        )
        self.import_project()
        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "agent", "custom-id")["status"],
            "synced",
        )
        self.assertIsNone(
            self.state.get_resource(PROJECT_ID, "agent", "agents-bar")
        )

    def test_generated_skill_names_preserve_short_ids_and_hash_long_collisions(self):
        self.assertEqual(generated_skill_name("agent", "custom-id"), "agent-custom-id")
        self.assertEqual(
            generated_skill_name("workflow", "delivery-flow"),
            "workflow-delivery-flow",
        )
        shared_prefix = "x" * 63
        first = generated_skill_name("agent", shared_prefix + "a")
        second = generated_skill_name("agent", shared_prefix + "b")
        self.assertEqual(len(first), MAX_GENERATED_SKILL_NAME_LENGTH)
        self.assertEqual(len(second), MAX_GENERATED_SKILL_NAME_LENGTH)
        self.assertNotEqual(first, second)
        self.assertEqual(first, generated_skill_name("agent", shared_prefix + "a"))

    def test_long_agent_id_sync_uses_one_hashed_path_and_reimports_as_synced(self):
        self.import_project()
        agent_id = "a" * 64
        published = self.publish_new_agent(agent_id, "Long Agent")
        skill_file, metadata_file = generated_skill_paths("agent", agent_id)
        self.assertEqual(
            published["codexInvocation"],
            generated_skill_invocation("agent", agent_id),
        )

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "agent", "id": agent_id}],
        )

        self.assertEqual([item["id"] for item in result["succeeded"]], [agent_id])
        self.assertEqual(
            result["succeeded"][0]["resource"]["codexInvocation"],
            generated_skill_invocation("agent", agent_id),
        )
        self.assertIn(skill_file, result["succeeded"][0]["syncedFiles"])
        self.assertIn(metadata_file, result["succeeded"][0]["syncedFiles"])
        self.assertTrue((self.project_root / skill_file).exists())
        self.assertTrue((self.project_root / metadata_file).exists())
        self.assertIn(
            f"`{generated_skill_invocation('agent', agent_id)}`",
            (self.project_root / "AGENTS.md").read_text(encoding="utf-8"),
        )

        self.import_project()
        imported = self.state.get_resource(PROJECT_ID, "agent", agent_id)
        self.assertEqual(imported["status"], "synced")
        self.assertIn(skill_file, imported["synced_manifest"])
        self.assertIn("AGENTS.md", imported["synced_manifest"])

    def test_long_agent_id_failure_rolls_back_hashed_skill_path(self):
        self.import_project()
        agent_id = "b" * 64
        self.publish_new_agent(agent_id, "Long Failing Agent")
        skill_file, _ = generated_skill_paths("agent", agent_id)
        before = snapshot_tree(self.project_root)

        result = self.service.sync(
            PROJECT_ID,
            FailAfterAgentWriteStore(self.project_root),
            selected=[{"kind": "agent", "id": agent_id}],
        )

        self.assertEqual([item["id"] for item in result["failed"]], [agent_id])
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse((self.project_root / skill_file).exists())

    def test_long_workflow_id_sync_reimports_and_failure_rolls_back(self):
        self.import_project()
        workflow_id = "w" * 64
        payload = {
            "id": workflow_id,
            "name": "Long Workflow",
            "description": "Uses a stable generated Skill path.",
            "nodes": [
                {
                    "id": "writer",
                    "type": "agent",
                    "agentId": "agents-writer",
                    "label": "Writer",
                }
            ],
            "edges": [],
        }
        self.service.save_draft(PROJECT_ID, "workflow", workflow_id, payload)
        published = self.service.publish(
            PROJECT_ID, "workflow", workflow_id, self.store
        )
        skill_file, metadata_file = generated_skill_paths("workflow", workflow_id)
        self.assertEqual(
            published["codexInvocation"],
            generated_skill_invocation("workflow", workflow_id),
        )

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "workflow", "id": workflow_id}],
        )

        self.assertEqual([item["id"] for item in result["succeeded"]], [workflow_id])
        self.assertEqual(
            result["succeeded"][0]["resource"]["codexInvocation"],
            generated_skill_invocation("workflow", workflow_id),
        )
        self.assertTrue((self.project_root / skill_file).exists())
        self.assertTrue((self.project_root / metadata_file).exists())
        self.import_project()
        imported = self.state.get_resource(PROJECT_ID, "workflow", workflow_id)
        self.assertEqual(imported["status"], "synced")
        self.assertIn(skill_file, imported["synced_manifest"])
        self.assertIn("AGENTS.md", imported["synced_manifest"])

        failing_id = ("w" * 63) + "x"
        failing_payload = {**payload, "id": failing_id, "name": "Failing Workflow"}
        self.service.save_draft(PROJECT_ID, "workflow", failing_id, failing_payload)
        self.service.publish(PROJECT_ID, "workflow", failing_id, self.store)
        failing_skill_file, _ = generated_skill_paths("workflow", failing_id)
        before = snapshot_tree(self.project_root)

        failed = self.service.sync(
            PROJECT_ID,
            FailAfterWorkflowWriteStore(self.project_root),
            selected=[{"kind": "workflow", "id": failing_id}],
        )

        self.assertEqual([item["id"] for item in failed["failed"]], [failing_id])
        self.assertEqual(snapshot_tree(self.project_root), before)
        self.assertFalse((self.project_root / failing_skill_file).exists())

    def test_manual_agents_file_is_not_owned_by_agent_or_workflow_manifests(self):
        workflow_id = "manual-flow"
        workflow_path = self.project_root / ".codex/workflows" / f"{workflow_id}.json"
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "id": workflow_id,
                    "name": "Manual Flow",
                    "description": "Imported without generated index entries.",
                    "nodes": [],
                    "edges": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        agents_file = self.project_root / "AGENTS.md"
        agents_file.write_text("# Hand-written project instructions\n", encoding="utf-8")

        self.import_project()

        agent = self.state.get_resource(PROJECT_ID, "agent", "agents-writer")
        workflow = self.state.get_resource(PROJECT_ID, "workflow", workflow_id)
        self.assertNotIn("AGENTS.md", agent["synced_manifest"])
        self.assertNotIn("AGENTS.md", workflow["synced_manifest"])

        agents_file.unlink()
        self.import_project()

        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "agent", "agents-writer")["status"],
            "synced",
        )
        self.assertEqual(
            self.state.get_resource(PROJECT_ID, "workflow", workflow_id)["status"],
            "synced",
        )

    def test_new_agent_failure_rolls_back_all_identity_targets(self):
        self.import_project()
        self.publish_new_agent("custom-id", "Bar")
        before = snapshot_tree(self.project_root)

        result = self.service.sync(
            PROJECT_ID,
            FailAfterAgentWriteStore(self.project_root),
            selected=[{"kind": "agent", "id": "custom-id"}],
        )

        self.assertEqual([item["id"] for item in result["failed"]], ["custom-id"])
        self.assertEqual(snapshot_tree(self.project_root), before)

    def test_new_skill_sync_uses_its_studio_path_not_its_display_name(self):
        self.import_project()
        skill_id = "agents-skills-custom"
        self.service.save_draft(
            PROJECT_ID,
            "skill",
            skill_id,
            {
                "id": skill_id,
                "name": "Different Name",
                "description": "A project skill with a stable path.",
                "instructions": "Follow this reusable method.",
                "path": ".agents/skills/custom/SKILL.md",
            },
        )
        self.service.publish(PROJECT_ID, "skill", skill_id, self.store)

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "skill", "id": skill_id}],
        )

        self.assertEqual([item["id"] for item in result["succeeded"]], [skill_id])
        self.assertTrue(
            (self.project_root / ".agents/skills/custom/SKILL.md").exists()
        )
        self.assertFalse(
            (self.project_root / ".agents/skills/different-name/SKILL.md").exists()
        )

    def test_existing_skill_sync_tracks_and_deletes_its_metadata_sidecar(self):
        skill_root = self.project_root / ".agents" / "skills" / "existing"
        metadata_path = skill_root / "agents" / "openai.yaml"
        metadata_path.parent.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: existing\ndescription: Original description.\n---\n\nOriginal instructions.\n",
            encoding="utf-8",
        )
        metadata_path.write_text(
            'interface:\n  display_name: "Old metadata"\n', encoding="utf-8"
        )
        imported = self.import_project()
        skill = next(item for item in imported["skills"] if item["path"].endswith("existing/SKILL.md"))
        skill_id = skill["id"]
        payload = {
            "id": skill_id,
            "name": "existing",
            "description": "Updated description.",
            "instructions": "Updated instructions.",
            "path": skill["path"],
            "generated": skill["generated"],
        }
        self.service.save_draft(PROJECT_ID, "skill", skill_id, payload)
        self.service.publish(PROJECT_ID, "skill", skill_id, self.store)

        synced = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "skill", "id": skill_id}],
        )

        self.assertEqual(
            synced["succeeded"][0]["syncedFiles"],
            [
                ".agents/skills/existing/SKILL.md",
                ".agents/skills/existing/agents/openai.yaml",
            ],
        )
        self.assertIn(
            'short_description: "Updated description."',
            metadata_path.read_text(encoding="utf-8"),
        )
        tracked = self.state.get_resource(PROJECT_ID, "skill", skill_id)
        self.assertEqual(
            tracked["synced_manifest"], synced["succeeded"][0]["syncedFiles"]
        )

        self.service.stage_delete(PROJECT_ID, "skill", skill_id)
        deleted = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "skill", "id": skill_id}],
            confirm_delete=True,
        )
        self.assertEqual(
            deleted["succeeded"][0]["syncedFiles"],
            [
                ".agents/skills/existing/SKILL.md",
                ".agents/skills/existing/agents/openai.yaml",
            ],
        )
        self.assertFalse(skill_root.exists())

    def test_pending_delete_requires_confirmation_and_only_removes_recorded_target(self):
        deleted_path = self.project_root / ".workflow-studio/actions/delete-me.json"
        kept_path = self.project_root / ".workflow-studio/actions/keep-me.json"
        deleted_path.parent.mkdir(parents=True)
        deleted_path.write_text(
            json.dumps(action_payload("delete-me"), indent=2) + "\n", encoding="utf-8"
        )
        kept_path.write_text(
            json.dumps(action_payload("keep-me"), indent=2) + "\n", encoding="utf-8"
        )
        self.import_project()
        staged = self.service.stage_delete(PROJECT_ID, "action", "delete-me")
        self.assertEqual(staged["resourceStatus"], "pending_delete")

        unconfirmed = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "action", "id": "delete-me"}],
        )

        self.assertEqual(
            unconfirmed["blocked"][0]["blockedReasons"][0]["code"],
            "delete-confirmation-required",
        )
        self.assertTrue(deleted_path.exists())
        self.assertTrue(kept_path.exists())

        confirmed = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "action", "id": "delete-me"}],
            confirm_delete=True,
        )

        self.assertEqual(confirmed["succeeded"][0]["operation"], "delete")
        self.assertEqual(
            confirmed["succeeded"][0]["syncedFiles"],
            [".workflow-studio/actions/delete-me.json"],
        )
        self.assertFalse(deleted_path.exists())
        self.assertTrue(kept_path.exists())
        retained = self.state.get_resource(PROJECT_ID, "action", "delete-me")
        self.assertEqual(retained["status"], "source_missing")
        self.assertEqual(retained["synced_manifest"], [])
        self.assertEqual(retained["payload"]["id"], "delete-me")

        # A Studio-only record has no previously synced targets.  Even if an
        # unrelated file later appears at its derived path, deletion must not
        # remove a path that Studio never recorded as its own.
        self.save_and_publish_action("never-synced")
        self.service.stage_delete(PROJECT_ID, "action", "never-synced")
        unrecorded_target = (
            self.project_root / ".workflow-studio/actions/never-synced.json"
        )
        unrecorded_target.write_text("external file\n", encoding="utf-8")

        studio_only_delete = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "action", "id": "never-synced"}],
            confirm_delete=True,
        )

        self.assertEqual(studio_only_delete["succeeded"][0]["syncedFiles"], [])
        self.assertEqual(unrecorded_target.read_text(encoding="utf-8"), "external file\n")

    def test_deleting_an_untested_agent_skips_the_agent_test_gate(self):
        self.import_project()
        staged = self.service.stage_delete(PROJECT_ID, "agent", "agents-writer")
        self.assertEqual(staged["resourceStatus"], "pending_delete")

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "agent", "id": "agents-writer"}],
            confirm_delete=True,
        )

        self.assertEqual(result["blocked"], [])
        self.assertEqual(result["succeeded"][0]["operation"], "delete")
        self.assertFalse((self.project_root / "agents/writer/AGENT.md").exists())

    def test_deleting_an_invalid_workflow_skips_dry_run_and_dependency_gates(self):
        workflow_path = self.project_root / ".codex/workflows/delete-cycle.json"
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text(
            json.dumps(
                {
                    "id": "delete-cycle",
                    "name": "Delete cycle",
                    "nodes": [
                        {"id": "a", "type": "agent", "agentId": "missing-a"},
                        {"id": "b", "type": "agent", "agentId": "missing-b"},
                    ],
                    "edges": [
                        {"id": "ab", "source": "a", "target": "b"},
                        {"id": "ba", "source": "b", "target": "a"},
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.import_project()
        self.service.stage_delete(PROJECT_ID, "workflow", "delete-cycle")

        result = self.service.sync(
            PROJECT_ID,
            self.store,
            selected=[{"kind": "workflow", "id": "delete-cycle"}],
            confirm_delete=True,
        )

        self.assertEqual(result["blocked"], [])
        self.assertEqual(result["succeeded"][0]["operation"], "delete")
        self.assertFalse(workflow_path.exists())

    def test_multi_file_agent_write_rolls_back_the_entire_resource(self):
        self.import_project()
        self.publish_changed_agent()
        before = snapshot_tree(self.project_root)
        failing_store = FailAfterAgentWriteStore(self.project_root)

        result = self.service.sync(
            PROJECT_ID,
            failing_store,
            selected=[{"kind": "agent", "id": "agents-writer"}],
        )

        self.assertEqual(result["failed"][0]["id"], "agents-writer")
        self.assertEqual(snapshot_tree(self.project_root), before)
        failed = self.state.get_resource(PROJECT_ID, "agent", "agents-writer")
        self.assertEqual(failed["status"], "sync_failed")
        self.assertIn("injected failure", failed["sync_error"])


if __name__ == "__main__":
    unittest.main()
