from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
PERSISTENCE_DIR = CLIENT / "Assets/Scripts/Oasis/Persistence"
SCENE_DIR = CLIENT / "Assets/Scripts/Oasis/Scene"
UI_DIR = CLIENT / "Assets/Scripts/Oasis/UI"


def test_creator_history_class_contracts() -> None:
    history_content = (PERSISTENCE_DIR / "OasisCreatorHistory.cs").read_text(encoding="utf-8")

    # Verify standard operation payload fields
    assert "public string type" in history_content
    assert "public OasisWorldObject snapshot" in history_content
    assert "public OasisWorldObject before" in history_content
    assert "public OasisWorldObject after" in history_content
    assert "public string instance_id" in history_content
    assert "public OasisWorldTransform from" in history_content
    assert "public OasisWorldTransform to" in history_content

    # Verify history state methods and stacks
    assert "Stack<OasisCreatorOperation> undoStack" in history_content
    assert "Stack<OasisCreatorOperation> redoStack" in history_content
    assert "PushOperation" in history_content
    assert "PopUndo" in history_content
    assert "PopRedo" in history_content
    assert "Clear" in history_content
    assert "ReferencesAsset" in history_content

    # Invariant: new operation clears redo
    assert "redoStack.Clear()" in history_content


def test_place_and_delete_use_full_snapshots_and_byte_exact_restore() -> None:
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    # Verify that placing uses full snapshots
    assert "new OasisCreatorOperation" in bootstrap_content
    assert 'type = "place"' in bootstrap_content
    assert "snapshot = CloneWorldObject(worldObject)" in bootstrap_content

    # Verify that deleting uses full snapshots
    assert 'type = "delete"' in bootstrap_content
    assert "snapshot = CloneWorldObject(wObj)" in bootstrap_content

    # Verify restoration methods clone/restore exactly
    assert "RestoreObjectInMemoryAsync" in bootstrap_content
    assert "DeleteObjectInMemory" in bootstrap_content
    assert "CloneWorldObject" in bootstrap_content
    assert "CloneWorldTransform" in bootstrap_content


def test_move_uses_full_from_to_transforms_and_restores_exactly() -> None:
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    # Verify that move uses full from and to transforms, not a delta
    assert 'type = "move"' in bootstrap_content
    assert "from = CloneWorldTransform(wObj.transform)" in bootstrap_content
    assert "to = CloneWorldTransform(toTransform)" in bootstrap_content
    
    # Verify that applying and restoring transform exists
    assert "RestoreMoveInMemory" in bootstrap_content
    assert "ApplyTransform" in bootstrap_content


def test_refine_uses_full_before_after_snapshots_and_pinned_assets() -> None:
    history_content = (PERSISTENCE_DIR / "OasisCreatorHistory.cs").read_text(encoding="utf-8")
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    assert 'type = "refine"' in bootstrap_content
    assert "before = CloneWorldObject(before)" in bootstrap_content
    assert "after = CloneWorldObject(after)" in bootstrap_content
    assert "RestoreRefineInMemoryAsync(op.before)" in bootstrap_content
    assert "RestoreRefineInMemoryAsync(op.after)" in bootstrap_content
    assert "PinInSessionAsset(before.asset_id)" in bootstrap_content
    assert "PinInSessionAsset(generatedAsset.Manifest.asset_id" in bootstrap_content
    assert "creatorHistory.ReferencesAsset(assetId)" in bootstrap_content
    assert "op.before != null && op.before.asset_id == assetId" in history_content
    assert "op.after != null && op.after.asset_id == assetId" in history_content


def test_refine_respec_commit_is_atomic_and_preserves_instance_id() -> None:
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    apply_refine = bootstrap_content[
        bootstrap_content.find("public async Task ApplyRefineRespecAsync"):
        bootstrap_content.find("public void PerformDelete")
    ]
    assert "TryBeginRespec(instanceId)" in apply_refine
    assert "replacement.name = \"OasisObject_\" + instanceId" in apply_refine
    assert "behaviour.instanceId = instanceId" in apply_refine
    assert "after.asset_id = generatedAsset.Manifest.asset_id" in apply_refine
    assert "ReplaceWorldObject(after)" in apply_refine
    assert "creatorHistory.PushOperation(op)" in apply_refine
    assert "catch (Exception)" in apply_refine
    assert "ReplaceWorldObject(before)" in apply_refine
    assert "FinishRespec(instanceId)" in apply_refine
    assert "lock (respecInFlightLock)" in bootstrap_content


def test_undo_redo_do_not_reference_generation_or_network_or_paths() -> None:
    history_content = (PERSISTENCE_DIR / "OasisCreatorHistory.cs").read_text(encoding="utf-8")
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    # Extract UndoAsync and RedoAsync implementations
    undo_index = bootstrap_content.find("public async Task UndoAsync()")
    redo_index = bootstrap_content.find("public async Task RedoAsync()")
    assert undo_index != -1, "UndoAsync method must exist in OasisSceneBootstrap"
    assert redo_index != -1, "RedoAsync method must exist in OasisSceneBootstrap"
    
    # Check that neither class nor method invokes backend/network/persistence loading
    forbidden_terms = [
        "FetchAssetAsync",
        "UnityWebRequest",
        "HttpClient",
        "fetch_path",
        "source_url",
        "local_path",
        "SaveAsync",
        "ExportBundleAsync",
    ]

    for term in forbidden_terms:
        # History script must not touch filesystem / network
        assert term not in history_content

    # Let's inspect the undo/redo flow context in bootstrap (methods UndoAsync, RedoAsync, RestoreObjectInMemoryAsync, RestoreMoveInMemory, DeleteObjectInMemory)
    # We assert these specific methods don't touch network or save/load
    perform_move_index = bootstrap_content.find("public void PerformMove(")
    assert perform_move_index != -1
    relevant_flow_content = bootstrap_content[undo_index:perform_move_index]
    
    for term in forbidden_terms:
        # The relevant in-memory undo/redo methods must not trigger fetching or saving or loading from network/disk
        assert term not in relevant_flow_content


def test_operations_affect_objects_only_and_not_scene_settings() -> None:
    history_content = (PERSISTENCE_DIR / "OasisCreatorHistory.cs").read_text(encoding="utf-8")
    bootstrap_content = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    # Invariant: OasisCreatorOperation does not track scene_settings
    assert "scene_settings" not in history_content
    assert "scene_settings_json" not in history_content

    # Invariant: Undo/Redo logic doesn't touch scene settings
    undo_index = bootstrap_content.find("public async Task UndoAsync()")
    perform_move_index = bootstrap_content.find("public void PerformMove(")
    assert undo_index != -1 and perform_move_index != -1
    relevant_flow_content = bootstrap_content[undo_index:perform_move_index]
    assert "scene_settings" not in relevant_flow_content
    assert "scene_settings_json" not in relevant_flow_content
