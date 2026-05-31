from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
UI_DIR = CLIENT / "Assets/Scripts/Oasis/UI"


def test_voice_backend_is_server_side_stt_adapter_only() -> None:
    app = (ROOT / "src/ai/oasis_ai/app.py").read_text(encoding="utf-8")
    voice = (ROOT / "src/ai/oasis_ai/voice.py").read_text(encoding="utf-8")
    models = (ROOT / "src/ai/oasis_ai/models.py").read_text(encoding="utf-8")

    assert '"/voice/transcribe"' in app
    assert "VoiceService" in app
    assert "VoiceTranscriptRequest" in models
    assert "VoiceTranscriptResponse" in models
    assert "OASIS_STT_API_KEY" in voice
    assert "os.getenv(self.api_key_env)" in voice
    assert "self.client = httpx.Client" in voice
    assert "response = self.client.post" in voice
    assert "if not isinstance(payload, dict)" in voice
    assert "raise VoiceError(\"provider_error\", \"Speech-to-text provider request failed.\"" in voice
    assert "logger" not in voice.lower()
    assert "print(" not in voice


def test_voice_audio_is_not_persisted_or_logged() -> None:
    voice = (ROOT / "src/ai/oasis_ai/voice.py").read_text(encoding="utf-8")
    telemetry = (ROOT / "src/ai/oasis_ai/telemetry.py").read_text(encoding="utf-8")
    world_files = "\n".join(path.read_text(encoding="utf-8") for path in (CLIENT / "Assets/Scripts/Oasis/Persistence").rglob("*.cs"))

    assert "NamedTemporaryFile" in voice
    assert "delete=False" in voice
    assert "temp_path.unlink" in voice
    assert "deleted_temp_paths" in voice
    assert "audio_base64" not in telemetry
    assert "VoiceTranscript" not in telemetry
    assert "audio_base64" not in world_files
    assert "VoiceTranscript" not in world_files


def test_voice_client_uses_same_typed_router_after_transcription() -> None:
    ui = (UI_DIR / "OasisCreatorUI.cs").read_text(encoding="utf-8")
    facade = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")

    assert "StartVoiceAudioFlow" in facade
    assert 'NormalizeBaseUrl() + "/voice/transcribe"' in facade
    assert "VoiceTranscriptResponse" in facade
    assert "SubmitVoiceTranscript" in ui
    submit_voice = ui[ui.find("public void SubmitVoiceTranscript"):ui.find("private void PerformSelectedTransformRefine")]
    assert "promptInputField.text = transcript" in submit_voice
    assert "SubmitPrompt()" in submit_voice
    assert "StartRefineFlow" not in submit_voice
    assert "StartGenerationFlow" not in submit_voice
    assert "classifier" not in ui.lower()
    assert "intent" not in ui.lower()


def test_voice_recording_handles_microphone_edge_cases() -> None:
    ui = (UI_DIR / "OasisCreatorUI.cs").read_text(encoding="utf-8")

    assert "voiceClip = Microphone.Start" in ui
    assert "if (voiceClip == null)" in ui
    assert "catch (Exception)" in ui
    assert "Microphone.IsRecording(null)" in ui
    assert "voiceClip.samples" in ui
    assert "Coroutine voiceTimeoutCoroutine" in ui
    assert "StartCoroutine(CoWatchVoiceRecordingTimeout())" in ui
    assert "StopCoroutine(voiceTimeoutCoroutine)" in ui
    assert "bool isUiInteractable = interactable && !isVoiceRecording" in ui
    assert "generateButton.interactable = isUiInteractable" in ui
    assert "promptInputField.interactable = isUiInteractable" in ui


def test_stt_secret_names_are_not_in_unity_client() -> None:
    client_text = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT.rglob("*.cs"))

    assert "OASIS_STT_API_KEY" not in client_text
    assert "STT_API_KEY" not in client_text
    assert "OPENAI_API_KEY" not in client_text
    assert "ANTHROPIC_API_KEY" not in client_text
    assert "MESHY_API_KEY" not in client_text
