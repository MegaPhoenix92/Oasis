from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
FACADE = CLIENT / "Assets/Scripts/Oasis/UI/OasisGenerationFacade.cs"
PERSISTENCE = CLIENT / "Assets/Scripts/Oasis/Persistence/OasisWorldPersistence.cs"


def test_generation_facade_records_60fps_frame_budget_to_locked_sink() -> None:
    facade = FACADE.read_text(encoding="utf-8")

    assert "FrameBudgetTargetFps = 60f" in facade
    assert "Time.unscaledDeltaTime * 1000f" in facade
    assert "BeginFrameBudgetCounter()" in facade
    assert "FlushFrameBudgetCounter()" in facade
    assert '"unity-frame-budget"' in facade
    assert 'EmitTelemetry(\n                "generation_submitted"' in facade
    assert "elapsedOverrideMs" in facade
    assert "frameBudgetMaxFrameMs" in facade

    forbidden_new_events = [
        "frame_sample",
        "fps_sample",
        "frame_budget",
        "performance_sample",
    ]
    for event_name in forbidden_new_events:
        assert event_name not in facade, f"Frame budget must use the locked #24 event set, not {event_name}"


def test_world_load_manifest_and_glb_reads_are_backgrounded() -> None:
    persistence = PERSISTENCE.read_text(encoding="utf-8")

    assert "LoadAssetForObjectAsync" in persistence
    assert "await ReadAllTextAsync(manifestPath, cancellationToken)" in persistence
    assert "await ReadAllBytesAsync(assetPath, cancellationToken)" in persistence
    assert "OasisWorldPersistenceFailure failure = OasisWorldPersistenceFailure.None;" in persistence
    assert "bool validAssetBytes = OasisAssetManifestValidator.ValidateAssetBytes" in persistence
    assert "bool validChecksum = validAssetBytes && ValidateChecksum" in persistence
    assert "Task<byte[]> ReadAllBytesAsync" in persistence
    assert "File.ReadAllText(manifestPath" not in persistence
    assert "File.ReadAllBytes(assetPath" not in persistence
    assert "TryLoadAssetForObject" not in persistence


def test_bundle_import_extraction_and_checksum_are_backgrounded() -> None:
    persistence = PERSISTENCE.read_text(encoding="utf-8")

    assert "ReadBundleWorldJsonAsync" in persistence
    assert "WriteVerifiedBundleAssetsToDirectoryAsync" in persistence
    assert "Task.Run(() =>" in persistence
    assert "TryReadVerifiedBundleAsset(archive, assetId" in persistence
    assert "File.WriteAllText(Path.Combine(tempDirectory, ManifestsDirectoryName" in persistence
    assert "File.WriteAllBytes(Path.Combine(tempDirectory, AssetsDirectoryName" in persistence

    import_method = persistence[persistence.find("public async Task<OasisWorldLoadResult> ImportBundleAsync") : persistence.find("public async Task<OasisWorldPersistenceFailure> SaveAsync")]
    assert "using (ZipArchive archive" not in import_method
    assert "ReadArchiveEntryBytes(assetEntry)" not in import_method


def test_worlds_root_path_is_cached_before_background_io() -> None:
    persistence = PERSISTENCE.read_text(encoding="utf-8")

    assert "private string cachedWorldsRootPath" in persistence
    assert "cachedWorldsRootPath = Path.GetFullPath" in persistence
    assert "Application.persistentDataPath" in persistence

    async_helpers = persistence[
        persistence.find("private static Task<string> ReadBundleWorldJsonAsync") : persistence.find("private static string ReadArchiveEntryText")
    ]
    assert "Application.persistentDataPath" not in async_helpers
    assert "WorldsRootPath" not in async_helpers
