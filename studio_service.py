"""Studio persistence/import/sync orchestration.

The service keeps every ordinary edit in SQLite.  Calls into the supplied
Codex project adapter are limited to :meth:`import_project` (read-only) and the
explicit :meth:`sync` methods below.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from resource_paths import (
    generated_skill_invocation,
    generated_skill_paths,
    managed_section_mentions_invocation,
)
from studio_state import (
    ResourceNotFoundError,
    RevisionConflictError,
    StudioState,
    StudioStateError,
    canonical_hash,
    summary,
)
from workflow_preflight import dry_run_workflow


SYNCABLE_STATUSES = frozenset({"ready", "pending_delete", "sync_failed"})
SYNC_ORDER = {"skill": 0, "action": 0, "agent": 1, "workflow": 2}


def _slugify(value: str, fallback: str = "resource") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]+", "-", value)
    value = re.sub(r"[-_]{2,}", "-", value).strip("-_")
    return value[:64] or fallback


def _resource_key(value: Mapping[str, Any]) -> Tuple[str, str]:
    return str(value.get("kind") or ""), str(
        value.get("id") or value.get("resourceId") or value.get("resource_id") or ""
    )


class _ProjectFileTransaction:
    """Snapshot exact project targets and restore them when a write fails."""

    def __init__(self, root: Path, targets: Iterable[str]):
        self.root = root.resolve()
        self.targets = self._safe_targets(targets)
        self._temporary: Optional[tempfile.TemporaryDirectory[str]] = None
        self._snapshots: List[Tuple[Path, str, Optional[Path], Optional[int]]] = []
        self._missing_parents: Set[Path] = set()

    def _safe_targets(self, targets: Iterable[str]) -> List[Path]:
        result: List[Path] = []
        seen: Set[Path] = set()
        for raw in targets:
            relative = Path(str(raw))
            if not str(raw) or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Sync target must be a project-relative path.")
            path = self.root.joinpath(relative)
            # ``absolute`` does not follow a target symlink.  Existing parent
            # symlinks are rejected to keep rollback and deletion in-project.
            cursor = self.root
            for part in relative.parts[:-1]:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError("Sync target cannot traverse a symlinked directory.")
            if path in seen:
                continue
            seen.add(path)
            result.append(path)
        return result

    def __enter__(self) -> "_ProjectFileTransaction":
        self._temporary = tempfile.TemporaryDirectory(prefix="workflow-studio-sync-")
        backup_root = Path(self._temporary.name)
        for index, path in enumerate(self.targets):
            cursor = path.parent
            while cursor != self.root and cursor not in self._missing_parents:
                if cursor.exists() or cursor.is_symlink():
                    break
                self._missing_parents.add(cursor)
                cursor = cursor.parent
            mode: Optional[int] = None
            try:
                mode = stat.S_IMODE(path.lstat().st_mode)
            except OSError:
                pass
            if path.is_symlink():
                backup = backup_root / str(index)
                backup.symlink_to(os.readlink(path))
                self._snapshots.append((path, "symlink", backup, mode))
            elif path.is_dir():
                backup = backup_root / str(index)
                shutil.copytree(path, backup, symlinks=True)
                self._snapshots.append((path, "directory", backup, mode))
            elif path.exists():
                backup = backup_root / str(index)
                shutil.copy2(path, backup, follow_symlinks=False)
                self._snapshots.append((path, "file", backup, mode))
            else:
                self._snapshots.append((path, "missing", None, None))
        return self

    @staticmethod
    def _remove(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)

    def _restore(self) -> None:
        for path, kind, backup, mode in reversed(self._snapshots):
            self._remove(path)
            if kind == "missing":
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if kind == "directory":
                shutil.copytree(backup, path, symlinks=True)  # type: ignore[arg-type]
            elif kind == "symlink":
                path.symlink_to(os.readlink(backup))  # type: ignore[arg-type]
            else:
                shutil.copy2(backup, path, follow_symlinks=False)  # type: ignore[arg-type]
            if mode is not None and not path.is_symlink():
                os.chmod(path, mode)
        for directory in sorted(self._missing_parents, key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass

    def __exit__(self, exc_type: Any, _exc: Any, _traceback: Any) -> bool:
        try:
            if exc_type is not None:
                self._restore()
        finally:
            if self._temporary is not None:
                self._temporary.cleanup()
        return False


class StudioService:
    def __init__(self, state: StudioState):
        self.state = state

    @staticmethod
    def resource_response(resource: Mapping[str, Any]) -> Dict[str, Any]:
        payload = copy.deepcopy(resource.get("payload") or {})
        metadata = summary(resource)
        metadata["studioUpdatedAt"] = metadata.pop("updatedAt", None)
        response = {
            **payload,
            **metadata,
            "resourceStatus": metadata["status"],
            "revision": metadata["studioRevision"],
            "baselineHash": metadata["baseHash"],
        }
        kind = str(metadata.get("kind") or "")
        resource_id = str(metadata.get("id") or "")
        if kind in {"agent", "workflow"} and resource_id:
            response["codexInvocation"] = generated_skill_invocation(
                kind, resource_id
            )
        return response

    @staticmethod
    def sync_result_metadata(resource: Mapping[str, Any]) -> Dict[str, Any]:
        metadata = summary(resource)
        return {
            "resourceStatus": metadata["status"],
            "studioRevision": metadata["studioRevision"],
            "baselineHash": metadata["baselineHash"],
            "conflicts": metadata["conflicts"],
            "syncIntent": metadata["syncIntent"],
        }

    def require_authorized(self, project_id: str) -> None:
        if not self.state.is_authorized(project_id):
            raise StudioStateError(
                "Project details have not been authorized. Use ‘Authorize and import project’ first."
            )

    @staticmethod
    def _agent_manifest(store: Any, payload: Mapping[str, Any]) -> List[str]:
        agent_id = str(payload.get("id") or "")
        entrypoint = str(payload.get("entrypoint") or "")
        result = []
        if entrypoint:
            result.append(entrypoint)
        config = f".workflow-studio/agents/{agent_id}.json"
        if (store.root / config).exists():
            result.append(config)
        for relative in generated_skill_paths("agent", agent_id):
            if (store.root / relative).exists():
                result.append(relative)
        if store.agents_file.exists():
            try:
                agents_index = store.agents_file.read_text(encoding="utf-8")
            except OSError:
                agents_index = ""
            if managed_section_mentions_invocation(
                agents_index, generated_skill_invocation("agent", agent_id)
            ):
                result.append("AGENTS.md")
        return list(dict.fromkeys(result))

    @staticmethod
    def _skill_manifest(store: Any, payload: Mapping[str, Any]) -> List[str]:
        path = str(payload.get("path") or "")
        result = [path] if path else []
        if path:
            metadata = Path(path).parent / "agents" / "openai.yaml"
            if (store.root / metadata).exists():
                result.append(metadata.as_posix())
        return result

    @staticmethod
    def _workflow_manifest(store: Any, workflow_id: str) -> List[str]:
        skill_files = generated_skill_paths("workflow", workflow_id)
        candidates = [
            f".codex/workflows/{workflow_id}.json",
            *skill_files,
        ]
        result = [path for path in candidates if (store.root / path).exists()]
        if store.agents_file.exists():
            try:
                agents_index = store.agents_file.read_text(encoding="utf-8")
            except OSError:
                agents_index = ""
            if managed_section_mentions_invocation(
                agents_index, generated_skill_invocation("workflow", workflow_id)
            ):
                result.append("AGENTS.md")
        return result

    @staticmethod
    def _new_agent_entrypoint(resource_id: str) -> str:
        """Choose a path whose discovery id is exactly *resource_id*."""

        if resource_id.startswith("agents-") and resource_id != "agents-":
            return f"agents/{resource_id[len('agents-'):]}/AGENT.md"
        return f"{resource_id}/AGENT.md"

    def import_project(
        self, project_id: str, project: Mapping[str, Any], store: Any
    ) -> Dict[str, Any]:
        """Authorize and read a complete Codex snapshot without writing it."""

        self.state.authorize_project(
            project_id, project.get("path") or store.root, str(project.get("title") or "")
        )
        imported: Dict[str, List[Dict[str, Any]]] = {
            "agent": [],
            "skill": [],
            "action": [],
            "workflow": [],
        }
        for item in store.discover_agents():
            payload = store.get_agent(str(item["id"]))
            if isinstance(payload, dict):
                imported["agent"].append(
                    {
                        "resource_id": str(item["id"]),
                        "payload": payload,
                        "source_locator": {
                            "path": payload.get("path"),
                            "entrypoint": payload.get("entrypoint"),
                        },
                        "synced_manifest": self._agent_manifest(store, payload),
                    }
                )
        for item in store.discover_skills():
            payload = store.get_skill(str(item["id"]))
            if isinstance(payload, dict):
                imported["skill"].append(
                    {
                        "resource_id": str(item["id"]),
                        "payload": payload,
                        "source_locator": {"path": payload.get("path")},
                        "synced_manifest": self._skill_manifest(store, payload),
                    }
                )
        for item in store.discover_actions():
            payload = store.get_action(str(item["id"]))
            if isinstance(payload, dict):
                path = str(item.get("path") or f".workflow-studio/actions/{item['id']}.json")
                imported["action"].append(
                    {
                        "resource_id": str(item["id"]),
                        "payload": payload,
                        "source_locator": {"path": path},
                        "synced_manifest": [path],
                    }
                )
        for item in store.list_workflows():
            workflow_id = str(item["id"])
            payload = store.get_workflow(workflow_id)
            if isinstance(payload, dict):
                imported["workflow"].append(
                    {
                        "resource_id": workflow_id,
                        "payload": payload,
                        "source_locator": {"path": f".codex/workflows/{workflow_id}.json"},
                        "synced_manifest": self._workflow_manifest(store, workflow_id),
                    }
                )
        outcome = self.state.import_resources(project_id, imported)
        return {
            "project": {
                "id": project_id,
                "name": str(project.get("title") or store.root.name),
                "root": str(project.get("path") or store.root),
                "authorized": True,
            },
            "importedAt": outcome["imported_at"],
            "counts": outcome["counts"],
            **{
                kind + "s": [
                    self.resource_response(resource)
                    for resource in self.state.list_resources(project_id, kind)
                ]
                for kind in ("agent", "action", "skill", "workflow")
            },
        }

    def refresh_codex_baseline(self, project_id: str, store: Any) -> Dict[str, Any]:
        """Force a fresh read-only scan before previewing or writing Codex.

        The automatic UI refresh is intentionally throttled, but an explicit
        sync must never rely on that cache: Codex files may have changed after
        the last preview.  Re-importing here turns those changes into a merge
        or conflict before any project writer is called.
        """

        project = self.state.get_project(project_id)
        if project is None or not project.get("authorized"):
            self.require_authorized(project_id)
            raise StudioStateError("Authorized project metadata is unavailable.")
        return self.import_project(
            project_id,
            {
                "id": project_id,
                "title": project.get("name") or store.root.name,
                "path": project.get("root_path") or store.root,
            },
            store,
        )

    def list(self, project_id: str, kind: str) -> List[Dict[str, Any]]:
        self.require_authorized(project_id)
        return [
            self.resource_response(resource)
            for resource in self.state.list_resources(project_id, kind)
        ]

    def get(self, project_id: str, kind: str, resource_id: str) -> Optional[Dict[str, Any]]:
        self.require_authorized(project_id)
        resource = self.state.get_resource(project_id, kind, resource_id)
        return self.resource_response(resource) if resource else None

    def save_draft(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        payload: Mapping[str, Any],
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.require_authorized(project_id)
        clean = copy.deepcopy(dict(payload))
        for metadata_key in (
            "projectId",
            "kind",
            "status",
            "resourceStatus",
            "studioRevision",
            "revision",
            "baselineHash",
            "baseHash",
            "conflicts",
            "sourceLocator",
            "syncedManifest",
            "syncIntent",
            "syncError",
            "codexInvocation",
            "testStatus",
            "testRevision",
            "testJobId",
            "testSummary",
            "testResult",
            "createdAt",
            "studioUpdatedAt",
            "publishedAt",
            "syncedAt",
        ):
            clean.pop(metadata_key, None)
        clean["id"] = resource_id
        resource = self.state.save_draft(
            project_id,
            kind,
            resource_id,
            clean,
            expected_revision=expected_revision,
        )
        return self.resource_response(resource)

    def _resource_maps(self, project_id: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        agents = {
            resource["resource_id"]: resource["payload"]
            for resource in self.state.list_resources(project_id, "agent")
            if resource["status"] != "pending_delete"
        }
        actions = {
            resource["resource_id"]: resource["payload"]
            for resource in self.state.list_resources(project_id, "action")
            if resource["status"] != "pending_delete"
        }
        return agents, actions

    def test_workflow(
        self, project_id: str, workflow_id: str, store: Any
    ) -> Dict[str, Any]:
        resource = self.state.get_resource(project_id, "workflow", workflow_id)
        if resource is None:
            raise ResourceNotFoundError("Studio 中没有这个 Workflow。")
        agents, actions = self._resource_maps(project_id)
        result = dry_run_workflow(
            resource["payload"], agents, actions, runtime_check=store._action_runtime_binding
        )
        status = "passed" if result["valid"] else "failed"
        result["testedRevision"] = resource["studio_revision"]
        result["workflowId"] = workflow_id
        if hasattr(self.state, "record_resource_test"):
            self.state.record_resource_test(
                project_id,
                "workflow",
                workflow_id,
                resource["studio_revision"],
                status,
                json.dumps(
                    {"errors": result["errors"], "warnings": result["warnings"]},
                    ensure_ascii=False,
                ),
                result={
                    "payloadHash": canonical_hash(resource["payload"]),
                    "errors": result["errors"],
                    "warnings": result["warnings"],
                    "layers": result.get("layers", []),
                    "handoffs": result.get("handoffs", result.get("handoffPlan", [])),
                },
            )
        return result

    def _validate_publish(
        self, project_id: str, resource: Dict[str, Any], store: Any
    ) -> Dict[str, Any]:
        kind = resource["kind"]
        payload = resource["payload"]
        resource_id = resource["resource_id"]
        if resource["base_hash"] is None and _slugify(resource_id, "resource") != resource_id:
            raise ValueError(
                "New Studio resource ids must already be path-safe canonical ids."
            )
        if kind == "action":
            clean = store._normalize_action({**payload, "id": resource_id}, resource_id)
            if clean != payload:
                resource = self.state.save_draft(
                    project_id,
                    kind,
                    resource_id,
                    clean,
                    expected_revision=resource["studio_revision"],
                )
        elif kind == "skill":
            if not str(payload.get("name") or "").strip():
                raise ValueError("请填写 Skill 名称。")
            if not str(payload.get("description") or "").strip() or not str(
                payload.get("instructions") or ""
            ).strip():
                raise ValueError("请填写 Skill 描述和指令。")
            clean = {
                **payload,
                "id": resource_id,
                "name": _slugify(str(payload.get("name") or ""), "skill"),
                "description": " ".join(str(payload.get("description") or "").split()),
                "instructions": str(payload.get("instructions") or "").strip(),
            }
            if resource["base_hash"] is None:
                path = str(
                    clean.get("path")
                    or f".agents/skills/{clean['name']}/SKILL.md"
                )
                skill_id = _slugify(
                    Path(path).parent.as_posix().replace("/", "-"), "skill"
                )
                if skill_id != resource_id:
                    raise ValueError(
                        "New Skill id must match its project .agents/skills path."
                    )
                clean["path"] = path
            if clean != payload:
                resource = self.state.save_draft(
                    project_id,
                    kind,
                    resource_id,
                    clean,
                    expected_revision=resource["studio_revision"],
                )
        elif kind == "agent":
            if not str(payload.get("name") or "").strip() or not str(
                payload.get("description") or ""
            ).strip():
                raise ValueError("请填写 Agent 名称和描述。")
            allowed = payload.get("allowedActions", [])
            skills = payload.get("skills", [])
            if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
                raise ValueError("Agent allowedActions must be an array of Action ids.")
            if not isinstance(skills, list) or not all(isinstance(item, str) for item in skills):
                raise ValueError("Agent 的 skills 必须是数组。")
            if resource["base_hash"] is None:
                entrypoint = self._new_agent_entrypoint(resource_id)
                clean = {
                    **payload,
                    "id": resource_id,
                    "path": Path(entrypoint).parent.as_posix(),
                    "entrypoint": entrypoint,
                    "format": "AGENT.md",
                }
                if clean != payload:
                    resource = self.state.save_draft(
                        project_id,
                        kind,
                        resource_id,
                        clean,
                        expected_revision=resource["studio_revision"],
                    )
        elif kind == "workflow":
            clean = {**payload, "id": resource_id, "schemaVersion": 1}
            if clean != payload:
                resource = self.state.save_draft(
                    project_id,
                    kind,
                    resource_id,
                    clean,
                    expected_revision=resource["studio_revision"],
                )
            check = self.test_workflow(project_id, resource_id, store)
            if not check["valid"]:
                raise ValueError("\n".join(check["errors"]))
        return resource

    def publish(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        store: Any,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        resource = self.state.get_resource(project_id, kind, resource_id)
        if resource is None:
            raise ResourceNotFoundError("Studio 中没有这个资源。")
        if (
            expected_revision is not None
            and resource["studio_revision"] != expected_revision
        ):
            raise RevisionConflictError(
                expected_revision, resource["studio_revision"]
            )
        resource = self._validate_publish(project_id, resource, store)
        published = self.state.publish(
            project_id,
            kind,
            resource_id,
            expected_revision=resource["studio_revision"],
        )
        return self.resource_response(published)

    def stage_delete(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.resource_response(
            self.state.stage_delete(
                project_id,
                kind,
                resource_id,
                expected_revision=expected_revision,
            )
        )

    def resolve_conflict(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        resolutions: Any,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.resource_response(
            self.state.resolve_conflict(
                project_id,
                kind,
                resource_id,
                resolutions,
                expected_revision=expected_revision,
            )
        )

    def _skill_lookup(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for resource in self.state.list_resources(project_id, "skill"):
            result[resource["resource_id"]] = resource
            name = str(resource["payload"].get("name") or "")
            if name:
                result.setdefault(name, resource)
        return result

    def dependencies(self, project_id: str, resource: Mapping[str, Any]) -> List[Tuple[str, str]]:
        kind = resource["kind"]
        payload = resource["payload"]
        dependencies: List[Tuple[str, str]] = []
        if kind == "agent":
            dependencies.extend(("action", str(item)) for item in payload.get("allowedActions", []) if item)
            skills = self._skill_lookup(project_id)
            for item in payload.get("skills", []):
                match = skills.get(str(item))
                dependencies.append(
                    ("skill", match["resource_id"] if match is not None else str(item))
                )
        elif kind == "workflow":
            for node in payload.get("nodes", []) if isinstance(payload.get("nodes", []), list) else []:
                if not isinstance(node, dict):
                    continue
                if str(node.get("type") or "agent") == "action":
                    action_id = str(node.get("actionId") or "")
                    agent_id = str(node.get("agentId") or "")
                    if action_id:
                        dependencies.append(("action", action_id))
                    if agent_id:
                        dependencies.append(("agent", agent_id))
                else:
                    agent_id = str(node.get("agentId") or "")
                    if agent_id:
                        dependencies.append(("agent", agent_id))
        return list(dict.fromkeys(dependencies))

    def target_files(self, resource: Mapping[str, Any], store: Any = None) -> List[str]:
        manifest = [
            str(item) for item in resource.get("synced_manifest", []) if item
        ]
        deleting = (
            resource.get("sync_intent") == "delete"
            or resource.get("status") == "pending_delete"
        )
        # Optional sync targets (Claude Code, Qwen Code) add mirrored skills and
        # their instruction files; they are part of the snapshot and preview.
        extra = (
            list(store.target_files_for(str(resource["kind"]), str(resource["resource_id"])))
            if store is not None and hasattr(store, "target_files_for")
            else []
        )
        if deleting and extra:
            mirrors = [path for path in extra if Path(path).name == "SKILL.md"]
            return list(dict.fromkeys(manifest + mirrors))
        # Deletes are intentionally limited to the exact paths recorded by a
        # successful prior import/sync.  Upserts also include every file the
        # writer can create so a failure can roll back newly generated sidecar
        # files as well as files that already existed at import time.
        if deleting:
            return list(dict.fromkeys(manifest))
        kind = str(resource["kind"])
        resource_id = str(resource["resource_id"])
        payload = resource["payload"]
        if kind == "action":
            expected = [f".workflow-studio/actions/{resource_id}.json"]
            return list(dict.fromkeys(manifest + expected))
        if kind == "workflow":
            generated_skill_files = generated_skill_paths("workflow", resource_id)
            expected = [
                f".codex/workflows/{resource_id}.json",
                *generated_skill_files,
                "AGENTS.md",
                *extra,
            ]
            return list(dict.fromkeys(manifest + expected))
        if kind == "skill":
            path = str(
                payload.get("path")
                or f".agents/skills/{_slugify(str(payload.get('name') or resource_id), 'skill')}/SKILL.md"
            )
            expected = [path, (Path(path).parent / "agents" / "openai.yaml").as_posix()]
            return list(dict.fromkeys(manifest + expected))
        folder = _slugify(str(payload.get("name") or resource_id), "agent")
        entrypoint = str(payload.get("entrypoint") or f"agents/{folder}/AGENT.md")
        generated_skill_files = generated_skill_paths("agent", resource_id)
        expected = [
            entrypoint,
            f".workflow-studio/agents/{resource_id}.json",
            *generated_skill_files,
            "AGENTS.md",
            *extra,
        ]
        return list(dict.fromkeys(manifest + expected))

    def _selected_resources(
        self, project_id: str, selected: Optional[Sequence[Mapping[str, Any]]]
    ) -> List[Dict[str, Any]]:
        resources = self.state.list_resources(project_id)
        if selected is not None:
            keys = {_resource_key(item) for item in selected}
            resources = [
                resource
                for resource in resources
                if (resource["kind"], resource["resource_id"]) in keys
            ]
        else:
            resources = [resource for resource in resources if resource["status"] in SYNCABLE_STATUSES]
        return sorted(
            resources,
            key=lambda item: (SYNC_ORDER[item["kind"]], item["kind"], item["resource_id"]),
        )

    def preview(
        self,
        project_id: str,
        selected: Optional[Sequence[Mapping[str, Any]]] = None,
        store: Any = None,
    ) -> Dict[str, Any]:
        self.require_authorized(project_id)
        resources = self._selected_resources(project_id, selected)
        all_resources = {
            (resource["kind"], resource["resource_id"]): resource
            for resource in self.state.list_resources(project_id)
        }
        available = {
            key for key, resource in all_resources.items() if resource["status"] == "synced"
        }
        selected_keys = {(item["kind"], item["resource_id"]) for item in resources}
        items: List[Dict[str, Any]] = []
        for resource in resources:
            key = (resource["kind"], resource["resource_id"])
            blocked: List[Dict[str, Any]] = []
            deleting = (
                resource["sync_intent"] == "delete"
                or resource["status"] == "pending_delete"
            )
            if resource["status"] not in SYNCABLE_STATUSES:
                blocked.append({"code": "not-ready", "message": "Publish this draft to Studio first."})
            resource_dependencies = [] if deleting else self.dependencies(project_id, resource)
            for dependency in resource_dependencies:
                target = all_resources.get(dependency)
                if target is None:
                    blocked.append(
                        {
                            "code": "missing-dependency",
                            "kind": dependency[0],
                            "id": dependency[1],
                            "message": f"Missing {dependency[0]} dependency '{dependency[1]}'.",
                        }
                    )
                elif dependency not in available:
                    blocked.append(
                        {
                            "code": (
                                "dependency-blocked"
                                if dependency in selected_keys
                                else "unsynced-dependency"
                            ),
                            "kind": dependency[0],
                            "id": dependency[1],
                            "status": target["status"],
                            "message": (
                                "The selected dependency is blocked earlier in this sync."
                                if dependency in selected_keys
                                else "Dependency has not been synced to Codex."
                            ),
                        }
                    )
            if not deleting and resource["kind"] == "agent" and (
                resource["test_status"] != "passed"
                or resource["test_revision"] != resource["studio_revision"]
            ):
                blocked.append(
                    {"code": "agent-test-required", "message": "当前 Agent 草稿必须先通过一键测试才能同步。"}
                )
            if not deleting and resource["kind"] == "workflow" and (
                resource["test_status"] != "passed"
                or resource["test_revision"] != resource["studio_revision"]
            ):
                blocked.append(
                    {"code": "workflow-test-required", "message": "The current Workflow draft must pass Dry-run."}
                )
            operation = (
                "delete"
                if resource["sync_intent"] == "delete" or resource["status"] == "pending_delete"
                else ("add" if resource["base_hash"] is None else "modify")
            )
            item = {
                **summary(resource),
                "operation": operation,
                "dependencies": [
                    {"kind": kind, "id": resource_id}
                    for kind, resource_id in resource_dependencies
                ],
                "targetFiles": self.target_files(resource, store),
                "blockedReasons": blocked,
                "blocked": bool(blocked),
            }
            items.append(item)
            if not blocked and operation != "delete":
                available.add(key)
        return {
            "projectId": project_id,
            "items": items,
            "order": [{"kind": item["kind"], "id": item["id"]} for item in items],
            "blocked": [item for item in items if item["blocked"]],
            "canSync": bool(items) and not any(item["blocked"] for item in items),
        }

    @staticmethod
    def _remove_target(root: Path, relative: str) -> None:
        path = root / relative
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)
        cursor = path.parent
        while cursor != root:
            try:
                cursor.rmdir()
            except OSError:
                break
            cursor = cursor.parent

    def _delete_resource(self, store: Any, resource: Mapping[str, Any]) -> List[str]:
        removed: List[str] = []
        targets = self.target_files(resource, store)
        for relative in targets:
            # Instruction files are shared; regenerate their managed sections after
            # the resource-specific files disappear instead of deleting them.
            if relative in {"AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md", "QWEN.md"}:
                continue
            path = store.root / relative
            if path.exists() or path.is_symlink():
                self._remove_target(store.root, relative)
                removed.append(relative)
        if resource["kind"] in {"agent", "workflow"} and "AGENTS.md" in targets:
            store._write_agents_index()
        return removed

    def _write_resource(self, store: Any, resource: Mapping[str, Any]) -> Dict[str, Any]:
        kind = resource["kind"]
        resource_id = resource["resource_id"]
        payload = copy.deepcopy(resource["payload"])
        if kind == "action":
            return store.save_action(resource_id, payload, allow_overwrite=True)
        if kind == "workflow":
            return store.save_workflow(resource_id, payload)
        if kind == "skill":
            if store.get_skill(resource_id) is not None:
                return store.save_skill(resource_id, payload)
            return store.publish_skill(payload, skill_id=resource_id)
        if store.get_agent(resource_id) is not None:
            return store.save_agent(resource_id, payload)
        return store.publish_agent(payload, agent_id=resource_id)

    def _fresh_gate(
        self, project_id: str, resource: Dict[str, Any], store: Any
    ) -> Optional[Dict[str, Any]]:
        if resource["sync_intent"] == "delete" or resource["status"] == "pending_delete":
            return None
        if resource["kind"] == "workflow":
            check = self.test_workflow(project_id, resource["resource_id"], store)
            if not check["valid"]:
                return {
                    "code": "workflow-test-failed",
                    "message": "Workflow Dry-run failed.",
                    "errors": check["errors"],
                }
            resource = self.state.get_resource(project_id, "workflow", resource["resource_id"])
        if resource["kind"] == "agent" and (
            resource["test_status"] != "passed"
            or resource["test_revision"] != resource["studio_revision"]
        ):
            return {"code": "agent-test-required", "message": "当前 Agent 草稿必须先通过一键测试才能同步。"}
        return None

    def _sync_resource(
        self,
        project_id: str,
        resource: Dict[str, Any],
        store: Any,
        *,
        confirm_delete: bool,
    ) -> Dict[str, Any]:
        revision = resource["studio_revision"]
        result_metadata = self.sync_result_metadata(resource)
        operation = (
            "delete"
            if resource["sync_intent"] == "delete" or resource["status"] == "pending_delete"
            else ("add" if resource["base_hash"] is None else "modify")
        )
        if operation == "delete" and not confirm_delete:
            return {
                "kind": resource["kind"],
                "id": resource["resource_id"],
                "status": "blocked",
                **result_metadata,
                "blockedReasons": [{"code": "delete-confirmation-required", "message": "Confirm deletion before syncing."}],
            }
        gate = self._fresh_gate(project_id, resource, store)
        if gate is not None:
            return {
                "kind": resource["kind"],
                "id": resource["resource_id"],
                "status": "blocked",
                **result_metadata,
                "blockedReasons": [gate],
            }
        targets = self.target_files(resource, store)
        try:
            with _ProjectFileTransaction(store.root, targets):
                if operation == "delete":
                    synced_files = self._delete_resource(store, resource)
                    updated = self.state.mark_synced(
                        project_id,
                        resource["kind"],
                        resource["resource_id"],
                        expected_revision=revision,
                        synced_manifest=[],
                        deleted=True,
                    )
                else:
                    result = self._write_resource(store, resource)
                    synced_files = list(result.get("syncedFiles") or targets)
                    updated = self.state.mark_synced(
                        project_id,
                        resource["kind"],
                        resource["resource_id"],
                        expected_revision=revision,
                        synced_manifest=synced_files,
                    )
        except Exception as error:
            failed = self.state.mark_sync_failed(
                project_id,
                resource["kind"],
                resource["resource_id"],
                str(error),
                expected_revision=revision,
            )
            return {
                "kind": resource["kind"],
                "id": resource["resource_id"],
                "status": "failed",
                **self.sync_result_metadata(failed),
                "error": str(error),
                "resource": self.resource_response(failed),
            }
        return {
            "kind": resource["kind"],
            "id": resource["resource_id"],
            "status": "succeeded",
            **self.sync_result_metadata(updated),
            "operation": operation,
            "syncedFiles": synced_files,
            "resource": self.resource_response(updated),
        }

    def sync(
        self,
        project_id: str,
        store: Any,
        *,
        selected: Optional[Sequence[Mapping[str, Any]]] = None,
        confirm_delete: bool = False,
    ) -> Dict[str, Any]:
        self.refresh_codex_baseline(project_id, store)
        expected_revisions: Dict[Tuple[str, str], int] = {}
        for item in selected or []:
            key = _resource_key(item)
            raw_revision = item.get("studioRevision", item.get("revision"))
            if key[0] and key[1] and raw_revision is not None and raw_revision != "":
                try:
                    expected_revisions[key] = int(raw_revision)
                except (TypeError, ValueError) as error:
                    raise ValueError("Selected sync revision must be an integer.") from error
        resources = self._selected_resources(project_id, selected)
        results: List[Dict[str, Any]] = []
        succeeded: Set[Tuple[str, str]] = set()
        for resource in resources:
            resource = self.state.get_resource(
                project_id, resource["kind"], resource["resource_id"]
            )
            if resource is None:
                continue
            blocked: List[Dict[str, Any]] = []
            expected_revision = expected_revisions.get(
                (resource["kind"], resource["resource_id"])
            )
            if (
                expected_revision is not None
                and resource["studio_revision"] != expected_revision
            ):
                blocked.append(
                    {
                        "code": "revision-changed",
                        "expectedRevision": expected_revision,
                        "currentRevision": resource["studio_revision"],
                        "message": "Resource changed after preview; generate a new sync preview.",
                    }
                )
            deleting = (
                resource["sync_intent"] == "delete"
                or resource["status"] == "pending_delete"
            )
            for dependency in ([] if deleting else self.dependencies(project_id, resource)):
                target = self.state.get_resource(project_id, dependency[0], dependency[1])
                if target is None:
                    # Skill references may use their published name.
                    if dependency[0] == "skill":
                        target = self._skill_lookup(project_id).get(dependency[1])
                if target is None:
                    blocked.append(
                        {"code": "missing-dependency", "kind": dependency[0], "id": dependency[1]}
                    )
                elif target["status"] != "synced" and dependency not in succeeded:
                    blocked.append(
                        {
                            "code": "unsynced-dependency",
                            "kind": dependency[0],
                            "id": dependency[1],
                            "status": target["status"],
                        }
                    )
            if resource["status"] not in SYNCABLE_STATUSES:
                blocked.append({"code": "not-ready"})
            if blocked:
                results.append(
                    {
                        "kind": resource["kind"],
                        "id": resource["resource_id"],
                        "status": "blocked",
                        **self.sync_result_metadata(resource),
                        "blockedReasons": blocked,
                    }
                )
                continue
            result = self._sync_resource(
                project_id,
                resource,
                store,
                confirm_delete=confirm_delete,
            )
            results.append(result)
            if result["status"] == "succeeded" and result.get("operation") != "delete":
                succeeded.add((resource["kind"], resource["resource_id"]))
        response = {
            "projectId": project_id,
            "results": results,
            "succeeded": [item for item in results if item["status"] == "succeeded"],
            "failed": [item for item in results if item["status"] == "failed"],
            "blocked": [item for item in results if item["status"] == "blocked"],
        }
        if len(results) == 1:
            single = results[0]
            response["status"] = single["status"]
            response["syncedFiles"] = single.get("syncedFiles", [])
            if isinstance(single.get("resource"), dict):
                response["resource"] = single["resource"]
                response[single["kind"]] = single["resource"]
            for key in (
                "resourceStatus",
                "studioRevision",
                "baselineHash",
                "conflicts",
                "syncIntent",
            ):
                if key in single:
                    response[key] = single[key]
        return response


__all__ = ["SYNCABLE_STATUSES", "StudioService"]
