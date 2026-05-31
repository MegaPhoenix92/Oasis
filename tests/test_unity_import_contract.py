from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
VALID_MANIFEST = ROOT / "tests/fixtures/unity_import/valid_manifest.json"
MAX_ASSET_BYTES = 50 * 1024 * 1024


def _valid_manifest() -> dict:
    return json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))


def _validate_manifest(manifest: dict) -> tuple[bool, str]:
    required = {
        "asset_id",
        "source_prompt",
        "normalized_prompt",
        "spec",
        "provider",
        "job_id",
        "source_url",
        "fetch_path",
        "local_path",
        "checksum_sha256",
        "format",
        "file_size_bytes",
        "triangle_count",
        "texture_count",
        "created_at",
    }
    if missing := required - manifest.keys():
        return False, f"missing:{sorted(missing)}"
    try:
        UUID(manifest["asset_id"])
    except ValueError:
        return False, "bad_uuid"
    if manifest["format"] != "glb":
        return False, "unsupported_format"
    if manifest["fetch_path"] != f"/assets/{manifest['asset_id']}":
        return False, "bad_fetch_path"
    if manifest["file_size_bytes"] <= 0 or manifest["file_size_bytes"] > MAX_ASSET_BYTES:
        return False, "oversized"
    if not re.fullmatch(r"[a-fA-F0-9]{64}", manifest["checksum_sha256"]):
        return False, "bad_checksum"
    datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    spec = manifest["spec"]
    if spec.get("schema_version") != "1.0":
        return False, "bad_schema"
    dimensions = spec.get("dimensions") or {}
    if any(dimensions.get(axis, 0) <= 0 for axis in ("width", "height", "depth")):
        return False, "bad_dimensions"
    return True, "ok"


def _placement(source_size: tuple[float, float, float], source_center: tuple[float, float, float], target: dict, anchor: tuple[float, float, float]) -> tuple[float, tuple[float, float, float]]:
    scale = min(target["width"] / source_size[0], target["height"] / source_size[1], target["depth"] / source_size[2])
    extents = tuple(value * 0.5 for value in source_size)
    scaled_center = tuple(value * scale for value in source_center)
    scaled_extents = tuple(value * scale for value in extents)
    bottom_center = (scaled_center[0], scaled_center[1] - scaled_extents[1], scaled_center[2])
    root_position = tuple(anchor[index] - bottom_center[index] for index in range(3))
    return scale, root_position


def test_valid_manifest_matches_locked_contract() -> None:
    manifest = _valid_manifest()
    ok, reason = _validate_manifest(manifest)
    assert ok, reason


def test_manifest_rejects_unsupported_oversized_and_malformed_assets() -> None:
    manifest = _valid_manifest()
    unsupported = manifest | {"format": "fbx"}
    oversized = manifest | {"file_size_bytes": MAX_ASSET_BYTES + 1}
    missing = {key: value for key, value in manifest.items() if key != "fetch_path"}
    assert _validate_manifest(unsupported) == (False, "unsupported_format")
    assert _validate_manifest(oversized) == (False, "oversized")
    assert _validate_manifest(missing)[0] is False


def test_glb_header_and_checksum_fixture_are_deterministic() -> None:
    glb = b"glTF" + (2).to_bytes(4, "little") + (20).to_bytes(4, "little") + b"12345678"
    manifest = _valid_manifest()
    assert len(glb) == manifest["file_size_bytes"]
    assert glb[:4] == b"glTF"
    assert hashlib.sha256(glb).hexdigest() == manifest["checksum_sha256"]


def test_placement_fits_dimensions_and_grounds_bottom_center_without_axis_flip() -> None:
    manifest = _valid_manifest()
    scale, position = _placement(
        source_size=(2.0, 4.0, 1.0),
        source_center=(0.0, 2.0, 0.0),
        target=manifest["spec"]["dimensions"],
        anchor=(3.0, 0.0, -2.0),
    )
    assert math.isclose(scale, 0.25)
    assert position == (3.0, 0.0, -2.0)


def test_client_uses_gltfast_bytes_fetch_path_and_no_client_secrets() -> None:
    client_text = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT.rglob("*.cs"))
    assert "LoadGltfBinary" in client_text
    assert "InstantiateMainSceneAsync" in client_text
    assert "source_url" in client_text
    assert "new Uri(manifest.source_url" not in client_text
    assert "UnityWebRequest.Get(manifest.source_url" not in client_text
    assert "HttpClient" not in client_text
    assert "ANTHROPIC_API_KEY" not in client_text
    assert "MESHY_API_KEY" not in client_text
    assert "Quaternion.Euler(90" not in client_text
