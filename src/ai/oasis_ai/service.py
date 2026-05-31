"""Claude-backed text-to-structured-spec service."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from .models import Spec

MODEL_ID = "claude-sonnet-4-6"
MAX_PROMPT_CHARS = 1_000

SYSTEM_PROMPT = """You convert short user descriptions into the locked Oasis 3D Spec JSON.
Return only one JSON object. Do not include markdown or commentary.
The JSON object must contain exactly these fields:
schema_version, source_prompt, normalized_prompt, object_type, name, materials, style,
dimensions, details, meshy_prompt.
schema_version must be "1.0". dimensions are meters and must include width, height, depth.
materials and details are arrays of strings. meshy_prompt is a concise natural-language
3D generation prompt derived from the user's request."""


class SpecError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class ClaudeSpecClient(Protocol):
    def complete(self, prompt: str, normalized_prompt: str) -> str:
        """Return raw model text for a prompt."""


@dataclass(frozen=True)
class CacheEntry:
    spec: Spec
    expires_at: float


class AnthropicSpecClient:
    def __init__(self, model: str = MODEL_ID, max_tokens: int = 800) -> None:
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str, normalized_prompt: str) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise SpecError("provider_error", "Claude API key is not configured.", 502)

        try:
            from anthropic import Anthropic
            from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
        except ImportError as exc:
            raise SpecError("provider_error", "Claude client is not installed.", 502) from exc

        client = Anthropic(api_key=api_key)
        user_prompt = (
            "User prompt, preserve source_prompt verbatim and normalized_prompt exactly as given.\n"
            f"source_prompt: {prompt}\n"
            f"normalized_prompt: {normalized_prompt}"
        )

        for attempt in range(3):
            try:
                message = client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=0,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return _message_text(message)
            except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
                if attempt == 2:
                    raise SpecError("provider_error", "Claude API request failed.", 502) from exc
                time.sleep(0.2 * (2**attempt))
            except APIStatusError as exc:
                if 500 <= exc.status_code < 600 and attempt < 2:
                    time.sleep(0.2 * (2**attempt))
                    continue
                raise SpecError("provider_error", "Claude API request failed.", 502) from exc

        raise SpecError("provider_error", "Claude API request failed.", 502)


class SpecService:
    def __init__(self, client: ClaudeSpecClient, cache_ttl_seconds: int = 300) -> None:
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, CacheEntry] = {}

    def create_spec(self, prompt: str) -> Spec:
        normalized_prompt = normalize_prompt(prompt)
        now = time.time()
        cached = self._cache.get(normalized_prompt)
        if cached and cached.expires_at > now:
            return cached.spec.model_copy(
                update={
                    "source_prompt": prompt,
                    "normalized_prompt": normalized_prompt,
                }
            )

        raw_output = self.client.complete(prompt, normalized_prompt)
        spec = parse_spec(raw_output, prompt, normalized_prompt)
        self._cache[normalized_prompt] = CacheEntry(spec=spec, expires_at=now + self.cache_ttl_seconds)
        return spec


def normalize_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", prompt).strip().lower()
    if not normalized:
        raise SpecError("invalid_prompt", "Prompt must not be empty.", 400)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise SpecError("invalid_prompt", "Prompt is too long.", 400)
    return normalized


def parse_spec(raw_output: str, source_prompt: str, normalized_prompt: str) -> Spec:
    try:
        data = json.loads(_extract_json(raw_output))
        spec = Spec.model_validate(data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise SpecError("model_parse_error", "Claude response did not match the Spec schema.", 502) from exc

    return spec.model_copy(
        update={
            "schema_version": "1.0",
            "source_prompt": source_prompt,
            "normalized_prompt": normalized_prompt,
        }
    )


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return stripped
        return stripped[start : end + 1]


def _message_text(message: object) -> str:
    content = getattr(message, "content", None)
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(str(text))
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    if parts:
        return "\n".join(parts)
    return str(message)
