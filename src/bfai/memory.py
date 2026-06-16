"""Memory API module for BFAI.

Provides the public-facing memory API that applications and agents
use to interact with the knowledge base. This module wraps lower-level
database, parsing, and indexing operations into convenient functions.

The functions in this module correspond to the public API described in
the project specification:

- ``memory.create()``
- ``memory.update()``
- ``memory.delete()``
- ``memory.search()``
- ``memory.semantic_search()``
- ``memory.hybrid_search()``
- ``memory.retrieve()``
- ``memory.related()``
- ``memory.backlinks()``
- ``memory.expand()``
"""

from __future__ import annotations

import logging
from pathlib import Path

from bfai.db import (
    connect,
    get_db_path,
    get_note_by_title as db_get_note_by_title,
    expand_graph as db_expand_graph,
    get_note_by_id,
    get_all_note_ids,
    get_tags_for_note,
    init_db,
    get_backlinks as db_get_backlinks,
    get_related_notes as db_get_related_notes,
    index_note_fts,
    ranked_search,
    upsert_note,
    process_wiki_links,
    store_tags,
    delete_note_by_id,
    delete_note_fts,
    store_relationship,
    index_chunk_fts,
    delete_chunk_fts,
    chunk_search,
    _ensure_chunks_schema,
)
import json
import re
from bfai.loader import load_note
from bfai.models import Note, Chunk
from bfai.parser import parse_note
from bfai.vault import get_vault
from bfai.writer import create_note as writer_create_note
from bfai.writer import load_note_by_title as writer_load_note_by_title
from bfai.writer import update_note as writer_update_note
from bfai.writer import delete_note as writer_delete_note

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Note Listing API
# ---------------------------------------------------------------------------


def list_notes(
    limit: int = 100,
    offset: int = 0,
    include_tags: bool = True,
) -> list[dict]:
    """List all indexed notes with their titles, IDs, paths, and tags.

    This is the primary discovery API for agents.  Agents call this to
    enumerate what knowledge exists in the vault before deciding where
    to write an observation.

    Args:
        limit: Maximum number of results to return (default 100).
        offset: Number of results to skip (default 0).
        include_tags: Whether to include tags in each result.  Set to
            ``False`` to skip the per-note tag query for performance
            (default ``True``).

    Returns:
        List of dicts, each with keys ``note_id``, ``title``, ``path``,
        and (if ``include_tags`` is ``True``) ``tags``, ordered by note
        ID.
    """
    conn = _get_connection()
    try:
        all_ids = get_all_note_ids(conn)
        total = len(all_ids)
        paginated = all_ids[offset:offset + limit]

        results: list[dict] = []
        for nid in paginated:
            note = get_note_by_id(conn, nid)
            if not note:
                continue
            entry: dict = {
                "note_id": nid,
                "title": note.get("title", "") or "",
                "path": note.get("path", "") or "",
            }
            if include_tags:
                entry["tags"] = get_tags_for_note(conn, nid)
            results.append(entry)

        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_connection():
    """Open a connection to the BFAI database, ensuring the schema exists.

    Returns:
        An open :class:`sqlite3.Connection` ready for use.
    """
    return init_db()


def _resolve_incoming_wiki_links(conn, note: Note) -> None:
    """After indexing a note, create EXPLICIT_LINK relationships for any
    existing notes that have wiki links pointing to this note's title.

    This handles the case where note A references ``[[B]]`` but note B
    hasn't been created yet.  When B is later indexed, this function
    finds A and creates the A → B relationship.

    Args:
        conn: An open SQLite connection.
        note: The newly indexed note whose title may be referenced by
            other notes.
    """
    from bfai.parser import extract_wiki_links

    if not note.title:
        return

    # Find all other notes and check if they wiki-link to this note
    rows = conn.execute(
        """SELECT n.id, f.body FROM notes n
           JOIN notes_fts f ON n.id = f.note_id
           WHERE n.id != ?""",
        (note.id,),
    ).fetchall()

    for row in rows:
        other_id = row["id"]
        body = row["body"] or ""
        links = extract_wiki_links(body)
        if note.title in links:
            conn.execute(
                """INSERT OR IGNORE INTO relationships
                       (source_id, target_id, relationship_type)
                   VALUES (?, ?, 'EXPLICIT_LINK')""",
                (other_id, note.id),
            )

    conn.commit()


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------


def search(query: str, limit: int = 20) -> list[dict]:
    """Search across all indexed notes using multi-factor ranking.

    Combines BM25 text relevance (40%), recency (10%), access frequency
    (10%), and importance signals (20%) into a unified ranking score.
    Results are ordered by the combined score (highest first).

    Args:
        query: The search query string. Supports FTS5 query syntax
            (e.g. ``"exact phrase"``, ``prefix*``).
        limit: Maximum number of results to return (default 20).

    Returns:
        List of dicts with keys ``note_id``, ``title``, ``path``,
        ``rank``, ``recency_score``, ``access_score``,
        ``importance_score``, ``combined_score``, ordered by
        ``combined_score`` descending.

    Raises:
        sqlite3.OperationalError: If the query contains invalid FTS5
            syntax.
    """
    conn = _get_connection()
    try:
        return ranked_search(conn, query, limit=limit)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Retrieval pipeline with context assembly (Stories 5.2, 7.2, 7.3, 8.4)
# ---------------------------------------------------------------------------


