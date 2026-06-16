"""SQLite database module for BFAI.

Manages the SQLite database that stores graph relationships, metadata,
and tag information for the knowledge vault.

The database file is stored in the vault's ``metadata`` subdirectory.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bfai.models import Note, Chunk
from bfai.vault import get_vault

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL DEFAULT '',
    created_at  TEXT,
    updated_at  TEXT,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    note_id UNINDEXED,
    title,
    body
);

CREATE TABLE IF NOT EXISTS relationships (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id, target_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    UNIQUE(note_id, tag)
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_relationships_source
    ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target
    ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type
    ON relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_tags_note
    ON tags(note_id);
CREATE INDEX IF NOT EXISTS idx_tags_tag
    ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_notes_path
    ON notes(path);
"""

# ---------------------------------------------------------------------------
# Ranking weights — matches the formula from the specification:
# final_score = 0.40 * text_relevance + 0.20 * importance +
#               0.10 * recency + 0.10 * access_frequency +
#               0.20 * (reserved for future signals like confidence, graph_distance)
# ---------------------------------------------------------------------------

RANK_WEIGHT_TEXT = 0.40
RANK_WEIGHT_IMPORTANCE = 0.20
RANK_WEIGHT_RECENCY = 0.10
RANK_WEIGHT_ACCESS = 0.10
RANK_WEIGHT_RESERVED = 0.20

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Return the path to the SQLite database file.

    The database is stored as ``bfai.db`` inside the vault's metadata
    directory.
    """
    vault = get_vault()
    return vault / "metadata" / "bfai.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Create and return a connection to the BFAI database.

    Args:
        db_path: Path to the database file. Defaults to the standard
            location inside the vault's metadata directory.

    Returns:
        A :class:`sqlite3.Connection` with ``row_factory`` set to
        :attr:`sqlite3.Row` and ``PRAGMA foreign_keys = ON``.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    logger.debug("Connected to database: %s", db_path)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist.

    This operation is idempotent — calling it multiple times is safe.

    Args:
        conn: An open SQLite connection.
    """
    conn.executescript(SCHEMA_SQL)
    conn.executescript(INDEXES_SQL)

    cur = conn.execute("SELECT MAX(version) FROM schema_version")
    row = cur.fetchone()
    current_version = row[0] if row[0] is not None else 0

    if current_version < SCHEMA_VERSION:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        logger.info("Schema initialized to version %d", SCHEMA_VERSION)

        if current_version < 2:
            _migrate_v1_to_v2(conn)
        if current_version < 3:
            _migrate_v2_to_v3(conn)

    conn.commit()
    logger.debug("Schema is up to date (version %d)", current_version or SCHEMA_VERSION)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate schema from version 1 to 2.

    Adds the ``access_count`` column to the ``notes`` table.
    """
    try:
        conn.execute("ALTER TABLE notes ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0;")
        logger.info("Migrated schema v1→v2: added access_count column")
    except sqlite3.OperationalError:
        logger.debug("access_count column already exists, skipping migration")


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a database connection and ensure the schema is created.

    Convenience wrapper that calls :func:`connect` and
    :func:`ensure_schema`.

    Args:
        db_path: Path to the database file. Defaults to the standard
            location.

    Returns:
        An open :class:`sqlite3.Connection` with the schema ready.
    """
    conn = connect(db_path)
    ensure_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Note CRUD
# ---------------------------------------------------------------------------


def upsert_note(conn: sqlite3.Connection, note: Note) -> str:
    """Insert a note into the database, or update it if the path exists.

    Uses the note's ``id``, ``path``, ``title``, ``created_at``, and
    ``updated_at`` fields. If a note with the same path already exists,
    its title and updated_at are updated (the original ID is preserved).

    Args:
        conn: An open SQLite connection.
        note: The Note object to persist.

    Returns:
        The actual stored note ID (the existing ID if the path already
        existed, or the newly inserted ID).
    """
    created_at_str = note.created_at.isoformat() if note.created_at else None
    updated_at_str = note.updated_at.isoformat() if note.updated_at else None

    conn.execute(
        """INSERT INTO notes (id, path, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET
               title       = excluded.title,
               updated_at  = excluded.updated_at""",
        (note.id, str(note.path), note.title, created_at_str, updated_at_str),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id FROM notes WHERE path = ?", (str(note.path),)
    ).fetchone()
    stored_id = row["id"] if row else note.id

    logger.debug("Upserted note: %s (stored: %s)", note.title, stored_id)
    return stored_id


# ---------------------------------------------------------------------------
# Access tracking
# ---------------------------------------------------------------------------


def increment_access_count(conn: sqlite3.Connection, note_id: str) -> None:
    """Increment the access counter for a note.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to bump.
    """
    conn.execute(
        "UPDATE notes SET access_count = access_count + 1 WHERE id = ?",
        (note_id,),
    )
    conn.commit()
    logger.debug("Incremented access count for note: %s", note_id)


