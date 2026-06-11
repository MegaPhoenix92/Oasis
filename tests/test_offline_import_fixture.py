"""Offline behavioral tests for the deterministic import fixture (issue #74).

These tests exercise the #7 import/placement contract against real, decodable
geometry without Claude, Meshy, API keys, or network access. The GLB consumed
by the Unity pipeline is derived here independently from the checked-in glTF
text fixture and must match the checksum pinned in the fixture manifest.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

from test_unity_import_contract import MAX_ASSET_BYTES, _placement, _validate_manifest


ROOT = Path(__file__).resolve().parents[1]
GLTF_PATH = ROOT / "tests/fixtures/unity_import/oasis_fixture_cube.gltf"
MANIFEST_PATH = ROOT / "tests/fixtures/unity_import/oasis_fixture_cube_manifest.json"


def _gltf() -> dict:
    return json.loads(GLTF_PATH.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _decode_buffer(gltf: dict) -> bytes:
    uri = gltf["buffers"][0]["uri"]
    prefix = "data:application/octet-stream;base64,"
    assert uri.startswith(prefix)
    return base64.b64decode(uri[len(prefix):])


def _decode_geometry(gltf: dict) -> tuple[list[tuple[float, float, float]], list[int]]:
    buffer = _decode_buffer(gltf)
    views = gltf["bufferViews"]
    position_accessor, index_accessor = gltf["accessors"]
    position_view = views[position_accessor["bufferView"]]
    index_view = views[index_accessor["bufferView"]]

    positions = [
        struct.unpack_from("<3f", buffer, position_view.get("byteOffset", 0) + 12 * i)
        for i in range(position_accessor["count"])
    ]
    indices = [
        struct.unpack_from("<H", buffer, index_view.get("byteOffset", 0) + 2 * i)[0]
        for i in range(index_accessor["count"])
    ]
    return positions, indices


def _derive_glb(gltf: dict) -> bytes:
    """Independently re-derive the GLB container from the text fixture."""
    buffer = _decode_buffer(gltf)
    glb_gltf = copy.deepcopy(gltf)
    del glb_gltf["buffers"][0]["uri"]
    json_payload = json.dumps(glb_gltf, separators=(",", ":"), sort_keys=True).encode("utf-8")
    json_chunk = json_payload + b" " * (-len(json_payload) % 4)
    binary_chunk = buffer + b"\x00" * (-len(buffer) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return b"".join(
        [
            b"glTF",
            (2).to_bytes(4, "little"),
            total_length.to_bytes(4, "little"),
            len(json_chunk).to_bytes(4, "little"),
            b"JSON",
            json_chunk,
            len(binary_chunk).to_bytes(4, "little"),
            b"BIN\x00",
            binary_chunk,
        ]
    )


def test_fixture_builder_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_import_fixture.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Offline import fixture validation passed." in result.stdout


def test_fixture_is_valid_offline_gltf() -> None:
    gltf = _gltf()
    assert gltf["asset"]["version"] == "2.0"
    buffer = _decode_buffer(gltf)
    assert len(buffer) == gltf["buffers"][0]["byteLength"]
    for view in gltf["bufferViews"]:
        assert view.get("byteOffset", 0) + view["byteLength"] <= len(buffer)
    # Offline guarantee: the only URI in the asset is the embedded data buffer.
    for buffer_entry in gltf["buffers"]:
        assert buffer_entry["uri"].startswith("data:")
    assert "images" not in gltf


def test_fixture_geometry_is_a_consistent_unit_cube() -> None:
    gltf = _gltf()
    positions, indices = _decode_geometry(gltf)

    assert len(positions) == 8
    assert len(indices) == 36
    assert len(set(indices)) == 8
    assert all(0 <= index < len(positions) for index in indices)
    triangles = [tuple(indices[i : i + 3]) for i in range(0, len(indices), 3)]
    assert all(len(set(triangle)) == 3 for triangle in triangles)

    position_accessor = gltf["accessors"][0]
    for axis in range(3):
        values = [vertex[axis] for vertex in positions]
        assert min(values) == position_accessor["min"][axis]
        assert max(values) == position_accessor["max"][axis]
    assert position_accessor["min"] == [-0.5, -0.5, -0.5]
    assert position_accessor["max"] == [0.5, 0.5, 0.5]


def test_derived_glb_matches_pinned_manifest_checksum() -> None:
    glb = _derive_glb(_gltf())
    manifest = _manifest()

    assert glb[:4] == b"glTF"
    assert int.from_bytes(glb[4:8], "little") == 2
    assert int.from_bytes(glb[8:12], "little") == len(glb)
    assert len(glb) % 4 == 0
    assert glb[16:20] == b"JSON"

    assert len(glb) == manifest["file_size_bytes"]
    assert len(glb) <= MAX_ASSET_BYTES
    assert hashlib.sha256(glb).hexdigest() == manifest["checksum_sha256"]

    corrupted = bytearray(glb)
    corrupted[-1] ^= 0xFF
    assert hashlib.sha256(bytes(corrupted)).hexdigest() != manifest["checksum_sha256"]


def test_fixture_manifest_satisfies_locked_import_contract() -> None:
    manifest = _manifest()
    ok, reason = _validate_manifest(manifest)
    assert ok, reason
    assert manifest["triangle_count"] == 12
    assert manifest["texture_count"] == 0


def test_placement_grounds_fixture_cube_at_anchor() -> None:
    gltf = _gltf()
    positions, _ = _decode_geometry(gltf)
    source_size = tuple(
        max(vertex[axis] for vertex in positions) - min(vertex[axis] for vertex in positions)
        for axis in range(3)
    )
    source_center = tuple(
        (max(vertex[axis] for vertex in positions) + min(vertex[axis] for vertex in positions)) / 2
        for axis in range(3)
    )
    assert source_size == (1.0, 1.0, 1.0)
    assert source_center == (0.0, 0.0, 0.0)

    manifest = _manifest()
    scale, position = _placement(
        source_size=source_size,
        source_center=source_center,
        target=manifest["spec"]["dimensions"],
        anchor=(3.0, 0.0, -2.0),
    )
    assert scale == 0.25
    assert position == (3.0, 0.125, -2.0)
