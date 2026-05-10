from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "jnotebooklm.db"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "texts"
MODEL_CACHE_DIR = DATA_DIR / "models"
STATIC_DIR = ROOT_DIR / "static"


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
        for path in (DATA_DIR, UPLOAD_DIR, TEXT_DIR, MODEL_CACHE_DIR, STATIC_DIR):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
