"""FastAPI entrypoint for the Oasis AI service."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .generation import GenerationError, GenerationService, HttpxMeshyClient
from .models import ErrorResponse, GenerateResponse, JobResponse, PromptRequest, Spec
from .service import AnthropicSpecClient, SpecError, SpecService


def create_app(service: SpecService | None = None, generation_service: GenerationService | None = None) -> FastAPI:
    api = FastAPI(title="Oasis AI Service", version="0.1.0")
    api.state.spec_service = service or SpecService(AnthropicSpecClient())
    api.state.generation_service = generation_service or GenerationService(HttpxMeshyClient())

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
