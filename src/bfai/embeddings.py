"""Embedding provider interface for BFAI.

Provides an abstraction layer for generating text embeddings from
multiple provider backends:

- **SentenceTransformers** (local, open-source)
- **Ollama** (local API, supports many open models)
- **OpenAI** (remote API, ``text-embedding-*`` models)

External dependencies (``sentence-transformers``, ``requests``,
``openai``) are optional.  Import errors are raised lazily only when
the corresponding provider is actually used, so the package can be
installed without any of them.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from bfai.config import settings, ENV_EMBEDDING_PROVIDER

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    All embedding providers must implement :meth:`generate` and
    :meth:`generate_batch`, and expose :attr:`embedding_dimension` and
    :attr:`name`.
    """

    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """The dimensionality of the embedding vectors produced by this
        provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. ``"sentence-transformers"``)."""

    @abstractmethod
    def generate(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            RuntimeError: If embedding generation fails.
        """

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple text strings.

        The base implementation calls :meth:`generate` in a loop.
        Providers that support native batching should override this
        for better performance.

        Args:
            texts: A list of input text strings to embed.

        Returns:
            A list of embedding vectors (each a list of floats).

        Raises:
            RuntimeError: If embedding generation fails.
        """
        results = []
        for text in texts:
            results.append(self.generate(text))
        return results

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r}, dim={self.embedding_dimension})>"


# ---------------------------------------------------------------------------
# SentenceTransformers provider
# ---------------------------------------------------------------------------


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider that uses the ``sentence-transformers`` library.

    Requires the ``sentence-transformers`` package to be installed.

    Args:
        model_name: Name or path of a sentence-transformers model
            (default ``"all-MiniLM-L6-v2"``, 384 dimensions).

    Raises:
        ImportError: If ``sentence-transformers`` is not installed.
        RuntimeError: If the model fails to load.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.embedding_model or "all-MiniLM-L6-v2"
        self._model = self._load_model()
        self._dimension: int = self._model.get_sentence_embedding_dimension() or 384
        logger.info(
            "Initialised SentenceTransformerProvider: model=%s, dim=%d",
            self._model_name,
            self._dimension,
        )

    @staticmethod
    def _load_model():
        """Lazily import and load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            ) from exc
        try:
            model_name = settings.embedding_model or "all-MiniLM-L6-v2"
            return SentenceTransformer(model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load sentence-transformers model: {exc}"
            ) from exc

    @property
    def embedding_dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "sentence-transformers"

    def generate(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._dimension
        try:
            embedding = self._model.encode(text)
            return embedding.tolist()
        except Exception as exc:
            raise RuntimeError(
                f"SentenceTransformer embedding failed: {exc}"
            ) from exc

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self._model.encode(texts)
            return [emb.tolist() for emb in embeddings]
        except Exception as exc:
            raise RuntimeError(
                f"SentenceTransformer batch embedding failed: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that uses the Ollama API.

    Requires the ``requests`` package to be installed.

    Args:
        model_name: The Ollama model to use
            (default ``"nomic-embed-text"``, 768 dimensions).
        base_url: The base URL of the Ollama API
            (default ``"http://localhost:11434"``).

    Raises:
        ImportError: If ``requests`` is not installed.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model or "nomic-embed-text"
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._dimension: int = settings.bfai_embedding_dimensions or 768
        self._requests = self._import_requests()
        logger.info(
            "Initialised OllamaEmbeddingProvider: model=%s, url=%s",
            self._model_name,
            self._base_url,
        )

    @staticmethod
    def _import_requests():
        """Lazily import the ``requests`` module."""
        try:
            import requests  # type: ignore[import-untyped]
            return requests
        except ImportError as exc:
            raise ImportError(
                "requests is not installed. "
                "Install it with: pip install requests"
            ) from exc

    @property
    def embedding_dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "ollama"

    def generate(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._dimension
        try:
            resp = self._requests.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model_name, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not embedding:
                raise RuntimeError("Ollama returned empty embedding")
            self._dimension = len(embedding)
            return embedding
        except self._requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self._base_url}: {exc}"
            ) from exc
        except self._requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama request timed out: {exc}"
            ) from exc
        except self._requests.exceptions.RequestException as exc:
            raise RuntimeError(
                f"Ollama API request failed: {exc}"
            ) from exc

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            results.append(self.generate(text))
        return results


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that uses the OpenAI API.

    Requires the ``openai`` package to be installed.

    Args:
        model_name: The OpenAI embedding model to use
            (default ``"text-embedding-3-small"``, 1536 dimensions).
        api_key: OpenAI API key (default from
            ``BFAI_OPENAI_API_KEY`` environment variable).

    Raises:
        ImportError: If ``openai`` is not installed.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model or "text-embedding-3-small"
        self._api_key = api_key or settings.openai_api_key
        self._dimension: int = 1536  # Default for text-embedding-3-small
        self._client = self._create_client()
        logger.info(
            "Initialised OpenAIEmbeddingProvider: model=%s",
            self._model_name,
        )

    def _create_client(self):
        """Lazily import and create the OpenAI client."""
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "openai is not installed. "
                "Install it with: pip install openai"
            ) from exc

        if not self._api_key:
            logger.warning(
                "OpenAI API key not set. Set %s or pass api_key.", "OPENAI_API_KEY"
            )
        return OpenAI(api_key=self._api_key)

    @property
    def embedding_dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "openai"

    def generate(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._dimension
        try:
            resp = self._client.embeddings.create(
                model=self._model_name,
                input=text,
            )
            embedding = resp.data[0].embedding
            self._dimension = len(embedding)
            return list(embedding)
        except Exception as exc:
            raise RuntimeError(
                f"OpenAI embedding failed: {exc}"
            ) from exc

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = self._client.embeddings.create(
                model=self._model_name,
                input=texts,
            )
            # Sort by index to preserve order
            sorted_data = sorted(resp.data, key=lambda x: x.index)
            embeddings = [list(item.embedding) for item in sorted_data]
            self._dimension = len(embeddings[0]) if embeddings else self._dimension
            return embeddings
        except Exception as exc:
            raise RuntimeError(
                f"OpenAI batch embedding failed: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, type[EmbeddingProvider]] = {
    "sentence-transformers": SentenceTransformerProvider,
    "ollama": OllamaEmbeddingProvider,
    "openai": OpenAIEmbeddingProvider,
}


def get_provider(name: str | None = None, **kwargs: object) -> EmbeddingProvider:
    """Factory function to create an embedding provider by name.

    Args:
        name: The provider name.  One of ``"sentence-transformers"``,
            ``"ollama"``, or ``"openai"``.  If ``None`` (default), the
            value of the ``BFAI_EMBEDDING_PROVIDER`` environment variable
            is used.  If that is also unset, defaults to
            ``"sentence-transformers"``.
        **kwargs: Additional keyword arguments passed to the provider
            constructor (e.g. ``model_name``, ``api_key``, ``base_url``).

    Returns:
        An initialised :class:`EmbeddingProvider` instance.

    Raises:
        ValueError: If the provider name is unknown.
        ImportError: If the required package for the provider is not
            installed.
    """
    env_name = os.environ.get(ENV_EMBEDDING_PROVIDER)
    resolved = name or env_name or settings.bfai_embedding_provider or "sentence-transformers"
    resolved = resolved.lower().strip()

    provider_cls = _PROVIDER_REGISTRY.get(resolved)
    if provider_cls is None:
        valid = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown embedding provider: {resolved!r}. "
            f"Valid providers: {valid}"
        )

    logger.info("Creating embedding provider: %s", resolved)
    return provider_cls(**kwargs)