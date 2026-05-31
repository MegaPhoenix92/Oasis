from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
IMPORT_DIR = CLIENT / "Assets/Scripts/Oasis/Import"
PERSISTENCE_DIR = CLIENT / "Assets/Scripts/Oasis/Persistence"
SCENE_DIR = CLIENT / "Assets/Scripts/Oasis/Scene"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_slice(source: str, signature: str, next_signature: str | None = None) -> str:
    start = source.find(signature)
    assert start != -1, f"missing method: {signature}"
    if next_signature is None:
        return source[start:]
    end = source.find(next_signature, start + len(signature))
    assert end != -1, f"missing next method: {next_signature}"
    return source[start:end]


def _set_time_of_day(scene_settings: dict, value: float) -> dict:
    preserved = json.loads(json.dumps(scene_settings))
    preserved["time_of_day"] = max(0.0, min(1.0, value))
    return preserved


def test_first_person_controller_is_runtime_local_and_bootstrapped() -> None:
    controller = _read(SCENE_DIR / "OasisFirstPersonController.cs")
    bootstrap = _read(SCENE_DIR / "OasisSceneBootstrap.cs")

    assert "CharacterController" in controller
    assert "Input.GetAxisRaw(\"Horizontal\")" in controller
    assert "Input.GetAxisRaw(\"Vertical\")" in controller
    assert "Input.GetAxis(\"Mouse X\")" in controller
    assert "Input.GetAxis(\"Mouse Y\")" in controller
    assert "gravity" in controller
    assert "EventSystem.current.currentSelectedGameObject" in controller

    assert "new GameObject(\"Oasis First Person Explorer\")" in bootstrap
    assert "explorer.AddComponent<CharacterController>()" in bootstrap
    assert "explorer.AddComponent<OasisFirstPersonController>()" in bootstrap
    assert "cameraObject.tag = \"MainCamera\"" in bootstrap

    forbidden = ("UnityWebRequest", "HttpClient", "ANTHROPIC_API_KEY", "MESHY_API_KEY")
    for term in forbidden:
        assert term not in controller


def test_post_normalization_colliders_and_kinematic_bodies_are_attached_after_placement_math() -> None:
    importer = _read(IMPORT_DIR / "OasisGlbImporter.cs")
    physics = _read(IMPORT_DIR / "OasisPlacedAssetPhysics.cs")

    placement_index = importer.find("OasisPlacementMath.TryApply")
    physics_index = importer.find("OasisPlacedAssetPhysics.ConfigurePostImport")
    assert placement_index != -1
    assert physics_index != -1
    assert physics_index > placement_index

    assert "TryGetPostImportRendererBounds" in physics
    assert "GetComponentsInChildren<Renderer>()" in physics
    assert "BoxCollider" in physics
    assert "Rigidbody" in physics
    assert "body.useGravity = false" in physics
    assert "body.isKinematic = true" in physics
    assert "EnablePlacedPhysics" in physics
    assert "body.isKinematic = false" not in physics
    assert "RigidbodyConstraints.FreezeAll" in physics
    assert "body.WakeUp()" not in physics
    assert "sourceBounds" not in physics

    enable_method = _method_slice(physics, "public static void EnablePlacedPhysics", "private static void ConfigureAuthoredTransformBody")
    assert "ConfigurePostImport" not in enable_method
    assert "ConfigureAuthoredTransformBody(body)" in enable_method


def test_scene_bootstrap_enables_placed_physics_without_schema_changes() -> None:
    bootstrap = _read(SCENE_DIR / "OasisSceneBootstrap.cs")
    document = _read(PERSISTENCE_DIR / "OasisWorldDocument.cs")

    assert "OasisPlacedAssetPhysics.EnablePlacedPhysics(activeImportedObject)" in bootstrap
    assert bootstrap.count("OasisPlacedAssetPhysics.EnablePlacedPhysics(obj)") == 2
    assert "SyncWorldTransformsFromScene()" in bootstrap

    assert "Rigidbody" not in document
    assert "Collider" not in document
    assert "physics" not in document.lower()


def test_time_of_day_uses_scene_settings_only_and_preserves_unknown_keys() -> None:
    settings = _read(PERSISTENCE_DIR / "OasisSceneSettings.cs")
    controller = _read(SCENE_DIR / "OasisTimeOfDayController.cs")
    bootstrap = _read(SCENE_DIR / "OasisSceneBootstrap.cs")
    history = _read(PERSISTENCE_DIR / "OasisCreatorHistory.cs")
    document = _read(PERSISTENCE_DIR / "OasisWorldDocument.cs")

    assert "scene_settings_json" in document
    assert "time_of_day" not in document
    assert "OasisSceneSettings.SetTimeOfDay(worldDocument" in controller
    assert "currentTimeOfDay = OasisSceneSettings.GetTimeOfDay(worldDocument)" in controller
    assert "FlushToWorldDocument()" in controller
    assert "timeOfDayController.Initialize(activeWorld, directionalSun)" in bootstrap
    assert "timeOfDayController.FlushToWorldDocument()" in bootstrap
    assert "scene_settings_json = \"{ \\\"time_of_day\\\": 0.5 }\"" in bootstrap

    assert "OasisWorldObject" not in settings
    assert "objects" not in settings
    assert "scene_settings" not in history
    assert "time_of_day" not in history

    original = {"time_of_day": 0.25, "weather": {"fog": 0.4}, "custom": ["keep"]}
    updated = _set_time_of_day(original, 0.75)
    assert updated["time_of_day"] == 0.75
    assert updated["weather"] == {"fog": 0.4}
    assert updated["custom"] == ["keep"]


def test_time_of_day_is_not_added_to_objects_or_operation_model() -> None:
    history = _read(PERSISTENCE_DIR / "OasisCreatorHistory.cs")
    bootstrap = _read(SCENE_DIR / "OasisSceneBootstrap.cs")

    create_object = _method_slice(bootstrap, "private OasisWorldObject CreateWorldObject", "private void HandlePlaceRequested")
    clone_object = _method_slice(bootstrap, "private static OasisWorldObject CloneWorldObject", "private OasisWorldObject CreateWorldObject")
    undo_redo = bootstrap[
        bootstrap.find("public async Task UndoAsync()") : bootstrap.find("private void DeleteObjectInMemory")
    ]

    assert "time_of_day" not in create_object
    assert "scene_settings" not in create_object
    assert "time_of_day" not in clone_object
    assert "scene_settings" not in clone_object
    assert "time_of_day" not in undo_redo
    assert "scene_settings" not in undo_redo
    assert not re.search(r"time|scene_settings", history)


def test_exploration_scripts_do_not_use_network_api_keys_or_secrets() -> None:
    exploration_files = [
        SCENE_DIR / "OasisFirstPersonController.cs",
        SCENE_DIR / "OasisTimeOfDayController.cs",
        IMPORT_DIR / "OasisPlacedAssetPhysics.cs",
        PERSISTENCE_DIR / "OasisSceneSettings.cs",
    ]
    combined = "\n".join(_read(path) for path in exploration_files)
    forbidden = (
        "UnityWebRequest",
        "HttpClient",
        "http://",
        "https://",
        "ANTHROPIC_API_KEY",
        "MESHY_API_KEY",
        ".env",
        "secrets",
    )
    for term in forbidden:
        assert term not in combined
