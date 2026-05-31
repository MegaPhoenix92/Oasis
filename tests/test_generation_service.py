from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.generation import HttpxMeshyClient, GenerationService
from oasis_ai.models import Spec
from oasis_ai.service import SpecService
from oasis_ai.telemetry import LocalTelemetry


class UnusedClaudeClient:
    def complete(self, prompt: str, normalized_prompt: str) -> str:
        raise AssertionError("Claude should not be called by Meshy generation tests")


class FakeClaudeClient:
    def complete(self, prompt: str, normalized_prompt: str) -> str:
        assert prompt == "a wooden treasure chest"
        assert normalized_prompt == "a wooden treasure chest"
        return (
            '{"schema_version":"1.0","source_prompt":"a wooden treasure chest",'
            '"normalized_prompt":"a wooden treasure chest","object_type":"prop",'
            '"name":"wooden treasure chest","materials":["wood","metal"],'
            '"style":"medieval","dimensions":{"width":1.0,"height":0.7,"depth":0.6},'
            '"details":["hinged lid","metal bands"],'
            '"meshy_prompt":"a medieval wooden treasure chest with metal bands"}'
        )


class FakeMeshyClient:
    def __init__(self, statuses: list[dict[str, Any]], glb_bytes: bytes = b"glb-bytes") -> None:
        self.statuses = statuses
        self.glb_bytes = glb_bytes
        self.created_payloads: list[Spec] = []
        self.provider_job_id = "provider-task-1"
        self.downloaded_urls: list[str] = []

    def create_preview_task(self, spec: Spec) -> str:
        self.created_payloads.append(spec)
        return self.provider_job_id

    def get_task(self, provider_job_id: str) -> dict[str, Any]:
        assert provider_job_id == self.provider_job_id
        return self.statuses.pop(0)

    def download_asset(self, source_url: str) -> bytes:
        self.downloaded_urls.append(source_url)
        return self.glb_bytes


def spec_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "source_prompt": "A Wooden   Chair",
        "normalized_prompt": "a wooden chair",
        "object_type": "furniture",
        "name": "wooden chair",
        "materials": ["wood"],
        "style": "medieval",
        "dimensions": {"width": 0.5, "height": 1.0, "depth": 0.5},
        "details": ["high back"],
        "meshy_prompt": "a medieval wooden chair with a high back",
    }


def glb_with_triangles(index_count: int) -> bytes:
    payload = {
        "asset": {"version": "2.0"},
        "meshes": [{"primitives": [{"indices": 0}]}],
        "accessors": [{"count": index_count}],
    }
    json_chunk = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    length = 12 + 8 + len(json_chunk)
    return b"glTF" + (2).to_bytes(4, "little") + length.to_bytes(4, "little") + len(json_chunk).to_bytes(4, "little") + b"JSON" + json_chunk


def client_with(fake_meshy: FakeMeshyClient, cache_dir: Path, max_generation_calls: int = 5) -> TestClient:
    telemetry = LocalTelemetry(cache_dir / "telemetry.jsonl", enabled=False)
    app = create_app(
        SpecService(UnusedClaudeClient()),
        GenerationService(fake_meshy, cache_dir=cache_dir, max_generation_calls=max_generation_calls, telemetry=telemetry),
        telemetry=telemetry,
    )
    return TestClient(app)


