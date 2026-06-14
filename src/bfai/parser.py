"""Markdown parser for BFAI.

Handles extraction of frontmatter, title, tags, wiki links, entities,
and other structured data from markdown note content.
"""

from __future__ import annotations

import logging
import re
from typing import NamedTuple

from bfai.entities import ExtractedEntity, extract_entities

logger = logging.getLogger(__name__)

# Pattern to match YAML-like frontmatter blocks: --- ... ---
_FRONTMATTER_PATTERN = re.compile(
    r"^---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)",
    re.DOTALL | re.MULTILINE,
)

# Pattern to match the first ATX heading (# Title)
_HEADING_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Pattern to match inline tags like #tag, #my-tag, #tag123
# Ensures the # is preceded by whitespace or start of line,
# and the tag name contains only word chars and hyphens.
_TAG_PATTERN = re.compile(r"(?:^|\s)#([a-zA-Z_][a-zA-Z0-9_-]*)")

# Pattern to match frontmatter tags value (comma-separated)
_FRONTMATTER_TAG_PATTERN = re.compile(r"[,\s]+")

# Pattern to match wiki links: [[Link Title]] or [[Link Title|Display Text]]
# Captures the link target and optional display text.
# The display text group allows zero or more chars (for [[Link|]] edge case).
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]|]*))?\]\]")


class ParsedNote(NamedTuple):
    """Result of parsing a markdown string.

    Attributes:
        title: The extracted title. Derived from frontmatter ``title``
            field, the first ``# Heading``, or an empty string if neither
            exists.
        body: The markdown body content (excluding frontmatter).
        metadata: Key-value pairs parsed from YAML-like frontmatter.
            Empty dict if no frontmatter is present.
        tags: Sorted list of unique tags extracted from both frontmatter
            and inline ``#tag`` syntax.
        wiki_links: Sorted list of unique wiki link targets extracted
            from ``[[Link Title]]`` syntax (without display text).
        entities: Sorted list of extracted entities (people,
            organizations, technologies, projects).
    """

    title: str
    body: str
    metadata: dict[str, str] = {}
    tags: list[str] = []
    wiki_links: list[str] = []
    entities: list[ExtractedEntity] = []


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML-like frontmatter from markdown content.

    Frontmatter is expected between ``---`` delimiters at the very
    beginning of the file. Each line should be in ``key: value`` format.

    Args:
        content: Raw markdown content.

    Returns:
        Dictionary of frontmatter key-value pairs. Returns an empty dict
        if no valid frontmatter is found.
    """
    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}

    frontmatter_block = match.group(1)
    metadata: dict[str, str] = {}

    for line in frontmatter_block.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Split on the first colon only
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key:
                metadata[key] = value

    return metadata


def extract_title(content: str, metadata: dict[str, str] | None = None) -> str:
    """Extract the title from markdown content.

    Priority:
    1. The ``title`` key from frontmatter metadata.
    2. The first ``# ATX heading`` in the body.
    3. Empty string if neither exists.

    Args:
        content: The markdown content to search (body-only recommended
            to avoid matching frontmatter lines).
        metadata: Optional pre-parsed frontmatter metadata. If provided,
            the ``title`` key is checked first.

    Returns:
        The extracted title, or empty string if none found.
    """
    # Priority 1: title from frontmatter
    if metadata and metadata.get("title"):
        return metadata["title"].strip()

    # Priority 2: first # ATX heading
    heading_match = _HEADING_PATTERN.search(content)
    if heading_match:
        return heading_match.group(1).strip()

    # Priority 3: no title found
    return ""


def extract_tags(content: str, metadata: dict[str, str] | None = None) -> list[str]:
    """Extract tags from markdown content.

    Tags are collected from two sources:

    1. **Inline tags**: ``#tagname`` patterns in the body text. The ``#``
       must be preceded by whitespace or be at the start of a line to
       avoid matching markdown headings (``# Title``).
    2. **Frontmatter tags**: The ``tags`` key in frontmatter metadata,
       where multiple tags are separated by commas or whitespace.

    Duplicate tags are removed, and the result is sorted alphabetically.

    Args:
        content: The markdown body content to search for inline tags.
        metadata: Optional pre-parsed frontmatter metadata to check for
            a ``tags`` key.

    Returns:
        Sorted list of unique tag strings.
    """
    tags: set[str] = set()

    # Source 1: inline tags in body content
    for match in _TAG_PATTERN.finditer(content):
        tag = match.group(1).strip()
        if tag:
            tags.add(tag)

    # Source 2: frontmatter tags metadata
    if metadata and metadata.get("tags"):
        raw_tags = metadata["tags"]
        for tag in _FRONTMATTER_TAG_PATTERN.split(raw_tags):
            tag = tag.strip()
            if tag:
                tags.add(tag)

    return sorted(tags)


def extract_wiki_links(content: str) -> list[str]:
    """Extract wiki link targets from markdown body content.

    Finds Obsidian-style wiki links in the format ``[[Link Target]]``
    or ``[[Link Target|Display Text]]``. Only the link target (the
    part before the ``|``) is returned.

    Duplicate targets are removed, and the result is sorted
    alphabetically.

    Args:
        content: The markdown body content to search for wiki links.

    Returns:
        Sorted list of unique wiki link target strings.
    """
    targets: set[str] = set()

    for match in _WIKI_LINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        if target:
            targets.add(target)

    return sorted(targets)


def strip_frontmatter(content: str) -> str:
    """Remove frontmatter from markdown content, returning only the body.

    Args:
        content: Raw markdown content possibly with frontmatter.

    Returns:
        The markdown body with frontmatter removed. If no frontmatter
        is present, returns the content unchanged.
    """
    match = _FRONTMATTER_PATTERN.match(content)
    if match:
        return match.group(2)
    return content


def parse_note(content: str) -> ParsedNote:
    """Parse a full markdown note content into its components.

    This is the main entry point for parsing. It extracts frontmatter
    metadata, determines the title, separates the body from frontmatter,
    and extracts tags, wiki links, and entities.

    Args:
        content: Raw markdown content from a note file.

    Returns:
        A ParsedNote named tuple with title, body, metadata, tags,
        wiki_links, and entities.
    """
    metadata = parse_frontmatter(content)
    body = strip_frontmatter(content)
    title = extract_title(body, metadata=metadata)
    tags = extract_tags(body, metadata=metadata)
    wiki_links = extract_wiki_links(body)
    entities = extract_entities(body)

    return ParsedNote(
        title=title,
        body=body,
        metadata=metadata,
        tags=tags,
        wiki_links=wiki_links,
        entities=entities,
    )
