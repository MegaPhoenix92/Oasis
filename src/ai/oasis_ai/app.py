"""FastAPI entrypoint for the Oasis AI service."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .generation import GenerationError, GenerationService, HttpxMeshyClient
from .metrics import UserStudyHookSink, UserStudyObservation
from .models import ErrorResponse, GenerateResponse, JobResponse, PromptRequest, RefineRequest, RefineResult, Spec, UserStudyObservationRequest, UserStudyObservationResponse, VoiceTranscriptRequest, VoiceTranscriptResponse
from .service import AnthropicSpecClient, RefineService, SpecError, SpecService
from .telemetry import LocalTelemetry, elapsed_ms, new_prompt_id, new_session_id
from .voice import VoiceError, VoiceService


logger = logging.getLogger(__name__)


def create_app(
    service: SpecService | None = None,
    generation_service: GenerationService | None = None,
    refine_service: RefineService | None = None,
    voice_service: VoiceService | None = None,
    telemetry: LocalTelemetry | None = None,
    user_study_hooks: UserStudyHookSink | None = None,
) -> FastAPI:
    api = FastAPI(title="Oasis AI Service", version="0.1.0")
    api.state.spec_service = service or SpecService(AnthropicSpecClient())
    api.state.telemetry = telemetry or LocalTelemetry()
    api.state.generation_service = generation_service or GenerationService(HttpxMeshyClient(), telemetry=api.state.telemetry)
    api.state.refine_service = refine_service or RefineService(api.state.spec_service.client)
    api.state.voice_service = voice_service or VoiceService()
    api.state.user_study_hooks = user_study_hooks

    @api.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/spec", response_model=Spec, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
    def create_spec(payload: PromptRequest, request: Request) -> Spec:
        spec_service: SpecService = request.app.state.spec_service
        return spec_service.create_spec(payload.prompt)

    @api.post("/refine", response_model=RefineResult, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
    def refine(payload: RefineRequest, request: Request) -> RefineResult:
        started_at = time.monotonic()
        session_id = new_session_id()
        prompt_id = new_prompt_id()
        telemetry_sink: LocalTelemetry = request.app.state.telemetry
        telemetry_sink.emit("prompt_submitted", session_id=session_id, prompt_id=prompt_id, provider="refine", elapsed_ms=0)

        service: RefineService = request.app.state.refine_service
        try:
            result = service.refine(payload.prior_spec, payload.directive)
        except SpecError as exc:
            telemetry_sink.emit(
                "flow_failed",
                session_id=session_id,
                prompt_id=prompt_id,
                provider="refine",
                elapsed_ms=elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            raise

        telemetry_sink.emit(
            "prompt_structured",
            session_id=session_id,
            prompt_id=prompt_id,
            provider="refine",
            elapsed_ms=elapsed_ms(started_at),
        )
        return result

    @api.post(
        "/voice/transcribe",
        response_model=VoiceTranscriptResponse,
        responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    )
    def transcribe_voice(payload: VoiceTranscriptRequest, request: Request) -> VoiceTranscriptResponse:
        started_at = time.monotonic()
        session_id = new_session_id()
        prompt_id = new_prompt_id()
        telemetry_sink: LocalTelemetry = request.app.state.telemetry
        telemetry_sink.emit("prompt_submitted", session_id=session_id, prompt_id=prompt_id, provider="voice", elapsed_ms=0)

        voice: VoiceService = request.app.state.voice_service
        try:
            transcript = voice.transcribe(transcript=payload.transcript, audio_base64=payload.audio_base64, content_type=payload.content_type)
        except VoiceError as exc:
            telemetry_sink.emit(
                "flow_failed",
                session_id=session_id,
                prompt_id=prompt_id,
                provider="voice",
                elapsed_ms=elapsed_ms(started_at),
                error_code=exc.error_code,
            )
            raise

        telemetry_sink.emit(
            "prompt_structured",
            session_id=session_id,
            prompt_id=prompt_id,
            provider="voice",
            elapsed_ms=elapsed_ms(started_at),
        )
        return VoiceTranscriptResponse(transcript=transcript)

    @api.post(
        "/metrics/user-study",
        response_model=UserStudyObservationResponse,
        responses={422: {"model": ErrorResponse}},
    )
    def record_user_study_observation(payload: UserStudyObservationRequest, request: Request) -> UserStudyObservationResponse:
        hooks: UserStudyHookSink | None = request.app.state.user_study_hooks
        if hooks is not None:
            hooks.record(
                UserStudyObservation(
                    session_id=payload.session_id,
                    prompt_id=payload.prompt_id,
                    flow_completed=payload.flow_completed,
                    quality_score=payload.quality_score,
                    voice_intent_correct=payload.voice_intent_correct,
                    refine_cycles=payload.refine_cycles,
                )
            )
        else:
            logger.warning("User-study observation discarded because no hook sink is configured.")
        return UserStudyObservationResponse(status="recorded")

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

    @api.exception_handler(VoiceError)
    def handle_voice_error(_: Request, exc: VoiceError) -> JSONResponse:
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
