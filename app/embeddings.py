from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable

from app.config import Settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: TextEmbedding | None = None

    @property
    def provider_name(self) -> str:
        return self.settings.embedding_provider

    @property
    def model_name(self) -> str:
        return self.settings.embedding_model

    def health(self) -> dict:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "loaded": self._client is not None,
        }

    def embed_passages(self, texts: Iterable[str]) -> list[list[float]]:
        items = [text.strip() for text in texts if text and text.strip()]
        if not items:
            return []
        client = self._get_client()
        return [self._vector_to_list(vector) for vector in client.passage_embed(items)]

    def embed_query(self, text: str) -> list[float]:
        query = text.strip()
        if not query:
            return []
        client = self._get_client()
        vectors = list(client.query_embed([query]))
        return self._vector_to_list(vectors[0]) if vectors else []

    def _get_client(self) -> TextEmbedding:
        if self.provider_name != "fastembed":
            raise RuntimeError(f"Unsupported embedding provider: {self.provider_name}")
        if self._client is None:
            try:
                from fastembed import TextEmbedding
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "fastembed is not installed. Run `pip install -r requirements.txt` first."
                ) from exc
            self._client = TextEmbedding(
                model_name=self.model_name,
                cache_dir=self.settings.embedding_cache_dir,
                threads=self.settings.embedding_threads,
                cuda=self.settings.embedding_device,
                lazy_load=False,
            )
        return self._client

    @staticmethod
    def _vector_to_list(vector: object) -> list[float]:
        if hasattr(vector, "tolist"):
            values = vector.tolist()
        else:
            values = list(vector)  # type: ignore[arg-type]
        return normalize_vector([float(value) for value in values])
