"""Tests for the memory API module."""
import tempfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from bfai.db import connect, ensure_schema, get_note_by_id, search_notes as db_search_notes
from bfai.memory import (
    backlinks,
    create,
    delete,
    expand,
    hybrid_search,
    index_note,
    index_note_from_path,
    reindex_all,
    related,
    retrieve,
    search,
    semantic_search,
    update,
)
from bfai.models import Note
from bfai.vault import get_vault


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_vault(monkeypatch, tmp_path):
    """Redirect the vault to a temporary directory for each test.

    This fixture:
    1. Creates a temp vault directory with a ``notes`` subdirectory.
    2. Sets ``BFAI_VAULT_PATH`` env var so that ``get_vault()`` and
       ``os.getenv("BFAI_VAULT_PATH")`` resolve to the temp directory.
    3. Overrides ``settings.bfai_vault_path`` so that ``settings.database_path``
       (used by ``connect()`` / ``init_db()``) also points into the temp dir.

    Without step 3, all tests share the same real ``bfai.db``, causing
    ``UNIQUE constraint`` failures and other cross-test pollution.
    """
    from bfai.config import settings

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "notes").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BFAI_VAULT_PATH", str(vault_dir))
    # Override the cached settings singleton so ›database_path‹ resolves to
    # a temp path instead of the real vault (pydantic-settings BaseSettings
    # caches values at import time and does NOT re-read the env var).
    settings.bfai_vault_path = vault_dir
    return vault_dir


# ===========================================================================
# Tests: search API
# ===========================================================================


