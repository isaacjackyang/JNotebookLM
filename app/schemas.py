from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotebookCreate(BaseModel):
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

