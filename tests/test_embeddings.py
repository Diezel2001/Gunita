"""Tests for the embedding provider interface."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from bfai.config import (
    ENV_EMBEDDING_MODEL,
    ENV_EMBEDDING_PROVIDER,
    ENV_OLLAMA_BASE_URL,
    ENV_OPENAI_API_KEY,
)
from bfai.embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerProvider,
    get_provider,
)


# ===========================================================================
# Tests: abstract base class
# ===========================================================================


class TestEmbeddingProviderABC:
    """Tests for the EmbeddingProvider ABC."""

    def test_cannot_instantiate_abc(self):
        """EmbeddingProvider should not be directly instantiable."""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]

    def test_abstract_methods_defined(self):
        """EmbeddingProvider should define abstract methods."""
        abstract = set(EmbeddingProvider.__abstractmethods__)
        assert "generate" in abstract
        assert "embedding_dimension" in abstract
        assert "name" in abstract

    def test_generate_batch_fallback(self):
        """Base generate_batch should call generate in a loop."""

        class _TestProvider(EmbeddingProvider):
            @property
            def embedding_dimension(self) -> int:
                return 2

            @property
            def name(self) -> str:
                return "test"

            def generate(self, text: str) -> list[float]:
                return [0.1, 0.2] if text == "hello" else [0.3, 0.4]

        provider = _TestProvider()
        result = provider.generate_batch(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]


# ===========================================================================
# Tests: factory function
# ===========================================================================


class TestGetProvider:
    """Tests for the get_provider factory function."""

    def test_default_provider(self):
        """Default provider (no env) should be sentence-transformers."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_load.return_value = mock_model
                provider = get_provider()
                assert isinstance(provider, SentenceTransformerProvider)

    def test_env_var_provider(self):
        """BFAI_EMBEDDING_PROVIDER env var should select provider."""
        with patch.dict("os.environ", {ENV_EMBEDDING_PROVIDER: "ollama", "BFAI_OLLAMA_URL": "http://localhost:11434"}):
            with patch("bfai.embeddings.OllamaEmbeddingProvider._import_requests") as mock_import:
                mock_req = MagicMock()
                mock_resp = MagicMock()
                mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
                mock_req.post.return_value = mock_resp
                mock_import.return_value = mock_req
                provider = get_provider()
                assert isinstance(provider, OllamaEmbeddingProvider)

    def test_explicit_name(self):
        """Explicit name should override env var."""
        with patch("bfai.embeddings.OpenAIEmbeddingProvider._create_client") as mock_create:
            mock_resp = MagicMock()
            mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3, 0.4])]
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = mock_resp
            mock_create.return_value = mock_client
            provider = get_provider("openai", api_key="sk-test")
            assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_unknown_provider_raises(self):
        """Unknown provider name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_provider("nonexistent")

    def test_unknown_provider_via_env(self):
        """Unknown provider via env should raise ValueError."""
        with patch.dict("os.environ", {ENV_EMBEDDING_PROVIDER: "invalid"}):
            with pytest.raises(ValueError, match="Unknown embedding provider"):
                get_provider()

    def test_provider_registry_has_expected(self):
        """Registry should contain all three providers."""
        from bfai.embeddings import _PROVIDER_REGISTRY
        assert set(_PROVIDER_REGISTRY.keys()) == {
            "sentence-transformers", "ollama", "openai"
        }

    def test_provider_case_insensitive(self):
        """Provider name matching should be case-insensitive."""
        with patch("bfai.embeddings.OllamaEmbeddingProvider._import_requests") as mock_import:
            mock_req = MagicMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
            mock_req.post.return_value = mock_resp
            mock_import.return_value = mock_req
            provider = get_provider("OLLAMA", base_url="http://localhost:11434")
            assert isinstance(provider, OllamaEmbeddingProvider)

    def test_get_provider_passes_kwargs(self):
        """get_provider should pass kwargs to provider constructor."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_load.return_value = mock_model
            provider = get_provider("sentence-transformers", model_name="test-model")
            assert provider.embedding_dimension == 384


# ===========================================================================
# Tests: SentenceTransformerProvider
# ===========================================================================


