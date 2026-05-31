#!/usr/bin/env python3
"""Offline checks for the Unity Creator UI and service facade."""

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

    if not (ROOT / ui_path).is_file():
        fail(f"Missing required UI script: {ui_path}")
    if not (ROOT / facade_path).is_file():
        fail(f"Missing required service facade script: {facade_path}")

    ui = read(ui_path)
    facade = read(facade_path)

    # 1. State machine verify
    required_states = ["Idle", "Generating", "Preview", "Error"]
    missing_states = [state for state in required_states if f"OasisCreatorState.{state}" not in ui and state not in ui]
    if missing_states:
        fail("OasisCreatorUI missing required state names: " + ", ".join(missing_states))

    # 2. Integration seams verify
    required_seams = ["OnGenerationReady", "OnPlaceRequested", "OnFlowFailed"]
    missing_seams = [seam for seam in required_seams if seam not in ui]
    if missing_seams:
        fail("OasisCreatorUI missing required integration event/callback hooks: " + ", ".join(missing_seams))

    # 3. Keyboard/Input verify
    required_input = ["KeyCode.Return", "KeyCode.KeypadEnter", "SubmitPrompt"]
    missing_input = [term for term in required_input if term not in ui]
    if missing_input:
        fail("OasisCreatorUI missing keyboard submit support: " + ", ".join(missing_input))

    # 4. Error messages safety verify
    required_errors = ["GetSafeErrorMessage", "invalid_prompt", "timeout", "provider_error", "asset_invalid", "network_error"]
    missing_errors = [err for err in required_errors if err not in ui]
    if missing_errors:
        fail("OasisCreatorUI missing safe user-facing error handler: " + ", ".join(missing_errors))

    # 5. Service Facade verify
    required_facade_terms = ["StartGenerationFlow", "CoGenerateFlow", "ExtractErrorCode", "UnityWebRequest", "JsonUtility"]
    missing_facade = [term for term in required_facade_terms if term not in facade]
    if missing_facade:
        fail("OasisGenerationFacade missing required terms: " + ", ".join(missing_facade))

    # 6. DTO verify
    required_dtos = ["PromptRequest", "GenerateResponse", "JobResponse", "ErrorResponse"]
    missing_dtos = [dto for dto in required_dtos if dto not in facade]
    if missing_dtos:
        fail("OasisGenerationFacade missing required DTO definitions: " + ", ".join(missing_dtos))

    # 7. No secrets or direct source_url fetches in src/client
    client_text = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT.rglob("*.cs"))
    for forbidden in ("ANTHROPIC_API_KEY", "MESHY_API_KEY", "Quaternion.Euler(90", "new Uri(manifest.source_url", "UnityWebRequest.Get(manifest.source_url", "HttpClient"):
        if forbidden in client_text:
            fail(f"Forbidden Unity client reference found: {forbidden}")

    print("Unity Creator UI and Service Facade validation passed.")


if __name__ == "__main__":
    main()
