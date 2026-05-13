from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "jnotebooklm.db"
SETTINGS_PATH = DATA_DIR / "app-settings.json"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "texts"
MODEL_CACHE_DIR = DATA_DIR / "models"
DESIGN_DIR = DATA_DIR / "design"
DESIGN_WORKSPACE_DIR = DESIGN_DIR / "workspaces"
DESIGN_SESSION_DIR = DESIGN_DIR / "sessions"
STATIC_DIR = ROOT_DIR / "static"

RUNTIME_ONLY_FIELDS = {
    "host",
    "port",
}


def _split_csv(raw: str, fallback: list[str]) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or fallback


@dataclass(slots=True)
class Settings:
    host: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_PORT", "8000")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_CHUNK_SIZE", "1200")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_CHUNK_OVERLAP", "180")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_TOP_K", "6")))
    embedding_provider: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_EMBEDDING_PROVIDER", "fastembed"))
    embedding_model: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"))
    embedding_threads: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_EMBEDDING_THREADS", "4")))
    embedding_device: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_EMBEDDING_DEVICE", "auto"))
    embedding_cache_dir: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_EMBEDDING_CACHE_DIR", str(MODEL_CACHE_DIR)))
    llama_base_url: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_LLAMA_BASE_URL", "http://127.0.0.1:8080"))
    llama_model: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_LLAMA_MODEL", ""))
    llama_timeout: int = field(default_factory=lambda: int(os.getenv("JNOTEBOOKLM_LLAMA_TIMEOUT", "180")))
    llama_api_key: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_LLAMA_API_KEY", "not-needed"))
    ocr_provider: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_OCR_PROVIDER", "tesseract"))
    ocr_languages: list[str] = field(default_factory=lambda: _split_csv(os.getenv("JNOTEBOOKLM_OCR_LANGUAGES", "eng,chi_tra"), ["eng"]))
    stt_provider: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_STT_PROVIDER", "faster-whisper"))
    whisper_model: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_WHISPER_MODEL", "small"))
    whisper_device: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_WHISPER_DEVICE", "auto"))
    whisper_compute_type: str = field(default_factory=lambda: os.getenv("JNOTEBOOKLM_WHISPER_COMPUTE_TYPE", "int8"))

    def ensure_dirs(self) -> None:
        for path in (
            DATA_DIR,
            UPLOAD_DIR,
            TEXT_DIR,
            MODEL_CACHE_DIR,
            DESIGN_DIR,
            DESIGN_WORKSPACE_DIR,
            DESIGN_SESSION_DIR,
            STATIC_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def apply_overrides(self, payload: dict[str, Any]) -> None:
        for key, value in payload.items():
            if not hasattr(self, key):
                continue
            if key == "ocr_languages":
                setattr(self, key, self._normalize_languages(value))
                continue
            setattr(self, key, value)

    def load_overrides(self, path: Path = SETTINGS_PATH) -> None:
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            self.apply_overrides(payload)

    def save_overrides(self, path: Path = SETTINGS_PATH) -> None:
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_languages(value: Any) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return items or ["eng"]
        if isinstance(value, str):
            return _split_csv(value, ["eng"])
        return ["eng"]


settings = Settings()
settings.ensure_dirs()
settings.load_overrides()
