import json
import os
import sqlite3
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_test_jobs import AgentTestManager
from studio_state import (
    ProjectNotAuthorizedError,
    RevisionConflictError,
    StudioState,
    StudioStateError,
    canonical_hash,
    default_state_path,
    summary,
)


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


class StudioStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "app-data" / "state.sqlite3"
        self.store = StudioState(self.database)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        self.store.authorize_project("project-1", self.project_root, "Project One")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def import_agent(self, payload=None):
        payload = payload or {
            "id": "agent-a",
            "name": "Agent A",
            "description": "Original",
            "config": {"model": "inherit", "temperature": 0},
        }
        self.store.import_resources(
            "project-1",
            {
                "agent": [
                    {
                        "resource_id": "agent-a",
                        "payload": payload,
                        "source_locator": "agents/a/AGENT.md",
                        "synced_manifest": ["agents/a/AGENT.md"],
                    }
                ]
            },
        )
        return self.store.get_resource("project-1", "agent", "agent-a")

    def test_default_path_uses_platform_application_state_directory(self):
        fake_home = Path("/Users/example")
        with patch("studio_state.sys.platform", "darwin"), patch("studio_state.Path.home", return_value=fake_home):
            self.assertEqual(
                default_state_path(),
                fake_home / "Library/Application Support/Workflow Studio/state.sqlite3",
            )
        with patch("studio_state.sys.platform", "linux"), patch("studio_state.os.name", "posix"), patch.dict(
            os.environ, {"XDG_STATE_HOME": "/tmp/example-state"}, clear=False
        ):
            self.assertEqual(
                default_state_path(), Path("/tmp/example-state/workflow-studio/state.sqlite3")
            )

    def test_database_is_private_and_persists_authorization(self):
        self.assertEqual(stat.S_IMODE(self.database.stat().st_mode), 0o600)
        self.assertTrue(self.store.is_authorized("project-1"))
        project = self.store.get_project("project-1")
        self.assertEqual(project["root_path"], str(self.project_root.absolute()))
        self.store.close()
        self.store = StudioState(self.database)
        self.assertTrue(self.store.is_authorized("project-1"))

    def test_project_details_require_explicit_authorization(self):
        with self.assertRaises(ProjectNotAuthorizedError):
            self.store.list_resources("unknown")
        with self.assertRaises(ProjectNotAuthorizedError):
            self.store.save_draft("unknown", "skill", "s", {"id": "s"})
        self.store.revoke_project("project-1")
        self.assertFalse(self.store.is_authorized("project-1"))
        with self.assertRaises(ProjectNotAuthorizedError):
            self.store.import_resources("project-1", {"agent": []})

    def test_initial_import_records_baseline_locator_and_manifest(self):
        resource = self.import_agent()
        self.assertEqual(resource["status"], "synced")
        self.assertEqual(resource["payload"], resource["base_payload"])
        self.assertEqual(resource["base_hash"], canonical_hash(resource["payload"]))
        self.assertEqual(resource["source_locator"], "agents/a/AGENT.md")
        self.assertEqual(resource["synced_manifest"], ["agents/a/AGENT.md"])
        self.assertEqual(resource["studio_revision"], 1)
        self.assertIsNotNone(self.store.get_project("project-1")["last_scanned_at"])

    def test_save_publish_and_mark_synced_are_distinct_transitions(self):
        imported = self.import_agent()
        draft_payload = {**imported["payload"], "name": "Edited"}
        draft = self.store.save_draft(
            "project-1", "agent", "agent-a", draft_payload, expected_revision=1
        )
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(draft["studio_revision"], 2)
        self.assertEqual(draft["base_payload"]["name"], "Agent A")

        unchanged = self.store.save_draft("project-1", "agent", "agent-a", draft_payload)
        self.assertEqual(unchanged["studio_revision"], 2)
        ready = self.store.publish("project-1", "agent", "agent-a", expected_revision=2)
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["base_payload"]["name"], "Agent A")

        synced = self.store.mark_synced(
            "project-1",
            "agent",
            "agent-a",
            expected_revision=2,
            synced_manifest=["agents/a/AGENT.md", ".agents/skills/agent-a/SKILL.md"],
        )
        self.assertEqual(synced["status"], "synced")
        self.assertEqual(synced["base_payload"], draft_payload)
        self.assertIsNone(synced["sync_intent"])
        with self.assertRaises(RevisionConflictError):
            self.store.save_draft(
                "project-1", "agent", "agent-a", {**draft_payload, "name": "Stale"}, expected_revision=1
            )

    def test_action_and_ai_drafts_reject_embedded_credentials_before_persistence(self):
        unsafe_action = {
            "id": "unsafe",
            "name": "Unsafe",
            "executor": "api",
            "inputs": {"apiKey": "secret-value"},
            "credentialRefs": ["approved-reference"],
        }

        with self.assertRaisesRegex(ValueError, "credentialRefs"):
            self.store.save_draft("project-1", "action", "unsafe", unsafe_action)
        self.assertIsNone(self.store.get_resource("project-1", "action", "unsafe"))

        with self.assertRaisesRegex(ValueError, "credentialRefs"):
            self.store.save_latest_ai_draft(
                "project-1",
                "action",
                {"kind": "action", "actionJson": json.dumps(unsafe_action)},
            )
        self.assertIsNone(
            self.store.get_latest_ai_draft("project-1", "action")
        )
        with self.assertRaisesRegex(ValueError, "credentialRefs"):
            self.store.save_latest_ai_draft(
                "project-1",
                "action",
                {"kind": "action", "actionJson": '{"name":"Partial","apiKey":"secret'},
            )
        partial = self.store.save_latest_ai_draft(
            "project-1",
            "action",
            {"kind": "action", "actionJson": '{"name":"Partial"'},
        )
        self.assertEqual(partial["draft"]["actionJson"], '{"name":"Partial"')

        saved = self.store.save_draft(
            "project-1",
            "action",
            "safe",
            {
                "id": "safe",
                "name": "Safe",
                "executor": "api",
                "inputs": {},
                "credentialRefs": ["approved-reference"],
            },
        )
        self.assertEqual(saved["payload"]["credentialRefs"], ["approved-reference"])

    def test_three_way_merge_combines_different_fields(self):
        original = self.import_agent()
        local = json.loads(json.dumps(original["payload"]))
        local["name"] = "Studio name"
        local["config"]["temperature"] = 1
        self.store.save_draft("project-1", "agent", "agent-a", local)

        remote = json.loads(json.dumps(original["payload"]))
        remote["description"] = "Changed in Codex"
        remote["config"]["model"] = "gpt-new"
        result = self.store.import_resources("project-1", {"agent": [remote]})
        merged = self.store.get_resource("project-1", "agent", "agent-a")

        self.assertEqual(result["counts"]["merged"], 1)
        self.assertEqual(merged["status"], "draft")
        self.assertEqual(merged["payload"]["name"], "Studio name")
        self.assertEqual(merged["payload"]["description"], "Changed in Codex")
        self.assertEqual(merged["payload"]["config"], {"model": "gpt-new", "temperature": 1})
        self.assertEqual(merged["base_payload"], remote)
        self.assertEqual(merged["conflicts"], [])

    def test_same_field_conflict_is_explicit_and_resolvable(self):
        original = self.import_agent()
        self.store.save_draft(
            "project-1", "agent", "agent-a", {**original["payload"], "name": "Studio name"}
        )
        remote = {**original["payload"], "name": "Codex name"}
        self.store.import_resources("project-1", {"agent": [remote]})
        conflicted = self.store.get_resource("project-1", "agent", "agent-a")

        self.assertEqual(conflicted["status"], "conflict")
        self.assertEqual(conflicted["payload"]["name"], "Studio name")
        self.assertEqual(conflicted["conflicts"][0]["path"], "/name")
        resolved = self.store.resolve_conflict(
            "project-1", "agent", "agent-a", {"/name": "codex"}
        )
        self.assertEqual(resolved["payload"]["name"], "Codex name")
        self.assertEqual(resolved["status"], "synced")

    def test_autosave_keeps_conflict_and_refreshes_its_studio_choice(self):
        original = self.import_agent()
        self.store.save_draft(
            "project-1", "agent", "agent-a", {**original["payload"], "name": "Studio name"}
        )
        self.store.import_resources(
            "project-1", {"agent": [{**original["payload"], "name": "Codex name"}]}
        )
        conflicted = self.store.get_resource("project-1", "agent", "agent-a")

        autosaved = self.store.save_draft(
            "project-1",
            "agent",
            "agent-a",
            {**conflicted["payload"], "name": "Latest Studio name", "description": "Edited too"},
            expected_revision=conflicted["studio_revision"],
        )

        self.assertEqual(autosaved["status"], "conflict")
        self.assertEqual(autosaved["conflicts"][0]["studio"], "Latest Studio name")
        resolved = self.store.resolve_conflict(
            "project-1", "agent", "agent-a", {"/name": "studio"}
        )
        self.assertEqual(resolved["payload"]["name"], "Latest Studio name")
        self.assertEqual(resolved["payload"]["description"], "Edited too")
        self.assertEqual(resolved["status"], "draft")
        self.assertEqual(resolved["conflicts"], [])

    def test_partial_conflict_resolution_and_custom_value(self):
        base = self.import_agent()["payload"]
        self.store.save_draft(
            "project-1",
            "agent",
            "agent-a",
            {**base, "name": "Local", "description": "Local description"},
        )
        self.store.import_resources(
            "project-1",
            {"agent": [{**base, "name": "Remote", "description": "Remote description"}]},
        )
        partial = self.store.resolve_conflict(
            "project-1", "agent", "agent-a", {"/name": {"choice": "custom", "value": "Combined"}}
        )
        self.assertEqual(partial["status"], "conflict")
        self.assertEqual(partial["payload"]["name"], "Combined")
        self.assertEqual([item["path"] for item in partial["conflicts"]], ["/description"])
        finished = self.store.resolve_conflict(
            "project-1", "agent", "agent-a", {"/description": "studio"}
        )
        self.assertEqual(finished["status"], "draft")

    def test_complete_import_marks_missing_and_reappearance_recovers(self):
        self.import_agent()
        self.store.import_resources("project-1", {"agent": []})
        missing = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(missing["status"], "source_missing")
        self.assertEqual(missing["payload"]["name"], "Agent A")

        self.import_agent()
        recovered = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(recovered["status"], "synced")
        self.assertIsNotNone(recovered["base_hash"])

    def test_synced_deletion_keeps_recoverable_record_and_can_reappear(self):
        self.import_agent()
        staged = self.store.stage_delete("project-1", "agent", "agent-a")
        self.assertEqual(staged["status"], "pending_delete")
        self.assertEqual(staged["sync_intent"], "delete")
        deleted = self.store.mark_synced(
            "project-1", "agent", "agent-a", expected_revision=staged["studio_revision"], deleted=True
        )
        self.assertEqual(deleted["status"], "source_missing")
        self.assertIsNone(deleted["base_hash"])
        self.assertEqual(deleted["payload"]["name"], "Agent A")

        self.import_agent()
        restored = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(restored["status"], "synced")
        self.assertEqual(restored["base_payload"], restored["payload"])

    def test_sequence_import_is_partial_unless_complete_kinds_are_given(self):
        self.import_agent()
        self.store.import_resources("project-1", [], complete_kinds=[])
        self.assertEqual(self.store.get_resource("project-1", "agent", "agent-a")["status"], "synced")
        self.store.import_resources("project-1", [], complete_kinds=["agent"])
        self.assertEqual(
            self.store.get_resource("project-1", "agent", "agent-a")["status"], "source_missing"
        )

    def test_pending_delete_conflicts_with_external_change(self):
        original = self.import_agent()["payload"]
        self.store.stage_delete("project-1", "agent", "agent-a")
        self.store.import_resources(
            "project-1", {"agent": [{**original, "description": "Changed after staging"}]}
        )
        current = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(current["status"], "conflict")
        self.assertEqual(current["sync_intent"], "delete")
        self.assertTrue(current["conflicts"])
        with self.assertRaises(StudioStateError):
            self.store.stage_delete("project-1", "agent", "agent-a")

    def test_missing_import_keeps_an_explicit_delete_intent(self):
        self.import_agent()
        self.store.stage_delete("project-1", "agent", "agent-a")

        self.store.import_resources("project-1", {"agent": []})

        staged = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(staged["status"], "pending_delete")
        self.assertEqual(staged["sync_intent"], "delete")

    def test_partial_manifest_deletion_is_source_missing_and_keeps_targets(self):
        original = self.import_agent()

        self.store.import_resources(
            "project-1",
            {
                "agent": [
                    {
                        "resource_id": "agent-a",
                        "payload": original["payload"],
                        "source_locator": "agents/a/AGENT.md",
                        "synced_manifest": [],
                    }
                ]
            },
        )

        missing = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(missing["status"], "source_missing")
        self.assertEqual(missing["sync_intent"], "upsert")
        self.assertEqual(missing["synced_manifest"], ["agents/a/AGENT.md"])

    def test_test_job_creation_rejects_a_revision_changed_after_queueing(self):
        original = self.import_agent()
        self.store.save_draft(
            "project-1",
            "agent",
            "agent-a",
            {**original["payload"], "name": "Changed before job persistence"},
        )

        with self.assertRaises(RevisionConflictError):
            self.store.create_test_job(
                {
                    "jobId": "stale-job",
                    "projectId": "project-1",
                    "agentId": "agent-a",
                    "agentName": "Agent A",
                    "resourceRevision": original["studio_revision"],
                    "status": "queued",
                }
            )

    def test_sync_failure_keeps_retry_intent(self):
        original = self.import_agent()["payload"]
        self.store.stage_delete("project-1", "agent", "agent-a")
        failed = self.store.mark_sync_failed("project-1", "agent", "agent-a", "disk full")
        self.assertEqual(failed["status"], "sync_failed")
        self.assertEqual(failed["sync_intent"], "delete")
        self.assertEqual(failed["sync_error"], "disk full")
        self.store.import_resources(
            "project-1", {"agent": [{**original, "description": "Changed after failure"}]}
        )
        conflicted = self.store.get_resource("project-1", "agent", "agent-a")
        self.assertEqual(conflicted["status"], "conflict")
        self.assertEqual(conflicted["sync_intent"], "delete")

    def test_latest_ai_draft_round_trips_without_chat_history(self):
        saved = self.store.save_latest_ai_draft(
            "project-1",
            "skill",
            {"name": "Draft Skill", "instructions": "Do the work"},
            resource_id="draft-skill",
            studio_revision=3,
        )
        self.assertEqual(saved["draft"]["name"], "Draft Skill")
        loaded = self.store.get_latest_ai_draft(
            "project-1", "skill", resource_id="draft-skill"
        )
        self.assertEqual(loaded, saved)
        self.assertNotIn("messages", loaded)

    def test_resource_test_result_is_versioned_and_edit_makes_it_stale(self):
        resource = self.import_agent()
        tested = self.store.record_resource_test(
            "project-1",
            "agent",
            "agent-a",
            resource["studio_revision"],
            "passed",
            "Loaded correctly",
            {"output": "READY"},
            "job-1",
        )
        self.assertEqual(tested["test_status"], "passed")
        self.assertEqual(tested["test_result"], {"output": "READY"})
        edited = self.store.save_draft(
            "project-1", "agent", "agent-a", {**tested["payload"], "name": "Edited"}
        )
        self.assertEqual(edited["test_status"], "stale")
        self.assertIsNone(edited["test_result"])
        with self.assertRaises(RevisionConflictError):
            self.store.record_resource_test(
                "project-1", "agent", "agent-a", resource["studio_revision"], "passed"
            )

    def test_agent_manager_adapter_runs_in_background_and_tracks_unseen_result(self):
        self.import_agent()
        manager = AgentTestManager(
            self.store,
            lambda _job, payload: {"passed": True, "summary": "loaded " + payload["input"]},
            max_workers=1,
        )
        try:
            job = manager.start("project-1", "agent-a", "Agent A", 1, {"input": "draft"})
            self.assertEqual(job["status"], "queued")
            completed = wait_for(
                lambda: (
                    value
                    if (value := manager.get(job["jobId"]))["status"] == "passed"
                    else None
                )
            )
            self.assertEqual(completed["summary"], "loaded draft")
            self.assertEqual(
                self.store.get_resource("project-1", "agent", "agent-a")["test_status"], "passed"
            )
            unseen = self.store.list_unseen_agent_test_jobs("project-1")
            self.assertEqual([item["job_id"] for item in unseen], [job["jobId"]])
            self.store.mark_agent_test_job_seen(job["jobId"])
            self.assertEqual(self.store.list_unseen_agent_test_jobs("project-1"), [])
        finally:
            manager.shutdown(wait=True)

    def test_manager_timeout_and_cancelled_statuses_are_persisted(self):
        self.import_agent()
        first = {
            "jobId": "timeout",
            "projectId": "project-1",
            "agentId": "agent-a",
            "agentName": "A",
            "resourceRevision": 1,
            "testedRevision": 1,
            "draftHash": "one",
            "status": "queued",
            "passed": None,
            "summary": "",
            "durationMs": 0,
            "createdAt": "now",
            "startedAt": None,
            "completedAt": None,
        }
        self.store.create_test_job(first)
        timed_out = self.store.update_test_job(
            "timeout", {"status": "timed_out", "passed": False, "summary": "late"}
        )
        self.assertEqual(timed_out["status"], "timed_out")

        second = {**first, "jobId": "cancelled", "draftHash": "two"}
        self.store.create_test_job(second)
        cancelled = self.store.update_test_job(
            "cancelled", status="cancelled", passed=False, summary="cancelled"
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(
            [item["job_id"] for item in self.store.list_unseen_agent_test_jobs("project-1")],
            ["cancelled", "timeout"],
        )

    def test_unfinished_jobs_become_interrupted_after_restart(self):
        self.import_agent()
        job = self.store.create_agent_test_job("project-1", "agent-a", job_id="unfinished")
        self.assertEqual(job["status"], "queued")
        self.store.close()
        self.store = StudioState(self.database)
        self.assertEqual(self.store.interrupt_unfinished_test_jobs(), 1)
        interrupted = self.store.get_test_job("unfinished")
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertFalse(interrupted["seen"])

    def test_thread_safe_writes_share_one_connection(self):
        errors = []

        def save(index):
            try:
                self.store.save_draft(
                    "project-1", "skill", "skill-{}".format(index), {"id": "skill-{}".format(index)}
                )
            except Exception as error:  # pragma: no cover - assertion reports details
                errors.append(error)

        threads = [threading.Thread(target=save, args=(index,)) for index in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.store.list_resources("project-1", "skill")), 20)

    def test_v1_job_table_is_migrated_without_losing_job(self):
        self.import_agent()
        self.store.create_agent_test_job("project-1", "agent-a", job_id="old-job")
        self.store.close()
        connection = sqlite3.connect(str(self.database))
        connection.execute("PRAGMA foreign_keys = OFF")
        old = connection.execute("SELECT * FROM agent_test_jobs WHERE job_id = 'old-job'").fetchone()
        columns = [item[1] for item in connection.execute("PRAGMA table_info(agent_test_jobs)")]
        values = dict(zip(columns, old))
        connection.execute("DROP TABLE agent_test_jobs")
        connection.execute(
            """
            CREATE TABLE agent_test_jobs (
                job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, resource_id TEXT NOT NULL,
                studio_revision INTEGER NOT NULL, payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','passed','failed','interrupted')),
                result_json TEXT, summary TEXT, error TEXT, seen INTEGER NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL
            )
            """
        )
        names = [
            "job_id", "project_id", "resource_id", "studio_revision", "payload_hash", "payload_json",
            "status", "result_json", "summary", "error", "seen", "created_at", "started_at",
            "completed_at", "updated_at",
        ]
        connection.execute(
            "INSERT INTO agent_test_jobs ({}) VALUES ({})".format(
                ",".join(names), ",".join("?" for _ in names)
            ),
            [values[name] for name in names],
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()

        self.store = StudioState(self.database)
        migrated = self.store.get_test_job("old-job")
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated["status"], "queued")
        self.assertEqual(
            self.store.update_test_job("old-job", {"status": "timed_out"})["status"], "timed_out"
        )

    def test_canonical_hash_and_http_summary_are_stable(self):
        self.assertEqual(canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1}))
        resource = self.import_agent()
        compact = summary(resource)
        self.assertEqual(compact["projectId"], "project-1")
        self.assertEqual(compact["id"], "agent-a")
        self.assertEqual(compact["studioRevision"], 1)
        self.assertEqual(compact["baselineHash"], compact["baseHash"])
        self.assertNotIn("payload", compact)


if __name__ == "__main__":
    unittest.main()
