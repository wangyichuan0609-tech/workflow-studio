"""Connection helpers that never expose long-lived credentials to the browser."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional


_OFFICIAL_AUTH_URL = re.compile(
    r"https://(?:[A-Za-z0-9-]+\.)?(?:openai\.com|chatgpt\.com)(?:/[^\s]*)?",
    re.IGNORECASE,
)
_DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4,10}(?:-[A-Z0-9]{4,10})+\b")


class CodexDeviceAuthManager:
    """Run one bounded Codex device-auth flow and expose only URL/code/status."""

    def __init__(
        self,
        codex_path: str,
        authenticated: Callable[[], bool],
        *,
        timeout_seconds: int = 600,
    ):
        self.codex_path = codex_path
        self.authenticated = authenticated
        self.timeout_seconds = timeout_seconds
        self._lock = threading.RLock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._processes: Dict[str, subprocess.Popen[str]] = {}
        self._timers: Dict[str, threading.Timer] = {}

    @staticmethod
    def _public(job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: job.get(key)
            for key in (
                "jobId",
                "status",
                "verificationUrl",
                "userCode",
                "message",
                "error",
                "startedAt",
                "updatedAt",
            )
            if job.get(key) is not None
        }

    def start(self) -> Dict[str, Any]:
        if not self.codex_path or not Path(self.codex_path).exists():
            raise ValueError("未安装 Codex CLI。")
        with self._lock:
            for job in self._jobs.values():
                if job.get("status") in {"starting", "pending"}:
                    return self._public(job)
            job_id = uuid.uuid4().hex
            now = time.time()
            job = {
                "jobId": job_id,
                "status": "starting",
                "message": "正在启动 OpenAI 官方设备码登录…",
                "startedAt": now,
                "updatedAt": now,
            }
            self._jobs[job_id] = job
            try:
                process = subprocess.Popen(
                    [self.codex_path, "login", "--device-auth"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
            except OSError as error:
                job.update(
                    status="failed",
                    error=f"无法启动 Codex 登录：{error}",
                    message="Codex 登录未启动。",
                    updatedAt=time.time(),
                )
                return self._public(job)
            self._processes[job_id] = process
            timer = threading.Timer(self.timeout_seconds, self._timeout, args=(job_id,))
            timer.daemon = True
            self._timers[job_id] = timer
            timer.start()
            thread = threading.Thread(
                target=self._read_process,
                args=(job_id, process),
                name=f"codex-device-auth-{job_id[:8]}",
                daemon=True,
            )
            thread.start()
            return self._public(job)

    def _read_process(self, job_id: str, process: subprocess.Popen[str]) -> None:
        try:
            stream = process.stdout
            if stream is not None:
                for raw_line in stream:
                    line = raw_line.strip()
                    if not line:
                        continue
                    url_match = _OFFICIAL_AUTH_URL.search(line)
                    code_match = _DEVICE_CODE.search(line)
                    with self._lock:
                        job = self._jobs.get(job_id)
                        if job is None or job.get("status") not in {"starting", "pending"}:
                            continue
                        if url_match:
                            job["verificationUrl"] = url_match.group(0).rstrip(".,)")
                        if code_match:
                            job["userCode"] = code_match.group(0)
                        if url_match or code_match:
                            job["status"] = "pending"
                            job["message"] = "请在 OpenAI 官方页面输入一次性设备码。"
                        job["updatedAt"] = time.time()
            return_code = process.wait()
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None or job.get("status") not in {"starting", "pending"}:
                    return
                if return_code == 0 and self.authenticated():
                    job.update(
                        status="succeeded",
                        message="Codex 官方登录已完成。",
                        error=None,
                        updatedAt=time.time(),
                    )
                else:
                    job.update(
                        status="failed",
                        message="Codex 登录未完成。",
                        error="OpenAI 官方设备码登录失败或已过期。",
                        updatedAt=time.time(),
                    )
        finally:
            with self._lock:
                timer = self._timers.pop(job_id, None)
                if timer is not None:
                    timer.cancel()
                self._processes.pop(job_id, None)

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if hasattr(os, "killpg"):
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except (OSError, ProcessLookupError):
            try:
                process.terminate()
            except OSError:
                pass

    def _timeout(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.get("status") not in {"starting", "pending"}:
                return
            process = self._processes.get(job_id)
            job.update(
                status="timed_out",
                message="设备码登录已超时。",
                error="请重新启动登录并使用新的设备码。",
                updatedAt=time.time(),
            )
        if process is not None:
            self._stop_process(process)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public(job) if job is not None else None

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            process = self._processes.get(job_id)
            if job.get("status") in {"starting", "pending"}:
                job.update(
                    status="cancelled",
                    message="设备码登录已取消。",
                    error=None,
                    updatedAt=time.time(),
                )
        if process is not None:
            self._stop_process(process)
        return self.get(job_id)

    def shutdown(self) -> None:
        with self._lock:
            active = list(self._processes.items())
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()
        for _job_id, process in active:
            self._stop_process(process)
