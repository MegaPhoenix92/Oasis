#!/usr/bin/env python3
"""Mocked M4 create-refine-voice-explore-capture-save demo validator."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/ai"))

from fastapi.testclient import TestClient  # noqa: E402

from oasis_ai.app import create_app  # noqa: E402
from oasis_ai.generation import GenerationService  # noqa: E402
from oasis_ai.metrics import UserStudyHookSink, derive_phase1_metrics, load_telemetry_jsonl, load_user_study_jsonl  # noqa: E402
from oasis_ai.models import Spec  # noqa: E402
from oasis_ai.service import RefineService, SpecService  # noqa: E402
from oasis_ai.telemetry import LocalTelemetry  # noqa: E402
from oasis_ai.voice import VoiceService  # noqa: E402


PROMPT = "a medieval wooden treasure chest with iron bands"
VOICE_TRANSCRIPT = "add a matching wooden table"
GLB_BYTES = b"glTF" + (2).to_bytes(4, "little") + (20).to_bytes(4, "little") + b"12345678"
RUNBOOK = ROOT / "docs/demo/M4_PLAYABLE_DEMO.md"
CLIENT = ROOT / "src/client/Assets/Scripts/Oasis"


class MockClaudeClient:
    def complete(self, prompt: str, normalized_prompt: str, system_prompt: str = "") -> str:
        if "transform" in system_prompt.lower() and "respec" in system_prompt.lower():
            return json.dumps(
                {
                    "kind": "transform",
                    "transform_delta": {
                        "scale_factor": {"x": 1.2, "y": 1.2, "z": 1.2},
                        "rotation_delta": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        "translate": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "rationale": "size-only demo refine",
                }
            )

        return json.dumps(
            {
                "schema_version": "1.0",
                "source_prompt": prompt,
                "normalized_prompt": normalized_prompt,
                "object_type": "prop",
                "name": "medieval treasure chest",
                "materials": ["wood", "iron"],
                "style": "medieval",
                "dimensions": {"width": 1.0, "height": 0.7, "depth": 0.6},
                "details": ["hinged lid", "iron bands", "front latch"],
                "meshy_prompt": "a medieval wooden treasure chest with iron bands and a front latch",
            }
        )


class MockMeshyClient:
    provider_job_id = "mock-m4-demo-task"

    def __init__(self) -> None:
        self.created_specs: list[Spec] = []
        self.downloaded_urls: list[str] = []

    def create_preview_task(self, spec: Spec) -> str:
        self.created_specs.append(spec)
        return self.provider_job_id

    def get_task(self, provider_job_id: str) -> dict[str, Any]:
        if provider_job_id != self.provider_job_id:
            raise AssertionError("unexpected provider job")
        return {
            "status": "SUCCEEDED",
            "model_urls": {"glb": "https://assets.meshy.ai/mock/m4-demo.glb?Expires=mock"},
            "triangle_count": 4096,
            "texture_urls": [{"base_color": "mock-base-color.png"}],
        }

    def download_asset(self, source_url: str) -> bytes:
        self.downloaded_urls.append(source_url)
        return GLB_BYTES


class MockSttClient:
    def transcribe_file(self, audio_path: Path, content_type: str) -> str:
        return VOICE_TRANSCRIPT


def main() -> int:
    started_at = time.monotonic()
    require_runbook_contract()
    require_unity_wiring()

    with tempfile.TemporaryDirectory(prefix="oasis-m4-demo-") as temp_dir:
        temp_path = Path(temp_dir)
        telemetry = LocalTelemetry(temp_path / "telemetry.jsonl")
        study = UserStudyHookSink(temp_path / "study.jsonl")
        meshy = MockMeshyClient()
        claude = MockClaudeClient()
        app = create_app(
            SpecService(claude),
            GenerationService(meshy, cache_dir=temp_path / "assets", telemetry=telemetry),
            RefineService(claude),
            VoiceService(MockSttClient()),
            telemetry=telemetry,
            user_study_hooks=study,
        )
        client = TestClient(app)

        create = client.post("/create", json={"prompt": PROMPT})
        require(create.status_code == 200, f"/create failed: {create.text}")
        job_id = create.json()["job_id"]

        job = client.get(f"/jobs/{job_id}")
        require(job.status_code == 200, f"/jobs failed: {job.text}")
        manifest = job.json()["manifest"]
        require(job.json()["status"] == "ready", "generation did not become ready")
        require(manifest["fetch_path"] == f"/assets/{manifest['asset_id']}", "fetch_path mismatch")

        asset = client.get(manifest["fetch_path"])
        require(asset.status_code == 200, f"asset fetch failed: {asset.text}")
        require(hashlib.sha256(asset.content).hexdigest() == manifest["checksum_sha256"], "checksum mismatch")

        refine = client.post("/refine", json={"prior_spec": manifest["spec"], "directive": "make it larger and rotate it slightly"})
        require(refine.status_code == 200, f"/refine failed: {refine.text}")
        require(refine.json()["kind"] == "transform", "demo refine did not return transform")

        voice_audio = base64.b64encode(b"RIFFmock demo voice").decode("ascii")
        voice = client.post("/voice/transcribe", json={"audio_base64": voice_audio, "content_type": "audio/wav"})
        require(voice.status_code == 200, f"/voice/transcribe failed: {voice.text}")
        require(voice.json()["transcript"] == VOICE_TRANSCRIPT, "voice transcript mismatch")

        study_response = client.post(
            "/metrics/user-study",
            json={
                "session_id": "m4-demo-session",
                "prompt_id": "m4-demo-prompt",
                "flow_completed": True,
                "quality_score": 8,
                "voice_intent_correct": True,
                "refine_cycles": 1,
            },
        )
        require(study_response.status_code == 200, f"user-study hook failed: {study_response.text}")

        metrics = derive_phase1_metrics(
            load_telemetry_jsonl(temp_path / "telemetry.jsonl"),
            load_user_study_jsonl(temp_path / "study.jsonl"),
        )
        elapsed = time.monotonic() - started_at
        require(elapsed < 90.0, f"mock M4 validation exceeded CI budget: {elapsed:.3f}s")

        evidence = {
            "runbook": str(RUNBOOK.relative_to(ROOT)),
            "loop": ["create", "refine", "voice", "explore", "capture", "save"],
            "mock_provider_calls": False,
            "unity_editor_required": False,
            "ten_minute_script_seconds": 600,
            "job_id": job_id,
            "asset_id": manifest["asset_id"],
            "fetch_path": manifest["fetch_path"],
            "asset_bytes": len(asset.content),
            "refine_kind": refine.json()["kind"],
            "voice_transcript": voice.json()["transcript"],
            "metrics": metrics,
            "source_wiring": {
                "explore": "OasisFirstPersonController",
                "capture": "OasisCaptureService",
                "save": "OasisWorldPersistence",
            },
            "fallbacks": ["provider timeout", "voice unavailable", "asset import rejected", "frame budget drop", "save load failure"],
            "elapsed_seconds": round(elapsed, 3),
        }
        print(json.dumps(evidence, indent=2, sort_keys=True))
        print("Mock M4 playable demo validation passed.")
    return 0


def require_runbook_contract() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    required_terms = [
        "create -> refine -> voice -> explore -> capture -> save",
        "10-Minute Run Of Show",
        "Fallback A: provider timeout or Meshy outage",
        "Fallback B: voice device or STT unavailable",
        "Fallback C: import rejects an asset",
        "Fallback D: frame budget drops below 60 FPS",
        "Fallback E: save/load failure",
        "Do not start Gate 1->2 build work",
    ]
    for term in required_terms:
        require(term in text, f"runbook missing required term: {term}")


def require_unity_wiring() -> None:
    scene = (CLIENT / "Scene/OasisSceneBootstrap.cs").read_text(encoding="utf-8")
    ui = (CLIENT / "UI/OasisCreatorUI.cs").read_text(encoding="utf-8")
    capture = (CLIENT / "Capture/OasisCaptureService.cs").read_text(encoding="utf-8")
    persistence = (CLIENT / "Persistence/OasisWorldPersistence.cs").read_text(encoding="utf-8")

    required_pairs = [
        ("explore", "OasisFirstPersonController", scene),
        ("create", "OnGenerationReady", ui),
        ("refine", "OnRefineAssetReady", ui),
        ("voice", "SubmitVoiceTranscript", ui),
        ("capture", "CaptureShortClip", capture),
        ("save", "SaveAsync", persistence),
        ("load", "LoadAsync", persistence),
    ]
    for label, term, source in required_pairs:
        require(term in source, f"{label} wiring missing term: {term}")


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
