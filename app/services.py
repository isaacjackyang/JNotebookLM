from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.config import RUNTIME_ONLY_FIELDS, SETTINGS_PATH, TEXT_DIR, UPLOAD_DIR, Settings
from app.embeddings import EmbeddingService
from app.llama_client import LlamaClient
from app.retrieval import chunk_text, retrieve
from app.schemas import AppSettingsPayload
from app.storage import Storage
from app.text_extract import extract_text


class NotebookService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.embeddings = EmbeddingService(settings)
        self.llama = LlamaClient(settings)

    async def save_upload(self, notebook_id: str, upload: UploadFile) -> dict[str, Any]:
        safe_name = Path(upload.filename or "upload.bin").name
        source_dir = UPLOAD_DIR / notebook_id
        text_dir = TEXT_DIR / notebook_id
        source_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)

        source_path = source_dir / safe_name
        text_path = text_dir / f"{source_path.stem}.txt"

        content = await upload.read()
        source_path.write_bytes(content)

        source = self.storage.create_source(
            notebook_id=notebook_id,
            filename=safe_name,
            kind="pending",
            status="processing",
            original_path=str(source_path),
            text_path=str(text_path),
            metadata={},
        )

        try:
            result = extract_text(source_path, self.settings)
            text_path.write_text(result.text, encoding="utf-8")
            raw_chunks = chunk_text(result.text, self.settings.chunk_size, self.settings.chunk_overlap)
            chunk_embeddings = self.embeddings.embed_passages(raw_chunks)
            chunks = [
                {
                    "chunk_index": index,
                    "content": chunk,
                    "embedding": chunk_embeddings[index],
                    "embedding_model": self.embeddings.model_name,
                }
                for index, chunk in enumerate(raw_chunks)
            ]
            metadata = {
                **result.metadata,
                "chunk_count": len(chunks),
                "text_characters": len(result.text),
                "original_path": str(source_path),
                "text_path": str(text_path),
                "retrieval_provider": self.embeddings.provider_name,
                "embedding_model": self.embeddings.model_name,
            }
            self.storage.replace_chunks(notebook_id, source["id"], chunks)
            self.storage.update_source(
                source["id"],
                kind=result.kind,
                status="ready",
                metadata={**metadata, "kind": result.kind},
            )
        except Exception as exc:  # noqa: BLE001
            self.storage.replace_chunks(notebook_id, source["id"], [])
            self.storage.update_source(
                source["id"],
                kind="error",
                status="error",
                metadata={
                    "error": str(exc),
                    "original_path": str(source_path),
                    "text_path": str(text_path),
                    "kind": "error",
                },
            )

        source_row = self.storage.get_source(source["id"])
        if source_row is None:
            raise RuntimeError("Source disappeared after processing")
        return source_row

    def notebook_detail(self, notebook_id: str) -> dict[str, Any] | None:
        notebook = self.storage.get_notebook(notebook_id)
        if not notebook:
            return None
        notebook["sources"] = self.storage.list_sources(notebook_id)
        notebook["messages"] = self.storage.list_messages(notebook_id)
        return notebook

    def chat(self, notebook_id: str, question: str) -> dict[str, Any]:
        notebook = self.storage.get_notebook(notebook_id)
        if not notebook:
            raise KeyError("Notebook not found")

        chunks = self._ensure_notebook_embeddings(notebook_id)
        citations = retrieve(chunks, self.embeddings.embed_query(question), self.settings.retrieval_top_k)
        self.storage.add_message(notebook_id, "user", question)

        if not citations:
            answer = "目前找不到足夠接近問題的來源內容。請先上傳資料，或改用更明確的關鍵描述再試一次。"
            assistant = self.storage.add_message(notebook_id, "assistant", answer, [])
            return {"answer": assistant["content"], "citations": [], "warning": None}

        prompt_blocks = []
        api_citations = []
        for index, item in enumerate(citations, start=1):
            label = f"S{index}"
            prompt_blocks.append(
                f"[{label}] Source={item['source_name']} chunk={item['chunk_index']}\n{item['content']}"
            )
            api_citations.append(
                {
                    "source_id": item["source_id"],
                    "source_name": item["source_name"],
                    "chunk_id": item["chunk_id"],
                    "snippet": item["content"][:360],
                    "score": item["score"],
                    "chunk_index": item["chunk_index"],
                }
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are JNotebookLM, a local-first research assistant. "
                    "Answer only from the supplied sources when possible. "
                    "If the evidence is incomplete, say so clearly. "
                    "Cite the relevant snippets inline like [S1] [S2]. "
                    "Prefer Traditional Chinese when the user writes in Chinese."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nEvidence:\n\n{'\n\n'.join(prompt_blocks)}",
            },
        ]

        warning = None
        try:
            answer = self.llama.chat(messages)
        except Exception as exc:  # noqa: BLE001
            warning = f"llama.cpp 目前無法連線，已回退為向量檢索摘要。錯誤：{exc}"
            lines = [
                f"[S{index}] {citation['source_name']}：{citation['snippet']}"
                for index, citation in enumerate(api_citations, start=1)
            ]
            answer = "找到以下最相關內容，可先根據這些片段整理答案：\n\n" + "\n\n".join(lines)

        assistant = self.storage.add_message(notebook_id, "assistant", answer, api_citations)
        return {"answer": assistant["content"], "citations": api_citations, "warning": warning}

    def generate(self, notebook_id: str, mode: str) -> dict[str, Any]:
        notebook = self.storage.get_notebook(notebook_id)
        if not notebook:
            raise KeyError("Notebook not found")

        mode = mode.lower().strip()
        if mode not in {"overview", "faq", "timeline"}:
            raise ValueError("Unsupported mode")

        chunks = self._ensure_notebook_embeddings(notebook_id)
        if not chunks:
            return {
                "mode": mode,
                "content": "目前還沒有可整理的內容。",
                "citations": [],
                "warning": None,
            }

        retrieval_queries = {
            "overview": "請找出這份 notebook 的主題、重點、角色與未解問題",
            "faq": "請找出適合整理成常見問答的重點事實與說明",
            "timeline": "請找出與時間順序、事件流程或階段變化最相關的內容",
        }
        selected = retrieve(
            chunks,
            self.embeddings.embed_query(retrieval_queries[mode]),
            min(len(chunks), 10),
        )
        if not selected:
            selected = retrieve(chunks, self.embeddings.embed_query(notebook["title"]), min(len(chunks), 10))

        citations = [
            {
                "source_id": item["source_id"],
                "source_name": item["source_name"],
                "chunk_id": item["chunk_id"],
                "snippet": item["content"][:360],
                "score": item["score"],
                "chunk_index": item["chunk_index"],
            }
            for item in selected
        ]

        prompts = {
            "overview": "Create a concise notebook briefing with key themes, entities, and unresolved questions.",
            "faq": "Create a FAQ with short question-answer pairs grounded in the sources.",
            "timeline": "Extract a timeline or ordered sequence of events if present; otherwise explain that the source is not temporal.",
        }
        blocks = [
            f"[S{index}] Source={item['source_name']} chunk={item['chunk_index']}\n{item['content']}"
            for index, item in enumerate(selected, start=1)
        ]

        warning = None
        try:
            content = self.llama.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are JNotebookLM. Produce structured output grounded in the sources. "
                            "Use Traditional Chinese when the source or user context is Chinese. "
                            "Cite evidence inline like [S1]."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"{prompts[mode]}\n\nSources:\n\n{'\n\n'.join(blocks)}",
                    },
                ]
            )
        except Exception as exc:  # noqa: BLE001
            warning = f"llama.cpp 目前無法連線，已回退為靜態整理。錯誤：{exc}"
            content = "\n\n".join(
                f"[S{index}] {item['source_name']}：{item['content'][:320]}"
                for index, item in enumerate(selected, start=1)
            )

        return {
            "mode": mode,
            "content": content,
            "citations": citations,
            "warning": warning,
        }

    def health(self) -> dict[str, Any]:
        return {
            "service": "JNotebookLM",
            "embeddings": self.embeddings.health(),
            "llama": self.llama.health(),
            "features": {
                "ocr_provider": self.settings.ocr_provider,
                "ocr_languages": self.settings.ocr_languages,
                "stt_provider": self.settings.stt_provider,
                "whisper_model": self.settings.whisper_model,
                "retrieval_provider": self.settings.embedding_provider,
                "embedding_model": self.settings.embedding_model,
                "chunk_size": self.settings.chunk_size,
                "chunk_overlap": self.settings.chunk_overlap,
                "retrieval_top_k": self.settings.retrieval_top_k,
            },
        }

    def get_settings(self) -> dict[str, Any]:
        return self.settings.to_dict()

    def update_settings(self, payload: AppSettingsPayload) -> dict[str, Any]:
        previous = self.settings.to_dict()
        updated = payload.model_dump()
        self.settings.apply_overrides(updated)
        self.settings.save_overrides(SETTINGS_PATH)

        embedding_fields = {
            "embedding_provider",
            "embedding_model",
            "embedding_threads",
            "embedding_device",
            "embedding_cache_dir",
        }
        if any(previous[field] != updated[field] for field in embedding_fields):
            self.embeddings.invalidate()

        restart_required_fields = [
            field
            for field in sorted(RUNTIME_ONLY_FIELDS)
            if previous[field] != updated[field]
        ]
        note = None
        if restart_required_fields:
            note = "Host 或 port 變更已儲存，但要重新啟動服務後才會生效。"

        return {
            "settings": self.settings.to_dict(),
            "restart_required_fields": restart_required_fields,
            "note": note,
        }

    def _ensure_notebook_embeddings(self, notebook_id: str) -> list[dict[str, Any]]:
        chunks = self.storage.list_chunks(notebook_id)
        needs_embedding = [
            chunk
            for chunk in chunks
            if not chunk.get("embedding") or chunk.get("embedding_model") != self.embeddings.model_name
        ]
        if not needs_embedding:
            return chunks

        vectors = self.embeddings.embed_passages([chunk["content"] for chunk in needs_embedding])
        for chunk, vector in zip(needs_embedding, vectors, strict=True):
            self.storage.update_chunk_embedding(chunk["id"], vector, self.embeddings.model_name)
        return self.storage.list_chunks(notebook_id)
