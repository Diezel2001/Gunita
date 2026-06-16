"""Data models for BFAI.

Provides the core Note model that represents a markdown note
discovered in or created within the vault.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from bfai.entities import ExtractedEntity

logger = logging.getLogger(__name__)


@dataclass
class Note:
    """Represents a markdown note in the vault.

    Attributes:
        id: UUID uniquely identifying this note across the system.
        path: Absolute filesystem path to the note.
        content: Raw markdown content of the note.
        body: Markdown body content with frontmatter stripped.
        title: Extracted or filename-based title. Defaults to the stem
            of the filename if no frontmatter title is present.
        metadata: Optional frontmatter key-value pairs.
        tags: Sorted list of unique tags extracted from inline ``#tag``
            syntax and frontmatter.
        wiki_links: Sorted list of unique wiki link targets extracted
            from ``[[Link Title]]`` syntax.
        entities: Sorted list of extracted entities (people,
            organizations, technologies, projects).
        created_at: Timestamp when the note was first created.
        updated_at: Timestamp when the note was last modified.
    """

    path: Path
    content: str
    body: str = ""
    id: str = ""
    title: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    wiki_links: list[str] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        """Derive default title and UUID if not provided."""
        if not self.title:
            self.title = self.path.stem
        if not self.id:
            self.id = uuid4().hex
        if not self.body:
            self.body = self.content

    @property
    def filename(self) -> str:
        """Return the filename (e.g., 'project_x.md')."""
        return self.path.name

    @property
    def extension(self) -> str:
        """Return the file extension (e.g., '.md')."""
        return self.path.suffix


@dataclass
class Chunk:
    """A text chunk from a note for embedding.

    Attributes:
        chunk_id: Unique ID for this chunk (``{note_id}_chunk_{index}``).
        text: The chunk text content (section heading + paragraph).
        note_id: The ID of the note this chunk belongs to.
        section_heading: The markdown heading for this section (current heading only).
        heading_path: Full breadcrumb path of headings from the note title
            down to the current section, e.g. ``["Computer Vision", "CNNs", "Architecture"]``.
        chunk_index: Sequential index of this chunk within the note.
    """

    chunk_id: str
    text: str
    note_id: str
    section_heading: str
    chunk_index: int
    heading_path: list[str] = field(default_factory=list)
