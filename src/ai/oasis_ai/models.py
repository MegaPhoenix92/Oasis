"""Locked M1 prompt-to-spec data contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Dimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: float = Field(gt=0)
    height: float = Field(gt=0)
    depth: float = Field(gt=0)


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    source_prompt: str = Field(min_length=1)
    normalized_prompt: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    materials: list[str]
    style: str = Field(min_length=1)
    dimensions: Dimensions
    details: list[str]
    meshy_prompt: str = Field(min_length=1)


class PromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str


class RefineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prior_spec: Spec
    directive: str


class TransformVector3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class TransformScaleFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(gt=0)
    y: float = Field(gt=0)
    z: float = Field(gt=0)


class TransformQuaternion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float
    w: float


class TransformDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scale_factor: TransformScaleFactor
    rotation_delta: TransformQuaternion
    translate: TransformVector3


class TransformRefineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["transform"]
    transform_delta: TransformDelta
    rationale: str = Field(min_length=1)
    spec: None = None


class RespecRefineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["respec"]
    spec: Spec
    rationale: str = Field(min_length=1)
    transform_delta: None = None


RefineResult = Annotated[TransformRefineResult | RespecRefineResult, Field(discriminator="kind")]


class ErrorResponse(BaseModel):
    error_code: str
    message: str


class AssetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    source_prompt: str
    normalized_prompt: str
    spec: Spec
    provider: Literal["meshy.ai"]
    job_id: str
    source_url: str
    fetch_path: str
    local_path: str
    checksum_sha256: str
    format: Literal["glb"]
    file_size_bytes: int
    triangle_count: int
    texture_count: int
    created_at: str


class GenerateResponse(BaseModel):
    job_id: str
    status: Literal["pending"]


class JobResponse(BaseModel):
    status: Literal["pending", "processing", "ready", "failed"]
    manifest: AssetManifest | None = None
    error_code: str | None = None
