from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "src/client"
SCENE_DIR = CLIENT / "Assets/Scripts/Oasis/Scene"
UI_DIR = CLIENT / "Assets/Scripts/Oasis/UI"


def test_refine_endpoint_is_synchronous_and_generation_is_single_path() -> None:
    app = (ROOT / "src/ai/oasis_ai/app.py").read_text(encoding="utf-8")
    service = (ROOT / "src/ai/oasis_ai/service.py").read_text(encoding="utf-8")
    facade = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")

    assert '@api.post("/refine"' in app
    assert "response_model=RefineResult" in app
    refine_endpoint = app[app.find('def refine('):app.find('@api.post(\n        "/generate"')]
    assert "generation_service" not in refine_endpoint
    assert "job_id" not in refine_endpoint
    assert "GenerationService" not in service

    assert 'NormalizeBaseUrl() + "/refine"' in facade
    assert "CoRefineFlow" in facade
    refine_flow = facade[facade.find("private IEnumerator CoRefineFlow"):facade.find("private IEnumerator CoGenerateFromSpecFlow")]
    assert '"/generate"' not in refine_flow
    assert '"job_id"' not in refine_flow
    assert "StartGenerationFromSpec" in facade
    assert 'NormalizeBaseUrl() + "/generate"' in facade
    assert 'NormalizeBaseUrl() + "/refine/create"' not in facade


def test_client_refine_router_uses_selected_object_and_prior_manifest_spec() -> None:
    ui = (UI_DIR / "OasisCreatorUI.cs").read_text(encoding="utf-8")
    scene = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")
    facade = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")

    assert "StartRefineFlow(OasisSpec priorSpec, string directive" in facade
    assert "RefineRequest" in facade
    assert "public OasisSpec prior_spec" in facade
    assert "OnRefineRequested" in ui or "PerformRefineTransform" in scene
    assert "selectedInstanceId" in scene or "FindWorldObject(instanceId)" in scene
    assert "selectedPriorSpec" in ui
    assert "result.spec" in ui
    assert "public string SelectedInstanceId" in ui
    assert "ClearSelectedObject" in ui
    assert "SetSelectedObject(instanceId, generatedAsset.Manifest.spec)" in scene


def test_generation_polling_uses_realtime_clock_for_timeouts() -> None:
    facade = (UI_DIR / "OasisGenerationFacade.cs").read_text(encoding="utf-8")
    polling = facade[facade.find("private IEnumerator CoPollJobAndDownload"):facade.find("private IEnumerator CoDownloadAsset")]

    assert "Time.realtimeSinceStartup" in polling
    assert "Time.time - startTime" not in facade


def test_transform_refine_reuses_move_and_never_generates() -> None:
    scene = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")

    transform_refine = scene[
        scene.find("public void PerformRefineTransform"):
        scene.find("public async Task ApplyRefineRespecAsync")
    ]
    assert "ComposeTransformDelta" in transform_refine
    assert "PerformMove(instanceId, target)" in transform_refine
    assert "StartGeneration" not in transform_refine
    assert "UnityWebRequest" not in transform_refine


def test_respec_refine_preserves_instance_and_undo_redo_do_not_regenerate() -> None:
    scene = (SCENE_DIR / "OasisSceneBootstrap.cs").read_text(encoding="utf-8")
    history = (CLIENT / "Assets/Scripts/Oasis/Persistence/OasisCreatorHistory.cs").read_text(encoding="utf-8")

    assert 'type = "refine"' in scene
    assert "before" in history and "after" in history
    assert "PinInSessionAsset(before.asset_id)" in scene
    assert "PinInSessionAsset(generatedAsset.Manifest.asset_id" in scene

    undo_redo = scene[scene.find("public async Task UndoAsync()"):scene.find("public void PerformMove(")]
    for forbidden in ("StartGeneration", "CoGenerate", "UnityWebRequest", "/generate", "/create"):
        assert forbidden not in undo_redo
    assert "RestoreRefineInMemoryAsync(op.before)" in undo_redo
    assert "RestoreRefineInMemoryAsync(op.after)" in undo_redo
