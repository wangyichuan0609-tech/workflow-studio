"""Persistent Studio-only state for Workflow Studio.

This module deliberately has no knowledge of Codex project writers.  Importing
records a read-only snapshot of Codex resources; only a caller that explicitly
performs a sync should call :meth:`StudioState.mark_synced` afterwards.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple


RESOURCE_KINDS = frozenset({"agent", "skill", "action", "workflow"})
RESOURCE_STATUSES = frozenset(
    {
        "synced",
        "draft",
        "ready",
        "conflict",
        "pending_delete",
        "source_missing",
        "sync_failed",
    }
)
TEST_STATUSES = frozenset({"untested", "running", "passed", "failed", "stale", "interrupted"})
JOB_STATUSES = frozenset(
    {"queued", "running", "passed", "failed", "timed_out", "cancelled", "interrupted"}
)
TERMINAL_JOB_STATUSES = frozenset(
    {"passed", "failed", "timed_out", "cancelled", "interrupted"}
)
_SENSITIVE_ACTION_FIELD_NAMES = frozenset(
    {
        "apikey",
        "accesskey",
        "password",
        "passwd",
        "secret",
        "clientsecret",
        "token",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "authorization",
        "credential",
        "credentials",
        "xapikey",
    }
)

_MISSING = object()
_UNSET = object()


class StudioStateError(RuntimeError):
    """Base error for Studio state operations."""


class ProjectNotAuthorizedError(StudioStateError):
    """Raised when project details are accessed before explicit authorization."""


class ResourceNotFoundError(StudioStateError):
    """Raised when a requested Studio resource does not exist."""


class RevisionConflictError(StudioStateError):
    """Raised when a write targets an obsolete Studio revision."""

    def __init__(self, expected_revision: int, current_revision: int):
        super().__init__(
            "Studio revision conflict: expected {}, current {}.".format(
                expected_revision, current_revision
            )
        )
        self.expected_revision = expected_revision
        self.current_revision = current_revision


def default_state_path() -> Path:
    """Return the platform-appropriate per-user Workflow Studio database path."""

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Workflow Studio" / "state.sqlite3"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return Path(base) / "Workflow Studio" / "state.sqlite3" if base else home / "AppData" / "Local" / "Workflow Studio" / "state.sqlite3"
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else home / ".local" / "state"
    return base / "workflow-studio" / "state.sqlite3"


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Studio state must be JSON serializable.") from exc


def _json_copy(value: Any) -> Any:
    return json.loads(_json_text(value))


def canonical_hash(value: Any) -> str:
    """Hash a JSON value independent of mapping insertion order."""

    return hashlib.sha256(_json_text(value).encode("utf-8")).hexdigest()


def reject_embedded_action_credentials(value: Any) -> None:
    """Reject credential values before an Action draft reaches SQLite.

    ``credentialRefs`` contains names only and is the sole credential-related
    field allowed in an Action definition.  AI drafts can contain the Action
    as a JSON string, so inspect a valid ``actionJson`` value as well while
    still allowing incomplete JSON to be autosaved as an editor draft.
    """

    def reject_key(key: Any) -> None:
        normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if normalized_key in _SENSITIVE_ACTION_FIELD_NAMES:
            raise ValueError(
                "Action cannot store credential field '{}'; use credentialRefs instead.".format(
                    key
                )
            )

    def inspect(candidate: Any, *, action_json: bool = False) -> None:
        if action_json and isinstance(candidate, str) and candidate.strip():
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                # Preserve incomplete editor JSON, but never persist a secret
                # merely because the closing quote/bracket has not been typed.
                key_pattern = re.compile(
                    r'(?:^|[,{]\s*)(?:"((?:\\.|[^"\\])*)"|([A-Za-z_][A-Za-z0-9_.-]*))\s*:'
                )
                for quoted, bare in key_pattern.findall(candidate):
                    key = bare
                    if quoted:
                        try:
                            key = json.loads('"' + quoted + '"')
                        except json.JSONDecodeError:
                            key = quoted
                    reject_key(key)
                return
        if isinstance(candidate, Mapping):
            for key, nested in candidate.items():
                reject_key(key)
                if key == "credentialRefs":
                    continue
                inspect(nested, action_json=key == "actionJson")
        elif isinstance(candidate, list):
            for nested in candidate:
                inspect(nested)

    inspect(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decode_json(value: Optional[str], default: Any = None) -> Any:
    if value is None:
        return copy.deepcopy(default)
    return json.loads(value)


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _json_pointer(path: Sequence[str]) -> str:
    return "" if not path else "/" + "/".join(_pointer_part(part) for part in path)


def _pointer_tokens(pointer: str) -> List[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError("Conflict path must be a JSON pointer.")
    tokens = []
    for token in pointer[1:].split("/"):
        tokens.append(token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _same(left: Any, right: Any) -> bool:
    if left is _MISSING or right is _MISSING:
        return left is right
    return left == right


def _conflict_value(value: Any) -> Tuple[bool, Any]:
    if value is _MISSING:
        return False, None
    return True, copy.deepcopy(value)


def _merge_values(base: Any, studio: Any, codex: Any, path: Tuple[str, ...] = ()) -> Tuple[Any, List[Dict[str, Any]]]:
    """Three-way merge JSON values, treating arrays and scalars as one field."""

    if _same(studio, base):
        return copy.deepcopy(codex) if codex is not _MISSING else _MISSING, []
    if _same(codex, base) or _same(studio, codex):
        return copy.deepcopy(studio) if studio is not _MISSING else _MISSING, []

    dict_values = [value for value in (base, studio, codex) if value is not _MISSING]
    if dict_values and all(isinstance(value, dict) for value in dict_values):
        merged: Dict[str, Any] = {}
        conflicts: List[Dict[str, Any]] = []
        keys: Set[str] = set()
        for value in dict_values:
            keys.update(value)
        for key in sorted(keys):
            child, child_conflicts = _merge_values(
                base.get(key, _MISSING) if base is not _MISSING else _MISSING,
                studio.get(key, _MISSING) if studio is not _MISSING else _MISSING,
                codex.get(key, _MISSING) if codex is not _MISSING else _MISSING,
                path + (key,),
            )
            if child is not _MISSING:
                merged[key] = child
            conflicts.extend(child_conflicts)
        return merged, conflicts

    base_exists, base_value = _conflict_value(base)
    studio_exists, studio_value = _conflict_value(studio)
    codex_exists, codex_value = _conflict_value(codex)
    conflict = {
        "path": _json_pointer(path),
        "base": base_value,
        "studio": studio_value,
        "codex": codex_value,
        "baseExists": base_exists,
        "studioExists": studio_exists,
        "codexExists": codex_exists,
    }
    # Keep the Studio side visible until the user explicitly resolves it.
    return (copy.deepcopy(studio) if studio is not _MISSING else _MISSING), [conflict]


def _set_pointer(document: Any, pointer: str, exists: bool, value: Any) -> Any:
    tokens = _pointer_tokens(pointer)
    if not tokens:
        if not exists:
            return _MISSING
        return copy.deepcopy(value)
    if not isinstance(document, dict):
        raise ValueError("Cannot resolve a nested conflict in a non-object payload.")
    parent = document
    for token in tokens[:-1]:
        child = parent.get(token)
        if not isinstance(child, dict):
            child = {}
            parent[token] = child
        parent = child
    if exists:
        parent[tokens[-1]] = copy.deepcopy(value)
    else:
        parent.pop(tokens[-1], None)
    return document


def _get_pointer(document: Any, pointer: str) -> Tuple[bool, Any]:
    """Read a JSON-pointer field from an object without exposing internals."""

    current = document
    for token in _pointer_tokens(pointer):
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, copy.deepcopy(current)


def _refresh_conflict_studio_values(
    conflicts: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    """Keep unresolved conflict choices aligned with the latest Studio draft."""

    refreshed: List[Dict[str, Any]] = []
    for item in conflicts:
        conflict = copy.deepcopy(dict(item))
        exists, value = _get_pointer(payload, str(conflict.get("path") or ""))
        conflict["studioExists"] = exists
        conflict["studio"] = value
        refreshed.append(conflict)
    return refreshed


def summary(resource: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the compact camelCase representation used by HTTP responses."""

    base_hash = resource.get("base_hash")
    return {
        "projectId": resource.get("project_id"),
        "kind": resource.get("kind"),
        "id": resource.get("resource_id"),
        "status": resource.get("status"),
        "studioRevision": resource.get("studio_revision"),
        "baseHash": base_hash,
        "baselineHash": base_hash,
        "sourceLocator": copy.deepcopy(resource.get("source_locator")),
        "syncedManifest": copy.deepcopy(resource.get("synced_manifest") or []),
        "conflicts": copy.deepcopy(resource.get("conflicts") or []),
        "syncIntent": resource.get("sync_intent"),
        "syncError": resource.get("sync_error"),
        "testStatus": resource.get("test_status"),
        "testRevision": resource.get("test_revision"),
        "testJobId": resource.get("test_job_id"),
        "testSummary": resource.get("test_summary"),
        "testResult": copy.deepcopy(resource.get("test_result")),
        "createdAt": resource.get("created_at"),
        "updatedAt": resource.get("updated_at"),
        "publishedAt": resource.get("published_at"),
        "syncedAt": resource.get("synced_at"),
    }


