"""Tests for the database module."""
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from bfai.db import (
    SCHEMA_SQL,
    INDEXES_SQL,
    SCHEMA_VERSION,
    RANK_WEIGHT_TEXT,
    RANK_WEIGHT_RECENCY,
    RANK_WEIGHT_ACCESS,
    RANK_WEIGHT_IMPORTANCE,
    RANK_WEIGHT_RESERVED,
    RELATIONSHIP_TYPE_KEYS,
    connect,
    delete_note_by_id,
    delete_note_fts,
    delete_relationships_for_note,
    ensure_schema,
    expand_graph,
    get_access_count,
    get_all_note_ids,
    get_all_tags,
    get_backlinks,
    get_db_path,
    get_note_by_id,
    get_note_by_path,
    get_note_by_title,
    get_related_notes,
    get_relationships_for_note,
    get_tags_for_note,
    increment_access_count,
    index_note_fts,
    init_db,
    process_wiki_links,
    ranked_search,
    rebuild_fts_index,
    search_notes,
    store_relationship,
    store_relationships_bulk,
    store_tags,
    upsert_note,
    _validate_relationship_type,
)
from bfai.models import Note


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_conn(tmp_path):
    """Create a fresh in-memory database for each test."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def sample_note() -> Note:
    """Create a simple Note for testing."""
    now = datetime(2026, 6, 10, 12, 0, 0)
    return Note(
        path=Path("/vault/notes/test-note.md"),
        content="# Test Note\n\nHello world.",
        title="Test Note",
        id="note-001",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def two_notes(db_conn) -> tuple[str, str]:
    """Insert two notes and return their IDs."""
    now = datetime(2026, 6, 10, 12, 0, 0)
    n1 = Note(
        path=Path("/vault/notes/note-a.md"),
        content="# Note A",
        title="Note A",
        id="note-a",
        created_at=now,
        updated_at=now,
    )
    n2 = Note(
        path=Path("/vault/notes/note-b.md"),
        content="# Note B",
        title="Note B",
        id="note-b",
        created_at=now,
        updated_at=now,
    )
    upsert_note(db_conn, n1)
    upsert_note(db_conn, n2)
    return "note-a", "note-b"


# ===========================================================================
# Existing tests (unchanged)
# ===========================================================================


class TestGetDbPath:
    """Tests for database path resolution."""

    def test_get_db_path_returns_path(self):
        """get_db_path should return a path ending with bfai.db."""
        db_path = get_db_path()
        assert isinstance(db_path, Path)
        assert db_path.name == "bfai.db"

    def test_get_db_path_in_metadata(self):
        """get_db_path should be inside a metadata subdirectory."""
        db_path = get_db_path()
        assert "metadata" in db_path.parts


class TestConnect:
    """Tests for database connections."""

    def test_connect_creates_parent_dirs(self):
        """connect should create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sub" / "test.db"
            assert not db_path.parent.exists()

            conn = connect(db_path)
            try:
                assert db_path.parent.exists()
            finally:
                conn.close()

    def test_connect_returns_connection(self):
        """connect should return a sqlite3.Connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = connect(db_path)
            try:
                assert isinstance(conn, sqlite3.Connection)
            finally:
                conn.close()

    def test_connect_sets_row_factory(self):
        """connect should set row_factory to sqlite3.Row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = connect(db_path)
            try:
                assert conn.row_factory is sqlite3.Row
            finally:
                conn.close()

    def test_connect_enables_foreign_keys(self):
        """connect should enable foreign key enforcement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = connect(db_path)
            try:
                cur = conn.execute("PRAGMA foreign_keys;")
                assert cur.fetchone()[0] == 1
            finally:
                conn.close()

    def test_connect_enables_wal_mode(self):
        """connect should enable WAL journal mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = connect(db_path)
            try:
                cur = conn.execute("PRAGMA journal_mode;")
                assert cur.fetchone()[0].lower() == "wal"
            finally:
                conn.close()

    def test_connect_default_path(self):
        """connect with no args should use the default db path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect(Path(tmpdir) / "default_test.db")
            try:
                cur = conn.execute("SELECT 1;")
                assert cur.fetchone()[0] == 1
            finally:
                conn.close()


class TestEnsureSchema:
    """Tests for schema initialization."""

    def test_schema_creates_tables(self, tmp_path):
        """ensure_schema should create all expected tables."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' ORDER BY name;"
            )
            tables = {row["name"] for row in cur.fetchall()}

            assert "notes" in tables or "notes_fts" in tables
            assert "notes" in tables
            assert "relationships" in tables
            assert "tags" in tables
            assert "schema_version" in tables
        finally:
            conn.close()

    def test_schema_creates_indexes(self, tmp_path):
        """ensure_schema should create expected indexes."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name LIKE 'idx_%' ORDER BY name;"
            )
            indexes = {row["name"] for row in cur.fetchall()}

            assert "idx_relationships_source" in indexes
            assert "idx_relationships_target" in indexes
            assert "idx_relationships_type" in indexes
            assert "idx_tags_note" in indexes
            assert "idx_tags_tag" in indexes
            assert "idx_notes_path" in indexes
        finally:
            conn.close()

    def test_schema_idempotent(self, tmp_path):
        """Calling ensure_schema multiple times should not raise errors."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)
            ensure_schema(conn)
            ensure_schema(conn)
        finally:
            conn.close()

    def test_schema_records_version(self, tmp_path):
        """ensure_schema should record the schema version."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute(
                "SELECT MAX(version) FROM schema_version;"
            )
            assert cur.fetchone()[0] == SCHEMA_VERSION
        finally:
            conn.close()

    def test_notes_table_columns(self, tmp_path):
        """notes table should have the expected columns."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute("PRAGMA table_info(notes);")
            columns = {row["name"]: row for row in cur.fetchall()}

            assert "id" in columns
            assert columns["id"]["pk"] == 1

            assert "path" in columns
            assert columns["path"]["notnull"]

            assert "title" in columns
            assert "created_at" in columns
            assert "updated_at" in columns
        finally:
            conn.close()

    def test_relationships_table_columns(self, tmp_path):
        """relationships table should have the expected columns."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute("PRAGMA table_info(relationships);")
            columns = {row["name"]: row for row in cur.fetchall()}

            assert "id" in columns
            assert "source_id" in columns
            assert "target_id" in columns
            assert "relationship_type" in columns
            assert "created_at" in columns

            conn.execute(
                "INSERT INTO notes (id, path) VALUES ('n1', '/a.md'), ('n2', '/b.md');"
            )
            conn.commit()

            conn.execute(
                "INSERT INTO relationships (source_id, target_id, relationship_type) "
                "VALUES ('n1', 'n2', 'RELATED_TO');"
            )
            conn.commit()

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO relationships (source_id, target_id, relationship_type) "
                    "VALUES ('n1', 'n2', 'RELATED_TO');"
                )
                conn.commit()
        finally:
            conn.close()

    def test_tags_table_columns(self, tmp_path):
        """tags table should have the expected columns."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            cur = conn.execute("PRAGMA table_info(tags);")
            columns = {row["name"]: row for row in cur.fetchall()}

            assert "id" in columns
            assert "note_id" in columns
            assert columns["note_id"]["notnull"]
            assert "tag" in columns
            assert columns["tag"]["notnull"]
        finally:
            conn.close()

    def test_foreign_key_enforcement(self, tmp_path):
        """Foreign key constraints should be enforced."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO relationships (source_id, target_id, relationship_type) "
                    "VALUES ('nonexistent', 'also-nonexistent', 'RELATED_TO');"
                )
                conn.commit()
        finally:
            conn.close()

    def test_notes_unique_path(self, tmp_path):
        """notes.path column should have a UNIQUE constraint."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            conn.execute(
                "INSERT INTO notes (id, path, title) VALUES ('n1', '/a.md', 'A');"
            )
            conn.commit()

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO notes (id, path, title) VALUES ('n2', '/a.md', 'A2');"
                )
                conn.commit()
        finally:
            conn.close()

    def test_tags_unique_per_note(self, tmp_path):
        """tags should be unique per note."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            conn.execute(
                "INSERT INTO notes (id, path) VALUES ('n1', '/a.md');"
            )
            conn.commit()

            conn.execute(
                "INSERT INTO tags (note_id, tag) VALUES ('n1', 'robotics');"
            )
            conn.commit()

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO tags (note_id, tag) VALUES ('n1', 'robotics');"
                )
                conn.commit()
        finally:
            conn.close()

    def test_cascade_delete_relationships(self, tmp_path):
        """Deleting a note should cascade delete its relationships."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            conn.execute(
                "INSERT INTO notes (id, path) VALUES ('n1', '/a.md'), ('n2', '/b.md');"
            )
            conn.execute(
                "INSERT INTO relationships (source_id, target_id, relationship_type) "
                "VALUES ('n1', 'n2', 'RELATED_TO');"
            )
            conn.commit()

            conn.execute("DELETE FROM notes WHERE id = 'n1';")
            conn.commit()

            cur = conn.execute("SELECT COUNT(*) FROM relationships;")
            assert cur.fetchone()[0] == 0
        finally:
            conn.close()

    def test_cascade_delete_tags(self, tmp_path):
        """Deleting a note should cascade delete its tags."""
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)

            conn.execute(
                "INSERT INTO notes (id, path) VALUES ('n1', '/a.md');"
            )
            conn.execute(
                "INSERT INTO tags (note_id, tag) VALUES ('n1', 'robotics');"
            )
            conn.commit()

            conn.execute("DELETE FROM notes WHERE id = 'n1';")
            conn.commit()

            cur = conn.execute("SELECT COUNT(*) FROM tags;")
            assert cur.fetchone()[0] == 0
        finally:
            conn.close()


