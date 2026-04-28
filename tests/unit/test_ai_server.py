"""
tests/unit/test_ai_server.py – Unit tests for the AI server modules.
"""
import base64
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── Add ai_server to path ──────────────────────────────────────────────────────
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ai_server"),
)


# ══════════════════════════════════════════════════════════════════════════════
# config.py
# ══════════════════════════════════════════════════════════════════════════════
class TestConfig(unittest.TestCase):
    def test_defaults(self):
        import config

        self.assertIsInstance(config.PORT, int)
        self.assertIsInstance(config.RATE_LIMIT_PER_MINUTE, int)
        self.assertGreater(config.PORT, 0)


# ══════════════════════════════════════════════════════════════════════════════
# voice_generator.py
# ══════════════════════════════════════════════════════════════════════════════
class TestVoiceGenerator(unittest.TestCase):
    def test_empty_text_raises(self):
        from voice_generator import generate_speech

        with self.assertRaises(ValueError):
            generate_speech("", backend="pyttsx3")

    def test_get_audio_content_type_gtts(self):
        from voice_generator import get_audio_content_type

        self.assertEqual(get_audio_content_type("gtts"), "audio/mpeg")

    def test_get_audio_content_type_pyttsx3(self):
        from voice_generator import get_audio_content_type

        self.assertEqual(get_audio_content_type("pyttsx3"), "audio/wav")

    @patch("voice_generator._synthesize_pyttsx3", return_value=b"FAKEAUDIO")
    def test_generate_speech_pyttsx3(self, mock_synth):
        from voice_generator import generate_speech

        result = generate_speech("hello", backend="pyttsx3")
        self.assertEqual(result, b"FAKEAUDIO")
        mock_synth.assert_called_once()

    @patch("voice_generator._synthesize_gtts", return_value=b"MP3DATA")
    def test_generate_speech_gtts(self, mock_synth):
        from voice_generator import generate_speech

        result = generate_speech("hello", backend="gtts")
        self.assertEqual(result, b"MP3DATA")
        mock_synth.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# gesture_detection.py – pure heuristic, no model needed
# ══════════════════════════════════════════════════════════════════════════════
class TestGestureDetection(unittest.TestCase):
    def _make_landmark(self, x: float, y: float, z: float = 0.0):
        lm = MagicMock()
        lm.x = x
        lm.y = y
        lm.z = z
        return lm

    def _make_landmarks(self, config: dict):
        """config maps index -> (x, y). Missing indices default to (0.5, 0.5)."""
        lms = [self._make_landmark(0.5, 0.5)] * 21
        for idx, (x, y) in config.items():
            lms[idx] = self._make_landmark(x, y)
        return lms

    def test_classify_fist(self):
        from gesture_detection import _classify_gesture

        # All fingers folded: tips BELOW pips (higher y value)
        lms = self._make_landmarks(
            {
                # thumb folded (tip.x > ip.x)
                3: (0.4, 0.5),
                4: (0.6, 0.5),
                # fingers folded: tip y > pip y
                6: (0.5, 0.3),
                8: (0.5, 0.5),
                10: (0.5, 0.3),
                12: (0.5, 0.5),
                14: (0.5, 0.3),
                16: (0.5, 0.5),
                18: (0.5, 0.3),
                20: (0.5, 0.5),
            }
        )
        # Create a mock hand_landmarks object
        mock_hand = MagicMock()
        mock_hand.landmark = lms
        result = _classify_gesture(mock_hand.landmark)
        self.assertIsInstance(result, str)

    def test_extract_landmark_list(self):
        from gesture_detection import _extract_landmark_list

        mock_hand = MagicMock()
        mock_hand.landmark = [self._make_landmark(0.1, 0.2, 0.3)] * 21
        result = _extract_landmark_list(mock_hand)
        self.assertEqual(len(result), 21)
        self.assertIn("x", result[0])
        self.assertIn("y", result[0])
        self.assertIn("z", result[0])


# ══════════════════════════════════════════════════════════════════════════════
# firebase_service.py – mock firebase_admin
# ══════════════════════════════════════════════════════════════════════════════
class TestFirebaseService(unittest.TestCase):
    def setUp(self):
        # Patch firebase_admin so we don't need real credentials
        self.firebase_patcher = patch("firebase_admin.get_app", return_value=MagicMock())
        self.firebase_patcher.start()
        self.firestore_patcher = patch("firebase_admin.firestore.client", return_value=MagicMock())
        self.firestore_patcher.start()
        self.storage_patcher = patch("firebase_admin.storage.bucket", return_value=MagicMock())
        self.storage_patcher.start()

    def tearDown(self):
        self.firebase_patcher.stop()
        self.firestore_patcher.stop()
        self.storage_patcher.stop()

    def test_get_document_returns_none_when_not_exists(self):
        from firebase_service import FirebaseService

        svc = FirebaseService()
        snap = MagicMock()
        snap.exists = False
        svc._db.collection.return_value.document.return_value.get.return_value = snap
        result = svc.get_document("col", "doc")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
