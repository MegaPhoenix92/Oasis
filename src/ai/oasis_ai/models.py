"""Locked M1 prompt-to-spec data contract."""

from __future__ import annotations

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


class ErrorResponse(BaseModel):
    error_code: str
    message: str
