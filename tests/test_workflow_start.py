import copy
import tempfile
import unittest
from pathlib import Path

from server import WorkflowStore, credential_env_name, normalize_start_phrases


class StartPhraseTests(unittest.TestCase):
    def test_normalize_trims_dedupes_and_splits(self):
        self.assertEqual(normalize_start_phrases(None), [])
        self.assertEqual(normalize_start_phrases(" 开始 , start，开始吧、 START "), ["开始", "start", "开始吧"])
        self.assertEqual(normalize_start_phrases(["  开  始 ", "", "开 始"]), ["开 始"])

    def test_normalize_rejects_unsafe_or_too_many(self):
        for value in (["x" * 33], ["bad`tick"], [f"p{index}" for index in range(9)], 42):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_start_phrases(value)

    def test_credential_env_name(self):
        self.assertEqual(credential_env_name("api-credential"), "API_CREDENTIAL")
        self.assertEqual(credential_env_name("microsoft-graph-outlook-oauth"), "MICROSOFT_GRAPH_OUTLOOK_OAUTH")
        self.assertEqual(credential_env_name("1password.item"), "CRED_1PASSWORD_ITEM")


class WorkflowStartAndActionTests(unittest.TestCase):
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
        self.store.save_action(
            "fetch",
            {
                "id": "fetch",
                "name": "Fetch",
                "executor": "api",
                "inputs": {"since": "string"},
                "steps": [{"type": "http.request", "method": "GET", "path": "/v1/items?since={{inputs.since}}"}],
                "success": {"statusCodes": [200]},
                "outputs": {"items": "array"},
                "timeoutSeconds": 20,
                "errorHandling": {"strategy": "stop", "retries": 2},
                "credentialRefs": ["items-api"],
                "connection": {"kind": "http", "endpoint": "https://api.example.com"},
            },
        )
        self.store.save_action(
            "loose",
            {
                "id": "loose",
                "name": "Loose",
                "executor": "api",
                "inputs": {},
                "steps": [{"type": "http.request", "method": "POST", "path": "/v1/thing"}],
                "success": {"statusCodes": [201]},
                "outputs": {},
                "credentialRefs": [],
            },
        )
        self.store.save_action(
            "tool",
            {
                "id": "tool",
                "name": "Tool",
                "executor": "mcp",
                "inputs": {"arguments": "object"},
                "steps": [{"type": "mcp.call_tool", "tool": "lookup", "arguments": "{{inputs.arguments}}"}],
                "success": {"resultReceived": True},
                "outputs": {"result": "object"},
                "credentialRefs": [],
            },
        )
        agent = self.store.get_agent("agents-worker")
        agent["allowedActions"] = ["fetch", "loose", "tool"]
        self.store.save_agent("agents-worker", agent)
        self.workflow = {
            "id": "daily",
            "name": "Daily",
            "description": "Fetch and summarize.",
            "startPhrases": ["开始", " start "],
            "nodes": [
                {"id": "fetch-node", "type": "action", "actionId": "fetch", "agentId": "agents-worker", "label": "Fetch items"},
                {"id": "tool-node", "type": "action", "actionId": "tool", "agentId": "agents-worker", "label": "Lookup"},
                {"id": "write", "type": "agent", "agentId": "agents-worker", "label": "Write", "entrypoint": "agents/worker/AGENT.md", "role": "Summarize the items."},
            ],
            "edges": [
                {"id": "e1", "source": "fetch-node", "target": "write", "condition": "items fetched"},
                {"id": "e2", "source": "tool-node", "target": "write", "condition": "lookup done"},
            ],
        }

    def tearDown(self):
        self.temporary.cleanup()

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def test_start_phrases_reach_agents_md_skill_and_metadata(self):
        result = self.store.save_workflow("daily", self.workflow)

        self.assertEqual(result["workflow"]["startPhrases"], ["开始", "start"])
        agents = self.read("AGENTS.md")
        self.assertIn("## Start phrases", agents)
        self.assertIn("- “开始” → `$workflow-daily` (Daily)", agents)
        self.assertIn("- “start” → `$workflow-daily` (Daily)", agents)
        skill = self.read(".agents/skills/workflow-daily/SKILL.md")
        self.assertIn("sends a start phrase: “开始”、“start”.", skill)
        self.assertIn("When the user's whole message is one of them, start this workflow right away", skill)
        self.assertIn('default_prompt: "开始"', self.read(".agents/skills/workflow-daily/agents/openai.yaml"))

    def test_parallel_steps_share_a_number_and_handoffs_are_listed(self):
        self.store.save_workflow("daily", self.workflow)
        skill = self.read(".agents/skills/workflow-daily/SKILL.md")
        self.assertIn("### 1a. Fetch items — Action `fetch` (api)", skill)
        self.assertIn("### 1b. Lookup — Action `tool` (mcp)", skill)
        self.assertIn("### 2. Write — Agent", skill)
        self.assertIn("- Input: the results of step 1a (Fetch items), step 1b (Lookup).", skill)
        self.assertIn("- Hand off to step 2 (Write) when: items fetched", skill)

    def test_api_and_mcp_actions_are_run_by_codex_with_env_credentials(self):
        self.store.save_workflow("daily", self.workflow)
        skill = self.read(".agents/skills/workflow-daily/SKILL.md")
        self.assertIn("`GET https://api.example.com/v1/items?since={{inputs.since}}`", skill)
        self.assertIn("`$ITEMS_API` (ref `items-api`)", skill)
        self.assertIn("Never print, log, or write a secret", skill)
        self.assertIn("retry up to 2 time(s)", skill)
        self.assertIn("call the MCP tool `lookup`", skill)
        self.assertIn("mcp-not-configured", skill)

    def test_api_action_without_endpoint_stops_instead_of_guessing(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["nodes"][0]["actionId"] = "loose"
        self.store.save_workflow("daily", workflow)
        skill = self.read(".agents/skills/workflow-daily/SKILL.md")
        self.assertIn("`POST /v1/thing`", skill)
        self.assertIn("endpoint-required", skill)

    def test_agent_skill_explains_how_to_run_allowed_actions(self):
        agent = self.store.get_agent("agents-worker")
        self.store.save_agent("agents-worker", agent)
        skill = self.read(".agents/skills/agent-agents-worker/SKILL.md")
        self.assertIn("- `fetch` — Fetch", skill)
        self.assertIn("build them from the task you were given", skill)
        self.assertIn("run each exactly as declared", skill)
        self.assertNotIn("executed by the Action Runtime", skill)

    def test_start_phrase_conflicts_are_rejected_across_workflows(self):
        self.store.save_workflow("daily", self.workflow)
        other = copy.deepcopy(self.workflow)
        other["id"] = "weekly"
        other["name"] = "Weekly"
        other["startPhrases"] = ["START"]
        errors, _ = self.store.validate(other)
        self.assertTrue(any("已被 Workflow「Daily」使用" in error for error in errors))
        with self.assertRaises(ValueError):
            self.store.save_workflow("weekly", other)
        # Re-saving the owner with the same phrases stays valid.
        errors, _ = self.store.validate(self.workflow)
        self.assertEqual(errors, [])

    def test_clearing_start_phrases_removes_the_map(self):
        self.store.save_workflow("daily", self.workflow)
        cleared = copy.deepcopy(self.workflow)
        cleared["startPhrases"] = []
        result = self.store.save_workflow("daily", cleared)
        self.assertNotIn("startPhrases", result["workflow"])
        self.assertNotIn("## Start phrases", self.read("AGENTS.md"))


if __name__ == "__main__":
    unittest.main()
