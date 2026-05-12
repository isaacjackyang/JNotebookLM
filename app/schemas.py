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


class AppSettingsPayload(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    chunk_size: int = Field(ge=200, le=20000)
    chunk_overlap: int = Field(ge=0, le=10000)
    retrieval_top_k: int = Field(ge=1, le=50)
    embedding_provider: str = Field(min_length=1, max_length=80)
    embedding_model: str = Field(min_length=1, max_length=255)
    embedding_threads: int = Field(ge=1, le=128)
    embedding_device: str = Field(min_length=1, max_length=64)
    embedding_cache_dir: str = Field(min_length=1, max_length=500)
    llama_base_url: str = Field(min_length=1, max_length=500)
    llama_model: str = Field(default="", max_length=255)
    llama_timeout: int = Field(ge=5, le=3600)
    llama_api_key: str = Field(default="", max_length=255)
    ocr_provider: str = Field(min_length=1, max_length=80)
    ocr_languages: list[str] = Field(default_factory=list)
    stt_provider: str = Field(min_length=1, max_length=80)
    whisper_model: str = Field(min_length=1, max_length=120)
    whisper_device: str = Field(min_length=1, max_length=64)
    whisper_compute_type: str = Field(min_length=1, max_length=64)


class AppSettingsResponse(BaseModel):
    settings: dict[str, Any]
    restart_required_fields: list[str] = Field(default_factory=list)
    note: str | None = None