def retrieve(
    query: str,
    top_k: int = 10,
    *,
    include_backlinks: bool = True,
    max_hops: int = 2,
    hybrid: bool = True,
    provider_name: str | None = None,
) -> list[dict]:
    """Search for notes and expand results with graph neighbors for richer context.

    Uses a hybrid search pipeline (keyword + semantic) when ``hybrid`` is
    ``True`` (default), falling back to keyword-only if the vector store is
    unavailable. Results are then optionally expanded with backlinks and
    multi-hop graph neighbors to produce a rich context bundle.

    This is the primary retrieval API for agents. The returned context
    bundle includes both directly matched notes and connected supporting
    knowledge.

    Args:
        query: The search query string (FTS5 syntax supported).
        top_k: Maximum number of direct search results (default 10).
        include_backlinks: Whether to expand results with backlinks
            and graph neighbors (default True).
        max_hops: Maximum depth of graph expansion (default 2, ignored
            when ``include_backlinks`` is ``False``).
        hybrid: Whether to use hybrid (keyword + semantic) search
            instead of keyword-only (default True).
        provider_name: Embedding provider name for semantic search
            (e.g. ``"openai"``, ``"ollama"``). Only used when
            ``hybrid`` is ``True``.

    Returns:
        List of context dicts with keys:
        - ``note_id``, ``title``, ``path`` (from the matched or
          expanded note)
        - ``source``: ``"search"``, ``"backlink"``, or ``"graph"``
        - ``match_type``: for search results, ``"direct"``; for
          backlinks, the relationship type; for graph expansions,
          ``"graph_neighbor"``
        - ``matched_note_id``: for expanded results, the ID of the
          note that was originally matched by the search
        - ``hop_depth``: for graph expansions, the hop depth (1 or 2)
        - ``combined_score``: ranking score for the context item
        - ``chunk_id``: the matched chunk's ID (when matched at chunk level)
        - ``heading_path``: hierarchical heading breadcrumb (list of strings)
        - ``snippet``: keyword search snippet with highlights (when from keyword search)
        - ``text``: full chunk text content (when matched at chunk level)
    """
    conn = _get_connection()
    try:
        # Step 1: Search at chunk level for keyword matches
        keyword_chunk_results = chunk_search(conn, query, limit=top_k)
        semantic_chunk_results: list[dict] = []

        # Step 2: Run semantic search at chunk level
        if hybrid:
            try:
                semantic_chunk_results = _semantic_chunk_search(
                    query,
                    top_k=top_k,
                    provider_name=provider_name,
                )
            except Exception:
                logger.warning("Semantic search unavailable in retrieve, falling back to keyword-only")

        # Step 3: Merge keyword and semantic chunk results by chunk_id
        keyword_chunks: dict[str, dict] = {}
        for cr in keyword_chunk_results:
            heading_path_raw = cr.get("heading_path", "[]")
            try:
                heading_path = json.loads(heading_path_raw) if isinstance(heading_path_raw, str) else heading_path_raw
            except (json.JSONDecodeError, TypeError):
                heading_path = []
            keyword_chunks[cr["chunk_id"]] = {
                "note_id": cr["note_id"],
                "title": cr["note_title"],
                "path": cr.get("note_path", ""),
                "source": "search",
                "match_type": "keyword",
                "chunk_id": cr["chunk_id"],
                "snippet": cr.get("snippet", ""),
                "text": cr["text"],
                "heading_path": heading_path,
                "combined_score": 0.0,  # Will be normalized below
                "rank": cr.get("rank", 0),
            }

        semantic_chunks: dict[str, dict] = {}
        for sr in semantic_chunk_results:
            meta = sr.get("metadata", {})
            heading_path = meta.get("heading_path", [])
            chunk_id = sr.get("chunk_id", "")
            if not chunk_id:
                continue
            semantic_chunks[chunk_id] = {
                "note_id": sr["note_id"],
                "title": sr.get("title", ""),
                "path": meta.get("path", ""),
                "source": "search",
                "match_type": "semantic",
                "chunk_id": chunk_id,
                "snippet": "",
                "text": meta.get("text", ""),
                "heading_path": heading_path,
                "combined_score": sr.get("score", 0.0),
                "score": sr.get("score", 0.0),
            }

        # Merge: combine keyword and semantic results by chunk_id
        all_chunk_ids = set(keyword_chunks.keys()) | set(semantic_chunks.keys())
        merged_chunks: list[dict] = []

        # Normalize keyword ranks to [0, 1]
        if keyword_chunks:
            ranks = [kc["rank"] for kc in keyword_chunks.values()]
            min_rank = min(ranks) if ranks else 0
            max_rank = max(ranks) if ranks else 0
            for kc in keyword_chunks.values():
                if max_rank > min_rank:
                    kc["combined_score"] = (max_rank - kc["rank"]) / (max_rank - min_rank)
                else:
                    kc["combined_score"] = 1.0

        # Normalize semantic scores to [0, 1]
        if semantic_chunks:
            scores = [sc["score"] for sc in semantic_chunks.values()]
            max_score = max(scores) if scores else 1.0
            for sc in semantic_chunks.values():
                sc["combined_score"] = sc["score"] / max_score if max_score > 0 else 0.0

        for cid in all_chunk_ids:
            kc = keyword_chunks.get(cid)
            sc = semantic_chunks.get(cid)

            if kc and sc:
                # Hybrid match: weighted average
                combined = 0.3 * kc["combined_score"] + 0.7 * sc["combined_score"]
                merged_chunks.append({
                    "note_id": kc["note_id"],
                    "title": kc["title"],
                    "path": kc["path"],
                    "source": "search",
                    "match_type": "hybrid",
                    "chunk_id": cid,
                    "snippet": kc["snippet"],
                    "text": kc["text"],
                    "heading_path": kc["heading_path"] or sc["heading_path"],
                    "combined_score": round(combined, 4),
                })
            elif kc:
                merged_chunks.append({**kc, "combined_score": round(kc["combined_score"], 4), "match_type": "direct"})
            else:
                merged_chunks.append({
                    "note_id": sc["note_id"],
                    "title": sc["title"],
                    "path": sc["path"],
                    "source": "search",
                    "match_type": "direct",
                    "chunk_id": cid,
                    "snippet": sc["snippet"],
                    "text": sc["text"],
                    "heading_path": sc["heading_path"],
                    "combined_score": round(sc["combined_score"], 4),
                })

        # Sort by combined_score descending
        merged_chunks.sort(key=lambda x: x["combined_score"], reverse=True)
        search_results = merged_chunks[:top_k]

        if not search_results:
            return []

        # Build a set of note IDs already included to avoid duplicates
        seen_ids: set[str] = set()
        context: list[dict] = []

        for r in search_results:
            note_id = r["note_id"]
            seen_ids.add(note_id)

            context.append({
                "note_id": note_id,
                "title": r["title"],
                "path": r["path"],
                "source": "search",
                "match_type": r["match_type"],
                "matched_note_id": note_id,
                "combined_score": r.get("combined_score", 0.0),
                "chunk_id": r.get("chunk_id", ""),
                "heading_path": r.get("heading_path", []),
                "snippet": r.get("snippet", ""),
                "text": r.get("text", ""),
            })

        # Step 4: Expand with backlinks and graph neighbors if requested
        if include_backlinks:
            # Collect all matched note IDs for graph expansion
            matched_ids = list(set(r["note_id"] for r in search_results))

            # 4a: Expand with backlinks (incoming relationships)
            for r in search_results:
                note_id = r["note_id"]
                try:
                    backlink_results = db_get_backlinks(conn, note_id)
                except ValueError:
                    continue

                for bl in backlink_results:
                    bl_id = bl["related_note_id"]
                    if bl_id and bl_id not in seen_ids:
                        seen_ids.add(bl_id)
                        context.append({
                            "note_id": bl_id,
                            "title": bl["related_title"],
                            "path": bl["related_path"],
                            "source": "backlink",
                            "match_type": bl["relationship_type"],
                            "matched_note_id": note_id,
                            "combined_score": 0.0,
                        })

            # 4b: Expand with multi-hop graph traversal
            if max_hops > 0:
                try:
                    graph_results = db_expand_graph(
                        conn,
                        seed_ids=matched_ids,
                        max_hops=max_hops,
                        max_nodes=50,
                    )
                except ValueError:
                    graph_results = []

                for gr in graph_results:
                    gid = gr["note_id"]
                    hop = gr["hop_depth"]
                    # Skip seeds (hop 0) — they are already in the search results
                    if hop == 0:
                        continue
                    if gid not in seen_ids:
                        seen_ids.add(gid)
                        context.append({
                            "note_id": gid,
                            "title": gr["title"],
                            "path": gr["path"],
                            "source": "graph",
                            "match_type": "graph_neighbor",
                            "matched_note_id": gid,
                            "hop_depth": hop,
                            "combined_score": 0.0,
                        })

        # Sort: search results first (by combined_score), then backlinks/graph
        def _sort_key(item: dict) -> tuple:
            order = {"search": 0, "backlink": 1, "graph": 2}
            source_order = order.get(item.get("source", ""), 3)
            score = item.get("combined_score", 0.0) or 0.0
            return (source_order, -score, item.get("title", "") or "")

        context.sort(key=_sort_key)
        return context
    finally:
        conn.close()


