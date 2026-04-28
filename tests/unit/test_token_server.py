"""
tests/unit/test_token_server.py – Unit tests for the token server.
"""
import base64
import hashlib
import hmac
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add token_server to path
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "token_server"
    ),
)


class TestBuildToken(unittest.TestCase):
    """Test the Agora token builder in server.py."""

    def setUp(self):
        # Patch firebase init so importing server.py doesn't crash
        firestore_patcher = patch("firebase_admin.firestore.client", return_value=MagicMock())
        storage_patcher = patch("firebase_admin.storage.bucket", return_value=MagicMock())
        get_app_patcher = patch("firebase_admin.get_app", return_value=MagicMock())
        init_app_patcher = patch("firebase_admin.initialize_app")
        fs_client_patcher = patch("firestore_client.FirestoreClient.__init__", return_value=None)
        auth_mw_patcher = patch("auth_middleware.init_firebase")

        for p in [firestore_patcher, storage_patcher, get_app_patcher,
                  init_app_patcher, fs_client_patcher, auth_mw_patcher]:
            p.start()
            self.addCleanup(p.stop)

    def _import_build_token(self):
        import importlib
        import server as srv
        importlib.reload(srv)  # ensure fresh import after patching
        return srv._build_token

    def test_token_is_base64url(self):
        from server import _build_token

        tok = _build_token("appid", "cert", "channel", "uid123", 3600)
        # Must be valid base64url
        decoded = base64.urlsafe_b64decode(tok + "==")
        self.assertIn(b"appid:channel:uid123:", decoded)

    def test_token_contains_expected_payload(self):
        from server import _build_token

        before = int(time.time())
        tok = _build_token("APP", "CERT", "CH", "U", 60)
        after = int(time.time())
        decoded = base64.urlsafe_b64decode(tok + "==")
        payload_part = decoded.split(b".")[0].decode("utf-8")
        parts = payload_part.split(":")
        self.assertEqual(parts[0], "APP")
        self.assertEqual(parts[1], "CH")
        self.assertEqual(parts[2], "U")
        expire_ts = int(parts[3])
        self.assertGreaterEqual(expire_ts, before + 60)
        self.assertLessEqual(expire_ts, after + 60)

    def test_token_hmac_is_correct(self):
        from server import _build_token

        app_id, cert, channel, uid, ttl = "A", "S", "C", "U", 10
        tok = _build_token(app_id, cert, channel, uid, ttl)
        decoded = base64.urlsafe_b64decode(tok + "==")
        # Split on first '.'
        dot_idx = decoded.index(b".")
        payload_bytes = decoded[:dot_idx]
        sig = decoded[dot_idx + 1:]
        expected_sig = hmac.new(
            cert.encode(), payload_bytes, hashlib.sha256
        ).digest()
        self.assertEqual(sig, expected_sig)


class TestFirestoreClient(unittest.TestCase):
    @patch("firebase_admin.get_app", return_value=MagicMock())
    @patch("firebase_admin.firestore.client")
    def test_get_channel_participants_empty(self, mock_client, mock_get_app):
        from firestore_client import FirestoreClient

        snap = MagicMock()
        snap.exists = False
        mock_client.return_value.collection.return_value.document.return_value.get.return_value = snap
        fc = FirestoreClient.__new__(FirestoreClient)
        fc.db = mock_client.return_value
        result = fc.get_channel_participants("ch1")
        self.assertEqual(result, [])

    @patch("firebase_admin.get_app", return_value=MagicMock())
    @patch("firebase_admin.firestore.client")
    def test_get_channel_participants_returns_list(self, mock_client, mock_get_app):
        from firestore_client import FirestoreClient

        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = {"participants": ["u1", "u2"]}
        mock_client.return_value.collection.return_value.document.return_value.get.return_value = snap
        fc = FirestoreClient.__new__(FirestoreClient)
        fc.db = mock_client.return_value
        result = fc.get_channel_participants("ch1")
        self.assertEqual(result, ["u1", "u2"])


if __name__ == "__main__":
    unittest.main()
