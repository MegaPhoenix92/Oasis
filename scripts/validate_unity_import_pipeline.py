#!/usr/bin/env python3
"""Offline checks for the Unity import/placement pipeline."""

from __future__ import annotations

import json
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
    manifest = json.loads(read("tests/fixtures/unity_import/valid_manifest.json"))
    if manifest["format"] != "glb":
        fail("fixture manifest must use glb")
    if manifest["fetch_path"] != f"/assets/{manifest['asset_id']}":
        fail("fixture manifest must use the locked /assets/{asset_id} fetch path")

    importer = read("src/client/Assets/Scripts/Oasis/Import/OasisGlbImporter.cs")
    validator = read("src/client/Assets/Scripts/Oasis/Import/OasisAssetManifestValidator.cs")
    placement = read("src/client/Assets/Scripts/Oasis/Import/OasisPlacementMath.cs")
    scene = read("src/client/Assets/Scenes/OasisPoC.unity")

    required_importer_terms = ["LoadGltfBinary", "InstantiateMainSceneAsync", "ValidateChecksum", "ImportFromBytesAsync"]
    missing = [term for term in required_importer_terms if term not in importer]
    if missing:
        fail("Unity importer missing required terms: " + ", ".join(missing))

    required_validator_terms = ["ManifestUnsupportedFormat", "AssetOversized", "ManifestMalformed", "format != \"glb\"", "MaxAssetBytes"]
    missing = [term for term in required_validator_terms if term not in validator]
    if missing:
        fail("Unity manifest validator missing required terms: " + ", ".join(missing))

    required_placement_terms = ["Mathf.Min", "bottomCenter", "groundAnchor - bottomCenter", "Vector3.one * placement.UniformScale"]
    missing = [term for term in required_placement_terms if term not in placement]
    if missing:
        fail("Unity placement math missing required terms: " + ", ".join(missing))

    client_text = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT.rglob("*.cs"))
    for forbidden in ("ANTHROPIC_API_KEY", "MESHY_API_KEY", "Quaternion.Euler(90", "new Uri(manifest.source_url", "UnityWebRequest.Get(manifest.source_url", "HttpClient"):
        if forbidden in client_text:
            fail(f"Forbidden Unity client reference found: {forbidden}")

    if "guid: fbbaae9c734d42838117eb53be852e2e" not in scene:
        fail("PoC scene must reference OasisSceneBootstrap")

    print("Unity import pipeline validation passed.")


if __name__ == "__main__":
    main()
