"""Meshy-backed async asset generation service."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from .models import AssetManifest, Spec
from .telemetry import LocalTelemetry, elapsed_ms, new_prompt_id, new_session_id

MESHY_BASE_URL = "https://api.meshy.ai/openapi/v2"
DEFAULT_TARGET_POLYCOUNT = 100_000
DEFAULT_MAX_GENERATION_CALLS = 5
MAX_MESHY_PROMPT_CHARS = 600

JobStatus = Literal["pending", "processing", "ready", "failed"]


class GenerationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class MeshyClient(Protocol):
    def create_preview_task(self, spec: Spec) -> str:
        """Create a Meshy preview task and return the provider task id."""

    def get_task(self, provider_job_id: str) -> dict[str, Any]:
        """Return the provider task object."""

    def download_asset(self, source_url: str) -> bytes:
        """Download generated GLB bytes from a provider URL."""


class HttpxMeshyClient:
    def __init__(self, base_url: str = MESHY_BASE_URL, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def create_preview_task(self, spec: Spec) -> str:
        payload = {
            "mode": "preview",
            "prompt": _meshy_prompt(spec),
            "target_polycount": DEFAULT_TARGET_POLYCOUNT,
            "target_formats": ["glb"],
        }
        data = self._request_json("POST", f"{self.base_url}/text-to-3d", json=payload)
        provider_job_id = data.get("result")
        if not isinstance(provider_job_id, str) or not provider_job_id:
            raise GenerationError("provider_error", "Meshy response did not include a task id.", 502)
        return provider_job_id

    def get_task(self, provider_job_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"{self.base_url}/text-to-3d/{provider_job_id}")

    def download_asset(self, source_url: str) -> bytes:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(source_url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise GenerationError("timeout", "Meshy asset download timed out.", 504) from exc
        except httpx.HTTPError as exc:
            raise GenerationError("provider_error", "Meshy asset download failed.", 502) from exc

        if not response.content:
            raise GenerationError("provider_error", "Meshy asset download was empty.", 502)
        return response.content

    def _request_json(self, method: str, url: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        api_key = os.getenv("MESHY_API_KEY")
        if not api_key:
            raise GenerationError("provider_error", "Meshy API key is not configured.", 502)

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(method, url, headers=headers, json=json)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise GenerationError("timeout", "Meshy API request timed out.", 504) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise GenerationError("provider_error", "Meshy API request failed.", 502) from exc

        if not isinstance(data, dict):
            raise GenerationError("provider_error", "Meshy API response was invalid.", 502)
        return data


@dataclass
class GenerationJob:
    job_id: str
    provider_job_id: str | None
    spec: Spec
    status: JobStatus
    session_id: str
    prompt_id: str
    started_at: float
    manifest: AssetManifest | None = None
    error_code: str | None = None
    generation_ready_emitted: bool = False


class GenerationService:
    def __init__(
        self,
        client: MeshyClient,
        cache_dir: Path | None = None,
        max_generation_calls: int | None = None,
        telemetry: LocalTelemetry | None = None,
    ) -> None:
        self.client = client
        self.cache_dir = cache_dir or _repo_root() / "assets" / "generated"
        self.max_generation_calls = max_generation_calls if max_generation_calls is not None else _max_generation_calls_from_env()
        self.telemetry = telemetry or LocalTelemetry()
        self._generation_calls = 0
        self._jobs: dict[str, GenerationJob] = {}
        self._manifests_by_asset_id: dict[str, AssetManifest] = {}

    def submit(
        self,
        spec: Spec,
        *,
        session_id: str | None = None,
        prompt_id: str | None = None,
        started_at: float | None = None,
    ) -> GenerationJob:
        if self._generation_calls >= self.max_generation_calls:
            raise GenerationError("spend_guard_exceeded", "Meshy generation call limit was reached.", 429)

        self._generation_calls += 1
        job_id = str(uuid.uuid4())
        job = GenerationJob(
            job_id=job_id,
            provider_job_id=None,
            spec=spec,
            status="pending",
            session_id=session_id or new_session_id(),
            prompt_id=prompt_id or new_prompt_id(),
            started_at=started_at if started_at is not None else time.monotonic(),
        )
        self._jobs[job_id] = job

        try:
            job.provider_job_id = self.client.create_preview_task(spec)
            self.telemetry.emit(
                "generation_submitted",
                session_id=job.session_id,
                prompt_id=job.prompt_id,
                provider="meshy.ai",
                elapsed_ms=elapsed_ms(job.started_at),
            )
        except GenerationError as exc:
            job.status = "failed"
            job.error_code = exc.error_code
            self.telemetry.emit(
                "flow_failed",
                session_id=job.session_id,
                prompt_id=job.prompt_id,
                provider="meshy.ai",
                elapsed_ms=elapsed_ms(job.started_at),
                error_code=exc.error_code,
            )
            raise

        return job

    def get_job(self, job_id: str) -> GenerationJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise GenerationError("asset_not_found", "Generation job was not found.", 404)
        if job.status in {"ready", "failed"}:
            return job
        if job.provider_job_id is None:
            return job

        try:
            task = self.client.get_task(job.provider_job_id)
            self._apply_task(job, task)
        except GenerationError as exc:
            job.status = "failed"
            job.error_code = exc.error_code
            self.telemetry.emit(
                "flow_failed",
                session_id=job.session_id,
                prompt_id=job.prompt_id,
                provider="meshy.ai",
                elapsed_ms=elapsed_ms(job.started_at),
                error_code=exc.error_code,
            )
        return job

    def asset_path(self, asset_id: str) -> Path:
        try:
            uuid.UUID(asset_id, version=4)
        except ValueError as exc:
            raise GenerationError("asset_not_found", "Asset was not found.", 404) from exc

        manifest = self._manifests_by_asset_id.get(asset_id)
        if manifest is None:
            raise GenerationError("asset_not_found", "Asset was not found.", 404)

        path = (self.cache_dir / f"{asset_id}.glb").resolve()
        cache_root = self.cache_dir.resolve()
        if path.parent != cache_root or not path.is_file():
            raise GenerationError("asset_not_found", "Asset was not found.", 404)
        return path

    def _apply_task(self, job: GenerationJob, task: dict[str, Any]) -> None:
        status = str(task.get("status", "")).upper()
        if status == "PENDING":
            job.status = "pending"
            return
        if status in {"IN_PROGRESS", "PROCESSING"}:
            job.status = "processing"
            return
        if status in {"FAILED", "CANCELED", "CANCELLED"}:
            job.status = "failed"
            job.error_code = "provider_error"
            return
        if status != "SUCCEEDED":
            job.status = "failed"
            job.error_code = "provider_error"
            return

        source_url = _glb_url(task)
        if not source_url:
            job.status = "failed"
            job.error_code = "provider_error"
            return

        glb_bytes = self.client.download_asset(source_url)
        manifest = self._cache_asset(job, source_url, glb_bytes, task)
        job.status = "ready"
        job.manifest = manifest
        job.error_code = None
        self._manifests_by_asset_id[manifest.asset_id] = manifest
        if not job.generation_ready_emitted:
            self.telemetry.emit(
                "generation_ready",
                session_id=job.session_id,
                prompt_id=job.prompt_id,
                provider="meshy.ai",
                elapsed_ms=elapsed_ms(job.started_at),
                asset_id=manifest.asset_id,
            )
            job.generation_ready_emitted = True

    def _cache_asset(self, job: GenerationJob, source_url: str, glb_bytes: bytes, task: dict[str, Any]) -> AssetManifest:
        asset_id = str(uuid.uuid4())
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{asset_id}.glb"
        path.write_bytes(glb_bytes)
        checksum = hashlib.sha256(glb_bytes).hexdigest()
        local_path = f"assets/generated/{asset_id}.glb"
        return AssetManifest(
            asset_id=asset_id,
            source_prompt=job.spec.source_prompt,
            normalized_prompt=job.spec.normalized_prompt,
            spec=job.spec,
            provider="meshy.ai",
            job_id=job.provider_job_id or job.job_id,
            source_url=source_url,
            fetch_path=f"/assets/{asset_id}",
            local_path=local_path,
            checksum_sha256=checksum,
            format="glb",
            file_size_bytes=len(glb_bytes),
            triangle_count=_triangle_count_from_glb(glb_bytes),
            texture_count=_texture_count(task),
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )


def _meshy_prompt(spec: Spec) -> str:
    return spec.meshy_prompt[:MAX_MESHY_PROMPT_CHARS]


def _glb_url(task: dict[str, Any]) -> str | None:
    model_urls = task.get("model_urls")
    if not isinstance(model_urls, dict):
        return None
    glb = model_urls.get("glb")
    return glb if isinstance(glb, str) and glb else None


def _texture_count(task: dict[str, Any]) -> int:
    textures = task.get("texture_urls")
    return len(textures) if isinstance(textures, list) else 0


def _triangle_count_from_glb(glb_bytes: bytes) -> int:
    try:
        gltf = _glb_json(glb_bytes)
    except (json.JSONDecodeError, struct.error, UnicodeDecodeError):
        return 0
    if not isinstance(gltf, dict):
        return 0

    meshes = gltf.get("meshes")
    accessors = gltf.get("accessors")
    if not isinstance(meshes, list) or not isinstance(accessors, list):
        return 0

    triangles = 0
    for mesh in meshes:
        if not isinstance(mesh, dict):
            continue
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list):
            continue
        for primitive in primitives:
            if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
                continue
            count = _primitive_vertex_count(primitive, accessors)
            if count > 0:
                triangles += count // 3
    return triangles


def _primitive_vertex_count(primitive: dict[str, Any], accessors: list[Any]) -> int:
    indices = primitive.get("indices")
    if isinstance(indices, int) and 0 <= indices < len(accessors):
        accessor = accessors[indices]
        if isinstance(accessor, dict) and isinstance(accessor.get("count"), int):
            return accessor["count"]

    attributes = primitive.get("attributes")
    position = attributes.get("POSITION") if isinstance(attributes, dict) else None
    if isinstance(position, int) and 0 <= position < len(accessors):
        accessor = accessors[position]
        if isinstance(accessor, dict) and isinstance(accessor.get("count"), int):
            return accessor["count"]
    return 0


def _glb_json(glb_bytes: bytes) -> Any:
    if len(glb_bytes) < 20:
        return {}
    magic, version, length = struct.unpack_from("<4sII", glb_bytes, 0)
    if magic != b"glTF" or version != 2 or length > len(glb_bytes):
        return {}

    offset = 12
    while offset + 8 <= length:
        chunk_length, chunk_type = struct.unpack_from("<II", glb_bytes, offset)
        offset += 8
        chunk_end = offset + chunk_length
        if chunk_end > length:
            return {}
        if chunk_type == 0x4E4F534A:
            return json.loads(glb_bytes[offset:chunk_end].decode("utf-8").rstrip(" \t\r\n\x00"))
        offset = chunk_end
    return {}


def _max_generation_calls_from_env() -> int:
    raw = os.getenv("OASIS_MESHY_MAX_GENERATIONS")
    if raw is None:
        return DEFAULT_MAX_GENERATION_CALLS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_GENERATION_CALLS
    return max(0, value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