class TestInitDb:
    """Tests for the convenience init_db function."""

    def test_init_db_returns_connection(self, tmp_path):
        """init_db should return an open connection."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        try:
            assert isinstance(conn, sqlite3.Connection)
        finally:
            conn.close()

    def test_init_db_creates_schema(self, tmp_path):
        """init_db should create the schema."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' ORDER BY name;"
            )
            tables = {row["name"] for row in cur.fetchall()}
            assert "notes" in tables
            assert "relationships" in tables
            assert "tags" in tables
        finally:
            conn.close()

    def test_init_db_idempotent(self, tmp_path):
        """Calling init_db multiple times should be safe."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        conn.close()

        conn2 = init_db(db_path)
        conn2.close()


# ===========================================================================
# New tests: note CRUD
# ===========================================================================


class TestUpsertNote:
    """Tests for upserting notes into the database."""

    def test_upsert_new_note(self, db_conn, sample_note):
        """Inserting a new note should succeed."""
        note_id = upsert_note(db_conn, sample_note)
        assert note_id == sample_note.id

        saved = get_note_by_id(db_conn, note_id)
        assert saved is not None
        assert saved["id"] == sample_note.id
        assert saved["title"] == "Test Note"
        assert str(sample_note.path) in saved["path"]

    def test_upsert_note_updates_existing(self, db_conn, sample_note):
        """Upserting an existing note by path should update title."""
        upsert_note(db_conn, sample_note)

        updated = Note(
            path=sample_note.path,
            content="# Updated",
            title="Updated Title",
            id=sample_note.id,
            created_at=sample_note.created_at,
            updated_at=datetime(2026, 6, 10, 13, 0, 0),
        )
        upsert_note(db_conn, updated)

        saved = get_note_by_id(db_conn, sample_note.id)
        assert saved["title"] == "Updated Title"

    def test_upsert_note_preserves_id_on_path_conflict(self, db_conn, sample_note):
        """Upserting with same path but different ID should preserve original ID."""
        upsert_note(db_conn, sample_note)

        # Same path, different ID — should update the existing row but keep original ID
        note2 = Note(
            path=sample_note.path,
            content="# Another",
            title="Another Note",
            id="note-999",
            created_at=datetime(2026, 6, 10, 14, 0, 0),
            updated_at=datetime(2026, 6, 10, 14, 0, 0),
        )
        upsert_note(db_conn, note2)

        # The original note's ID should be preserved (not replaced)
        saved = get_note_by_id(db_conn, sample_note.id)
        assert saved is not None
        assert saved["title"] == "Another Note"
        assert saved["id"] == sample_note.id


class TestNoteQueries:
    """Tests for note query functions."""

    def test_get_note_by_id_not_found(self, db_conn):
        """get_note_by_id should return None for missing note."""
        result = get_note_by_id(db_conn, "nonexistent")
        assert result is None

    def test_get_note_by_id_found(self, db_conn, sample_note):
        """get_note_by_id should return the correct note."""
        upsert_note(db_conn, sample_note)
        result = get_note_by_id(db_conn, sample_note.id)
        assert result is not None
        assert result["id"] == sample_note.id
        assert result["title"] == "Test Note"

    def test_get_note_by_path_found(self, db_conn, sample_note):
        """get_note_by_path should find a note by its path."""
        upsert_note(db_conn, sample_note)
        result = get_note_by_path(db_conn, str(sample_note.path))
        assert result is not None
        assert result["id"] == sample_note.id

    def test_get_note_by_path_not_found(self, db_conn):
        """get_note_by_path should return None for missing path."""
        result = get_note_by_path(db_conn, "/nonexistent.md")
        assert result is None

    def test_get_all_note_ids_empty(self, db_conn):
        """get_all_note_ids should return empty list for empty db."""
        assert get_all_note_ids(db_conn) == []

    def test_get_all_note_ids(self, db_conn, two_notes):
        """get_all_note_ids should return all note IDs."""
        ids = get_all_note_ids(db_conn)
        assert len(ids) == 2
        assert "note-a" in ids
        assert "note-b" in ids

    def test_delete_note_by_id(self, db_conn, sample_note):
        """delete_note_by_id should remove a note."""
        upsert_note(db_conn, sample_note)
        assert delete_note_by_id(db_conn, sample_note.id) is True
        assert get_note_by_id(db_conn, sample_note.id) is None

    def test_delete_note_by_id_not_found(self, db_conn):
        """delete_note_by_id should return False for missing note."""
        assert delete_note_by_id(db_conn, "nonexistent") is False


# ===========================================================================
# New tests: relationship type validation
# ===========================================================================


class TestValidateRelationshipType:
    """Tests for relationship type validation."""

    def test_valid_type_upper(self):
        """Valid uppercase type should be accepted."""
        assert _validate_relationship_type("USES") == "USES"

    def test_valid_type_lower(self):
        """Valid lowercase type should be uppercased."""
        assert _validate_relationship_type("uses") == "USES"

    def test_valid_type_mixed_case(self):
        """Valid mixed-case type should be uppercased."""
        assert _validate_relationship_type("Related_To") == "RELATED_TO"

    def test_invalid_type_raises(self):
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown relationship type"):
            _validate_relationship_type("INVALID_TYPE")

    def test_invalid_type_empty(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown relationship type"):
            _validate_relationship_type("")

    def test_all_relationship_types_valid(self):
        """All relationship type keys should validate successfully."""
        for rel_type in RELATIONSHIP_TYPE_KEYS:
            assert _validate_relationship_type(rel_type.lower()) == rel_type


# ===========================================================================
# New tests: relationship storage
# ===========================================================================


class TestStoreRelationship:
    """Tests for storing individual relationships."""

    def test_store_relationship(self, db_conn, two_notes):
        """A valid relationship should be stored successfully."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 1
        assert rels[0]["source_id"] == note_a
        assert rels[0]["target_id"] == note_b
        assert rels[0]["relationship_type"] == "USES"

    def test_store_relationship_invalid_type(self, db_conn, two_notes):
        """An invalid relationship type should raise ValueError."""
        note_a, note_b = two_notes
        with pytest.raises(ValueError, match="Unknown relationship type"):
            store_relationship(db_conn, note_a, note_b, "NOT_A_TYPE")

    def test_store_relationship_duplicate_silently_ignored(self, db_conn, two_notes):
        """Duplicate (source, target, type) should be silently ignored."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "RELATED_TO")
        store_relationship(db_conn, note_a, note_b, "RELATED_TO")  # Should not raise

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 1

    def test_store_relationship_different_types_allowed(self, db_conn, two_notes):
        """Same notes with different relationship types should be allowed."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")
        store_relationship(db_conn, note_a, note_b, "DEPENDS_ON")

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 2

    def test_store_relationship_reverse_direction(self, db_conn, two_notes):
        """Reversed direction should be stored as a separate relationship."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")
        store_relationship(db_conn, note_b, note_a, "USES")

        rels_a = get_relationships_for_note(db_conn, note_a)
        rels_b = get_relationships_for_note(db_conn, note_b)
        assert len(rels_a) == 2  # outgoing + incoming
        assert len(rels_b) == 2  # incoming + outgoing

    def test_store_relationship_foreign_key_enforced(self, db_conn):
        """Referencing non-existent notes should raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            store_relationship(db_conn, "nonexistent", "also-nonexistent", "USES")

    def test_store_relationship_lowercase_type(self, db_conn, two_notes):
        """Lowercase type should be uppercased automatically."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "related_to")

        rels = get_relationships_for_note(db_conn, note_a)
        assert rels[0]["relationship_type"] == "RELATED_TO"


class TestStoreRelationshipsBulk:
    """Tests for bulk relationship storage."""

    def test_bulk_store(self, db_conn, two_notes):
        """Multiple relationships should be stored in one call."""
        note_a, note_b = two_notes
        store_relationships_bulk(db_conn, [
            (note_a, note_b, "USES"),
            (note_b, note_a, "DEPENDS_ON"),
        ])

        rels_a = get_relationships_for_note(db_conn, note_a)
        assert len(rels_a) == 2

    def test_bulk_store_duplicates_ignored(self, db_conn, two_notes):
        """Duplicate relationships in bulk should be ignored."""
        note_a, note_b = two_notes
        store_relationships_bulk(db_conn, [
            (note_a, note_b, "USES"),
            (note_a, note_b, "USES"),
        ])

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 1

    def test_bulk_store_invalid_type_raises(self, db_conn, two_notes):
        """Invalid type in bulk should raise ValueError."""
        note_a, note_b = two_notes
        with pytest.raises(ValueError, match="Unknown relationship type"):
            store_relationships_bulk(db_conn, [
                (note_a, note_b, "USES"),
                (note_a, note_b, "INVALID_TYPE"),
            ])

    def test_bulk_store_empty_list(self, db_conn):
        """An empty bulk list should not raise an error."""
        store_relationships_bulk(db_conn, [])  # Should not raise


class TestGetRelationshipsForNote:
    """Tests for querying relationships."""

    def test_no_relationships(self, db_conn, sample_note):
        """A note with no relationships should return empty list."""
        upsert_note(db_conn, sample_note)
        rels = get_relationships_for_note(db_conn, sample_note.id)
        assert rels == []

    def test_relationships_includes_outgoing(self, db_conn, two_notes):
        """Should include outgoing relationships."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 1
        assert rels[0]["source_id"] == note_a

    def test_relationships_includes_incoming(self, db_conn, two_notes):
        """Should include incoming relationships."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")

        rels = get_relationships_for_note(db_conn, note_b)
        assert len(rels) == 1
        assert rels[0]["target_id"] == note_b

    def test_relationships_includes_both_directions(self, db_conn, two_notes):
        """Should include both outgoing and incoming."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")
        store_relationship(db_conn, note_b, note_a, "SUPPORTS")

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 2
        types = {r["relationship_type"] for r in rels}
        assert types == {"USES", "SUPPORTS"}