def get_access_count(conn: sqlite3.Connection, note_id: str) -> int:
    """Get the current access count for a note.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note.

    Returns:
        The access count (0 if the note does not exist).
    """
    row = conn.execute(
        "SELECT access_count FROM notes WHERE id = ?", (note_id,)
    ).fetchone()
    return row["access_count"] if row else 0


# ---------------------------------------------------------------------------
# Relationship storage
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPE_KEYS = [
    "PART_OF",
    "CONTAINS",
    "PARENT_OF",
    "CHILD_OF",
    "DEPENDS_ON",
    "REQUIRES",
    "USES",
    "PROVIDES",
    "IMPLEMENTS",
    "RELATED_TO",
    "SIMILAR_TO",
    "REFERENCES",
    "MENTIONS",
    "DESCRIBES",
    "PRECEDES",
    "FOLLOWS",
    "REPLACED_BY",
    "DERIVED_FROM",
    "CAUSES",
    "INFLUENCES",
    "RESULTS_IN",
    "CREATED_BY",
    "OWNED_BY",
    "ASSIGNED_TO",
    "SUPPORTS",
    "CONTRADICTS",
    "CONFIRMS",
    "QUESTIONED_BY",
    "EXPLICIT_LINK",
    "INFERRED_LINK",
    "MEMORY_OF",
    "OBSERVED_FROM",
]


def _validate_relationship_type(rel_type: str) -> str:
    """Validate and normalize a relationship type string.

    Args:
        rel_type: The relationship type to validate.

    Returns:
        The uppercased relationship type if valid.

    Raises:
        ValueError: If the relationship type is not in the known set.
    """
    upper = rel_type.upper()
    if upper not in RELATIONSHIP_TYPE_KEYS:
        valid = ", ".join(RELATIONSHIP_TYPE_KEYS)
        raise ValueError(
            f"Unknown relationship type: {rel_type!r}. "
            f"Valid types: {valid}"
        )
    return upper


def store_relationship(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    rel_type: str,
) -> None:
    """Store a relationship between two notes.

    The relationship type is validated against the known set. Duplicate
    (source, target, type) tuples are silently ignored.

    Args:
        conn: An open SQLite connection.
        source_id: ID of the source note.
        target_id: ID of the target note.
        rel_type: Relationship type string (case-insensitive).

    Raises:
        ValueError: If the relationship type is not recognised.
        sqlite3.IntegrityError: If source_id or target_id do not exist
            in the notes table.
    """
    validated = _validate_relationship_type(rel_type)

    conn.execute(
        """INSERT OR IGNORE INTO relationships
               (source_id, target_id, relationship_type)
           VALUES (?, ?, ?)""",
        (source_id, target_id, validated),
    )
    conn.commit()
    logger.debug(
        "Stored relationship: %s --[%s]--> %s",
        source_id,
        validated,
        target_id,
    )


def store_relationships_bulk(
    conn: sqlite3.Connection,
    relationships: list[tuple[str, str, str]],
) -> None:
    """Store multiple relationships in a single transaction.

    Each tuple is ``(source_id, target_id, rel_type)``. Duplicates
    are silently ignored.

    Args:
        conn: An open SQLite connection.
        relationships: List of (source_id, target_id, rel_type) tuples.

    Raises:
        ValueError: If any relationship type is not recognised.
        sqlite3.IntegrityError: If any source_id or target_id does not
            exist in the notes table.
    """
    validated: list[tuple[str, str, str]] = []
    for source, target, rel_type in relationships:
        validated.append(
            (source, target, _validate_relationship_type(rel_type))
        )

    conn.executemany(
        """INSERT OR IGNORE INTO relationships
               (source_id, target_id, relationship_type)
           VALUES (?, ?, ?)""",
        validated,
    )
    conn.commit()
    logger.debug("Stored %d relationship(s) in bulk", len(validated))


def get_relationships_for_note(
    conn: sqlite3.Connection,
    note_id: str,
) -> list[dict[str, str | None]]:
    """Get all relationships involving a note (outgoing and incoming).

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to query.

    Returns:
        List of dicts with keys ``source_id``, ``target_id``,
        ``relationship_type``, ``created_at``.
    """
    rows = conn.execute(
        """SELECT source_id, target_id, relationship_type, created_at
           FROM relationships
           WHERE source_id = ? OR target_id = ?
           ORDER BY relationship_type, source_id""",
        (note_id, note_id),
    ).fetchall()

    return [dict(row) for row in rows]


def delete_relationships_for_note(
    conn: sqlite3.Connection,
    note_id: str,
) -> None:
    """Delete all relationships involving a note.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note whose relationships to delete.
    """
    conn.execute(
        "DELETE FROM relationships WHERE source_id = ? OR target_id = ?",
        (note_id, note_id),
    )
    conn.commit()
    logger.debug("Deleted relationships for note: %s", note_id)


# ---------------------------------------------------------------------------
# Wiki links → relationships
# ---------------------------------------------------------------------------


