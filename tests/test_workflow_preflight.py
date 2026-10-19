import copy
import unittest

from workflow_preflight import dry_run_workflow


class WorkflowPreflightTests(unittest.TestCase):
    def setUp(self):
        self.agents = {
            "writer": {
                "id": "writer",
                "name": "Writer",
                "allowedActions": ["verify", "normalize"],
            },
            "reviewer": {
                "id": "reviewer",
                "name": "Reviewer",
                "allowedActions": [],
            },
        }
        self.actions = {
            "verify": {"id": "verify", "name": "Verify", "executor": "api"},
            "normalize": {
                "id": "normalize",
                "name": "Normalize",
                "executor": "script",
            },
        }

    @staticmethod
    def workflow(nodes, edges, name="Draft flow"):
        return {
            "id": "draft-flow",
            "name": name,
            "nodes": nodes,
            "edges": edges,
        }

    @staticmethod
    def agent_node(node_id, agent_id="writer", label=None):
        return {
            "id": node_id,
            "type": "agent",
            "agentId": agent_id,
            "label": label or node_id,
        }

    @staticmethod
    def action_node(node_id, action_id="verify", agent_id="writer", label=None):
        return {
            "id": node_id,
            "type": "action",
            "actionId": action_id,
            "agentId": agent_id,
            "label": label or node_id,
        }

    def test_multi_root_graph_merges_into_one_stable_layer(self):
        workflow = self.workflow(
            [
                self.agent_node("root-b", label="Root B"),
                self.agent_node("merge", agent_id="reviewer", label="Merge"),
                self.agent_node("root-a", label="Root A"),
            ],
            [
                {"id": "a-to-merge", "source": "root-a", "target": "merge"},
                {"id": "b-to-merge", "source": "root-b", "target": "merge"},
            ],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertTrue(result["valid"])
        self.assertEqual(result["layers"], [["root-b", "root-a"], ["merge"]])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(
            result["dependencies"],
            [{"kind": "agent", "id": "writer"}, {"kind": "agent", "id": "reviewer"}],
        )

    def test_merge_topology_and_handoffs_are_deterministic(self):
        workflow = self.workflow(
            [
                self.agent_node("start", label="Start"),
                self.agent_node("right", label="Right"),
                self.agent_node("left", label="Left"),
                self.agent_node("finish", agent_id="reviewer", label="Finish"),
            ],
            [
                {"id": "right-finish", "source": "right", "target": "finish"},
                {
                    "id": "start-left",
                    "source": "start",
                    "target": "left",
                    "condition": "draft ready",
                },
                {"id": "left-finish", "source": "left", "target": "finish"},
                {"id": "start-right", "source": "start", "target": "right"},
            ],
        )

        first = dry_run_workflow(workflow, self.agents, self.actions)
        second = dry_run_workflow(copy.deepcopy(workflow), self.agents, self.actions)

        self.assertEqual(first, second)
        self.assertEqual(first["layers"], [["start"], ["right", "left"], ["finish"]])
        self.assertEqual(
            [handoff["id"] for handoff in first["handoffs"]],
            ["right-finish", "start-left", "left-finish", "start-right"],
        )
        self.assertEqual(first["handoffs"][1]["condition"], "draft ready")
        self.assertEqual(
            first["handoffs"][0]["condition"], "after the source completes"
        )

    def test_cycle_is_an_error_and_has_no_execution_layers(self):
        workflow = self.workflow(
            [self.agent_node("a"), self.agent_node("b", agent_id="reviewer")],
            [
                {"id": "a-b", "source": "a", "target": "b"},
                {"id": "b-a", "source": "b", "target": "a"},
            ],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertFalse(result["valid"])
        self.assertEqual(result["layers"], [])
        self.assertTrue(any("cycle" in error.lower() for error in result["errors"]))

    def test_malformed_nodes_and_edges_are_reported_without_crashing(self):
        workflow = self.workflow(
            [
                "not-an-object",
                {"type": "agent", "agentId": "writer"},
                self.agent_node("valid"),
                self.agent_node("valid", agent_id="reviewer"),
                self.agent_node("bad id"),
            ],
            [
                "not-an-object",
                {"id": "missing-target", "source": "valid", "target": "absent"},
                {"id": "self", "source": "valid", "target": "valid"},
                {"source": "valid", "target": "bad id"},
            ],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertFalse(result["valid"])
        joined = "\n".join(result["errors"])
        self.assertIn("第 1 个节点必须是对象", joined)
        self.assertIn("每个节点都需要唯一的 id", joined)
        self.assertIn("重复", joined)
        self.assertIn("只能包含字母", joined)
        self.assertIn("第 1 条连线必须是对象", joined)
        self.assertIn("引用了不存在的节点", joined)
        self.assertIn("不能连接到自己", joined)
        self.assertIn("每条连线都需要唯一的 id", joined)

    def test_non_array_nodes_or_edges_are_rejected(self):
        for field in ("nodes", "edges"):
            with self.subTest(field=field):
                workflow = self.workflow([], [])
                workflow[field] = {}
                result = dry_run_workflow(workflow, self.agents, self.actions)
                self.assertFalse(result["valid"])
                self.assertTrue(
                    any("nodes 和 edges 必须是数组" in error for error in result["errors"])
                )

    def test_missing_studio_agent_and_action_are_both_errors(self):
        workflow = self.workflow(
            [
                self.agent_node("ghost-agent", agent_id="missing-agent"),
                self.action_node("ghost-action", action_id="missing-action"),
            ],
            [],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertFalse(result["valid"])
        joined = "\n".join(result["errors"])
        self.assertIn("Agent「missing-agent」不在 Studio 中", joined)
        self.assertIn("Action「missing-action」不在 Studio 中", joined)
        self.assertNotIn(
            {"kind": "action", "id": "missing-action"}, result["dependencies"]
        )

    def test_action_must_be_authorized_for_its_caller(self):
        workflow = self.workflow(
            [self.action_node("verify-node", agent_id="reviewer")],
            [],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertFalse(result["valid"])
        self.assertIn(
            "Agent「reviewer」未被授权调用 Action「verify」。",
            result["errors"],
        )
        self.assertEqual(
            result["dependencies"],
            [{"kind": "action", "id": "verify"}, {"kind": "agent", "id": "reviewer"}],
        )

    def test_missing_script_runtime_means_codex_runs_the_action(self):
        workflow = self.workflow(
            [self.action_node("normalize-node", action_id="normalize")],
            [],
        )

        result = dry_run_workflow(workflow, self.agents, self.actions)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertFalse(any("Runtime" in warning for warning in result["warnings"]))
        self.assertEqual(
            result["runtime"],
            {
                "required": True,
                "available": True,
                "executor": "codex",
                "scriptActions": ["normalize"],
            },
        )

    def test_malformed_script_runtime_is_a_blocking_error(self):
        workflow = self.workflow(
            [self.action_node("normalize-node", action_id="normalize")],
            [],
        )

        def malformed_runtime():
            raise ValueError("Action Runtime binding requires schemaVersion 1.")

        result = dry_run_workflow(
            workflow, self.agents, self.actions, runtime_check=malformed_runtime
        )

        self.assertFalse(result["valid"])
        self.assertIn(
            "Action Runtime binding requires schemaVersion 1.", result["errors"]
        )
        self.assertEqual(
            result["runtime"]["error"],
            "Action Runtime binding requires schemaVersion 1.",
        )
        self.assertFalse(result["runtime"]["available"])

    def test_valid_script_runtime_is_exposed_in_plan(self):
        workflow = self.workflow(
            [self.action_node("normalize-node", action_id="normalize")],
            [],
        )
        binding = {
            "id": "local-runtime",
            "argv": ["python3", ".runtime/adapter.py"],
        }

        result = dry_run_workflow(
            workflow, self.agents, self.actions, runtime_check=lambda: binding
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["warnings"], [])
        self.assertTrue(result["runtime"]["available"])
        self.assertEqual(result["runtime"]["binding"], binding)


if __name__ == "__main__":
    unittest.main()
