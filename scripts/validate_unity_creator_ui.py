#!/usr/bin/env python3
"""Offline validation script for the Unity Creator UI and Service Facade."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> None:
    ui_path = "src/client/Assets/Scripts/Oasis/UI/OasisCreatorUI.cs"
    facade_path = "src/client/Assets/Scripts/Oasis/UI/OasisGenerationFacade.cs"
    manifest_path = "src/client/Assets/Scripts/Oasis/Import/OasisAssetManifest.cs"

    if not (ROOT / ui_path).is_file():
        fail(f"Missing required UI script: {ui_path}")
    if not (ROOT / facade_path).is_file():
        fail(f"Missing required service facade script: {facade_path}")
    if not (ROOT / manifest_path).is_file():
        fail(f"Missing required asset manifest DTO script: {manifest_path}")

    ui = read(ui_path)
    facade = read(facade_path)
    manifest = read(manifest_path)

    # 1. State machine verify (Idle/Generating/Preview/Error)
    required_states = ["Idle", "Generating", "Preview", "Error"]
    missing_states = [state for state in required_states if state not in ui]
    if missing_states:
        fail("OasisCreatorUI missing required state names: " + ", ".join(missing_states))

    # 2. DTO fields match contract
    # PromptRequest: prompt
    if "class PromptRequest" not in facade or "public string prompt" not in facade:
        fail("OasisGenerationFacade missing PromptRequest DTO or prompt field")

    # GenerateResponse: job_id, status
    if "class GenerateResponse" not in facade or "public string job_id" not in facade or "public string status" not in facade:
        fail("OasisGenerationFacade missing GenerateResponse DTO or fields (job_id, status)")

    # JobResponse: status, manifest, error_code
    if "class JobResponse" not in facade or "public string status" not in facade or ("public OasisAssetManifest manifest" not in facade and "public Oasis.Import.OasisAssetManifest manifest" not in facade) or "public string error_code" not in facade:
        fail("OasisGenerationFacade missing JobResponse DTO or fields (status, manifest, error_code)")

    # ErrorResponse: error_code, message
    if "class ErrorResponse" not in facade or "public string error_code" not in facade or "public string message" not in facade:
        fail("OasisGenerationFacade missing ErrorResponse DTO or fields (error_code, message)")

    # 3. No secrets in client
    client_files = list(CLIENT.rglob("*.cs"))
    client_text = "\n".join(path.read_text(encoding="utf-8") for path in client_files)
    for key in ("ANTHROPIC_API_KEY", "MESHY_API_KEY"):
        if key in client_text:
            fail(f"API key reference found in Unity client scripts: {key}")

    # 4. No source_url fetches in client
    for forbidden in (
        "new Uri(manifest.source_url",
        "new Uri(spec.source_url",
        "UnityWebRequest.Get(manifest.source_url",
        "UnityWebRequest.Get(spec.source_url",
        "HttpClient"
    ):
        if forbidden in client_text:
            fail(f"Forbidden direct source_url/HttpClient fetch found: {forbidden}")

    # 5. fetch_path handoff verification
    if "public string fetch_path" not in manifest:
        fail("OasisAssetManifest is missing the fetch_path field necessary for handoff")
    if 'NormalizeBaseUrl() + "/create"' not in facade:
        fail("OasisGenerationFacade must submit prompts through POST /create")
    if "manifest.fetch_path" not in facade or "UnityWebRequest.Get(assetUrl)" not in facade:
        fail("OasisGenerationFacade must download generated assets through manifest.fetch_path")
    if "ImportFromBytesAsync" not in read("src/client/Assets/Scripts/Oasis/Scene/OasisSceneBootstrap.cs"):
        fail("OasisSceneBootstrap must hand downloaded bytes and manifest JSON to OasisGlbImporter")

    # 6. Enter submits when idle/error and prompt is non-empty
    if "KeyCode.Return" not in ui and "KeyCode.KeypadEnter" not in ui:
        fail("OasisCreatorUI missing Enter key submit detection")
    if "SubmitPrompt" not in ui:
        fail("OasisCreatorUI missing SubmitPrompt method hook")

    # 7. generate/place hooks and integration events
    required_seams = ["OnGenerationReady", "OnPlaceRequested", "OnFlowFailed", "placeButton"]
    missing_seams = [seam for seam in required_seams if seam not in ui]
    if missing_seams:
        fail("OasisCreatorUI missing required integration hooks/events: " + ", ".join(missing_seams))

    print("Unity Creator UI validation passed successfully.")


if __name__ == "__main__":
    main()
