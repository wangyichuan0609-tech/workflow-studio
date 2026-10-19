import copy
import threading
import time
import unittest

from agent_test_jobs import AgentTestManager, AgentTestQueueFull


class FakeStore:
    def __init__(self, jobs=None):
        self._lock = threading.RLock()
        self.jobs = {
            job["jobId"]: copy.deepcopy(job)
            for job in (jobs or [])
        }

    def create_test_job(self, job):
        with self._lock:
            self.jobs[job["jobId"]] = copy.deepcopy(job)
            return copy.deepcopy(job)

    def update_test_job(self, job_id, updates):
        with self._lock:
            self.jobs[job_id].update(copy.deepcopy(updates))
            return copy.deepcopy(self.jobs[job_id])

    def get_test_job(self, job_id):
        with self._lock:
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job is not None else None

    def list_test_jobs(self, project_id=None, agent_id=None):
        with self._lock:
            return [
                copy.deepcopy(job)
                for job in self.jobs.values()
                if (project_id is None or job["projectId"] == project_id)
                and (agent_id is None or job["agentId"] == agent_id)
            ]

    def interrupt_unfinished_test_jobs(self):
        with self._lock:
            for job in self.jobs.values():
                if job.get("status") in {"queued", "running"}:
                    job.update(
                        status="interrupted",
                        passed=False,
                        summary="Interrupted by service restart.",
                    )


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.005)
    raise AssertionError("condition was not reached before timeout")


class AgentTestManagerTests(unittest.TestCase):
    def test_start_returns_immediately_and_persists_completed_result(self):
        store = FakeStore()
        release = threading.Event()

        def executor(job, payload):
            release.wait(2)
            return {"passed": True, "summary": f"loaded {payload['input']}"}

        manager = AgentTestManager(store, executor)
        started = time.monotonic()
        job = manager.start("project", "agent", "Agent", "rev-1", {"input": "hello"})
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.2)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["draftHash"], "rev-1")
        release.set()
        completed = wait_for(
            lambda: (
                current
                if (current := manager.get(job["jobId"]))["status"] == "passed"
                else None
            )
        )
        self.assertTrue(completed["passed"])
        self.assertEqual(completed["summary"], "loaded hello")
        self.assertGreaterEqual(completed["durationMs"], 0)
        manager.shutdown(wait=True)

    def test_same_agent_revision_is_deduplicated_while_unfinished(self):
        release = threading.Event()
        calls = []

        def executor(job, payload):
            calls.append(job["jobId"])
            release.wait(2)
            return True

        manager = AgentTestManager(FakeStore(), executor)
        first = manager.start("p", "a", "Agent", "same", {})
        duplicate = manager.start("p", "a", "Agent", "same", {"different": True})
        newer = manager.start("p", "a", "Agent", "new", {})
        self.assertEqual(first["jobId"], duplicate["jobId"])
        self.assertNotEqual(first["jobId"], newer["jobId"])
        release.set()
        wait_for(lambda: all(job["status"] == "passed" for job in manager.list()))
        self.assertEqual(len(calls), 2)
        manager.shutdown(wait=True)

    def test_never_runs_more_than_two_and_bounds_pending_queue(self):
        store = FakeStore()
        release = threading.Event()
        two_running = threading.Event()
        guard = threading.Lock()
        active = 0
        maximum = 0

        def executor(job, payload):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
                if active == 2:
                    two_running.set()
            release.wait(2)
            with guard:
                active -= 1
            return True

        manager = AgentTestManager(store, executor, max_workers=2, max_queue=8)
        manager.start("p", "a-0", "Agent", "r", {})
        manager.start("p", "a-1", "Agent", "r", {})
        self.assertTrue(two_running.wait(1))
        for index in range(2, 10):
            manager.start("p", f"a-{index}", "Agent", "r", {})
        with self.assertRaises(AgentTestQueueFull):
            manager.start("p", "overflow", "Agent", "r", {})
        self.assertEqual(maximum, 2)
        release.set()
        wait_for(lambda: all(job["status"] == "passed" for job in manager.list()))
        self.assertEqual(maximum, 2)
        manager.shutdown(wait=True)

    def test_executor_exception_fails_one_job_without_killing_worker(self):
        def executor(job, payload):
            if payload["fail"]:
                raise RuntimeError("boom")
            return {"passed": True, "summary": "recovered"}

        manager = AgentTestManager(FakeStore(), executor, max_workers=1)
        failed = manager.start("p", "bad", "Bad", "r", {"fail": True})
        wait_for(lambda: manager.get(failed["jobId"])["status"] == "failed")
        passed = manager.start("p", "good", "Good", "r", {"fail": False})
        completed = wait_for(
            lambda: (
                current
                if (current := manager.get(passed["jobId"]))["status"] == "passed"
                else None
            )
        )
        self.assertEqual(completed["summary"], "recovered")
        self.assertIn("RuntimeError: boom", manager.get(failed["jobId"])["summary"])
        manager.shutdown(wait=True)

    def test_cancel_removes_queued_job_and_does_not_execute_it(self):
        release = threading.Event()
        first_running = threading.Event()
        executed = []

        def executor(job, payload):
            executed.append(job["agentId"])
            first_running.set()
            release.wait(2)
            return True

        manager = AgentTestManager(FakeStore(), executor, max_workers=1, max_queue=1)
        first = manager.start("p", "first", "First", "r", {})
        self.assertTrue(first_running.wait(1))
        queued = manager.start("p", "queued", "Queued", "r", {})
        cancelled = manager.cancel(queued["jobId"])
        self.assertEqual(cancelled["status"], "cancelled")
        replacement = manager.start("p", "replacement", "Replacement", "r", {})
        release.set()
        wait_for(lambda: manager.get(first["jobId"])["status"] == "passed")
        wait_for(lambda: manager.get(replacement["jobId"])["status"] == "passed")
        self.assertNotIn("queued", executed)
        manager.shutdown(wait=True)

    def test_initialisation_marks_previous_unfinished_jobs_interrupted(self):
        old_jobs = [
            {
                "jobId": "queued",
                "projectId": "p",
                "agentId": "a",
                "resourceRevision": "r1",
                "status": "queued",
            },
            {
                "jobId": "running",
                "projectId": "p",
                "agentId": "b",
                "resourceRevision": "r2",
                "status": "running",
            },
            {
                "jobId": "done",
                "projectId": "p",
                "agentId": "c",
                "resourceRevision": "r3",
                "status": "passed",
            },
        ]
        store = FakeStore(old_jobs)
        manager = AgentTestManager(store, lambda job, payload: True)
        self.assertEqual(manager.get("queued")["status"], "interrupted")
        self.assertEqual(manager.get("running")["status"], "interrupted")
        self.assertEqual(manager.get("done")["status"], "passed")
        manager.shutdown(wait=True)

    def test_timeout_exception_records_timed_out(self):
        manager = AgentTestManager(
            FakeStore(), lambda job, payload: (_ for _ in ()).throw(TimeoutError("late"))
        )
        job = manager.start("p", "a", "Agent", "r", {})
        completed = wait_for(
            lambda: (
                current
                if (current := manager.get(job["jobId"]))["status"] == "timed_out"
                else None
            )
        )
        self.assertFalse(completed["passed"])
        manager.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
