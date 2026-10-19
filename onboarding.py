"""First-run A2A tutorial state and isolated project management."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from studio_service import StudioService
from studio_state import StudioState, StudioStateError


TUTORIAL_PROJECT_ID = "workflow-studio-tutorial"
TUTORIAL_PROJECT_NAME = "Workflow Studio A2A Tutorial"
TUTORIAL_MARKER = ".workflow-studio-tutorial.json"
REQUIREMENTS_AGENT_ID = "requirements-clarifier"
REVIEW_AGENT_ID = "plan-reviewer"
TUTORIAL_WORKFLOW_ID = "a2a-requirement-review"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hash_payload(value: Mapping[str, Any]) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TutorialManager:
    """Own the generated tutorial project without broadening normal project access."""

    def __init__(self, state: StudioState, studio: StudioService, version: str):
        self.state = state
        self.studio = studio
        self.version = version
        self.base_dir = (state.path.parent / "tutorial-projects").absolute()
        self.project_root = (self.base_dir / "a2a-workflow").absolute()

    @staticmethod
    def handoff_condition(language: str) -> str:
        if language == "en":
            return "Requirements, scope, constraints, and acceptance criteria are complete."
        return "需求、范围、约束和验收标准已整理完成"

    @staticmethod
    def sample_task(language: str) -> str:
        if language == "en":
            return (
                "Add CSV export to an existing Python CLI while keeping JSON as the default. "
                "Invalid output paths must return a non-zero exit code."
            )
        return "为现有 Python CLI 增加 CSV 导出，同时保持 JSON 为默认格式；无效输出路径必须返回非零退出码。"

    @classmethod
    def _agent_templates(cls, language: str) -> Dict[str, Dict[str, Any]]:
        if language == "en":
            return {
                REQUIREMENTS_AGENT_ID: {
                    "id": REQUIREMENTS_AGENT_ID,
                    "name": "Requirements Clarifier",
                    "description": "Turns a software request into explicit, testable requirements.",
                    "model": "inherit",
                    "instructions": (
                        "Read the supplied feature request. Do not implement it. Return exactly these "
                        "sections: Goal, In scope, Out of scope, Constraints, Assumptions, and Acceptance "
                        "criteria. When information is missing, state the smallest reasonable assumption."
                    ),
                    "allowedActions": [],
                    "legacyActions": [],
                    "skills": [],
                    "tools": [],
                    "actionCount": 0,
                    "skillCount": 0,
                    "path": "requirements-clarifier",
                    "entrypoint": "requirements-clarifier/AGENT.md",
                    "format": "AGENT.md",
                },
                REVIEW_AGENT_ID: {
                    "id": REVIEW_AGENT_ID,
                    "name": "Plan Reviewer",
                    "description": "Reviews clarified requirements for gaps, risks, and testability.",
                    "model": "inherit",
                    "instructions": (
                        "Review the supplied requirements package without implementing it. Return exactly "
                        "these sections: Verdict, Gaps, Risks, Required changes, and Final acceptance "
                        "checklist. Flag contradictions and requirements that cannot be tested."
                    ),
                    "allowedActions": [],
                    "legacyActions": [],
                    "skills": [],
                    "tools": [],
                    "actionCount": 0,
                    "skillCount": 0,
                    "path": "plan-reviewer",
                    "entrypoint": "plan-reviewer/AGENT.md",
                    "format": "AGENT.md",
                },
            }
        return {
            REQUIREMENTS_AGENT_ID: {
                "id": REQUIREMENTS_AGENT_ID,
                "name": "需求澄清员",
                "description": "把软件需求整理为明确、可测试的需求包。",
                "model": "inherit",
                "instructions": (
                    "阅读用户提供的功能需求，不要实现代码。严格按以下标题输出：目标、范围内、范围外、"
                    "约束、假设、验收标准。信息不足时，只做最小且明确的合理假设。"
                ),
                "allowedActions": [],
                "legacyActions": [],
                "skills": [],
                "tools": [],
                "actionCount": 0,
                "skillCount": 0,
                "path": "requirements-clarifier",
                "entrypoint": "requirements-clarifier/AGENT.md",
                "format": "AGENT.md",
            },
            REVIEW_AGENT_ID: {
                "id": REVIEW_AGENT_ID,
                "name": "方案审校员",
                "description": "审查需求包的缺口、风险与可测试性。",
                "model": "inherit",
                "instructions": (
                    "审查输入的需求包，不要实现代码。严格按以下标题输出：结论、缺口、风险、必须修改项、"
                    "最终验收清单。指出矛盾以及无法测试的表述。"
                ),
                "allowedActions": [],
                "legacyActions": [],
                "skills": [],
                "tools": [],
                "actionCount": 0,
                "skillCount": 0,
                "path": "plan-reviewer",
                "entrypoint": "plan-reviewer/AGENT.md",
                "format": "AGENT.md",
            },
        }

    @classmethod
    def _workflow_template(cls, language: str) -> Dict[str, Any]:
        return {
            "id": TUTORIAL_WORKFLOW_ID,
            "name": "A2A Requirements Review" if language == "en" else "A2A 需求审校工作流",
            "description": (
                "Clarify a software request, then review it for completeness."
                if language == "en"
                else "先澄清软件需求，再审校完整性与可测试性。"
            ),
            "schemaVersion": 1,
            "nodes": [],
            "edges": [],
            "updatedAt": _now(),
        }

    def _marker_payload(self, session: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "schemaVersion": 1,
            "projectId": TUTORIAL_PROJECT_ID,
            "sessionId": session["session_id"],
            "markerToken": session["marker_token"],
            "createdBy": "Workflow Studio",
            "version": self.version,
        }

    def _write_marker(self, session: Mapping[str, Any]) -> None:
        if self.base_dir.is_symlink() or self.project_root.is_symlink():
            raise PermissionError("Tutorial project path cannot traverse a symbolic link.")
        self.project_root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)
            os.chmod(self.project_root, 0o700)
        except OSError:
            pass
        marker = self.project_root / TUTORIAL_MARKER
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._marker_payload(session), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, marker)
        try:
            os.chmod(marker, 0o600)
        except OSError:
            pass

    def _validate_marker(self, session: Mapping[str, Any]) -> Path:
        root = Path(str(session.get("root_path") or ""))
        if self.base_dir.is_symlink() or root.is_symlink():
            raise PermissionError("Tutorial project path cannot traverse a symbolic link.")
        expected = self.project_root.resolve(strict=False)
        actual = root.resolve(strict=False)
        if actual != expected:
            raise PermissionError("Tutorial project path does not match the managed location.")
        marker = actual / TUTORIAL_MARKER
        if marker.is_symlink() or not marker.is_file():
            raise PermissionError("Tutorial project marker is missing or unsafe.")
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PermissionError("Tutorial project marker is invalid.") from error
        if (
            payload.get("projectId") != TUTORIAL_PROJECT_ID
            or payload.get("sessionId") != session.get("session_id")
            or payload.get("markerToken") != session.get("marker_token")
        ):
            raise PermissionError("Tutorial project marker does not match this session.")
        return actual

    def project(self) -> Optional[Dict[str, Any]]:
        session = self.state.get_tutorial_session()
        if session is None:
            return None
        root = Path(session["root_path"])
        return {
            "id": TUTORIAL_PROJECT_ID,
            "title": TUTORIAL_PROJECT_NAME,
            "path": str(root),
            "active": False,
            "available": root.is_dir(),
            "tutorial": True,
            "managedByStudio": True,
        }

    def select(self, project_id: str) -> Optional[Dict[str, Any]]:
        if project_id != TUTORIAL_PROJECT_ID:
            return None
        project = self.project()
        if project is None or not project["available"]:
            raise ValueError("教程项目不可用。")
        return project

    def dismiss_invitation(self) -> Dict[str, Any]:
        if self.state.get_setting("onboarding.invitation") == "pending":
            self.state.set_setting("onboarding.invitation", "dismissed")
        return self.status()

    def start(self, language: str = "zh") -> Dict[str, Any]:
        language = "en" if language == "en" else "zh"
        current = self.state.get_tutorial_session()
        if current is not None:
            self._validate_marker(current)
            return self.status()
        if self.project_root.exists():
            raise FileExistsError(
                "Tutorial directory already exists without a matching Studio session."
            )
        session = self.state.save_tutorial_session(
            {
                "session_id": uuid.uuid4().hex,
                "project_id": TUTORIAL_PROJECT_ID,
                "root_path": str(self.project_root),
                "marker_token": uuid.uuid4().hex,
                "language": language,
                "status": "in_progress",
                "step_id": "connection",
                "data": {
                    "sampleTask": self.sample_task(language),
                    "handoffCondition": self.handoff_condition(language),
                },
            }
        )
        self._write_marker(session)
        self.state.set_setting("onboarding.invitation", "dismissed")
        return self.status()

    def seed_after_import(self, project_id: str) -> None:
        if project_id != TUTORIAL_PROJECT_ID:
            return
        session = self.state.get_tutorial_session(project_id)
        if session is None:
            raise StudioStateError("找不到教程进度。")
        self._validate_marker(session)
        language = session["language"]
        for resource_id, payload in self._agent_templates(language).items():
            if self.state.get_resource(project_id, "agent", resource_id) is None:
                self.studio.save_draft(project_id, "agent", resource_id, payload)
        if self.state.get_resource(project_id, "workflow", TUTORIAL_WORKFLOW_ID) is None:
            self.studio.save_draft(
                project_id,
                "workflow",
                TUTORIAL_WORKFLOW_ID,
                self._workflow_template(language),
            )

    def _derive_step(self, session: Mapping[str, Any], connection_ready: bool) -> str:
        if not connection_ready:
            return "connection"
        if not self.state.is_authorized(TUTORIAL_PROJECT_ID):
            return "authorize-import"
        resources: Dict[tuple[str, str], Dict[str, Any]] = {}
        for kind in ("agent", "workflow"):
            for resource in self.state.list_resources(TUTORIAL_PROJECT_ID, kind):
                resources[(kind, resource["resource_id"])] = resource
        requirements = resources.get(("agent", REQUIREMENTS_AGENT_ID))
        reviewer = resources.get(("agent", REVIEW_AGENT_ID))
        workflow = resources.get(("workflow", TUTORIAL_WORKFLOW_ID))
        if requirements is None or reviewer is None or workflow is None:
            return "authorize-import"
        if requirements["test_status"] != "passed":
            return "test-requirements"
        if requirements["status"] not in {"ready", "synced"}:
            return "publish-requirements"
        if reviewer["test_status"] != "passed":
            return "test-reviewer"
        if reviewer["status"] not in {"ready", "synced"}:
            return "publish-reviewer"
        payload = workflow["payload"]
        nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
        node_ids = {
            str(node.get("agentId") or "")
            for node in nodes
            if isinstance(node, Mapping) and str(node.get("type") or "agent") == "agent"
        }
        if not {REQUIREMENTS_AGENT_ID, REVIEW_AGENT_ID}.issubset(node_ids):
            return "add-agents"
        node_by_agent = {
            str(node.get("agentId") or ""): str(node.get("id") or "")
            for node in nodes
            if isinstance(node, Mapping)
        }
        edges = payload.get("edges") if isinstance(payload.get("edges"), list) else []
        expected_source = node_by_agent.get(REQUIREMENTS_AGENT_ID)
        expected_target = node_by_agent.get(REVIEW_AGENT_ID)
        handoff = next(
            (
                edge
                for edge in edges
                if isinstance(edge, Mapping)
                and str(edge.get("source") or "") == expected_source
                and str(edge.get("target") or "") == expected_target
            ),
            None,
        )
        if handoff is None:
            return "connect-agents"
        if str(handoff.get("condition") or "").strip() != str(
            session.get("data", {}).get("handoffCondition") or ""
        ):
            return "handoff-condition"
        tested_hash = str((workflow.get("test_result") or {}).get("payloadHash") or "")
        if workflow["test_status"] != "passed" or tested_hash != _hash_payload(payload):
            return "test-workflow"
        if workflow["status"] not in {"ready", "synced"}:
            return "publish-workflow"
        if any(resource["status"] != "synced" for resource in (requirements, reviewer, workflow)):
            return "batch-sync"
        return "completed"

    def status(self, *, connection_ready: bool = False) -> Dict[str, Any]:
        session = self.state.get_tutorial_session()
        invitation = str(self.state.get_setting("onboarding.invitation", "dismissed"))
        if session is None:
            return {
                "invitation": invitation,
                "status": "not_started",
                "stepId": "invitation",
                "canResume": False,
                "project": None,
            }
        try:
            self._validate_marker(session)
            marker_valid = True
        except PermissionError:
            marker_valid = False
        completion_recorded = bool(session.get("completed_at")) and bool(
            self.state.get_setting("onboarding.completed", False)
        )
        if marker_valid and (
            session.get("status") == "completed" or completion_recorded
        ):
            # Completion is a durable milestone. Keeping the practice project
            # means the user may edit it later; those edits must not reopen the
            # tutorial or revoke an already-earned completion.
            step = "completed"
        else:
            step = (
                self._derive_step(session, connection_ready)
                if marker_valid
                else "repair-required"
            )
        status = "completed" if step == "completed" else "in_progress"
        if step != session["step_id"] or status != session["status"]:
            session = self.state.save_tutorial_session(
                {
                    **session,
                    "step_id": step,
                    "status": status,
                    "completed_at": (
                        session.get("completed_at") or _now()
                        if status == "completed"
                        else None
                    ),
                }
            )
        if status == "completed":
            self.state.set_setting("onboarding.invitation", "completed")
            self.state.set_setting("onboarding.completed", True)
        milestones: Dict[str, Any] = {}
        failure: Optional[Dict[str, Any]] = None
        if self.state.is_authorized(TUTORIAL_PROJECT_ID):
            for kind, resource_id in (
                ("agent", REQUIREMENTS_AGENT_ID),
                ("agent", REVIEW_AGENT_ID),
                ("workflow", TUTORIAL_WORKFLOW_ID),
            ):
                resource = self.state.get_resource(
                    TUTORIAL_PROJECT_ID, kind, resource_id
                )
                if resource is None:
                    continue
                milestones[resource_id] = {
                    "status": resource["status"],
                    "testStatus": resource["test_status"],
                    "testSummary": resource.get("test_summary") or "",
                    "syncError": resource.get("sync_error") or "",
                }
                if step in {"test-requirements", "test-reviewer", "test-workflow"} and (
                    (resource_id == REQUIREMENTS_AGENT_ID and step == "test-requirements")
                    or (resource_id == REVIEW_AGENT_ID and step == "test-reviewer")
                    or (resource_id == TUTORIAL_WORKFLOW_ID and step == "test-workflow")
                ) and resource["test_status"] in {"failed", "interrupted"}:
                    failure = {
                        "kind": "test",
                        "resourceId": resource_id,
                        "message": resource.get("test_summary")
                        or "The tutorial test did not pass. Review the result and retry manually.",
                    }
                if step == "batch-sync" and resource["status"] == "sync_failed":
                    failure = {
                        "kind": "sync",
                        "resourceId": resource_id,
                        "message": resource.get("sync_error")
                        or "This tutorial resource did not sync. Preview and retry manually.",
                    }
        response = {
            "invitation": invitation if status != "completed" else "completed",
            "status": status,
            "stepId": step,
            "canResume": status == "in_progress",
            "sessionId": session["session_id"],
            "language": session["language"],
            "sampleTask": session["data"].get("sampleTask"),
            "handoffCondition": session["data"].get("handoffCondition"),
            "project": {
                "id": TUTORIAL_PROJECT_ID,
                "title": TUTORIAL_PROJECT_NAME,
                "authorized": self.state.is_authorized(TUTORIAL_PROJECT_ID),
                "tutorial": True,
                "managedByStudio": True,
            },
            "completedAt": session.get("completed_at"),
            "markerValid": marker_valid,
            "milestones": milestones,
        }
        if failure is not None:
            response["failure"] = failure
        return response

    def restart(self, language: str = "zh") -> Dict[str, Any]:
        session = self.state.get_tutorial_session()
        if session is not None and self.state.is_authorized(TUTORIAL_PROJECT_ID):
            for kind in ("agent", "workflow"):
                if any(
                    resource.get("test_status") == "running"
                    for resource in self.state.list_resources(TUTORIAL_PROJECT_ID, kind)
                ):
                    raise StudioStateError("请等待正在运行的教程测试结束后再重新开始。")
        self.cleanup(preserve_completion=False)
        return self.start(language)

    def cleanup(self, *, preserve_completion: bool = True) -> Dict[str, Any]:
        session = self.state.get_tutorial_session()
        if session is None:
            return self.status()
        root = self._validate_marker(session)
        if root.exists():
            shutil.rmtree(root)
        self.state.delete_project_state(TUTORIAL_PROJECT_ID)
        self.state.delete_tutorial_session(TUTORIAL_PROJECT_ID)
        if preserve_completion:
            self.state.set_setting("onboarding.invitation", "completed")
            self.state.set_setting("onboarding.completed", True)
        else:
            self.state.set_setting("onboarding.invitation", "dismissed")
        return self.status()
