"""Phase-1 metric derivation from sanitized telemetry and user-study hooks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .telemetry import M1_EVENTS, safe_identifier

GENERATION_LATENCY_TARGET_MS = 30_000
QUALITY_TARGET_SCORE = 7
COMPLETION_TARGET_RATIO = 0.80
VOICE_INTENT_TARGET_RATIO = 0.90
REFINE_CYCLES_TARGET = 3


class UserStudyObservation(BaseModel):
    """Sanitized local study hook; no prompts, transcripts, audio, notes, or PII."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    flow_completed: bool | None = None
    quality_score: int | None = Field(default=None, ge=1, le=10)
    voice_intent_correct: bool | None = None
    refine_cycles: int | None = Field(default=None, ge=0)

    def sanitized(self) -> "UserStudyObservation":
        return self.model_copy(
            update={
                "session_id": safe_identifier(self.session_id),
                "prompt_id": safe_identifier(self.prompt_id),
            }
        )


class UserStudyHookSink:
    def __init__(self, jsonl_path: Path) -> None:
        self.jsonl_path = jsonl_path

    def record(self, observation: UserStudyObservation) -> None:
        safe_observation = observation.sanitized()
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(safe_observation.model_dump_json(exclude_none=True) + "\n")


@dataclass(frozen=True)
class MetricResult:
    sample_count: int
    target: float
    value: float | None
    passed: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "target": self.target,
            "value": self.value,
            "passed": self.passed,
        }


def derive_phase1_metrics(
    telemetry_records: list[dict[str, Any]],
    user_study_observations: list[UserStudyObservation] | None = None,
) -> dict[str, Any]:
    observations = user_study_observations or []
    generation_latencies = [
        int(record["elapsed_ms"])
        for record in telemetry_records
        if record.get("event") == "generation_ready" and isinstance(record.get("elapsed_ms"), int)
    ]
    object_placed_prompt_ids = {str(record.get("prompt_id", "")) for record in telemetry_records if record.get("event") == "object_placed"}
    submitted_prompt_ids = {
        str(record.get("prompt_id", ""))
        for record in telemetry_records
        if record.get("event") == "prompt_submitted" and record.get("provider", "") not in {"refine", "voice"}
    }
    refine_cycle_counts = _refine_cycles_by_session(telemetry_records)
    if observations:
        completion_values = [obs.flow_completed for obs in observations if obs.flow_completed is not None]
        quality_scores = [obs.quality_score for obs in observations if obs.quality_score is not None]
        voice_values = [obs.voice_intent_correct for obs in observations if obs.voice_intent_correct is not None]
        hook_refine_counts = [obs.refine_cycles for obs in observations if obs.refine_cycles is not None]
    else:
        completion_values = []
        quality_scores = []
        voice_values = []
        hook_refine_counts = []

    completion_ratio = _ratio_true(completion_values)
    if completion_ratio is None and submitted_prompt_ids:
        completion_ratio = len(object_placed_prompt_ids & submitted_prompt_ids) / len(submitted_prompt_ids)

    refine_counts = hook_refine_counts or list(refine_cycle_counts.values())
    average_refine_cycles = (sum(refine_counts) / len(refine_counts)) if refine_counts else None

    return {
        "generation_latency": MetricResult(
            sample_count=len(generation_latencies),
            target=GENERATION_LATENCY_TARGET_MS,
            value=max(generation_latencies) if generation_latencies else None,
            passed=(max(generation_latencies) < GENERATION_LATENCY_TARGET_MS) if generation_latencies else None,
        ).as_dict(),
        "voice_intent_accuracy": MetricResult(
            sample_count=len(voice_values),
            target=VOICE_INTENT_TARGET_RATIO,
            value=_ratio_true(voice_values),
            passed=(_ratio_true(voice_values) >= VOICE_INTENT_TARGET_RATIO) if voice_values else None,
        ).as_dict(),
        "refinement_cycles": MetricResult(
            sample_count=len(refine_counts),
            target=REFINE_CYCLES_TARGET,
            value=average_refine_cycles,
            passed=(average_refine_cycles < REFINE_CYCLES_TARGET) if average_refine_cycles is not None else None,
        ).as_dict(),
        "flow_completion": MetricResult(
            sample_count=len(completion_values) if completion_values else len(submitted_prompt_ids),
            target=COMPLETION_TARGET_RATIO,
            value=completion_ratio,
            passed=(completion_ratio >= COMPLETION_TARGET_RATIO) if completion_ratio is not None else None,
        ).as_dict(),
        "asset_quality": MetricResult(
            sample_count=len(quality_scores),
            target=QUALITY_TARGET_SCORE,
            value=(sum(quality_scores) / len(quality_scores)) if quality_scores else None,
            passed=((sum(quality_scores) / len(quality_scores)) >= QUALITY_TARGET_SCORE) if quality_scores else None,
        ).as_dict(),
        "inputs": {
            "telemetry_events": len(telemetry_records),
            "user_study_observations": len(observations),
            "schema": "0002-section-5-jsonl-plus-sanitized-study-hooks",
        },
    }


def load_telemetry_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _is_locked_event_record(record):
            records.append(record)
    return records


def load_user_study_jsonl(path: Path) -> list[UserStudyObservation]:
    if not path.exists():
        return []

    observations: list[UserStudyObservation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            observations.append(UserStudyObservation.model_validate_json(line).sanitized())
        except ValueError:
            continue
    return observations


def _is_locked_event_record(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("event") in M1_EVENTS
        and isinstance(record.get("session_id"), str)
        and isinstance(record.get("prompt_id"), str)
        and isinstance(record.get("provider"), str)
        and isinstance(record.get("elapsed_ms"), int)
        and isinstance(record.get("error_code"), str)
        and isinstance(record.get("asset_id"), str)
    )


def _ratio_true(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _refine_cycles_by_session(records: list[dict[str, Any]]) -> dict[str, int]:
    cycles: dict[str, int] = {}
    for record in records:
        if record.get("event") == "prompt_submitted" and record.get("provider") == "refine":
            session_id = str(record.get("session_id", ""))
            cycles[session_id] = cycles.get(session_id, 0) + 1
    return cycles