class TestDeleteRelationshipsForNote:
    """Tests for deleting relationships."""

    def test_delete_all_relationships(self, db_conn, two_notes):
        """Deleting relationships for a note should remove all."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")
        store_relationship(db_conn, note_b, note_a, "SUPPORTS")

        delete_relationships_for_note(db_conn, note_a)

        rels = get_relationships_for_note(db_conn, note_a)
        assert len(rels) == 0

    def test_delete_relationships_other_note_unaffected(self, db_conn, two_notes):
        """Deleting relationships for one note should not affect others."""
        note_a, note_b = two_notes
        store_relationship(db_conn, note_a, note_b, "USES")

        delete_relationships_for_note(db_conn, note_a)

        rels_b = get_relationships_for_note(db_conn, note_b)
        assert len(rels_b) == 0  # The relationship is gone entirely

    def test_delete_relationships_nonexistent_note(self, db_conn):
        """Deleting for a non-existent note should not raise."""
        delete_relationships_for_note(db_conn, "nonexistent")  # Should not raise


# ===========================================================================
# New tests: tag storage
# ===========================================================================


class TestStoreTags:
    """Tests for storing tags."""

    def test_store_tags(self, db_conn, sample_note):
        """Tags should be stored correctly."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["robotics", "esp32", "ai"])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == ["ai", "esp32", "robotics"]  # Sorted

    def test_store_tags_replaces_existing(self, db_conn, sample_note):
        """Storing tags should replace all existing tags."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["first", "second"])
        store_tags(db_conn, sample_note.id, ["third"])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == ["third"]

    def test_store_tags_empty_list(self, db_conn, sample_note):
        """An empty tag list should clear all tags."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["robotics"])
        store_tags(db_conn, sample_note.id, [])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == []

    def test_store_tags_duplicates_ignored(self, db_conn, sample_note):
        """Duplicate tags should be silently ignored."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["robotics", "robotics", "esp32"])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == ["esp32", "robotics"]

    def test_store_tags_nonexistent_note_raises(self, db_conn):
        """Storing tags for a non-existent note should raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            store_tags(db_conn, "nonexistent", ["robotics"])

    def test_store_tags_whitespace_ignored(self, db_conn, sample_note):
        """Tags with surrounding whitespace should be stripped."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["  robotics  ", "esp32"])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == ["esp32", "robotics"]


class TestGetTagsForNote:
    """Tests for querying tags."""

    def test_no_tags(self, db_conn, sample_note):
        """A note with no tags should return empty list."""
        upsert_note(db_conn, sample_note)
        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == []

    def test_tags_sorted(self, db_conn, sample_note):
        """Tags should be returned in alphabetical order."""
        upsert_note(db_conn, sample_note)
        store_tags(db_conn, sample_note.id, ["zebra", "alpha", "bravo"])

        tags = get_tags_for_note(db_conn, sample_note.id)
        assert tags == ["alpha", "bravo", "zebra"]


class TestGetAllTags:
    """Tests for getting all tags grouped by note."""

    def test_empty_db(self, db_conn):
        """An empty database should return empty dict."""
        assert get_all_tags(db_conn) == {}

    def test_multiple_notes_with_tags(self, db_conn, two_notes):
        """Tags should be grouped by note ID."""
        note_a, note_b = two_notes
        store_tags(db_conn, note_a, ["tag-a1", "tag-a2"])
        store_tags(db_conn, note_b, ["tag-b1"])

        all_tags = get_all_tags(db_conn)
        assert all_tags[note_a] == ["tag-a1", "tag-a2"]
        assert all_tags[note_b] == ["tag-b1"]

    def test_tags_sorted_per_note(self, db_conn, two_notes):
        """Tags for each note should be sorted."""
        note_a, note_b = two_notes
        store_tags(db_conn, note_a, ["zebra", "apple"])

        all_tags = get_all_tags(db_conn)
        assert all_tags[note_a] == ["apple", "zebra"]


# ===========================================================================
# New tests: note query by title
# ===========================================================================


class TestGetNoteByTitle:
    """Tests for looking up notes by title."""

    def test_get_note_by_title_found(self, db_conn):
        """get_note_by_title should find a note by exact title."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        note = Note(
            path=Path("/vault/notes/my-note.md"),
            content="# My Note",
            title="My Note",
            id="note-title-test",
            created_at=now,
            updated_at=now,
        )
        upsert_note(db_conn, note)

        result = get_note_by_title(db_conn, "My Note")
        assert result is not None
        assert result["id"] == "note-title-test"

    def test_get_note_by_title_case_insensitive(self, db_conn):
        """get_note_by_title should match case-insensitively."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        note = Note(
            path=Path("/vault/notes/project-x.md"),
            content="# Project X",
            title="Project X",
            id="note-case-test",
            created_at=now,
            updated_at=now,
        )
        upsert_note(db_conn, note)

        result = get_note_by_title(db_conn, "project x")
        assert result is not None
        assert result["id"] == "note-case-test"

    def test_get_note_by_title_not_found(self, db_conn):
        """get_note_by_title should return None for nonexistent title."""
        result = get_note_by_title(db_conn, "Nonexistent Note")
        assert result is None

    def test_get_note_by_title_empty_db(self, db_conn):
        """get_note_by_title should return None on empty database."""
        result = get_note_by_title(db_conn, "Anything")
        assert result is None


# ===========================================================================
# New tests: wiki links → relationships
# ===========================================================================


class TestProcessWikiLinks:
    """Tests for converting wiki links into EXPLICIT_LINK relationships."""

    def _make_note(self, title: str, note_id: str, wiki_links: list[str] | None = None) -> Note:
        """Helper to create a Note with wiki links."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        return Note(
            path=Path(f"/vault/notes/{note_id}.md"),
            content=f"# {title}",
            title=title,
            id=note_id,
            wiki_links=wiki_links or [],
            created_at=now,
            updated_at=now,
        )

    def test_process_wiki_links_creates_relationships(self, db_conn):
        """Wiki links to existing notes should create EXPLICIT_LINK relationships."""
        # Set up: note A links to note B and note C
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        note_a = self._make_note("Note A", "note-a", wiki_links=["Note B", "Note C"])
        upsert_note(db_conn, note_a)

        # Process wiki links
        stored = process_wiki_links(db_conn, note_a)

        # Verify relationships were created
        assert len(stored) == 2
        assert stored[0] == ("note-a", "note-b", "EXPLICIT_LINK")
        assert stored[1] == ("note-a", "note-c", "EXPLICIT_LINK")

        # Verify via query
        rels = get_relationships_for_note(db_conn, "note-a")
        assert len(rels) == 2
        types = {r["relationship_type"] for r in rels}
        assert types == {"EXPLICIT_LINK"}

    def test_process_wiki_links_skips_missing_targets(self, db_conn):
        """Wiki links to non-existent notes should be silently skipped."""
        note_a = self._make_note("Note A", "note-a", wiki_links=["Missing Note"])
        upsert_note(db_conn, note_a)

        stored = process_wiki_links(db_conn, note_a)

        # No relationship should have been created
        assert stored == []
        rels = get_relationships_for_note(db_conn, "note-a")
        assert rels == []

    def test_process_wiki_links_empty_links(self, db_conn):
        """Empty wiki links should result in no relationships."""
        note_a = self._make_note("Note A", "note-a", wiki_links=[])
        upsert_note(db_conn, note_a)

        stored = process_wiki_links(db_conn, note_a)
        assert stored == []

    def test_process_wiki_links_replaces_existing(self, db_conn):
        """Re-processing should replace old EXPLICIT_LINK relationships."""
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        note_a = self._make_note("Note A", "note-a", wiki_links=["Note B", "Note C"])
        upsert_note(db_conn, note_a)

        # First pass: create both links
        stored1 = process_wiki_links(db_conn, note_a)
        assert len(stored1) == 2

        # Change wiki links and re-process
        note_a2 = self._make_note("Note A", "note-a", wiki_links=["Note B"])
        stored2 = process_wiki_links(db_conn, note_a2)

        # Should only have one relationship now (Note B)
        assert len(stored2) == 1
        assert stored2[0] == ("note-a", "note-b", "EXPLICIT_LINK")

        rels = get_relationships_for_note(db_conn, "note-a")
        assert len(rels) == 1
        assert rels[0]["target_id"] == "note-b"

    def test_process_wiki_links_preserves_other_relationships(self, db_conn):
        """Other relationship types should not be affected by wiki link processing."""
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        note_a = self._make_note("Note A", "note-a", wiki_links=["Note B"])
        upsert_note(db_conn, note_a)

        # Add a non-wiki relationship
        store_relationship(db_conn, "note-a", "note-c", "USES")

        # Process wiki links
        process_wiki_links(db_conn, note_a)

        rels = get_relationships_for_note(db_conn, "note-a")
        assert len(rels) == 2
        types = {r["relationship_type"] for r in rels}
        assert types == {"EXPLICIT_LINK", "USES"}

    def test_process_wiki_links_case_insensitive_target(self, db_conn):
        """Wiki link lookup should be case-insensitive."""
        note_b = self._make_note("Project X", "note-b")
        upsert_note(db_conn, note_b)

        note_a = self._make_note("Note A", "note-a", wiki_links=["project x"])
        upsert_note(db_conn, note_a)

        stored = process_wiki_links(db_conn, note_a)
        assert len(stored) == 1
        assert stored[0] == ("note-a", "note-b", "EXPLICIT_LINK")


