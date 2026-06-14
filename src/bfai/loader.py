"""Markdown loader for BFAI.

Handles discovery and loading of markdown files from the vault.
Provides functions to list, load, and iterate over notes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from bfai.models import Note
from bfai.parser import parse_note
from bfai.vault import get_vault

logger = logging.getLogger(__name__)


def _notes_dir() -> Path:
    """Return the path to the vault's notes directory."""
    return get_vault() / "notes"


def list_notes() -> list[Path]:
    """Discover all markdown files in the vault's notes directory.

    Returns:
        Sorted list of paths to all .md files in the notes directory.
        Returns an empty list if the notes directory does not exist.
    """
    notes_path = _notes_dir()
    if not notes_path.exists():
        logger.debug("Notes directory does not exist: %s", notes_path)
        return []

    md_files = sorted(notes_path.glob("*.md"))
    logger.debug("Discovered %d markdown file(s) in %s", len(md_files), notes_path)
    return md_files


def load_note(path: Path) -> Note:
    """Load a single markdown file into a Note object.

    Args:
        path: Absolute or relative path to the .md file.

    Returns:
        A Note populated with the file's content, path, and filesystem
        timestamps.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a .md file.
    """
    resolved = path.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"Note file not found: {resolved}")

    if resolved.suffix.lower() != ".md":
        raise ValueError(f"Not a markdown file: {resolved}")

    content = resolved.read_text(encoding="utf-8")

    # Parse frontmatter, title, and body from the raw content
    parsed = parse_note(content)

    stat = resolved.stat()
    updated_at = datetime.fromtimestamp(stat.st_mtime)

    note = Note(
        path=resolved,
        content=content,
        body=parsed.body,
        title=parsed.title or resolved.stem,
        metadata=parsed.metadata,
        tags=parsed.tags,
        wiki_links=parsed.wiki_links,
        entities=parsed.entities,
        updated_at=updated_at,
    )
    logger.debug("Loaded note: %s (%d chars)", note.title, len(content))
    return note


def load_all_notes() -> list[Note]:
    """Discover and load all markdown notes from the vault.

    Returns:
        List of Note objects for every .md file in the notes directory.
        Returns an empty list if the notes directory does not exist
        or contains no markdown files.
    """
    paths = list_notes()
    notes: list[Note] = []
    for filepath in paths:
        try:
            note = load_note(filepath)
            notes.append(note)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("Skipping %s: %s", filepath, exc)
            continue

    logger.info("Loaded %d note(s) from vault", len(notes))
    return notes