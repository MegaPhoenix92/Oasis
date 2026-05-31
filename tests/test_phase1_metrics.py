from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.generation import GenerationService
from oasis_ai.metrics import UserStudyHookSink, UserStudyObservation, derive_phase1_metrics, load_user_study_jsonl
from oasis_ai.models import Spec
from oasis_ai.service import RefineService, SpecService
from oasis_ai.telemetry import LocalTelemetry


ROOT = Path(__file__).resolve().parents[1]


class FakeClaudeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs

    def complete(self, prompt: str, normalized_prompt: str, system_prompt: str = "") -> str:
        return self.outputs.pop(0)


class FakeMeshyClient:
    def create_preview_task(self, spec: Spec) -> str:
        return "provider-task"

    def get_task(self, provider_job_id: str) -> dict[str, object]:
        return {"status": "PENDING"}

    def download_asset(self, source_url: str) -> bytes:
        return b"glb"


def spec_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source_prompt": "A Wooden Chair",
        "normalized_prompt": "a wooden chair",
        "object_type": "furniture",
        "name": "wooden chair",
        "materials": ["wood"],
        "style": "plain",
        "dimensions": {"width": 0.5, "height": 1.0, "depth": 0.5},
        "details": ["high back"],
        "meshy_prompt": "a plain wooden chair with a high back",
    }


