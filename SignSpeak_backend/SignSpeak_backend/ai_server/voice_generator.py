"""
voice_generator.py – Text-to-Speech (TTS) generator.

Supports two backends:
  1. pyttsx3  – offline, cross-platform (default).
  2. gTTS     – online, uses Google's TTS service; set TTS_USE_GTTS=true.

Output is always WAV or MP3 bytes so the caller can stream / cache / upload.
"""
import io
import logging
import os
import tempfile
from typing import Literal, Optional

logger = logging.getLogger(__name__)


def _synthesize_pyttsx3(
    text: str,
    rate: int = 150,
    volume: float = 1.0,
    voice_id: Optional[str] = None,
) -> bytes:
    """Synthesize speech with pyttsx3 and return WAV bytes."""
    try:
        import pyttsx3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    engine.setProperty("volume", volume)

    if voice_id:
        engine.setProperty("voice", voice_id)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        os.unlink(tmp_path)

    return data


def _synthesize_gtts(
    text: str,
    lang: str = "en",
    slow: bool = False,
) -> bytes:
    """Synthesize speech with gTTS and return MP3 bytes."""
    try:
        from gtts import gTTS  # type: ignore
    except ImportError as exc:
        raise RuntimeError("gTTS is not installed. Run: pip install gTTS") from exc

    tts = gTTS(text=text, lang=lang, slow=slow)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def generate_speech(
    text: str,
    backend: Literal["pyttsx3", "gtts"] = "pyttsx3",
    lang: str = "en",
    rate: int = 150,
    volume: float = 1.0,
    voice_id: Optional[str] = None,
    slow: bool = False,
) -> bytes:
    """
    Convert text to speech audio bytes.

    Parameters
    ----------
    text    : The text to synthesise.
    backend : 'pyttsx3' (offline WAV) or 'gtts' (online MP3).
    lang    : Language code for gTTS (e.g. 'en', 'hi', 'es').
    rate    : Speech rate in words-per-minute (pyttsx3 only).
    volume  : Volume 0.0–1.0 (pyttsx3 only).
    voice_id: Optional pyttsx3 voice ID string.
    slow    : Slow mode for gTTS.

    Returns
    -------
    bytes – raw audio bytes (WAV for pyttsx3, MP3 for gTTS).
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    if backend == "gtts":
        logger.info("Synthesising speech via gTTS (lang=%s)", lang)
        return _synthesize_gtts(text, lang=lang, slow=slow)
    else:
        logger.info("Synthesising speech via pyttsx3 (rate=%d)", rate)
        return _synthesize_pyttsx3(text, rate=rate, volume=volume, voice_id=voice_id)


def get_audio_content_type(backend: str = "pyttsx3") -> str:
    """Return the MIME type for the audio produced by the given backend."""
    return "audio/mpeg" if backend == "gtts" else "audio/wav"
