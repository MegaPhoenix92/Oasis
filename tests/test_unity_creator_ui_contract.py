from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
UI_DIR = CLIENT / "Assets/Scripts/Oasis/UI"
IMPORT_DIR = CLIENT / "Assets/Scripts/Oasis/Import"


def test_ui_scripts_exist() -> None:
    ui_script = UI_DIR / "OasisCreatorUI.cs"
    facade_script = UI_DIR / "OasisGenerationFacade.cs"
    assert ui_script.is_file(), "OasisCreatorUI.cs must exist"
    assert facade_script.is_file(), "OasisGenerationFacade.cs must exist"


def test_ui_states_exist() -> None:
    ui_content = (UI_DIR / "OasisCreatorUI.cs").read_text(encoding="utf-8")
    for state in ("Idle", "Generating", "Preview", "Error"):
        assert f"OasisCreatorState.{state}" in ui_content or state in ui_content, f"State {state} must be defined/referenced in OasisCreatorUI.cs"


def test_dto_fields_match_contract() -> None:
    facade_content = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")
    
    # PromptRequest: prompt
    assert "class PromptRequest" in facade_content
    assert "public string prompt" in facade_content
    
    # GenerateResponse: job_id, status
    assert "class GenerateResponse" in facade_content
    assert "public string job_id" in facade_content
    assert "public string status" in facade_content

    # JobResponse: status, manifest, error_code
    assert "class JobResponse" in facade_content
    assert "public string status" in facade_content
    assert "public OasisAssetManifest manifest" in facade_content or "public Oasis.Import.OasisAssetManifest manifest" in facade_content
    assert "public string error_code" in facade_content

    # ErrorResponse: error_code, message
    assert "class ErrorResponse" in facade_content
    assert "public string error_code" in facade_content
    assert "public string message" in facade_content


def test_keyboard_error_placement_hooks_present() -> None:
    ui_content = (UI_DIR / "OasisCreatorUI.cs").read_text(encoding="utf-8")

    # Keyboard support hook: Enter submit
    assert "KeyCode.Return" in ui_content or "KeyCode.KeypadEnter" in ui_content
    assert "SubmitPrompt" in ui_content

    # Error handling hook: typed error code and safe messages
    assert "GetSafeErrorMessage" in ui_content
    assert "invalid_prompt" in ui_content
    assert "timeout" in ui_content
    assert "provider_error" in ui_content
    assert "asset_invalid" in ui_content

    # Placement & integration callback/events hooks
    assert "OnGenerationReady" in ui_content
    assert "OnPlaceRequested" in ui_content
    assert "OnFlowFailed" in ui_content
    assert "placeButton" in ui_content


def test_no_secrets_and_no_source_url_fetches_in_ui() -> None:
    client_files = list(CLIENT.rglob("*.cs"))
    client_text = "\n".join(path.read_text(encoding="utf-8") for path in client_files)

    # API keys must not be hardcoded in client scripts
    assert "ANTHROPIC_API_KEY" not in client_text
    assert "MESHY_API_KEY" not in client_text

    # No direct source_url fetching in scripts
    assert "new Uri(manifest.source_url" not in client_text
    assert "new Uri(spec.source_url" not in client_text
    assert "UnityWebRequest.Get(manifest.source_url" not in client_text
    assert "UnityWebRequest.Get(spec.source_url" not in client_text
    assert "HttpClient" not in client_text


def test_fetch_path_handoff_present() -> None:
    manifest_content = (IMPORT_DIR / "OasisAssetManifest.cs").read_text(encoding="utf-8")
    facade_content = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")
    scene_content = (CLIENT / "Assets/Scripts/Oasis/Scene/OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    assert "public string fetch_path" in manifest_content, "OasisAssetManifest must have fetch_path field"
    assert 'NormalizeBaseUrl() + "/create"' in facade_content
    assert "manifest.fetch_path" in facade_content
    assert "UnityWebRequest.Get(assetUrl)" in facade_content
    assert "ImportFromBytesAsync(asset.GlbBytes, asset.ManifestJson" in scene_content
