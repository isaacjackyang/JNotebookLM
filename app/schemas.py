from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class NotebookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class GenerateRequest(BaseModel):
    mode: str = Field(default="overview")


class Citation(BaseModel):
    source_id: str
    source_name: str
    chunk_id: str
    snippet: str
    score: float
    chunk_index: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    citations: list[Citation] = Field(default_factory=list)


class SourceOut(BaseModel):
    id: str
    filename: str
    kind: str
    status: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotebookOut(BaseModel):
    id: str
    title: str
    description: str
    created_at: datetime


class NotebookDetail(NotebookOut):
    sources: list[SourceOut] = Field(default_factory=list)
    messages: list[MessageOut] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    warning: str | None = None


class GenerateResponse(BaseModel):
    mode: str
    content: str
    citations: list[Citation]
    warning: str | None = None


class DesignSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brief: str = Field(min_length=1, max_length=8000)
    language: str = Field(default="zh-Hant", min_length=2, max_length=20)


class DesignAdvisorRequest(BaseModel):
    goal: str = Field(default="", max_length=4000)


class DesignDirection(BaseModel):
    name: str
    philosophy: str
    palette: list[str] = Field(default_factory=list)
    typography: str
    rationale: str
    scene_focus: str


class DesignAdvisorResponse(BaseModel):
    summary: str
    directions: list[DesignDirection]
    warning: str | None = None


class DesignArtifactGenerateRequest(BaseModel):
    artifact_type: Literal["prototype", "slides", "motion", "infographic"]
    direction_name: str = Field(default="", max_length=120)
    requirements: str = Field(default="", max_length=8000)


class DesignTweakUpdateRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


class DesignCritiqueRequest(BaseModel):
    focus: str = Field(default="", max_length=2000)


class DesignArtifactOut(BaseModel):
    id: str
    artifact_type: str
    title: str
    file_path: str
    preview_text: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    warning: str | None = None


class DesignEventOut(BaseModel):
    id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DesignSessionOut(BaseModel):
    id: str
    name: str
    brief: str
    language: str
    workspace_path: str
    design_spec_path: str
    created_at: datetime
    updated_at: datetime


class DesignSessionDetail(DesignSessionOut):
    artifacts: list[DesignArtifactOut] = Field(default_factory=list)
    events: list[DesignEventOut] = Field(default_factory=list)


class DesignCritiqueDimension(BaseModel):
    name: str
    score: float
    note: str


class DesignCritiqueResponse(BaseModel):
    overview: str
    dimensions: list[DesignCritiqueDimension]
    keep: list[str]
    fix: list[str]
    quick_wins: list[str]
    warning: str | None = None

