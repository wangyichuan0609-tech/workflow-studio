"""Small, dependency-free background queue for Agent smoke tests.

The manager deliberately knows nothing about HTTP or SQLite.  Its store is a
duck-typed object with ``create_test_job``, ``update_test_job``,
``get_test_job``, ``list_test_jobs`` and ``interrupt_unfinished_test_jobs``
methods.  This keeps the queue usable by the server without coupling worker
threads to a particular persistence implementation.
"""

from __future__ import annotations

import copy
import inspect
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, Iterable, List, Mapping, Optional, Tuple


UNFINISHED_STATUSES = frozenset({"queued", "running"})
TERMINAL_STATUSES = frozenset(
    {"passed", "failed", "timed_out", "cancelled", "interrupted"}
)


class AgentTestQueueFull(RuntimeError):
    """Raised when all worker and pending queue capacity is in use."""


class AgentTestManagerClosed(RuntimeError):
    """Raised when a job is submitted after manager shutdown."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AgentTestManager:
    """Persist and execute Agent smoke tests on a bounded daemon worker pool.

    ``executor`` receives ``(job, payload)`` and should return either a mapping
    containing ``passed``/``summary`` (or ``status``), or a boolean.  Timeouts
    enforced by the executor can be reported with ``status='timed_out'``,
    ``timedOut=True``, or by raising ``TimeoutError``.  The manager itself does
    not spawn an unkillable extra thread to impose a timeout, so the configured
    worker limit is also the real executor concurrency limit.
    """

    def __init__(
        self,
        store: Any,
        executor: Callable[[Dict[str, Any], Any], Any],
        *,
        max_workers: int = 2,
        max_queue: int = 8,
        id_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if max_queue < 1:
            raise ValueError("max_queue must be at least 1")
        if not callable(executor):
            raise TypeError("executor must be callable")

        self.store = store
        self.executor = executor
        self.max_workers = max_workers
        self.max_queue = max_queue
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._condition = threading.Condition(threading.RLock())
        self._pending: Deque[Tuple[str, Any]] = deque()
        self._closed = False

        # Jobs left queued/running belong to a previous process and cannot be
        # resumed because their in-memory executor payload is intentionally not
        # persisted.  Make that state explicit before accepting new work.
        self.store.interrupt_unfinished_test_jobs()

        self._workers = [
            threading.Thread(
                target=self._worker_loop,
                name=f"agent-test-{index + 1}",
                daemon=True,
            )
            for index in range(max_workers)
        ]
        for worker in self._workers:
            worker.start()

    def start(
        self,
        project_id: str,
        agent_id: str,
        agent_name: str,
        resource_revision: Any,
        payload: Any,
    ) -> Dict[str, Any]:
        """Persist and enqueue a job, returning without waiting for execution.

        A queued/running job for the same project, Agent and draft revision is
        returned as-is.  The pending queue holds at most ``max_queue`` jobs in
        addition to the jobs already executing on workers.
        """

        project_id = str(project_id or "").strip()
        agent_id = str(agent_id or "").strip()
        if not project_id or not agent_id:
            raise ValueError("project_id and agent_id are required")
        if resource_revision is None or resource_revision == "":
            raise ValueError("resource_revision is required")

        with self._condition:
            if self._closed:
                raise AgentTestManagerClosed("Agent test manager is closed")

            duplicate = self._find_duplicate(
                project_id, agent_id, resource_revision
            )
            if duplicate is not None:
                return duplicate
            if len(self._pending) >= self.max_queue:
                raise AgentTestQueueFull(
                    f"Agent test queue is full ({self.max_queue} pending jobs)"
                )

            job_id = str(self._id_factory())
            created_at = _utc_now()
            job = {
                "jobId": job_id,
                "projectId": project_id,
                "agentId": agent_id,
                "agentName": str(agent_name or agent_id),
                "resourceRevision": resource_revision,
                # Both aliases are persisted so callers can invalidate a test
                # after edits without depending on one revision vocabulary.
                "testedRevision": resource_revision,
                "draftHash": resource_revision,
                "status": "queued",
                "passed": None,
                "summary": "",
                "durationMs": 0,
                "createdAt": created_at,
                "startedAt": None,
                "completedAt": None,
            }
            created = self._store_create(job)
            self._pending.append((job_id, copy.deepcopy(payload)))
            self._condition.notify()
            return copy.deepcopy(created)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.store.get_test_job(str(job_id))
        return copy.deepcopy(job) if isinstance(job, Mapping) else None

    def list(
        self,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return [
            copy.deepcopy(job)
            for job in self._store_list(project_id=project_id, agent_id=agent_id)
        ]

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Cancel queued work or mark running work cancelled, without waiting."""

        job_id = str(job_id)
        with self._condition:
            job = self.store.get_test_job(job_id)
            if not isinstance(job, Mapping):
                return None
            if job.get("status") in TERMINAL_STATUSES:
                return copy.deepcopy(dict(job))

            # Removing a queued item immediately releases queue capacity.  A
            # running executor cannot be killed safely, but its eventual result
            # is ignored because the persisted state is already terminal.
            for index, (pending_id, _payload) in enumerate(self._pending):
                if pending_id == job_id:
                    del self._pending[index]
                    break
            updated = self._store_update(
                job_id,
                {
                    "status": "cancelled",
                    "passed": False,
                    "summary": "Agent test cancelled.",
                    "completedAt": _utc_now(),
                },
            )
            self._condition.notify_all()
            return updated

    def shutdown(self, wait: bool = False, cancel_pending: bool = True) -> None:
        """Stop accepting jobs; optionally cancel queued jobs and join workers."""

        with self._condition:
            if not self._closed:
                self._closed = True
                if cancel_pending:
                    pending_ids = [job_id for job_id, _payload in self._pending]
                    self._pending.clear()
                    for job_id in pending_ids:
                        try:
                            self._store_update(
                                job_id,
                                {
                                    "status": "cancelled",
                                    "passed": False,
                                    "summary": "Agent test cancelled during shutdown.",
                                    "completedAt": _utc_now(),
                                },
                            )
                        except Exception:
                            # Shutdown must remain best-effort and non-blocking
                            # even if persistence has become unavailable.
                            pass
                self._condition.notify_all()
        if wait:
            for worker in self._workers:
                worker.join()

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._pending and not self._closed:
                    self._condition.wait()
                if not self._pending:
                    return
                job_id, payload = self._pending.popleft()
                try:
                    current = self.store.get_test_job(job_id)
                    if not isinstance(current, Mapping) or current.get("status") != "queued":
                        continue
                    job = self._store_update(
                        job_id,
                        {"status": "running", "startedAt": _utc_now()},
                    )
                except Exception:
                    # A persistence error for one item must not terminate a
                    # long-lived worker and strand all later queue entries.
                    continue

            started = time.monotonic()
            try:
                result = self.executor(copy.deepcopy(job), payload)
                status, summary = self._normalise_result(result)
            except TimeoutError as error:
                status = "timed_out"
                summary = str(error).strip() or "Agent 测试超时。"
            except Exception as error:
                # subprocess.TimeoutExpired is intentionally recognised without
                # importing subprocess or constraining executor implementations.
                if error.__class__.__name__ == "TimeoutExpired":
                    status = "timed_out"
                    summary = str(error).strip() or "Agent 测试超时。"
                else:
                    status = "failed"
                    detail = str(error).strip()
                    summary = error.__class__.__name__ + (f": {detail}" if detail else "")
            duration_ms = max(0, int((time.monotonic() - started) * 1000))

            with self._condition:
                try:
                    current = self.store.get_test_job(job_id)
                    if not isinstance(current, Mapping):
                        continue
                    if current.get("status") in TERMINAL_STATUSES:
                        # A concurrent cancel wins over a late executor result.
                        continue
                    self._store_update(
                        job_id,
                        {
                            "status": status,
                            "passed": status == "passed",
                            "summary": summary[:4000],
                            "durationMs": duration_ms,
                            "completedAt": _utc_now(),
                        },
                    )
                except Exception:
                    # Keep the worker alive.  The next process startup will
                    # convert a record stuck in running state to interrupted.
                    continue

    @staticmethod
    def _normalise_result(result: Any) -> Tuple[str, str]:
        if isinstance(result, Mapping):
            requested_status = str(result.get("status") or "").strip().lower()
            if requested_status in TERMINAL_STATUSES:
                status = requested_status
            elif result.get("timedOut") or result.get("timed_out"):
                status = "timed_out"
            else:
                status = "passed" if bool(result.get("passed")) else "failed"
            summary = str(
                result.get("summary")
                or result.get("output")
                or result.get("message")
                or ("Agent test passed." if status == "passed" else "Agent test failed.")
            ).strip()
            return status, summary
        if isinstance(result, bool):
            return (
                ("passed", "Agent test passed.")
                if result
                else ("failed", "Agent test failed.")
            )
        return "failed", "Agent test executor returned an invalid result."

    def _find_duplicate(
        self, project_id: str, agent_id: str, resource_revision: Any
    ) -> Optional[Dict[str, Any]]:
        for job in self._store_list(project_id=project_id, agent_id=agent_id):
            revision = job.get("resourceRevision", job.get("testedRevision"))
            if revision == resource_revision and job.get("status") in UNFINISHED_STATUSES:
                return copy.deepcopy(job)
        return None

    def _store_create(self, job: Dict[str, Any]) -> Dict[str, Any]:
        result = self.store.create_test_job(copy.deepcopy(job))
        if isinstance(result, Mapping):
            return dict(result)
        persisted = self.store.get_test_job(job["jobId"])
        return dict(persisted) if isinstance(persisted, Mapping) else copy.deepcopy(job)

    def _store_update(self, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        method = self.store.update_test_job
        parameters = list(inspect.signature(method).parameters.values())
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if accepts_kwargs:
            result = method(job_id, **copy.deepcopy(updates))
        else:
            result = method(job_id, copy.deepcopy(updates))
        if isinstance(result, Mapping):
            return dict(result)
        persisted = self.store.get_test_job(job_id)
        if not isinstance(persisted, Mapping):
            raise KeyError(f"Agent test job not found: {job_id}")
        return dict(persisted)

    def _store_list(
        self,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        method = self.store.list_test_jobs
        parameters = inspect.signature(method).parameters
        kwargs: Dict[str, Any] = {}
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if project_id is not None:
            if accepts_kwargs or "project_id" in parameters:
                kwargs["project_id"] = project_id
            elif "projectId" in parameters:
                kwargs["projectId"] = project_id
        if agent_id is not None:
            if accepts_kwargs or "agent_id" in parameters:
                kwargs["agent_id"] = agent_id
            elif "agentId" in parameters:
                kwargs["agentId"] = agent_id
        result = method(**kwargs) if kwargs else method()
        if isinstance(result, Mapping):
            result = result.get("jobs", [])
        jobs: Iterable[Any] = result or []
        return [
            dict(job)
            for job in jobs
            if isinstance(job, Mapping)
            and (project_id is None or job.get("projectId") == project_id)
            and (agent_id is None or job.get("agentId") == agent_id)
        ]

