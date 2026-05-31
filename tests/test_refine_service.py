from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.generation import GenerationService
from oasis_ai.models import Spec
from oasis_ai.service import RefineService, SpecService
from oasis_ai.telemetry import LocalTelemetry


class FakeClaudeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, str]] = []

    def complete(self, prompt: str, normalized_prompt: str, system_prompt: str = "") -> str:
        self.calls.append((prompt, normalized_prompt))
        assert "transform" in system_prompt.lower()
        assert "respec" in system_prompt.lower()
        return self.outputs.pop(0)


class FakeMeshyClient:
    def __init__(self) -> None:
        self.created_payloads: list[Spec] = []

    def create_preview_task(self, spec: Spec) -> str:
        self.created_payloads.append(spec)
        return "provider-refine-task"

    def get_task(self, provider_job_id: str) -> dict[str, Any]:
        return {"status": "PENDING"}

    def download_asset(self, source_url: str) -> bytes:
        return b"glb"


def spec_payload() -> dict[str, Any]:
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


def respec_output() -> str:
    payload = spec_payload()
    payload.update(
        {
            "source_prompt": "ignored",
            "normalized_prompt": "ignored",
            "style": "medieval",
            "details": ["high back", "carved trim"],
            "meshy_prompt": "a medieval wooden chair with carved trim",
        }
    )
    return json.dumps({"kind": "respec", "spec": payload, "rationale": "style change requires new geometry"})


def client_with(fake: FakeClaudeClient, tmp_path: Path, fake_meshy: FakeMeshyClient | None = None) -> TestClient:
    telemetry = LocalTelemetry(tmp_path / "telemetry.jsonl", enabled=False)
    return TestClient(
        create_app(
            SpecService(fake),
            GenerationService(fake_meshy or FakeMeshyClient(), cache_dir=tmp_path, max_generation_calls=1, telemetry=telemetry),
            RefineService(fake),
            telemetry=telemetry,
        )
    )


def test_refine_transform_is_synchronous_discriminated_and_zero_cost(tmp_path: Path) -> None:
    fake = FakeClaudeClient(
        [
            json.dumps(
                {
                    "kind": "transform",
                    "transform_delta": {
                        "scale_factor": {"x": 1.5, "y": 1.5, "z": 1.5},
                        "rotation_delta": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        "translate": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "rationale": "size-only directive",
                }
            )
        ]
    )
    fake_meshy = FakeMeshyClient()
    client = client_with(fake, tmp_path, fake_meshy)

    response = client.post("/refine", json={"prior_spec": spec_payload(), "directive": "make it bigger"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "transform"
    assert body["transform_delta"]["scale_factor"] == {"x": 1.5, "y": 1.5, "z": 1.5}
    assert body["spec"] is None
    assert "job_id" not in body
    assert fake.calls[0][1] == "make it bigger"
    assert fake_meshy.created_payloads == []


def test_refine_respec_returns_full_spec_with_composed_lineage_and_no_job(tmp_path: Path) -> None:
    fake = FakeClaudeClient([respec_output()])
    fake_meshy = FakeMeshyClient()
    client = client_with(fake, tmp_path, fake_meshy)

    response = client.post("/refine", json={"prior_spec": spec_payload(), "directive": "make it medieval"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "respec"
    assert body["transform_delta"] is None
    assert "job_id" not in body
    assert body["spec"]["schema_version"] == "1.0"
    assert body["spec"]["source_prompt"] == "A Wooden Chair \u2192 make it medieval"
    assert body["spec"]["normalized_prompt"] == "a wooden chair \u2192 make it medieval"
    assert body["spec"]["style"] == "medieval"
    assert fake_meshy.created_payloads == []


def test_refine_rejects_bad_directive_and_sanitizes_model_parse_errors(tmp_path: Path) -> None:
    empty = client_with(FakeClaudeClient([]), tmp_path)
    empty_response = empty.post("/refine", json={"prior_spec": spec_payload(), "directive": " \n\t "})
    assert empty_response.status_code == 400
    assert empty_response.json() == {"error_code": "invalid_prompt", "message": "Prompt must not be empty."}

    malformed = client_with(FakeClaudeClient(["raw provider stack with secret-ish details"]), tmp_path)
    malformed_response = malformed.post("/refine", json={"prior_spec": spec_payload(), "directive": "add windows"})
    assert malformed_response.status_code == 502
    assert malformed_response.json() == {
        "error_code": "model_parse_error",
        "message": "Claude response did not match the RefineResult schema.",
    }


def test_refine_rejects_unsafe_transform_shape_and_sanitizes_error(tmp_path: Path) -> None:
    tiny_scale = json.dumps(
        {
            "kind": "transform",
            "transform_delta": {
                "scale_factor": {"x": 0.001, "y": 1.0, "z": 1.0},
                "rotation_delta": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                "translate": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
            "rationale": "unsafe tiny axis",
        }
    )
    tiny_response = client_with(FakeClaudeClient([tiny_scale]), tmp_path).post(
        "/refine",
        json={"prior_spec": spec_payload(), "directive": "make it almost flat"},
    )

    assert tiny_response.status_code == 502
    assert tiny_response.json() == {
        "error_code": "model_parse_error",
        "message": "Claude response did not match the RefineResult schema.",
    }

    non_unit_rotation = json.dumps(
        {
            "kind": "transform",
            "transform_delta": {
                "scale_factor": {"x": 1.0, "y": 1.0, "z": 1.0},
                "rotation_delta": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 2.0},
                "translate": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
            "rationale": "bad rotation",
        }
    )
    rotation_response = client_with(FakeClaudeClient([non_unit_rotation]), tmp_path).post(
        "/refine",
        json={"prior_spec": spec_payload(), "directive": "turn it strangely"},
    )

    assert rotation_response.status_code == 502
    assert rotation_response.json() == {
        "error_code": "model_parse_error",
        "message": "Claude response did not match the RefineResult schema.",
    }


def test_respec_uses_existing_generate_path_and_spend_guard_after_refine(tmp_path: Path) -> None:
    fake = FakeClaudeClient([respec_output()])
    fake_meshy = FakeMeshyClient()
    client = client_with(fake, tmp_path, fake_meshy)

    refine = client.post("/refine", json={"prior_spec": spec_payload(), "directive": "add windows"})
    assert refine.status_code == 200
    assert fake_meshy.created_payloads == []

    first_generate = client.post("/generate", json=refine.json()["spec"])
    second_generate = client.post("/generate", json=refine.json()["spec"])

    assert first_generate.status_code == 200
    assert second_generate.status_code == 429
    assert second_generate.json()["error_code"] == "spend_guard_exceeded"
    assert len(fake_meshy.created_payloads) == 1