def process_wiki_links(
    conn: sqlite3.Connection,
    note: Note,
) -> list[tuple[str, str, str]]:
    """Convert a note's wiki links into ``EXPLICIT_LINK`` relationships.

    For each wiki link target in the note's ``wiki_links`` list, the
    function looks up the target note by title (case-insensitive) in the
    database. If the target exists, an ``EXPLICIT_LINK`` relationship is
    stored from this note to the target. Targets that are not found in
    the database are silently skipped.

    Existing ``EXPLICIT_LINK`` relationships for the source note are
    replaced (deleted then re-created) to stay in sync with the parsed
    wiki links.

    Args:
        conn: An open SQLite connection.
        note: The Note whose wiki links should be processed. The note
            must already exist in the database (via :func:`upsert_note`).

    Returns:
        List of ``(source_id, target_id, relationship_type)`` tuples
        that were stored.
    """
    conn.execute(
        "DELETE FROM relationships WHERE source_id = ? AND relationship_type = 'EXPLICIT_LINK'",
        (note.id,),
    )

    stored: list[tuple[str, str, str]] = []
    for link_target in note.wiki_links:
        target = get_note_by_title(conn, link_target)
        if target is None:
            logger.debug(
                "Wiki link target not found in database: %r (source: %s)",
                link_target,
                note.title,
            )
            continue

        conn.execute(
            """INSERT OR IGNORE INTO relationships
                   (source_id, target_id, relationship_type)
               VALUES (?, ?, 'EXPLICIT_LINK')""",
            (note.id, target["id"]),
        )
        stored.append((note.id, target["id"], "EXPLICIT_LINK"))

    conn.commit()
    logger.debug(
        "Processed %d wiki link(s) for note %s (%d stored)",
        len(note.wiki_links),
        note.title,
        len(stored),
    )
    return stored


# ---------------------------------------------------------------------------
# Tag-based relationship generation
# ---------------------------------------------------------------------------


def generate_tag_relationships(
    conn: sqlite3.Connection,
    *,
    min_shared_tags: int = 1,
) -> int:
    """Generate ``RELATED_TO`` relationships between notes sharing tags.

    For every pair of notes that share at least ``min_shared_tags`` tags,
    a ``RELATED_TO`` relationship is created (or left intact if it already
    exists).  Existing ``RELATED_TO`` relationships that no longer share
    enough tags are removed.

    Args:
        conn: An open SQLite connection.
        min_shared_tags: Minimum number of shared tags required to
            create a relationship (default 1).

    Returns:
        The number of ``RELATED_TO`` relationships created or retained.
    """
    from collections import defaultdict

    # Build tag → set of note_ids mapping
    tag_notes: dict[str, set[str]] = defaultdict(set)
    rows = conn.execute("SELECT note_id, tag FROM tags").fetchall()
    for row in rows:
        tag_notes[row["tag"]].add(row["note_id"])

    # Build pairs of notes that share tags
    pair_shared: dict[tuple[str, str], int] = defaultdict(int)
    for _tag, note_ids in tag_notes.items():
        sorted_ids = sorted(note_ids)
        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                pair_shared[(sorted_ids[i], sorted_ids[j])] += 1

    # Filter to pairs meeting the threshold
    new_pairs = {
        pair: count
        for pair, count in pair_shared.items()
        if count >= min_shared_tags
    }

    # Remove existing RELATED_TO relationships that no longer qualify
    existing = conn.execute(
        """SELECT source_id, target_id FROM relationships
           WHERE relationship_type = 'RELATED_TO'"""
    ).fetchall()
    existing_pairs = {(r["source_id"], r["target_id"]) for r in existing}

    for src, tgt in existing_pairs:
        pair = (min(src, tgt), max(src, tgt))
        if pair not in new_pairs:
            conn.execute(
                """DELETE FROM relationships
                   WHERE source_id = ? AND target_id = ?
                     AND relationship_type = 'RELATED_TO'""",
                (src, tgt),
            )

    # Insert new relationships
    count = 0
    for (src, tgt), _shared in new_pairs.items():
        conn.execute(
            """INSERT OR IGNORE INTO relationships
                   (source_id, target_id, relationship_type)
               VALUES (?, ?, 'RELATED_TO')""",
            (src, tgt),
        )
        count += 1

    conn.commit()
    logger.debug(
        "Generated %d RELATED_TO relationships from shared tags", count,
    )
    return count


