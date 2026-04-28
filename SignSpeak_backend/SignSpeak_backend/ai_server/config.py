"""
config.py – Centralised configuration for the AI Server.
Reads all settings from environment variables with safe defaults.
"""
import os

# ──────────────────────────────────────────────
# Firebase / GCP
# ──────────────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS: str = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", ""
)
FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "signspeak-20dff")
FIREBASE_STORAGE_BUCKET: str = os.environ.get(
    "FIREBASE_STORAGE_BUCKET", f"{FIREBASE_PROJECT_ID}.appspot.com"
)

# ──────────────────────────────────────────────
# Server
# ──────────────────────────────────────────────
HOST: str = os.environ.get("AI_SERVER_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("AI_SERVER_PORT", "8081"))
DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# ──────────────────────────────────────────────
# Rate limiting (requests per minute per user)
# ──────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))

# ──────────────────────────────────────────────
# MediaPipe / gesture detection
# ──────────────────────────────────────────────
GESTURE_MIN_DETECTION_CONFIDENCE: float = float(
    os.environ.get("GESTURE_MIN_DETECTION_CONFIDENCE", "0.6")
)
GESTURE_MIN_TRACKING_CONFIDENCE: float = float(
    os.environ.get("GESTURE_MIN_TRACKING_CONFIDENCE", "0.5")
)
GESTURE_MAX_NUM_HANDS: int = int(os.environ.get("GESTURE_MAX_NUM_HANDS", "2"))

# ──────────────────────────────────────────────
# DeepFace / emotion detection
# ──────────────────────────────────────────────
EMOTION_BACKEND: str = os.environ.get(
    "EMOTION_BACKEND", "opencv"
)  # choices: opencv, ssd, dlib, mtcnn, retinaface
EMOTION_ENFORCE_DETECTION: bool = (
    os.environ.get("EMOTION_ENFORCE_DETECTION", "false").lower() == "true"
)

# ──────────────────────────────────────────────
# TTS
# ──────────────────────────────────────────────
TTS_RATE: int = int(os.environ.get("TTS_RATE", "150"))   # words per minute
TTS_VOLUME: float = float(os.environ.get("TTS_VOLUME", "1.0"))
TTS_USE_GTTS: bool = os.environ.get("TTS_USE_GTTS", "false").lower() == "true"
TTS_GTTS_LANG: str = os.environ.get("TTS_GTTS_LANG", "en")