# ===========================================================================
# New tests: relationship type keys constant
# ===========================================================================


class TestRelationshipTypeKeys:
    """Tests for the RELATIONSHIP_TYPE_KEYS constant."""

    def test_all_types_are_uppercase(self):
        """All relationship type keys should be uppercase."""
        for rel_type in RELATIONSHIP_TYPE_KEYS:
            assert rel_type == rel_type.upper(), f"Not uppercase: {rel_type}"

    def test_all_types_are_unique(self):
        """All relationship type keys should be unique."""
        assert len(RELATIONSHIP_TYPE_KEYS) == len(set(RELATIONSHIP_TYPE_KEYS))

    def test_has_expected_types(self):
        """Should contain the core relationship types."""
        assert "USES" in RELATIONSHIP_TYPE_KEYS
        assert "RELATED_TO" in RELATIONSHIP_TYPE_KEYS
        assert "DEPENDS_ON" in RELATIONSHIP_TYPE_KEYS
        assert "EXPLICIT_LINK" in RELATIONSHIP_TYPE_KEYS
        assert "INFERRED_LINK" in RELATIONSHIP_TYPE_KEYS
        assert "PART_OF" in RELATIONSHIP_TYPE_KEYS


# ===========================================================================
# New tests: relationship query API (Story 3.4)
# ===========================================================================


