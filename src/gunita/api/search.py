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
    RETRIEVE = "retrieve"


class SearchResult(BaseModel):
    """A single search result."""
    note_id: str
    title: str
    path: str
    score: float = 0.0
    snippet: str = ""
    section_heading: str | None = None
    chunk_id: str = ""
    heading_path: list[str] = []
    text: str = ""


class SearchResponse(BaseModel):
    """Search results payload."""
    query: str
    mode: str
    results: list[SearchResult]
    total: int


class RetrieveDirectResult(BaseModel):
    """A direct match from retrieve mode (source == 'search')."""
    note_id: str
    title: str
    path: str
    score: float = 0.0
    match_type: str = "hybrid"
    snippet: str = ""
    text: str = ""
    heading_path: list[str] = []
    chunk_id: str = ""


class RetrieveSupportingItem(BaseModel):
    """A supporting knowledge item from retrieve mode (source == 'backlink' or 'graph')."""
    note_id: str
    title: str
    path: str
    source: str = ""
    relationship_type: str = ""
    hop_depth: int = 0


class RetrieveResponse(BaseModel):
    """Retrieve context results payload (mirrors get_agent_context)."""
    query: str
    mode: str = "retrieve"
    direct_matches: list[RetrieveDirectResult]
    supporting_knowledge: list[RetrieveSupportingItem]
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

@router.get("/")
async def search_get(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: SearchMode = Query(default=SearchMode.KEYWORD),
    limit: int = Query(default=20, ge=1, le=100),
    score_threshold: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum similarity score (0-1) for semantic/hybrid search results. "
            "Only results with a score >= this threshold are returned. "
            "Keyword search ignores this parameter."
        ),
    ),
    keyword_threshold: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum normalised keyword score (0-1) for hybrid search. "
            "Only keyword results with a normalised score >= this threshold "
            "are included in the hybrid merge. Default: no filtering."
        ),
    ),
):
    """Search notes using the specified mode.

    - **keyword**: Full-text search via SQLite FTS5
    - **semantic**: Vector similarity via Qdrant embeddings
    - **hybrid**: Combines keyword + semantic + backlink expansion

    For **semantic** and **hybrid** modes, an optional ``score_threshold``
    sets the minimum similarity score (cosine distance) for results from
    the vector store.  For **hybrid** mode, an additional
    ``keyword_threshold`` filters keyword results before merging.
    """
    if mode == SearchMode.KEYWORD:
        return _search_keyword(q, limit)
    elif mode == SearchMode.SEMANTIC:
        return _search_semantic(q, limit, score_threshold=score_threshold)
    elif mode == SearchMode.HYBRID:
        return _search_hybrid(
            q, limit,
            semantic_threshold=score_threshold,
            keyword_threshold=keyword_threshold,
        )
    elif mode == SearchMode.RETRIEVE:
        return _search_retrieve(q, limit)
    # Fallback (shouldn't reach here)
    return SearchResponse(query=q, mode=mode.value, results=[], total=0)


def _search_keyword(query: str, limit: int) -> SearchResponse:
    """Keyword search via bfai.memory.search()."""
    from bfai.memory import search as memory_search
    from pathlib import Path

    try:
        results_raw = memory_search(query, limit=limit)
    except Exception as exc:
        logger.warning("Keyword search failed: %s", exc)
        return SearchResponse(query=query, mode="keyword", results=[], total=0)

    results = []
    for r in results_raw:
        note_id = r.get("note_id", "")
        path_str = r.get("path", "") or ""
        # Generate a snippet from the note file content
        snippet = ""
        text = ""
        if path_str:
            try:
                content = Path(path_str).read_text(encoding="utf-8")
                snippet = _generate_snippet(content, query, max_len=200)
                text = content[:300]  # First ~300 chars as fallback text
                # Try to extract first heading as section heading
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# ") or stripped.startswith("## ") or stripped.startswith("### "):
                        section_heading = stripped.lstrip("#").strip()
                        break
                else:
                    section_heading = None
            except (OSError, UnicodeDecodeError):
                section_heading = None
        else:
            section_heading = None

        results.append(SearchResult(
            note_id=note_id,
            title=r.get("title", "") or "",
            path=path_str,
            score=round(r.get("combined_score", 0.0) or 0.0, 4),
            snippet=snippet,
            section_heading=section_heading,
            text=text,
        ))

    return SearchResponse(
        query=query,
        mode="keyword",
        results=results,
        total=len(results),
    )


