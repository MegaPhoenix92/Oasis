from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
PERSISTENCE_DIR = CLIENT / "Assets/Scripts/Oasis/Persistence"
VALID_MANIFEST = ROOT / "tests/fixtures/unity_import/valid_manifest.json"
GLB = b"glTF" + (2).to_bytes(4, "little") + (20).to_bytes(4, "little") + b"12345678"


@dataclass(frozen=True)
class WorldError(Exception):
    code: str


def _manifest() -> dict:
    return json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))


def _world(*, duplicate: bool = False, asset_id: str | None = None, scene_settings: dict | None = None) -> dict:
    manifest = _manifest()
    asset = asset_id or manifest["asset_id"]
    first_instance = "223e4567-e89b-12d3-a456-426614174001"
    second_instance = first_instance if duplicate else "323e4567-e89b-12d3-a456-426614174002"
    return {
        "schema_version": "1.0",
        "world_id": "423e4567-e89b-42d3-a456-426614174003",
        "name": "Fixture World",
        "created_at": "2026-05-31T00:00:00Z",
        "updated_at": "2026-05-31T00:01:00Z",
        "scene_settings": scene_settings or {"time_of_day": 0.5, "weather": {"fog": 0.25}},
        "objects": [
            {
                "instance_id": first_instance,
                "asset_id": asset,
                "transform": {
                    "position": {"x": 1.0, "y": 0.0, "z": -2.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                },
                "created_at": "2026-05-31T00:00:30Z",
            },
            {
                "instance_id": second_instance,
                "asset_id": asset,
                "transform": {
                    "position": {"x": 2.0, "y": 0.0, "z": 3.0},
                    "rotation": {"x": 0.0, "y": 0.7071068, "z": 0.0, "w": 0.7071068},
                    "scale": {"x": 1.5, "y": 1.0, "z": 1.5},
                },
                "created_at": "2026-05-31T00:00:40Z",
            },
        ],
    }


def _uuid(value: str, code: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise WorldError(code) from exc


def _timestamp(value: str) -> None:
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_world(world: dict) -> None:
    if world.get("schema_version") != "1.0" or not isinstance(world.get("scene_settings"), dict):
        raise WorldError("invalid_world_document")
    _uuid(world.get("world_id", ""), "invalid_world_id")
    _timestamp(world["created_at"])
    _timestamp(world["updated_at"])
    seen: set[str] = set()
    for item in world.get("objects", []):
        _uuid(item.get("instance_id", ""), "invalid_world_document")
        _uuid(item.get("asset_id", ""), "invalid_asset_id")
        if item["instance_id"] in seen:
            raise WorldError("duplicate_instance_id")
        seen.add(item["instance_id"])
        transform = item["transform"]
        assert set(transform) == {"position", "rotation", "scale"}
        assert set(transform["rotation"]) == {"x", "y", "z", "w"}


def _safe_world_dir(root: Path, world_id: str) -> Path:
    _uuid(world_id, "invalid_world_id")
    resolved_root = root.resolve()
    world_dir = (resolved_root / world_id).resolve()
    if resolved_root not in world_dir.parents:
        raise WorldError("invalid_world_id")
    return world_dir


def _save_world(root: Path, world: dict, manifests: dict[str, dict], fetcher) -> None:
    _validate_world(world)
    world_dir = _safe_world_dir(root, world["world_id"])
    temp_dir = root / f"{world['world_id']}.tmp"
    shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        (temp_dir / "manifests").mkdir(parents=True)
        (temp_dir / "assets").mkdir()
        (temp_dir / "world.json").write_text(json.dumps(world, indent=2), encoding="utf-8")
        for asset_id in sorted({item["asset_id"] for item in world["objects"]}):
            _uuid(asset_id, "invalid_asset_id")
            manifest = manifests[asset_id]
            assert manifest["fetch_path"] == f"/assets/{asset_id}"
            glb = fetcher(manifest)
            if not glb:
                raise WorldError("asset_fetch_failed")
            if hashlib.sha256(glb).hexdigest() != manifest["checksum_sha256"]:
                raise WorldError("asset_checksum_mismatch")
            (temp_dir / "manifests" / f"{asset_id}.json").write_text(json.dumps(manifest), encoding="utf-8")
            (temp_dir / "assets" / f"{asset_id}.glb").write_bytes(glb)
        if world_dir.exists():
            shutil.rmtree(world_dir)
        temp_dir.rename(world_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _load_world(root: Path, world_id: str) -> tuple[dict, list[dict], list[dict]]:
    world_dir = _safe_world_dir(root, world_id)
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    _validate_world(world)
    loaded: list[dict] = []
    skipped: list[dict] = []
    for item in world["objects"]:
        asset_id = item["asset_id"]
        manifest_path = world_dir / "manifests" / f"{asset_id}.json"
        asset_path = world_dir / "assets" / f"{asset_id}.glb"
        if not manifest_path.exists() or not asset_path.exists():
            skipped.append({"instance_id": item["instance_id"], "reason": "asset_missing"})
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        glb = asset_path.read_bytes()
        if hashlib.sha256(glb).hexdigest() != manifest["checksum_sha256"]:
            skipped.append({"instance_id": item["instance_id"], "reason": "asset_checksum_mismatch"})
            continue
        loaded.append(item)
    return world, loaded, skipped


def _sanitize_bundle_filename(display_name: str, fallback_world_id: str) -> str:
    source = display_name or fallback_world_id
    chars: list[str] = []
    for char in source:
        if char.isalnum() or char in "-_ ":
            chars.append(char)
        elif char == "." and chars:
            chars.append(char)
        else:
            chars.append("-")
    sanitized = "".join(chars).strip(" .-")
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    sanitized = sanitized[:80].strip(" .-")
    return sanitized or fallback_world_id


def _export_bundle(root: Path, export_dir: Path, world_id: str, display_name: str | None = None) -> Path:
    world_dir = _safe_world_dir(root, world_id)
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    _validate_world(world)
    asset_ids = sorted({item["asset_id"] for item in world["objects"]})
    for asset_id in asset_ids:
        _uuid(asset_id, "invalid_asset_id")
        manifest_path = world_dir / "manifests" / f"{asset_id}.json"
        asset_path = world_dir / "assets" / f"{asset_id}.glb"
        if not manifest_path.exists() or not asset_path.exists():
            raise WorldError("asset_missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        glb = asset_path.read_bytes()
        if manifest["asset_id"] != asset_id or hashlib.sha256(glb).hexdigest() != manifest["checksum_sha256"]:
            raise WorldError("asset_checksum_mismatch")

    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_bundle_filename(display_name or world["name"], world["world_id"]) + ".oasisworld"
    bundle_path = (export_dir / filename).resolve()
    temp_path = bundle_path.with_suffix(bundle_path.suffix + ".tmp")
    with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(world_dir / "world.json", "world.json")
        for asset_id in asset_ids:
            archive.write(world_dir / "manifests" / f"{asset_id}.json", f"manifests/{asset_id}.json")
            archive.write(world_dir / "assets" / f"{asset_id}.glb", f"assets/{asset_id}.glb")
    temp_path.replace(bundle_path)
    return bundle_path


def _import_bundle(root: Path, bundle_path: Path) -> tuple[dict, list[dict], list[dict]]:
    with zipfile.ZipFile(bundle_path) as archive:
        world = json.loads(archive.read("world.json").decode("utf-8"))
        _validate_world(world)
        world_dir = _safe_world_dir(root, world["world_id"])
        temp_dir = root / f"{world['world_id']}.import"
        shutil.rmtree(temp_dir, ignore_errors=True)
        (temp_dir / "manifests").mkdir(parents=True)
        (temp_dir / "assets").mkdir()
        (temp_dir / "world.json").write_text(json.dumps(world, indent=2), encoding="utf-8")
        for asset_id in sorted({item["asset_id"] for item in world["objects"]}):
            manifest_name = f"manifests/{asset_id}.json"
            asset_name = f"assets/{asset_id}.glb"
            if manifest_name not in archive.namelist() or asset_name not in archive.namelist():
                continue
            manifest_json = archive.read(manifest_name).decode("utf-8")
            manifest = json.loads(manifest_json)
            glb = archive.read(asset_name)
            if manifest["asset_id"] != asset_id or hashlib.sha256(glb).hexdigest() != manifest["checksum_sha256"]:
                continue
            (temp_dir / "manifests" / f"{asset_id}.json").write_text(manifest_json, encoding="utf-8")
            (temp_dir / "assets" / f"{asset_id}.glb").write_bytes(glb)
        if world_dir.exists():
            shutil.rmtree(world_dir)
        temp_dir.rename(world_dir)
    return _load_world(root, world["world_id"])


def test_world_document_round_trips_with_unknown_scene_settings(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world(scene_settings={"time_of_day": 0.25, "weather": {"fog": 0.4}, "custom": ["keep"]})
    _save_world(tmp_path, world, {manifest["asset_id"]: manifest}, lambda _: GLB)

    loaded_world, loaded_objects, skipped = _load_world(tmp_path, world["world_id"])
    assert loaded_world == world
    assert len(loaded_objects) == 2
    assert skipped == []
    assert loaded_world["scene_settings"]["weather"] == {"fog": 0.4}
    assert loaded_world["scene_settings"]["custom"] == ["keep"]


def test_uuid_path_safety_and_traversal_rejection(tmp_path: Path) -> None:
    manifest = _manifest()
    with pytest.raises(WorldError, match="invalid_world_id"):
        _save_world(tmp_path, _world() | {"world_id": "../escape"}, {manifest["asset_id"]: manifest}, lambda _: GLB)
    with pytest.raises(WorldError, match="invalid_asset_id"):
        _save_world(tmp_path, _world(asset_id="../asset"), {manifest["asset_id"]: manifest}, lambda _: GLB)


def test_duplicate_instance_id_is_typed_schema_error(tmp_path: Path) -> None:
    manifest = _manifest()
    with pytest.raises(WorldError, match="duplicate_instance_id"):
        _save_world(tmp_path, _world(duplicate=True), {manifest["asset_id"]: manifest}, lambda _: GLB)


def test_all_or_nothing_save_failure_leaves_no_partial_world_directory(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world()
    with pytest.raises(WorldError, match="asset_fetch_failed"):
        _save_world(tmp_path, world, {manifest["asset_id"]: manifest}, lambda _: None)

    assert not (tmp_path / world["world_id"]).exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_missing_or_corrupt_asset_skips_object_gracefully_on_load(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world()
    _save_world(tmp_path, world, {manifest["asset_id"]: manifest}, lambda _: GLB)
    asset_path = tmp_path / world["world_id"] / "assets" / f"{manifest['asset_id']}.glb"
    asset_path.write_bytes(b"glTF" + b"corrupt")

    _, loaded, skipped = _load_world(tmp_path, world["world_id"])
    assert loaded == []
    assert {item["reason"] for item in skipped} == {"asset_checksum_mismatch"}

    asset_path.unlink()
    _, loaded, skipped = _load_world(tmp_path, world["world_id"])
    assert loaded == []
    assert {item["reason"] for item in skipped} == {"asset_missing"}


def test_export_bundle_is_sanitized_zip_of_saved_world_layout(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world() | {"name": "../QA: World?*"}
    _save_world(tmp_path, world, {manifest["asset_id"]: manifest}, lambda _: GLB)

    bundle = _export_bundle(tmp_path, tmp_path / "exports", world["world_id"])

    assert bundle.name == "QA- World.oasisworld"
    assert bundle.parent == (tmp_path / "exports").resolve()
    with zipfile.ZipFile(bundle) as archive:
        assert sorted(archive.namelist()) == [
            f"assets/{manifest['asset_id']}.glb",
            f"manifests/{manifest['asset_id']}.json",
            "world.json",
        ]
        assert json.loads(archive.read("world.json")) == world


def test_export_fails_loudly_when_referenced_bundle_asset_is_missing(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world()
    _save_world(tmp_path, world, {manifest["asset_id"]: manifest}, lambda _: GLB)
    (tmp_path / world["world_id"] / "assets" / f"{manifest['asset_id']}.glb").unlink()

    with pytest.raises(WorldError, match="asset_missing"):
        _export_bundle(tmp_path, tmp_path / "exports", world["world_id"])

    assert not list((tmp_path / "exports").glob("*.oasisworld"))


def test_bundle_import_is_clean_machine_relative_and_checksum_guarded(tmp_path: Path) -> None:
    manifest = _manifest()
    world = _world()
    _save_world(tmp_path / "source", world, {manifest["asset_id"]: manifest}, lambda _: GLB)
    bundle = _export_bundle(tmp_path / "source", tmp_path / "exports", world["world_id"])
    shutil.rmtree(tmp_path / "source")

    loaded_world, loaded, skipped = _import_bundle(tmp_path / "clean", bundle)

    assert loaded_world == world
    assert len(loaded) == 2
    assert skipped == []

    corrupt_bundle = tmp_path / "exports" / "corrupt.oasisworld"
    with zipfile.ZipFile(bundle) as original, zipfile.ZipFile(corrupt_bundle, "w") as corrupt:
        for name in original.namelist():
            data = b"corrupt" if name.startswith("assets/") else original.read(name)
            corrupt.writestr(name, data)

    _, loaded, skipped = _import_bundle(tmp_path / "corrupt-clean", corrupt_bundle)
    assert loaded == []
    assert {item["reason"] for item in skipped} == {"asset_missing"}


def test_unity_persistence_contract_is_client_local_and_fetch_path_only() -> None:
    persistence = (PERSISTENCE_DIR / "OasisWorldPersistence.cs").read_text(encoding="utf-8")
    document = (PERSISTENCE_DIR / "OasisWorldDocument.cs").read_text(encoding="utf-8")
    scene = (CLIENT / "Assets/Scripts/Oasis/Scene/OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    assert "schema_version" in document
    assert "world_id" in document
    assert "scene_settings_json" in document
    assert "instance_id" in document
    assert "OasisWorldQuaternion" in document
    assert "DuplicateInstanceId" in persistence
    assert "SkippedObjects" in persistence
    assert "ValidateChecksum" in persistence
    assert "manifest.fetch_path" in persistence
    assert '"/assets/" + manifest.asset_id' in persistence
    assert "manifest.local_path" not in persistence
    assert "manifest.source_url" not in persistence
    assert ".tmp-" in persistence
    assert "Directory.Move(tempDirectory, worldDirectory)" in persistence
    assert "ExportBundleAsync" in persistence
    assert "ImportBundleAsync" in persistence
    assert "ZipArchive" in persistence
    assert "SanitizeBundleFilename" in persistence
    assert "archive.GetEntry(AssetsDirectoryName + \"/\" + assetId + \".glb\")" in persistence
    assert "SaveActiveWorldAsync" in scene
    assert "LoadWorldAsync" in scene
    assert "placedWorldObjects" in scene
    assert "DestroyActiveSceneObjects" in scene


def test_scene_settings_extraction_ignores_string_value_collisions() -> None:
    persistence = (PERSISTENCE_DIR / "OasisWorldPersistence.cs").read_text(encoding="utf-8")

    assert "json.IndexOf" not in persistence
    assert "depth != 1" in persistence
    assert "keyBuilder.ToString()" in persistence
    assert "json[colonIndex] != ':'" in persistence
    assert "continue;" in persistence