class TestGetRelatedNotes:
    """Tests for the high-level relationship query API."""

    def _make_note(self, title: str, note_id: str) -> Note:
        """Helper to create a simple Note."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        return Note(
            path=Path(f"/vault/notes/{note_id}.md"),
            content=f"# {title}",
            title=title,
            id=note_id,
            created_at=now,
            updated_at=now,
        )

    # ── No relationships ────────────────────────────────────────────────

    def test_no_relationships(self, db_conn):
        """A note with no relationships should return empty list."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        note = Note(
            path=Path("/vault/notes/solo.md"),
            content="# Solo",
            title="Solo",
            id="solo",
            created_at=now,
            updated_at=now,
        )
        upsert_note(db_conn, note)

        related = get_related_notes(db_conn, "solo")
        assert related == []

    # ── Outgoing ────────────────────────────────────────────────────────

    def test_outgoing_relationships(self, db_conn):
        """Should return related notes for outgoing edges."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-a", "note-b", "USES")
        store_relationship(db_conn, "note-a", "note-c", "USES")

        related = get_related_notes(db_conn, "note-a", direction="outgoing")
        assert len(related) == 2
        for r in related:
            assert r["source_id"] == "note-a"
            assert r["relationship_type"] == "USES"

        titles = {r["related_title"] for r in related}
        assert titles == {"Note B", "Note C"}

    # ── Incoming ────────────────────────────────────────────────────────

    def test_incoming_relationships(self, db_conn):
        """Should return related notes for incoming edges."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-b", "note-a", "REFERENCES")
        store_relationship(db_conn, "note-c", "note-a", "REFERENCES")

        related = get_related_notes(db_conn, "note-a", direction="incoming")
        assert len(related) == 2
        for r in related:
            assert r["target_id"] == "note-a"
            assert r["relationship_type"] == "REFERENCES"

    # ── Both directions ─────────────────────────────────────────────────

    def test_both_directions(self, db_conn):
        """Should return outgoing and incoming relationships."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-a", "note-b", "USES")       # outgoing
        store_relationship(db_conn, "note-c", "note-a", "REFERENCES")  # incoming

        related = get_related_notes(db_conn, "note-a", direction="both")
        assert len(related) == 2

        types = {(r["source_id"], r["relationship_type"]) for r in related}
        assert ("note-a", "USES") in types
        assert ("note-c", "REFERENCES") in types

    # ── Default direction ───────────────────────────────────────────────

    def test_default_direction_is_both(self, db_conn):
        """Default direction should be 'both'."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)

        store_relationship(db_conn, "note-a", "note-b", "USES")

        related = get_related_notes(db_conn, "note-a")  # No direction arg
        assert len(related) == 1

    # ── Relationship type filter ────────────────────────────────────────

    def test_filter_by_relationship_type(self, db_conn):
        """Should filter results to a specific relationship type."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-a", "note-b", "USES")
        store_relationship(db_conn, "note-a", "note-c", "DEPENDS_ON")

        related = get_related_notes(
            db_conn, "note-a", relationship_type="USES"
        )
        assert len(related) == 1
        assert related[0]["target_id"] == "note-b"
        assert related[0]["relationship_type"] == "USES"

    def test_filter_by_type_case_insensitive(self, db_conn):
        """Type filter should be case-insensitive."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)

        store_relationship(db_conn, "note-a", "note-b", "RELATED_TO")

        related = get_related_notes(
            db_conn, "note-a", relationship_type="related_to"
        )
        assert len(related) == 1
        assert related[0]["relationship_type"] == "RELATED_TO"

    def test_filter_no_match(self, db_conn):
        """Filtering by a type with no matches should return empty list."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)

        store_relationship(db_conn, "note-a", "note-b", "USES")

        related = get_related_notes(
            db_conn, "note-a", relationship_type="DEPENDS_ON"
        )
        assert related == []

    def test_filter_invalid_type_raises(self, db_conn):
        """Invalid relationship type should raise ValueError."""
        note_a = self._make_note("Note A", "note-a")
        upsert_note(db_conn, note_a)

        with pytest.raises(ValueError, match="Unknown relationship type"):
            get_related_notes(
                db_conn, "note-a", relationship_type="NOT_A_TYPE"
            )

    # ── Direction and type combined ─────────────────────────────────────

    def test_filter_by_type_and_direction(self, db_conn):
        """Should combine type and direction filters."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Note B", "note-b")
        note_c = self._make_note("Note C", "note-c")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-a", "note-b", "USES")
        store_relationship(db_conn, "note-a", "note-c", "DEPENDS_ON")
        store_relationship(db_conn, "note-c", "note-a", "REFERENCES")

        related = get_related_notes(
            db_conn, "note-a",
            direction="outgoing",
            relationship_type="USES",
        )
        assert len(related) == 1
        assert related[0]["target_id"] == "note-b"

    # ── Related note details ────────────────────────────────────────────

    def test_related_note_details(self, db_conn):
        """Should include title and path of related notes."""
        note_a = self._make_note("Source Note", "source")
        note_b = self._make_note("Target Note", "target")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)

        store_relationship(db_conn, "source", "target", "USES")

        related = get_related_notes(db_conn, "source")
        assert len(related) == 1
        r = related[0]
        assert r["related_note_id"] == "target"
        assert r["related_title"] == "Target Note"
        assert "target" in r["related_path"]

    # ── Invalid direction ───────────────────────────────────────────────

    def test_invalid_direction_raises(self, db_conn):
        """Invalid direction should raise ValueError."""
        note_a = self._make_note("Note A", "note-a")
        upsert_note(db_conn, note_a)

        with pytest.raises(ValueError, match="Invalid direction"):
            get_related_notes(db_conn, "note-a", direction="sideways")

    # ── Results are sorted ──────────────────────────────────────────────

    def test_results_sorted(self, db_conn):
        """Results should be sorted by relationship type then title."""
        note_a = self._make_note("Note A", "note-a")
        note_b = self._make_note("Zebra Note", "note-zebra")
        note_c = self._make_note("Alpha Note", "note-alpha")
        upsert_note(db_conn, note_a)
        upsert_note(db_conn, note_b)
        upsert_note(db_conn, note_c)

        store_relationship(db_conn, "note-a", "note-zebra", "USES")
        store_relationship(db_conn, "note-a", "note-alpha", "SUPPORTS")

        related = get_related_notes(db_conn, "note-a")
        assert len(related) == 2
        # SUPPORTS before USES, then by title within each type
        assert related[0]["relationship_type"] == "SUPPORTS"
        assert related[1]["relationship_type"] == "USES"


# ===========================================================================
# New tests: full-text search (Story 4.1)
# ===========================================================================


class TestIndexNoteFts:
    """Tests for indexing notes in the FTS5 full-text index."""

    def _insert_note(self, db_conn, note_id: str, title: str, body: str) -> None:
        """Helper: insert a note row directly into the notes table."""
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES (?, ?, ?)",
            (note_id, f"/vault/notes/{note_id}.md", title),
        )
        db_conn.commit()

    def test_index_note_fts(self, db_conn):
        """Indexing a note should make it searchable."""
        self._insert_note(db_conn, "n1", "Test Note", "Hello world content")
        index_note_fts(db_conn, "n1", "Test Note", "Hello world content")

        results = search_notes(db_conn, "Hello")
        assert len(results) == 1
        assert results[0]["note_id"] == "n1"

    def test_index_note_fts_replaces_existing(self, db_conn):
        """Re-indexing should replace the FTS entry."""
        self._insert_note(db_conn, "n1", "Test Note", "Hello world")
        index_note_fts(db_conn, "n1", "Test Note", "Hello world")
        index_note_fts(db_conn, "n1", "Test Note", "Replaced content")

        results = search_notes(db_conn, "Replaced")
        assert len(results) == 1

    def test_index_note_fts_search_by_title(self, db_conn):
        """Title field should be searchable."""
        self._insert_note(db_conn, "n1", "ESP32 Guide", "Technical content")
        index_note_fts(db_conn, "n1", "ESP32 Guide", "Technical content")

        results = search_notes(db_conn, "ESP32")
        assert len(results) == 1
        assert results[0]["title"] == "ESP32 Guide"

    def test_index_note_fts_no_match(self, db_conn):
        """Search with no matches should return empty list."""
        self._insert_note(db_conn, "n1", "Test", "Content")
        index_note_fts(db_conn, "n1", "Test", "Content")

        results = search_notes(db_conn, "nonexistent")
        assert results == []


class TestDeleteNoteFts:
    """Tests for removing notes from the FTS index."""

    def test_delete_note_fts_removes_entry(self, db_conn):
        """Deleting an FTS entry should remove it from search results."""
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES ('n1', '/vault/notes/n1.md', 'Searchable')"
        )
        db_conn.commit()
        index_note_fts(db_conn, "n1", "Searchable", "Some content")

        # Verify it's searchable
        assert len(search_notes(db_conn, "Searchable")) == 1

        # Delete from FTS
        delete_note_fts(db_conn, "n1")
        results = search_notes(db_conn, "Searchable")
        assert results == []

    def test_delete_note_fts_nonexistent(self, db_conn):
        """Deleting a non-existent FTS entry should not raise."""
        delete_note_fts(db_conn, "nonexistent")  # Should not raise


