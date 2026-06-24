"""Vault module for BFAI.

Handles vault directory initialization and provides access
to the vault's subdirectory structure.
"""

import logging
from pathlib import Path

from bfai.config import settings, VAULT_SUBDIRS, get_vault_path

logger = logging.getLogger(__name__)


def ensure_vault(vault_path: Path | str | None = None) -> Path:
    """Ensure the vault directory structure exists.

    Creates the vault root and all required subdirectories
    (notes, images, documents, metadata) if they don't exist.

    Args:
        vault_path: Optional custom path for the vault. If ``None``,
            uses the default resolution from ``settings.vault_path``.

    Returns:
        Path to the vault root directory.

    Raises:
        OSError: If directory creation fails due to permissions or other OS errors.
    """
    if vault_path is None:
        vault_path = settings.vault_path
    else:
        vault_path = Path(vault_path).resolve()

    vault_path.mkdir(parents=True, exist_ok=True)

    for subdir in VAULT_SUBDIRS:
        subdir_path = vault_path / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured vault subdirectory: %s", subdir_path)

    logger.info("Vault initialized at: %s", vault_path)
    return vault_path


def get_vault() -> Path:
    """Get the vault path without ensuring it exists.

    Re-reads from the environment on every call so callers that set
    ``BFAI_VAULT_PATH`` at runtime (e.g. the writer module or tests)
    are honoured. For most purposes the ``settings.vault_path`` property
    should be used instead.

    Returns:
        Path to the vault root directory.
    """
    return get_vault_path()
