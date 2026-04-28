"""
main.py – AI Server for SignSpeak.

Endpoints
─────────
GET  /health           Liveness probe
GET  /ready            Readiness probe
POST /translate        Translate text between languages (stub – integrate NMT model)
POST /emotion          Detect facial emotion from an uploaded image
POST /speech-to-text   Transcribe audio to text (stub – integrate Whisper/STT)
POST /text-to-sign     Convert text to sign-language sequence
POST /gesture          Detect hand gesture from an uploaded image
POST /tts              Convert text to speech audio (WAV/MP3)

All non-probe endpoints require a Firebase ID token in the Authorization header.
"""
import base64
import logging
import os
import sys

from flask import Flask, Response, abort, jsonify, request

# ── Local imports ──────────────────────────────────────────────────────────────
from ai_server.config import (
    DEBUG,
    EMOTION_BACKEND,
    GESTURE_MAX_NUM_HANDS,
    GESTURE_MIN_DETECTION_CONFIDENCE,
    GESTURE_MIN_TRACKING_CONFIDENCE,
    HOST,
    LOG_LEVEL,
    PORT,
    TTS_GTTS_LANG,
    TTS_RATE,
    TTS_USE_GTTS,
    TTS_VOLUME,
)
from ai_server.emotion_detection import detect_emotion
from ai_server.gesture_detection import detect_gestures_from_bytes
from ai_server.voice_generator import generate_speech, get_audio_content_type
import firebase_admin
from firebase_admin import auth, credentials

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)


# ── Firebase initialisation ────────────────────────────────────────────────────
def _init_firebase() -> None:
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    local_key = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "serviceAccountKey.json"
    )
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    elif os.path.exists(local_key):
        cred = credentials.Certificate(local_key)
    else:
        cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized.")


_init_firebase()


