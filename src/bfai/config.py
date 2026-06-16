"""Configuration management for BFAI.

Uses *pydantic-settings* ``BaseSettings`` to load all configuration from
environment variables (and ``.env`` files).  Legacy module-level constants
are kept for backward compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── internal helpers  ────────────────────────────────────────────────────

_MODEL_DEFAULTS: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "ollama": "nomic-embed-text",
}

VAULT_SUBDIRS: tuple[str, ...] = ("notes", "documents", "images", "metadata")


def get_vault_path() -> Path:
    """Return the absolute vault path from env or default."""
    raw = os.getenv("BFAI_VAULT_PATH", str(Path.cwd() / "vault"))
    return Path(raw).expanduser().resolve()


# Legacy env-var name constants (for introspection / backward compat).
ENV_VAULT_PATH = "BFAI_VAULT_PATH"
ENV_DB_PATH = "BFAI_DB_PATH"
ENV_EMBEDDING_MODEL = "BFAI_EMBEDDING_MODEL"
ENV_EMBEDDING_PROVIDER = "BFAI_EMBEDDING_PROVIDER"
ENV_EMBEDDING_BATCH_SIZE = "BFAI_EMBEDDING_BATCH_SIZE"
ENV_EMBEDDING_DIMENSIONS = "BFAI_EMBEDDING_DIMENSIONS"
ENV_OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_SYNC_INTERVAL = "BFAI_SYNC_INTERVAL"
ENV_SYNC_BATCH_SIZE = "BFAI_SYNC_BATCH_SIZE"
ENV_SYNC_MAX_WORKERS = "BFAI_SYNC_MAX_WORKERS"
ENV_CHUNK_SIZE = "BFAI_CHUNK_SIZE"
ENV_CHUNK_OVERLAP = "BFAI_CHUNK_OVERLAP"
ENV_CHUNK_BY_LINES = "BFAI_CHUNK_BY_LINES"

# Gunita env-var name constants.
ENV_GUNITA_HOST = "GUNITA_HOST"
ENV_GUNITA_PORT = "GUNITA_PORT"
ENV_GUNITA_RELOAD = "GUNITA_RELOAD"
ENV_GUNITA_GRAPH_MAX_NODES = "GUNITA_GRAPH_MAX_NODES"
ENV_GUNITA_API_KEY = "GUNITA_API_KEY"
ENV_GUNITA_EXTRA_VAULTS = "GUNITA_EXTRA_VAULTS"


# ── Settings class  ──────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Centralised settings for both **BFAI** and **Gunita**."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── vault ──────────────────────────────────────────────────────────
    bfai_vault_path: Path = Field(
        default=Path.cwd() / "vault",
        description="Path to the vault directory (BFAI_VAULT_PATH).",
    )
    bfai_db_path: Path | None = Field(
        default=None,
        description="Explicit database path (BFAI_DB_PATH).  Falls back to <vault>/metadata/bfai.db.",
    )

    # ── embedding ──────────────────────────────────────────────────────
    bfai_embedding_provider: str = Field(
        default="sentence-transformers", alias="BFAI_EMBEDDING_PROVIDER"
    )
    bfai_embedding_model: str | None = Field(
        default=None, alias="BFAI_EMBEDDING_MODEL"
    )
    bfai_embedding_batch_size: int = Field(default=32, alias="BFAI_EMBEDDING_BATCH_SIZE")
    bfai_embedding_dimensions: int = Field(default=768, alias="BFAI_EMBEDDING_DIMENSIONS")

    # ── API ────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # ── sync ───────────────────────────────────────────────────────────
    bfai_sync_interval: int = Field(default=60, alias="BFAI_SYNC_INTERVAL")
    bfai_sync_batch_size: int = Field(default=50, alias="BFAI_SYNC_BATCH_SIZE")
    bfai_sync_max_workers: int = Field(default=4, alias="BFAI_SYNC_MAX_WORKERS")

    # ── chunking ───────────────────────────────────────────────────────
    bfai_chunk_size: int = Field(default=500, alias="BFAI_CHUNK_SIZE")
    bfai_chunk_overlap: int = Field(default=50, alias="BFAI_CHUNK_OVERLAP")
    bfai_chunk_by_lines: bool = Field(default=True, alias="BFAI_CHUNK_BY_LINES")

    # ── Gunita ─────────────────────────────────────────────────────────
    gunita_host: str = Field(default="0.0.0.0", alias="GUNITA_HOST")
    gunita_port: int = Field(default=8080, alias="GUNITA_PORT")
    gunita_reload: bool = Field(default=False, alias="GUNITA_RELOAD")
    gunita_graph_max_nodes: int = Field(default=100, alias="GUNITA_GRAPH_MAX_NODES")
    gunita_api_key: str = Field(default="", alias="GUNITA_API_KEY")
    gunita_extra_vaults: str = Field(default="", alias="GUNITA_EXTRA_VAULTS")

    # ── backward‑compat aliases (used by gunita code) ───────────────────

    @property
    def host(self) -> str:
        """Alias for ``gunita_host`` (backward compat)."""
        return self.gunita_host

    @property
    def port(self) -> int:
        """Alias for ``gunita_port`` (backward compat)."""
        return self.gunita_port

    @property
    def reload(self) -> bool:
        """Alias for ``gunita_reload`` (backward compat)."""
        return self.gunita_reload

    @property
    def api_key(self) -> str:
        """Alias for ``gunita_api_key`` (backward compat)."""
        return self.gunita_api_key

    @property
    def extra_vaults(self) -> list[str]:
        """Backward‑compat: return the extra vaults as a list of path strings."""
        return [str(p) for p in self.extra_vaults_list]

    @property
    def qdrant_url(self) -> str:
        """Backward‑compat Qdrant URL (read from env or default)."""
        import os
        return os.environ.get("BFAI_QDRANT_URL", "http://localhost:6333")

    @property
    def graph_max_nodes(self) -> int:
        """Alias for ``gunita_graph_max_nodes`` (backward compat)."""
        return self.gunita_graph_max_nodes

    # ── computed / resolved properties ──────────────────────────────────

    @property
    def vault_path(self) -> Path:
        """Resolve the vault path to an absolute directory."""
        return self.bfai_vault_path.expanduser().resolve()

    @property
    def database_path(self) -> Path:
        """Return the database path – explicit or fallback."""
        if self.bfai_db_path:
            return self.bfai_db_path.expanduser().resolve()
        return self.vault_path / "metadata" / "bfai.db"

    @property
    def embedding_model(self) -> str:
        """Resolve the embedding model string.

        If explicitly set, use it; otherwise pick the default for the
        active provider.
        """
        if self.bfai_embedding_model:
            return self.bfai_embedding_model
        return _MODEL_DEFAULTS.get(self.bfai_embedding_provider, _MODEL_DEFAULTS["ollama"])

    @property
    def extra_vaults_list(self) -> list[Path]:
        """Parse ``GUNITA_EXTRA_VAULTS`` into a list of resolved paths."""
        raw = self.gunita_extra_vaults
        if not raw:
            return []
        return [Path(p.strip()).expanduser().resolve() for p in raw.split(",") if p.strip()]

    @property
    def all_vault_paths(self) -> list[Path]:
        """All vault paths: primary + extras."""
        paths: list[Path] = [self.vault_path]
        paths.extend(self.extra_vaults_list)
        return paths

    # ── validators ──────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_port(self) -> "Settings":
        if not (1 <= self.gunita_port <= 65535):
            msg = f"GUNITA_PORT must be between 1 and 65535, got {self.gunita_port}"
            raise ValueError(msg)
        return self


# ── singleton  ───────────────────────────────────────────────────────────

settings = Settings()

# ── backward-compatible module-level constants  ──────────────────────────

VAULT_PATH: Path = settings.vault_path
DATABASE_PATH: Path = settings.database_path
EMBEDDING_MODEL: str = settings.embedding_model
EMBEDDING_PROVIDER: str = settings.bfai_embedding_provider
EMBEDDING_BATCH_SIZE: int = settings.bfai_embedding_batch_size
EMBEDDING_DIMENSIONS: int = settings.bfai_embedding_dimensions
OLLAMA_BASE_URL: str = settings.ollama_base_url
OPENAI_API_KEY: str = settings.openai_api_key
SYNC_INTERVAL: int = settings.bfai_sync_interval
SYNC_BATCH_SIZE: int = settings.bfai_sync_batch_size
SYNC_MAX_WORKERS: int = settings.bfai_sync_max_workers
CHUNK_SIZE: int = settings.bfai_chunk_size
CHUNK_OVERLAP: int = settings.bfai_chunk_overlap
CHUNK_BY_LINES: bool = settings.bfai_chunk_by_lines

# ── export helpers  ──────────────────────────────────────────────────────
__all__ = [
    "Settings",
    "settings",
    "VAULT_SUBDIRS",
    "get_vault_path",
    "VAULT_PATH",
    "DATABASE_PATH",
    "EMBEDDING_MODEL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_BATCH_SIZE",
    "EMBEDDING_DIMENSIONS",
    "OLLAMA_BASE_URL",
    "OPENAI_API_KEY",
    "SYNC_INTERVAL",
    "SYNC_BATCH_SIZE",
    "SYNC_MAX_WORKERS",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "CHUNK_BY_LINES",
    # Env-var name constants
    "ENV_VAULT_PATH",
    "ENV_DB_PATH",
    "ENV_EMBEDDING_MODEL",
    "ENV_EMBEDDING_PROVIDER",
    "ENV_EMBEDDING_BATCH_SIZE",
    "ENV_EMBEDDING_DIMENSIONS",
    "ENV_OLLAMA_BASE_URL",
    "ENV_OPENAI_API_KEY",
    "ENV_SYNC_INTERVAL",
    "ENV_SYNC_BATCH_SIZE",
    "ENV_SYNC_MAX_WORKERS",
    "ENV_CHUNK_SIZE",
    "ENV_CHUNK_OVERLAP",
    "ENV_CHUNK_BY_LINES",
    "ENV_GUNITA_HOST",
    "ENV_GUNITA_PORT",
    "ENV_GUNITA_RELOAD",
    "ENV_GUNITA_GRAPH_MAX_NODES",
    "ENV_GUNITA_API_KEY",
    "ENV_GUNITA_EXTRA_VAULTS",
]