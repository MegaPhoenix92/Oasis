"""Local JSONL telemetry sink for the M1 prompt-to-object flow."""

from __future__ import annotations

import json
import os
import re
import hashlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


M1_EVENTS = {
    "prompt_submitted",
    "prompt_structured",
    "generation_submitted",
    "generation_ready",
    "asset_downloaded",
    "asset_imported",
    "object_placed",
    "flow_failed",
}

SAFE_ERROR_CODES = {
    "",
    "asset_invalid",
    "asset_not_found",
    "invalid_prompt",
    "microphone_error",
    "model_parse_error",
    "network_error",
    "provider_error",
    "spend_guard_exceeded",
    "timeout",
}

SAFE_PROVIDERS = {"", "anthropic", "meshy.ai", "refine", "unity", "voice"}
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class LocalTelemetry:
    def __init__(self, jsonl_path: Path | None = None, enabled: bool = True) -> None:
        self.jsonl_path = jsonl_path or _telemetry_path()
        self.enabled = enabled

    def emit(
        self,
        event: str,
        *,
        session_id: str,
        prompt_id: str,
        provider: str = "",
        elapsed_ms: int = 0,
        error_code: str = "",
        asset_id: str = "",
    ) -> None:
        if not self.enabled or event not in M1_EVENTS:
            return

        record: dict[str, Any] = {
            "event": event,
            "session_id": safe_identifier(session_id),
            "prompt_id": safe_identifier(prompt_id),
            "provider": safe_provider(provider),
            "elapsed_ms": max(0, int(elapsed_ms)),
            "error_code": safe_error_code(error_code),
            "asset_id": safe_identifier(asset_id),
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def new_session_id() -> str:
    return str(uuid.uuid4())


def new_prompt_id() -> str:
    return str(uuid.uuid4())


def elapsed_ms(started_at: float) -> int:
    return int((time.monotonic() - started_at) * 1000)


def safe_identifier(value: str) -> str:
    if value == "":
        return ""
    lowered = value.lower()
    if "sk-" in lowered or "api_key" in lowered or "secret" in lowered or "bearer " in lowered or "@" in value:
        return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]
    if SAFE_TOKEN_PATTERN.fullmatch(value):
        return value
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def safe_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    return normalized if normalized in SAFE_PROVIDERS else ""


def safe_error_code(error_code: str) -> str:
    normalized = error_code.strip().lower()
    return normalized if normalized in SAFE_ERROR_CODES else "provider_error"


def _telemetry_path() -> Path:
    configured = os.getenv("OASIS_TELEMETRY_JSONL")
    if configured:
        return Path(configured)
    return _repo_root() / "logs" / "oasis_m1_telemetry.jsonl"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
