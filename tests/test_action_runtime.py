import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server import ACTION_RUNTIME_CONFIG, WorkflowStore


class ExternalActionRuntimeBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = WorkflowStore(self.root)
        agent_root = self.root / "agents" / "worker"
        agent_root.mkdir(parents=True)
        (agent_root / "AGENT.md").write_text(
            "---\nname: Worker\ndescription: Processes a payload.\n---\n\n# Worker\n",
            encoding="utf-8",
        )
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "normalize.py").write_text(
            "import json, sys\npayload = json.load(sys.stdin)\njson.dump(payload, sys.stdout)\n",
            encoding="utf-8",
        )
        self.action = {
            "id": "normalize",
            "name": "Normalize",
            "description": "Normalize a local payload.",
            "executor": "script",
            "inputs": {"payload": "object"},
            "steps": [
                {
                    "type": "process.exec",
                    "command": "python3",
                    "args": ["scripts/normalize.py"],
                    "stdin": "{{inputs.payload}}",
                }
            ],
            "success": {"exitCode": 0},
            "outputs": {"normalized": "object"},
            "timeoutSeconds": 5,
            "errorHandling": {"strategy": "stop", "retries": 0},
            "credentialRefs": [],
        }
        self.store.save_action("normalize", self.action)
        agent = self.store.get_agent("agents-worker")
        agent["allowedActions"] = ["normalize"]
        self.store.save_agent("agents-worker", agent)
        self.workflow = {
            "id": "runtime-demo",
            "name": "Runtime Demo",
            "description": "Test an external Action Runtime binding.",
            "nodes": [
                {
                    "id": "prepare",
                    "type": "agent",
                    "agentId": "agents-worker",
                    "label": "Prepare",
                    "entrypoint": "agents/worker/AGENT.md",
                },
                {
                    "id": "normalize-node",
                    "type": "action",
                    "actionId": "normalize",
                    "agentId": "agents-worker",
                    "label": "Normalize",
                },
                {
                    "id": "review",
                    "type": "agent",
                    "agentId": "agents-worker",
                    "label": "Review",
                    "entrypoint": "agents/worker/AGENT.md",
                },
            ],
            "edges": [
                {"id": "to-normalize", "source": "prepare", "target": "normalize-node", "condition": "ready"},
                {"id": "to-review", "source": "normalize-node", "target": "review", "condition": "normalized"},
            ],
        }

    def tearDown(self):
        self.temporary.cleanup()

    @property
    def config_path(self):
        return self.root / ACTION_RUNTIME_CONFIG

    def install_external_runtime(self, updates=None):
        adapter = self.root / ".external-runtime" / "adapter.py"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text("# independently installed runtime fixture\n", encoding="utf-8")
        config = {
            "schemaVersion": 1,
            "id": "fixture-runtime",
            "contractVersion": 1,
            "supports": ["script/process.exec"],
            "argv": ["python3", ".external-runtime/adapter.py"],
        }
        if updates:
            config.update(updates)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        return adapter

    def test_unconfigured_script_action_runs_directly_in_codex(self):
        errors, warnings = self.store.validate(self.workflow)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

        result = self.store.save_workflow("runtime-demo", self.workflow)

        self.assertEqual(len(result["syncedFiles"]), 4)
        self.assertEqual(result["warnings"], [])
        self.assertFalse((self.root / ".workflow-studio" / "action_runtime.py").exists())
        skill = (self.root / ".agents/skills/workflow-runtime-demo/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("runtime-required", skill)
        self.assertNotIn(" run-node --workflow ", skill)
        self.assertIn("python3 scripts/normalize.py", skill)
        self.assertIn("stdin: the value of input `payload`", skill)
        self.assertIn("Timeout 5 s. Success: exit code 0.", skill)
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("2 agents + 1 action, 2 connections", agents)

    def test_explicit_binding_generates_command_without_touching_runtime(self):
        adapter = self.install_external_runtime()
        before = hashlib.sha256(adapter.read_bytes()).hexdigest()

        result = self.store.save_workflow("runtime-demo", self.workflow)

        after = hashlib.sha256(adapter.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(len(result["syncedFiles"]), 4)
        self.assertNotIn(adapter.relative_to(self.root).as_posix(), result["syncedFiles"])
        self.assertNotIn(self.config_path.relative_to(self.root).as_posix(), result["syncedFiles"])
        skill = (self.root / ".agents/skills/workflow-runtime-demo/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "python3 .external-runtime/adapter.py run-node --workflow runtime-demo --node normalize-node",
            skill,
        )
        self.assertIn("inputs.payload", skill)

    def test_invalid_or_unsafe_binding_is_rejected(self):
        cases = {
            "incompatible contract": {"contractVersion": 2},
            "missing capability": {"supports": ["api/http"]},
            "path traversal": {"argv": ["python3", "../escape.py"]},
            "option-like script": {"argv": ["python3", "-adapter.py"]},
            "unsupported executable": {"argv": ["bash", ".external-runtime/adapter.py"]},
            "markdown injection": {"argv": ["python3", ".external-runtime/adapter`bad.py"]},
            "unknown field": {"secret": "must-not-be-ignored"},
        }
        for label, updates in cases.items():
            with self.subTest(label=label):
                self.install_external_runtime(updates)
                with self.assertRaises(ValueError):
                    self.store.save_workflow("runtime-demo", self.workflow)

    def test_node_ids_are_safe_and_unicode_ids_are_supported(self):
        self.install_external_runtime()
        malicious = copy.deepcopy(self.workflow)
        malicious["nodes"][1]["id"] = "node;touch-pwned"
        malicious["edges"][0]["target"] = "node;touch-pwned"
        malicious["edges"][1]["source"] = "node;touch-pwned"
        with self.assertRaises(ValueError):
            self.store.save_workflow("runtime-demo", malicious)

        option_like = copy.deepcopy(self.workflow)
        option_like["nodes"][1]["id"] = "-normalize-node"
        option_like["edges"][0]["target"] = "-normalize-node"
        option_like["edges"][1]["source"] = "-normalize-node"
        with self.assertRaises(ValueError):
            self.store.save_workflow("runtime-demo", option_like)

        unicode_workflow = copy.deepcopy(self.workflow)
        unicode_workflow["nodes"][1]["id"] = "标准化节点"
        unicode_workflow["edges"][0]["target"] = "标准化节点"
        unicode_workflow["edges"][1]["source"] = "标准化节点"
        self.store.save_workflow("会议流程", unicode_workflow)
        skill = (self.root / ".agents/skills/workflow-会议流程/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--workflow", skill)
        self.assertIn("会议流程", skill)
        self.assertIn("标准化节点", skill)

    def test_runtime_binding_symlink_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = Path(outside_directory) / "action-runtime.json"
            outside.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "id": "outside-runtime",
                        "contractVersion": 1,
                        "supports": ["script/process.exec"],
                        "argv": ["python3", ".external-runtime/adapter.py"],
                    }
                ),
                encoding="utf-8",
            )
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.symlink_to(outside)

            errors, _ = self.store.validate(self.workflow)

        self.assertTrue(any("stay inside" in error for error in errors))

    def test_removing_binding_switches_back_to_direct_execution(self):
        self.install_external_runtime()
        self.store.save_workflow("runtime-demo", self.workflow)
        self.config_path.unlink()

        result = self.store.save_workflow("runtime-demo", self.workflow)

        self.assertEqual(result["warnings"], [])
        skill = (self.root / ".agents/skills/workflow-runtime-demo/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(" run-node --workflow ", skill)
        self.assertIn("python3 scripts/normalize.py", skill)

if __name__ == "__main__":
    unittest.main()
