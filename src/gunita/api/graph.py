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
    nodes: list[GraphNode] = []
    for nid in note_ids:
        note = get_note_by_id(conn, nid)
        if not note:
            continue
        tags = get_tags_for_note(conn, nid)
        nodes.append(GraphNode(
            note_id=nid,
            title=note.get("title", "") or "",
            path=note.get("path", "") or "",
            tags=tags,
            degree=degree_map.get(nid, 0),
        ))

    return nodes, edges


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

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )
    finally:
        conn.close()