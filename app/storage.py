from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import DB_PATH


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS notebooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    text_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(notebook_id) REFERENCES notebooks(id)
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    embedding_json TEXT NOT NULL DEFAULT '[]',
                    embedding_model TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(notebook_id) REFERENCES notebooks(id),
                    FOREIGN KEY(source_id) REFERENCES sources(id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(notebook_id) REFERENCES notebooks(id)
                );

                CREATE TABLE IF NOT EXISTS design_sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    brief TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'zh-Hant',
                    workspace_path TEXT NOT NULL,
                    design_spec_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS design_artifacts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    preview_text TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES design_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS design_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES design_sessions(id)
                );
                """
            )
            self._ensure_column(conn, "chunks", "embedding_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "chunks", "embedding_model", "TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, spec: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {spec}")

    def create_notebook(self, title: str, description: str) -> dict[str, Any]:
        notebook = {
            "id": str(uuid.uuid4()),
            "title": title.strip(),
            "description": description.strip(),
            "created_at": now_utc(),
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO notebooks (id, title, description, created_at) VALUES (?, ?, ?, ?)",
                (notebook["id"], notebook["title"], notebook["description"], notebook["created_at"]),
            )
        return notebook

    def list_notebooks(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, description, created_at FROM notebooks ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, description, created_at FROM notebooks WHERE id = ?",
                (notebook_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_notebook(self, notebook_id: str, title: str, description: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE notebooks
                SET title = ?, description = ?
                WHERE id = ?
                """,
                (title.strip(), description.strip(), notebook_id),
            )
            if cursor.rowcount <= 0:
                return None
            row = conn.execute(
                "SELECT id, title, description, created_at FROM notebooks WHERE id = ?",
                (notebook_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_notebook(self, notebook_id: str) -> bool:
        with self._connect() as conn:
            notebook = conn.execute(
                "SELECT id FROM notebooks WHERE id = ?",
                (notebook_id,),
            ).fetchone()
            if notebook is None:
                return False

            conn.execute("DELETE FROM chunks WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM messages WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM sources WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
        return True

    def create_source(
        self,
        notebook_id: str,
        filename: str,
        kind: str,
        status: str,
        original_path: str,
        text_path: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        source = {
            "id": str(uuid.uuid4()),
            "notebook_id": notebook_id,
            "filename": filename,
            "kind": kind,
            "status": status,
            "original_path": original_path,
            "text_path": text_path,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
            "created_at": now_utc(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sources (
                    id, notebook_id, filename, kind, status, original_path, text_path, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source["id"],
                    source["notebook_id"],
                    source["filename"],
                    source["kind"],
                    source["status"],
                    source["original_path"],
                    source["text_path"],
                    source["metadata_json"],
                    source["created_at"],
                ),
            )
        return self._row_to_source(source)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, filename, kind, status, metadata_json, created_at
                FROM sources
                WHERE id = ?
                """,
                (source_id,),
            ).fetchone()
        return self._row_to_source(dict(row)) if row else None

    def update_source(self, source_id: str, kind: str, status: str, metadata: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sources SET kind = ?, status = ?, metadata_json = ? WHERE id = ?",
                (kind, status, json.dumps(metadata, ensure_ascii=False), source_id),
            )

    def list_sources(self, notebook_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, kind, status, metadata_json, created_at
                FROM sources
                WHERE notebook_id = ?
                ORDER BY created_at DESC
                """,
                (notebook_id,),
            ).fetchall()
        return [self._row_to_source(dict(row)) for row in rows]

    def replace_chunks(self, notebook_id: str, source_id: str, chunks: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            conn.executemany(
                """
                INSERT INTO chunks (
                    id, notebook_id, source_id, chunk_index, content, token_count, embedding_json, embedding_model
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        notebook_id,
                        source_id,
                        chunk["chunk_index"],
                        chunk["content"],
                        len(chunk["content"].split()),
                        json.dumps(chunk.get("embedding", []), ensure_ascii=False),
                        chunk.get("embedding_model", ""),
                    )
                    for chunk in chunks
                ],
            )

    def list_chunks(self, notebook_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.source_id,
                    c.chunk_index,
                    c.content,
                    c.token_count,
                    c.embedding_json,
                    c.embedding_model,
                    s.filename
                FROM chunks c
                JOIN sources s ON s.id = c.source_id
                WHERE c.notebook_id = ?
                ORDER BY s.created_at, c.chunk_index
                """,
                (notebook_id,),
            ).fetchall()
        return [self._row_to_chunk(dict(row)) for row in rows]

    def update_chunk_embedding(self, chunk_id: str, embedding: list[float], embedding_model: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chunks
                SET embedding_json = ?, embedding_model = ?
                WHERE id = ?
                """,
                (json.dumps(embedding, ensure_ascii=False), embedding_model, chunk_id),
            )

    def add_message(
        self,
        notebook_id: str,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        message = {
            "id": str(uuid.uuid4()),
            "notebook_id": notebook_id,
            "role": role,
            "content": content,
            "citations_json": json.dumps(citations or [], ensure_ascii=False),
            "created_at": now_utc(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, notebook_id, role, content, citations_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    message["notebook_id"],
                    message["role"],
                    message["content"],
                    message["citations_json"],
                    message["created_at"],
                ),
            )
        return self._row_to_message(message)

    def list_messages(self, notebook_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, citations_json, created_at
                FROM messages
                WHERE notebook_id = ?
                ORDER BY created_at
                """,
                (notebook_id,),
            ).fetchall()
        return [self._row_to_message(dict(row)) for row in rows]

    def create_design_session(
        self,
        name: str,
        brief: str,
        language: str,
        workspace_path: str,
        design_spec_path: str,
    ) -> dict[str, Any]:
        created_at = now_utc()
        session = {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "brief": brief.strip(),
            "language": language.strip() or "zh-Hant",
            "workspace_path": workspace_path,
            "design_spec_path": design_spec_path,
            "created_at": created_at,
            "updated_at": created_at,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO design_sessions (
                    id, name, brief, language, workspace_path, design_spec_path, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    session["name"],
                    session["brief"],
                    session["language"],
                    session["workspace_path"],
                    session["design_spec_path"],
                    session["created_at"],
                    session["updated_at"],
                ),
            )
        return session

    def list_design_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    name,
                    brief,
                    language,
                    workspace_path,
                    design_spec_path,
                    created_at,
                    updated_at
                FROM design_sessions
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_design_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    name,
                    brief,
                    language,
                    workspace_path,
                    design_spec_path,
                    created_at,
                    updated_at
                FROM design_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def touch_design_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE design_sessions SET updated_at = ? WHERE id = ?",
                (now_utc(), session_id),
            )

    def add_design_artifact(
        self,
        session_id: str,
        artifact_type: str,
        title: str,
        file_path: str,
        preview_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "artifact_type": artifact_type,
            "title": title.strip(),
            "file_path": file_path,
            "preview_text": preview_text.strip(),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": now_utc(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO design_artifacts (
                    id, session_id, artifact_type, title, file_path, preview_text, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact["id"],
                    artifact["session_id"],
                    artifact["artifact_type"],
                    artifact["title"],
                    artifact["file_path"],
                    artifact["preview_text"],
                    artifact["metadata_json"],
                    artifact["created_at"],
                ),
            )
        self.touch_design_session(session_id)
        return self._row_to_design_artifact(artifact)

    def list_design_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    artifact_type,
                    title,
                    file_path,
                    preview_text,
                    metadata_json,
                    created_at
                FROM design_artifacts
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [self._row_to_design_artifact(dict(row)) for row in rows]

    def get_design_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    session_id,
                    artifact_type,
                    title,
                    file_path,
                    preview_text,
                    metadata_json,
                    created_at
                FROM design_artifacts
                WHERE id = ?
                """,
                (artifact_id,),
            ).fetchone()
        return self._row_to_design_artifact(dict(row)) if row else None

    def update_design_artifact(
        self,
        artifact_id: str,
        preview_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE design_artifacts
                SET preview_text = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    preview_text,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    artifact_id,
                ),
            )
            conn.execute(
                """
                UPDATE design_sessions
                SET updated_at = ?
                WHERE id = (SELECT session_id FROM design_artifacts WHERE id = ?)
                """,
                (now_utc(), artifact_id),
            )

    def add_design_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "event_type": event_type,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "created_at": now_utc(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO design_events (id, session_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["session_id"],
                    event["event_type"],
                    event["payload_json"],
                    event["created_at"],
                ),
            )
        self.touch_design_session(session_id)
        return self._row_to_design_event(event)

    def list_design_events(self, session_id: str, limit: int = 60) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, payload_json, created_at
                FROM design_events
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, max(limit, 1)),
            ).fetchall()
        return [self._row_to_design_event(dict(row)) for row in rows]

    @staticmethod
    def _row_to_source(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "filename": row["filename"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata_json"]) if row.get("metadata_json") else {},
        }

    @staticmethod
    def _row_to_chunk(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "token_count": row["token_count"],
            "embedding": json.loads(row["embedding_json"]) if row.get("embedding_json") else [],
            "embedding_model": row.get("embedding_model", ""),
            "filename": row["filename"],
        }

    @staticmethod
    def _row_to_message(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
            "citations": json.loads(row["citations_json"]) if row.get("citations_json") else [],
        }

    @staticmethod
    def _row_to_design_artifact(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row.get("session_id", ""),
            "artifact_type": row["artifact_type"],
            "title": row["title"],
            "file_path": row["file_path"],
            "preview_text": row["preview_text"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata_json"]) if row.get("metadata_json") else {},
        }

    @staticmethod
    def _row_to_design_event(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]) if row.get("payload_json") else {},
            "created_at": row["created_at"],
        }
