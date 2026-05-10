from __future__ import annotations

import re
from typing import Any


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not cleaned:
        return []

    paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue

        if len(current) + len(paragraph) + 2 <= chunk_size:
            current += "\n\n" + paragraph
            continue

        chunks.append(current)
        overlap = current[-chunk_overlap:] if chunk_overlap > 0 else ""
        current = (overlap + "\n\n" + paragraph).strip()

        while len(current) > chunk_size * 1.5:
            chunks.append(current[:chunk_size].strip())
            current = current[max(chunk_size - chunk_overlap, 1) :].strip()

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))


def retrieve(chunks: list[dict[str, Any]], query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
    if not chunks or not query_embedding:
        return []

    scored: list[dict[str, Any]] = []
    for chunk in chunks:
        embedding = chunk.get("embedding") or []
        score = cosine_similarity(query_embedding, embedding)
        if score <= 0:
            continue
        scored.append(
            {
                "chunk_id": chunk["id"],
                "source_id": chunk["source_id"],
                "source_name": chunk["filename"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