def _semantic_chunk_search(
    query: str,
    top_k: int = 10,
    *,
    provider_name: str | None = None,
    vector_store: object | None = None,
) -> list[dict]:
    """Semantic search returning chunk-level results with full metadata.

    Args:
        query: The search query string.
        top_k: Maximum number of results (default 10).
        provider_name: Embedding provider name.
        vector_store: Optional VectorStore instance.

    Returns:
        List of dicts with keys: note_id, chunk_id, score, title, metadata.
    """
    from bfai.embeddings import get_provider
    from bfai.vectorstore import VectorStore

    provider = get_provider(name=provider_name)
    logger.info("Generating embedding for semantic chunk search query")
    query_vector = provider.generate(query)

    if vector_store is None:
        vector_store = VectorStore(dimension=provider.embedding_dimension)

    results = vector_store.search(query_vector, top_k=top_k)

    chunk_results: list[dict] = []
    for r in results:
        meta = r.metadata or {}
        chunk_results.append({
            "note_id": meta.get("note_id", r.note_id),
            "chunk_id": r.note_id,  # The point ID is the chunk_id
            "score": r.score,
            "title": meta.get("title", r.title),
            "metadata": dict(meta),
        })

    return chunk_results


# ---------------------------------------------------------------------------
# Related API (Story 3.4, 8.4)
# ---------------------------------------------------------------------------