def resolve_all_wiki_links(conn: sqlite3.Connection) -> int:
    """Resolve wiki links for ALL notes in the database.

    This is a second-pass operation that should be called after all
    notes have been upserted.  It re-processes wiki links for every
    note, ensuring that cross-references between notes are captured
    even when notes were originally indexed out of order.

    Returns:
        The total number of EXPLICIT_LINK relationships created.
    """
    notes = conn.execute(
        "SELECT id, path FROM notes ORDER BY id"
    ).fetchall()

    total_created = 0
    for note_row in notes:
        note_id = note_row["id"]
        note_path = note_row["path"]
        if not note_path:
            continue

        try:
            from bfai.loader import load_note
            from bfai.parser import parse_note

            file_path = Path(note_path)
            if not file_path.is_file():
                continue

            note_obj = load_note(file_path)
            parsed = parse_note(note_obj.content)
            note_obj.title = parsed.title
            note_obj.body = parsed.body
            note_obj.metadata = parsed.metadata
            note_obj.tags = parsed.tags
            note_obj.wiki_links = parsed.wiki_links

            note_obj.id = note_id
            if note_obj.wiki_links:
                stored = process_wiki_links(conn, note_obj)
                total_created += len(stored)
        except Exception as exc:
            logger.debug(
                "Failed to resolve wiki links for %s: %s", note_path, exc,
            )

    conn.commit()
    logger.info(
        "Resolved wiki links for %d notes, created %d EXPLICIT_LINK relationships",
        len(notes),
        total_created,
    )
    return total_created


# ---------------------------------------------------------------------------
# Tag storage
# ---------------------------------------------------------------------------


def store_tags(
    conn: sqlite3.Connection,
    note_id: str,
    tags: list[str],
) -> None:
    """Replace all tags for a note.

    Existing tags are deleted first, then the new tags are inserted.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note.
        tags: List of tag strings to set.

    Raises:
        sqlite3.IntegrityError: If note_id does not exist in the notes
            table.
    """
    conn.execute("DELETE FROM tags WHERE note_id = ?", (note_id,))

    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO tags (note_id, tag) VALUES (?, ?)",
            (note_id, tag),
        )

    conn.commit()
    logger.debug("Stored %d tag(s) for note: %s", len(tags), note_id)


def get_tags_for_note(
    conn: sqlite3.Connection,
    note_id: str,
) -> list[str]:
    """Get all tags for a note.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to query.

    Returns:
        Sorted list of tag strings.
    """
    rows = conn.execute(
        "SELECT tag FROM tags WHERE note_id = ? ORDER BY tag",
        (note_id,),
    ).fetchall()

    return [row["tag"] for row in rows]


