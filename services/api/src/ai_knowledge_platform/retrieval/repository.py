"""SQLite-backed chunk storage and FTS5 evidence retrieval."""

import re
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import status

from ai_knowledge_platform.errors import ApiError, ErrorCode
from ai_knowledge_platform.retrieval.domain import (
    DocumentIndex,
    RetrievalChunk,
    RetrievalMatch,
)

SCHEMA_VERSION = 1
_QUERY_TOKEN = re.compile(r"[^\W_]+", flags=re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS indexed_documents (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    chunk_count INTEGER NOT NULL CHECK (chunk_count >= 0),
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES indexed_documents(document_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
    text TEXT NOT NULL,
    UNIQUE (document_id, page_number, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_document_page
ON chunks(document_id, page_number, chunk_index);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2',
    prefix='2 3'
);

CREATE TRIGGER IF NOT EXISTS chunks_after_insert AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_after_delete AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_after_update AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


def initialize_database(database_path: Path) -> None:
    """Create the versioned local retrieval schema if it does not exist."""
    try:
        with closing(_connect(database_path)) as connection:
            _ensure_schema(connection)
    except sqlite3.Error as exc:
        raise _database_error() from exc


def replace_document_index(
    database_path: Path,
    document_index: DocumentIndex,
    chunks: Sequence[RetrievalChunk],
) -> None:
    """Replace one document and all of its chunks in a single transaction."""
    try:
        with closing(_connect(database_path)) as connection:
            _ensure_schema(connection)
            with connection:
                connection.execute(
                    "DELETE FROM indexed_documents WHERE document_id = ?",
                    (str(document_index.document_id),),
                )
                connection.execute(
                    """
                    INSERT INTO indexed_documents(document_id, filename, chunk_count, indexed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(document_index.document_id),
                        document_index.filename,
                        document_index.chunk_count,
                        document_index.indexed_at.isoformat(),
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO chunks(
                        document_id, page_number, chunk_index, start_offset, end_offset, text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            str(chunk.document_id),
                            chunk.page_number,
                            chunk.chunk_index,
                            chunk.start_offset,
                            chunk.end_offset,
                            chunk.text,
                        )
                        for chunk in chunks
                    ],
                )
    except sqlite3.Error as exc:
        raise _database_error() from exc


def load_document_index(database_path: Path, document_id: UUID) -> DocumentIndex | None:
    try:
        with closing(_connect(database_path)) as connection:
            _ensure_schema(connection)
            row = connection.execute(
                """
                SELECT document_id, filename, chunk_count, indexed_at
                FROM indexed_documents
                WHERE document_id = ?
                """,
                (str(document_id),),
            ).fetchone()
    except sqlite3.Error as exc:
        raise _database_error() from exc

    if row is None:
        return None
    return DocumentIndex(
        document_id=UUID(row["document_id"]),
        filename=row["filename"],
        chunk_count=row["chunk_count"],
        indexed_at=_parse_datetime(row["indexed_at"]),
    )


def search_chunks(
    database_path: Path,
    query: str,
    *,
    limit: int,
    document_id: UUID | None = None,
) -> tuple[RetrievalMatch, ...]:
    """Return FTS5/BM25-ranked evidence for a plain-language query."""
    fts_query = compile_fts_query(query)
    try:
        with closing(_connect(database_path)) as connection:
            _ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT
                    chunks.document_id,
                    indexed_documents.filename,
                    chunks.page_number,
                    chunks.chunk_index,
                    chunks.text,
                    chunks.start_offset,
                    chunks.end_offset
                FROM chunks_fts
                JOIN chunks ON chunks.id = chunks_fts.rowid
                JOIN indexed_documents
                    ON indexed_documents.document_id = chunks.document_id
                WHERE chunks_fts MATCH ?
                    AND (? IS NULL OR chunks.document_id = ?)
                ORDER BY chunks_fts.rank, chunks.document_id, chunks.page_number, chunks.chunk_index
                LIMIT ?
                """,
                (
                    fts_query,
                    str(document_id) if document_id else None,
                    str(document_id) if document_id else None,
                    limit,
                ),
            ).fetchall()
    except sqlite3.Error as exc:
        raise _database_error() from exc

    return tuple(
        RetrievalMatch(
            rank=rank,
            document_id=UUID(row["document_id"]),
            filename=row["filename"],
            page_number=row["page_number"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
        )
        for rank, row in enumerate(rows, start=1)
    )


def compile_fts_query(query: str) -> str:
    """Turn user prose into a bounded OR query without exposing FTS syntax."""
    tokens = _deduplicate(_QUERY_TOKEN.findall(query.casefold()))
    meaningful = [token for token in tokens if token not in _STOP_WORDS and len(token) > 1]
    selected = (meaningful or tokens)[:20]
    if not selected:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.SEARCH_QUERY_EMPTY,
            message="Search query must contain at least one letter or number.",
        )
    return " OR ".join(f'"{token}"' for token in selected)


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    version_row = connection.execute("PRAGMA user_version").fetchone()
    version = int(version_row[0]) if version_row is not None else 0
    if version not in (0, SCHEMA_VERSION):
        raise sqlite3.DatabaseError(f"Unsupported retrieval schema version: {version}")
    if version == 0:
        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()


def _deduplicate(tokens: list[str]) -> list[str]:
    return list(dict.fromkeys(tokens))


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _database_error() -> ApiError:
    return ApiError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_ERROR,
        message="The local retrieval index could not be read or updated.",
    )