def test_generate_returns_immediate_pending_job(tmp_path: Path) -> None:
    fake_meshy = FakeMeshyClient([{"status": "PENDING"}])
    client = client_with(fake_meshy, tmp_path)

    response = client.post("/generate", json=spec_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["job_id"]
    assert len(fake_meshy.created_payloads) == 1
    assert fake_meshy.statuses == [{"status": "PENDING"}]


def test_create_chains_spec_to_generation_and_returns_immediate_pending_job(tmp_path: Path) -> None:
    fake_meshy = FakeMeshyClient([{"status": "PENDING"}])
    telemetry = LocalTelemetry(tmp_path / "telemetry.jsonl")
    app = create_app(
        SpecService(FakeClaudeClient()),
        GenerationService(fake_meshy, cache_dir=tmp_path, telemetry=telemetry),
        telemetry=telemetry,
    )
    client = TestClient(app)

    response = client.post("/create", json={"prompt": "a wooden treasure chest"})

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["job_id"]
    assert len(fake_meshy.created_payloads) == 1
    assert fake_meshy.created_payloads[0].meshy_prompt == "a medieval wooden treasure chest with metal bands"
    assert fake_meshy.statuses == [{"status": "PENDING"}]
    events = [line for line in (tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert len(events) == 3
    assert '"event":"prompt_submitted"' in events[0]
    assert '"event":"prompt_structured"' in events[1]
    assert '"event":"generation_submitted"' in events[2]


def test_polling_ready_downloads_cache_and_returns_locked_manifest(tmp_path: Path) -> None:
    source_url = "https://assets.meshy.ai/task/output/model.glb?Expires=test"
    glb = glb_with_triangles(6)
    fake_meshy = FakeMeshyClient(
        [
            {
                "status": "SUCCEEDED",
                "model_urls": {"glb": source_url},
                "texture_urls": [{"base_color": "texture.png"}],
            }
        ],
        glb_bytes=glb,
    )
    client = client_with(fake_meshy, tmp_path)

    generate = client.post("/generate", json=spec_payload())
    job_id = generate.json()["job_id"]
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["error_code"] is None
    manifest = body["manifest"]
    assert manifest["source_prompt"] == "A Wooden   Chair"
    assert manifest["normalized_prompt"] == "a wooden chair"
    assert manifest["spec"] == spec_payload()
    assert manifest["provider"] == "meshy.ai"
    assert manifest["job_id"] == "provider-task-1"
    assert manifest["source_url"] == source_url
    assert manifest["fetch_path"] == f"/assets/{manifest['asset_id']}"
    assert manifest["local_path"] == f"assets/generated/{manifest['asset_id']}.glb"
    assert manifest["checksum_sha256"] == hashlib.sha256(glb).hexdigest()
    assert manifest["format"] == "glb"
    assert manifest["file_size_bytes"] == len(glb)
    assert manifest["triangle_count"] == 2
    assert manifest["texture_count"] == 1
    assert (tmp_path / f"{manifest['asset_id']}.glb").read_bytes() == glb

    asset_response = client.get(manifest["fetch_path"])
    assert asset_response.status_code == 200
    assert asset_response.content == glb
    assert asset_response.headers["content-type"].startswith("model/gltf-binary")


def test_meshy_v2_payload_omits_art_style_and_caps_prompt() -> None:
    class CapturingMeshyClient(HttpxMeshyClient):
        def __init__(self) -> None:
            super().__init__(base_url="https://example.test/openapi/v2")
            self.payload: dict[str, Any] | None = None

        def _request_json(self, method: str, url: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
            self.payload = json
            return {"result": "provider-task-1"}

    payload = spec_payload()
    payload["meshy_prompt"] = "x" * 800
    client = CapturingMeshyClient()

    provider_job_id = client.create_preview_task(Spec.model_validate(payload))

    assert provider_job_id == "provider-task-1"
    assert client.payload is not None
    assert client.payload["mode"] == "preview"
    assert client.payload["target_formats"] == ["glb"]
    assert client.payload["target_polycount"] == 100_000
    assert len(client.payload["prompt"]) == 600
    assert "art_style" not in client.payload


def test_processing_status_is_reported_without_downloading(tmp_path: Path) -> None:
    fake_meshy = FakeMeshyClient([{"status": "IN_PROGRESS"}])
    client = client_with(fake_meshy, tmp_path)

    generate = client.post("/generate", json=spec_payload())
    response = client.get(f"/jobs/{generate.json()['job_id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "manifest": None, "error_code": None}
    assert fake_meshy.downloaded_urls == []


def test_failed_provider_status_returns_typed_failure(tmp_path: Path) -> None:
    fake_meshy = FakeMeshyClient([{"status": "FAILED", "task_error": {"message": "raw provider detail"}}])
    client = client_with(fake_meshy, tmp_path)

    generate = client.post("/generate", json=spec_payload())
    response = client.get(f"/jobs/{generate.json()['job_id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "failed", "manifest": None, "error_code": "provider_error"}


def test_unknown_job_returns_typed_not_found(tmp_path: Path) -> None:
    client = client_with(FakeMeshyClient([]), tmp_path)

    response = client.get("/jobs/unknown")

    assert response.status_code == 404
    assert response.json() == {"error_code": "asset_not_found", "message": "Generation job was not found."}


@pytest.mark.parametrize("asset_id", ["unknown", "..%2FREADME.md", "00000000-0000-4000-8000-000000000000"])
def test_assets_reject_unknown_uuid_and_path_traversal(asset_id: str, tmp_path: Path) -> None:
    client = client_with(FakeMeshyClient([]), tmp_path)

    response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 404
    assert response.json() == {"error_code": "asset_not_found", "message": "Asset was not found."}


def test_spend_guard_limits_generation_calls(tmp_path: Path) -> None:
    client = client_with(FakeMeshyClient([]), tmp_path, max_generation_calls=1)

    first = client.post("/generate", json=spec_payload())
    second = client.post("/generate", json=spec_payload())

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {
        "error_code": "spend_guard_exceeded",
        "message": "Meshy generation call limit was reached.",
    }