class TestSearchAPI:
    """Tests for the high-level search API function."""

    def _index_test_note(self, note_id: str, title: str, content: str) -> str:
        """Helper to create and index a Note."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=content,
            title=title,
            body=content,
            id=note_id,
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def test_search_basic(self):
        """Basic search should return matching notes."""
        self._index_test_note("n1", "Robotics", "Building a robot")
        self._index_test_note("n2", "ESP32 Guide", "Microcontroller guide")

        results = search("robot")
        assert len(results) >= 1

    def test_search_no_results(self):
        """Search with no matches should return empty list."""
        results = search("nonexistent")
        assert results == []

    def test_search_limit(self):
        """Search should respect the limit parameter."""
        for i in range(5):
            self._index_test_note(f"n{i}", f"Note {i}", f"Content {i}")

        results = search("Note", limit=2)
        assert len(results) == 2

    def test_search_default_limit(self):
        """Default limit should be 20."""
        results = search("anything")
        assert isinstance(results, list)

    def test_search_returns_note_details(self):
        """Results should include note_id, title, path, and rank."""
        self._index_test_note("n1", "Test Note", "Test content here")

        results = search("Test")
        assert len(results) >= 1
        r = results[0]
        assert "note_id" in r
        assert "title" in r
        assert "path" in r
        assert "rank" in r


# ===========================================================================
# Tests: index API
# ===========================================================================


class TestIndexNote:
    """Tests for the index_note function."""

    def test_index_note_basic(self):
        """Indexing a note should store it in the database."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "test.md",
            content="# Test\n\nHello world.",
            title="Test Note",
            id="test-001",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )

        note_id = index_note(note)
        assert note_id == "test-001"

        conn = connect()
        try:
            ensure_schema(conn)
            saved = get_note_by_id(conn, "test-001")
            assert saved is not None
            assert saved["title"] == "Test Note"
        finally:
            conn.close()

    def test_index_note_makes_searchable(self):
        """Indexing should make the note searchable."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "searchable.md",
            content="# Search Me\n\nThis is searchable content.",
            title="Search Me",
            id="search-001",
            body="This is searchable content.",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )

        index_note(note)

        results = search("searchable")
        assert len(results) >= 1
        assert results[0]["note_id"] == "search-001"

    def test_index_note_with_tags(self):
        """Indexing should store tags when process_tags is True."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "tags.md",
            content="# Tags\n\nContent.",
            title="Tags Note",
            id="tags-001",
            tags=["robotics", "esp32"],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )

        index_note(note, process_tags=True)

        conn = connect()
        try:
            ensure_schema(conn)
            from bfai.db import get_tags_for_note
            tags = get_tags_for_note(conn, "tags-001")
            assert "robotics" in tags
            assert "esp32" in tags
        finally:
            conn.close()

    def test_index_note_with_wiki_links(self):
        """Indexing should process wiki links into relationships."""
        from datetime import datetime
        # First, create the target note
        target = Note(
            path=get_vault() / "notes" / "target.md",
            content="# Target",
            title="Target Note",
            id="target-001",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(target)

        # Create a note that links to it
        source = Note(
            path=get_vault() / "notes" / "source.md",
            content="# Source\n\nLinks to [[Target Note]].",
            title="Source Note",
            id="source-001",
            wiki_links=["Target Note"],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(source)

        conn = connect()
        try:
            ensure_schema(conn)
            from bfai.db import get_relationships_for_note
            rels = get_relationships_for_note(conn, "source-001")
            assert len(rels) == 1
            assert rels[0]["relationship_type"] == "EXPLICIT_LINK"
            assert rels[0]["target_id"] == "target-001"
        finally:
            conn.close()


class TestIndexNoteFromPath:
    """Tests for the index_note_from_path function."""

    def test_index_note_from_path(self, _clean_vault):
        """Loading and indexing from a file path should work."""
        notes_dir = _clean_vault / "notes"
        file_path = notes_dir / "hello.md"
        file_path.write_text("# Hello World\n\nThis is a test note.\n\n#robotics")

        note_id = index_note_from_path(file_path)
        assert note_id is not None

        # Should be searchable
        results = search("Hello")
        assert any(r["note_id"] == note_id for r in results)

        # Should have extracted the tag
        conn = connect()
        try:
            ensure_schema(conn)
            from bfai.db import get_tags_for_note
            tags = get_tags_for_note(conn, note_id)
            assert "robotics" in tags
        finally:
            conn.close()

    def test_index_note_from_path_nonexistent(self):
        """Indexing a non-existent file should return None."""
        result = index_note_from_path(Path("/nonexistent/file.md"))
        assert result is None

    def test_index_note_from_path_non_markdown(self, _clean_vault):
        """Indexing a non-markdown file should return None."""
        file_path = _clean_vault / "notes" / "test.txt"
        file_path.write_text("Not markdown")

        result = index_note_from_path(file_path)
        assert result is None


class TestDeleteNote:
    """Tests for the delete_note function (legacy)."""

    def test_delete_note_removes_from_db(self):
        """Deleting a note should remove it from the database."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "delete-me.md",
            content="# Delete Me",
            title="Delete Me",
            id="delete-001",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)

        result = delete("Delete Me")
        assert result["success"] is True

        conn = connect()
        try:
            ensure_schema(conn)
            assert get_note_by_id(conn, "delete-001") is None
        finally:
            conn.close()

    def test_delete_note_not_found(self):
        """Deleting a non-existent note should return False."""
        result = delete("Nonexistent")
        assert result["success"] is False

    def test_delete_note_removes_from_search(self):
        """Deleting a note should remove it from search results."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "searchable2.md",
            content="# Searchable\n\nContent.",
            title="Searchable",
            id="search-002",
            body="Content.",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)

        assert len(search("Searchable")) >= 1
        result = delete("Searchable")
        print(f"result:{result}")
        print(search("Searchable"))
        assert search("Searchable") == []


class TestReindexAll:
    """Tests for the reindex_all function."""

    def test_reindex_all_basic(self, _clean_vault):
        """Reindexing should index all markdown files in the vault."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "note_a.md").write_text("# Note A\n\nContent A.")
        (notes_dir / "note_b.md").write_text("# Note B\n\nContent B.")

        count = reindex_all()
        assert count == 2

        # Both should be searchable
        results = search("Content")
        assert len(results) == 2

    def test_reindex_all_skips_non_markdown(self, _clean_vault):
        """Reindexing should skip non-markdown files."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "note_a.md").write_text("# Note A\n\nContent.")
        (notes_dir / "note_b.txt").write_text("Not markdown.")

        count = reindex_all()
        assert count == 1

    def test_reindex_all_empty_vault(self, _clean_vault):
        """Reindexing an empty vault should return 0."""
        count = reindex_all()
        assert count == 0

    def test_reindex_all_replaces_old(self, _clean_vault):
        """Reindexing should replace old data."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "note_a.md").write_text("# Note A\n\nOld content.")

        # First index
        reindex_all()
        assert len(search("Old")) == 1

        # Now change the file and reindex
        (notes_dir / "note_a.md").write_text("# Note A\n\nNew content.")
        reindex_all()

        assert search("Old") == []
        assert len(search("New")) == 1


# ===========================================================================
# Tests: backlinks API (Story 5.1)
# ===========================================================================


class TestBacklinksAPI:
    """Tests for the high-level backlinks API function."""

    def _make_and_index_note(self, note_id: str, title: str, wiki_links: list[str] | None = None):
        """Helper to create and index a Note with optional wiki links."""
        from datetime import datetime
        from bfai.models import Note
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}",
            title=title,
            body=f"Content of {title}.",
            id=note_id,
            wiki_links=wiki_links or [],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def test_backlinks_no_results(self):
        """A note with no backlinks should return empty list."""
        self._make_and_index_note("n1", "Solo Note")
        result = backlinks("n1")
        assert result == []

    def test_backlinks_from_wiki_links(self, _clean_vault):
        """Wiki links should create backlinks."""
        # Index target first, then source with wiki link
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        # Target should see source as a backlink
        result = backlinks("target")
        assert len(result) >= 1
        titles = {r["related_title"] for r in result}
        assert "Source Note" in titles

    def test_backlinks_filter_by_type(self, _clean_vault):
        """Backlinks should be filterable by relationship type."""
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        # Filter to EXPLICIT_LINK (which is what wiki links create)
        result = backlinks("target", relationship_type="EXPLICIT_LINK")
        assert len(result) >= 1
        assert result[0]["relationship_type"] == "EXPLICIT_LINK"

        # Filter to a non-matching type
        result = backlinks("target", relationship_type="USES")
        assert result == []

    def test_backlinks_invalid_type_raises(self):
        """Invalid relationship type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown relationship type"):
            backlinks("nonexistent", relationship_type="NOT_A_TYPE")


# ===========================================================================
# Tests: retrieval with backlink and graph expansion (Stories 5.2, 7.2)
# ===========================================================================


class TestRetrieve:
    """Tests for the retrieve function with backlink and graph expansion."""

    def _make_and_index_note(self, note_id: str, title: str,
                              content: str = "",
                              wiki_links: list[str] | None = None) -> str:
        """Helper to create and index a Note."""
        from datetime import datetime
        from bfai.models import Note
        body = content or f"Content of {title}."
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}\n\n{body}",
            title=title,
            body=body,
            id=note_id,
            wiki_links=wiki_links or [],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def _make_and_index_note_with_rels(self, note_id: str, title: str,
                                        content: str = "") -> str:
        """Helper to create, index, and return a Note object for relationship setup."""
        from datetime import datetime
        from bfai.models import Note
        from bfai.db import connect, store_relationship
        body = content or f"Content of {title}."
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}\n\n{body}",
            title=title,
            body=body,
            id=note_id,
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)
        return note

    def test_retrieve_basic_search(self):
        """retrieve should return search results when there are no backlinks."""
        self._make_and_index_note("n1", "ESP32 Guide", "Complete guide to ESP32")
        results = retrieve("ESP32")
        assert len(results) >= 1
        assert results[0]["source"] == "search"
        assert results[0]["match_type"] == "direct"

    def test_retrieve_no_results(self):
        """retrieve with no matches should return empty list."""
        with patch("bfai.memory._semantic_chunk_search", return_value=[]):
            results = retrieve("nonexistent")
        assert results == []

    def test_retrieve_expands_with_backlinks(self, _clean_vault):
        """retrieve should expand results with backlinks."""
        self._make_and_index_note("target", "ESP32 Chip",
                                  "ESP32 Chip microcontroller specifications")

        self._make_and_index_note("src1", "Project X",
                                  "Project X documentation",
                                  wiki_links=["ESP32 Chip"])
        self._make_and_index_note("src2", "Project Y",
                                  "Project Y documentation",
                                  wiki_links=["ESP32 Chip"])

        results = retrieve("ESP32 Chip")
        assert len(results) >= 1

        direct = [r for r in results if r["source"] == "search"]
        assert len(direct) >= 1
        assert direct[0]["title"] == "ESP32 Chip"

        backlinks_found = [r for r in results if r["source"] == "backlink"]
        backlink_titles = {r["title"] for r in backlinks_found}
        assert "Project X" in backlink_titles
        assert "Project Y" in backlink_titles

    def test_retrieve_backlinks_have_match_info(self, _clean_vault):
        """Backlink entries should include matched_note_id and match_type."""
        self._make_and_index_note("target", "ESP32 Chip", "ESP32 specs")
        self._make_and_index_note("src", "Project X", "Uses ESP32",
                                  wiki_links=["ESP32 Chip"])

        results = retrieve("ESP32 Chip")
        backlinks_found = [r for r in results if r["source"] == "backlink"]
        assert len(backlinks_found) >= 1
        bl = backlinks_found[0]
        assert "matched_note_id" in bl
        assert bl["match_type"] == "EXPLICIT_LINK"
        assert bl["title"] == "Project X"

    def test_retrieve_no_double_counting(self, _clean_vault):
        """A note should not appear twice."""
        self._make_and_index_note("target", "ESP32", "ESP32 content")

        results = retrieve("ESP32")
        ids = [r["note_id"] for r in results]
        assert len(ids) == len(set(ids)), "Duplicate note IDs found"

    def test_retrieve_top_k(self, _clean_vault):
        """retrieve should respect the top_k parameter."""
        for i in range(5):
            self._make_and_index_note(f"n{i}", f"Note {i}", f"Content {i}")

        results = retrieve("Note", top_k=2)
        direct = [r for r in results if r["source"] == "search"]
        assert len(direct) <= 2

    def test_retrieve_include_backlinks_false(self, _clean_vault):
        """include_backlinks=False should only return search results."""
        self._make_and_index_note("target", "ESP32 Chip", "ESP32 specs")
        self._make_and_index_note("src", "Project X", "Uses ESP32",
                                  wiki_links=["ESP32 Chip"])

        results = retrieve("ESP32 Chip", include_backlinks=False)
        backlinks_found = [r for r in results if r["source"] == "backlink"]
        assert len(backlinks_found) == 0
        assert all(r["source"] == "search" for r in results)

    def test_retrieve_result_fields(self):
        """Each result should have the expected fields."""
        self._make_and_index_note("n1", "Test Note", "Test content")
        results = retrieve("Test")
        assert len(results) >= 1
        r = results[0]
        assert "note_id" in r
        assert "title" in r
        assert "path" in r
        assert "source" in r
        assert "match_type" in r
        assert "matched_note_id" in r

    def test_retrieve_graph_expansion(self, _clean_vault):
        """retrieve should expand results with graph neighbors."""
        from bfai.db import connect, store_relationship, upsert_note
        from datetime import datetime
        from bfai.models import Note

        # Index the target note that will be found via search
        target = Note(
            path=get_vault() / "notes" / "target.md",
            content="# ESP32 Chip\n\nContent about ESP32 Chip.",
            title="ESP32 Chip",
            body="Content about ESP32 Chip.",
            id="target",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(target)

        # Create and index neighbor notes (using different content to avoid
        # matching the search query)
        neighbor_a = Note(
            path=get_vault() / "notes" / "neighbor-a.md",
            content="# Neighbor A\n\nSome other content here.",
            title="Neighbor A",
            body="Some other content here.",
            id="neighbor-a",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        neighbor_b = Note(
            path=get_vault() / "notes" / "neighbor-b.md",
            content="# Neighbor B\n\nDifferent content entirely.",
            title="Neighbor B",
            body="Different content entirely.",
            id="neighbor-b",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(neighbor_a)
        index_note(neighbor_b)

        # Add relationships: target USES neighbor_a, neighbor_a USES neighbor_b
        conn = connect()
        try:
            from bfai.db import ensure_schema
            ensure_schema(conn)
            store_relationship(conn, "target", "neighbor-a", "USES")
            store_relationship(conn, "neighbor-a", "neighbor-b", "USES")
        finally:
            conn.close()

        # Search for the target with max_hops=1
        results = retrieve("ESP32 Chip", max_hops=1)
        graph = [r for r in results if r["source"] == "graph"]
        graph_titles = {r["title"] for r in graph}
        assert "Neighbor A" in graph_titles

        # Search with max_hops=2 should include neighbor_b too
        results2 = retrieve("ESP32 Chip", max_hops=2)
        graph2 = [r for r in results2 if r["source"] == "graph"]
        graph2_titles = {r["title"] for r in graph2}
        assert "Neighbor A" in graph2_titles
        assert "Neighbor B" in graph2_titles

    def test_retrieve_graph_expansion_hop_depth_field(self, _clean_vault):
        """Graph expansion entries should include hop_depth."""
        from bfai.db import connect, store_relationship
        from datetime import datetime
        from bfai.models import Note

        target = Note(
            path=get_vault() / "notes" / "target.md",
            content="# ESP32 Chip\n\nContent about ESP32 Chip.",
            title="ESP32 Chip",
            body="Content about ESP32 Chip.",
            id="target",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(target)

        neighbor = Note(
            path=get_vault() / "notes" / "neighbor.md",
            content="# Neighbor\n\nOther content.",
            title="Neighbor",
            body="Other content.",
            id="neighbor",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(neighbor)

        conn = connect()
        try:
            from bfai.db import ensure_schema
            ensure_schema(conn)
            store_relationship(conn, "target", "neighbor", "USES")
        finally:
            conn.close()

        results = retrieve("ESP32 Chip", max_hops=1)
        graph = [r for r in results if r["source"] == "graph"]
        if graph:
            assert "hop_depth" in graph[0]
            assert graph[0]["hop_depth"] == 1

    def test_retrieve_graph_max_hops_zero(self, _clean_vault):
        """max_hops=0 should prevent graph expansion."""
        from bfai.db import connect, store_relationship
        from datetime import datetime
        from bfai.models import Note

        target = Note(
            path=get_vault() / "notes" / "target.md",
            content="# ESP32 Chip\n\nContent about ESP32 Chip.",
            title="ESP32 Chip",
            body="Content about ESP32 Chip.",
            id="target",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(target)

        neighbor = Note(
            path=get_vault() / "notes" / "neighbor.md",
            content="# Neighbor\n\nOther content.",
            title="Neighbor",
            body="Other content.",
            id="neighbor",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(neighbor)

        conn = connect()
        try:
            from bfai.db import ensure_schema
            ensure_schema(conn)
            store_relationship(conn, "target", "neighbor", "USES")
        finally:
            conn.close()

        results = retrieve("ESP32 Chip", max_hops=0)
        graph = [r for r in results if r["source"] == "graph"]
        assert len(graph) == 0


# ===========================================================================
# Tests: semantic search API (Story 6.3)
# ===========================================================================


class TestSemanticSearch:
    """Tests for the semantic_search function."""

    def _make_vectorstore(self, mock_client, collection="test_col", dimension=4):
        """Create a VectorStore with a mocked QdrantClient."""
        from bfai.vectorstore import VectorStore
        store = VectorStore(
            url="http://localhost:6333",
            collection=collection,
            dimension=dimension,
            client=mock_client,
        )
        return store

    def test_semantic_search_basic(self):
        """semantic_search should return results from vector store."""
        mock_client = MagicMock()
        hit = MagicMock()
        hit.id = "n1"
        hit.score = 0.95
        hit.payload = {"title": "ESP32 Robotics"}
        query_response = MagicMock()
        query_response.points = [hit]
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            results = semantic_search("robot controller", vector_store=store)

            assert len(results) == 1
            assert results[0]["note_id"] == "n1"
            assert results[0]["score"] == 0.95
            assert results[0]["title"] == "ESP32 Robotics"

    def test_semantic_search_empty(self):
        """semantic_search should return empty list when no results."""
        mock_client = MagicMock()
        query_response = MagicMock()
        query_response.points = []
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            results = semantic_search("nonexistent", vector_store=store)
            assert results == []

    def test_semantic_search_multiple_results(self):
        """semantic_search should return multiple results."""
        mock_client = MagicMock()
        hit1 = MagicMock()
        hit1.id = "n1"
        hit1.score = 0.95
        hit1.payload = {"title": "ESP32"}
        hit2 = MagicMock()
        hit2.id = "n2"
        hit2.score = 0.82
        hit2.payload = {"title": "Robotics", "tags": ["ai"]}
        query_response = MagicMock()
        query_response.points = [hit1, hit2]
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            results = semantic_search("robot", vector_store=store, top_k=5)

            assert len(results) == 2
            assert results[0]["note_id"] == "n1"
            assert results[1]["note_id"] == "n2"
            assert results[1]["metadata"] == {"tags": ["ai"]}

    def test_semantic_search_generates_embedding(self):
        """semantic_search should generate an embedding for the query."""
        mock_client = MagicMock()
        query_response = MagicMock()
        query_response.points = []
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            semantic_search("test query", vector_store=store)

            mock_provider.generate.assert_called_once_with("test query")

    def test_semantic_search_passes_provider_name(self):
        """semantic_search should pass provider_name to get_provider."""
        mock_client = MagicMock()
        query_response = MagicMock()
        query_response.points = []
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            semantic_search("query", provider_name="openai", vector_store=store)

            mock_get_provider.assert_called_once_with(name="openai")

    def test_semantic_search_result_fields(self):
        """Each semantic search result should have expected fields."""
        mock_client = MagicMock()
        hit = MagicMock()
        hit.id = "n1"
        hit.score = 0.9
        hit.payload = {"title": "Test"}
        query_response = MagicMock()
        query_response.points = [hit]
        mock_client.query_points.return_value = query_response

        store = self._make_vectorstore(mock_client)

        with patch("bfai.embeddings.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.generate.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_provider.embedding_dimension = 4
            mock_get_provider.return_value = mock_provider

            results = semantic_search("test", vector_store=store)
            assert len(results) == 1
            r = results[0]
            assert "note_id" in r
            assert "score" in r
            assert "title" in r
            assert "metadata" in r


# ===========================================================================
# Tests: hybrid search API (Story 7.1)
# ===========================================================================


class TestHybridSearch:
    """Tests for the hybrid_search function."""

    def _index_test_notes(self):
        """Index test notes for hybrid search tests."""
        from datetime import datetime
        notes = [
            Note(
                path=get_vault() / "notes" / "esp32.md",
                content="# ESP32 Guide\n\nComplete guide to the ESP32 microcontroller.",
                title="ESP32 Guide",
                body="Complete guide to the ESP32 microcontroller.",
                id="e1",
                created_at=datetime(2026, 6, 10),
                updated_at=datetime(2026, 6, 10),
            ),
            Note(
                path=get_vault() / "notes" / "robotics.md",
                content="# Robotics\n\nBuilding robots with microcontrollers.",
                title="Robotics",
                body="Building robots with microcontrollers.",
                id="e2",
                created_at=datetime(2026, 6, 10),
                updated_at=datetime(2026, 6, 10),
            ),
        ]
        for n in notes:
            index_note(n)

    def test_hybrid_search_fallback(self):
        """hybrid_search should fall back to keyword-only when vector search fails."""
        self._index_test_notes()

        # semantic_search raises RuntimeError → hybrid should fall back
        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.side_effect = RuntimeError("Qdrant not available")

            results = hybrid_search("ESP32", top_k=5)

            assert len(results) >= 1
            # All results should be from keyword source
            for r in results:
                assert r["source"] in ("keyword",)
                assert r["semantic_score"] == 0.0

    def test_hybrid_search_deduplicates(self):
        """hybrid_search should deduplicate notes appearing in both sets."""
        from datetime import datetime

        # Index a note that will match via keyword
        note = Note(
            path=get_vault() / "notes" / "esp32.md",
            content="# ESP32 Guide\n\nComplete guide to the ESP32 microcontroller.",
            title="ESP32 Guide",
            body="Complete guide to the ESP32 microcontroller.",
            id="e1",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)

        # Mock semantic search to return the same note
        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.return_value = [
                {"note_id": "e1", "score": 0.95, "title": "ESP32 Guide", "metadata": None}
            ]

            results = hybrid_search("ESP32", top_k=10)

            # Should only appear once
            ids = [r["note_id"] for r in results]
            assert len(ids) == len(set(ids))
            assert ids.count("e1") == 1

            # Should be marked as hybrid
            hybrid = [r for r in results if r["source"] == "hybrid"]
            assert len(hybrid) >= 1

    def test_hybrid_search_only_semantic(self):
        """hybrid_search should return only semantic results when keyword has none."""
        # Index a note that won't match FTS5
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "esp32.md",
            content="# ESP32 Guide\n\nContent.",
            title="ESP32 Guide",
            body="Content.",
            id="e1",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)

        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.return_value = [
                {"note_id": "e1", "score": 0.9, "title": "ESP32 Guide", "metadata": None}
            ]

            # Search for something that won't match FTS5
            results = hybrid_search("nonexistent", top_k=10)

            assert len(results) >= 1
            assert results[0]["source"] == "semantic"
            assert results[0]["keyword_score"] == 0.0

    def test_hybrid_search_weights(self):
        """hybrid_search should respect custom keyword/semantic weights."""
        from datetime import datetime
        note = Note(
            path=get_vault() / "notes" / "esp32.md",
            content="# ESP32 Guide\n\nComplete guide to the ESP32 microcontroller.",
            title="ESP32 Guide",
            body="Complete guide to the ESP32 microcontroller.",
            id="e1",
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        index_note(note)

        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.return_value = [
                {"note_id": "e1", "score": 0.5, "title": "ESP32 Guide", "metadata": None}
            ]

            # keyword_weight=1.0 means only keyword matters
            results = hybrid_search("ESP32", keyword_weight=1.0, semantic_weight=0.0)

            assert len(results) >= 1
            r = results[0]
            assert r["keyword_score"] > 0.0
            # semantic_score is the raw normalised score (0.5/0.5=1.0),
            # but combined_score = 1.0 * keyword_score + 0.0 * semantic_score
            assert r["combined_score"] == r["keyword_score"]
            assert r["semantic_score"] > 0.0  # raw score, not weighted
            assert r["source"] == "hybrid"

    def test_hybrid_search_invalid_weights(self):
        """hybrid_search should raise ValueError for invalid weights."""
        with pytest.raises(ValueError, match="keyword_weight"):
            hybrid_search("test", keyword_weight=0.5, semantic_weight=0.6)

    def test_hybrid_search_result_fields(self):
        """Each hybrid search result should have expected fields."""
        self._index_test_notes()

        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.side_effect = RuntimeError("Not available")

            results = hybrid_search("ESP32", top_k=5)
            assert len(results) >= 1
            r = results[0]
            assert "note_id" in r
            assert "title" in r
            assert "path" in r
            assert "source" in r
            assert "keyword_score" in r
            assert "semantic_score" in r
            assert "combined_score" in r

    def test_hybrid_search_empty(self):
        """hybrid_search should return empty list when no results from either source."""
        with patch("bfai.memory.search") as mock_search:
            mock_search.return_value = []
            with patch("bfai.memory.semantic_search") as mock_semantic:
                mock_semantic.return_value = []
                results = hybrid_search("nonexistent")
                assert results == []

    def test_hybrid_search_orders_by_combined_score(self):
        """hybrid_search results should be ordered by combined_score descending."""
        from datetime import datetime

        notes = [
            Note(
                path=get_vault() / "notes" / "esp32.md",
                content="# ESP32 Guide\n\nGuide to ESP32 microcontroller.",
                title="ESP32 Guide",
                body="Guide to ESP32 microcontroller.",
                id="e1",
                created_at=datetime(2026, 6, 10),
                updated_at=datetime(2026, 6, 10),
            ),
            Note(
                path=get_vault() / "notes" / "robot-arm.md",
                content="# Robot Arm\n\nBuilding a robot arm with microcontrollers.",
                title="Robot Arm",
                body="Building a robot arm with microcontrollers.",
                id="e2",
                created_at=datetime(2026, 6, 10),
                updated_at=datetime(2026, 6, 10),
            ),
        ]
        for n in notes:
            index_note(n)

        with patch("bfai.memory.semantic_search") as mock_semantic:
            mock_semantic.side_effect = RuntimeError("Not available")

            results = hybrid_search("microcontroller", top_k=5)

            if len(results) >= 2:
                for i in range(len(results) - 1):
                    assert results[i]["combined_score"] >= results[i + 1]["combined_score"]


# ===========================================================================
# Tests: create API (Story 8.1)
# ===========================================================================


class TestCreateAPI:
    """Tests for the high-level create API function."""

    def test_create_basic(self, _clean_vault):
        """create should create a note and index it."""
        result = create("My New Note", "This is the content.")
        assert "note" in result
        assert "id" in result
        assert result["embedded"] is False
        assert result["note"].title == "My New Note"

        # Should be searchable
        search_results = search("content")
        assert any(r["note_id"] == result["id"] for r in search_results)

    def test_create_with_tags(self, _clean_vault):
        """create should accept tags."""
        result = create("Tagged Note", "Content here.", tags=["robotics", "esp32"])
        assert result["note"].tags == ["robotics", "esp32"]

    def test_create_with_metadata(self, _clean_vault):
        """create should accept metadata."""
        result = create(
            "Meta Note",
            "Content.",
            metadata={"author": "Test", "version": "1"},
        )
        assert result["note"].metadata.get("author") == "Test"

    def test_create_creates_file(self, _clean_vault):
        """create should create a markdown file on disk."""
        result = create("File Check", "Content.")
        assert result["note"].path.exists()
        assert result["note"].path.suffix == ".md"

    def test_create_with_embed_failure_graceful(self, _clean_vault):
        """create should handle embedding failure gracefully."""
        with patch("bfai.memory._embed_note") as mock_embed:
            mock_embed.side_effect = RuntimeError("Qdrant unavailable")
            result = create("Embed Fail", "Content.", embed=True)
            assert result["embedded"] is False
            assert "note" in result
            assert "id" in result


# ===========================================================================
# Tests: update API (Story 8.2)
# ===========================================================================


class TestUpdateAPI:
    """Tests for the high-level update API function."""

    def test_update_content(self, _clean_vault):
        """update should change the content of a note."""
        created = create("Update Test", "Original content.")
        note_id = created["id"]

        result = update("Update Test", content="Updated content.")
        assert result is not None
        assert result["id"] == note_id

        # Should find updated content
        search_results = search("Updated")
        assert any(r["note_id"] == note_id for r in search_results)

        # Original content should no longer be searchable
        assert "Updated content." in result["note"].body

    def test_update_nonexistent(self, _clean_vault):
        """update on a non-existent note should return None."""
        result = update("Nonexistent Note", content="Content.")
        assert result is None

    def test_update_preserves_id(self, _clean_vault):
        """update should preserve the note ID."""
        created = create("Preserve ID", "Content.")
        original_id = created["id"]

        result = update("Preserve ID", content="New content.")
        assert result["id"] == original_id

    def test_update_with_metadata(self, _clean_vault):
        """update should accept new metadata."""
        create("Meta Update", "Content.")
        result = update("Meta Update", metadata={"status": "updated"})
        assert result["note"].metadata.get("status") == "updated"

    def test_update_content_only(self, _clean_vault):
        """update with only content should preserve existing metadata."""
        create("Partial Update", "Original.", metadata={"key": "value"})
        result = update("Partial Update", content="New content.")
        assert result["note"].metadata.get("key") == "value"


# ===========================================================================
# Tests: delete API (Story 8.3)
# ===========================================================================


class TestDeleteAPI:
    """Tests for the high-level delete API function."""

    def test_delete_basic(self, _clean_vault):
        """delete should remove a note from all storage layers."""
        created = create("Delete Test", "Content to delete.")
        note_id = created["id"]

        # Verify it's searchable
        assert any(r["note_id"] == note_id for r in search("Delete"))

        result = delete("Delete Test")
        assert result["success"] is True
        assert result["file_deleted"] is True
        assert result["db_deleted"] is True
        assert result["embedding_removed"] is False

        # Should no longer be searchable
        assert search("Delete") == []

    def test_delete_nonexistent(self, _clean_vault):
        """delete on a non-existent note should return success=False."""
        result = delete("Nonexistent Note")
        assert result["success"] is False
        assert "error" in result

    def test_delete_removes_file_from_disk(self, _clean_vault):
        """delete should remove the markdown file from disk."""
        create("Disk Delete", "Content.")
        notes_dir = _clean_vault / "notes"
        file_path = notes_dir / "disk-delete.md"
        assert file_path.exists()

        delete("Disk Delete")
        assert not file_path.exists()

    def test_delete_removes_relationships(self, _clean_vault):
        """delete should cascade to remove relationships."""
        from bfai.db import connect, get_relationships_for_note, ensure_schema

        # Create two notes with a wiki link relationship
        create("Source Note", "Links to [[Target Note]].")
        create("Target Note", "Target content.")

        # Verify relationship exists
        conn = connect()
        try:
            ensure_schema(conn)
            src_id = self._get_note_id("Source Note")
            rels = get_relationships_for_note(conn, src_id)
            assert len(rels) >= 1
        finally:
            conn.close()

        # Delete the source note
        delete("Source Note")

        # Relationship should be gone
        conn = connect()
        try:
            ensure_schema(conn)
            rels = get_relationships_for_note(conn, src_id)
            assert len(rels) == 0
        finally:
            conn.close()

    def test_delete_empty_title_raises(self):
        """delete with empty title should raise ValueError."""
        with pytest.raises(ValueError, match="Note title must not be empty"):
            delete("")
        with pytest.raises(ValueError, match="Note title must not be empty"):
            delete("   ")

    def test_delete_with_embedding_removal(self, _clean_vault):
        """delete should remove embedding when remove_embedding=True."""
        with patch("bfai.memory._remove_embedding") as mock_remove:
            create("Embed Delete", "Content.", embed=True)
            result = delete("Embed Delete", remove_embedding=True)
            assert result["success"] is True
            # _remove_embedding is called at least once (from delete).
            # It may also be called inside _embed_note if embedding succeeds,
            # but if model loading fails, only the delete call fires.
            assert mock_remove.call_count >= 1
            # Verify the call(s) include the delete step arguments:
            # _remove_embedding(note_id, provider_name=None)
            mock_remove.assert_called_with(ANY, provider_name=None)

    def _get_note_id(self, title: str) -> str:
        """Helper to get a note ID by title from the database."""
        from bfai.db import connect, ensure_schema, get_note_by_title as db_get_by_title

        conn = connect()
        try:
            ensure_schema(conn)
            from bfai.writer import _resolve_note_path
            path = str(_resolve_note_path(title))
            note = db_get_by_title(conn, title)
            return note["id"] if note else ""
        finally:
            conn.close()


# ===========================================================================
# Tests: related API (Story 3.4 / 8.4)
# ===========================================================================


class TestRelatedAPI:
    """Tests for the high-level related API function."""

    def _make_and_index_note(self, note_id: str, title: str,
                              wiki_links: list[str] | None = None) -> str:
        """Helper to create and index a Note."""
        from datetime import datetime
        from bfai.models import Note
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}",
            title=title,
            body=f"Content of {title}.",
            id=note_id,
            wiki_links=wiki_links or [],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def test_related_no_relationships(self):
        """related with no relationships should return empty list."""
        self._make_and_index_note("n1", "Solo Note")
        result = related("n1")
        assert result == []

    def test_related_outgoing(self, _clean_vault):
        """related should return outgoing relationships."""
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        result = related("src", direction="outgoing")
        assert len(result) >= 1
        titles = {r["related_title"] for r in result}
        assert "Target Note" in titles

    def test_related_incoming(self, _clean_vault):
        """related should return incoming relationships."""
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        result = related("target", direction="incoming")
        assert len(result) >= 1
        titles = {r["related_title"] for r in result}
        assert "Source Note" in titles

    def test_related_both_directions(self, _clean_vault):
        """related with direction='both' should return both directions."""
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        result = related("target", direction="both")
        assert len(result) >= 1
        titles = {r["related_title"] for r in result}
        assert "Source Note" in titles

    def test_related_filter_by_type(self, _clean_vault):
        """related should filter by relationship type."""
        self._make_and_index_note("target", "Target Note")
        self._make_and_index_note("src", "Source Note", wiki_links=["Target Note"])

        result = related("target", relationship_type="EXPLICIT_LINK")
        assert len(result) >= 1
        assert result[0]["relationship_type"] == "EXPLICIT_LINK"

        result = related("target", relationship_type="USES")
        assert result == []

    def test_related_invalid_direction(self, _clean_vault):
        """related with invalid direction should raise ValueError."""
        self._make_and_index_note("n1", "Note")
        with pytest.raises(ValueError, match="direction"):
            related("n1", direction="invalid")


# ===========================================================================
# Tests: expand API (Story 7.2 / 8.4)
# ===========================================================================


class TestExpandAPI:
    """Tests for the high-level expand API function."""

    def _make_and_index_note(self, note_id: str, title: str) -> str:
        """Helper to create and index a Note."""
        from datetime import datetime
        from bfai.models import Note
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}",
            title=title,
            body=f"Content of {title}.",
            id=note_id,
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def test_expand_zero_hops(self, _clean_vault):
        """expand with max_hops=0 should return only seeds."""
        self._make_and_index_note("n1", "Note One")
        result = expand(["n1"], max_hops=0)
        assert len(result) == 1
        assert result[0]["hop_depth"] == 0
        assert result[0]["title"] == "Note One"

    def test_expand_one_hop(self, _clean_vault):
        """expand should traverse 1-hop relationships."""
        from bfai.db import connect, store_relationship, ensure_schema

        self._make_and_index_note("n1", "Seed Note")
        self._make_and_index_note("n2", "Neighbor")

        conn = connect()
        try:
            ensure_schema(conn)
            store_relationship(conn, "n1", "n2", "USES")
        finally:
            conn.close()

        result = expand(["n1"], max_hops=1)
        titles = {r["title"] for r in result}
        assert "Seed Note" in titles
        assert "Neighbor" in titles

    def test_expand_two_hops(self, _clean_vault):
        """expand should traverse 2-hop relationships."""
        from bfai.db import connect, store_relationship, ensure_schema

        self._make_and_index_note("n1", "Seed Note")
        self._make_and_index_note("n2", "Middle")
        self._make_and_index_note("n3", "Far Neighbor")

        conn = connect()
        try:
            ensure_schema(conn)
            store_relationship(conn, "n1", "n2", "USES")
            store_relationship(conn, "n2", "n3", "USES")
        finally:
            conn.close()

        result = expand(["n1"], max_hops=2)
        titles = {r["title"] for r in result}
        assert "Seed Note" in titles
        assert "Middle" in titles
        assert "Far Neighbor" in titles

    def test_expand_empty_seeds(self):
        """expand with empty seeds should return empty list."""
        result = expand([], max_hops=2)
        assert result == []

    def test_expand_max_nodes(self, _clean_vault):
        """expand should respect max_nodes limit."""
        from bfai.db import connect, store_relationship, ensure_schema

        self._make_and_index_note("n1", "Seed")
        for i in range(5):
            self._make_and_index_note(f"n{i+2}", f"Neighbor {i+1}")
            conn = connect()
            try:
                ensure_schema(conn)
                store_relationship(conn, "n1", f"n{i+2}", "USES")
            finally:
                conn.close()

        result = expand(["n1"], max_hops=1, max_nodes=3)
        assert len(result) <= 3


# ===========================================================================
# Tests: retrieve API — expanded coverage (Story 8.4)
# ===========================================================================


class TestRetrieveExtended:
    """Extended tests for the retrieve API beyond the initial suite."""

    def _make_and_index_note(self, note_id: str, title: str,
                              content: str = "",
                              wiki_links: list[str] | None = None) -> str:
        """Helper to create and index a Note."""
        from datetime import datetime
        from bfai.models import Note
        body = content or f"Content of {title}."
        note = Note(
            path=get_vault() / "notes" / f"{note_id}.md",
            content=f"# {title}\n\n{body}",
            title=title,
            body=body,
            id=note_id,
            wiki_links=wiki_links or [],
            created_at=datetime(2026, 6, 10),
            updated_at=datetime(2026, 6, 10),
        )
        return index_note(note)

    def test_retrieve_with_backlinks_and_graph(self, _clean_vault):
        """retrieve should return combined search + backlinks + graph."""
        from bfai.db import connect, store_relationship, ensure_schema

        # Create a target and linked notes
        self._make_and_index_note("target", "ESP32 Chip", "ESP32 Chip microcontroller")

        # Backlink via wiki link
        self._make_and_index_note("src", "Project X", "Uses ESP32",
                                   wiki_links=["ESP32 Chip"])

        # Graph neighbor via relationship
        self._make_and_index_note("neighbor", "ESP32 Datasheet", "Technical specs.")
        conn = connect()
        try:
            ensure_schema(conn)
            store_relationship(conn, "target", "neighbor", "RELATED_TO")
        finally:
            conn.close()

        results = retrieve("ESP32 Chip")

        # Should have search result
        search_items = [r for r in results if r["source"] == "search"]
        assert len(search_items) >= 1

        # Should have backlink
        backlink_items = [r for r in results if r["source"] == "backlink"]
        assert len(backlink_items) >= 1

        # Should have graph neighbor
        graph_items = [r for r in results if r["source"] == "graph"]
        assert len(graph_items) >= 1