# ── Auth helper ────────────────────────────────────────────────────────────────
def _require_auth() -> str:
    """Verify Firebase Bearer token; abort(401) on failure. Returns uid."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        logger.warning("Missing or malformed Authorization header.")
        abort(401, "Missing Bearer token.")
    token = header.split(" ", 1)[1].strip()
    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        abort(401, "Invalid or expired token.")


def _get_image_bytes() -> bytes:
    """
    Extract image bytes from the request.
    Supports:
      • multipart file upload  (field name: 'image')
      • JSON body              {'image': '<base64_string>'}
      • raw body               (Content-Type: image/*)
    """
    if "image" in request.files:
        return request.files["image"].read()

    data = request.get_json(silent=True) or {}
    if "image" in data:
        try:
            return base64.b64decode(data["image"])
        except Exception:
            abort(400, "Invalid base64 image data.")

    if request.content_type and request.content_type.startswith("image/"):
        return request.data

    abort(400, "No image provided. Send 'image' as file, base64 JSON, or raw body.")


# ── Health / readiness ─────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ready", methods=["GET"])
def ready():
    return jsonify({"ready": True})


# ── /translate ─────────────────────────────────────────────────────────────────
@app.route("/translate", methods=["POST"])
def translate():
    uid = _require_auth()
    data = request.get_json(silent=True) or {}
    image_bytes = None
    
    if "image" in data:
        try:
            image_bytes = base64.b64decode(data["image"])
        except Exception:
            pass
    elif "image" in request.files:
        image_bytes = request.files["image"].read()

    text_to_log = ""
    source = data.get("source", "auto")
    target = data.get("target", "en")

    if image_bytes:
        # If image is provided, detect gesture and use it as text
        try:
            gesture_result = detect_gestures_from_bytes(
                image_bytes,
                max_num_hands=GESTURE_MAX_NUM_HANDS,
                min_detection_confidence=GESTURE_MIN_DETECTION_CONFIDENCE,
                min_tracking_confidence=GESTURE_MIN_TRACKING_CONFIDENCE,
            )
            hands = gesture_result.get("hands", [])
            if hands:
                translated_text = hands[0].get("gesture", "UNKNOWN")
            else:
                translated_text = ""
            text_to_log = f"[Image: {len(image_bytes)} bytes]"
        except Exception as exc:
            logger.error("Gesture detection failed: %s", exc)
            abort(500, "Internal error during gesture detection.")
    else:
        text = str(data.get("text", "")).strip()
        if not text:
            abort(400, "Field 'text' or 'image' is required.")
        translated_text = text  # identity translation for now
        text_to_log = text

    logger.info(
        "translate: input=%s src=%s tgt=%s uid=%s",
        text_to_log[:50],
        source,
        target,
        uid,
    )
    return jsonify(
        {
            "translated_text": translated_text,
            "source_lang": source,
            "target_lang": target,
            "confidence": 1.0,
        }
    )


# ── /emotion ───────────────────────────────────────────────────────────────────
@app.route("/emotion", methods=["POST"])
def emotion():
    _require_auth()
    image_bytes = _get_image_bytes()

    result = detect_emotion(image_bytes, backend=EMOTION_BACKEND)
    logger.info("emotion: face_count=%d label=%s", result["face_count"], result["label"])
    return jsonify(result)


# ── /speech-to-text ────────────────────────────────────────────────────────────
@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():
    _require_auth()

    # Accept audio as a file upload or raw body.
    audio_bytes: bytes = b""
    if "audio" in request.files:
        audio_bytes = request.files["audio"].read()
    else:
        audio_bytes = request.data

    if not audio_bytes:
        abort(400, "No audio data provided. Send 'audio' file or raw body.")

    # ── Placeholder: swap for Whisper, Google STT, etc. ──────────────────
    transcript = ""
    confidence = 0.0
    # Example Whisper integration (uncomment when model is available):
    # import whisper
    # model = whisper.load_model("base")
    # with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    #     f.write(audio_bytes); tmp = f.name
    # res = model.transcribe(tmp); os.unlink(tmp)
    # transcript = res["text"]; confidence = 0.9

    logger.info("speech-to-text: audio_len=%d", len(audio_bytes))
    return jsonify({"transcript": transcript, "confidence": confidence})


# ── /text-to-sign ──────────────────────────────────────────────────────────────
@app.route("/text-to-sign", methods=["POST"])
def text_to_sign():
    _require_auth()
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    locale = str(data.get("locale", "en-US")).strip()

    if not text:
        abort(400, "Field 'text' is required.")

    # Build a naïve word-per-sign sequence as a placeholder.
    # Replace with a proper ISL/ASL mapping or a sequence model.
    words = text.upper().split()
    sign_sequence = words if words else ["SIGN"]

    logger.info("text-to-sign: words=%d locale=%s", len(sign_sequence), locale)
    return jsonify({"sign_sequence": sign_sequence, "locale": locale})


# ── /gesture ───────────────────────────────────────────────────────────────────
@app.route("/gesture", methods=["POST"])
def gesture():
    _require_auth()
    image_bytes = _get_image_bytes()

    result = detect_gestures_from_bytes(
        image_bytes,
        max_num_hands=GESTURE_MAX_NUM_HANDS,
        min_detection_confidence=GESTURE_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=GESTURE_MIN_TRACKING_CONFIDENCE,
    )
    logger.info("gesture: hand_count=%d", result["hand_count"])
    return jsonify(result)


# ── /tts ───────────────────────────────────────────────────────────────────────
@app.route("/tts", methods=["POST"])
def tts():
    _require_auth()
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    backend = "gtts" if TTS_USE_GTTS else "pyttsx3"
    lang = str(data.get("lang", TTS_GTTS_LANG)).strip()

    if not text:
        abort(400, "Field 'text' is required.")

    try:
        audio_bytes = generate_speech(
            text,
            backend=backend,  # type: ignore[arg-type]
            lang=lang,
            rate=TTS_RATE,
            volume=TTS_VOLUME,
        )
    except Exception as exc:
        logger.error("TTS generation failed: %s", exc)
        abort(500, f"TTS generation failed: {exc}")

    content_type = get_audio_content_type(backend)
    logger.info("tts: len=%d backend=%s lang=%s", len(audio_bytes), backend, lang)
    return Response(audio_bytes, status=200, mimetype=content_type)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