def get_all_tags(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Get all tags grouped by note ID.

    Returns:
        Dict mapping note ID to a sorted list of tag strings.
    """
    rows = conn.execute(
        "SELECT note_id, tag FROM tags ORDER BY note_id, tag"
    ).fetchall()

    result: dict[str, list[str]] = {}
    for row in rows:
        note_id = row["note_id"]
        if note_id not in result:
            result[note_id] = []
        result[note_id].append(row["tag"])

    return result


# ---------------------------------------------------------------------------
# Relationship queries
# ---------------------------------------------------------------------------


def _query_related(
    conn: sqlite3.Connection,
    note_id: str,
    related_col: str,
    where_clause: str,
    where_params: list[str | None],
    type_filter: str,
) -> list[dict[str, str | None]]:
    """Internal helper to build and execute a related-notes query.

    Args:
        conn: Database connection.
        note_id: The ID of the note being queried.
        related_col: SQL expression for the related note's ID column.
        where_clause: WHERE clause with ``?`` placeholders.
        where_params: Parameter values for the WHERE clause.
        type_filter: Additional filter string or empty.
    """
    sql = f"""
        SELECT r.source_id,
               r.target_id,
               r.relationship_type,
               {related_col} AS related_note_id,
               n.title         AS related_title,
               n.path          AS related_path
          FROM relationships r
          JOIN notes n ON n.id = {related_col}
         WHERE {where_clause}
           {type_filter}
         ORDER BY r.relationship_type, n.title
    """
    rows = conn.execute(sql, where_params).fetchall()
    return [dict(row) for row in rows]


def get_related_notes(
    conn: sqlite3.Connection,
    note_id: str,
    *,
    relationship_type: str | None = None,
    direction: str = "both",
) -> list[dict[str, str | None]]:
    """Get notes related to a given note via graph relationships.

    Returns details about the related notes (title, path) along with
    the relationship that connects them.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the source note.
        relationship_type: Optional filter to restrict to a specific
            relationship type. Case-insensitive.
        direction: One of ``"outgoing"``, ``"incoming"``, or ``"both"``
            (default).

    Returns:
        List of dicts with keys ``source_id``, ``target_id``,
        ``relationship_type``, ``related_note_id``, ``related_title``,
        ``related_path``.

    Raises:
        ValueError: If ``direction`` or ``relationship_type`` is invalid.
    """
    if direction not in ("outgoing", "incoming", "both"):
        raise ValueError(
            f"Invalid direction: {direction!r}. "
            f"Expected 'outgoing', 'incoming', or 'both'."
        )

    type_params: list[str | None] = []
    type_filter = ""

    if relationship_type is not None:
        validated = _validate_relationship_type(relationship_type)
        type_filter = "AND r.relationship_type = ?"
        type_params.append(validated)

    if direction == "outgoing":
        return _query_related(
            conn, note_id, "r.target_id",
            "r.source_id = ?", [note_id, *type_params],
            type_filter,
        )
    elif direction == "incoming":
        return _query_related(
            conn, note_id, "r.source_id",
            "r.target_id = ?", [note_id, *type_params],
            type_filter,
        )
    else:
        outgoing = _query_related(
            conn, note_id, "r.target_id",
            "r.source_id = ?", [note_id, *type_params],
            type_filter,
        )
        incoming = _query_related(
            conn, note_id, "r.source_id",
            "r.target_id = ?", [note_id, *type_params],
            type_filter,
        )
        merged = outgoing + incoming
        merged.sort(key=lambda r: (r["relationship_type"] or "", r["related_title"] or ""))
        return merged


# ---------------------------------------------------------------------------
# Graph expansion (Story 7.2)
# ---------------------------------------------------------------------------


def expand_graph(
    conn: sqlite3.Connection,
    seed_ids: list[str],
    max_hops: int = 2,
    max_nodes: int = 50,
) -> list[dict[str, str | None]]:
    """Traverse the relationship graph from seed nodes up to ``max_hops``.

    Starting from the given seed note IDs, the function follows
    relationships in both directions (outgoing and incoming) for the
    specified number of hops. Duplicate nodes are removed on each hop
    so that the same note does not appear multiple times.

    Args:
        conn: An open SQLite connection.
        seed_ids: List of note IDs to start the traversal from.
        max_hops: Maximum depth of graph traversal (default 2,
            minimum 0).
        max_nodes: Maximum number of unique nodes to return (default 50).

    Returns:
        List of dicts with keys ``note_id``, ``title``, ``path``,
        ``hop_depth`` (the hop at which this node was discovered),
        ordered by hop depth then title.
    """
    if max_hops < 0:
        raise ValueError(f"max_hops must be >= 0, got {max_hops}")

    if not seed_ids:
        return []

    # Track discovered nodes: note_id -> (title, path, hop_depth)
    discovered: dict[str, tuple[str, str, int]] = {}

    # Initialize with seed nodes at hop 0
    for nid in seed_ids:
        if nid not in discovered:
            row = conn.execute(
                "SELECT id, title, path FROM notes WHERE id = ?", (nid,)
            ).fetchone()
            if row:
                discovered[row["id"]] = (row["title"], row["path"], 0)

    # BFS traversal: current frontier starts as seeds
    frontier: list[str] = [nid for nid in seed_ids if nid in discovered]

    for hop in range(1, max_hops + 1):
        if not frontier:
            break

        next_frontier: set[str] = set()

        for current_id in frontier:
            # Get all neighbors (both outgoing and incoming)
            rows = conn.execute(
                """SELECT source_id, target_id
                   FROM relationships
                   WHERE source_id = ? OR target_id = ?""",
                (current_id, current_id),
            ).fetchall()

            for row in rows:
                neighbor_id = row["target_id"] if row["source_id"] == current_id else row["source_id"]
                if neighbor_id not in discovered:
                    next_frontier.add(neighbor_id)

        # Look up titles and paths for the new neighbors
        for nid in list(next_frontier):
            row = conn.execute(
                "SELECT id, title, path FROM notes WHERE id = ?", (nid,)
            ).fetchone()
            if row:
                discovered[row["id"]] = (row["title"], row["path"], hop)
            else:
                next_frontier.discard(nid)

        frontier = list(next_frontier)

        if len(discovered) >= max_nodes:
            break

    # Convert to sorted list
    result = [
        {
            "note_id": nid,
            "title": info[0],
            "path": info[1],
            "hop_depth": info[2],
        }
        for nid, info in discovered.items()
    ]
    result.sort(key=lambda r: (r["hop_depth"], r["title"] or ""))
    return result[:max_nodes]


# ---------------------------------------------------------------------------
# Backlinks API (Story 5.1)
# ---------------------------------------------------------------------------


def get_backlinks(
    conn: sqlite3.Connection,
    note_id: str,
    *,
    relationship_type: str | None = None,
) -> list[dict[str, str | None]]:
    """Get all notes that link *to* the given note (backlinks).

    Backlinks are incoming relationships — notes that reference,
    mention, or otherwise point to the given note. This is equivalent
    to ``get_related_notes(conn, note_id, direction="incoming")`` but
    provides a semantically clearer name and a simpler signature.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note whose backlinks to retrieve.
        relationship_type: Optional filter to restrict to a specific
            relationship type (e.g. ``"EXPLICIT_LINK"``). Case-insensitive.

    Returns:
        List of dicts with keys ``source_id``, ``target_id``,
        ``relationship_type``, ``related_note_id`` (the backlinking
        note's ID), ``related_title``, ``related_path``.

    Raises:
        ValueError: If the relationship type is invalid.
    """
    return get_related_notes(
        conn, note_id, relationship_type=relationship_type, direction="incoming",
    )


def get_note_by_id(
    conn: sqlite3.Connection,
    note_id: str,
) -> dict[str, str | None] | None:
    """Get a single note by its ID.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to look up.

    Returns:
        A dict with keys ``id``, ``path``, ``title``, ``created_at``,
        ``updated_at``, or ``None`` if not found.
    """
    row = conn.execute(
        "SELECT id, path, title, created_at, updated_at, access_count FROM notes WHERE id = ?",
        (note_id,),
    ).fetchone()

    return dict(row) if row else None


def get_note_by_path(
    conn: sqlite3.Connection,
    path: str,
) -> dict[str, str | None] | None:
    """Get a single note by its filesystem path.

    Args:
        conn: An open SQLite connection.
        path: The filesystem path of the note.

    Returns:
        A dict with keys ``id``, ``path``, ``title``, ``created_at``,
        ``updated_at``, or ``None`` if not found.
    """
    row = conn.execute(
        "SELECT id, path, title, created_at, updated_at, access_count FROM notes WHERE path = ?",
        (path,),
    ).fetchone()

    return dict(row) if row else None


def get_note_by_title(
    conn: sqlite3.Connection,
    title: str,
) -> dict[str, str | None] | None:
    """Get a single note by its title (case-insensitive).

    Args:
        conn: An open SQLite connection.
        title: The title of the note to look up.

    Returns:
        A dict with keys ``id``, ``path``, ``title``, ``created_at``,
        ``updated_at``, or ``None`` if not found.
    """
    row = conn.execute(
        "SELECT id, path, title, created_at, updated_at, access_count FROM notes WHERE LOWER(title) = LOWER(?)",
        (title,),
    ).fetchone()

    return dict(row) if row else None


def get_all_note_ids(conn: sqlite3.Connection) -> list[str]:
    """Get all note IDs in the database.

    Args:
        conn: An open SQLite connection.

    Returns:
        Sorted list of note IDs.
    """
    rows = conn.execute(
        "SELECT id FROM notes ORDER BY id"
    ).fetchall()

    return [row["id"] for row in rows]


def cleanup_stale_notes(conn: sqlite3.Connection) -> tuple[int, int]:
    """Remove notes whose file no longer exists on disk.

    Deletes the note record, its FTS entry, chunks, and relationships.
    Returns (total_deleted, total_checked).

    This is a data-cleanup operation — safe to run periodically.
    """
    import os
    rows = conn.execute("SELECT id, path FROM notes").fetchall()
    total_checked = len(rows)
    total_deleted = 0

    for row in rows:
        note_id = row["id"]
        path = row["path"]
        if path and not os.path.isfile(path):
            # Delete from FTS
            conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
            # Delete chunks
            conn.execute("DELETE FROM chunks_fts WHERE note_id = ?", (note_id,))
            conn.execute("DELETE FROM chunks WHERE note_id = ?", (note_id,))
            # Delete relationships (CASCADE handles this, but be explicit)
            conn.execute("DELETE FROM relationships WHERE source_id = ? OR target_id = ?", (note_id, note_id))
            # Delete tags
            conn.execute("DELETE FROM tags WHERE note_id = ?", (note_id,))
            # Delete the note itself
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            total_deleted += 1

    conn.commit()
    logger.info(
        "Cleaned up %d stale notes out of %d total",
        total_deleted,
        total_checked,
    )
    return total_deleted, total_checked


def delete_note_by_id(conn: sqlite3.Connection, note_id: str) -> bool:
    """Delete a note and all related data (cascades to tags and
    relationships).

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to delete.

    Returns:
        ``True`` if a note was deleted, ``False`` if not found.
    """
    cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    if deleted:
        logger.debug("Deleted note from database: %s", note_id)
    return deleted


# ---------------------------------------------------------------------------
# Full-text search (FTS5)
# ---------------------------------------------------------------------------


def index_note_fts(
    conn: sqlite3.Connection,
    note_id: str,
    title: str,
    body: str,
) -> None:
    """Insert or update a note in the FTS5 full-text index.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to index.
        title: The note title.
        body: The markdown body content.
    """
    conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
    conn.execute(
        "INSERT INTO notes_fts (note_id, title, body) VALUES (?, ?, ?)",
        (note_id, title, body),
    )
    conn.commit()
    logger.debug("Indexed note in FTS: %s", note_id)


def delete_note_fts(conn: sqlite3.Connection, note_id: str) -> None:
    """Remove a note from the FTS5 full-text index.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note to remove from the index.
    """
    conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
    conn.commit()
    logger.debug("Removed note from FTS index: %s", note_id)


def rebuild_fts_index(
    conn: sqlite3.Connection,
    notes: list[Note],
) -> None:
    """Rebuild the full FTS5 index from scratch.

    All existing FTS entries are deleted first, then the provided notes
    are indexed in a single transaction.

    Args:
        conn: An open SQLite connection.
        notes: List of Note objects to index.
    """
    conn.execute("DELETE FROM notes_fts")
    for note in notes:
        conn.execute(
            "INSERT INTO notes_fts (note_id, title, body) VALUES (?, ?, ?)",
            (note.id, note.title, note.body or note.content),
        )
    conn.commit()
    logger.debug("Rebuilt FTS index with %d note(s)", len(notes))


# ---------------------------------------------------------------------------
# FTS5 query sanitization
# ---------------------------------------------------------------------------


def _sanitize_fts5_query(query: str) -> str:
    """Sanitize a user-provided FTS5 search query to prevent crashes.

    Escapes or removes characters and patterns that would cause
    ``sqlite3.OperationalError``:
    - Unmatched double quotes (``"``)
    - Bare boolean operators (``AND``, ``OR``, ``NOT``) at start/end
    - Unbalanced parentheses

    Args:
        query: Raw user query string.

    Returns:
        A sanitized query safe for FTS5 ``MATCH``.
    """
    if not query or not query.strip():
        return ""

    # Strip whitespace
    q = query.strip()

    # Escape unbalanced double quotes: FTS5 requires paired quotes.
    # Count quotes; if odd, append a closing quote.
    if q.count('"') % 2 != 0:
        q += '"'

    # Ensure balanced parentheses
    open_count = q.count("(")
    close_count = q.count(")")
    if open_count > close_count:
        q += ")" * (open_count - close_count)

    # Remove trailing operators that would cause syntax errors
    trailing_operators = ("AND", "OR", "NOT", "and", "or", "not")
    while q.split() and q.split()[-1] in trailing_operators:
        q = " ".join(q.split()[:-1])

    # Remove leading operators
    while q.split() and q.split()[0].upper() in ("AND", "OR", "NOT"):
        q = " ".join(q.split()[1:])

    return q


def search_notes(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
) -> list[dict[str, str | None | float]]:
    """Full-text search across indexed notes.

    Uses SQLite FTS5 ranking (BM25) for relevance scoring.

    Args:
        conn: An open SQLite connection.
        query: The search query string (FTS5 query syntax supported).
        limit: Maximum number of results to return (default 20).

    Returns:
        List of dicts with keys ``note_id``, ``title``, ``path``,
        ``rank`` (float, lower is better/relevant), ordered by rank.

    Raises:
        sqlite3.OperationalError: If the query contains invalid FTS5
            syntax after sanitization.
    """
    sanitized = _sanitize_fts5_query(query)
    if not sanitized:
        return []

    rows = conn.execute(
        """SELECT n.id       AS note_id,
                   n.title    AS title,
                   n.path     AS path,
                   fts.rank   AS rank
              FROM notes_fts fts
              JOIN notes n    ON n.id = fts.note_id
             WHERE notes_fts MATCH ?
             ORDER BY rank
             LIMIT ?""",
        (sanitized, limit),
    ).fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Ranked search (Story 4.3)
# ---------------------------------------------------------------------------


def _normalize_rank(rank: float, min_rank: float, max_rank: float) -> float:
    """Normalise a BM25 rank to a [0, 1] score where higher is better.

    BM25 rank is typically negative; lower (more negative) means better
    match.  We invert and clamp to [0, 1].
    """
    if max_rank == min_rank:
        return 1.0
    normalized = (max_rank - rank) / (max_rank - min_rank)
    return max(0.0, min(1.0, normalized))


def _compute_recency_score(updated_at_str: str | None, now: datetime) -> float:
    """Compute a recency score in [0, 1] based on how recently the note
    was updated.

    Uses an exponential decay with a half-life of 30 days.
    """
    HALF_LIFE_DAYS = 30.0

    if not updated_at_str:
        return 0.0

    try:
        updated = datetime.fromisoformat(updated_at_str)
    except (ValueError, TypeError):
        return 0.0

    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    days = max(0.0, (now - updated).total_seconds() / 86400.0)
    score = math.exp(-days * math.log(2) / HALF_LIFE_DAYS)
    return score


def _normalize_access_count(count: int, max_count: int) -> float:
    """Normalise an access count to a [0, 1] score.

    Uses logarithmic scaling so that one very popular note doesn't
    squash all others.
    """
    if max_count <= 0:
        return 0.0
    return math.log1p(count) / math.log1p(max_count)


def ranked_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    now: datetime | None = None,
) -> list[dict[str, str | None | float]]:
    """Full-text search with multi-factor ranking.

    Combines BM25 text relevance (40%), recency (10%), access frequency
    (10%), and importance signals (20%) into a unified score.

    Args:
        conn: An open SQLite connection.
        query: The search query string (FTS5 query syntax supported).
        limit: Maximum number of results to return (default 20).
        now: The reference time for recency calculations. Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        List of dicts with keys ``note_id``, ``title``, ``path``,
        ``rank``, ``recency_score``, ``access_score``,
        ``importance_score``, ``combined_score``, ordered by
        ``combined_score`` descending.

    Raises:
        sqlite3.OperationalError: If the query contains invalid FTS5
            syntax.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    sanitized = _sanitize_fts5_query(query)
    if not sanitized:
        return []

    rows = conn.execute(
        """SELECT n.id             AS note_id,
                   n.title          AS title,
                   n.path           AS path,
                   fts.rank         AS rank,
                   n.updated_at     AS updated_at,
                   n.access_count   AS access_count
              FROM notes_fts fts
              JOIN notes n          ON n.id = fts.note_id
             WHERE notes_fts MATCH ?
             ORDER BY rank
             LIMIT ?""",
        (sanitized, limit * 2),
    ).fetchall()

    results = [dict(row) for row in rows]
    if not results:
        return []

    ranks = [r["rank"] for r in results if r["rank"] is not None]
    min_rank = min(ranks) if ranks else 0.0
    max_rank = max(ranks) if ranks else 0.0

    access_counts = [r["access_count"] or 0 for r in results]
    max_access = max(access_counts) if access_counts else 0

    title_lengths = [len(r["title"] or "") for r in results]
    max_title_len = max(title_lengths) if title_lengths else 1

    scored = []
    for r in results:
        text_score = _normalize_rank(r["rank"], min_rank, max_rank)
        recency_score = _compute_recency_score(r["updated_at"], now)
        access_score = _normalize_access_count(r["access_count"] or 0, max_access)
        import_score = (len(r["title"] or "") / max_title_len) if max_title_len > 0 else 0.0

        combined = (
            RANK_WEIGHT_TEXT * text_score
            + RANK_WEIGHT_RECENCY * recency_score
            + RANK_WEIGHT_ACCESS * access_score
            + RANK_WEIGHT_IMPORTANCE * import_score
            + RANK_WEIGHT_RESERVED * 0.5
        )

        scored.append({
            "note_id": r["note_id"],
            "title": r["title"],
            "path": r["path"],
            "rank": r["rank"],
            "recency_score": round(recency_score, 4),
            "access_score": round(access_score, 4),
            "importance_score": round(import_score, 4),
            "combined_score": round(combined, 4),
        })

    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------------------
# Chunk-level FTS5 indexing (Phase 2)
# ---------------------------------------------------------------------------


CHUNKS_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    note_id UNINDEXED,
    heading_path,
    text,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    section_heading TEXT,
    heading_path TEXT,   -- JSON array of strings e.g. '["NLP", "Applications", "Text Classification"]'
    text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_note ON chunks(note_id);
"""


def _ensure_chunks_schema(conn: sqlite3.Connection) -> None:
    """Create chunk-related tables if they do not exist.

    Idempotent — safe to call multiple times.
    """
    conn.executescript(CHUNKS_SCHEMA_SQL)
    conn.commit()


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate schema from version 2 to 3.

    Creates the ``chunks`` and ``chunks_fts`` tables.
    Does NOT reindex existing notes here — the incremental reindex
    loop will handle chunk indexing naturally during the next scan.
    Reindexing here would set ``updated_at`` timestamps prematurely,
    causing ``incremental_reindex()`` to skip all existing files.
    """
    _ensure_chunks_schema(conn)
    logger.info("Migrated schema v2→v3: created chunks and chunks_fts tables")


def index_chunk_fts(
    conn: sqlite3.Connection,
    chunk: Chunk,
) -> None:
    """Index a single chunk in chunks_fts and chunks table.

    Args:
        conn: An open SQLite connection.
        chunk: The Chunk object to index.
    """
    conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
    conn.execute(
        "INSERT INTO chunks_fts (chunk_id, note_id, heading_path, text) VALUES (?, ?, ?, ?)",
        (chunk.chunk_id, chunk.note_id, json.dumps(chunk.heading_path), chunk.text),
    )
    conn.execute(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, note_id, section_heading, heading_path, text, chunk_index)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (chunk.chunk_id, chunk.note_id, chunk.section_heading,
         json.dumps(chunk.heading_path), chunk.text, chunk.chunk_index),
    )
    conn.commit()


def delete_chunk_fts(conn: sqlite3.Connection, note_id: str) -> None:
    """Remove all chunks for a note from chunks_fts and chunks tables.

    Args:
        conn: An open SQLite connection.
        note_id: The ID of the note whose chunks to remove.
    """
    conn.execute("DELETE FROM chunks_fts WHERE note_id = ?", (note_id,))
    conn.execute("DELETE FROM chunks WHERE note_id = ?", (note_id,))
    conn.commit()


def chunk_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search at the chunk level using FTS5.

    Args:
        conn: An open SQLite connection.
        query: The search query string (FTS5 query syntax supported).
        limit: Maximum number of results to return (default 20).

    Returns:
        List of dicts with keys: chunk_id, note_id, note_title, title,
        section_heading, heading_path, text, rank, snippet, ordered by
        rank (BM25 relevance).
    """
    sanitized = _sanitize_fts5_query(query)
    if not sanitized:
        return []

    rows = conn.execute(
        """SELECT c.chunk_id,
                   c.note_id,
                   n.title AS note_title,
                   n.path AS note_path,
                   c.section_heading,
                   c.heading_path,
                   c.text,
                   fts.rank,
                   snippet(chunks_fts, 3, '<b>', '</b>', '...', 32) AS snippet
              FROM chunks_fts fts
              JOIN chunks c ON c.chunk_id = fts.chunk_id
              JOIN notes n  ON n.id = c.note_id
             WHERE chunks_fts MATCH ?
             ORDER BY rank
             LIMIT ?""",
        (sanitized, limit),
    ).fetchall()

    return [dict(row) for row in rows]