class TestSentenceTransformerProvider:
    """Tests for SentenceTransformerProvider (with mocked model)."""

    @pytest.fixture
    def mock_st(self):
        """Mock the sentence_transformers model loading."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 4
            mock_load.return_value = mock_model
            yield mock_model

    def test_generate(self, mock_st):
        """generate should return an embedding vector."""
        mock_st.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3, 0.4]
        provider = SentenceTransformerProvider(model_name="test-model")
        result = provider.generate("hello")
        assert result == [0.1, 0.2, 0.3, 0.4]

    def test_generate_batch(self, mock_st):
        """generate_batch should return multiple vectors."""
        mock_st.encode.return_value = [
            MagicMock(tolist=lambda: [0.1, 0.2, 0.3, 0.4]),
            MagicMock(tolist=lambda: [0.5, 0.6, 0.7, 0.8]),
        ]
        provider = SentenceTransformerProvider(model_name="test-model")
        results = provider.generate_batch(["hello", "world"])
        assert len(results) == 2

    def test_embedding_dimension(self, mock_st):
        """embedding_dimension should return the model's dimension."""
        provider = SentenceTransformerProvider(model_name="test-model")
        assert provider.embedding_dimension == 4

    def test_name(self, mock_st):
        """name should return 'sentence-transformers'."""
        provider = SentenceTransformerProvider(model_name="test-model")
        assert provider.name == "sentence-transformers"

    def test_generate_empty_string(self, mock_st):
        """generate with empty string should return zero vector."""
        provider = SentenceTransformerProvider(model_name="test-model")
        result = provider.generate("")
        assert result == [0.0, 0.0, 0.0, 0.0]

    def test_import_error(self):
        """Should raise ImportError when sentence-transformers not installed."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_load.side_effect = ImportError("sentence-transformers is not installed")
            with pytest.raises(ImportError, match="sentence-transformers"):
                SentenceTransformerProvider()


# ===========================================================================
# Tests: OllamaEmbeddingProvider
# ===========================================================================


class TestOllamaEmbeddingProvider:
    """Tests for OllamaEmbeddingProvider (with mocked requests)."""

    @pytest.fixture
    def provider(self):
        """Create an OllamaEmbeddingProvider with mocked requests."""
        with patch("bfai.embeddings.OllamaEmbeddingProvider._import_requests") as mock_import:
            mock_req = MagicMock()
            # Set up the exceptions hierarchy
            mock_req.exceptions = MagicMock()
            mock_req.exceptions.RequestException = type("RequestException", (Exception,), {})
            mock_req.exceptions.ConnectionError = type("ConnectionError", (mock_req.exceptions.RequestException,), {})
            mock_req.exceptions.Timeout = type("Timeout", (mock_req.exceptions.RequestException,), {})
            # Default successful response
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
            mock_req.post.return_value = mock_resp
            mock_import.return_value = mock_req
            yield OllamaEmbeddingProvider(
                model_name="test-model",
                base_url="http://localhost:11434",
            )

    def test_generate(self, provider):
        """generate should return an embedding vector."""
        result = provider.generate("hello")
        assert result == [0.1, 0.2, 0.3]

    def test_generate_batch(self, provider):
        """generate_batch should call generate for each text."""
        # Set up alternating responses
        provider._requests.post.return_value.json.side_effect = [
            {"embedding": [0.1, 0.2, 0.3]},
            {"embedding": [0.4, 0.5, 0.6]},
        ]
        results = provider.generate_batch(["hello", "world"])
        assert len(results) == 2
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6]

    def test_embedding_dimension(self, provider):
        """embedding_dimension should return the dimension."""
        assert provider.embedding_dimension == 768

    def test_name(self, provider):
        """name should return 'ollama'."""
        assert provider.name == "ollama"

    def test_generate_empty_string(self, provider):
        """generate with empty string should return zero vector."""
        result = provider.generate("")
        assert result == [0.0] * 768

    def test_api_error_handling(self, provider):
        """Should wrap API errors in RuntimeError."""
        provider._requests.post.side_effect = provider._requests.exceptions.RequestException("API error")
        with pytest.raises(RuntimeError, match="Ollama API request failed"):
            provider.generate("hello")

    def test_connection_error_handling(self, provider):
        """Should wrap connection errors in RuntimeError."""
        provider._requests.post.side_effect = provider._requests.exceptions.ConnectionError("refused")
        with pytest.raises(RuntimeError, match="Could not connect to Ollama"):
            provider.generate("hello")

    def test_timeout_handling(self, provider):
        """Should wrap timeout errors in RuntimeError."""
        provider._requests.post.side_effect = provider._requests.exceptions.Timeout("timed out")
        with pytest.raises(RuntimeError, match="Ollama request timed out"):
            provider.generate("hello")

    def test_import_error(self):
        """Should raise ImportError when requests not installed."""
        with patch("bfai.embeddings.OllamaEmbeddingProvider._import_requests") as mock_import:
            mock_import.side_effect = ImportError("requests is not installed")
            with pytest.raises(ImportError, match="requests"):
                OllamaEmbeddingProvider()

    def test_empty_embedding_response(self, provider):
        """Should raise RuntimeError if Ollama returns empty embedding."""
        provider._requests.post.return_value.json.return_value = {}
        with pytest.raises(RuntimeError, match="empty embedding"):
            provider.generate("hello")


# ===========================================================================
# Tests: OpenAIEmbeddingProvider
# ===========================================================================


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider (with mocked client)."""

    @pytest.fixture
    def provider(self):
        """Create an OpenAIEmbeddingProvider with mocked client."""
        with patch("bfai.embeddings.OpenAIEmbeddingProvider._create_client") as mock_create:
            mock_client = MagicMock()
            mock_embedding = MagicMock()
            mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4]
            mock_resp = MagicMock()
            mock_resp.data = [mock_embedding]
            mock_client.embeddings.create.return_value = mock_resp
            mock_create.return_value = mock_client
            yield OpenAIEmbeddingProvider(
                model_name="test-model",
                api_key="sk-test",
            )

    def test_generate(self, provider):
        """generate should return an embedding vector."""
        result = provider.generate("hello")
        assert result == [0.1, 0.2, 0.3, 0.4]

    def test_generate_batch(self, provider):
        """generate_batch should return multiple vectors."""
        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1, 0.2, 0.3]
        emb2 = MagicMock()
        emb2.index = 1
        emb2.embedding = [0.4, 0.5, 0.6]
        provider._client.embeddings.create.return_value.data = [emb1, emb2]

        results = provider.generate_batch(["hello", "world"])
        assert len(results) == 2
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6]

    def test_generate_batch_empty(self, provider):
        """generate_batch with empty list should return empty list."""
        results = provider.generate_batch([])
        assert results == []

    def test_embedding_dimension(self, provider):
        """embedding_dimension should return the default dimension."""
        assert provider.embedding_dimension == 1536

    def test_name(self, provider):
        """name should return 'openai'."""
        assert provider.name == "openai"

    def test_generate_empty_string(self, provider):
        """generate with empty string should return zero vector."""
        result = provider.generate("")
        assert result == [0.0] * 1536

    def test_api_error_handling(self, provider):
        """Should wrap API errors in RuntimeError."""
        provider._client.embeddings.create.side_effect = Exception("API error")
        with pytest.raises(RuntimeError, match="OpenAI embedding failed"):
            provider.generate("hello")

    def test_import_error(self):
        """Should raise ImportError when openai not installed."""
        with patch("bfai.embeddings.OpenAIEmbeddingProvider._create_client") as mock_create:
            mock_create.side_effect = ImportError("openai is not installed")
            with pytest.raises(ImportError, match="openai"):
                OpenAIEmbeddingProvider()

    def test_batch_sorts_by_index(self, provider):
        """generate_batch should sort results by index."""
        emb1 = MagicMock()
        emb1.index = 1
        emb1.embedding = [0.4, 0.5, 0.6]
        emb2 = MagicMock()
        emb2.index = 0
        emb2.embedding = [0.1, 0.2, 0.3]
        provider._client.embeddings.create.return_value.data = [emb1, emb2]

        results = provider.generate_batch(["hello", "world"])
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6]


