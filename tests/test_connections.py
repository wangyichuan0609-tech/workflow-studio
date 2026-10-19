from __future__ import annotations

import json
import stat
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from server import OpenAIAssistant
from studio_state import StudioState


def models_response(*model_ids: str) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(
        {"data": [{"id": model_id} for model_id in model_ids]}
    ).encode()
    response.__enter__.return_value = response
    return response


class ConnectionCenterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = StudioState(self.root / "app-data" / "state.sqlite3")
        self.config = self.state.path.parent / "connections.json"

    def tearDown(self):
        self.state.close()
        self.temporary.cleanup()

    @patch.object(OpenAIAssistant, "_open_model_catalog")
    @patch.object(OpenAIAssistant, "_codex_is_authenticated", return_value=False)
    def test_session_key_disappears_after_restart_and_saved_key_is_private(
        self, _authenticated, open_model_catalog
    ):
        open_model_catalog.return_value = models_response("model-a")
        assistant = OpenAIAssistant(config_path=self.config, state=self.state)
        result = assistant.save_config(
            {
                "apiKey": "session-secret",
                "baseUrl": "https://models.example/v1",
                "model": "model-a",
                "saveLocally": False,
            }
        )
        self.assertTrue(result["status"]["configured"])
        self.assertFalse(self.config.exists())
        self.assertNotIn("session-secret", json.dumps(result))

        restarted = OpenAIAssistant(config_path=self.config, state=self.state)
        self.assertFalse(restarted.public_config()["hasApiKey"])

        saved = restarted.save_config(
            {
                "apiKey": "saved-secret",
                "baseUrl": "https://models.example/v1",
                "model": "model-a",
                "saveLocally": True,
            }
        )
        self.assertTrue(self.config.exists())
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertNotIn("saved-secret", json.dumps(saved))

        session_only = restarted.save_config(
            {
                "apiKey": "",
                "baseUrl": "https://models.example/v1",
                "model": "model-a",
                "saveLocally": False,
            }
        )
        self.assertTrue(session_only["status"]["configured"])
        self.assertTrue(self.config.exists())
        self.assertNotIn("api_key", json.loads(self.config.read_text(encoding="utf-8")))
        self.assertEqual(session_only["config"]["credentialSource"], "session")
        self.assertFalse(session_only["config"]["savedLocally"])

        forgotten = restarted.forget_saved_api_key()
        self.assertFalse(forgotten["config"]["hasApiKey"])
        self.assertNotIn("saved-secret", json.dumps(forgotten))

    @patch.object(OpenAIAssistant, "_open_model_catalog")
    @patch.object(OpenAIAssistant, "_codex_is_authenticated", return_value=True)
    def test_both_providers_require_a_choice_and_failure_never_falls_back(
        self, _authenticated, open_model_catalog
    ):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            json.dumps(
                {
                    "api_key": "saved-secret",
                    "base_url": "https://models.example/v1",
                    "model": "model-a",
                }
            ),
            encoding="utf-8",
        )
        open_model_catalog.return_value = models_response("model-a")
        assistant = OpenAIAssistant(config_path=self.config, state=self.state)
        status = assistant.connection_status()
        self.assertIsNone(status["activeProvider"])
        self.assertFalse(status["configured"])

        selected = assistant.set_active_provider("api")
        self.assertEqual(selected["activeProvider"], "api")
        self.assertTrue(selected["configured"])
        open_model_catalog.side_effect = urllib.error.URLError("offline")
        assistant._health_fingerprint = None
        failed = assistant.connection_status()
        self.assertEqual(failed["activeProvider"], "api")
        self.assertEqual(failed["provider"], "OpenAI-compatible API")
        self.assertFalse(failed["connected"])
        self.assertTrue(failed["providers"]["codex"]["connected"])

    @patch.object(OpenAIAssistant, "_codex_is_authenticated", return_value=False)
    def test_model_discovery_rejects_redirect_without_forwarding_api_key(
        self, _authenticated
    ):
        redirected_requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_GET(self):  # noqa: N802
                if self.path == "/v1/models":
                    self.send_response(302)
                    self.send_header("Location", "/redirected")
                    self.end_headers()
                    return
                redirected_requests.append(
                    {"path": self.path, "authorization": self.headers.get("Authorization")}
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data": [{"id": "should-not-be-reached"}]}')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assistant = OpenAIAssistant(config_path=self.config, state=self.state)
            with self.assertRaisesRegex(ValueError, "HTTP 302"):
                assistant.list_models(
                    {
                        "apiKey": "redirect-secret",
                        "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                    }
                )
            self.assertEqual(redirected_requests, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(1)

    @patch("server.shutil.which", return_value="/bin/echo")
    @patch("server.subprocess.run", return_value=SimpleNamespace(returncode=0))
    def test_codex_manual_model_is_separate_from_api_model(self, _run, _which):
        assistant = OpenAIAssistant(config_path=self.config, state=self.state)
        status = assistant.configure_codex({"modelId": "gpt-custom", "activate": True})
        self.assertEqual(status["activeProvider"], "codex")
        self.assertEqual(status["providers"]["codex"]["model"], "gpt-custom")
        self.assertEqual(self.state.get_setting("connections.codex_model"), "gpt-custom")


if __name__ == "__main__":
    unittest.main()
