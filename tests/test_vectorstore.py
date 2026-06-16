"""Tests for the Qdrant vector store integration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from bfai.vectorstore import (
    ENV_QDRANT_COLLECTION,
    ENV_QDRANT_URL,
    SearchResult,
    VectorStore,
)


# ===========================================================================
# Tests: SearchResult dataclass
# ===========================================================================


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_basic_creation(self):
        """SearchResult should hold note_id and score."""
        result = SearchResult(note_id="n1", score=0.95)
        assert result.note_id == "n1"
        assert result.score == 0.95

    def test_with_title(self):
        """SearchResult should accept title."""
        result = SearchResult(note_id="n1", score=0.9, title="Test Note")
        assert result.title == "Test Note"

    def test_with_metadata(self):
        """SearchResult should accept metadata."""
        result = SearchResult(
            note_id="n1", score=0.9, metadata={"tags": ["ai"]}
        )
        assert result.metadata == {"tags": ["ai"]}

    def test_metadata_default_none(self):
        """metadata should default to None."""
        result = SearchResult(note_id="n1", score=0.9)
        assert result.metadata is None

    def test_title_default_empty(self):
        """title should default to empty string."""
        result = SearchResult(note_id="n1", score=0.9)
        assert result.title == ""


# ===========================================================================
# Helper to create mocked VectorStore
# ===========================================================================


def _make_vectorstore(mock_client, collection="test_col", dimension=4):
    """Create a VectorStore with a mocked QdrantClient."""
    with patch("bfai.vectorstore.VectorStore._connect") as mock_connect:
        mock_connect.return_value = mock_client
        store = VectorStore(
            url="http://localhost:6333",
            collection=collection,
            dimension=dimension,
        )
    return store


# ===========================================================================
# Tests: VectorStore initialization
# ===========================================================================


class TestVectorStoreInit:
    """Tests for VectorStore initialization."""

    def test_import_error(self):
        """Should raise ImportError when qdrant_client not installed."""
        with patch("bfai.vectorstore.VectorStore._connect") as mock_connect:
            mock_connect.side_effect = ImportError("qdrant-client is not installed")
            with pytest.raises(ImportError, match="qdrant-client"):
                VectorStore()

    def test_collection_name(self):
        """collection_name property should return the collection name."""
        client = MagicMock()
        store = _make_vectorstore(client, collection="my_col")
        assert store.collection_name == "my_col"

    def test_dimension(self):
        """dimension property should return the dimension."""
        client = MagicMock()
        store = _make_vectorstore(client, dimension=256)
        assert store.dimension == 256

    def test_env_url(self):
        """Should use BFAI_QDRANT_URL env var."""
        with patch.dict("os.environ", {ENV_QDRANT_URL: "http://custom:6333"}):
            client = MagicMock()
            with patch("bfai.vectorstore.VectorStore._connect") as mock_connect:
                mock_connect.return_value = client
                store = VectorStore(collection="test")
                assert store._url == "http://custom:6333"

    def test_env_collection(self):
        """Should use BFAI_QDRANT_COLLECTION env var."""
        with patch.dict("os.environ", {ENV_QDRANT_COLLECTION: "custom_col"}):
            client = MagicMock()
            with patch("bfai.vectorstore.VectorStore._connect") as mock_connect:
                mock_connect.return_value = client
                store = VectorStore()
                assert store._collection == "custom_col"


# ===========================================================================
# Tests: ensure_collection
# ===========================================================================


class TestEnsureCollection:
    """Tests for ensure_collection."""

    def test_creates_collection(self):
        """Should create the collection when it does not exist."""
        client = MagicMock()
        client.get_collections.return_value.collections = []
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            store.ensure_collection()
            client.create_collection.assert_called_once()

    def test_skips_existing(self):
        """Should skip if collection already exists."""
        client = MagicMock()
        mock_col = MagicMock()
        mock_col.name = "test_col"
        client.get_collections.return_value.collections = [mock_col]
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            store.ensure_collection()
            client.create_collection.assert_not_called()

    def test_custom_dimension(self):
        """Should use provided dimension."""
        client = MagicMock()
        client.get_collections.return_value.collections = []
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            store.ensure_collection(dimension=512)
            assert client.create_collection.called

    def test_error_handling(self):
        """Should raise RuntimeError on failure."""
        client = MagicMock()
        client.get_collections.side_effect = Exception("connection failed")
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="Failed to create collection"):
                store.ensure_collection()


# ===========================================================================
# Tests: upsert
# ===========================================================================


class TestUpsert:
    """Tests for upsert operations."""

    def test_upsert_single(self):
        """Should call client.upsert with a single point."""
        client = MagicMock()
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            store.upsert(
                note_id="n1",
                vector=[0.1, 0.2, 0.3, 0.4],
                title="Test Note",
            )
            client.upsert.assert_called_once()

    def test_upsert_with_metadata(self):
        """Should include metadata in payload."""
        client = MagicMock()
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            store.upsert(
                note_id="n2",
                vector=[0.1, 0.2, 0.3, 0.4],
                title="Test Note",
                metadata={"tags": ["ai"]},
            )
            client.upsert.assert_called_once()

    def test_upsert_error(self):
        """Should raise RuntimeError on upsert failure."""
        client = MagicMock()
        client.upsert.side_effect = Exception("connection failed")
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="Failed to upsert"):
                store.upsert(
                    note_id="n1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                )


# ===========================================================================
# Tests: upsert_batch
# ===========================================================================


class TestUpsertBatch:
    """Tests for upsert_batch operations."""

    def test_upsert_batch(self):
        """Should upsert multiple vectors."""
        client = MagicMock()
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            count = store.upsert_batch(
                note_ids=["n1", "n2", "n3"],
                vectors=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
                titles=["Note 1", "Note 2", "Note 3"],
            )
            assert count == 3
            client.upsert.assert_called_once()

    def test_upsert_batch_error(self):
        """Should raise RuntimeError on batch upsert failure."""
        client = MagicMock()
        client.upsert.side_effect = Exception("failed")
        store = _make_vectorstore(client)
        with patch("bfai.vectorstore.VectorStore._import_models") as mock_models:
            mock_models.return_value = (MagicMock(), MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="Failed to upsert batch"):
                store.upsert_batch(
                    note_ids=["n1"],
                    vectors=[[0.1, 0.2]],
                )


# ===========================================================================
# Tests: search
# ===========================================================================


class TestSearch:
    """Tests for search operation."""

    def test_search(self):
        """Should return SearchResult objects from search hits."""
        client = MagicMock()
        hit1 = MagicMock()
        hit1.id = "n1"
        hit1.score = 0.95
        hit1.payload = {"title": "ESP32"}
        hit2 = MagicMock()
        hit2.id = "n2"
        hit2.score = 0.82
        hit2.payload = {"title": "Robot", "tags": ["ai"]}
        query_response = MagicMock()
        query_response.points = [hit1, hit2]
        client.query_points.return_value = query_response
        store = _make_vectorstore(client)
        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert len(results) == 2
        assert results[0].note_id == "n1"
        assert results[0].score == 0.95
        assert results[0].title == "ESP32"
        assert results[1].note_id == "n2"
        assert results[1].metadata == {"tags": ["ai"]}

    def test_search_empty(self):
        """Should return empty list when no results."""
        client = MagicMock()
        query_response = MagicMock()
        query_response.points = []
        client.query_points.return_value = query_response
        store = _make_vectorstore(client)
        results = store.search([0.1, 0.2, 0.3, 0.4])
        assert results == []

    def test_search_with_threshold(self):
        """Should pass score_threshold to client.query_points."""
        client = MagicMock()
        query_response = MagicMock()
        query_response.points = []
        client.query_points.return_value = query_response
        store = _make_vectorstore(client)
        store.search([0.1, 0.2, 0.3, 0.4], score_threshold=0.5)
        client.query_points.assert_called_once()
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["score_threshold"] == 0.5

    def test_search_error(self):
        """Should raise RuntimeError on search failure."""
        client = MagicMock()
        client.query_points.side_effect = Exception("connection failed")
        store = _make_vectorstore(client)
        with pytest.raises(RuntimeError, match="Vector search failed"):
            store.search([0.1, 0.2, 0.3, 0.4])


# ===========================================================================
# Tests: delete
# ===========================================================================


class TestDelete:
    """Tests for delete operation."""

    def test_delete(self):
        """Should delete notes by IDs."""
        client = MagicMock()
        store = _make_vectorstore(client)
        count = store.delete(["n1", "n2"])
        assert count == 2
        client.delete.assert_called_once()

    def test_delete_error(self):
        """Should raise RuntimeError on delete failure."""
        client = MagicMock()
        client.delete.side_effect = Exception("failed")
        store = _make_vectorstore(client)
        with pytest.raises(RuntimeError, match="Failed to delete vectors"):
            store.delete(["n1"])


# ===========================================================================
# Tests: get_collection_info
# ===========================================================================


class TestGetCollectionInfo:
    """Tests for get_collection_info."""

    def test_get_info(self):
        """Should return collection info."""
        client = MagicMock()
        info = MagicMock()
        info.points_count = 42
        info.config.params.vectors.size = 384
        info.status = "green"
        client.get_collection.return_value = info
        store = _make_vectorstore(client)
        result = store.get_collection_info()
        assert result["vector_count"] == 42
        assert result["dimension"] == 384
        assert result["status"] == "green"

    def test_get_info_error(self):
        """Should raise RuntimeError on failure."""
        client = MagicMock()
        client.get_collection.side_effect = Exception("not found")
        store = _make_vectorstore(client)
        with pytest.raises(RuntimeError, match="Failed to get collection info"):
            store.get_collection_info()


# ===========================================================================
# Tests: close and context manager
# ===========================================================================


class TestCloseAndContext:
    """Tests for close and context manager protocol."""

    def test_close(self):
        """Should call client.close()."""
        client = MagicMock()
        store = _make_vectorstore(client)
        store.close()
        client.close.assert_called_once()

    def test_context_manager(self):
        """Should support with statement."""
        client = MagicMock()
        store = _make_vectorstore(client)
        with store as s:
            assert s is store
        client.close.assert_called_once()

    def test_close_error_handled(self):
        """Should not raise on close error."""
        client = MagicMock()
        client.close.side_effect = Exception("error")
        store = _make_vectorstore(client)
        store.close()