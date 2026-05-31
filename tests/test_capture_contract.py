from __future__ import annotations

import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
CAPTURE_SERVICE_PATH = CLIENT / "Assets/Scripts/Oasis/Capture/OasisCaptureService.cs"
CREATOR_UI_PATH = CLIENT / "Assets/Scripts/Oasis/UI/OasisCreatorUI.cs"
BOOTSTRAP_PATH = CLIENT / "Assets/Scripts/Oasis/Scene/OasisSceneBootstrap.cs"
CAPTURE_DIR = CLIENT / "Assets/Scripts/Oasis/Capture"

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

def sanitize_clip_directory_name_port(filename: str) -> str:
    sanitized = sanitize_filename_port(filename)
    without_extension = os.path.splitext(os.path.basename(sanitized))[0]
    if not without_extension.strip():
        without_extension = "clip_default"

    clean = without_extension.strip()
    invalid_chars = '<>:"/\\|?*\0'
    for char in invalid_chars:
        clean = clean.replace(char, "_")
    clean = clean.replace("/", "_").replace("\\", "_").replace("..", "_").replace(":", "_")
    if not clean.strip() or clean in {".", ".."}:
        clean = "clip_default"
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

def test_python_clip_directory_sanitization() -> None:
    assert sanitize_clip_directory_name_port("clip.mp4") == "clip"
    assert sanitize_clip_directory_name_port("../../outside/clip.mp4") == "clip"
    assert sanitize_clip_directory_name_port("bad:name?.mp4") == "bad_name_"
    assert "/" not in sanitize_clip_directory_name_port("../bad/name.mp4")
    assert "\\" not in sanitize_clip_directory_name_port("bad\\name.mp4")

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

def test_short_clip_does_not_write_static_mp4_header() -> None:
    content = CAPTURE_SERVICE_PATH.read_text(encoding="utf-8")
    match = re.search(r"public bool CaptureShortClip\(.*?\n        \}", content, re.S)
    assert match, "CaptureShortClip method must exist"
    method = match.group(0)

    forbidden = [
        "mockMp4",
        "ftypmp42",
        ".mp4",
        "File.WriteAllBytes(targetPath",
    ]
    for term in forbidden:
        assert term not in method, f"CaptureShortClip must not write a fake static MP4 artifact. Found '{term}'."

def test_short_clip_frame_sequence_and_manifest_contract() -> None:
    content = CAPTURE_SERVICE_PATH.read_text(encoding="utf-8")

    required_terms = [
        "ShortClipDirectoryName",
        "ShortClipFramesDirectoryName",
        "ShortClipManifestName",
        "CaptureFrameSequenceCoroutine",
        "CaptureFrameSequenceNow",
        "CaptureSingleFrame",
        "ScreenCapture.CaptureScreenshotAsTexture",
        "WaitForEndOfFrame",
        "WriteClipManifest",
        "ShortClipManifest",
        "duration_seconds",
        "frame_count",
        "frames",
        "manifest.json",
        "frame_",
        ".png",
    ]
    missing = [term for term in required_terms if term not in content]
    assert not missing, "Short clip capture missing frame sequence/manifest terms: " + ", ".join(missing)

def test_short_clip_output_paths_are_contained_and_sanitized() -> None:
    capture_root = "/app/captures"
    clip_name = sanitize_clip_directory_name_port("../../outside/bad:name?.mp4")
    clips_dir = os.path.join(capture_root, "short_clips")
    clip_dir = os.path.join(clips_dir, clip_name)
    frames_dir = os.path.join(clip_dir, "frames")
    frame_path = os.path.join(frames_dir, "frame_0000.png")
    manifest_path = os.path.join(clip_dir, "manifest.json")

    assert clip_name == "bad_name_"
    assert is_path_contained_port(capture_root, clips_dir) is True
    assert is_path_contained_port(clips_dir, clip_dir) is True
    assert is_path_contained_port(clip_dir, frames_dir) is True
    assert is_path_contained_port(frames_dir, frame_path) is True
    assert is_path_contained_port(clip_dir, manifest_path) is True

    escaped_manifest = os.path.join(clip_dir, "..", "..", "manifest.json")
    assert is_path_contained_port(clip_dir, escaped_manifest) is False

def test_capture_unity_meta_files_exist() -> None:
    capture_meta = CAPTURE_DIR.with_suffix(".meta")
    service_meta = CAPTURE_SERVICE_PATH.with_suffix(".cs.meta")

    assert capture_meta.is_file(), "Unity Capture folder must have a .meta file"
    assert service_meta.is_file(), "OasisCaptureService.cs must have a .meta file"

    for meta_path in (capture_meta, service_meta):
        content = meta_path.read_text(encoding="utf-8")
        assert "fileFormatVersion: 2" in content
        assert re.search(r"^guid: [a-f0-9]{32}$", content, re.M), f"{meta_path} must contain a Unity GUID"

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
