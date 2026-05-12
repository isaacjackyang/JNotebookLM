from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".log"}

_easyocr_reader = None
_whisper_model = None


@dataclass(slots=True)
class ExtractionResult:
    text: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_text(file_path: Path, settings: Settings) -> ExtractionResult:
    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return ExtractionResult(text=_read_text(file_path), kind="text")
    if suffix == ".pdf":
        return _extract_pdf(file_path)
    if suffix == ".docx":
        return _extract_docx(file_path)
    if suffix in {".html", ".htm"}:
        return _extract_html(file_path)
    if suffix == ".json":
        return _extract_json(file_path)
    if suffix == ".csv":
        return _extract_csv(file_path)
    if suffix in IMAGE_EXTENSIONS:
        return _extract_image_ocr(file_path, settings)
    if suffix in AUDIO_EXTENSIONS:
        return _extract_audio_stt(file_path, settings, original_kind="audio")
    if suffix in VIDEO_EXTENSIONS:
        return _extract_video_stt(file_path, settings)
    raise RuntimeError(f"Unsupported file type: {suffix or 'unknown'}")


def _extract_pdf(file_path: Path) -> ExtractionResult:
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return ExtractionResult(
        text="\n\n".join(pages).strip(),
        kind="pdf",
        metadata={"page_count": len(reader.pages)},
    )


def _extract_docx(file_path: Path) -> ExtractionResult:
    from docx import Document

    document = Document(str(file_path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return ExtractionResult(text="\n".join(paragraphs), kind="docx")


def _extract_html(file_path: Path) -> ExtractionResult:
    from bs4 import BeautifulSoup

    html = _read_text(file_path)
    soup = BeautifulSoup(html, "html.parser")
    return ExtractionResult(text=soup.get_text("\n", strip=True), kind="html")


def _extract_json(file_path: Path) -> ExtractionResult:
    data = json.loads(_read_text(file_path))
    return ExtractionResult(text=json.dumps(data, ensure_ascii=False, indent=2), kind="json")


def _extract_csv(file_path: Path) -> ExtractionResult:
    with file_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        rows = [" | ".join(cell.strip() for cell in row) for row in reader]
    return ExtractionResult(text="\n".join(rows), kind="csv", metadata={"row_count": len(rows)})


def _read_text(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8-sig", errors="ignore")


def _extract_image_ocr(file_path: Path, settings: Settings) -> ExtractionResult:
    provider = settings.ocr_provider.lower()
    from PIL import Image

    image = Image.open(file_path)

    if provider == "tesseract":
        import pytesseract

        text = pytesseract.image_to_string(image, lang="+".join(settings.ocr_languages))
        return ExtractionResult(
            text=text.strip(),
            kind="image-ocr",
            metadata={"ocr_provider": "tesseract", "languages": settings.ocr_languages},
        )

    if provider == "easyocr":
        global _easyocr_reader
        if _easyocr_reader is None:
            import easyocr

            _easyocr_reader = easyocr.Reader(settings.ocr_languages)
        lines = _easyocr_reader.readtext(str(file_path), detail=0, paragraph=True)
        return ExtractionResult(
            text="\n".join(lines).strip(),
            kind="image-ocr",
            metadata={"ocr_provider": "easyocr", "languages": settings.ocr_languages},
        )

    raise RuntimeError(f"Unsupported OCR provider: {settings.ocr_provider}")


def _extract_audio_stt(file_path: Path, settings: Settings, original_kind: str) -> ExtractionResult:
    segments, meta = _transcribe(file_path, settings)
    return ExtractionResult(
        text="\n".join(segments).strip(),
        kind=f"{original_kind}-stt",
        metadata=meta,
    )


def _extract_video_stt(file_path: Path, settings: Settings) -> ExtractionResult:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg is required to extract audio from video files")

    with tempfile.TemporaryDirectory(prefix="jnotebooklm-video-") as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(file_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to extract audio")
        result = _extract_audio_stt(wav_path, settings, original_kind="video")
        result.metadata["transcoded_audio"] = str(wav_path.name)
        return result


def _transcribe(file_path: Path, settings: Settings) -> tuple[list[str], dict[str, Any]]:
    provider = settings.stt_provider.lower()
    if provider != "faster-whisper":
        raise RuntimeError(f"Unsupported STT provider: {settings.stt_provider}")

    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    segments, info = _whisper_model.transcribe(str(file_path), vad_filter=True)
    transcript_lines = []
    for segment in segments:
        start = getattr(segment, "start", 0.0)
        end = getattr(segment, "end", 0.0)
        transcript_lines.append(f"[{start:07.2f}-{end:07.2f}] {segment.text.strip()}")

    return transcript_lines, {
        "stt_provider": "faster-whisper",
        "whisper_model": settings.whisper_model,
        "language": getattr(info, "language", "unknown"),
        "duration_seconds": getattr(info, "duration", None),
    }