class TestRebuildFtsIndex:
    """Tests for rebuilding the full FTS index."""

    def _make_note(self, note_id: str, title: str, body: str):
        """Helper to create a Note object."""
        from datetime import datetime
        return Note(
            path=Path(f"/vault/notes/{note_id}.md"),
            content=body,
            title=title,
            body=body,
            id=note_id,
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )

    def test_rebuild_fts_index(self, db_conn):
        """Rebuilding should index all provided notes."""
        notes = [
            self._make_note("n1", "Alpha", "Alpha content"),
            self._make_note("n2", "Beta", "Beta content"),
        ]
        for n in notes:
            db_conn.execute(
                "INSERT INTO notes (id, path, title) VALUES (?, ?, ?)",
                (n.id, str(n.path), n.title),
            )
        db_conn.commit()

        rebuild_fts_index(db_conn, notes)

        results = search_notes(db_conn, "content")
        assert len(results) == 2

    def test_rebuild_fts_index_replaces_old(self, db_conn):
        """Rebuilding should replace all existing FTS entries."""
        # Insert old note
        self._make_note("old", "Old Note", "Old content")
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES ('old', '/vault/notes/old.md', 'Old Note')"
        )
        db_conn.commit()
        index_note_fts(db_conn, "old", "Old Note", "Old content")

        # Rebuild with just one new note
        new_note = self._make_note("new", "New Note", "New content")
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES ('new', '/vault/notes/new.md', 'New Note')"
        )
        db_conn.commit()
        rebuild_fts_index(db_conn, [new_note])

        # Old note should no longer be searchable
        old_results = search_notes(db_conn, "Old")
        assert old_results == []

        # New note should be searchable
        new_results = search_notes(db_conn, "New")
        assert len(new_results) == 1

    def test_rebuild_fts_index_empty(self, db_conn):
        """Rebuilding with empty list should clear the index."""
        rebuild_fts_index(db_conn, [])
        results = search_notes(db_conn, "anything")
        assert results == []


