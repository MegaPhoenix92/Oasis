#!/usr/bin/env python3
"""Mocked M1 prompt-to-object demo validator for issue #9.

This runs the locked prompt -> /create -> /jobs -> fetch_path asset download path
without live Claude, Meshy, or Unity Editor dependencies.
"""

from __future__ import annotations

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
from oasis_ai.models import Spec  # noqa: E402
from oasis_ai.service import SpecService  # noqa: E402
from oasis_ai.telemetry import LocalTelemetry  # noqa: E402


PROMPT = "a wooden treasure chest"
GLB_BYTES = b"glTF" + (2).to_bytes(4, "little") + (20).to_bytes(4, "little") + b"12345678"
PLACEMENT_POINT = {"x": 2.0, "y": 0.0, "z": -1.5}


class MockClaudeClient:
    def complete(self, prompt: str, normalized_prompt: str) -> str:
        if prompt != PROMPT or normalized_prompt != PROMPT:
            raise AssertionError("unexpected prompt")
        return json.dumps(
            {
                "schema_version": "1.0",
                "source_prompt": prompt,
                "normalized_prompt": normalized_prompt,
                "object_type": "prop",
                "name": "wooden treasure chest",
                "materials": ["wood", "iron"],
                "style": "medieval",
                "dimensions": {"width": 1.0, "height": 0.7, "depth": 0.6},
                "details": ["hinged lid", "iron bands", "front latch"],
                "meshy_prompt": "a medieval wooden treasure chest with iron bands and a front latch",
            }
        )


class MockMeshyClient:
    provider_job_id = "mock-meshy-treasure-chest"

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
            "model_urls": {"glb": "https://assets.meshy.ai/mock/treasure-chest.glb?Expires=mock"},
            "triangle_count": 4096,
            "texture_urls": [{"base_color": "mock-base-color.png"}],
        }

    def download_asset(self, source_url: str) -> bytes:
        self.downloaded_urls.append(source_url)
        return GLB_BYTES


def main() -> None:
    started_at = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="oasis-m1-demo-") as temp_dir:
        temp_path = Path(temp_dir)
        telemetry = LocalTelemetry(temp_path / "telemetry.jsonl")
        meshy = MockMeshyClient()
        app = create_app(
            SpecService(MockClaudeClient()),
            GenerationService(meshy, cache_dir=temp_path / "assets", telemetry=telemetry),
            telemetry=telemetry,
        )
        client = TestClient(app)

        create = client.post("/create", json={"prompt": PROMPT})
        require(create.status_code == 200, f"/create failed: {create.text}")
        create_body = create.json()
        require(create_body["status"] == "pending", "/create did not return pending")

        job = client.get(f"/jobs/{create_body['job_id']}")
        require(job.status_code == 200, f"/jobs failed: {job.text}")
        job_body = job.json()
        require(job_body["status"] == "ready", "mock generation did not become ready")

        manifest = job_body["manifest"]
        require(manifest["source_prompt"] == PROMPT, "manifest lost source prompt")
        require(manifest["fetch_path"] == f"/assets/{manifest['asset_id']}", "manifest fetch_path mismatch")

        asset = client.get(manifest["fetch_path"])
        require(asset.status_code == 200, f"asset fetch failed: {asset.text}")
        require(asset.content == GLB_BYTES, "asset bytes mismatch")
        require(asset.content[:4] == b"glTF", "asset is not a GLB payload")
        require(hashlib.sha256(asset.content).hexdigest() == manifest["checksum_sha256"], "checksum mismatch")
        require(not meshy.downloaded_urls[0].startswith(manifest["fetch_path"]), "backend did not own provider download")

        elapsed = time.monotonic() - started_at
        require(elapsed < 90.0, f"mock M1 demo exceeded 90s: {elapsed:.3f}s")

        telemetry_events = [
            json.loads(line)["event"]
            for line in (temp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for event in ("prompt_submitted", "prompt_structured", "generation_submitted", "generation_ready"):
            require(event in telemetry_events, f"missing telemetry event: {event}")

        evidence = {
            "prompt": PROMPT,
            "job_id": create_body["job_id"],
            "status": job_body["status"],
            "asset_id": manifest["asset_id"],
            "fetch_path": manifest["fetch_path"],
            "asset_bytes": len(asset.content),
            "checksum_sha256": manifest["checksum_sha256"],
            "placement_handoff": {"importer_input": "glb bytes + manifest json", "ground_anchor": PLACEMENT_POINT},
            "elapsed_seconds": round(elapsed, 3),
            "budget_seconds": 90,
            "telemetry_events": telemetry_events,
            "live_provider_calls": False,
            "unity_editor_required": False,
        }
        print(json.dumps(evidence, indent=2, sort_keys=True))
        print("Mock M1 prompt-to-object demo validation passed.")


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
