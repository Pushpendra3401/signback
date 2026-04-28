"""
tests/integration/test_endpoints.py – Integration tests for AI & Token servers.

These tests spin up the Flask test clients directly (no HTTP).
They mock Firebase auth so no real credentials are needed.
"""
import base64
import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── Patch paths before any server import ──────────────────────────────────────
AI_SERVER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ai_server"
)
TOKEN_SERVER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "token_server"
)


def _make_auth_header(uid: str = "test-uid") -> dict:
    return {"Authorization": f"Bearer fake-token-for-{uid}"}


# ══════════════════════════════════════════════════════════════════════════════
# AI Server integration tests
# ══════════════════════════════════════════════════════════════════════════════
@patch.dict(
    os.environ,
    {
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "FIREBASE_PROJECT_ID": "test-project",
        "FIREBASE_STORAGE_BUCKET": "test-project.appspot.com",
    },
)
class TestAIServerEndpoints(unittest.TestCase):
    def setUp(self):
        # Insert path so we can import ai_server modules
        if AI_SERVER_PATH not in sys.path:
            sys.path.insert(0, AI_SERVER_PATH)

        # Patch Firebase before importing main
        self.firebase_mock = patch("firebase_admin.initialize_app").start()
        self.get_app_mock = patch("firebase_admin.get_app").start()
        self.verify_mock = patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"uid": "test-uid"},
        ).start()

        import main as ai_main
        ai_main.app.testing = True
        self.client = ai_main.app.test_client()

    def tearDown(self):
        patch.stopall()

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")

    def test_ready(self):
        resp = self.client.get("/ready")
        self.assertEqual(resp.status_code, 200)

    def test_translate_missing_body_returns_400(self):
        resp = self.client.post(
            "/translate",
            json={},
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 400)

    def test_translate_success(self):
        resp = self.client.post(
            "/translate",
            json={"text": "Hello", "source_lang": "en", "target_lang": "es"},
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("translated_text", data)

    def test_text_to_sign_success(self):
        resp = self.client.post(
            "/text-to-sign",
            json={"text": "Hello World", "locale": "en-US"},
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("sign_sequence", data)
        self.assertIsInstance(data["sign_sequence"], list)

    def test_text_to_sign_missing_text(self):
        resp = self.client.post(
            "/text-to-sign",
            json={},
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 400)

    def test_speech_to_text_no_audio(self):
        resp = self.client.post(
            "/speech-to-text",
            data=b"",
            content_type="audio/wav",
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 400)

    @patch("main.generate_speech", return_value=b"AUDIO")
    @patch("main.get_audio_content_type", return_value="audio/wav")
    def test_tts_success(self, mock_ct, mock_speech):
        resp = self.client.post(
            "/tts",
            json={"text": "Hello"},
            headers=_make_auth_header(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"AUDIO")

    def test_unauthenticated_returns_401(self):
        resp = self.client.post("/translate", json={"text": "hi"})
        self.assertEqual(resp.status_code, 401)


# ══════════════════════════════════════════════════════════════════════════════
# Token Server integration tests
# ══════════════════════════════════════════════════════════════════════════════
class TestTokenServerEndpoints(unittest.TestCase):
    def setUp(self):
        if TOKEN_SERVER_PATH not in sys.path:
            sys.path.insert(0, TOKEN_SERVER_PATH)

        self.mock_firebase = patch("firebase_admin.initialize_app").start()
        self.mock_get_app = patch("firebase_admin.get_app").start()
        self.mock_verify = patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"uid": "caller-uid"},
        ).start()
        self.mock_fs = patch("firestore_client.FirestoreClient").start()
        self.mock_fs_instance = self.mock_fs.return_value
        self.mock_fs_instance.get_channel_participants.return_value = ["caller-uid", "other-uid"]
        self.mock_fs_instance.record_token_issued.return_value = None

        with patch.dict(
            os.environ,
            {
                "AGORA_APP_ID": "TEST_APP_ID",
                "AGORA_APP_CERTIFICATE": "TEST_CERT",
                "TOKEN_TTL_SECONDS": "3600",
            },
        ):
            import server as token_srv
            token_srv.app.testing = True
            self.client = token_srv.app.test_client()

    def tearDown(self):
        patch.stopall()

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_token_missing_fields(self):
        resp = self.client.post(
            "/token",
            json={},
            headers=_make_auth_header("caller-uid"),
        )
        self.assertEqual(resp.status_code, 400)

    def test_token_success(self):
        with patch.dict(
            os.environ,
            {"AGORA_APP_ID": "APP", "AGORA_APP_CERTIFICATE": "CERT"},
        ):
            resp = self.client.post(
                "/token",
                json={"channelId": "ch1", "uid": "caller-uid"},
                headers=_make_auth_header("caller-uid"),
            )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("token", data)
        self.assertIn("expiresIn", data)


if __name__ == "__main__":
    unittest.main()
