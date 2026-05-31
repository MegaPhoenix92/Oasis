"""FastAPI entrypoint for the Oasis AI service."""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .generation import GenerationError, GenerationService, HttpxMeshyClient
from .models import ErrorResponse, GenerateResponse, JobResponse, PromptRequest, Spec
from .service import AnthropicSpecClient, SpecError, SpecService
from .telemetry import LocalTelemetry, elapsed_ms, new_prompt_id, new_session_id


def create_app(
    service: SpecService | None = None,
    generation_service: GenerationService | None = None,
    telemetry: LocalTelemetry | None = None,
) -> FastAPI:
    api = FastAPI(title="Oasis AI Service", version="0.1.0")
    api.state.spec_service = service or SpecService(AnthropicSpecClient())
    api.state.telemetry = telemetry or LocalTelemetry()
    api.state.generation_service = generation_service or GenerationService(HttpxMeshyClient(), telemetry=api.state.telemetry)

    @api.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/spec", response_model=Spec, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
    def create_spec(payload: PromptRequest, request: Request) -> Spec:
        spec_service: SpecService = request.app.state.spec_service
        return spec_service.create_spec(payload.prompt)

    @api.post(
        "/generate",
        response_model=GenerateResponse,
        responses={429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    )
    def generate(spec: Spec, request: Request) -> GenerateResponse:
        generation: GenerationService = request.app.state.generation_service
        job = generation.submit(spec)
        return GenerateResponse(job_id=job.job_id, status="pending")

    @api.post(
        "/create",
        response_model=GenerateResponse,
        responses={
            400: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    def create(payload: PromptRequest, request: Request) -> GenerateResponse:
        started_at = time.monotonic()
        session_id = new_session_id()
        prompt_id = new_prompt_id()
        telemetry_sink: LocalTelemetry = request.app.state.telemetry
        telemetry_sink.emit("prompt_submitted", session_id=session_id, prompt_id=prompt_id, elapsed_ms=0)

        spec_service: SpecService = request.app.state.spec_service
        generation: GenerationService = request.app.state.generation_service

        try:
            spec = spec_service.create_spec(payload.prompt)
            telemetry_sink.emit(
                "prompt_structured",
                session_id=session_id,
                prompt_id=prompt_id,
                provider="anthropic",
                elapsed_ms=elapsed_ms(started_at),
            )
            job = generation.submit(spec, session_id=session_id, prompt_id=prompt_id, started_at=started_at)
        except (SpecError, GenerationError) as exc:
            provider = "anthropic" if isinstance(exc, SpecError) else "meshy.ai"
            telemetry_sink.emit(
                "flow_failed",
                session_id=session_id,
                prompt_id=prompt_id,
                provider=provider,
                elapsed_ms=elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            raise

        return GenerateResponse(job_id=job.job_id, status="pending")

    @api.get(
        "/jobs/{job_id}",
        response_model=JobResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_job(job_id: str, request: Request) -> JobResponse:
        generation: GenerationService = request.app.state.generation_service
        job = generation.get_job(job_id)
        return JobResponse(status=job.status, manifest=job.manifest, error_code=job.error_code)

    @api.get(
        "/assets/{asset_id:path}",
        responses={404: {"model": ErrorResponse}},
    )
    def get_asset(asset_id: str, request: Request) -> FileResponse:
        generation: GenerationService = request.app.state.generation_service
        path = generation.asset_path(asset_id)
        return FileResponse(path, media_type="model/gltf-binary", filename=f"{asset_id}.glb")

    @api.exception_handler(SpecError)
    def handle_spec_error(_: Request, exc: SpecError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error_code=exc.error_code, message=exc.message).model_dump(),
        )

    @api.exception_handler(GenerationError)
    def handle_generation_error(_: Request, exc: GenerationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error_code=exc.error_code, message=exc.message).model_dump(),
        )

    return api


app = create_app()
