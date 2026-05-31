from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.service import SpecService


class FakeClaudeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, str]] = []

    def complete(self, prompt: str, normalized_prompt: str) -> str:
        self.calls.append((prompt, normalized_prompt))
        return self.outputs.pop(0)


def valid_spec_json(source_prompt: str = "A Wooden   Chair") -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "source_prompt": source_prompt,
            "normalized_prompt": "a wooden chair",
            "object_type": "furniture",
            "name": "wooden chair",
            "materials": ["wood"],
            "style": "medieval",
            "dimensions": {"width": 0.5, "height": 1.0, "depth": 0.5},
            "details": ["high back"],
            "meshy_prompt": "a medieval wooden chair with a high back",
        }
    )


def test_post_spec_returns_locked_schema_and_normalized_prompt() -> None:
    fake = FakeClaudeClient([valid_spec_json()])
    client = TestClient(create_app(SpecService(fake)))

    response = client.post("/spec", json={"prompt": "A Wooden   Chair"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
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
    assert fake.calls == [("A Wooden   Chair", "a wooden chair")]


def test_empty_prompt_returns_typed_error_without_calling_claude() -> None:
    fake = FakeClaudeClient([])
    client = TestClient(create_app(SpecService(fake)))

    response = client.post("/spec", json={"prompt": " \n\t "})

    assert response.status_code == 400
    assert response.json() == {"error_code": "invalid_prompt", "message": "Prompt must not be empty."}
    assert fake.calls == []


def test_malformed_model_output_returns_typed_parse_error() -> None:
    fake = FakeClaudeClient(["not json"])
    client = TestClient(create_app(SpecService(fake)))

    response = client.post("/spec", json={"prompt": "a wooden chair"})

    assert response.status_code == 502
    assert response.json() == {
        "error_code": "model_parse_error",
        "message": "Claude response did not match the Spec schema.",
    }


def test_fenced_model_json_is_repaired_and_validated() -> None:
    fake = FakeClaudeClient([f"```json\n{valid_spec_json('a lamp')}\n```"])
    client = TestClient(create_app(SpecService(fake)))

    response = client.post("/spec", json={"prompt": "a lamp"})

    assert response.status_code == 200
    assert response.json()["name"] == "wooden chair"
    assert response.json()["source_prompt"] == "a lamp"
    assert response.json()["normalized_prompt"] == "a lamp"


def test_cache_is_keyed_by_normalized_prompt() -> None:
    fake = FakeClaudeClient([valid_spec_json()])
    client = TestClient(create_app(SpecService(fake)))

    first = client.post("/spec", json={"prompt": "A Wooden Chair"})
    second = client.post("/spec", json={"prompt": "  a   wooden chair  "})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["source_prompt"] == "  a   wooden chair  "
    assert second.json()["normalized_prompt"] == "a wooden chair"
    assert len(fake.calls) == 1


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not configured")
def test_live_claude_smoke_is_opt_in() -> None:
    pytest.skip("Live Claude smoke test is intentionally not run in CI.")