def _search_semantic(
    query: str,
    limit: int,
    *,
    score_threshold: float | None = None,
) -> SearchResponse:
    """Semantic search via bfai.memory.semantic_search().

    Falls back to keyword search if Qdrant is unavailable.

    Args:
        query: The search query.
        limit: Maximum number of results.
        score_threshold: Minimum similarity score (cosine distance).
            ``None`` means no filtering.
    """
    from bfai.memory import semantic_search

    try:
        results_raw = semantic_search(
            query,
            top_k=limit,
            score_threshold=score_threshold,
        )
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
            chunk_id=r.get("chunk_id", ""),
            heading_path=r.get("metadata", {}).get("heading_path", []) if isinstance(r.get("metadata"), dict) else [],
            text=r.get("metadata", {}).get("text", "") if isinstance(r.get("metadata"), dict) else "",
        )
        for r in results_raw
    ]

    return SearchResponse(
        query=query,
        mode="semantic",
        results=results,
        total=len(results),
    )


def _search_hybrid(
    query: str,
    limit: int,
    *,
    semantic_threshold: float | None = None,
    keyword_threshold: float | None = None,
) -> SearchResponse:
    """Hybrid search via bfai.memory.hybrid_search().

    Falls back to keyword search if Qdrant is unavailable.

    Each search type is independently filtered by its threshold before
    merging: semantic results must have a raw similarity score >=
    ``semantic_threshold``, keyword results must have a normalised
    score >= ``keyword_threshold``.

    Args:
        query: The search query.
        limit: Maximum number of results.
        semantic_threshold: Minimum raw semantic score (cosine distance).
            ``None`` means no filtering.
        keyword_threshold: Minimum normalised keyword score [0, 1].
            ``None`` means no filtering.
    """
    from bfai.memory import hybrid_search

    try:
        results_raw = hybrid_search(
            query,
            top_k=limit,
            semantic_threshold=semantic_threshold,
            keyword_threshold=keyword_threshold,
        )
    except Exception as exc:
        logger.warning("Hybrid search failed, falling back to keyword: %s", exc)
        return _search_keyword(query, limit)

    results = [
        SearchResult(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("path", "") or "",
            score=round(r.get("combined_score", 0.0) or 0.0, 4),
            section_heading=r.get("heading_path")[-1] if isinstance(r.get("heading_path"), list) and len(r.get("heading_path", [])) > 0 else None,
            chunk_id=r.get("chunk_id", ""),
            heading_path=r.get("heading_path", []),
            snippet=r.get("snippet", ""),
            text=r.get("text", ""),
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


def _search_retrieve(query: str, limit: int) -> RetrieveResponse:
    """Retrieve context via bfai.memory.retrieve() — same logic as get_agent_context.

    Runs hybrid search, then expands results with backlinks and graph neighbors.
    Returns direct matches (source == 'search') and supporting knowledge
    (source == 'backlink' or 'graph') separately.

    Falls back to keyword-only if Qdrant is unavailable.
    """
    from bfai.memory import retrieve

    try:
        results_raw = retrieve(
            query,
            top_k=limit,
            max_hops=2,
            include_backlinks=True,
            hybrid=True,
        )
    except Exception as exc:
        logger.warning("Retrieve search failed, falling back to keyword: %s", exc)
        # Fallback: run keyword-only retrieve
        try:
            results_raw = retrieve(
                query,
                top_k=limit,
                max_hops=2,
                include_backlinks=True,
                hybrid=False,
            )
        except Exception as exc2:
            logger.warning("Keyword-only retrieve also failed: %s", exc2)
            return RetrieveResponse(
                query=query,
                direct_matches=[],
                supporting_knowledge=[],
                total=0,
            )

    direct = [
        RetrieveDirectResult(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("path", "") or "",
            score=round(r.get("combined_score", 0.0) or 0.0, 4),
            match_type=r.get("match_type", "direct"),
            snippet=r.get("snippet", ""),
            text=r.get("text", ""),
            heading_path=r.get("heading_path", []),
            chunk_id=r.get("chunk_id", ""),
        )
        for r in results_raw
        if r.get("source") == "search"
    ]

    supporting = [
        RetrieveSupportingItem(
            note_id=r.get("note_id", ""),
            title=r.get("title", "") or "",
            path=r.get("path", "") or "",
            source=r.get("source", ""),
            relationship_type=r.get("match_type", ""),
            hop_depth=r.get("hop_depth", 0),
        )
        for r in results_raw
        if r.get("source") != "search"
    ]

    return RetrieveResponse(
        query=query,
        direct_matches=direct,
        supporting_knowledge=supporting,
        total=len(direct) + len(supporting),
    )