def related(
    note_id: str,
    *,
    direction: str = "both",
    relationship_type: str | None = None,
) -> list[dict]:
    """Get notes related to a given note through graph relationships.

    Retrieves notes that are connected to the specified note via
    outgoing, incoming, or bidirectional relationships.

    Args:
        note_id: The ID of the note to find related notes for.
        direction: Relationship direction. One of ``"outgoing"``,
            ``"incoming"``, or ``"both"`` (default).
        relationship_type: Optional filter to restrict to a specific
            relationship type (e.g. ``"USES"``, ``"EXPLICIT_LINK"``).

    Returns:
        List of dicts with keys ``related_note_id``, ``related_title``,
        ``related_path``, and ``relationship_type``.

    Raises:
        ValueError: If the direction or relationship type is invalid.
    """
    conn = _get_connection()
    try:
        return db_get_related_notes(
            conn,
            note_id,
            direction=direction,
            relationship_type=relationship_type,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Expand API (Story 7.2, 8.4)
# ---------------------------------------------------------------------------


def expand(
    seed_ids: list[str],
    max_hops: int = 2,
    max_nodes: int = 50,
) -> list[dict]:
    """Traverse the graph from seed notes to discover connected knowledge.

    Performs a multi-hop BFS traversal from the given seed note IDs,
    following both outgoing and incoming relationships up to the
    specified depth.

    Args:
        seed_ids: List of note IDs to start traversal from.
        max_hops: Maximum traversal depth (default 2, 0 returns only
            the seeds).
        max_nodes: Maximum number of nodes to return (default 50).

    Returns:
        List of dicts with keys ``note_id``, ``title``, ``path``, and
        ``hop_depth``, ordered by hop depth then title. Seeds are
        returned with ``hop_depth=0``.

    Raises:
        ValueError: If ``max_hops`` is negative.
    """
    conn = _get_connection()
    try:
        return db_expand_graph(
            conn,
            seed_ids=seed_ids,
            max_hops=max_hops,
            max_nodes=max_nodes,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Semantic Search API (Story 6.3)
# ---------------------------------------------------------------------------


def semantic_search(
    query: str,
    top_k: int = 10,
    *,
    provider_name: str | None = None,
    vector_store: object | None = None,
) -> list[dict]:
    """Search for similar memories using semantic embeddings.

    Uses an embedding provider to convert the query into a vector
    representation, then searches the Qdrant vector store for the most
    similar embeddings.

    Args:
        query: The search query string.
        top_k: Maximum number of results (default 10).
        provider_name: Embedding provider name (e.g. ``"openai"``,
            ``"ollama"``, ``"sentence-transformers"``). If ``None``,
            uses the ``BFAI_EMBEDDING_PROVIDER`` environment variable
            or falls back to the default.
        vector_store: An optional :class:`bfai.vectorstore.VectorStore`
            instance. If ``None``, one is created using
            ``BFAI_QDRANT_URL`` / ``BFAI_QDRANT_COLLECTION`` env vars.

    Returns:
        List of dicts with keys ``note_id``, ``score``, ``title``,
        ``chunk_id``, and ``metadata`` (which includes ``heading_path``,
        ``text``, ``section_heading``), ordered by score descending.

    Raises:
        ImportError: If the embedding provider or Qdrant client is not
            installed.
        RuntimeError: If embedding generation or vector search fails.
    """
    from bfai.embeddings import get_provider
    from bfai.vectorstore import VectorStore

    provider = get_provider(name=provider_name)
    logger.info("Generating embedding for semantic search query")
    query_vector = provider.generate(query)

    if vector_store is None:
        vector_store = VectorStore(dimension=provider.embedding_dimension)

    # Request extra results to account for multiple chunks per note
    fetch_k = top_k * 5
    logger.info("Searching vector store (top_k=%d, fetch=%d)", top_k, fetch_k)
    results = vector_store.search(query_vector, top_k=fetch_k)

    # Return all chunk-level results (no dedup by note_id) for rich context
    chunk_results: list[dict] = []
    for r in results:
        meta = r.metadata or {}
        chunk_results.append({
            "note_id": meta.get("note_id", r.note_id),
            "chunk_id": r.note_id,  # The point ID is the chunk_id
            "score": r.score,
            "title": meta.get("title", r.title),
            "metadata": dict(meta),
        })

    chunk_results.sort(key=lambda x: x["score"], reverse=True)
    return chunk_results[:top_k]


# ---------------------------------------------------------------------------
# Hybrid Search API (Story 7.1)
# ---------------------------------------------------------------------------


def hybrid_search(
    query: str,
    top_k: int = 10,
    *,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
    provider_name: str | None = None,
) -> list[dict]:
    """Hybrid search combining keyword (FTS5) and semantic (vector) search.

    Runs keyword search and semantic search in parallel, normalises their
    scores to a common [0, 1] scale, merges and deduplicates results, and
    returns them ranked by combined score.

    If the vector store or embedding provider fails (e.g. Qdrant is not
    running), the function falls back to keyword-only results.

    Args:
        query: The search query string.
        top_k: Maximum number of results to return (default 10).
        keyword_weight: Weight for the keyword search score in the
            combined ranking (default 0.3).
        semantic_weight: Weight for the semantic search score in the
            combined ranking (default 0.7). Must satisfy
            ``keyword_weight + semantic_weight == 1.0``.
        provider_name: Embedding provider name for semantic search
            (e.g. ``"openai"``, ``"ollama"``, ``"sentence-transformers"``).
            If ``None``, uses the ``BFAI_EMBEDDING_PROVIDER`` env var
            or the default provider.

    Returns:
        List of result dicts with keys:
        - ``note_id``, ``title``, ``path``
        - ``source``: ``"keyword"``, ``"semantic"``, or ``"hybrid"``
        - ``keyword_score``: normalised keyword search score [0, 1]
        - ``semantic_score``: normalised semantic search score [0, 1]
        - ``combined_score``: weighted sum of keyword and semantic scores

    Raises:
        ValueError: If ``keyword_weight + semantic_weight != 1.0``.
    """
    if abs(keyword_weight + semantic_weight - 1.0) > 1e-6:
        raise ValueError(
            f"keyword_weight + semantic_weight must equal 1.0, "
            f"got {keyword_weight} + {semantic_weight}"
        )

    # Step 1: Run keyword search
    keyword_results = search(query, limit=top_k)

    # Step 2: Run semantic search (with graceful fallback)
    semantic_results: list[dict] = []
    try:
        semantic_results = semantic_search(
            query,
            top_k=top_k,
            provider_name=provider_name,
        )
    except (ImportError, RuntimeError) as exc:
        logger.warning("Semantic search unavailable, falling back to keyword-only: %s", exc)

    if not keyword_results and not semantic_results:
        return []

    # Step 3: Build a lookup of note_id → keyword scores
    # Normalise keyword BM25 rank to [0, 1] where higher is better
    keyword_scores: dict[str, float] = {}
    if keyword_results:
        ranks = [r.get("rank", 0) or 0 for r in keyword_results]
        min_rank = min(ranks)
        max_rank = max(ranks)
        for r in keyword_results:
            nid = r["note_id"]
            if max_rank > min_rank:
                normalised = (max_rank - (r.get("rank", 0) or 0)) / (max_rank - min_rank)
            else:
                normalised = 1.0
            keyword_scores[nid] = max(0.0, min(1.0, normalised))

    # Step 4: Build a lookup of note_id → semantic scores
    semantic_scores: dict[str, float] = {}
    if semantic_results:
        scores_list = [r.get("score", 0) or 0 for r in semantic_results]
        max_score = max(scores_list) if scores_list else 1.0
        for r in semantic_results:
            nid = r["note_id"]
            semantic_scores[nid] = (r.get("score", 0) or 0) / max_score if max_score > 0 else 0.0

    # Step 5: Merge all note IDs
    all_ids = list(keyword_scores.keys() | semantic_scores.keys())

    # Build a title/path lookup from keyword results, fall back to semantic
    title_map: dict[str, str] = {}
    path_map: dict[str, str] = {}
    for r in keyword_results:
        title_map[r["note_id"]] = r.get("title", "")
        path_map[r["note_id"]] = r.get("path", "")
    for r in semantic_results:
        if r["note_id"] not in title_map:
            title_map[r["note_id"]] = r.get("title", "")
        if r["note_id"] not in path_map:
            path_map[r["note_id"]] = r.get("path", "")

    # Step 6: Score and rank
    scored: list[dict] = []
    for nid in all_ids:
        kw_score = keyword_scores.get(nid, 0.0)
        sem_score = semantic_scores.get(nid, 0.0)
        combined = keyword_weight * kw_score + semantic_weight * sem_score

        # Determine source tag
        in_keyword = nid in keyword_scores
        in_semantic = nid in semantic_scores
        if in_keyword and in_semantic:
            source = "hybrid"
        elif in_keyword:
            source = "keyword"
        else:
            source = "semantic"

        scored.append({
            "note_id": nid,
            "title": title_map.get(nid, ""),
            "path": path_map.get(nid, ""),
            "source": source,
            "keyword_score": round(kw_score, 4),
            "semantic_score": round(sem_score, 4),
            "combined_score": round(combined, 4),
        })

    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Backlinks API (Story 5.1)
# ---------------------------------------------------------------------------


def backlinks(note_id: str, *, relationship_type: str | None = None) -> list[dict]:
    """Get all notes that link *to* the given note (backlinks).

    Backlinks are incoming relationships — notes that reference,
    point to, or mention the given note. For example, if Note A
    contains ``[[ESP32-S3]]``, then Note A is a backlink of ESP32-S3.

    Args:
        note_id: The ID of the note whose backlinks to retrieve.
        relationship_type: Optional filter to restrict to a specific
            relationship type (e.g. ``"EXPLICIT_LINK"``).

    Returns:
        List of dicts with keys ``source_id``, ``target_id``,
        ``relationship_type``, ``related_note_id`` (the backlinking
        note's ID), ``related_title``, ``related_path``.

    Raises:
        ValueError: If the relationship type is not recognised.
    """
    conn = _get_connection()
    try:
        return db_get_backlinks(conn, note_id, relationship_type=relationship_type)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Indexing API
# ---------------------------------------------------------------------------


def index_note(note: Note, process_tags: bool = True) -> str:
    """Index a single note into the database and full-text search index.

    This performs the full indexing pipeline:
    1. Upsert the note into the ``notes`` table
    2. Store the note in the FTS5 full-text index
    3. Chunk the note and index chunks into ``chunks_fts``
    4. Process wiki links into ``EXPLICIT_LINK`` relationships
    5. Resolve any incoming wiki links from other notes
    6. Store tags (if ``process_tags`` is True)

    Args:
        note: The Note object to index. Must have ``id``, ``title``,
            ``path``, and at minimum ``content`` or ``body``.
        process_tags: Whether to store tags extracted from the note
            (default True).

    Returns:
        The note's ID.

    Raises:
        sqlite3.IntegrityError: If the note fails foreign key
            constraints.
    """
    conn = _get_connection()
    try:
        note_id = upsert_note(conn, note)

        # Index into FTS5 — use the stored note_id (which may differ
        # from note.id when the path already existed in the database).
        index_note_fts(conn, note_id, note.title, note.body or note.content)

        # Index chunks into chunks_fts
        _ensure_chunks_schema(conn)
        note.id = note_id
        chunks = chunk_note(note)
        delete_chunk_fts(conn, note_id)
        for chunk in chunks:
            index_chunk_fts(conn, chunk)

        # Process outgoing wiki links
        if note.wiki_links:
            process_wiki_links(conn, note)

        # Resolve incoming wiki links (other notes that link to this one)
        _resolve_incoming_wiki_links(conn, note)

        # Store tags
        if process_tags and note.tags:
            store_tags(conn, note_id, note.tags)

        logger.info("Indexed note: %s (%s)", note.title, note_id)
        return note_id
    finally:
        conn.close()


def index_note_from_path(path: Path | str, process_tags: bool = True) -> str | None:
    """Load a note from the filesystem and index it.

    Convenience wrapper that loads a markdown file, parses it, and
    indexes it into the database.

    Args:
        path: Path to the markdown file to index.
        process_tags: Whether to store extracted tags (default True).

    Returns:
        The note's ID, or ``None`` if the file could not be loaded or
        parsed.
    """
    try:
        note = load_note(Path(path))
        # Parse the note to extract tags, wiki links, entities, etc.
        parsed = parse_note(note.content)
        note.title = parsed.title
        note.body = parsed.body
        note.metadata = parsed.metadata
        note.tags = parsed.tags
        note.wiki_links = parsed.wiki_links
        note.entities = parsed.entities

        return index_note(note, process_tags=process_tags)
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.error("Failed to index note from path %s: %s", path, exc)
        return None


def _index_note_internal(note: Note, process_tags: bool = True) -> str:
    """Index a note using an existing connection (no open/close).

    Internal helper used by the create/update pipelines to avoid
    opening and closing a connection when it is already managed by
    the caller.

    Args:
        note: The Note to index.
        process_tags: Whether to store tags.

    Returns:
        The note's database ID.
    """
    conn = _get_connection()
    try:
        note_id = upsert_note(conn, note)
        index_note_fts(conn, note_id, note.title, note.body or note.content)

        # Index chunks into chunks_fts
        _ensure_chunks_schema(conn)
        note.id = note_id
        chunks = chunk_note(note)
        delete_chunk_fts(conn, note_id)
        for chunk in chunks:
            index_chunk_fts(conn, chunk)

        if note.wiki_links:
            process_wiki_links(conn, note)
        _resolve_incoming_wiki_links(conn, note)
        if process_tags and note.tags:
            store_tags(conn, note_id, note.tags)
        return note_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Create API (Story 8.1)
# ---------------------------------------------------------------------------


def create(
    title: str,
    content: str,
    *,
    tags: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    embed: bool = False,
    provider_name: str | None = None,
) -> dict:
    """Create a new note and index it into the system.

    Creates a markdown file in the vault, parses it, extracts tags and
    wiki links, indexes into SQLite and FTS5, and optionally generates
    embeddings for semantic search.

    Args:
        title: The note title. Used to generate the filename via
            slugification.
        content: The markdown body content.
        tags: Optional list of tags to associate with the note.
        metadata: Optional key-value metadata dict (stored as
            frontmatter).
        embed: Whether to generate and store an embedding for the
            note (default False). Requires an embedding provider.
        provider_name: Embedding provider name (e.g. ``"openai"``,
            ``"ollama"``). Only used when ``embed=True``.

    Returns:
        Dict with keys ``note`` (the created Note object), ``id``
        (the note's database ID), and ``embedded`` (bool indicating
        whether embedding was stored).

    Raises:
        FileExistsError: If a note with the same slugified title
            already exists and ``exist_ok=False``.
    """
    # Step 1: Create the markdown file
    note = writer_create_note(
        title,
        content,
        metadata=metadata,
    )

    # Step 2: Parse to extract tags and wiki links
    parsed = parse_note(note.content)
    note.title = parsed.title or title
    note.body = parsed.body
    note.metadata = parsed.metadata
    note.tags = parsed.tags or tags or []
    note.wiki_links = parsed.wiki_links
    note.entities = parsed.entities

    # Step 3: Index into database and FTS
    note_id = index_note(note, process_tags=True)

    # Step 4: Optionally generate embedding
    embedded = False
    if embed:
        try:
            _embed_note(note, provider_name=provider_name)
            embedded = True
        except Exception as exc:
            logger.warning("Failed to embed note '%s': %s", title, exc)

    logger.info("Created note: %s (id=%s, embedded=%s)", title, note_id, embedded)
    return {
        "note": note,
        "id": note_id,
        "embedded": embedded,
    }


# ---------------------------------------------------------------------------
# Observe API — Append an observation to a note
# ---------------------------------------------------------------------------


def observe(
    title: str,
    observation: str,
    *,
    tags: list[str] | None = None,
    source: str | None = None,
    source_note_id: str | None = None,
    auto_create: bool = True,
    section_heading: str = "## Observations",
    re_embed: bool = False,
    provider_name: str | None = None,
) -> dict:
    """Append an observation to a note and re-index it.

    This is the primary API for agents to record new knowledge into an
    existing note.  The observation is appended under a configurable
    section heading (default ``"## Observations"``).  The note is then
    re-parsed, re-indexed, and optionally re-embedded.

    Args:
        title: Note title to append to (slugified to locate the file).
        observation: Markdown content to append.
        tags: Optional tags to add to the note.
        source: Human-readable source label (e.g. ``"web_search"``,
            ``"conversation"``).  If provided, appended as italic text
            alongside the observation.
        source_note_id: Optional ID of a source note to link via an
            ``OBSERVED_FROM`` relationship.
        auto_create: If ``True`` (default), create the note if it does
            not already exist.
        section_heading: Heading under which to group observations.
            Defaults to ``"## Observations"``.
        re_embed: Whether to regenerate vector embeddings after append
            (default ``False``).
        provider_name: Embedding provider name (for ``re_embed``).

    Returns:
        Dict with keys:
        - ``note``: The updated :class:`~bfai.models.Note` object.
        - ``id``: The note's database ID.
        - ``appended``: ``True`` if content was appended.
        - ``created``: ``True`` if the note was auto-created.
        - ``version``: The new version number (from version history).
        - ``embedded``: Whether embedding was stored/updated.

    Raises:
        FileNotFoundError: If the note does not exist and
            ``auto_create`` is ``False``.
        ValueError: If ``title`` is empty or ``observation`` is empty.
    """
    if not title or not title.strip():
        raise ValueError("Note title must not be empty")
    if not observation or not observation.strip():
        raise ValueError("Observation content must not be empty")

    note: Note | None = None
    created = False

    # Step 1: Try to load existing note by title
    try:
        note = writer_load_note_by_title(title)
    except FileNotFoundError:
        if not auto_create:
            raise FileNotFoundError(
                f"No note found with title '{title}' and auto_create=False"
            )
        # Auto-create the note with the observation as initial content
        obs_content = f"# {title}\n\n{section_heading}\n\n{observation}\n"
        note = writer_create_note(title, obs_content, exist_ok=True)
        created = True

    # Step 2: Append the observation content
    source_fragment = f"*{source}* — " if source else ""
    content_to_append = f"{source_fragment}{observation}"

    from bfai.writer import append_note as writer_append_note
    note = writer_append_note(note, content_to_append, section_heading=section_heading)
    appended = True

    # Step 3: Re-parse the note to extract wiki links, tags, entities
    parsed = parse_note(note.content)
    note.title = parsed.title or title
    note.body = parsed.body
    note.metadata = parsed.metadata
    # Merge new tags with existing parsed tags
    if tags:
        note.tags = sorted(set(parsed.tags + tags))
    else:
        note.tags = parsed.tags
    note.wiki_links = parsed.wiki_links
    note.entities = parsed.entities

    # Step 4: Re-index into SQLite + FTS
    conn = _get_connection()
    try:
        note_id = upsert_note(conn, note)
        index_note_fts(conn, note_id, note.title, note.body or note.content)

        # Index chunks into chunks_fts
        _ensure_chunks_schema(conn)
        note.id = note_id
        chunks = chunk_note(note)
        delete_chunk_fts(conn, note_id)
        for chunk in chunks:
            index_chunk_fts(conn, chunk)

        if note.wiki_links:
            process_wiki_links(conn, note)
        _resolve_incoming_wiki_links(conn, note)
        if note.tags:
            store_tags(conn, note_id, note.tags)

        # Step 5: Create OBSERVED_FROM relationship if source_note_id given
        if source_note_id:
            try:
                store_relationship(
                    conn, note_id, source_note_id, "OBSERVED_FROM"
                )
            except ValueError:
                logger.warning(
                    "Could not create OBSERVED_FROM relationship: "
                    "note_id=%s source_note_id=%s",
                    note_id, source_note_id,
                )
    finally:
        conn.close()

    # Step 6: Optionally re-embed
    embedded = False
    if re_embed:
        try:
            _embed_note(note, provider_name=provider_name)
            embedded = True
        except Exception as exc:
            logger.warning("Failed to re-embed note '%s': %s", title, exc)

    logger.info(
        "Observed: %s (id=%s, appended=%s, created=%s, embedded=%s)",
        title, note_id, appended, created, embedded,
    )
    return {
        "note": note,
        "id": note_id,
        "appended": appended,
        "created": created,
        "version": 0,  # version tracking is handled by the REST API layer
        "embedded": embedded,
    }


# ---------------------------------------------------------------------------
# Update API (Story 8.2)
# ---------------------------------------------------------------------------


def update(
    title: str,
    content: str | None = None,
    *,
    metadata: dict[str, str] | None = None,
    tags: list[str] | None = None,
    re_embed: bool = False,
    provider_name: str | None = None,
) -> dict | None:
    """Update an existing note and re-index it.

    Updates the markdown file content and/or metadata, re-parses,
    re-indexes into SQLite and FTS5, and optionally regenerates the
    embedding.

    Args:
        title: The note title (used to locate the existing note via
            slugification).
        content: Optional new markdown body content. If ``None``, the
            existing content is preserved.
        metadata: Optional new metadata dict. If provided, replaces
            existing metadata. If ``None``, existing metadata is
            preserved.
        tags: Optional new list of tags. If provided, replaces existing
            tags. If ``None``, existing tags are preserved.
        re_embed: Whether to regenerate the embedding (default False).
        provider_name: Embedding provider name for re-embedding.

    Returns:
        Dict with keys ``note``, ``id``, ``embedded`` if the note was
        found and updated, or ``None`` if no note with that title
        exists.
    """
    # Step 1: Load the existing note by title
    try:
        existing = writer_load_note_by_title(title)
    except FileNotFoundError:
        logger.warning("No note found with title: %s", title)
        return None

    # Step 2: Update the metadata on the existing Note
    safe_metadata = metadata if metadata is not None else existing.metadata

    # Step 3: Call the writer's update_note with the Note object
    try:
        note = writer_update_note(existing, content=content)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Failed to update note '%s': %s", title, exc)
        return None

    # Step 4: Re-parse to extract updated tags, wiki links, etc.
    parsed = parse_note(note.content)
    note.title = parsed.title or title
    note.body = parsed.body
    note.metadata = safe_metadata
    note.tags = parsed.tags or tags or []
    note.wiki_links = parsed.wiki_links
    note.entities = parsed.entities

    # Step 5: Re-index
    note_id = index_note(note, process_tags=True)

    # Step 6: Optionally re-embed
    embedded = False
    if re_embed:
        try:
            _embed_note(note, provider_name=provider_name)
            embedded = True
        except Exception as exc:
            logger.warning("Failed to re-embed note '%s': %s", title, exc)

    logger.info("Updated note: %s (id=%s, embedded=%s)", title, note_id, embedded)
    return {
        "note": note,
        "id": note_id,
        "embedded": embedded,
    }


# ---------------------------------------------------------------------------
# Delete API (Story 8.3)
# ---------------------------------------------------------------------------


def delete(
    title: str,
    *,
    remove_embedding: bool = False,
    provider_name: str | None = None,
) -> dict:
    """Delete a note from the system completely.

    Removes the note from all storage layers:
    1. Deletes the markdown file from disk
    2. Removes the note from the SQLite database (cascading to
       relationships and tags)
    3. Removes the note from the FTS5 full-text index
    4. Optionally removes the embedding from the Qdrant vector store

    Args:
        title: The note title (used to locate the note via
            slugification).
        remove_embedding: Whether to also remove the note's vector
            embedding from Qdrant (default False).
        provider_name: Embedding provider name for determining the
            vector dimension. Only used when ``remove_embedding`` is
            ``True`` and the note's embedding dimension differs from
            the default.

    Returns:
        Dict with keys:
        - ``success``: ``True`` if the note was found and deleted
        - ``file_deleted``: whether the file was removed from disk
        - ``db_deleted``: whether the note was removed from the
          database
        - ``embedding_removed``: whether the embedding was removed
          from the vector store
        - ``error``: error message if something went wrong (only
          present on failure)

    Raises:
        ValueError: If the title is empty.
    """
    if not title or not title.strip():
        raise ValueError("Note title must not be empty")

    from bfai.db import get_note_by_path
    from bfai.writer import _resolve_note_path

    result: dict = {
        "success": False,
        "file_deleted": False,
        "db_deleted": False,
        "embedding_removed": False,
    }

    conn = _get_connection()
    try:
        # Step 1: Look up the note — try by title first, fall back to slugified path.
        # Title-based lookup is the primary approach (the API accepts a title).
        # Path-based fallback handles cases where the stored title is empty
        # (e.g. notes created via create() where the content lacks a # heading).
        note_record = db_get_note_by_title(conn, title)
        if not note_record:
            file_path_fallback = _resolve_note_path(title)
            note_record = get_note_by_path(conn, str(file_path_fallback))

        note_id = note_record["id"] if note_record else None

        # Step 2: Delete from FTS and database first
        if note_id:
            delete_note_fts(conn, note_id)
            delete_chunk_fts(conn, note_id)
            db_deleted = delete_note_by_id(conn, note_id)
            result["db_deleted"] = db_deleted

        # Step 3: Delete the file from disk
        file_path: Path | None = None
        if note_record and note_record.get("path"):
            file_path = Path(note_record["path"])
        else:
            file_path = _resolve_note_path(title)

        try:
            if file_path.exists():
                file_path.unlink()
                result["file_deleted"] = True
        except (FileNotFoundError, OSError) as exc:
            logger.warning("Could not delete file for note '%s': %s", title, exc)

        # Step 4: Optionally remove the embedding from vector store
        if remove_embedding and note_id:
            try:
                _remove_embedding(note_id, provider_name=provider_name)
                result["embedding_removed"] = True
            except Exception as exc:
                logger.warning("Could not remove embedding for note '%s': %s", title, exc)

        result["success"] = result["file_deleted"] or result["db_deleted"]
        if not result["success"]:
            result["error"] = f"Note '{title}' not found"

        logger.info(
            "Deleted note: %s (file=%s, db=%s, embedding=%s)",
            title,
            result["file_deleted"],
            result["db_deleted"],
            result["embedding_removed"],
        )
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chunking for semantic embeddings
# ---------------------------------------------------------------------------

# Regex to match markdown heading lines (e.g. "# Title", "## Section")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def chunk_note(note: Note) -> list[Chunk]:
    """Split a note into paragraph-level chunks grouped by sections.

    Chunking strategy:
    1. Split the note into sections by markdown headings.
    2. Within each section, split by paragraphs (double newlines).
    3. Each paragraph becomes a separate chunk with the full heading
       breadcrumb path prepended for context.

    The heading hierarchy is tracked using a stack: when a heading is
    encountered, the stack is truncated to (level - 1) and the new
    heading text is appended. The chunk text is then prefixed with
    ``note.title > ... > parent > heading`` separated by `` > ``.

    Args:
        note: The note to chunk.

    Returns:
        A list of :class:`Chunk` objects.  If the note has no headings,
        the entire body is treated as a single section.
    """
    text = note.body or note.content
    if not text or not text.strip():
        return []

    chunks: list[Chunk] = []
    chunk_index = 0

    # Track heading hierarchy: stack of heading texts (without # marks)
    heading_stack: list[str] = []

    def _make_breadcrumbs() -> list[str]:
        """Build the full breadcrumb path including the note title."""
        return [note.title] + list(heading_stack) if note.title else list(heading_stack)

    def _chunk_paragraphs(section_text: str, breadcrumbs: list[str], heading_line: str) -> None:
        """Split section_text into paragraphs and append chunks."""
        nonlocal chunk_index
        paragraphs = _split_paragraphs(section_text)
        for para in paragraphs:
            chunk_text = f"{' > '.join(breadcrumbs)}\n\n{para.strip()}"
            if chunk_text.strip():
                chunks.append(Chunk(
                    chunk_id=f"{note.id}_chunk_{chunk_index}",
                    text=chunk_text,
                    note_id=note.id,
                    section_heading=heading_line,
                    heading_path=list(breadcrumbs),
                    chunk_index=chunk_index,
                ))
                chunk_index += 1

    def _chunk_empty_section(breadcrumbs: list[str], heading_line: str) -> None:
        """Handle sections with only a heading and no body text."""
        nonlocal chunk_index
        chunk_text = ' > '.join(breadcrumbs)
        if chunk_text.strip():
            chunks.append(Chunk(
                chunk_id=f"{note.id}_chunk_{chunk_index}",
                text=chunk_text,
                note_id=note.id,
                section_heading=heading_line,
                heading_path=list(breadcrumbs),
                chunk_index=chunk_index,
            ))
            chunk_index += 1

    # Find all heading positions
    headings = list(_HEADING_RE.finditer(text))

    if not headings:
        # No headings — treat entire text as one section
        paragraphs = _split_paragraphs(text)
        breadcrumbs = [note.title] if note.title else []
        for para in paragraphs:
            chunk_text = ' > '.join(breadcrumbs + [para.strip()]) if breadcrumbs else para.strip()
            if chunk_text.strip():
                chunks.append(Chunk(
                    chunk_id=f"{note.id}_chunk_{chunk_index}",
                    text=chunk_text,
                    note_id=note.id,
                    section_heading="",
                    heading_path=list(breadcrumbs),
                    chunk_index=chunk_index,
                ))
                chunk_index += 1
        return chunks

    # Process preamble (text before first heading)
    preamble = text[: headings[0].start()].strip()
    if preamble:
        breadcrumbs = _make_breadcrumbs()
        _chunk_paragraphs(preamble, breadcrumbs, "")

    # Process each section, tracking heading hierarchy
    for i, heading_match in enumerate(headings):
        heading_level = len(heading_match.group(1))  # Number of # characters
        heading_text = heading_match.group(2).strip()  # Text without # marks
        heading_line = heading_match.group(0).strip()  # Full heading line e.g. "### Title"

        # Truncate stack to (level - 1) and append new heading
        while len(heading_stack) >= heading_level:
            heading_stack.pop()
        heading_stack.append(heading_text)

        breadcrumbs = _make_breadcrumbs()

        start = heading_match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section_text = text[start:end].strip()

        if not section_text:
            _chunk_empty_section(breadcrumbs, heading_line)
        else:
            _chunk_paragraphs(section_text, breadcrumbs, heading_line)

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by double newlines.

    Args:
        text: The text to split.

    Returns:
        List of paragraph strings (non-empty).
    """
    paragraphs = re.split(r"\n\s*\n", text)
    return [p for p in paragraphs if p.strip()]


# ---------------------------------------------------------------------------
# Internal: embed a note into Qdrant (chunked)
# ---------------------------------------------------------------------------


def _embed_note(
    note: Note,
    provider_name: str | None = None,
) -> None:
    """Chunk a note, generate embeddings for each chunk, and store them.

    Each chunk is stored with a deterministic ID (``{note_id}_chunk_{index}``)
    and a payload containing ``note_id``, ``title``, ``chunk_index``,
    ``section_heading``, ``heading_path``, and ``text``.

    Args:
        note: The Note to embed.
        provider_name: Optional embedding provider name.

    Raises:
        ImportError: If the embedding provider or Qdrant client is not
            installed.
        RuntimeError: If embedding generation or storage fails.
    """
    from bfai.embeddings import get_provider
    from bfai.vectorstore import VectorStore

    provider = get_provider(name=provider_name)
    store = VectorStore(dimension=provider.embedding_dimension)

    # Remove old chunks before embedding new ones
    _remove_embedding(note.id)

    # Chunk the note
    chunks = chunk_note(note)
    if not chunks:
        logger.warning("No chunks generated for note '%s' (id=%s)", note.title, note.id)
        return

    # Generate embeddings for all chunks
    texts = [c.text for c in chunks]
    vectors = provider.generate_batch(texts)

    # Build batch upsert data
    chunk_ids = [c.chunk_id for c in chunks]
    titles = [note.title] * len(chunks)
    metadata_list = [
        {
            "note_id": note.id,
            "title": note.title,
            "chunk_index": c.chunk_index,
            "section_heading": c.section_heading,
            "heading_path": c.heading_path,
            "text": c.text,
            "tags": note.tags,
        }
        for c in chunks
    ]

    store.upsert_batch(
        note_ids=chunk_ids,
        vectors=vectors,
        titles=titles,
        metadata_list=metadata_list,
    )

    logger.debug(
        "Embedded note '%s' as %d chunks (dim=%d)",
        note.title,
        len(chunks),
        provider.embedding_dimension,
    )


def _remove_embedding(note_id: str, provider_name: str | None = None) -> None:
    """Remove all chunk embeddings for a note from the vector store.

    Uses a payload filter to delete all vectors where ``note_id`` matches,
    which handles both legacy single-vector and new chunked embeddings.

    Args:
        note_id: The ID of the note whose embeddings to remove.
        provider_name: Optional embedding provider name (unused, kept for
            API compatibility).

    Raises:
        ImportError: If the Qdrant client is not installed.
        RuntimeError: If the deletion fails.
    """
    from bfai.vectorstore import VectorStore

    store = VectorStore()
    try:
        store.delete_by_payload("note_id", note_id)
        logger.debug("Removed chunk embeddings for note: %s", note_id)
    except Exception:
        # Fallback: try deleting by point ID (legacy single-vector)
        try:
            store.delete([note_id])
            logger.debug("Removed legacy embedding for note: %s", note_id)
        except Exception as exc:
            logger.warning("Could not remove embedding for note %s: %s", note_id, exc)


# ---------------------------------------------------------------------------
# Re-indexing
# ---------------------------------------------------------------------------


def reindex_all() -> int:
    """Re-index all notes in the vault.

    Discovers all markdown files in the vault, loads and parses each
    one, then rebuilds the database and full-text index from scratch.

    Returns:
        The number of notes successfully indexed.

    Raises:
        Exception: If the vault directory cannot be accessed.
    """
    from bfai.loader import load_all_notes
    from bfai.db import rebuild_fts_index

    notes = load_all_notes()
    conn = _get_connection()
    indexed = 0

    try:
        for note in notes:
            parsed = parse_note(note.content)
            note.title = parsed.title
            note.body = parsed.body
            note.metadata = parsed.metadata
            note.tags = parsed.tags
            note.wiki_links = parsed.wiki_links
            note.entities = parsed.entities

            # upsert_note preserves the stored ID on path conflict, so
            # we capture the actual database ID for the FTS index.
            stored_id = upsert_note(conn, note)

            if note.wiki_links:
                process_wiki_links(conn, note)

            if note.tags:
                store_tags(conn, stored_id, note.tags)

            # Index into FTS using the stored (preserved) ID
            index_note_fts(conn, stored_id, note.title, note.body or note.content)

            # Index chunks into chunks_fts
            _ensure_chunks_schema(conn)
            note.id = stored_id
            chunks = chunk_note(note)
            delete_chunk_fts(conn, stored_id)
            for chunk in chunks:
                index_chunk_fts(conn, chunk)

            indexed += 1

        logger.info("Re-indexed %d note(s)", indexed)
        return indexed
    finally:
        conn.close()