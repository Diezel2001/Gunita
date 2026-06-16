"""Knowledge graph endpoints.

GET /api/graph/         — Full graph (nodes + edges) for all notes
GET /api/graph/{note_id} — Neighborhood around a specific note
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Relationship type → color mapping for frontend rendering
# ---------------------------------------------------------------------------

REL_TYPE_COLORS: dict[str, str] = {
    "EXPLICIT_LINK": "#6c9ce3",
    "PART_OF": "#7bc47f",
    "CONTAINS": "#e07b54",
    "DEPENDS_ON": "#d45d5d",
    "REQUIRES": "#d45d5d",
    "USES": "#c792ea",
    "PROVIDES": "#82aaff",
    "IMPLEMENTS": "#82aaff",
    "RELATED_TO": "#89ddff",
    "SIMILAR_TO": "#89ddff",
    "REFERENCES": "#ffcb6b",
    "MENTIONS": "#f0c674",
    "DESCRIBES": "#c3e88d",
    "PRECEDES": "#546e7a",
    "FOLLOWS": "#546e7a",
    "REPLACED_BY": "#ff5370",
    "DERIVED_FROM": "#f78c6c",
    "CAUSES": "#c53929",
    "INFLUENCES": "#e8912d",
    "RESULTS_IN": "#f07178",
    "CREATED_BY": "#a6accd",
    "OWNED_BY": "#a6accd",
    "ASSIGNED_TO": "#a6accd",
    "SUPPORTS": "#7fdbca",
    "CONTRADICTS": "#ff5370",
    "CONFIRMS": "#7fdbca",
    "QUESTIONED_BY": "#ffcb6b",
    "INFERRED_LINK": "#546e7a",
    "MEMORY_OF": "#c792ea",
    "OBSERVED_FROM": "#c792ea",
    "PARENT_OF": "#c3e88d",
    "CHILD_OF": "#c3e88d",
}

DEFAULT_EDGE_COLOR = "#89ddff"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """A single node in the knowledge graph."""
    note_id: str
    title: str
    path: str
    tags: list[str] = []
    degree: int = 0
    chunk_count: int = 0


class GraphEdge(BaseModel):
    """A single edge (relationship) between two notes."""
    source_id: str
    target_id: str
    rel_type: str


class GraphResponse(BaseModel):
    """Full graph payload."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_graph_data(
    note_ids: list[str],
    conn,
    *,
    include_edges_between: set[str] | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build graph nodes and edges from a set of note IDs.

    Applies deduplication: nodes sharing the same path are merged
    (the first encountered note_id is kept). Edges referencing
    merged-out or non-existent nodes are filtered out.

    Args:
        note_ids: The note IDs to include as nodes.
        conn: An open SQLite connection.
        include_edges_between: If provided, only include edges where
            both source_id and target_id are in this set. If None,
            include all edges for the given notes.

    Returns:
        Tuple of (nodes, edges) lists.
    """
    from bfai.db import get_note_by_id, get_relationships_for_note, get_tags_for_note

    # Build adjacency for degree counting
    degree_map: dict[str, int] = defaultdict(int)
    all_edges_raw: list[dict] = []

    for nid in note_ids:
        rels = get_relationships_for_note(conn, nid)
        for rel in rels:
            src = rel["source_id"]
            tgt = rel["target_id"]
            # Deduplicate: use a canonical key (sorted pair + type)
            edge_key = (min(src, tgt), max(src, tgt), rel["relationship_type"])
            all_edges_raw.append({
                "source_id": src,
                "target_id": tgt,
                "rel_type": rel["relationship_type"],
                "_key": edge_key,
            })
            degree_map[src] += 1
            degree_map[tgt] += 1

    # Deduplicate edges
    seen_keys: set[tuple[str, str, str]] = set()
    edges: list[GraphEdge] = []
    for raw in all_edges_raw:
        key = raw["_key"]
        if key not in seen_keys:
            seen_keys.add(key)
            # Filter edges if needed
            if include_edges_between is not None:
                if raw["source_id"] not in include_edges_between or raw["target_id"] not in include_edges_between:
                    continue
            edges.append(GraphEdge(
                source_id=raw["source_id"],
                target_id=raw["target_id"],
                rel_type=raw["rel_type"],
            ))

    # Build nodes
    raw_nodes: list[GraphNode] = []
    for nid in note_ids:
        note = get_note_by_id(conn, nid)
        if not note:
            continue
        tags = get_tags_for_note(conn, nid)
        raw_nodes.append(GraphNode(
            note_id=nid,
            title=note.get("title", "") or "",
            path=note.get("path", "") or "",
            tags=tags,
            degree=degree_map.get(nid, 0),
        ))

    # ── Filter out stale notes (files that no longer exist on disk) ──
    import os as _os
    live_nodes: list[GraphNode] = []
    stale_ids: set[str] = set()
    for node in raw_nodes:
        if node.path and _os.path.isfile(node.path):
            live_nodes.append(node)
        else:
            stale_ids.add(node.note_id)
    # Use only live nodes for dedup
    raw_nodes = live_nodes

    # ── Deduplicate nodes by title (case-insensitive) ──
    # If multiple note_ids share the same title (e.g. from old renamed directory
    # paths), merge them into a single node.  Prefer the node whose file exists
    # on disk (already filtered above, but belt-and-suspenders).
    seen_titles: dict[str, GraphNode] = {}
    merged_nodes: list[GraphNode] = []
    merged_id_map: dict[str, str] = {}  # old_id -> kept_id (maps merged-out IDs to the survivor)

    for node in raw_nodes:
        title_key = (node.title or "").strip().lower()
        if not title_key:
            title_key = node.note_id  # fallback to ID

        if title_key in seen_titles:
            # Duplicate title — merge into existing
            existing = seen_titles[title_key]
            existing.degree = max(existing.degree, node.degree)
            # Prefer the node with a longer (more complete) path
            if len(node.path) > len(existing.path):
                existing.path = node.path
            # Merge tags
            existing_tags_set = set(existing.tags)
            for t in node.tags:
                if t not in existing_tags_set:
                    existing.tags.append(t)
                    existing_tags_set.add(t)
            # Record that this old note_id maps to the survivor
            merged_id_map[node.note_id] = existing.note_id
        else:
            seen_titles[title_key] = node
            merged_nodes.append(node)

    # ── Remap edges ──
    # Build set of valid (surviving) note IDs
    valid_ids = set(n.note_id for n in merged_nodes)

    # Remap source/target through merged_id_map and filter invalid
    remapped_edges: list[GraphEdge] = []
    seen_edge_keys: set[tuple[str, str, str]] = set()
    for e in edges:
        src = merged_id_map.get(e.source_id, e.source_id)
        tgt = merged_id_map.get(e.target_id, e.target_id)
        # Skip self-loops created by merging
        if src == tgt:
            continue
        # Skip if either side no longer exists
        if src not in valid_ids or tgt not in valid_ids:
            continue
        # Deduplicate remapped edges
        edge_key = (min(src, tgt), max(src, tgt), e.rel_type)
        if edge_key in seen_edge_keys:
            continue
        seen_edge_keys.add(edge_key)
        remapped_edges.append(GraphEdge(source_id=src, target_id=tgt, rel_type=e.rel_type))

    return merged_nodes, remapped_edges


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=GraphResponse)
async def get_graph(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> GraphResponse:
    """Return the full knowledge graph as nodes and edges.

    Fetches all notes from the database, builds adjacency from
    relationships, and returns a vis.js-compatible structure.
    """
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_all_note_ids

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)
        all_ids = get_all_note_ids(conn)
        total = len(all_ids)
        # Apply pagination
        paginated_ids = all_ids[offset:offset + limit]

        nodes, edges = _build_graph_data(paginated_ids, conn)

        # Count chunks per note
        chunk_counts: dict[str, int] = {}
        try:
            rows = conn.execute(
                "SELECT note_id, COUNT(*) as cnt FROM chunks GROUP BY note_id"
            ).fetchall()
            for row in rows:
                chunk_counts[row["note_id"]] = row["cnt"]
        except Exception:
            pass  # chunks table may not exist yet

        for node in nodes:
            node.chunk_count = chunk_counts.get(node.note_id, 0)

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=total,
            total_edges=len(edges),
        )
    finally:
        conn.close()


@router.get("/{note_id}", response_model=GraphResponse)
async def get_neighborhood(
    note_id: str,
    hops: int = Query(default=2, ge=1, le=5),
) -> GraphResponse:
    """Return the neighborhood graph around a specific note (N hops)."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id, expand_graph

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        # Check that the note exists
        note = get_note_by_id(conn, note_id)
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        # Expand graph from this note
        expanded = expand_graph(conn, [note_id], max_hops=hops, max_nodes=200)
        note_ids = [item["note_id"] for item in expanded]

        # Build graph data, but only include edges between the expanded nodes
        expanded_set = set(note_ids)
        nodes, edges = _build_graph_data(
            note_ids, conn, include_edges_between=expanded_set,
        )

        # Count chunks per node
        chunk_counts: dict[str, int] = {}
        try:
            rows = conn.execute(
                "SELECT note_id, COUNT(*) as cnt FROM chunks GROUP BY note_id"
            ).fetchall()
            for row in rows:
                chunk_counts[row["note_id"]] = row["cnt"]
        except Exception:
            pass

        for node in nodes:
            node.chunk_count = chunk_counts.get(node.note_id, 0)

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )
    finally:
        conn.close()