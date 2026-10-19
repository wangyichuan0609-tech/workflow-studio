"""Read-only Workflow draft validation for Workflow Studio.

This module deliberately has no project write operations.  It validates a
Studio draft against Studio resources and describes the execution plan that
Codex would later use after an explicit sync.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional


def _resource_map(resources: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(resources, Mapping):
        return {
            str(resource_id): value
            for resource_id, value in resources.items()
            if isinstance(value, dict)
        }
    if isinstance(resources, Iterable) and not isinstance(resources, (str, bytes)):
        result: Dict[str, Dict[str, Any]] = {}
        for value in resources:
            if isinstance(value, dict) and str(value.get("id") or ""):
                result[str(value["id"])] = value
        return result
    return {}


def dry_run_workflow(
    workflow: Dict[str, Any],
    agents: Any,
    actions: Any,
    runtime_check: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    """Validate *workflow* and return a deterministic, UI-friendly plan.

    ``agents`` and ``actions`` may be id-keyed mappings or resource lists.  A
    runtime checker is invoked only when at least one script Action is used.
    Without an external binding the coding agent (Codex) runs script Actions
    itself, exactly as declared, so that is not a warning; malformed runtime
    configuration is an error.
    """

    errors: List[str] = []
    warnings: List[str] = []
    agent_map = _resource_map(agents)
    action_map = _resource_map(actions)

    if not isinstance(workflow, dict):
        return {
            "valid": False,
            "errors": ["Workflow 必须是 JSON 对象。"],
            "warnings": [],
            "layers": [],
            "handoffs": [],
            "dependencies": [],
        }
    if not str(workflow.get("name") or "").strip():
        errors.append("请填写 Workflow 名称。")

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {
            "valid": False,
            "errors": [*errors, "nodes 和 edges 必须是数组。"],
            "warnings": warnings,
            "layers": [],
            "handoffs": [],
            "dependencies": [],
        }
    if not nodes:
        warnings.append("Workflow 还没有节点。")

    node_by_id: Dict[str, Dict[str, Any]] = {}
    node_order: List[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"第 {index + 1} 个节点必须是对象。")
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            errors.append("每个节点都需要唯一的 id。")
            continue
        if node_id in node_by_id:
            errors.append(f"节点 id「{node_id}」重复。")
            continue
        if not re.fullmatch(r"[\w][\w-]{0,127}", node_id, re.UNICODE):
            errors.append(
                f"节点 id「{node_id}」只能包含字母、数字、下划线和连字符。"
            )
        node_by_id[node_id] = node
        node_order.append(node_id)

    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_order}
    indegree: Dict[str, int] = {node_id: 0 for node_id in node_order}
    edge_ids = set()
    handoffs: List[Dict[str, Any]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"第 {index + 1} 条连线必须是对象。")
            continue
        edge_id = str(edge.get("id") or "")
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not edge_id or edge_id in edge_ids:
            errors.append("每条连线都需要唯一的 id。")
        if edge_id:
            edge_ids.add(edge_id)
        if source not in node_by_id or target not in node_by_id:
            errors.append(
                f"连线「{edge_id or '未命名'}」引用了不存在的节点。"
            )
            continue
        if source == target:
            errors.append("节点不能连接到自己。")
            continue
        adjacency[source].append(target)
        indegree[target] += 1
        handoffs.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "sourceLabel": str(node_by_id[source].get("label") or source),
                "targetLabel": str(node_by_id[target].get("label") or target),
                "condition": str(edge.get("condition") or "after the source completes"),
            }
        )

    # Stable Kahn traversal makes the result useful in the canvas and tests.
    position = {node_id: index for index, node_id in enumerate(node_order)}
    current = [node_id for node_id in node_order if indegree[node_id] == 0]
    layers: List[List[str]] = []
    visited = 0
    while current:
        current.sort(key=position.__getitem__)
        layers.append(list(current))
        following: List[str] = []
        for node_id in current:
            visited += 1
            for target in adjacency[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    following.append(target)
        current = following
    if visited != len(node_order):
        errors.append("Workflow 存在循环（cycle）：Codex Workflow 必须是有向无环图，请删除形成回路的连线。")
        layers = []

    dependencies: List[Dict[str, str]] = []
    dependency_keys = set()
    script_actions: List[str] = []
    for node_id in node_order:
        node = node_by_id[node_id]
        node_type = str(node.get("type") or "agent")
        agent_id = str(node.get("agentId") or "")
        if node_type == "agent":
            if not agent_id or agent_id not in agent_map:
                errors.append(
                    f"Agent「{agent_id or '缺失'}」不在 Studio 中。"
                )
            else:
                key = ("agent", agent_id)
                if key not in dependency_keys:
                    dependency_keys.add(key)
                    dependencies.append({"kind": "agent", "id": agent_id})
            continue
        if node_type != "action":
            errors.append(f"不支持的 Workflow 节点类型「{node_type}」。")
            continue
        action_id = str(node.get("actionId") or "")
        action = action_map.get(action_id)
        if action is None:
            errors.append(
                f"Action「{action_id or '缺失'}」不在 Studio 中。"
            )
        else:
            key = ("action", action_id)
            if key not in dependency_keys:
                dependency_keys.add(key)
                dependencies.append({"kind": "action", "id": action_id})
            if str(action.get("executor") or "") == "script":
                script_actions.append(action_id)
        caller = agent_map.get(agent_id)
        if caller is None:
            errors.append(f"Action 节点「{node_id}」需要一个已授权它的 Agent。")
        else:
            key = ("agent", agent_id)
            if key not in dependency_keys:
                dependency_keys.add(key)
                dependencies.append({"kind": "agent", "id": agent_id})
            allowed = caller.get("allowedActions", [])
            if not isinstance(allowed, list) or action_id not in allowed:
                errors.append(
                    f"Agent「{agent_id}」未被授权调用 Action「{action_id}」。"
                )

    runtime: Dict[str, Any] = {
        "required": bool(script_actions),
        "available": True,
        "executor": "codex" if script_actions else "none",
        "scriptActions": list(dict.fromkeys(script_actions)),
    }
    if script_actions and runtime_check is not None:
        try:
            binding = runtime_check()
        except ValueError as error:
            runtime["error"] = str(error)
            runtime["available"] = False
            errors.append(str(error))
        else:
            if isinstance(binding, dict):
                runtime["binding"] = binding
                runtime["executor"] = "external"

    if len(layers) > 1:
        covered = {source for source, targets in adjacency.items() if targets}
        covered.update(target for targets in adjacency.values() for target in targets)
        isolated = [node_id for node_id in node_order if node_id not in covered]
        if isolated and len(node_order) > 1:
            warnings.append("部分节点未连接：" + "、".join(isolated) + "。")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "layers": layers,
        "handoffs": handoffs,
        "dependencies": dependencies,
        "runtime": runtime,
    }