def test_locked_telemetry_sanitizes_typed_fields_only(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    telemetry = LocalTelemetry(path)

    telemetry.emit(
        "flow_failed",
        session_id="alice@example.com",
        prompt_id="prompt with raw words",
        provider="Traceback with sk-test-key",
        elapsed_ms=-10,
        error_code="raw provider exception sk-test-key",
        asset_id="sk-test-key",
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert set(record) == {"event", "session_id", "prompt_id", "provider", "elapsed_ms", "error_code", "asset_id", "created_at"}
    assert record["event"] == "flow_failed"
    assert record["session_id"].startswith("sha256:")
    assert record["prompt_id"].startswith("sha256:")
    assert record["provider"] == ""
    assert record["elapsed_ms"] == 0
    assert record["error_code"] == "provider_error"
    assert record["asset_id"].startswith("sha256:")
    assert "sk-test-key" not in path.read_text(encoding="utf-8")
    assert "alice@example.com" not in path.read_text(encoding="utf-8")


def test_refine_endpoint_emits_existing_prompt_events_without_raw_directive(tmp_path: Path) -> None:
    telemetry_path = tmp_path / "telemetry.jsonl"
    fake = FakeClaudeClient(
        [
            json.dumps(
                {
                    "kind": "transform",
                    "transform_delta": {
                        "scale_factor": {"x": 1.1, "y": 1.1, "z": 1.1},
                        "rotation_delta": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        "translate": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "rationale": "size-only directive",
                }
            )
        ]
    )
    telemetry = LocalTelemetry(telemetry_path)
    client = TestClient(
        create_app(
            SpecService(fake),
            GenerationService(FakeMeshyClient(), cache_dir=tmp_path, telemetry=telemetry),
            RefineService(fake),
            telemetry=telemetry,
        )
    )

    response = client.post("/refine", json={"prior_spec": spec_payload(), "directive": "make it taller with secret words"})

    assert response.status_code == 200
    lines = telemetry_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"event":"prompt_submitted"' in lines[0]
    assert '"provider":"refine"' in lines[0]
    assert '"event":"prompt_structured"' in lines[1]
    assert "make it taller" not in telemetry_path.read_text(encoding="utf-8")


def test_user_study_hooks_are_separate_sanitized_inputs(tmp_path: Path) -> None:
    study_path = tmp_path / "study.jsonl"
    sink = UserStudyHookSink(study_path)
    sink.record(
        UserStudyObservation(
            session_id="person@example.com",
            prompt_id="prompt-1",
            flow_completed=True,
            quality_score=8,
            voice_intent_correct=True,
            refine_cycles=2,
        )
    )

    observations = load_user_study_jsonl(study_path)
    assert len(observations) == 1
    assert observations[0].session_id.startswith("sha256:")
    assert observations[0].quality_score == 8
    assert "person@example.com" not in study_path.read_text(encoding="utf-8")


def test_metrics_derivation_reports_phase1_targets(tmp_path: Path) -> None:
    telemetry_records = [
        {"event": "prompt_submitted", "session_id": "s1", "prompt_id": "p1", "provider": "", "elapsed_ms": 0, "error_code": "", "asset_id": ""},
        {"event": "generation_ready", "session_id": "s1", "prompt_id": "p1", "provider": "meshy.ai", "elapsed_ms": 25_000, "error_code": "", "asset_id": "a1"},
        {"event": "object_placed", "session_id": "s1", "prompt_id": "p1", "provider": "unity", "elapsed_ms": 26_000, "error_code": "", "asset_id": "a1"},
        {"event": "prompt_submitted", "session_id": "s1", "prompt_id": "r1", "provider": "refine", "elapsed_ms": 0, "error_code": "", "asset_id": ""},
    ]
    observations = [
        UserStudyObservation(session_id="s1", prompt_id="p1", flow_completed=True, quality_score=8, voice_intent_correct=True, refine_cycles=1),
        UserStudyObservation(session_id="s2", prompt_id="p2", flow_completed=True, quality_score=7, voice_intent_correct=True, refine_cycles=2),
    ]

    metrics = derive_phase1_metrics(telemetry_records, observations)

    assert metrics["generation_latency"]["passed"] is True
    assert metrics["voice_intent_accuracy"]["value"] == 1.0
    assert metrics["refinement_cycles"]["passed"] is True
    assert metrics["flow_completion"]["value"] == 1.0
    assert metrics["asset_quality"]["value"] == 7.5
    assert metrics["inputs"]["schema"] == "0002-section-5-jsonl-plus-sanitized-study-hooks"


def test_refinement_cycles_value_and_pass_use_average() -> None:
    observations = [
        UserStudyObservation(session_id=f"s{index}", prompt_id=f"p{index}", refine_cycles=cycles)
        for index, cycles in enumerate([0, 0, 0, 5], start=1)
    ]

    metrics = derive_phase1_metrics([], observations)

    assert metrics["refinement_cycles"]["value"] == 1.25
    assert metrics["refinement_cycles"]["passed"] is True


def test_user_study_hook_without_sink_logs_warning(tmp_path: Path, caplog) -> None:
    client = TestClient(create_app(telemetry=LocalTelemetry(tmp_path / "telemetry.jsonl", enabled=False)))

    with caplog.at_level(logging.WARNING, logger="oasis_ai.app"):
        response = client.post(
            "/metrics/user-study",
            json={
                "session_id": "s1",
                "prompt_id": "p1",
                "flow_completed": True,
                "quality_score": 8,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
    assert "no hook sink is configured" in caplog.text


def test_phase1_metrics_cli_reads_jsonl(tmp_path: Path) -> None:
    telemetry_path = tmp_path / "telemetry.jsonl"
    telemetry_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "prompt_submitted",
                        "session_id": "s1",
                        "prompt_id": "p1",
                        "provider": "",
                        "elapsed_ms": 0,
                        "error_code": "",
                        "asset_id": "",
                    }
                ),
                json.dumps(
                    {
                        "event": "generation_ready",
                        "session_id": "s1",
                        "prompt_id": "p1",
                        "provider": "meshy.ai",
                        "elapsed_ms": 20_000,
                        "error_code": "",
                        "asset_id": "a1",
                    }
                ),
            ]
        )
    )
    study_path = tmp_path / "study.jsonl"
    study_path.write_text(UserStudyObservation(session_id="s1", prompt_id="p1", flow_completed=True, quality_score=9).model_dump_json() + "\n")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/derive_phase1_metrics.py"), "--telemetry", str(telemetry_path), "--user-study", str(study_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = json.loads(result.stdout)
    assert output["generation_latency"]["passed"] is True
    assert output["asset_quality"]["value"] == 9.0
