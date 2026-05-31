"""FastAPI entrypoint for the Oasis AI service."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .models import ErrorResponse, PromptRequest, Spec
from .service import AnthropicSpecClient, SpecError, SpecService


def create_app(service: SpecService | None = None) -> FastAPI:
    api = FastAPI(title="Oasis AI Service", version="0.1.0")
    api.state.spec_service = service or SpecService(AnthropicSpecClient())

    @api.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/spec", response_model=Spec, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
    def create_spec(payload: PromptRequest, request: Request) -> Spec:
        spec_service: SpecService = request.app.state.spec_service
        return spec_service.create_spec(payload.prompt)

    @api.exception_handler(SpecError)
    def handle_spec_error(_: Request, exc: SpecError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error_code=exc.error_code, message=exc.message).model_dump(),
        )

    return api


app = create_app()
