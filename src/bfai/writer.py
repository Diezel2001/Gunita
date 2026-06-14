"""Markdown writer for BFAI.

Handles creation, updating, and deletion of markdown notes in the vault.
Provides functions to write notes to the vault's notes directory.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from bfai.loader import _notes_dir, load_note
from bfai.models import Note
from bfai.parser import parse_note

logger = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    """Convert a title to a filesystem-safe slug.

    Replaces non-alphanumeric characters (except hyphens and underscores)
    with hyphens, collapses multiple hyphens, strips leading/trailing
    hyphens, and lowercases the result.

    Args:
        title: The title to slugify.

    Returns:
        A safe filename stem.
    """
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in title)
    slug = "-".join(filter(None, slug.split("-")))
    slug = slug.strip("-").lower()
    return slug if slug else "untitled"


def _metadata_to_frontmatter(metadata: dict[str, str]) -> str:
    """Convert a metadata dictionary to YAML-like frontmatter string.

    Args:
        metadata: Key-value pairs to convert.

    Returns:
        A string formatted as YAML frontmatter, or empty string if
        metadata is empty.
    """
    if not metadata:
        return ""

    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("---\n")
    return "\n".join(lines)


def _build_content(content: str, metadata: dict[str, str]) -> str:
    """Build the full file content including optional frontmatter.

    Args:
        content: The markdown body content.
        metadata: Optional frontmatter key-value pairs.

    Returns:
        Full content string with frontmatter prepended if metadata
        is non-empty.
    """
    frontmatter = _metadata_to_frontmatter(metadata)
    if frontmatter:
        return frontmatter + content
    return content


def _resolve_note_path(title: str) -> Path:
    """Resolve a title to its expected filesystem path.

    Args:
        title: The note title (slugified to determine filename).

    Returns:
        The expected absolute path in the vault's notes directory.
    """
    notes_dir = _notes_dir()
    slug = _slugify(title)
    return (notes_dir / slug).with_suffix(".md")


def create_note(
    title: str,
    content: str,
    metadata: dict[str, str] | None = None,
    exist_ok: bool = False,
) -> Note:
    """Create a new markdown note in the vault.

    The title is slugified to determine the filename. For example,
    "My Project" becomes ``my-project.md``.

    Args:
        title: The note title. Used to generate the filename and set
            the Note's title attribute.
        content: The markdown body content.
        metadata: Optional frontmatter key-value pairs.
        exist_ok: If False (default), raise FileExistsError when a note
            with the same slugified title already exists.

    Returns:
        The newly created Note object with id, created_at, and
        updated_at populated.

    Raises:
        FileExistsError: If a note with the same slugified filename
            already exists and ``exist_ok`` is False.
        OSError: If file creation fails due to permissions or other
            OS errors.
    """
    resolved = _resolve_note_path(title)

    if not exist_ok and resolved.exists():
        raise FileExistsError(
            f"Note already exists at {resolved}. Use exist_ok=True to overwrite."
        )

    safe_metadata = metadata or {}
    body = _build_content(content, safe_metadata)

    # Ensure the notes directory exists
    resolved.parent.mkdir(parents=True, exist_ok=True)

    resolved.write_text(body, encoding="utf-8")
    logger.info("Created note: %s -> %s", title, resolved)

    now = datetime.now()
    return Note(
        path=resolved,
        content=body,
        body=body,
        title=title,
        metadata=safe_metadata,
        created_at=now,
        updated_at=now,
    )


def update_note(note: Note, content: str | None = None) -> Note:
    """Update an existing markdown note's content on disk.

    Args:
        note: The Note object to update. The Note's path must point
            to an existing file.
        content: New markdown body content. If None, the existing
            content from the Note object is used.

    Returns:
        The updated Note object with new content, preserved metadata,
        and updated updated_at timestamp.

    Raises:
        FileNotFoundError: If the note file does not exist on disk.
        ValueError: If the path is not a markdown file.
    """
    resolved = note.path.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"Note file not found: {resolved}")

    if resolved.suffix.lower() != ".md":
        raise ValueError(f"Not a markdown file: {resolved}")

    new_content = content if content is not None else note.content
    body = _build_content(new_content, note.metadata)

    resolved.write_text(body, encoding="utf-8")
    logger.info("Updated note: %s", note.title)

    return Note(
        path=resolved,
        content=body,
        body=body,
        title=note.title,
        metadata=note.metadata,
        id=note.id,
        created_at=note.created_at,
        updated_at=datetime.now(),
    )


def delete_note(note: Note | str) -> None:
    """Delete a markdown note from the vault.

    Args:
        note: Either a Note object or a string title to delete.
            If a string, it is slugified to locate the file.

    Raises:
        FileNotFoundError: If the note file does not exist.
        OSError: If file deletion fails.
    """
    if isinstance(note, Note):
        resolved = note.path.resolve()
    else:
        resolved = _resolve_note_path(note)

    if not resolved.exists():
        raise FileNotFoundError(f"Note file not found: {resolved}")

    resolved.unlink()
    logger.info("Deleted note: %s", resolved.name)


def load_note_by_title(title: str) -> Note:
    """Load a note from the vault by its title.

    The title is slugified to determine the filename before loading.

    Args:
        title: The note title to look up.

    Returns:
        The loaded Note object.

    Raises:
        FileNotFoundError: If no note with the given title exists.
    """
    resolved = _resolve_note_path(title)
    return load_note(resolved)