# ===========================================================================
# Tests: input normalization edge cases
# ===========================================================================


class TestProviderInputNormalization:
    """Tests for input type handling across providers."""

    def test_single_string(self):
        """Single string input should produce single embedding."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 4
            mock_model.encode.return_value = MagicMock()
            mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_load.return_value = mock_model

            provider = SentenceTransformerProvider()
            result = provider.generate("hello")
            assert len(result) == 4

    def test_list_of_strings(self):
        """List of strings should produce multiple embeddings."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 4
            mock_model.encode.return_value = [
                MagicMock(tolist=lambda: [0.1, 0.2, 0.3, 0.4]),
                MagicMock(tolist=lambda: [0.5, 0.6, 0.7, 0.8]),
            ]
            mock_load.return_value = mock_model

            provider = SentenceTransformerProvider()
            results = provider.generate_batch(["hello", "world"])
            assert len(results) == 2

    def test_empty_string_returns_zero_vector(self):
        """Empty string should return zero vector for all providers."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 3
            mock_load.return_value = mock_model

            provider = SentenceTransformerProvider()
            result = provider.generate("")
            assert result == [0.0, 0.0, 0.0]

    def test_empty_list_returns_empty_list(self):
        """Empty list should return empty list."""
        with patch("bfai.embeddings.SentenceTransformerProvider._load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 4
            mock_load.return_value = mock_model

            provider = SentenceTransformerProvider()
            results = provider.generate_batch([])
            assert results == []