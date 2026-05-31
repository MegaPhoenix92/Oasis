"""Server-side speech-to-text adapter for Oasis voice input."""

from __future__ import annotations

import base64
import binascii
import os
import tempfile
from pathlib import Path
from typing import Protocol

import httpx

from .service import SpecError, normalize_prompt

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
DEFAULT_STT_MODEL = "gpt-4o-mini-transcribe"
MAX_AUDIO_BYTES = 8 * 1024 * 1024


class VoiceError(SpecError):
    """Typed, sanitized voice/STT error."""


class SttClient(Protocol):
    def transcribe_file(self, audio_path: Path, content_type: str) -> str:
        """Return transcript text for a temporary audio file."""


class HttpSttClient:
    """HTTP STT provider client. API key stays in the server process."""

    def __init__(
        self,
        api_key_env: str = "OASIS_STT_API_KEY",
        model_env: str = "OASIS_STT_MODEL",
        url: str = OPENAI_TRANSCRIPTION_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key_env = api_key_env
        self.model_env = model_env
        self.url = url
        self.timeout_seconds = timeout_seconds

    def transcribe_file(self, audio_path: Path, content_type: str) -> str:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise VoiceError("provider_error", "Speech-to-text provider key is not configured.", 502)

        model = os.getenv(self.model_env, DEFAULT_STT_MODEL)
        try:
            with audio_path.open("rb") as handle:
                files = {"file": (audio_path.name, handle, content_type or "application/octet-stream")}
                data = {"model": model}
                headers = {"Authorization": f"Bearer {api_key}"}
                response = httpx.post(self.url, headers=headers, data=data, files=files, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise VoiceError("provider_error", "Speech-to-text provider request failed.", 502) from exc

        transcript = str(payload.get("text", ""))
        return _safe_transcript(transcript)


class VoiceService:
    def __init__(self, stt_client: SttClient | None = None) -> None:
        self.stt_client = stt_client or HttpSttClient()
        self.deleted_temp_paths: list[Path] = []

    def transcribe(self, *, transcript: str | None = None, audio_base64: str | None = None, content_type: str | None = None) -> str:
        if transcript is not None and transcript.strip():
            return _safe_transcript(transcript)

        if audio_base64 is None or not audio_base64.strip():
            raise VoiceError("invalid_prompt", "Voice input did not include audio or transcript text.", 400)

        audio_bytes = _decode_audio(audio_base64)
        suffix = _suffix_for_content_type(content_type)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="oasis_voice_", suffix=suffix, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(audio_bytes)
            return self.stt_client.transcribe_file(temp_path, content_type or "application/octet-stream")
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                    self.deleted_temp_paths.append(temp_path)
                except OSError:
                    pass


def _safe_transcript(transcript: str) -> str:
    normalized = normalize_prompt(transcript)
    return normalized


def _decode_audio(audio_base64: str) -> bytes:
    try:
        audio = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VoiceError("asset_invalid", "Voice audio payload was invalid.", 422) from exc

    if not audio:
        raise VoiceError("invalid_prompt", "Voice audio payload was empty.", 400)
    if len(audio) > MAX_AUDIO_BYTES:
        raise VoiceError("asset_invalid", "Voice audio payload was too large.", 422)
    return audio


def _suffix_for_content_type(content_type: str | None) -> str:
    if content_type == "audio/wav":
        return ".wav"
    if content_type == "audio/webm":
        return ".webm"
    if content_type == "audio/mpeg":
        return ".mp3"
    return ".audio"