class TestSearchNotes:
    """Tests for the search_notes function."""

    def _setup(self, db_conn):
        """Helper: insert and index two notes."""
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES "
            "('n1', '/vault/notes/n1.md', 'Robotics Project'), "
            "('n2', '/vault/notes/n2.md', 'ESP32 Guide')"
        )
        db_conn.commit()
        index_note_fts(db_conn, "n1", "Robotics Project", "Building a robot with ESP32")
        index_note_fts(db_conn, "n2", "ESP32 Guide", "Complete guide to ESP32 microcontrollers")

    def test_search_basic(self, db_conn):
        """Basic keyword search should return matching notes."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32")
        assert len(results) == 2

    def test_search_limit(self, db_conn):
        """Search should respect the limit parameter."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32", limit=1)
        assert len(results) == 1

    def test_search_default_limit(self, db_conn):
        """Default limit should be 20."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32")
        assert len(results) <= 20

    def test_search_returns_rank(self, db_conn):
        """Results should include a rank (relevance score)."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32")
        for r in results:
            assert "rank" in r
            # rank is a float (lower = more relevant)
            assert isinstance(r["rank"], float)

    def test_search_results_ordered_by_relevance(self, db_conn):
        """Results should be ordered by rank (most relevant first)."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32")
        assert len(results) >= 2
        # n2 (ESP32 Guide) should rank higher for "ESP32" than n1 (Robotics Project)
        assert results[0]["note_id"] == "n2"
        assert results[0]["rank"] <= results[1]["rank"]

    def test_search_returns_note_details(self, db_conn):
        """Results should include note_id, title, path."""
        self._setup(db_conn)
        results = search_notes(db_conn, "ESP32")
        r = results[0]
        assert "note_id" in r
        assert "title" in r
        assert "path" in r
        assert r["note_id"] == "n2"
        assert r["title"] == "ESP32 Guide"

    def test_search_no_results(self, db_conn):
        """Search with no matches should return empty list."""
        self._setup(db_conn)
        results = search_notes(db_conn, "nonexistent")
        assert results == []

    def test_search_empty_query(self, db_conn):
        """Empty query should return empty list."""
        self._setup(db_conn)
        results = search_notes(db_conn, "")
        assert results == []

    def test_search_empty_index(self, db_conn):
        """Search on empty index should return empty list."""
        # No notes indexed
        results = search_notes(db_conn, "anything")
        assert results == []

    def test_search_fts5_syntax(self, db_conn):
        """FTS5 query syntax should work (prefix queries)."""
        self._setup(db_conn)
        # FTS5 prefix query: "Gui*" matches "Guide"
        results = search_notes(db_conn, "Gui*")
        assert len(results) == 1
        assert results[0]["title"] == "ESP32 Guide"

    def test_search_case_insensitive(self, db_conn):
        """FTS5 search should be case-insensitive."""
        self._setup(db_conn)
        results = search_notes(db_conn, "esp32")
        assert len(results) == 2


# ===========================================================================
# New tests: access tracking (Story 4.3)
# ===========================================================================


class TestAccessTracking:
    """Tests for the access count feature."""

    def _insert_note(self, db_conn, note_id: str, title: str):
        """Helper to insert a note."""
        db_conn.execute(
            "INSERT INTO notes (id, path, title) VALUES (?, ?, ?)",
            (note_id, f"/vault/notes/{note_id}.md", title),
        )
        db_conn.commit()

    def test_increment_access_count(self, db_conn):
        """Incrementing access count should increase the counter."""
        self._insert_note(db_conn, "n1", "Test Note")
        assert get_access_count(db_conn, "n1") == 0

        increment_access_count(db_conn, "n1")
        assert get_access_count(db_conn, "n1") == 1

        increment_access_count(db_conn, "n1")
        assert get_access_count(db_conn, "n1") == 2

    def test_get_access_count_nonexistent(self, db_conn):
        """Getting access count for a non-existent note should return 0."""
        assert get_access_count(db_conn, "nonexistent") == 0

    def test_increment_access_count_nonexistent(self, db_conn):
        """Incrementing for a non-existent note should not raise (no-op)."""
        increment_access_count(db_conn, "nonexistent")
        # No rows affected, should silently do nothing

    def test_access_count_default_zero(self, db_conn):
        """New notes should have an access count of 0."""
        self._insert_note(db_conn, "n1", "Fresh Note")
        assert get_access_count(db_conn, "n1") == 0

    def test_notes_table_has_access_count_column(self, tmp_path):
        """The notes table should have an access_count column."""
        from bfai.db import connect, ensure_schema
        db_path = tmp_path / "test.db"
        conn = connect(db_path)
        try:
            ensure_schema(conn)
            cur = conn.execute("PRAGMA table_info(notes);")
            columns = {row["name"]: row for row in cur.fetchall()}
            assert "access_count" in columns
            assert columns["access_count"]["dflt_value"] == "0"
        finally:
            conn.close()


# ===========================================================================
# New tests: ranked search (Story 4.3)
# ===========================================================================


class TestRankedSearch:
    """Tests for the multi-factor ranked search function."""

    def _setup(self, db_conn, notes_data: list[dict]) -> None:
        """Insert and index multiple notes from a list of dicts with keys:
        id, path, title, body, updated_at (str), access_count (int).
        """
        for nd in notes_data:
            db_conn.execute(
                """INSERT INTO notes (id, path, title, updated_at, access_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (nd["id"], nd["path"], nd["title"],
                 nd.get("updated_at"), nd.get("access_count", 0)),
            )
            index_note_fts(db_conn, nd["id"], nd["title"], nd["body"])
        db_conn.commit()

    def test_ranked_search_returns_results(self, db_conn):
        """ranked_search should return matching notes."""
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Alpha", body="Content about alpha"),
        ])
        results = ranked_search(db_conn, "alpha")
        assert len(results) == 1
        assert results[0]["note_id"] == "n1"

    def test_ranked_search_no_results(self, db_conn):
        """ranked_search with no matches should return empty list."""
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Alpha", body="Content"),
        ])
        results = ranked_search(db_conn, "nonexistent")
        assert results == []

    def test_ranked_search_includes_score_fields(self, db_conn):
        """Results should include all ranking score fields."""
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Alpha", body="Content about alpha"),
        ])
        results = ranked_search(db_conn, "alpha")
        r = results[0]
        assert "note_id" in r
        assert "title" in r
        assert "path" in r
        assert "rank" in r
        assert "recency_score" in r
        assert "access_score" in r
        assert "importance_score" in r
        assert "combined_score" in r

    def test_ranked_search_scores_are_in_range(self, db_conn):
        """Score fields should be in valid [0, 1] range."""
        now_str = "2026-06-11T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Alpha Note",
                 body="Content about alpha", updated_at=now_str, access_count=5),
        ])
        results = ranked_search(db_conn, "alpha")
        r = results[0]
        assert 0.0 <= r["recency_score"] <= 1.0
        assert 0.0 <= r["access_score"] <= 1.0
        assert 0.0 <= r["importance_score"] <= 1.0
        assert 0.0 <= r["combined_score"] <= 1.0

    def test_ranked_search_orders_by_combined_score(self, db_conn):
        """Results should be ordered by combined_score descending."""
        now_str = "2026-06-11T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Alpha",
                 body="ESP32 guide and tutorial", updated_at=now_str, access_count=0),
            dict(id="n2", path="/v/notes/b.md", title="Better esp32 Guide",
                 body="ESP32 comprehensive guide", updated_at=now_str, access_count=10),
        ])
        results = ranked_search(db_conn, "ESP32")
        assert len(results) == 2
        # Higher combined_score should be first
        assert results[0]["combined_score"] >= results[1]["combined_score"]

    def test_ranked_search_recency_boost(self, db_conn):
        """Recently updated notes should get a recency boost."""
        recent = "2026-06-11T12:00:00"  # today
        old = "2025-01-01T12:00:00"     # over a year ago

        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Old Note",
                 body="ESP32 content here", updated_at=old, access_count=0),
            dict(id="n2", path="/v/notes/b.md", title="Recent Note",
                 body="ESP32 content here too", updated_at=recent, access_count=0),
        ])
        results = ranked_search(db_conn, "ESP32")
        assert len(results) == 2
        # The recently updated note should have a higher recency_score
        recent_result = next(r for r in results if r["note_id"] == "n2")
        old_result = next(r for r in results if r["note_id"] == "n1")
        assert recent_result["recency_score"] > old_result["recency_score"]

    def test_ranked_search_access_boost(self, db_conn):
        """More frequently accessed notes should get an access boost."""
        now_str = "2026-06-11T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Popular Note",
                 body="ESP32 content here", updated_at=now_str, access_count=50),
            dict(id="n2", path="/v/notes/b.md", title="Unpopular Note",
                 body="ESP32 content here too", updated_at=now_str, access_count=0),
        ])
        results = ranked_search(db_conn, "ESP32")
        assert len(results) == 2
        popular = next(r for r in results if r["note_id"] == "n1")
        unpopular = next(r for r in results if r["note_id"] == "n2")
        assert popular["access_score"] > unpopular["access_score"]

    def test_ranked_search_limit(self, db_conn):
        """ranked_search should respect the limit."""
        now_str = "2026-06-11T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Note A",
                 body="ESP32", updated_at=now_str, access_count=0),
            dict(id="n2", path="/v/notes/b.md", title="Note B",
                 body="ESP32", updated_at=now_str, access_count=0),
        ])
        results = ranked_search(db_conn, "ESP32", limit=1)
        assert len(results) == 1

    def test_ranked_search_importance_signal(self, db_conn):
        """Longer titles should get a higher importance score."""
        now_str = "2026-06-11T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md",
                 title="Short Title", body="ESP32 content",
                 updated_at=now_str, access_count=0),
            dict(id="n2", path="/v/notes/b.md",
                 title="A Much Longer and More Detailed Title Here",
                 body="ESP32 content", updated_at=now_str, access_count=0),
        ])
        results = ranked_search(db_conn, "ESP32")
        assert len(results) == 2
        long = next(r for r in results if r["note_id"] == "n2")
        short = next(r for r in results if r["note_id"] == "n1")
        assert long["importance_score"] >= short["importance_score"]

    def test_ranked_search_ranking_weights_defined(self):
        """Ranking weight constants should be properly defined."""
        total = (RANK_WEIGHT_TEXT + RANK_WEIGHT_IMPORTANCE +
                 RANK_WEIGHT_RECENCY + RANK_WEIGHT_ACCESS +
                 RANK_WEIGHT_RESERVED)
        # Weights should sum to 1.0, but with floating point we check approx
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"
        assert RANK_WEIGHT_TEXT == 0.40
        assert RANK_WEIGHT_IMPORTANCE == 0.20
        assert RANK_WEIGHT_RECENCY == 0.10
        assert RANK_WEIGHT_ACCESS == 0.10
        assert RANK_WEIGHT_RESERVED == 0.20

    def test_ranked_search_with_now_param(self, db_conn):
        """The now parameter should control recency calculation."""
        from datetime import datetime, timezone
        # Note updated 10 days ago
        ten_days_ago = "2026-06-01T12:00:00"
        self._setup(db_conn, [
            dict(id="n1", path="/v/notes/a.md", title="Test",
                 body="ESP32 content", updated_at=ten_days_ago, access_count=0),
        ])
        # Reference time = 10 days after the update
        ref_now = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
        results = ranked_search(db_conn, "ESP32", now=ref_now)
        assert len(results) == 1
        # 10 days / 30-day half-life => score = exp(-10*ln(2)/30) ≈ 0.7937
        assert abs(results[0]["recency_score"] - 0.7937) < 0.01

    def test_ranked_search_empty_query(self, db_conn):
        """Empty query should return empty list."""
        results = ranked_search(db_conn, "")
        assert results == []

    def test_ranked_search_empty_index(self, db_conn):
        """Searching empty index should return empty list."""
        results = ranked_search(db_conn, "anything")
        assert results == []


# ===========================================================================
# New tests: backlinks (Story 5.1)
# ===========================================================================


