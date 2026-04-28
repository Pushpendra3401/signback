"""
gesture_detection.py – Real-time hand gesture / sign-language detection
                        using MediaPipe Hands.

The module exposes two public functions:
  • detect_gestures_from_bytes  – takes a raw image (bytes) and returns
                                   detected hand landmarks and a gesture label.
  • detect_gestures_from_frame  – takes a NumPy BGR frame (for frame-by-frame
                                   video pipelines) and returns the same.
"""
import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy globals ──────────────────────────────────────────────────────────────
_mp_hands = None
_mp_drawing = None
_gesture_recogniser = None   # reserved for future ModelMaker-based recogniser


def _get_mp_hands():
    global _mp_hands, _mp_drawing
    if _mp_hands is None:
        try:
            import mediapipe as mp  # type: ignore

            _mp_hands = mp.solutions.hands
            _mp_drawing = mp.solutions.drawing_utils
            logger.info("MediaPipe Hands loaded.")
        except ImportError as exc:
            raise RuntimeError(
                "mediapipe is not installed. Run: pip install mediapipe"
            ) from exc
    return _mp_hands


# ── Heuristic gesture rules ───────────────────────────────────────────────────
# Each finger is represented by 4 landmarks: MCP, PIP, DIP, TIP
# Landmark indices: https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
_FINGER_TIPS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky
_FINGER_PIPS = [3, 6, 10, 14, 18]


def _fingers_extended(landmarks) -> List[bool]:
    """
    Returns a list of 5 booleans indicating whether each finger is extended,
    using simple tip-above-PIP heuristics (for front-facing hand).
    Thumb is treated separately (horizontal motion).
    """
    extended = []
    # Thumb: compare x of tip vs IP (landmark 3)
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    extended.append(thumb_tip.x < thumb_ip.x)  # assumes right-hand mirrored view

    for tip_idx, pip_idx in zip(_FINGER_TIPS[1:], _FINGER_PIPS[1:]):
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        extended.append(tip.y < pip.y)  # y increases downward in image space

    return extended


def _classify_gesture(landmarks) -> str:
    """Map finger extension pattern to a gesture string."""
    ext = _fingers_extended(landmarks)
    num_extended = sum(ext)
    thumb, index, middle, ring, pinky = ext

    if num_extended == 0:
        return "FIST"
    if num_extended == 5:
        return "OPEN_HAND"
    if index and not middle and not ring and not pinky:
        return "POINTING"
    if index and middle and not ring and not pinky:
        return "PEACE"
    if not index and not middle and not ring and pinky:
        return "PINKY"
    if index and pinky and not middle and not ring:
        return "ROCK_ON"
    if thumb and not index and not middle and not ring and not pinky:
        return "THUMBS_UP"
    if num_extended >= 3:
        return "PARTIAL_OPEN"
    return "UNKNOWN"


def _extract_landmark_list(hand_landmarks) -> List[Dict[str, float]]:
    """Convert MediaPipe NormalizedLandmarkList to a JSON-serialisable list."""
    return [
        {"x": round(lm.x, 5), "y": round(lm.y, 5), "z": round(lm.z, 5)}
        for lm in hand_landmarks.landmark
    ]


def _decode_image(image_data: bytes) -> np.ndarray:
    import cv2  # type: ignore

    buf = np.frombuffer(image_data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes.")
    return img


# ── Public API ────────────────────────────────────────────────────────────────

def detect_gestures_from_bytes(
    image_data: bytes,
    max_num_hands: int = 2,
    min_detection_confidence: float = 0.6,
    min_tracking_confidence: float = 0.5,
) -> Dict[str, Any]:
    """
    Detect hand gestures from a raw JPEG/PNG image.

    Returns
    -------
    {
        "hands": [
            {
                "handedness": "Right" | "Left",
                "gesture":    str,
                "landmarks":  [{"x": float, "y": float, "z": float}, ...]
            },
            ...
        ],
        "hand_count": int
    }
    """
    frame = _decode_image(image_data)
    return detect_gestures_from_frame(
        frame,
        max_num_hands=max_num_hands,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )


# ── Persistent MediaPipe Instance ──────────────────────────────────────────────
import threading
_thread_local = threading.local()

def _get_hands_instance(max_num_hands, min_detection_confidence, min_tracking_confidence):
    if not hasattr(_thread_local, "hands_instance"):
        mp_hands = _get_mp_hands()
        _thread_local.hands_instance = mp_hands.Hands(
            static_image_mode=True,  # MUST be True for stateless web API
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
    return _thread_local.hands_instance


def detect_gestures_from_frame(
    frame: np.ndarray,
    max_num_hands: int = 2,
    min_detection_confidence: float = 0.6,
    min_tracking_confidence: float = 0.5,
) -> Dict[str, Any]:
    """
    Detect hand gestures from a NumPy BGR frame.

    Parameters
    ----------
    frame : np.ndarray
        A BGR image as returned by cv2.imread or cap.read.
    """
    import cv2  # type: ignore

    hands = _get_hands_instance(
        max_num_hands, min_detection_confidence, min_tracking_confidence
    )

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False

    results = hands.process(rgb)

    hands_data: List[Dict[str, Any]] = []
    if results.multi_hand_landmarks and results.multi_handedness:
        for hand_lm, hand_info in zip(
            results.multi_hand_landmarks, results.multi_handedness
        ):
            handedness = hand_info.classification[0].label  # "Left" or "Right"
            gesture = _classify_gesture(hand_lm.landmark)
            landmarks = _extract_landmark_list(hand_lm)
            hands_data.append(
                {
                    "handedness": handedness,
                    "gesture": gesture,
                    "landmarks": landmarks,
                }
            )

    return {"hands": hands_data, "hand_count": len(hands_data)}
