from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from oasis_ai.app import create_app
from oasis_ai.models import Spec
from oasis_ai.service import SpecService


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/golden_prompts_m1.json"


class GoldenPromptClaudeClient:
    def __init__(self, cases: list[dict[str, Any]]) -> None:
        self.outputs_by_prompt = {_normalize(case["prompt"]): _spec_json_for_case(case) for case in cases}
        self.calls: list[tuple[str, str]] = []

    def complete(self, prompt: str, normalized_prompt: str, system_prompt: str = "") -> str:
        self.calls.append((prompt, normalized_prompt))
        return self.outputs_by_prompt[normalized_prompt]


def test_golden_prompt_fixture_is_canonical_and_telemetry_keyed() -> None:
    fixture = _load_fixture()
    cases = fixture["prompts"]
    prompt_ids = [case["prompt_id"] for case in cases]

    assert fixture["schema_version"] == "1.0"
    assert fixture["suite_id"] == "m1-golden-prompts-v1"
    assert len(cases) == 20
    assert len(prompt_ids) == len(set(prompt_ids))
    assert {case["category"] for case in cases} == {"simple", "stylized", "complex", "terrain_large", "edge"}

    for case in cases:
        assert re.fullmatch(r"gp_[a-z0-9_]+_\d{3}", case["prompt_id"])
        assert case["prompt"].strip()
        assert case["expected"]["object_type"].strip()
        assert case["expected"]["materials_any"]
        assert set(case["acceptance_metrics"]) == {
            "generation_latency_ms",
            "import_success",
            "placement_success",
            "quality_score",
        }
        assert all(value is None for value in case["acceptance_metrics"].values())


def test_golden_prompts_pass_mock_spec_harness_without_provider_calls() -> None:
    cases = _load_fixture()["prompts"]
    fake = GoldenPromptClaudeClient(cases)
    client = TestClient(create_app(SpecService(fake)))

    for case in cases:
        response = client.post("/spec", json={"prompt": case["prompt"]})

        assert response.status_code == 200, case["prompt_id"]
        spec = Spec.model_validate(response.json())
        expected = case["expected"]
        assert spec.schema_version == "1.0"
        assert spec.source_prompt == case["prompt"]
        assert spec.normalized_prompt == _normalize(case["prompt"])
        assert spec.object_type == expected["object_type"]
        assert spec.meshy_prompt
        assert any(material in spec.materials for material in expected["materials_any"])
        for axis in ("width", "height", "depth"):
            bounds = expected["dimensions_m"][axis]
            assert bounds["min"] <= getattr(spec.dimensions, axis) <= bounds["max"], (case["prompt_id"], axis)

    assert len(fake.calls) == len(cases)


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _normalize(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt).strip().lower()


def _spec_json_for_case(case: dict[str, Any]) -> str:
    expected = case["expected"]
    dimensions = {
        axis: round((bounds["min"] + bounds["max"]) / 2, 3)
        for axis, bounds in expected["dimensions_m"].items()
    }
    primary_material = expected["materials_any"][0]
    name = _name_from_prompt(case["prompt"])
    spec = {
        "schema_version": "1.0",
        "source_prompt": case["prompt"],
        "normalized_prompt": _normalize(case["prompt"]),
        "object_type": expected["object_type"],
        "name": name,
        "materials": list(expected["materials_any"]),
        "style": expected["style"],
        "dimensions": dimensions,
        "details": [case["category"], f"primary material: {primary_material}", "golden prompt acceptance fixture"],
        "meshy_prompt": f"{expected['style']} {name} made with {primary_material}",
    }
    return json.dumps(spec)


def _name_from_prompt(prompt: str) -> str:
    words = re.sub(r"[^a-zA-Z0-9 ]+", "", prompt).lower().split()
    ignored = {"a", "an", "the", "with", "and", "over", "of", "that", "but", "should", "become"}
    selected = [word for word in words if word not in ignored]
    return " ".join(selected[:5]) or "golden prompt object"
