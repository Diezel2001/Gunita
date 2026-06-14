"""Entity extraction framework for BFAI.

Provides entity types, extracted entity model, and pattern-based entity
extraction for identifying people, organizations, technologies, and
projects within markdown note content.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Pattern

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities that can be extracted from note content."""

    PERSON = "person"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    PROJECT = "project"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ExtractedEntity:
    """A single entity extracted from note content.

    Attributes:
        entity_type: The type/category of the entity.
        name: The extracted entity name.
        context: The surrounding text snippet for disambiguation.
    """

    entity_type: EntityType
    name: str
    context: str = ""


# ---------------------------------------------------------------------------
# Pattern-based extraction
# ---------------------------------------------------------------------------

# People: honorific + name patterns
_PERSON_PATTERNS: list[Pattern[str]] = [
    re.compile(
        r"(?:Dr\.|Professor|Prof\.|Mr\.|Mrs\.|Ms\.|Capt\.|Col\.|Gen\.|Sen\.|Rep\.)"
        r"\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
    ),
]

# Organizations: known suffix patterns, university/institute names
_ORGANIZATION_PATTERNS: list[Pattern[str]] = [
    re.compile(
        r"[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*"
        r"\s+(?:Inc|Corp|LLC|Ltd|Foundation|Institute|Group|Team"
        r"|Organization|Agency|Commission|Authority|Association"
        r"|Committee|Department|Division|Board|Council|Laboratory"
        r"|Lab|GmbH|SA|PLC)"
    ),
    re.compile(
        r"(?:The\s+)?[A-Z][A-Za-z]*\s+(?:University|College|School|Academy)"
        r"(?:\s+of\s+[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*)?"
    ),
]

# Technologies: versioned names (e.g. ESP32-S3), common tech keywords
_TECHNOLOGY_PATTERNS: list[Pattern[str]] = [
    # Versioned names like ESP32-S3, SAMD21G18A, STM32F407
    re.compile(r"\b[A-Z][A-Za-z0-9]*(?:\d+[-_]\w+)+\b"),
    # Versioned names like ESP32, STM32, SAMD21, ARM7
    re.compile(r"\b[A-Z]{2,}\d+[A-Za-z]*\b"),
    re.compile(r"\b[A-Z][a-z]+\d+(?:[A-Za-z]\d*)*\b"),
    re.compile(
        r"\b(?:Python|JavaScript|TypeScript|Rust|Go(?!ing\b)|Java"
        r"|C\+\+|C#|Ruby|PHP|Swift|Kotlin|Scala|Elixir|Haskell"
        r"|Clojure|Dart|Flutter|React|Angular|Vue|Svelte|Django"
        r"|Flask|FastAPI|Spring|Docker|Kubernetes|AWS|GCP(?!\b)"
        r"|Azure|SQLite|Qdrant|PostgreSQL|MySQL|MongoDB|Redis"
        r"|Kafka|TensorFlow|PyTorch|OpenAI(?!\b)|Ollama"
        r"|SentenceTransformers|LangChain|LlamaIndex)\b"
    ),
]

# Projects: "Project [Name]", "[Name] Project" patterns
_PROJECT_PATTERNS: list[Pattern[str]] = [
    re.compile(r"Project\s+[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)?"),
    re.compile(r"[A-Z][a-z]+\s+Project"),
]

# Map entity types to their patterns for iteration
_ENTITY_PATTERNS: dict[EntityType, list[Pattern[str]]] = {
    EntityType.PERSON: _PERSON_PATTERNS,
    EntityType.ORGANIZATION: _ORGANIZATION_PATTERNS,
    EntityType.TECHNOLOGY: _TECHNOLOGY_PATTERNS,
    EntityType.PROJECT: _PROJECT_PATTERNS,
}

# ---------------------------------------------------------------------------
# Known entity sets (can be extended at runtime)
# ---------------------------------------------------------------------------

# Known technology/software names that may not match regex patterns
_KNOWN_TECHNOLOGIES: set[str] = {
    "C++",
    "C#",
    ".NET",
    "Node.js",
    "Next.js",
    "Nuxt.js",
    "JQuery",
    "Jira",
    "GitHub",
    "GitLab",
    "Bitbucket",
    "VSCode",
    "VS Code",
    "IntelliJ",
    "PyCharm",
    "Jupyter",
    "Linux",
    "macOS",
    "Windows",
    "Arduino",
    "Raspberry Pi",
    "ESP32",
}


def extract_entities(
    content: str,
    known_technologies: set[str] | None = None,
) -> list[ExtractedEntity]:
    """Extract entities from markdown body content.

    Searches the content using predefined regex patterns and known entity
    sets to identify people, organizations, technologies, and projects.

    Duplicate entities (same type + name) are removed, and the result is
    sorted by entity type then name.

    Args:
        content: The markdown body content to search.
        known_technologies: Optional set of additional known technology
            names to consider. Merged with the built-in set.

    Returns:
        Sorted list of unique ExtractedEntity instances.
    """
    if not content:
        return []

    found: set[tuple[EntityType, str]] = set()
    context_size = 60  # characters of surrounding context

    # 1. Pattern-based extraction
    for entity_type, patterns in _ENTITY_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(content):
                name = match.group(0).strip()
                if not name:
                    continue

                # Compute context snippet
                start = max(0, match.start() - context_size)
                end = min(len(content), match.end() + context_size)
                context = content[start:end].strip().replace("\n", " ")

                found.add((entity_type, name, context))

    # 2. Known technology lookups
    techs = _KNOWN_TECHNOLOGIES | (known_technologies or set())
    for tech in techs:
        # Case-insensitive search for known technologies
        pattern = re.compile(re.escape(tech), re.IGNORECASE)
        for match in pattern.finditer(content):
            # Verify it's a whole-word match
            start_char = content[match.start() - 1] if match.start() > 0 else " "
            end_char = content[match.end()] if match.end() < len(content) else " "
            if start_char.isalnum() or end_char.isalnum():
                continue  # Part of a larger word

            actual_name = match.group(0)
            start_ctx = max(0, match.start() - context_size)
            end_ctx = min(len(content), match.end() + context_size)
            context = content[start_ctx:end_ctx].strip().replace("\n", " ")

            found.add((EntityType.TECHNOLOGY, actual_name, context))

    # 3. Build result sorted by entity type then name
    seen: set[tuple[EntityType, str]] = set()
    result: list[ExtractedEntity] = []

    for entity_type, name, context in sorted(
        found, key=lambda x: (x[0].value, x[1].lower())
    ):
        key = (entity_type, name)
        if key not in seen:
            seen.add(key)
            result.append(
                ExtractedEntity(
                    entity_type=entity_type,
                    name=name,
                    context=context,
                )
            )

    return result