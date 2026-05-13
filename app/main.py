from __future__ import annotations

import shutil
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, TEXT_DIR, UPLOAD_DIR, settings
from app.design_service import DesignStudioService
from app.schemas import (
    AppSettingsPayload,
    AppSettingsResponse,
    ChatRequest,
    ChatResponse,
    DesignAdvisorRequest,
    DesignAdvisorResponse,
    DesignArtifactGenerateRequest,
    DesignArtifactOut,
    DesignCritiqueRequest,
    DesignCritiqueResponse,
    DesignSessionCreate,
    DesignSessionDetail,
    DesignSessionOut,
    DesignTweakUpdateRequest,
    GenerateRequest,
    GenerateResponse,
    NotebookCreate,
    NotebookDetail,
    NotebookOut,
    NotebookUpdate,
    SourceOut,
)
from app.services import NotebookService
from app.storage import Storage


settings.ensure_dirs()
storage = Storage()
service = NotebookService(settings, storage)
design_service = DesignStudioService(settings, storage)
app = FastAPI(title="JNotebookLM", version="0.2.0")


@app.get("/api/health")
def health() -> dict:
    return service.health()


@app.get("/api/settings", response_model=AppSettingsResponse)
def get_settings() -> dict:
    return {
        "settings": service.get_settings(),
        "restart_required_fields": [],
        "note": None,
    }


@app.put("/api/settings", response_model=AppSettingsResponse)
def update_settings(payload: AppSettingsPayload) -> dict:
    return service.update_settings(payload)


@app.get("/api/notebooks", response_model=list[NotebookOut])
def list_notebooks() -> list[dict]:
    return storage.list_notebooks()


@app.post("/api/notebooks", response_model=NotebookOut)
def create_notebook(payload: NotebookCreate) -> dict:
    return storage.create_notebook(payload.title, payload.description)


@app.put("/api/notebooks/{notebook_id}", response_model=NotebookOut)
def update_notebook(notebook_id: str, payload: NotebookUpdate) -> dict:
    notebook = storage.update_notebook(notebook_id, payload.title, payload.description)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@app.delete("/api/notebooks/{notebook_id}")
def delete_notebook(notebook_id: str) -> dict:
    deleted = storage.delete_notebook(notebook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notebook not found")

    _remove_notebook_dir(UPLOAD_DIR, notebook_id)
    _remove_notebook_dir(TEXT_DIR, notebook_id)

    return {"deleted": True, "id": notebook_id}


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


@app.get("/api/design/sessions", response_model=list[DesignSessionOut])
def list_design_sessions() -> list[dict]:
    return design_service.list_sessions()


@app.post("/api/design/sessions", response_model=DesignSessionOut)
def create_design_session(payload: DesignSessionCreate) -> dict:
    return design_service.create_session(payload.name, payload.brief, payload.language)


@app.get("/api/design/sessions/{session_id}", response_model=DesignSessionDetail)
def get_design_session(session_id: str) -> dict:
    try:
        return design_service.session_detail(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/design/sessions/{session_id}/advisor", response_model=DesignAdvisorResponse)
def run_design_advisor(session_id: str, payload: DesignAdvisorRequest) -> dict:
    try:
        return design_service.advisor(session_id, payload.goal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/design/sessions/{session_id}/artifacts", response_model=DesignArtifactOut)
def create_design_artifact(session_id: str, payload: DesignArtifactGenerateRequest) -> dict:
    try:
        return design_service.generate_artifact(
            session_id=session_id,
            artifact_type=payload.artifact_type,
            direction_name=payload.direction_name,
            requirements=payload.requirements,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/design/sessions/{session_id}/artifacts/{artifact_id}/critique", response_model=DesignCritiqueResponse)
def critique_design_artifact(session_id: str, artifact_id: str, payload: DesignCritiqueRequest) -> dict:
    try:
        return design_service.critique_artifact(session_id, artifact_id, payload.focus)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/design/sessions/{session_id}/artifacts/{artifact_id}/tweaks", response_model=DesignArtifactOut)
def tweak_design_artifact(session_id: str, artifact_id: str, payload: DesignTweakUpdateRequest) -> dict:
    try:
        return design_service.apply_tweaks(session_id, artifact_id, payload.values)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/design/sessions/{session_id}/artifacts/{artifact_id}/content")
def get_design_artifact_content(session_id: str, artifact_id: str) -> JSONResponse:
    try:
        payload = design_service.read_artifact_content(session_id, artifact_id)
        return JSONResponse(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run() -> None:
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


def _remove_notebook_dir(base_dir: Path, notebook_id: str) -> None:
    target = (base_dir / notebook_id).resolve()
    base = base_dir.resolve()
    if target.parent != base:
        return
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
