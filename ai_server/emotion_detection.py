"""
emotion_detection.py – Facial emotion detection using DeepFace.

Accepts a JPEG/PNG image (as bytes or a file-like object) and returns
an emotion label plus confidence scores for all detected emotions.
"""
import io
import logging
import numpy as np
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Lazy-import to avoid heavy imports at startup when the module is only imported
# but emotion detection is not immediately needed.
_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace  # type: ignore
            _deepface = DeepFace
            logger.info("DeepFace loaded successfully.")
        except ImportError as exc:
            logger.error("DeepFace is not installed: %s", exc)
            raise RuntimeError(
                "DeepFace is not installed. Run: pip install deepface"
            ) from exc
    return _deepface


def _decode_image(image_data: bytes) -> np.ndarray:
    """Convert raw image bytes to a NumPy BGR array (OpenCV format)."""
    import cv2  # type: ignore

    buf = np.frombuffer(image_data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Ensure it is a valid JPEG/PNG.")
    return img


def detect_emotion(image_data: bytes, backend: str = "opencv") -> Dict[str, Any]:
    """
    Detect the dominant facial emotion in an image.

    Parameters
    ----------
    image_data : bytes
        Raw bytes of a JPEG or PNG image.
    backend : str
        Face detection backend for DeepFace (opencv, ssd, dlib, mtcnn, retinaface).

    Returns
    -------
    dict with keys:
        label  – string, dominant emotion (e.g. 'happy', 'neutral', …)
        scores – dict mapping each emotion label to its confidence (0-1)
        face_count – number of faces detected
    """
    DeepFace = _get_deepface()

    img = _decode_image(image_data)

    try:
        results = DeepFace.analyze(
            img_path=img,
            actions=["emotion"],
            detector_backend=backend,
            enforce_detection=False,
            silent=True,
        )
    except Exception as exc:
        logger.warning("DeepFace.analyze failed: %s", exc)
        return {
            "label": "unknown",
            "scores": {},
            "face_count": 0,
        }

    # DeepFace may return a list if multiple faces are found, or a single dict.
    if isinstance(results, dict):
        results = [results]

    face_count = len(results)

    # Aggregate emotions across all detected faces (average confidence).
    combined: Dict[str, float] = {}
    for face in results:
        raw_emotions: Dict[str, float] = face.get("emotion", {})
        # DeepFace returns percentages; normalise to 0-1.
        total = sum(raw_emotions.values()) or 1.0
        for emotion_label, value in raw_emotions.items():
            combined[emotion_label] = combined.get(emotion_label, 0.0) + (
                value / total / face_count
            )

    dominant = max(combined, key=combined.get) if combined else "neutral"

    return {
        "label": dominant,
        "scores": {k: round(v, 4) for k, v in combined.items()},
        "face_count": face_count,
    }
