from __future__ import annotations

import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
CAPTURE_SERVICE_PATH = CLIENT / "Assets/Scripts/Oasis/Capture/OasisCaptureService.cs"
CREATOR_UI_PATH = CLIENT / "Assets/Scripts/Oasis/UI/OasisCreatorUI.cs"
BOOTSTRAP_PATH = CLIENT / "Assets/Scripts/Oasis/Scene/OasisSceneBootstrap.cs"

# ----------------- Dynamic/Unit checks of the logic in Python -----------------

def sanitize_filename_port(filename: str) -> str:
    """Python port of the C# SanitizeFilename logic for verification."""
    if not filename:
        return "capture_default"
    
    # Remove path navigation / directory separators
    clean = os.path.basename(filename)
    
    # Strip out invalid chars
    invalid_chars = '<>:"/\\|?*\0'
    for char in invalid_chars:
        clean = clean.replace(char, '_')
        
    # Replace relative path traversal sequences
    clean = clean.replace("/", "_").replace("\\", "_").replace("..", "_").replace(":", "_")
    
    if not clean.strip():
        return "capture_default"
        
    return clean

def is_path_contained_port(parent_dir: str, child_path: str) -> bool:
    """Python port of the C# IsPathContained logic for verification."""
    try:
        full_parent = os.path.abspath(parent_dir).rstrip(os.path.sep)
        full_child = os.path.abspath(child_path)
        return full_child.startswith(full_parent + os.path.sep)
    except Exception:
        return False

def test_python_filename_sanitization() -> None:
    # Basic filename remains valid
    assert sanitize_filename_port("test.png") == "test.png"
    # Backslashes / directory traversal removed
    assert sanitize_filename_port("../../etc/passwd") == "passwd"
    assert sanitize_filename_port("subdir/file.png") == "file.png"
    # Backslashes are replaced by underscores on Unix, which is a safe filename
    assert sanitize_filename_port("a\\b\\c.png") in ("c.png", "a_b_c.png")
    # Special characters replaced
    assert sanitize_filename_port("a:b?c.png") == "a_b_c.png"
    # Empty or whitespace only
    assert sanitize_filename_port("") == "capture_default"
    assert sanitize_filename_port("   ") == "capture_default"

def test_python_path_containment() -> None:
    parent = "/app/captures"
    # Valid contained path
    assert is_path_contained_port(parent, "/app/captures/screenshot1.png") is True
    assert is_path_contained_port(parent, "/app/captures/nested/screenshot1.png") is True
    # Traversal attempts outside the folder
    assert is_path_contained_port(parent, "/app/captures/../etc/passwd") is False
    assert is_path_contained_port(parent, "/app/etc/passwd") is False
    assert is_path_contained_port(parent, "/other/path") is False

# ----------------- Source code verification checks -----------------

def test_capture_service_exists() -> None:
    assert CAPTURE_SERVICE_PATH.is_file(), "OasisCaptureService.cs must exist"

def test_capture_service_containment_checks() -> None:
    content = CAPTURE_SERVICE_PATH.read_text(encoding="utf-8")
    
    # Assert path containment check method and its usage are present
    assert "IsPathContained" in content, "OasisCaptureService must define IsPathContained"
    assert "SanitizeFilename" in content, "OasisCaptureService must define SanitizeFilename"
    
    # Assert checks are called inside both CaptureScreenshot and CaptureShortClip
    assert content.count("IsPathContained") >= 3, "IsPathContained must be called in both capture methods"
    assert content.count("SanitizeFilename") >= 3, "SanitizeFilename must be called in both capture methods"

def test_no_network_or_api_keys_in_capture() -> None:
    content = CAPTURE_SERVICE_PATH.read_text(encoding="utf-8")
    
    # Assert no secret or network usages
    forbidden_terms = [
        "API_KEY", "HttpClient", "UnityWebRequest", "url", "http://", "https://"
    ]
    for term in forbidden_terms:
        assert term not in content, f"Forbidden term '{term}' found in OasisCaptureService.cs"

def test_no_schema_or_operation_model_mutation_in_capture() -> None:
    content = CAPTURE_SERVICE_PATH.read_text(encoding="utf-8")
    
    # Capture service should not deal with the world document data schema or operations
    forbidden_types = [
        "OasisWorldDocument", "OasisWorldObject", "OasisCreatorOperation",
        "OasisCreatorHistory", "world.json"
    ]
    for term in forbidden_types:
        assert term not in content, f"Capture service must not mutate world document/schema. Found '{term}'."

def test_creator_ui_wired_with_screenshot_and_video() -> None:
    ui_content = CREATOR_UI_PATH.read_text(encoding="utf-8")
    
    # Verify UI variables exist
    assert "screenshotButton" in ui_content, "OasisCreatorUI must declare screenshotButton"
    assert "videoButton" in ui_content, "OasisCreatorUI must declare videoButton"
    
    # Verify UI event hooks exist
    assert "OnScreenshotRequested" in ui_content, "OasisCreatorUI must declare OnScreenshotRequested event"
    assert "OnVideoRequested" in ui_content, "OasisCreatorUI must declare OnVideoRequested event"

def test_scene_bootstrap_wires_listeners() -> None:
    bootstrap_content = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    
    # Verify bootstrap contains captureService and registers events
    assert "captureService" in bootstrap_content, "OasisSceneBootstrap must define captureService"
    assert "OnScreenshotRequested" in bootstrap_content, "OasisSceneBootstrap must subscribe to OnScreenshotRequested"
    assert "OnVideoRequested" in bootstrap_content, "OasisSceneBootstrap must subscribe to OnVideoRequested"
    assert "HandleScreenshotRequested" in bootstrap_content, "OasisSceneBootstrap must define HandleScreenshotRequested"
    assert "HandleVideoRequested" in bootstrap_content, "OasisSceneBootstrap must define HandleVideoRequested"