class StudioState:
    """Thread-safe SQLite persistence for unpublished Workflow Studio work."""

    schema_version = 3

    def __init__(self, database_path: Optional[Path] = None):
        self.path = Path(database_path).expanduser() if database_path is not None else default_state_path()
        self.path = self.path.absolute()
        self.new_database = not self.path.exists()
        parent_missing = not self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if parent_missing:
            try:
                os.chmod(str(self.path.parent), 0o700)
            except OSError:
                pass
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path), timeout=30.0, isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        try:
            os.chmod(str(self.path), 0o600)
        except OSError:
            self._connection.close()
            raise
        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 30000")
            self._create_schema()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "StudioState":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                yield self._connection
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    def _create_schema(self) -> None:
        statuses = ",".join("'{}'".format(value) for value in sorted(RESOURCE_STATUSES))
        tests = ",".join("'{}'".format(value) for value in sorted(TEST_STATUSES))
        jobs = ",".join("'{}'".format(value) for value in sorted(JOB_STATUSES))
        legacy_jobs = False
        existing_job_sql_row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'agent_test_jobs'"
        ).fetchone()
        if existing_job_sql_row is not None:
            existing_job_sql = str(existing_job_sql_row["sql"] or "")
            existing_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(agent_test_jobs)").fetchall()
            }
            required_columns = {"kind", "agent_name", "tested_revision", "draft_hash", "passed", "duration_ms"}
            if not required_columns.issubset(existing_columns) or "timed_out" not in existing_job_sql:
                self._connection.execute("DROP INDEX IF EXISTS agent_test_jobs_lookup_idx")
                self._connection.execute("DROP INDEX IF EXISTS agent_test_jobs_one_active_idx")
                self._connection.execute("ALTER TABLE agent_test_jobs RENAME TO agent_test_jobs_legacy")
                legacy_jobs = True
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL,
                name TEXT,
                authorized INTEGER NOT NULL DEFAULT 1 CHECK (authorized IN (0, 1)),
                authorized_at TEXT NOT NULL,
                last_scanned_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resources (
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('agent', 'skill', 'action', 'workflow')),
                resource_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                base_payload_json TEXT,
                base_hash TEXT,
                studio_revision INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL CHECK (status IN (""" + statuses + """)),
                source_locator_json TEXT,
                synced_manifest_json TEXT NOT NULL DEFAULT '[]',
                conflicts_json TEXT NOT NULL DEFAULT '[]',
                sync_intent TEXT CHECK (sync_intent IN ('upsert', 'delete') OR sync_intent IS NULL),
                sync_error TEXT,
                test_status TEXT NOT NULL DEFAULT 'untested' CHECK (test_status IN (""" + tests + """)),
                test_revision INTEGER,
                test_job_id TEXT,
                test_summary TEXT,
                test_result_json TEXT,
                tested_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                published_at TEXT,
                synced_at TEXT,
                PRIMARY KEY (project_id, kind, resource_id),
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS resources_project_status_idx
                ON resources(project_id, status, kind);

            CREATE TABLE IF NOT EXISTS latest_ai_drafts (
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('agent', 'skill', 'action', 'workflow')),
                resource_id TEXT NOT NULL DEFAULT '',
                draft_json TEXT NOT NULL,
                studio_revision INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_id, kind, resource_id),
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_test_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'agent' CHECK (kind = 'agent'),
                resource_id TEXT NOT NULL,
                studio_revision INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                agent_name TEXT NOT NULL DEFAULT '',
                tested_revision TEXT,
                draft_hash TEXT,
                status TEXT NOT NULL CHECK (status IN (""" + jobs + """)),
                passed INTEGER CHECK (passed IN (0, 1) OR passed IS NULL),
                duration_ms INTEGER NOT NULL DEFAULT 0,
                result_json TEXT,
                summary TEXT,
                error TEXT,
                seen INTEGER NOT NULL DEFAULT 1 CHECK (seen IN (0, 1)),
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id, kind, resource_id)
                    REFERENCES resources(project_id, kind, resource_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS agent_test_jobs_lookup_idx
                ON agent_test_jobs(project_id, resource_id, studio_revision, status);
            CREATE UNIQUE INDEX IF NOT EXISTS agent_test_jobs_one_active_idx
                ON agent_test_jobs(project_id, resource_id, studio_revision)
                WHERE status IN ('queued', 'running');

            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tutorial_sessions (
                session_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                root_path TEXT NOT NULL,
                marker_token TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'zh',
                status TEXT NOT NULL,
                step_id TEXT NOT NULL,
                data_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            """
        )
        if legacy_jobs:
            legacy_rows = self._connection.execute("SELECT * FROM agent_test_jobs_legacy").fetchall()
            for legacy in legacy_rows:
                values = dict(legacy)
                resource = self._connection.execute(
                    """
                    SELECT payload_json FROM resources
                    WHERE project_id = ? AND kind = 'agent' AND resource_id = ?
                    """,
                    (values.get("project_id"), values.get("resource_id")),
                ).fetchone()
                if resource is None:
                    continue
                payload = _decode_json(values.get("payload_json"), {})
                resource_payload = _decode_json(resource["payload_json"], {})
                old_status = str(values.get("status") or "interrupted")
                status = old_status if old_status in JOB_STATUSES else "interrupted"
                passed = True if status == "passed" else (False if status in TERMINAL_JOB_STATUSES else None)
                revision = values.get("studio_revision")
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO agent_test_jobs (
                        job_id, project_id, kind, resource_id, studio_revision, payload_hash,
                        payload_json, agent_name, tested_revision, draft_hash, status, passed,
                        duration_ms, result_json, summary, error, seen, created_at, started_at,
                        completed_at, updated_at
                    ) VALUES (?, ?, 'agent', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values.get("job_id"),
                        values.get("project_id"),
                        values.get("resource_id"),
                        revision,
                        values.get("payload_hash") or canonical_hash(payload),
                        _json_text(payload),
                        str(resource_payload.get("name") or values.get("resource_id") or ""),
                        str(revision) if revision is not None else None,
                        values.get("payload_hash") or canonical_hash(payload),
                        status,
                        passed,
                        values.get("result_json"),
                        values.get("summary"),
                        values.get("error"),
                        values.get("seen", 1),
                        values.get("created_at") or _now(),
                        values.get("started_at"),
                        values.get("completed_at"),
                        values.get("updated_at") or _now(),
                    ),
                )
            self._connection.execute("DROP TABLE agent_test_jobs_legacy")
        resource_columns = {
            row["name"] for row in self._connection.execute("PRAGMA table_info(resources)").fetchall()
        }
        if "test_result_json" not in resource_columns:
            self._connection.execute("ALTER TABLE resources ADD COLUMN test_result_json TEXT")
        invitation = self._connection.execute(
            "SELECT setting_key FROM app_settings WHERE setting_key = 'onboarding.invitation'"
        ).fetchone()
        if invitation is None:
            timestamp = _now()
            self._connection.execute(
                """
                INSERT INTO app_settings (setting_key, value_json, created_at, updated_at)
                VALUES ('onboarding.invitation', ?, ?, ?)
                """,
                (_json_text("pending" if self.new_database else "dismissed"), timestamp, timestamp),
            )
        self._connection.execute("PRAGMA user_version = {}".format(self.schema_version))

    def get_setting(self, key: str, default: Any = None) -> Any:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("setting key is required.")
        with self._lock:
            row = self._connection.execute(
                "SELECT value_json FROM app_settings WHERE setting_key = ?", (key,)
            ).fetchone()
        return _decode_json(row["value_json"]) if row is not None else copy.deepcopy(default)

    def set_setting(self, key: str, value: Any) -> Any:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("setting key is required.")
        serialized = _json_text(value)
        timestamp = _now()
        with self._write() as connection:
            connection.execute(
                """
                INSERT INTO app_settings (setting_key, value_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, serialized, timestamp, timestamp),
            )
        return _json_copy(value)

    def get_tutorial_session(
        self, project_id: str = "workflow-studio-tutorial"
    ) -> Optional[Dict[str, Any]]:
        self._validate_identity(project_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM tutorial_sessions WHERE project_id = ?", (project_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "project_id": row["project_id"],
            "root_path": row["root_path"],
            "marker_token": row["marker_token"],
            "language": row["language"],
            "status": row["status"],
            "step_id": row["step_id"],
            "data": _decode_json(row["data_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
        }

    def save_tutorial_session(self, session: Mapping[str, Any]) -> Dict[str, Any]:
        project_id = str(session.get("project_id") or "workflow-studio-tutorial")
        self._validate_identity(project_id)
        session_id = str(session.get("session_id") or uuid.uuid4().hex)
        root_path = str(session.get("root_path") or "").strip()
        marker_token = str(session.get("marker_token") or "").strip()
        if not root_path or not marker_token:
            raise ValueError("Tutorial root_path and marker_token are required.")
        status = str(session.get("status") or "in_progress")
        step_id = str(session.get("step_id") or "authorize-import")
        language = "en" if str(session.get("language") or "zh") == "en" else "zh"
        data = session.get("data") if isinstance(session.get("data"), Mapping) else {}
        timestamp = _now()
        completed_at = session.get("completed_at")
        with self._write() as connection:
            connection.execute(
                """
                INSERT INTO tutorial_sessions (
                    session_id, project_id, root_path, marker_token, language,
                    status, step_id, data_json, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    root_path = excluded.root_path,
                    marker_token = excluded.marker_token,
                    language = excluded.language,
                    status = excluded.status,
                    step_id = excluded.step_id,
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at
                """,
                (
                    session_id,
                    project_id,
                    root_path,
                    marker_token,
                    language,
                    status,
                    step_id,
                    _json_text(dict(data)),
                    str(session.get("created_at") or timestamp),
                    timestamp,
                    completed_at,
                ),
            )
        saved = self.get_tutorial_session(project_id)
        if saved is None:
            raise StudioStateError("Tutorial session was not saved.")
        return saved

    def delete_tutorial_session(self, project_id: str = "workflow-studio-tutorial") -> None:
        self._validate_identity(project_id)
        with self._write() as connection:
            connection.execute("DELETE FROM tutorial_sessions WHERE project_id = ?", (project_id,))

    def delete_project_state(self, project_id: str) -> None:
        """Delete one explicitly identified Studio project and its cascaded resources."""

        self._validate_identity(project_id)
        with self._write() as connection:
            connection.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

    @staticmethod
    def _validate_identity(project_id: str, kind: Optional[str] = None, resource_id: Optional[str] = None) -> None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id is required.")
        if kind is not None and kind not in RESOURCE_KINDS:
            raise ValueError("Unsupported resource kind: {}".format(kind))
        if resource_id is not None and (not isinstance(resource_id, str) or not resource_id.strip()):
            raise ValueError("resource_id is required.")

    def _require_authorized(self, connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM projects WHERE project_id = ? AND authorized = 1", (project_id,)
        ).fetchone()
        if row is None:
            raise ProjectNotAuthorizedError(
                "Project details must be explicitly authorized before Studio can access them."
            )
        return row

    def authorize_project(self, project_id: str, root_path: Any, name: Optional[str] = None) -> Dict[str, Any]:
        self._validate_identity(project_id)
        if root_path is None or not str(root_path).strip():
            raise ValueError("root_path is required.")
        normalized_root = str(Path(root_path).expanduser().absolute())
        timestamp = _now()
        with self._write() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, root_path, name, authorized, authorized_at, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    root_path = excluded.root_path,
                    name = COALESCE(excluded.name, projects.name),
                    authorized = 1,
                    authorized_at = excluded.authorized_at,
                    updated_at = excluded.updated_at
                """,
                (project_id, normalized_root, name, timestamp, timestamp, timestamp),
            )
            row = connection.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return self._project_from_row(row)

    def revoke_project(self, project_id: str) -> None:
        self._validate_identity(project_id)
        with self._write() as connection:
            connection.execute(
                "UPDATE projects SET authorized = 0, updated_at = ? WHERE project_id = ?",
                (_now(), project_id),
            )

    def is_authorized(self, project_id: str) -> bool:
        self._validate_identity(project_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT authorized FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return bool(row and row["authorized"])

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        self._validate_identity(project_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return self._project_from_row(row) if row else None

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "root_path": row["root_path"],
            "name": row["name"],
            "authorized": bool(row["authorized"]),
            "authorized_at": row["authorized_at"],
            "last_scanned_at": row["last_scanned_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _resource_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "kind": row["kind"],
            "resource_id": row["resource_id"],
            "payload": _decode_json(row["payload_json"], {}),
            "base_payload": _decode_json(row["base_payload_json"]),
            "base_hash": row["base_hash"],
            "studio_revision": row["studio_revision"],
            "status": row["status"],
            "source_locator": _decode_json(row["source_locator_json"]),
            "synced_manifest": _decode_json(row["synced_manifest_json"], []),
            "conflicts": _decode_json(row["conflicts_json"], []),
            "sync_intent": row["sync_intent"],
            "sync_error": row["sync_error"],
            "test_status": row["test_status"],
            "test_revision": row["test_revision"],
            "test_job_id": row["test_job_id"],
            "test_summary": row["test_summary"],
            "test_result": _decode_json(row["test_result_json"]),
            "tested_at": row["tested_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "published_at": row["published_at"],
            "synced_at": row["synced_at"],
        }

    def _fetch_resource(
        self, connection: sqlite3.Connection, project_id: str, kind: str, resource_id: str
    ) -> Optional[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM resources WHERE project_id = ? AND kind = ? AND resource_id = ?",
            (project_id, kind, resource_id),
        ).fetchone()

    def get_resource(self, project_id: str, kind: str, resource_id: str) -> Optional[Dict[str, Any]]:
        self._validate_identity(project_id, kind, resource_id)
        with self._lock:
            self._require_authorized(self._connection, project_id)
            row = self._fetch_resource(self._connection, project_id, kind, resource_id)
        return self._resource_from_row(row) if row else None

    def list_resources(
        self,
        project_id: str,
        kind: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        self._validate_identity(project_id, kind)
        query = "SELECT * FROM resources WHERE project_id = ?"
        values: List[Any] = [project_id]
        if kind is not None:
            query += " AND kind = ?"
            values.append(kind)
        if statuses is not None:
            selected = sorted(set(statuses))
            if any(status not in RESOURCE_STATUSES for status in selected):
                raise ValueError("Unsupported resource status.")
            if not selected:
                return []
            query += " AND status IN ({})".format(",".join("?" for _ in selected))
            values.extend(selected)
        query += " ORDER BY kind, resource_id"
        with self._lock:
            self._require_authorized(self._connection, project_id)
            rows = self._connection.execute(query, values).fetchall()
        return [self._resource_from_row(row) for row in rows]

    @staticmethod
    def _normalize_import(
        resources: Any, complete_kinds: Optional[Iterable[str]]
    ) -> Tuple[List[Dict[str, Any]], Set[str]]:
        records: List[Dict[str, Any]] = []
        scoped: Set[str] = set(complete_kinds or [])
        if isinstance(resources, Mapping):
            iterable: List[Tuple[str, Any]] = []
            for kind, items in resources.items():
                if kind not in RESOURCE_KINDS:
                    raise ValueError("Unsupported resource kind: {}".format(kind))
                scoped.add(kind)
                for item in items or []:
                    iterable.append((kind, item))
        else:
            iterable = []
            for item in resources or []:
                if not isinstance(item, Mapping):
                    raise ValueError("Imported resources must be objects.")
                kind = str(item.get("kind") or "")
                iterable.append((kind, item))
        if any(kind not in RESOURCE_KINDS for kind in scoped):
            raise ValueError("Unsupported complete import kind.")

        for kind, item in iterable:
            if kind not in RESOURCE_KINDS or not isinstance(item, Mapping):
                raise ValueError("Every imported resource requires a supported kind.")
            is_wrapper = "resource_id" in item or (
                isinstance(item.get("payload"), Mapping)
                and (
                    "kind" in item
                    or any(
                        key in item
                        for key in ("source_locator", "sourceLocator", "synced_manifest", "syncedManifest")
                    )
                )
            )
            payload = item.get("payload") if is_wrapper else item
            if not isinstance(payload, Mapping):
                raise ValueError("Imported resource payload must be an object.")
            resource_id = str(
                (item.get("resource_id") if is_wrapper else None)
                or item.get("id")
                or payload.get("id")
                or ""
            )
            if not resource_id:
                raise ValueError("Every imported resource requires an id.")
            source_locator = item.get("source_locator", item.get("sourceLocator")) if is_wrapper else None
            synced_manifest = item.get("synced_manifest", item.get("syncedManifest", [])) if is_wrapper else []
            manifest_known = bool(
                is_wrapper
                and any(key in item for key in ("synced_manifest", "syncedManifest"))
            )
            records.append(
                {
                    "kind": kind,
                    "resource_id": resource_id,
                    "payload": _json_copy(dict(payload)),
                    "source_locator": _json_copy(source_locator) if source_locator is not None else None,
                    "synced_manifest": _json_copy(synced_manifest or []),
                    "manifest_known": manifest_known,
                }
            )
        return records, scoped

    def import_resources(
        self,
        project_id: str,
        resources: Any,
        *,
        complete_kinds: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Merge a complete or partial read-only Codex scan into Studio state.

        A mapping such as ``{"agent": [...], "skill": []}`` is considered a
        complete scan for its keys, so missing previously-synced records become
        ``source_missing``.  A sequence may pass ``complete_kinds`` explicitly.
        """

        self._validate_identity(project_id)
        incoming, scoped_kinds = self._normalize_import(resources, complete_kinds)
        timestamp = _now()
        seen: Set[Tuple[str, str]] = set()
        counts = {"created": 0, "updated": 0, "merged": 0, "conflicted": 0, "missing": 0}
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            for imported in incoming:
                kind = imported["kind"]
                resource_id = imported["resource_id"]
                key = (kind, resource_id)
                if key in seen:
                    raise ValueError("Duplicate imported resource: {}/{}".format(kind, resource_id))
                seen.add(key)
                remote = imported["payload"]
                remote_hash = canonical_hash(remote)
                row = self._fetch_resource(connection, project_id, kind, resource_id)
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO resources (
                            project_id, kind, resource_id, payload_json, base_payload_json,
                            base_hash, studio_revision, status, source_locator_json,
                            synced_manifest_json, conflicts_json, sync_intent, created_at,
                            updated_at, synced_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, 'synced', ?, ?, '[]', NULL, ?, ?, ?)
                        """,
                        (
                            project_id,
                            kind,
                            resource_id,
                            _json_text(remote),
                            _json_text(remote),
                            remote_hash,
                            _json_text(imported["source_locator"]) if imported["source_locator"] is not None else None,
                            _json_text(imported["synced_manifest"]),
                            timestamp,
                            timestamp,
                            timestamp,
                        ),
                    )
                    counts["created"] += 1
                    continue

                current = self._resource_from_row(row)
                base = current["base_payload"]
                local = current["payload"]
                current_manifest = [str(item) for item in current["synced_manifest"] if item]
                incoming_manifest = [
                    str(item) for item in imported["synced_manifest"] if item
                ]
                incoming_manifest_set = set(incoming_manifest)
                missing_manifest_targets = [
                    item for item in current_manifest if item not in incoming_manifest_set
                ]
                manifest_incomplete = bool(
                    imported.get("manifest_known") and missing_manifest_targets
                )
                stored_manifest = (
                    list(dict.fromkeys(current_manifest + incoming_manifest))
                    if manifest_incomplete
                    else (
                        incoming_manifest
                        if imported.get("manifest_known")
                        else current_manifest
                    )
                )
                remote_changed = current["base_hash"] != remote_hash
                payload = local
                conflicts = current["conflicts"]
                status = current["status"]
                revision = current["studio_revision"]
                payload_changed = False
                sync_intent = current["sync_intent"]

                if not remote_changed:
                    if status == "source_missing" and not manifest_incomplete:
                        status = "synced" if canonical_hash(local) == remote_hash else "draft"
                        sync_intent = None if status == "synced" else "upsert"
                        conflicts = []
                        counts["updated"] += 1
                elif base is None:
                    # A Studio-only resource now appeared independently in Codex.
                    merged, conflicts = _merge_values(_MISSING, local, remote)
                    payload = {} if merged is _MISSING else merged
                    payload_changed = payload != local
                    status = "conflict" if conflicts else ("synced" if payload == remote else "draft")
                    sync_intent = None if status == "synced" else "upsert"
                    counts["conflicted" if conflicts else "merged"] += 1

                elif (
                    canonical_hash(local) == current["base_hash"]
                    and status != "pending_delete"
                    and sync_intent != "delete"
                ):
                    payload = remote
                    payload_changed = payload != local
                    conflicts = []
                    status = "synced"
                    sync_intent = None
                    counts["updated"] += 1
                elif status == "pending_delete" or sync_intent == "delete":
                    # Do not silently delete a resource that changed in Codex after staging.
                    _, conflicts = _merge_values(base, _MISSING, remote)
                    status = "conflict"
                    sync_intent = "delete"
                    counts["conflicted"] += 1
                else:
                    merged, conflicts = _merge_values(base, local, remote)
                    payload = {} if merged is _MISSING else merged
                    payload_changed = payload != local
                    status = "conflict" if conflicts else ("synced" if payload == remote else "draft")
                    sync_intent = None if status == "synced" else "upsert"
                    counts["conflicted" if conflicts else "merged"] += 1

                if (
                    manifest_incomplete
                    and status not in {"conflict", "pending_delete"}
                    and sync_intent != "delete"
                ):
                    if current["status"] != "source_missing":
                        counts["missing"] += 1
                    status = "source_missing"
                    sync_intent = "upsert"

                if payload_changed:
                    revision += 1
                test_status = current["test_status"]
                test_job_id = current["test_job_id"]
                test_summary = current["test_summary"]
                test_result = current["test_result"]
                tested_at = current["tested_at"]
                if payload_changed and current["test_revision"] is not None:
                    test_status, test_job_id, test_summary, test_result, tested_at = "stale", None, None, None, None
                connection.execute(
                    """
                    UPDATE resources SET
                        payload_json = ?, base_payload_json = ?, base_hash = ?,
                        studio_revision = ?, status = ?, source_locator_json = ?,
                        synced_manifest_json = ?, conflicts_json = ?, sync_intent = ?,
                        sync_error = NULL, test_status = ?, test_job_id = ?,
                        test_summary = ?, test_result_json = ?, tested_at = ?, updated_at = ?
                    WHERE project_id = ? AND kind = ? AND resource_id = ?
                    """,
                    (
                        _json_text(payload),
                        _json_text(remote),
                        remote_hash,
                        revision,
                        status,
                        _json_text(imported["source_locator"]) if imported["source_locator"] is not None else None,
                        _json_text(stored_manifest),
                        _json_text(conflicts),
                        sync_intent,
                        test_status,
                        test_job_id,
                        test_summary,
                        _json_text(test_result) if test_result is not None else None,
                        tested_at,
                        timestamp,
                        project_id,
                        kind,
                        resource_id,
                    ),
                )

            for kind in scoped_kinds:
                rows = connection.execute(
                    "SELECT * FROM resources WHERE project_id = ? AND kind = ? AND base_hash IS NOT NULL",
                    (project_id, kind),
                ).fetchall()
                for row in rows:
                    key = (kind, row["resource_id"])
                    if key in seen or row["status"] == "source_missing":
                        continue
                    if row["sync_intent"] == "delete":
                        # A confirmed Studio delete must still be able to clean
                        # up its recorded sidecars when the canonical Codex
                        # file disappeared before the explicit sync.
                        continue
                    connection.execute(
                        """
                        UPDATE resources SET status = 'source_missing', sync_intent = 'upsert',
                            sync_error = NULL, updated_at = ?
                        WHERE project_id = ? AND kind = ? AND resource_id = ?
                        """,
                        (timestamp, project_id, kind, row["resource_id"]),
                    )
                    counts["missing"] += 1
            connection.execute(
                "UPDATE projects SET last_scanned_at = ?, updated_at = ? WHERE project_id = ?",
                (timestamp, timestamp, project_id),
            )

        return {
            "project_id": project_id,
            "imported_at": timestamp,
            "counts": counts,
            "resources": self.list_resources(project_id),
        }

    def _check_revision(self, row: sqlite3.Row, expected_revision: Optional[int]) -> None:
        if expected_revision is not None and row["studio_revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, row["studio_revision"])

    def save_draft(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        payload: Mapping[str, Any],
        *,
        expected_revision: Optional[int] = None,
        source_locator: Any = _UNSET,
        synced_manifest: Any = _UNSET,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind, resource_id)
        if not isinstance(payload, Mapping):
            raise ValueError("Resource payload must be an object.")
        clean_payload = _json_copy(dict(payload))
        if kind == "action":
            reject_embedded_action_credentials(clean_payload)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                if expected_revision not in (None, 0):
                    raise RevisionConflictError(expected_revision, 0)
                connection.execute(
                    """
                    INSERT INTO resources (
                        project_id, kind, resource_id, payload_json, studio_revision,
                        status, source_locator_json, synced_manifest_json, conflicts_json,
                        sync_intent, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, 'draft', ?, ?, '[]', 'upsert', ?, ?)
                    """,
                    (
                        project_id,
                        kind,
                        resource_id,
                        _json_text(clean_payload),
                        None if source_locator is _UNSET else _json_text(source_locator),
                        "[]" if synced_manifest is _UNSET else _json_text(synced_manifest),
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                self._check_revision(row, expected_revision)
                current = self._resource_from_row(row)
                changed = current["payload"] != clean_payload
                revision = current["studio_revision"] + (1 if changed else 0)
                if changed and current["status"] == "conflict":
                    # Autosave must never make an unresolved three-way conflict
                    # disappear.  Keep the conflict panel authoritative while
                    # updating its Studio-side choices to the latest draft.
                    status = "conflict"
                    conflicts = (
                        current["conflicts"]
                        if current["sync_intent"] == "delete"
                        else _refresh_conflict_studio_values(
                            current["conflicts"], clean_payload
                        )
                    )
                else:
                    status = "draft" if changed else current["status"]
                    conflicts = [] if changed else current["conflicts"]
                test_status = current["test_status"]
                test_job_id = current["test_job_id"]
                test_summary = current["test_summary"]
                test_result = current["test_result"]
                tested_at = current["tested_at"]
                if changed and current["test_revision"] is not None:
                    test_status, test_job_id, test_summary, test_result, tested_at = "stale", None, None, None, None
                locator_json = row["source_locator_json"] if source_locator is _UNSET else _json_text(source_locator)
                manifest_json = row["synced_manifest_json"] if synced_manifest is _UNSET else _json_text(synced_manifest)
                connection.execute(
                    """
                    UPDATE resources SET payload_json = ?, studio_revision = ?, status = ?,
                        source_locator_json = ?, synced_manifest_json = ?, conflicts_json = ?,
                        sync_intent = ?, sync_error = NULL, test_status = ?, test_job_id = ?,
                        test_summary = ?, test_result_json = ?, tested_at = ?, updated_at = ?
                    WHERE project_id = ? AND kind = ? AND resource_id = ?
                    """,
                    (
                        _json_text(clean_payload),
                        revision,
                        status,
                        locator_json,
                        manifest_json,
                        _json_text(conflicts),
                        (
                            current["sync_intent"] or "upsert"
                            if changed and current["status"] == "conflict"
                            else ("upsert" if changed else current["sync_intent"])
                        ),
                        test_status,
                        test_job_id,
                        test_summary,
                        _json_text(test_result) if test_result is not None else None,
                        tested_at,
                        timestamp,
                        project_id,
                        kind,
                        resource_id,
                    ),
                )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def publish(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        *,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind, resource_id)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, expected_revision)
            if row["status"] == "conflict":
                raise StudioStateError("请先解决冲突，再发布到 Studio。")
            if row["status"] == "pending_delete":
                raise StudioStateError("已标记删除的资源不能发布。")
            connection.execute(
                """
                UPDATE resources SET status = 'ready', sync_intent = 'upsert',
                    sync_error = NULL, published_at = ?, updated_at = ?
                WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (timestamp, timestamp, project_id, kind, resource_id),
            )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def stage_delete(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        *,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind, resource_id)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, expected_revision)
            if row["status"] == "conflict":
                raise StudioStateError(
                    "Resolve conflicts before staging this resource for deletion."
                )
            revision = row["studio_revision"] + (0 if row["status"] == "pending_delete" else 1)
            test_status = "stale" if row["test_revision"] is not None else row["test_status"]
            connection.execute(
                """
                UPDATE resources SET studio_revision = ?, status = 'pending_delete',
                    conflicts_json = '[]', sync_intent = 'delete', sync_error = NULL,
                    test_status = ?, test_job_id = NULL, test_summary = NULL,
                    test_result_json = NULL, tested_at = NULL, updated_at = ?
                WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (revision, test_status, timestamp, project_id, kind, resource_id),
            )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def resolve_conflict(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        resolutions: Any,
        *,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resolve conflicts with ``studio``, ``codex`` or a custom JSON value."""

        self._validate_identity(project_id, kind, resource_id)
        if isinstance(resolutions, Mapping):
            choices = dict(resolutions)
        elif isinstance(resolutions, Sequence) and not isinstance(resolutions, (str, bytes)):
            choices = {str(item.get("path")): item for item in resolutions if isinstance(item, Mapping)}
        else:
            raise ValueError("Conflict resolutions must be a mapping or list.")
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, expected_revision)
            current = self._resource_from_row(row)
            if not current["conflicts"]:
                raise StudioStateError("这个资源没有待解决的冲突。")
            known = {item["path"]: item for item in current["conflicts"]}
            unknown = set(choices) - set(known)
            if unknown:
                raise ValueError("Unknown conflict path: {}".format(sorted(unknown)[0]))
            payload: Any = copy.deepcopy(current["payload"])
            remaining = []
            for conflict in current["conflicts"]:
                pointer = conflict["path"]
                if pointer not in choices:
                    remaining.append(conflict)
                    continue
                resolution = choices[pointer]
                if isinstance(resolution, str):
                    choice = resolution
                    custom = _UNSET
                    delete_custom = False
                elif isinstance(resolution, Mapping):
                    choice = str(resolution.get("choice") or "custom")
                    custom = resolution.get("value", _UNSET)
                    delete_custom = bool(resolution.get("delete"))
                else:
                    choice, custom, delete_custom = "custom", resolution, False
                if choice in {"studio", "local"}:
                    exists, value = conflict["studioExists"], conflict["studio"]
                elif choice in {"codex", "remote"}:
                    exists, value = conflict["codexExists"], conflict["codex"]
                elif choice == "custom":
                    if custom is _UNSET and not delete_custom:
                        raise ValueError("Custom conflict resolution requires a value or delete=true.")
                    exists, value = (False, None) if delete_custom else (True, _json_copy(custom))
                else:
                    raise ValueError("Conflict choice must be studio, codex, or custom.")
                payload = _set_pointer(payload, pointer, exists, value)
            if payload is _MISSING or not isinstance(payload, dict):
                raise ValueError("A resource payload must remain an object after conflict resolution.")
            changed = payload != current["payload"]
            revision = current["studio_revision"] + (1 if changed else 0)
            if remaining:
                status = "conflict"
            elif current["sync_intent"] == "delete":
                status = "draft"
            else:
                status = "synced" if current["base_payload"] == payload else "draft"
            sync_intent = None if status == "synced" else "upsert"
            test_status = current["test_status"]
            test_job_id = current["test_job_id"]
            test_summary = current["test_summary"]
            test_result = current["test_result"]
            tested_at = current["tested_at"]
            if changed and current["test_revision"] is not None:
                test_status, test_job_id, test_summary, test_result, tested_at = "stale", None, None, None, None
            connection.execute(
                """
                UPDATE resources SET payload_json = ?, studio_revision = ?, status = ?,
                    conflicts_json = ?, sync_intent = ?, sync_error = NULL,
                    test_status = ?, test_job_id = ?, test_summary = ?, test_result_json = ?, tested_at = ?,
                    updated_at = ?
                WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (
                    _json_text(payload),
                    revision,
                    status,
                    _json_text(remaining),
                    sync_intent,
                    test_status,
                    test_job_id,
                    test_summary,
                    _json_text(test_result) if test_result is not None else None,
                    tested_at,
                    timestamp,
                    project_id,
                    kind,
                    resource_id,
                ),
            )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def mark_synced(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        *,
        expected_revision: Optional[int] = None,
        source_locator: Any = _UNSET,
        synced_manifest: Any = _UNSET,
        deleted: bool = False,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind, resource_id)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, expected_revision)
            current = self._resource_from_row(row)
            if deleted:
                base_json, base_hash, status = None, None, "source_missing"
                manifest_json = "[]" if synced_manifest is _UNSET else _json_text(synced_manifest)
            else:
                base_json = _json_text(current["payload"])
                base_hash = canonical_hash(current["payload"])
                status = "synced"
                manifest_json = row["synced_manifest_json"] if synced_manifest is _UNSET else _json_text(synced_manifest)
            locator_json = row["source_locator_json"] if source_locator is _UNSET else (
                None if source_locator is None else _json_text(source_locator)
            )
            connection.execute(
                """
                UPDATE resources SET base_payload_json = ?, base_hash = ?, status = ?,
                    source_locator_json = ?, synced_manifest_json = ?, conflicts_json = '[]',
                    sync_intent = NULL, sync_error = NULL, synced_at = ?, updated_at = ?
                WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (
                    base_json,
                    base_hash,
                    status,
                    locator_json,
                    manifest_json,
                    timestamp,
                    timestamp,
                    project_id,
                    kind,
                    resource_id,
                ),
            )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def mark_sync_failed(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        error: str,
        *,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind, resource_id)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, expected_revision)
            intent = row["sync_intent"] or ("delete" if row["status"] == "pending_delete" else "upsert")
            connection.execute(
                """
                UPDATE resources SET status = 'sync_failed', sync_intent = ?, sync_error = ?,
                    updated_at = ? WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (intent, str(error)[:4000], timestamp, project_id, kind, resource_id),
            )
            result = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(result)

    def record_resource_test(
        self,
        project_id: str,
        kind: str,
        resource_id: str,
        studio_revision: int,
        status: str,
        summary_text: str = "",
        result: Any = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a test/Dry-run result only for the exact current draft version."""

        self._validate_identity(project_id, kind, resource_id)
        normalized_status = {
            "queued": "running",
            "timed_out": "failed",
            "cancelled": "interrupted",
        }.get(status, status)
        if normalized_status not in TEST_STATUSES:
            raise ValueError("Unsupported resource test status: {}".format(status))
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            row = self._fetch_resource(connection, project_id, kind, resource_id)
            if row is None:
                raise ResourceNotFoundError("Studio 中没有这个资源。")
            self._check_revision(row, studio_revision)
            tested_at = None if normalized_status == "running" else timestamp
            connection.execute(
                """
                UPDATE resources SET test_status = ?, test_revision = ?, test_job_id = ?,
                    test_summary = ?, test_result_json = ?, tested_at = ?, updated_at = ?
                WHERE project_id = ? AND kind = ? AND resource_id = ?
                """,
                (
                    normalized_status,
                    studio_revision,
                    job_id,
                    str(summary_text or "")[:4000],
                    _json_text(result) if result is not None else None,
                    tested_at,
                    timestamp,
                    project_id,
                    kind,
                    resource_id,
                ),
            )
            updated = self._fetch_resource(connection, project_id, kind, resource_id)
        return self._resource_from_row(updated)

    def save_latest_ai_draft(
        self,
        project_id: str,
        kind: str,
        draft: Mapping[str, Any],
        *,
        resource_id: str = "",
        studio_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, kind)
        if not isinstance(draft, Mapping):
            raise ValueError("AI draft must be an object.")
        timestamp = _now()
        clean = _json_copy(dict(draft))
        if kind == "action":
            reject_embedded_action_credentials(clean)
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            connection.execute(
                """
                INSERT INTO latest_ai_drafts (
                    project_id, kind, resource_id, draft_json, studio_revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, kind, resource_id) DO UPDATE SET
                    draft_json = excluded.draft_json,
                    studio_revision = excluded.studio_revision,
                    updated_at = excluded.updated_at
                """,
                (project_id, kind, resource_id, _json_text(clean), studio_revision, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM latest_ai_drafts WHERE project_id = ? AND kind = ? AND resource_id = ?",
                (project_id, kind, resource_id),
            ).fetchone()
        return self._ai_draft_from_row(row)

    def get_latest_ai_draft(
        self, project_id: str, kind: str, *, resource_id: Optional[str] = ""
    ) -> Optional[Dict[str, Any]]:
        self._validate_identity(project_id, kind)
        with self._lock:
            self._require_authorized(self._connection, project_id)
            if resource_id is None:
                row = self._connection.execute(
                    """
                    SELECT * FROM latest_ai_drafts
                    WHERE project_id = ? AND kind = ?
                    ORDER BY updated_at DESC, resource_id DESC LIMIT 1
                    """,
                    (project_id, kind),
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT * FROM latest_ai_drafts WHERE project_id = ? AND kind = ? AND resource_id = ?",
                    (project_id, kind, resource_id),
                ).fetchone()
        return self._ai_draft_from_row(row) if row else None

    @staticmethod
    def _ai_draft_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "kind": row["kind"],
            "resource_id": row["resource_id"],
            "draft": _decode_json(row["draft_json"], {}),
            "studio_revision": row["studio_revision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _job_from_row(row: sqlite3.Row, deduplicated: bool = False) -> Dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "project_id": row["project_id"],
            "resource_id": row["resource_id"],
            "studio_revision": row["studio_revision"],
            "payload_hash": row["payload_hash"],
            "payload": _decode_json(row["payload_json"], {}),
            "agent_name": row["agent_name"],
            "tested_revision": row["tested_revision"],
            "draft_hash": row["draft_hash"],
            "status": row["status"],
            "passed": None if row["passed"] is None else bool(row["passed"]),
            "duration_ms": row["duration_ms"],
            "result": _decode_json(row["result_json"]),
            "summary": row["summary"],
            "error": row["error"],
            "seen": bool(row["seen"]),
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "updated_at": row["updated_at"],
            "deduplicated": deduplicated,
        }

    def create_agent_test_job(
        self, project_id: str, resource_id: str, *, job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        self._validate_identity(project_id, "agent", resource_id)
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            resource = self._fetch_resource(connection, project_id, "agent", resource_id)
            if resource is None:
                raise ResourceNotFoundError("Studio 中没有这个 Agent。")
            existing = connection.execute(
                """
                SELECT * FROM agent_test_jobs
                WHERE project_id = ? AND resource_id = ? AND studio_revision = ?
                    AND status IN ('queued', 'running')
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, resource_id, resource["studio_revision"]),
            ).fetchone()
            if existing is not None:
                return self._job_from_row(existing, deduplicated=True)
            identifier = job_id or uuid.uuid4().hex
            payload = _decode_json(resource["payload_json"], {})
            connection.execute(
                """
                INSERT INTO agent_test_jobs (
                    job_id, project_id, resource_id, studio_revision, payload_hash,
                    payload_json, agent_name, tested_revision, draft_hash, status,
                    seen, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 1, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    resource_id,
                    resource["studio_revision"],
                    canonical_hash(payload),
                    _json_text(payload),
                    str(payload.get("name") or resource_id),
                    str(resource["studio_revision"]),
                    str(resource["studio_revision"]),
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                UPDATE resources SET test_status = 'running', test_revision = ?,
                    test_job_id = ?, test_summary = NULL, tested_at = NULL, updated_at = ?
                WHERE project_id = ? AND kind = 'agent' AND resource_id = ?
                """,
                (resource["studio_revision"], identifier, timestamp, project_id, resource_id),
            )
            row = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (identifier,)
            ).fetchone()
        return self._job_from_row(row)

    def get_agent_test_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not job_id:
            raise ValueError("job_id is required.")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._job_from_row(row) if row else None

    def list_agent_test_jobs(
        self,
        *,
        project_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        unseen_only: bool = False,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM agent_test_jobs WHERE 1 = 1"
        values: List[Any] = []
        if project_id is not None:
            self._validate_identity(project_id)
            query += " AND project_id = ?"
            values.append(project_id)
        if resource_id is not None:
            query += " AND resource_id = ?"
            values.append(resource_id)
        if statuses is not None:
            selected = sorted(set(statuses))
            if any(status not in JOB_STATUSES for status in selected):
                raise ValueError("Unsupported job status.")
            if not selected:
                return []
            query += " AND status IN ({})".format(",".join("?" for _ in selected))
            values.extend(selected)
        if unseen_only:
            query += (
                " AND seen = 0 AND status IN "
                "('passed', 'failed', 'timed_out', 'cancelled', 'interrupted')"
            )
        query += " ORDER BY created_at, job_id"
        with self._lock:
            if project_id is not None:
                self._require_authorized(self._connection, project_id)
            rows = self._connection.execute(query, values).fetchall()
        return [self._job_from_row(row) for row in rows]

    def update_agent_test_job(
        self,
        job_id: str,
        status: str,
        *,
        result: Any = _UNSET,
        summary_text: Optional[str] = None,
        error: Optional[str] = None,
        passed: Any = _UNSET,
        duration_ms: Any = _UNSET,
        started_at: Any = _UNSET,
        completed_at: Any = _UNSET,
    ) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id is required.")
        if status not in JOB_STATUSES:
            raise ValueError("Unsupported job status.")
        timestamp = _now()
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("找不到这次 Agent 测试。")
            if row["status"] in TERMINAL_JOB_STATUSES and status != row["status"]:
                raise StudioStateError("A completed agent test job cannot change status.")
            effective_started_at = row["started_at"] if started_at is _UNSET else started_at
            if status == "running" and effective_started_at is None:
                effective_started_at = timestamp
            effective_completed_at = (
                (timestamp if status in TERMINAL_JOB_STATUSES else None)
                if completed_at is _UNSET
                else completed_at
            )
            seen = 0 if status in TERMINAL_JOB_STATUSES else 1
            result_json = row["result_json"] if result is _UNSET else _json_text(result)
            effective_passed = row["passed"] if passed is _UNSET else (None if passed is None else int(bool(passed)))
            if passed is _UNSET and status in TERMINAL_JOB_STATUSES:
                effective_passed = int(status == "passed")
            effective_duration = row["duration_ms"] if duration_ms is _UNSET else max(0, int(duration_ms or 0))
            connection.execute(
                """
                UPDATE agent_test_jobs SET status = ?, result_json = ?, summary = ?, error = ?,
                    passed = ?, duration_ms = ?, seen = ?, started_at = ?, completed_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    result_json,
                    summary_text,
                    error,
                    effective_passed,
                    effective_duration,
                    seen,
                    effective_started_at,
                    effective_completed_at,
                    timestamp,
                    job_id,
                ),
            )
            resource = self._fetch_resource(connection, row["project_id"], "agent", row["resource_id"])
            if (
                resource is not None
                and resource["studio_revision"] == row["studio_revision"]
                and resource["test_job_id"] == job_id
            ):
                test_status = {
                    "queued": "running",
                    "timed_out": "failed",
                    "cancelled": "interrupted",
                }.get(status, status)
                connection.execute(
                    """
                    UPDATE resources SET test_status = ?, test_summary = ?, tested_at = ?,
                        updated_at = ? WHERE project_id = ? AND kind = 'agent' AND resource_id = ?
                    """,
                    (
                        test_status,
                        summary_text,
                        effective_completed_at,
                        timestamp,
                        row["project_id"],
                        row["resource_id"],
                    ),
                )
            updated = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._job_from_row(updated)

    def mark_unfinished_jobs_interrupted(self, reason: str = "Studio restarted before the test completed.") -> int:
        timestamp = _now()
        with self._write() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE agent_test_jobs SET status = 'interrupted', error = ?, seen = 0,
                        completed_at = ?, updated_at = ? WHERE job_id = ?
                    """,
                    (reason, timestamp, timestamp, row["job_id"]),
                )
                connection.execute(
                    """
                    UPDATE resources SET test_status = 'interrupted', test_summary = ?,
                        tested_at = ?, updated_at = ?
                    WHERE project_id = ? AND kind = 'agent' AND resource_id = ?
                        AND studio_revision = ? AND test_job_id = ?
                    """,
                    (
                        reason,
                        timestamp,
                        timestamp,
                        row["project_id"],
                        row["resource_id"],
                        row["studio_revision"],
                        row["job_id"],
                    ),
                )
        return len(rows)

    def list_unseen_agent_test_jobs(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.list_agent_test_jobs(project_id=project_id, unseen_only=True)

    def mark_agent_test_job_seen(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id is required.")
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("找不到这次 Agent 测试。")
            connection.execute("UPDATE agent_test_jobs SET seen = 1 WHERE job_id = ?", (job_id,))
            updated = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._job_from_row(updated)

    @staticmethod
    def _manager_job(record: Mapping[str, Any]) -> Dict[str, Any]:
        """Translate a persisted job to AgentTestManager's camelCase contract."""

        return {
            "jobId": record.get("job_id"),
            "projectId": record.get("project_id"),
            "agentId": record.get("resource_id"),
            "agentName": record.get("agent_name") or record.get("resource_id"),
            "resourceRevision": record.get("studio_revision"),
            "testedRevision": record.get("studio_revision"),
            "draftHash": record.get("draft_hash") or record.get("payload_hash"),
            "status": record.get("status"),
            "passed": record.get("passed"),
            "summary": record.get("summary") or "",
            "durationMs": record.get("duration_ms") or 0,
            "result": copy.deepcopy(record.get("result")),
            "error": record.get("error"),
            "seen": bool(record.get("seen")),
            "createdAt": record.get("created_at"),
            "startedAt": record.get("started_at"),
            "completedAt": record.get("completed_at"),
            "updatedAt": record.get("updated_at"),
        }

    def create_test_job(self, job: Mapping[str, Any]) -> Dict[str, Any]:
        """AgentTestManager store adapter using its camelCase job shape."""

        if not isinstance(job, Mapping):
            raise ValueError("Agent test job must be an object.")
        job_id = str(job.get("jobId") or "").strip()
        project_id = str(job.get("projectId") or "").strip()
        resource_id = str(job.get("agentId") or "").strip()
        revision = job.get("resourceRevision", job.get("testedRevision"))
        status = str(job.get("status") or "queued")
        if not job_id:
            raise ValueError("jobId is required.")
        self._validate_identity(project_id, "agent", resource_id)
        if revision is None or revision == "":
            raise ValueError("resourceRevision is required.")
        try:
            revision = int(revision)
        except (TypeError, ValueError) as error:
            raise ValueError("resourceRevision must be an integer.") from error
        if status not in JOB_STATUSES:
            raise ValueError("Unsupported job status.")
        timestamp = _now()
        with self._write() as connection:
            self._require_authorized(connection, project_id)
            resource = self._fetch_resource(connection, project_id, "agent", resource_id)
            if resource is None:
                raise ResourceNotFoundError("Studio 中没有这个 Agent。")
            if resource["studio_revision"] != revision:
                raise RevisionConflictError(revision, resource["studio_revision"])
            duplicate = connection.execute(
                """
                SELECT * FROM agent_test_jobs
                WHERE project_id = ? AND resource_id = ? AND studio_revision = ?
                    AND status IN ('queued', 'running')
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, resource_id, revision),
            ).fetchone()
            if duplicate is not None:
                return self._manager_job(self._job_from_row(duplicate, deduplicated=True))
            payload = _decode_json(resource["payload_json"], {})
            created_at = str(job.get("createdAt") or timestamp)
            started_at = job.get("startedAt")
            completed_at = job.get("completedAt")
            passed = job.get("passed")
            connection.execute(
                """
                INSERT INTO agent_test_jobs (
                    job_id, project_id, kind, resource_id, studio_revision, payload_hash,
                    payload_json, agent_name, tested_revision, draft_hash, status, passed,
                    duration_ms, result_json, summary, error, seen, created_at, started_at,
                    completed_at, updated_at
                ) VALUES (?, ?, 'agent', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    resource_id,
                    revision,
                    canonical_hash(payload),
                    _json_text(payload),
                    str(job.get("agentName") or payload.get("name") or resource_id),
                    str(job.get("testedRevision", revision)),
                    str(job.get("draftHash", revision)),
                    status,
                    None if passed is None else int(bool(passed)),
                    max(0, int(job.get("durationMs") or 0)),
                    _json_text(job.get("result")) if job.get("result") is not None else None,
                    str(job.get("summary") or "")[:4000],
                    str(job.get("error") or "")[:4000] or None,
                    0 if status in TERMINAL_JOB_STATUSES else 1,
                    created_at,
                    started_at,
                    completed_at,
                    timestamp,
                ),
            )
            connection.execute(
                """
                UPDATE resources SET test_status = ?, test_revision = ?, test_job_id = ?,
                    test_summary = ?, test_result_json = NULL, tested_at = ?, updated_at = ?
                WHERE project_id = ? AND kind = 'agent' AND resource_id = ?
                """,
                (
                    "running" if status in {"queued", "running"} else (
                        "failed" if status in {"failed", "timed_out"} else (
                            "interrupted" if status in {"cancelled", "interrupted"} else "passed"
                        )
                    ),
                    revision,
                    job_id,
                    str(job.get("summary") or "")[:4000],
                    completed_at,
                    timestamp,
                    project_id,
                    resource_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_test_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._manager_job(self._job_from_row(row))

    def update_test_job(
        self, job_id: str, updates: Optional[Mapping[str, Any]] = None, **keyword_updates: Any
    ) -> Dict[str, Any]:
        values = dict(updates or {})
        values.update(keyword_updates)
        current = self.get_agent_test_job(job_id)
        if current is None:
            raise ResourceNotFoundError("找不到这次 Agent 测试。")
        status = str(values.get("status") or current["status"])
        updated = self.update_agent_test_job(
            job_id,
            status,
            result=values.get("result", _UNSET),
            summary_text=(
                str(values["summary"])[:4000]
                if "summary" in values
                else current.get("summary")
            ),
            error=(str(values["error"])[:4000] if values.get("error") else None),
            passed=values.get("passed", _UNSET),
            duration_ms=values.get("durationMs", _UNSET),
            started_at=values.get("startedAt", _UNSET),
            completed_at=values.get("completedAt", _UNSET),
        )
        return self._manager_job(updated)

    def get_test_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        record = self.get_agent_test_job(job_id)
        return self._manager_job(record) if record is not None else None

    def list_test_jobs(
        self, project_id: Optional[str] = None, agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return [
            self._manager_job(record)
            for record in self.list_agent_test_jobs(project_id=project_id, resource_id=agent_id)
        ]

    def interrupt_unfinished_test_jobs(self) -> int:
        return self.mark_unfinished_jobs_interrupted("Interrupted by service restart.")


# The longer name reads naturally in callers and keeps compatibility with the
# short class name used by the initial implementation plan.
StudioStateStore = StudioState


__all__ = [
    "JOB_STATUSES",
    "RESOURCE_KINDS",
    "RESOURCE_STATUSES",
    "TEST_STATUSES",
    "ProjectNotAuthorizedError",
    "ResourceNotFoundError",
    "RevisionConflictError",
    "StudioState",
    "StudioStateError",
    "StudioStateStore",
    "canonical_hash",
    "default_state_path",
    "summary",
]
