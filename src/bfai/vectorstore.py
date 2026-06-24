"""Qdrant vector store integration for BFAI.

Provides a layer for storing and retrieving semantic embeddings using
Qdrant as the vector database backend.

Configuration via environment variables:

- ``BFAI_QDRANT_URL`` -- Qdrant server URL (default ``http://localhost:6333``)
- ``BFAI_QDRANT_COLLECTION`` -- Collection name (default ``bfai``)

The ``qdrant-client`` package is only required when the vector store
is actually used. Import errors are raised lazily.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from bfai.config import settings

logger = logging.getLogger(__name__)

# Env-var name constants (for introspection / backward compat).
ENV_QDRANT_URL = "BFAI_QDRANT_URL"
ENV_QDRANT_COLLECTION = "BFAI_QDRANT_COLLECTION"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single semantic search result.

    Attributes:
        note_id: The ID of the matched note.
        score: Similarity score (higher means more similar).
        title: The note title.
        metadata: Optional payload metadata.
    """

    note_id: str
    score: float
    title: str = ""
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# VectorStore class
# ---------------------------------------------------------------------------


class VectorStore:
    """Qdrant-backed vector store for note embeddings.

    Args:
        url: The Qdrant server URL. Defaults to the ``BFAI_QDRANT_URL``
            environment variable or ``http://localhost:6333``.
        collection: The collection name. Defaults to the
            ``BFAI_QDRANT_COLLECTION`` environment variable or ``bfai``.
        dimension: The vector dimension (must match the embedding model).

    Raises:
        ImportError: If ``qdrant-client`` is not installed.
        RuntimeError: If connection to Qdrant fails.
    """

    def __init__(
        self,
        url: str | None = None,
        collection: str | None = None,
        dimension: int = 384,
        client: object | None = None,
    ) -> None:
        self._url = url or self._resolve_url()
        self._collection = collection or self._resolve_collection()
        self._dimension = dimension
        if client is not None:
            self._client = client
        else:
            self._client = self._connect()

    @staticmethod
    def _resolve_url() -> str:
        """Resolve Qdrant URL from env, settings, or default.

        Checks runtime ``os.environ`` first (so that tests which
        patch the environment at runtime work), then falls back to
        the cached ``Settings`` singleton, then the hard-coded
        default.
        """
        import os
        return (
            os.environ.get("BFAI_QDRANT_URL")
            or settings.bfai_qdrant_url
            or "http://localhost:6333"
        )

    @staticmethod
    def _resolve_collection() -> str:
        """Resolve Qdrant collection name from env, settings, or default."""
        import os
        return (
            os.environ.get("BFAI_QDRANT_COLLECTION")
            or settings.bfai_qdrant_collection
            or "bfai"
        )

    @staticmethod
    def _import_client():
        """Lazily import the qdrant_client module."""
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-untyped]
            return QdrantClient
        except ImportError as exc:
            raise ImportError(
                "qdrant-client is not installed. "
                "Install it with: pip install qdrant-client"
            ) from exc

    @staticmethod
    def _import_models():
        """Lazily import qdrant_client models."""
        try:
            from qdrant_client.models import (  # type: ignore[import-untyped]
                Distance,
                PointStruct,
                VectorParams,
            )
            return Distance, PointStruct, VectorParams
        except ImportError as exc:
            raise ImportError(
                "qdrant-client is not installed. "
                "Install it with: pip install qdrant-client"
            ) from exc

    @staticmethod
    def _coerce_point_id(id_str: str) -> str:
        """Convert arbitrary string IDs to valid Qdrant point IDs.

        Qdrant v1.12+ only accepts unsigned integers or UUIDs as point
        IDs.  Chunk IDs like ``{note_id}_chunk_{n}`` are not valid UUIDs,
        so we convert them deterministically via ``uuid.uuid5``.

        Args:
            id_str: The original point ID string (e.g. a chunk ID).

        Returns:
            A canonical UUID string (e.g. ``"550e8400-e29b-41d4-a716-446655440000"``).
        """
        # Already a canonical UUID (with dashes) — return as-is
        try:
            return str(uuid.UUID(id_str))
        except ValueError:
            pass
        # Derive a deterministic UUID v5 from the string
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))

    def _connect(self) -> Any:
        """Create a Qdrant client connection."""
        QdrantClient = self._import_client()
        try:
            client = QdrantClient(url=self._url)
            logger.info("Connected to Qdrant at %s", self._url)
            return client
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to Qdrant at {self._url}: {exc}"
            ) from exc

    @property
    def collection_name(self) -> str:
        """The collection name."""
        return self._collection

    @property
    def dimension(self) -> int:
        """The vector dimension."""
        return self._dimension

    def ensure_collection(self, dimension: int | None = None) -> None:
        """Create the collection if it does not already exist.

        Args:
            dimension: Vector dimension to use. Falls back to the
                instance dimension if not provided.
        """
        Distance, PointStruct, VectorParams = self._import_models()
        dim = dimension or self._dimension
        try:
            collections = self._client.get_collections()
            existing = [c.name for c in collections.collections]
            if self._collection in existing:
                logger.debug("Collection '%s' already exists", self._collection)
                return

            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
            )
            self._dimension = dim
            logger.info(
                "Created collection '%s' (dim=%d)", self._collection, dim
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create collection '{self._collection}': {exc}"
            ) from exc

    def upsert(
        self,
        note_id: str,
        vector: list[float],
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a single embedding.

        Args:
            note_id: The note ID to use as the point ID.
            vector: The embedding vector.
            title: The note title (stored as payload).
            metadata: Additional metadata to store as payload.
        """
        _, PointStruct, _ = self._import_models()

        payload: dict[str, Any] = {"title": title}
        if metadata:
            payload.update(metadata)

        point = PointStruct(
            id=self._coerce_point_id(note_id),
            vector=vector,
            payload=payload,
        )
        try:
            self._client.upsert(
                collection_name=self._collection,
                points=[point],
            )
            logger.debug("Upserted vector for note: %s", note_id)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to upsert vector for note {note_id}: {exc}"
            ) from exc

    def upsert_batch(
        self,
        note_ids: list[str],
        vectors: list[list[float]],
        titles: list[str] | None = None,
        metadata_list: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update multiple embeddings in a single operation.

        Args:
            note_ids: List of note IDs.
            vectors: List of embedding vectors.
            titles: Optional list of note titles.
            metadata_list: Optional list of metadata dicts.

        Returns:
            The number of points upserted.
        """
        _, PointStruct, _ = self._import_models()

        points = []
        for i, note_id in enumerate(note_ids):
            payload: dict[str, Any] = {}
            if titles and i < len(titles):
                payload["title"] = titles[i]
            if metadata_list and i < len(metadata_list):
                payload.update(metadata_list[i])
            points.append(
                PointStruct(
                    id=self._coerce_point_id(note_id),
                    vector=vectors[i],
                    payload=payload,
                )
            )

        try:
            self._client.upsert(
                collection_name=self._collection,
                points=points,
            )
            logger.info("Upserted %d vectors", len(points))
            return len(points)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to upsert batch: {exc}"
            ) from exc

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar embeddings.

        Args:
            query_vector: The query embedding vector.
            top_k: Maximum number of results (default 10).
            score_threshold: Optional minimum similarity score.

        Returns:
            List of :class:`SearchResult` objects ordered by score
            (highest first).
        """
        try:
            kwargs: dict[str, Any] = {
                "collection_name": self._collection,
                "query": query_vector,
                "limit": top_k,
            }
            if score_threshold is not None:
                kwargs["score_threshold"] = score_threshold

            results = self._client.query_points(**kwargs)

            search_results = []
            for hit in results.points:
                payload = hit.payload or {}
                search_results.append(
                    SearchResult(
                        note_id=str(hit.id),
                        score=hit.score,
                        title=payload.get("title", ""),
                        metadata={
                            k: v
                            for k, v in payload.items()
                            if k != "title"
                        }
                        or None,
                    )
                )
            return search_results
        except Exception as exc:
            raise RuntimeError(
                f"Vector search failed: {exc}"
            ) from exc

    def delete(self, note_ids: list[str]) -> int:
        """Delete embeddings by note IDs.

        Args:
            note_ids: List of note IDs.

        Returns:
            The number of points deleted.
        """
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=[self._coerce_point_id(nid) for nid in note_ids],
            )
            logger.info("Deleted %d vector(s)", len(note_ids))
            return len(note_ids)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete vectors: {exc}"
            ) from exc

    def delete_by_payload(self, key: str, value: str) -> int:
        """Delete all embeddings matching a payload filter.

        Args:
            key: The payload field name to filter on (e.g. ``"note_id"``).
            value: The value to match (e.g. a note's UUID).

        Returns:
            The number of points deleted (approximate, from Qdrant response).
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            self._client.delete(
                collection_name=self._collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                    ],
                ),
            )
            logger.info("Deleted vectors where %s=%s", key, value)
            return 0  # Qdrant doesn't return count for filter deletes
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete vectors by payload {key}={value}: {exc}"
            ) from exc

    def get_collection_info(self) -> dict[str, Any]:
        """Get information about the collection.

        Returns:
            Dict with ``vector_count``, ``dimension``, and ``status``.
        """
        try:
            info = self._client.get_collection(self._collection)
            return {
                "vector_count": info.points_count or 0,
                "dimension": info.config.params.vectors.size
                if info.config.params.vectors
                else self._dimension,
                "status": str(info.status),
            }
        except Exception as exc:
            raise RuntimeError(
                f"Failed to get collection info: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the Qdrant client connection."""
        try:
            self._client.close()
            logger.debug("Closed Qdrant connection")
        except Exception:
            pass

    def __enter__(self) -> VectorStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()