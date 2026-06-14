"""Search endpoints.

GET  /api/search/              — Unified search (mode = keyword | semantic | hybrid)
"""

from __future__ import annotations

import logging
from enum import Enum

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    """Available search modes."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchResult(BaseModel):
    """A single search result."""
    note_id: str
    title: str
    path: str
    score: float = 0.0
    snippet: str = ""
    section_heading: str | None = None


class SearchResponse(BaseModel):
    """Search results payload."""
    query: str
    mode: str
    results: list[SearchResult]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_snippet(content: str, query: str, max_len: int = 200) -> str:
    """Extract a snippet around the first occurrence of the query in content.

    Args:
        content: The full text content to search within.
        query: The search query to highlight.
        max_len: Maximum snippet length in characters.

    Returns:
        A snippet string, potentially with ellipsis.
    """
    if not content or not query:
        return content[:max_len] if content else ""

    content_lower = content.lower()
    query_lower = query.lower()

    # Find the first occurrence of the query
    idx = content_lower.find(query_lower)
    if idx == -1:
        # Query not found literally; return the beginning
        return content[:max_len]

    # Center the snippet around the match
    start = max(0, idx - max_len // 4)
    end = min(len(content), start + max_len)

    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


def _get_note_snippet(note_id: str, conn, query: str) -> str:
    """Load a note's content and generate a search snippet.

    Args:
        note_id: The note's database ID.
        conn: An open SQLite connection.
        query: The search query for snippet generation.

    Returns:
        A text snippet or empty string.
    """
    from bfai.db import get_note_by_id
    from pathlib import Path

    note = get_note_by_id(conn, note_id)
    if not note or not note.get("path"):
        return ""

    note_path = Path(note["path"])
    if not note_path.exists():
        return ""

    try:
        content = note_path.read_text(encoding="utf-8")
        return _generate_snippet(content, query)
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=SearchResponse)
async def search_get(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: SearchMode = Query(default=SearchMode.KEYWORD),
    limit: int = Query(default=20, ge=1, le=100),
) -> SearchResponse:
    """Search notes using the specified mode.

    - **keyword**: Full-text search via SQLite FTS5
    - **semantic**: Vector similarity via Qdrant embeddings
    - **hybrid**: Combines keyword + semantic + backlink expansion
    """
    if mode == SearchMode.KEYWORD:
        return _search_keyword(q, limit)
    elif mode == SearchMode.SEMANTIC:
        return _search_semantic(q, limit)
    elif mode == SearchMode.HYBRID:
        return _search_hybrid(q, limit)
    # Fallback (shouldn't reach here)
    return SearchResponse(query=q, mode=mode.value, results=[], total=0)


def _search_keyword(query: str, limit: int) -> SearchResponse:
    """Keyword search via bfai.memory.search()."""
    from bfai.memory import search as memory_search

    try:
        results_raw = memory_search(query, limit=limit)
    except Exception as exc:
        logger.warning("Keyword search failed: %s", exc)
        return SearchResponse(query=query, mode="keyword", results=[], total=0)

    results = [
        SearchResult(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("path", "") or "",
            score=round(r.get("combined_score", 0.0) or 0.0, 4),
        )
        for r in results_raw
    ]

    return SearchResponse(
        query=query,
        mode="keyword",
        results=results,
        total=len(results),
    )


def _search_semantic(query: str, limit: int) -> SearchResponse:
    """Semantic search via bfai.memory.semantic_search().

    Falls back to keyword search if Qdrant is unavailable.
    """
    from bfai.memory import semantic_search

    try:
        results_raw = semantic_search(query, top_k=limit)
    except (ImportError, RuntimeError, Exception) as exc:
        logger.warning("Semantic search unavailable, falling back to keyword: %s", exc)
        return _search_keyword(query, limit)

    results = [
        SearchResult(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("metadata", {}).get("path", "") if isinstance(r.get("metadata"), dict) else "",
            score=round(r.get("score", 0.0) or 0.0, 4),
            section_heading=r.get("metadata", {}).get("section_heading") if isinstance(r.get("metadata"), dict) else None,
        )
        for r in results_raw
    ]

    return SearchResponse(
        query=query,
        mode="semantic",
        results=results,
        total=len(results),
    )


def _search_hybrid(query: str, limit: int) -> SearchResponse:
    """Hybrid search via bfai.memory.retrieve().

    Falls back to keyword search if Qdrant is unavailable.
    """
    from bfai.memory import retrieve

    try:
        results_raw = retrieve(query, top_k=limit, include_backlinks=False)
    except Exception as exc:
        logger.warning("Hybrid search failed, falling back to keyword: %s", exc)
        return _search_keyword(query, limit)

    results = [
        SearchResult(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("path", "") or "",
            score=round(r.get("combined_score", 0.0) or 0.0, 4),
        )
        for r in results_raw
        if r.get("source") == "search"  # Only include direct search results
    ]

    return SearchResponse(
        query=query,
        mode="hybrid",
        results=results,
        total=len(results),
    )