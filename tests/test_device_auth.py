from __future__ import annotations

import io
import json
import time
import unittest
from unittest.mock import patch

from connections import CodexDeviceAuthManager


class _CompletedProcess:
    def __init__(self, output: str, return_code: int):
        self.stdout = io.StringIO(output)
        self.return_code = return_code
        self.pid = 424242

    def wait(self):
        return self.return_code

    def poll(self):
        return self.return_code

    def terminate(self):
        return None


class _ActiveProcess:
    pid = 434343

    def poll(self):
        return None

    def terminate(self):
        return None


class CodexDeviceAuthManagerTests(unittest.TestCase):
    def wait_for_terminal(self, manager: CodexDeviceAuthManager, job_id: str):
        for _ in range(100):
            job = manager.get(job_id)
            if job and job.get("status") not in {"starting", "pending"}:
                return job
            time.sleep(0.01)
        self.fail("Device authorization job did not finish.")

    @patch("connections.subprocess.Popen")
    def test_success_exposes_only_official_url_code_and_status(self, popen):
        popen.return_value = _CompletedProcess(
            "Open https://auth.openai.com/codex/device and enter ABCD-EFGH\n"
            "access_token=must-not-leak sk-secret-must-not-leak\n",
            0,
        )
        manager = CodexDeviceAuthManager("/bin/echo", lambda: True)
        started = manager.start()
        result = self.wait_for_terminal(manager, started["jobId"])

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["verificationUrl"], "https://auth.openai.com/codex/device")
        self.assertEqual(result["userCode"], "ABCD-EFGH")
        public_json = json.dumps(result)
        self.assertNotIn("access_token", public_json)
        self.assertNotIn("sk-secret", public_json)

    @patch("connections.subprocess.Popen")
    def test_nonzero_exit_is_a_redacted_failure(self, popen):
        popen.return_value = _CompletedProcess(
            "https://auth.openai.com/codex/device WXYZ-1234 password=hunter2\n",
            1,
        )
        manager = CodexDeviceAuthManager("/bin/echo", lambda: False)
        started = manager.start()
        result = self.wait_for_terminal(manager, started["jobId"])

        self.assertEqual(result["status"], "failed")
        self.assertNotIn("hunter2", json.dumps(result))

    def test_cancel_stops_an_active_job(self):
        manager = CodexDeviceAuthManager("/bin/echo", lambda: False)
        process = _ActiveProcess()
        manager._jobs["cancel-job"] = {
            "jobId": "cancel-job",
            "status": "pending",
            "startedAt": 1.0,
            "updatedAt": 1.0,
        }
        manager._processes["cancel-job"] = process

        with patch.object(manager, "_stop_process") as stop:
            result = manager.cancel("cancel-job")

        self.assertEqual(result["status"], "cancelled")
        stop.assert_called_once_with(process)

    def test_timeout_stops_an_active_job(self):
        manager = CodexDeviceAuthManager("/bin/echo", lambda: False)
        process = _ActiveProcess()
        manager._jobs["timeout-job"] = {
            "jobId": "timeout-job",
            "status": "pending",
            "startedAt": 1.0,
            "updatedAt": 1.0,
        }
        manager._processes["timeout-job"] = process

        with patch.object(manager, "_stop_process") as stop:
            manager._timeout("timeout-job")

        result = manager.get("timeout-job")
        self.assertEqual(result["status"], "timed_out")
        stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