class TestGetBacklinks:
    """Tests for the get_backlinks function."""

    def _make_note(self, title: str, note_id: str) -> Note:
        """Helper to create a simple Note."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        return Note(
            path=Path(f"/vault/notes/{note_id}.md"),
            content=f"# {title}",
            title=title,
            id=note_id,
            created_at=now,
            updated_at=now,
        )

    def test_no_backlinks(self, db_conn):
        """A note with no backlinks should return empty list."""
        note = self._make_note("Solo Note", "solo")
        upsert_note(db_conn, note)

        result = get_backlinks(db_conn, "solo")
        assert result == []

    def test_backlinks_basic(self, db_conn):
        """Should return notes that link to the given note."""
        target = self._make_note("Target Note", "target")
        source_a = self._make_note("Source A", "src-a")
        source_b = self._make_note("Source B", "src-b")
        upsert_note(db_conn, target)
        upsert_note(db_conn, source_a)
        upsert_note(db_conn, source_b)

        store_relationship(db_conn, "src-a", "target", "EXPLICIT_LINK")
        store_relationship(db_conn, "src-b", "target", "USES")

        result = get_backlinks(db_conn, "target")
        assert len(result) == 2
        titles = {r["related_title"] for r in result}
        assert titles == {"Source A", "Source B"}

    def test_backlinks_does_not_include_outgoing(self, db_conn):
        """Backlinks should not include outgoing relationships."""
        target = self._make_note("Target Note", "target")
        other = self._make_note("Other Note", "other")
        upsert_note(db_conn, target)
        upsert_note(db_conn, other)

        # Target points TO other (outgoing) — should NOT appear as backlink
        store_relationship(db_conn, "target", "other", "REFERENCES")

        result = get_backlinks(db_conn, "target")
        assert result == []

    def test_backlinks_filter_by_type(self, db_conn):
        """Should filter backlinks by relationship type."""
        target = self._make_note("Target", "target")
        src_a = self._make_note("Source A", "src-a")
        src_b = self._make_note("Source B", "src-b")
        upsert_note(db_conn, target)
        upsert_note(db_conn, src_a)
        upsert_note(db_conn, src_b)

        store_relationship(db_conn, "src-a", "target", "EXPLICIT_LINK")
        store_relationship(db_conn, "src-b", "target", "USES")

        # Filter to only EXPLICIT_LINK
        result = get_backlinks(db_conn, "target", relationship_type="EXPLICIT_LINK")
        assert len(result) == 1
        assert result[0]["related_title"] == "Source A"

    def test_backlinks_filter_invalid_type_raises(self, db_conn):
        """Invalid relationship type should raise ValueError."""
        target = self._make_note("Target", "target")
        upsert_note(db_conn, target)

        with pytest.raises(ValueError, match="Unknown relationship type"):
            get_backlinks(db_conn, "target", relationship_type="NOT_A_TYPE")

    def test_backlinks_nonexistent_note(self, db_conn):
        """Querying backlinks for a non-existent note should return empty."""
        result = get_backlinks(db_conn, "nonexistent")
        assert result == []

    def test_backlinks_returns_note_details(self, db_conn):
        """Results should include the backlinking note's title and path."""
        target = self._make_note("Target", "target")
        source = self._make_note("Referencing Note", "ref")
        upsert_note(db_conn, target)
        upsert_note(db_conn, source)

        store_relationship(db_conn, "ref", "target", "MENTIONS")

        result = get_backlinks(db_conn, "target")
        assert len(result) == 1
        r = result[0]
        assert r["related_note_id"] == "ref"
        assert r["related_title"] == "Referencing Note"
        assert "ref" in r["related_path"]
        assert r["relationship_type"] == "MENTIONS"


# ===========================================================================
# New tests: graph expansion (Story 7.2)
# ===========================================================================


class TestExpandGraph:
    """Tests for the expand_graph function."""

    def _make_note(self, title: str, note_id: str) -> Note:
        """Helper to create a simple Note."""
        now = datetime(2026, 6, 10, 12, 0, 0)
        return Note(
            path=Path(f"/vault/notes/{note_id}.md"),
            content=f"# {title}",
            title=title,
            id=note_id,
            created_at=now,
            updated_at=now,
        )

    def _setup_graph(self, db_conn) -> list[str]:
        """Set up a simple graph:
        A --[USES]--> B
        B --[USES]--> C
        C --[RELATED_TO]--> D
        Returns [A, B, C, D] IDs.
        """
        ids = ["note-a", "note-b", "note-c", "note-d"]
        for nid, title in zip(ids, ["Note A", "Note B", "Note C", "Note D"]):
            upsert_note(db_conn, self._make_note(title, nid))

        store_relationship(db_conn, "note-a", "note-b", "USES")
        store_relationship(db_conn, "note-b", "note-c", "USES")
        store_relationship(db_conn, "note-c", "note-d", "RELATED_TO")

        return ids

    def test_expand_zero_hops(self, db_conn):
        """max_hops=0 should return only the seed nodes."""
        ids = self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=0)
        assert len(result) == 1
        assert result[0]["note_id"] == "note-a"
        assert result[0]["hop_depth"] == 0

    def test_expand_one_hop(self, db_conn):
        """max_hops=1 should return seeds + direct neighbors."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=1)
        assert len(result) == 2
        ids = {r["note_id"] for r in result}
        assert "note-a" in ids  # seed
        assert "note-b" in ids  # 1-hop neighbor

    def test_expand_two_hops(self, db_conn):
        """max_hops=2 should traverse two levels of relationships."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=2)
        assert len(result) == 3
        ids = {r["note_id"] for r in result}
        assert "note-a" in ids
        assert "note-b" in ids
        assert "note-c" in ids

    def test_expand_three_hops(self, db_conn):
        """max_hops=3 should traverse three levels."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=3)
        assert len(result) == 4
        ids = {r["note_id"] for r in result}
        assert ids == {"note-a", "note-b", "note-c", "note-d"}

    def test_expand_multiple_seeds(self, db_conn):
        """Multiple seed nodes should be treated as starting points."""
        self._setup_graph(db_conn)
        # Start from note-b and note-d
        result = expand_graph(db_conn, seed_ids=["note-b", "note-d"], max_hops=1)
        ids = {r["note_id"] for r in result}
        assert "note-b" in ids
        assert "note-d" in ids
        # note-b's neighbor: note-c (via USES) + note-a (incoming)
        # note-d's neighbor: note-c (incoming)
        assert "note-c" in ids

    def test_expand_empty_seeds(self, db_conn):
        """Empty seed list should return empty list."""
        result = expand_graph(db_conn, seed_ids=[], max_hops=2)
        assert result == []

    def test_expand_nonexistent_seeds(self, db_conn):
        """Non-existent seed IDs should be silently skipped."""
        result = expand_graph(db_conn, seed_ids=["nonexistent"], max_hops=2)
        assert result == []

    def test_expand_hop_depth_in_result(self, db_conn):
        """Results should include the hop_depth field."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=2)
        for r in result:
            assert "hop_depth" in r
            assert isinstance(r["hop_depth"], int)
            assert 0 <= r["hop_depth"] <= 2

    def test_expand_results_include_title_and_path(self, db_conn):
        """Each result should include title and path."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=1)
        for r in result:
            assert "title" in r
            assert "path" in r
            assert r["title"]  # non-empty

    def test_expand_deduplicates(self, db_conn):
        """Same node should not appear twice."""
        self._setup_graph(db_conn)
        # From note-b: note-c is 1 hop; from note-a: note-b 1 hop, note-c 2 hops
        result = expand_graph(db_conn, seed_ids=["note-a", "note-b"], max_hops=2)
        ids = [r["note_id"] for r in result]
        assert len(ids) == len(set(ids))

    def test_expand_negative_hops_raises(self, db_conn):
        """Negative max_hops should raise ValueError."""
        with pytest.raises(ValueError, match="max_hops must be >= 0"):
            expand_graph(db_conn, seed_ids=["note-a"], max_hops=-1)

    def test_expand_results_ordered_by_hop_then_title(self, db_conn):
        """Results should be ordered by hop_depth then title."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=3)
        for i in range(len(result) - 1):
            assert result[i]["hop_depth"] <= result[i + 1]["hop_depth"]
            if result[i]["hop_depth"] == result[i + 1]["hop_depth"]:
                assert result[i]["title"] <= result[i + 1]["title"]

    def test_expand_bidirectional(self, db_conn):
        """Graph expansion should follow both outgoing and incoming relationships."""
        # A --[USES]--> B  (outgoing from A)
        # C --[REFERENCES]--> A  (incoming to A)
        ids = ["n-a", "n-b", "n-c"]
        for nid, title in zip(ids, ["Note A", "Note B", "Note C"]):
            upsert_note(db_conn, self._make_note(title, nid))

        store_relationship(db_conn, "n-a", "n-b", "USES")        # outgoing from A
        store_relationship(db_conn, "n-c", "n-a", "REFERENCES")   # incoming to A

        # From A: 1-hop should give B (outgoing) + C (incoming)
        result = expand_graph(db_conn, seed_ids=["n-a"], max_hops=1)
        assert len(result) == 3  # A + B + C
        ids_found = {r["note_id"] for r in result}
        assert ids_found == {"n-a", "n-b", "n-c"}

    def test_expand_max_nodes(self, db_conn):
        """max_nodes should limit the total number of returned nodes."""
        self._setup_graph(db_conn)
        result = expand_graph(db_conn, seed_ids=["note-a"], max_hops=3, max_nodes=2)
        assert len(result) <= 2
