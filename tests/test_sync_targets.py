import tempfile
import unittest
from pathlib import Path

from server import CodexProjectRegistry, WorkflowStore, detect_agent_tools, normalize_sync_targets
from studio_service import StudioService


class SyncTargetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        agent_root = self.root / "agents" / "worker"
        agent_root.mkdir(parents=True)
        (agent_root / "AGENT.md").write_text(
            "---\nname: Worker\ndescription: Processes a payload.\n---\n\n# Worker\n",
            encoding="utf-8",
        )
        self.workflow = {
            "id": "daily",
            "name": "Daily",
            "description": "Summarize the day.",
            "startPhrases": ["开始"],
            "nodes": [
                {"id": "write", "type": "agent", "agentId": "agents-worker", "label": "Write", "entrypoint": "agents/worker/AGENT.md"},
            ],
            "edges": [],
        }

    def tearDown(self):
        self.temporary.cleanup()

    def store(self, targets=None):
        return WorkflowStore(self.root, targets=targets)

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def test_normalize_targets_keeps_known_ids_in_order(self):
        self.assertEqual(normalize_sync_targets(["QWEN", "unknown", "claude", "qwen"]), ["claude", "qwen"])
        self.assertEqual(normalize_sync_targets("claude"), [])

    def test_codex_only_store_writes_nothing_extra(self):
        result = self.store().save_workflow("daily", self.workflow)
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / "QWEN.md").exists())
        self.assertNotIn("QWEN.md", result["syncedFiles"])

    def test_targets_mirror_skills_and_write_qwen_instructions(self):
        store = self.store(["claude", "qwen"])
        store.save_agent("agents-worker", store.get_agent("agents-worker"))
        result = store.save_workflow("daily", self.workflow)

        canonical = self.read(".agents/skills/workflow-daily/SKILL.md")
        self.assertEqual(self.read(".claude/skills/workflow-daily/SKILL.md"), canonical)
        self.assertEqual(self.read(".qwen/skills/workflow-daily/SKILL.md"), canonical)
        self.assertEqual(
            self.read(".claude/skills/agent-agents-worker/SKILL.md"),
            self.read(".agents/skills/agent-agents-worker/SKILL.md"),
        )
        self.assertIn(".claude/skills/workflow-daily/SKILL.md", result["syncedFiles"])
        self.assertIn("QWEN.md", result["syncedFiles"])
        qwen = self.read("QWEN.md")
        self.assertIn("project skills under `.qwen/skills/`", qwen)
        self.assertIn("- “开始” → `$workflow-daily` (Daily)", qwen)
        # Without a CLAUDE.md, Claude Code reads AGENTS.md itself: no file is created.
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_existing_claude_md_gets_one_import_block_and_keeps_user_text(self):
        (self.root / "CLAUDE.md").write_text("# My rules\n\nUse tabs.\n", encoding="utf-8")
        store = self.store(["claude"])
        store.save_workflow("daily", self.workflow)
        store.save_workflow("daily", self.workflow)

        claude = self.read("CLAUDE.md")
        self.assertTrue(claude.startswith("# My rules\n\nUse tabs.\n"))
        self.assertEqual(claude.count("@AGENTS.md"), 1)
        self.assertEqual(claude.count("<!-- workflow-studio:start -->"), 1)
        self.assertIn("CLAUDE.md", store.target_files_for("workflow", "daily"))

    def test_apply_targets_mirrors_already_synced_skills(self):
        self.store().save_workflow("daily", self.workflow)
        self.assertFalse((self.root / ".qwen").exists())

        written = self.store(["qwen"]).apply_targets()

        self.assertIn(".qwen/skills/workflow-daily/SKILL.md", written)
        self.assertIn("QWEN.md", written)
        self.assertTrue((self.root / ".qwen/skills/workflow-daily/SKILL.md").is_file())

    def test_sync_target_files_include_mirrors_and_deletes_skip_instructions(self):
        store = self.store(["claude", "qwen"])
        resource = {
            "kind": "workflow",
            "resource_id": "daily",
            "payload": self.workflow,
            "synced_manifest": [".codex/workflows/daily.json"],
            "status": "ready",
        }
        upsert = StudioService.target_files(None, resource, store)
        self.assertIn(".claude/skills/workflow-daily/SKILL.md", upsert)
        self.assertIn(".qwen/skills/workflow-daily/SKILL.md", upsert)
        self.assertIn("QWEN.md", upsert)

        deleting = dict(resource, status="pending_delete")
        removed = StudioService.target_files(None, deleting, store)
        self.assertIn(".qwen/skills/workflow-daily/SKILL.md", removed)
        self.assertNotIn("QWEN.md", removed)

    def test_detect_agent_tools(self):
        (self.root / ".qwen").mkdir()
        (self.root / "CLAUDE.md").write_text("x", encoding="utf-8")
        detected = detect_agent_tools(self.root)
        self.assertTrue(detected["qwen"])
        self.assertTrue(detected["claude"])
        self.assertFalse(detected["opencode"])


class FolderProjectTests(unittest.TestCase):
    def test_added_folders_join_the_project_list_with_stable_ids(self):
        with tempfile.TemporaryDirectory() as codex_home, tempfile.TemporaryDirectory() as active, tempfile.TemporaryDirectory() as folder:
            registry = CodexProjectRegistry(Path(active), codex_home=Path(codex_home))
            self.assertEqual([project["id"] for project in registry.list_projects()], ["current-project"])

            registry.folder_provider = lambda: [folder, folder]
            projects = registry.list_projects(include_paths=True)

            # The start folder stays listed; the added folder follows it once.
            self.assertEqual([project["id"] for project in projects][0], "current-project")
            folders = [project for project in projects if project.get("source") == "folder"]
            self.assertEqual(len(folders), 1)
            self.assertEqual(folders[0]["id"], CodexProjectRegistry.folder_project_id(Path(folder)))
            self.assertTrue(folders[0]["available"])
            self.assertEqual(registry.select(folders[0]["id"])["path"], str(Path(folder).resolve()))


if __name__ == "__main__":
    unittest.main()
