from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.voice import MAX_AUDIO_BASE64_CHARS, VoiceService


class FakeSttClient:
    def __init__(self, transcript: str = "make it taller") -> None:
        self.transcript = transcript
        self.paths_seen: list[Path] = []
        self.exists_during_call: list[bool] = []

    def transcribe_file(self, audio_path: Path, content_type: str) -> str:
        self.paths_seen.append(audio_path)
        self.exists_during_call.append(audio_path.exists())
        assert content_type == "audio/wav"
        return self.transcript


def client_with_voice(voice_service: VoiceService) -> TestClient:
    return TestClient(create_app(voice_service=voice_service))


def test_voice_transcript_endpoint_returns_text_without_generation_or_telemetry(tmp_path: Path) -> None:
    telemetry_path = tmp_path / "telemetry.jsonl"
    client = client_with_voice(VoiceService(FakeSttClient()))

    response = client.post("/voice/transcribe", json={"transcript": "  Make It Taller  "})

    assert response.status_code == 200
    assert response.json() == {"transcript": "make it taller"}
    assert not telemetry_path.exists()


def test_voice_audio_is_transient_and_temp_file_deleted_after_stt() -> None:
    fake = FakeSttClient("add a window")
    service = VoiceService(fake, track_temp_paths=True)
    client = client_with_voice(service)
    audio_base64 = base64.b64encode(b"RIFFmock wav bytes").decode("ascii")

    response = client.post(
        "/voice/transcribe",
        json={"audio_base64": audio_base64, "content_type": "audio/wav"},
    )

    assert response.status_code == 200
    assert response.json() == {"transcript": "add a window"}
    assert fake.exists_during_call == [True]
    assert len(service.deleted_temp_paths) == 1
    assert not service.deleted_temp_paths[0].exists()
    assert service.deleted_temp_paths[0].name.startswith("oasis_voice_")


def test_voice_temp_tracking_is_bounded() -> None:
    service = VoiceService(FakeSttClient(), track_temp_paths=True)
    audio_base64 = base64.b64encode(b"RIFFmock wav bytes").decode("ascii")

    for index in range(105):
        assert service.transcribe(audio_base64=audio_base64, content_type="audio/wav") == "make it taller"

    assert len(service.deleted_temp_paths) == 100
    assert all(not path.exists() for path in service.deleted_temp_paths)


def test_voice_service_sweeps_stale_temp_files_on_startup(tmp_path: Path) -> None:
    stale = tmp_path / "oasis_voice_stale.wav"
    stale.write_bytes(b"orphaned audio")
    old = time.time() - 7200
    os.utime(stale, (old, old))

    service = VoiceService(FakeSttClient(), temp_dir=tmp_path, track_temp_paths=True)

    assert service.swept_temp_paths == [stale]
    assert not stale.exists()


def test_voice_rejects_empty_or_invalid_payload_with_sanitized_error() -> None:
    client = client_with_voice(VoiceService(FakeSttClient()))

    empty = client.post("/voice/transcribe", json={"transcript": " \n\t "})
    invalid_audio = client.post("/voice/transcribe", json={"audio_base64": "not base64", "content_type": "audio/wav"})

    assert empty.status_code == 400
    assert empty.json() == {
        "error_code": "invalid_prompt",
        "message": "Voice input did not include audio or transcript text.",
    }
    assert invalid_audio.status_code == 422
    assert invalid_audio.json() == {"error_code": "asset_invalid", "message": "Voice audio payload was invalid."}

    oversized = client.post("/voice/transcribe", json={"audio_base64": "A" * (MAX_AUDIO_BASE64_CHARS + 1)})
    assert oversized.status_code == 422
    assert oversized.json() == {"error_code": "asset_invalid", "message": "Voice audio payload was too large."}


def test_voice_temp_tracking_is_disabled_by_default() -> None:
    service = VoiceService(FakeSttClient())

    assert service.deleted_temp_paths is None
    assert service.swept_temp_paths is None


def test_stt_provider_key_is_server_side_only(monkeypatch) -> None:
    monkeypatch.delenv("OASIS_STT_API_KEY", raising=False)
    client = TestClient(create_app())
    audio_base64 = base64.b64encode(b"RIFFmock wav bytes").decode("ascii")

    response = client.post("/voice/transcribe", json={"audio_base64": audio_base64, "content_type": "audio/wav"})

    assert response.status_code == 502
    assert response.json() == {
        "error_code": "provider_error",
        "message": "Speech-to-text provider key is not configured.",
    }
