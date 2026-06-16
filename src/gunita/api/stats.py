"""Vault statistics and reindex endpoints.

GET  /api/stats/           — Get vault statistics
POST /api/stats/reindex    — Trigger incremental reindex
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class VaultStats(BaseModel):
    """Aggregate vault statistics."""
    notes_count: int = 0
    relationships_count: int = 0
    tags_count: int = 0
    files_on_disk: int = 0
    unindexed_count: int = 0
    qdrant_connected: bool = False
    vector_count: int = 0
    last_reindex: str | None = None


class ReindexResult(BaseModel):
    """Result of a reindex operation."""
    added: int = 0
    updated: int = 0
    deleted: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    embedded: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=VaultStats)
async def get_stats() -> VaultStats:
    """Return aggregate statistics about the vault and indexes."""
    from gunita.config import settings
    from bfai.db import (
        connect,
        ensure_schema,
        get_all_note_ids,
        get_all_tags,
    )

    vault_path = settings.vault_path
    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_ids = get_all_note_ids(conn)
        notes_count = len(note_ids)

        # Count relationships directly from the DB (avoids double-counting
        # issues with directed relationships like OBSERVED_FROM).
        row = conn.execute("SELECT COUNT(*) AS cnt FROM relationships").fetchone()
        relationships_count = row["cnt"] if row else 0

        # Tags: count unique tags across all notes
        all_tags = get_all_tags(conn)
        unique_tags: set[str] = set()
        for tag_list in all_tags.values():
            unique_tags.update(tag_list)
        tags_count = len(unique_tags)

        # Files on disk
        notes_dir = vault_path / "notes"
        files_on_disk = 0
        if notes_dir.exists():
            files_on_disk = len(list(notes_dir.glob("*.md")))
    finally:
        conn.close()

    # Qdrant check + vector count (no DB connection needed, outside try)
    qdrant_ok = False
    vector_count = 0
    try:
        import httpx
        r = httpx.get(f"{settings.qdrant_url}/collections", timeout=2.0)
        qdrant_ok = r.status_code == 200
        if qdrant_ok:
            collections = r.json().get("result", {}).get("collections", [])
            for coll in collections:
                collection_name = os.environ.get("BFAI_QDRANT_COLLECTION", "bfai")
                if coll.get("name") == collection_name:
                    info = httpx.get(
                        f"{settings.qdrant_url}/collections/{coll['name']}",
                        timeout=2.0,
                    )
                    if info.status_code == 200:
                        vector_count = info.json().get("result", {}).get("points_count", 0) or 0
    except Exception:
        pass

    return VaultStats(
        notes_count=notes_count,
        relationships_count=relationships_count,
        tags_count=tags_count,
        files_on_disk=files_on_disk,
        unindexed_count=max(0, files_on_disk - notes_count),
        qdrant_connected=qdrant_ok,
        vector_count=vector_count,
    )


@router.post("/reindex", response_model=ReindexResult)
async def trigger_reindex(
    embed: bool = Query(default=False, description="Generate vector embeddings"),
    provider: str | None = Query(default=None, description="Embedding provider"),
    force: bool = Query(default=False, description="Force full reindex"),
) -> ReindexResult:
    """Trigger an incremental reindex of the vault.

    Optionally generate chunked vector embeddings for reindexed notes.
    """
    from gunita.config import settings
    from bfai.sync import incremental_reindex

    start = time.time()
    reindexed = incremental_reindex(
        db_path=settings.database_path,
        embed=embed,
        provider_name=provider,
    )
    duration = time.time() - start

    return ReindexResult(
        added=reindexed,
        updated=0,
        deleted=0,
        errors=0,
        duration_seconds=round(duration, 3),
        embedded=embed,
    )