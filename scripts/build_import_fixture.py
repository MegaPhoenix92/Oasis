#!/usr/bin/env python3
"""Build and verify the deterministic offline import fixture (issue #74).

The canonical fixture is a glTF 2.0 *text* file with an embedded base64 buffer
(`tests/fixtures/unity_import/oasis_fixture_cube.gltf`) so the repo respects the
Git LFS policy (`docs/LFS_POLICY.md`): no mesh binaries are committed. The
binary GLB consumed by the Unity import pipeline is derived byte-for-byte
deterministically from the same geometry, and its sha256/size are pinned in
`oasis_fixture_cube_manifest.json` so any drift fails CI.

Usage:
    python3 scripts/build_import_fixture.py          # (re)write fixture files
    python3 scripts/build_import_fixture.py --check  # verify checked-in files
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests/fixtures/unity_import"
GLTF_PATH = FIXTURE_DIR / "oasis_fixture_cube.gltf"
MANIFEST_PATH = FIXTURE_DIR / "oasis_fixture_cube_manifest.json"

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK_TYPE = b"JSON"
BIN_CHUNK_TYPE = b"BIN\x00"

FIXTURE_ASSET_ID = "a74c0b6e-0f15-4f74-9b3a-2d6c1e5b8f01"

# Unit cube centered on the origin, spanning [-0.5, 0.5] on every axis.
CUBE_VERTICES = [
    (-0.5, -0.5, -0.5),
    (0.5, -0.5, -0.5),
    (0.5, 0.5, -0.5),
    (-0.5, 0.5, -0.5),
    (-0.5, -0.5, 0.5),
    (0.5, -0.5, 0.5),
    (0.5, 0.5, 0.5),
    (-0.5, 0.5, 0.5),
]

# 12 triangles, counter-clockwise winding so every face normal points outward.
CUBE_INDICES = [
    4, 5, 6, 4, 6, 7,  # +Z
    1, 0, 3, 1, 3, 2,  # -Z
    3, 7, 6, 3, 6, 2,  # +Y
    0, 1, 5, 0, 5, 4,  # -Y
    1, 2, 6, 1, 6, 5,  # +X
    0, 4, 7, 0, 7, 3,  # -X
]


def build_geometry_bytes() -> tuple[bytes, bytes]:
    positions = b"".join(struct.pack("<3f", *vertex) for vertex in CUBE_VERTICES)
    indices = b"".join(struct.pack("<H", index) for index in CUBE_INDICES)
    return positions, indices


def build_gltf_dict(embed_buffer_uri: bool) -> dict:
    positions, indices = build_geometry_bytes()
    buffer_bytes = positions + indices
    buffer_entry: dict = {"byteLength": len(buffer_bytes)}
    if embed_buffer_uri:
        encoded = base64.b64encode(buffer_bytes).decode("ascii")
        buffer_entry["uri"] = "data:application/octet-stream;base64," + encoded
    return {
        "asset": {"generator": "oasis scripts/build_import_fixture.py", "version": "2.0"},
        "scene": 0,
        "scenes": [{"name": "OasisFixtureScene", "nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "OasisFixtureCube"}],
        "meshes": [
            {
                "name": "OasisFixtureCubeMesh",
                "primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}],
            }
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(CUBE_VERTICES),
                "max": [0.5, 0.5, 0.5],
                "min": [-0.5, -0.5, -0.5],
                "type": "VEC3",
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(CUBE_INDICES),
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteLength": len(positions), "byteOffset": 0, "target": 34962},
            {"buffer": 0, "byteLength": len(indices), "byteOffset": len(positions), "target": 34963},
        ],
        "buffers": [buffer_entry],
    }


def build_gltf_text() -> str:
    return json.dumps(build_gltf_dict(embed_buffer_uri=True), indent=2, sort_keys=True) + "\n"


def _pad_chunk(payload: bytes, fill: bytes) -> bytes:
    remainder = len(payload) % 4
    return payload if remainder == 0 else payload + fill * (4 - remainder)


def build_glb_bytes() -> bytes:
    positions, indices = build_geometry_bytes()
    binary_chunk = _pad_chunk(positions + indices, b"\x00")
    json_payload = json.dumps(
        build_gltf_dict(embed_buffer_uri=False), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    json_chunk = _pad_chunk(json_payload, b" ")
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return b"".join(
        [
            GLB_MAGIC,
            struct.pack("<I", GLB_VERSION),
            struct.pack("<I", total_length),
            struct.pack("<I", len(json_chunk)),
            JSON_CHUNK_TYPE,
            json_chunk,
            struct.pack("<I", len(binary_chunk)),
            BIN_CHUNK_TYPE,
            binary_chunk,
        ]
    )


def build_manifest_dict() -> dict:
    glb = build_glb_bytes()
    return {
        "asset_id": FIXTURE_ASSET_ID,
        "source_prompt": "a plain gray cube",
        "normalized_prompt": "plain gray cube",
        "spec": {
            "schema_version": "1.0",
            "source_prompt": "a plain gray cube",
            "normalized_prompt": "plain gray cube",
            "object_type": "primitive",
            "name": "fixture cube",
            "materials": ["matte"],
            "style": "minimal",
            "dimensions": {"width": 0.5, "height": 0.25, "depth": 0.75},
            "details": ["deterministic offline fixture", "12 triangles"],
            "meshy_prompt": "a plain gray unit cube, minimal style",
        },
        "provider": "meshy.ai",
        "job_id": "offline-fixture-cube",
        "source_url": "https://provider.example/assets/oasis-fixture-cube.glb",
        "fetch_path": f"/assets/{FIXTURE_ASSET_ID}",
        "local_path": f"assets/generated/{FIXTURE_ASSET_ID}.glb",
        "checksum_sha256": hashlib.sha256(glb).hexdigest(),
        "format": "glb",
        "file_size_bytes": len(glb),
        "triangle_count": len(CUBE_INDICES) // 3,
        "texture_count": 0,
        "created_at": "2026-06-11T00:00:00Z",
    }


def build_manifest_text() -> str:
    return json.dumps(build_manifest_dict(), indent=2) + "\n"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def check() -> None:
    if not GLTF_PATH.exists():
        fail(f"missing fixture: {GLTF_PATH.relative_to(ROOT)}")
    if not MANIFEST_PATH.exists():
        fail(f"missing fixture manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    if GLTF_PATH.read_text(encoding="utf-8") != build_gltf_text():
        fail("oasis_fixture_cube.gltf does not match deterministic regeneration")
    if MANIFEST_PATH.read_text(encoding="utf-8") != build_manifest_text():
        fail("oasis_fixture_cube_manifest.json does not match deterministic regeneration")

    glb = build_glb_bytes()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if hashlib.sha256(glb).hexdigest() != manifest["checksum_sha256"]:
        fail("derived GLB checksum does not match the pinned manifest checksum")
    if len(glb) != manifest["file_size_bytes"]:
        fail("derived GLB size does not match the pinned manifest size")
    print("Offline import fixture validation passed.")


def write() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    GLTF_PATH.write_text(build_gltf_text(), encoding="utf-8")
    MANIFEST_PATH.write_text(build_manifest_text(), encoding="utf-8")
    glb = build_glb_bytes()
    print(f"wrote {GLTF_PATH.relative_to(ROOT)}")
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"derived GLB: {len(glb)} bytes, sha256={hashlib.sha256(glb).hexdigest()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the checked-in fixture files")
    arguments = parser.parse_args()
    if arguments.check:
        check()
    else:
        write()


if __name__ == "__main__":
    main()
