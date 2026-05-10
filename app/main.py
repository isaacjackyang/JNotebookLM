from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    GenerateRequest,
    GenerateResponse,
    NotebookCreate,
    NotebookDetail,
    NotebookOut,
    SourceOut,
)
from app.services import NotebookService
from app.storage import Storage


settings.ensure_dirs()
storage = Storage()
service = NotebookService(settings, storage)
app = FastAPI(title="JNotebookLM", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return service.health()


@app.get("/api/notebooks", response_model=list[NotebookOut])
def list_notebooks() -> list[dict]:
    return storage.list_notebooks()


@app.post("/api/notebooks", response_model=NotebookOut)
def create_notebook(payload: NotebookCreate) -> dict:
    return storage.create_notebook(payload.title, payload.description)


@app.get("/api/notebooks/{notebook_id}", response_model=NotebookDetail)
def get_notebook(notebook_id: str) -> dict:
    notebook = service.notebook_detail(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@app.post("/api/notebooks/{notebook_id}/sources", response_model=list[SourceOut])
async def upload_sources(notebook_id: str, files: list[UploadFile] = File(...)) -> list[dict]:
    notebook = storage.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    results = []
    for upload in files:
        results.append(await service.save_upload(notebook_id, upload))
    return results


@app.post("/api/notebooks/{notebook_id}/chat", response_model=ChatResponse)
def chat(notebook_id: str, payload: ChatRequest) -> dict:
    try:
        return service.chat(notebook_id, payload.question)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/notebooks/{notebook_id}/generate", response_model=GenerateResponse)
def generate(notebook_id: str, payload: GenerateRequest) -> dict:
    try:
        return service.generate(notebook_id, payload.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run() -> None:
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)

