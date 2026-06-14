## Overview

This project aims to build a local-first AI-native memory and knowledge system inspired by Obsidian while extending it with graph memory, semantic retrieval, automatic relationship generation, and agent-oriented APIs.

Core principles:

- Markdown is the source of truth.
    
- SQLite stores graph relationships and metadata.
    
- Qdrant stores semantic embeddings.
    
- Agents interact through APIs instead of directly reading files.
    
- Human-readable and AI-friendly.
    
- Local-first architecture.
    

---

# Architecture

```text
Markdown Vault
      |
      v
Parser & Indexer
      |
      +---- SQLite (Graph Memory)
      |
      +---- Qdrant (Semantic Memory)
      |
      v
Memory API Layer
      |
      v
Agents / Applications
```

---

# V1 Scope

Must Have:

- Markdown Storage
    
- Wiki Links
    
- Backlinks
    
- Graph Memory
    
- Tags
    
- Full Text Search
    
- Semantic Search
    
- Entity Extraction
    
- Memory APIs
    

Future Versions:

- Inferred Relationships
    
- Temporal Memory
    
- Conflict Detection
    
- Memory Importance Scoring
    

---

# Feature: Markdown Storage

## Description

Markdown files are the canonical source of truth for all knowledge stored in the system.

### M1 — Basic Markdown Loading

The system can discover and load markdown files from the vault.

Example:

```text
vault/
├── project_x.md
├── esp32.md
```

Outcome:

Knowledge can be stored in human-readable files and loaded into the system.

### M2 — Automatic Synchronization

The system automatically detects when files are created, modified, renamed, or deleted.

Example:

```text
User edits project_x.md
```

Outcome:

The memory system remains synchronized without requiring manual refreshes.

### M3 — Asset Support

The system supports associated resources such as images and documents.

Example:

```text
project_x.md
camera_diagram.png
```

Outcome:

Knowledge can reference supporting material while remaining organized.

Final Output:

```text
vault/
├── notes/
├── images/
├── documents/
└── metadata/
```

---

# Feature: Wiki Links

## Description

Allows notes to reference other notes using Obsidian-style links.

### M1 — Link Detection

The system recognizes wiki-style links inside markdown.

Example:

```md
Uses [[ESP32-S3]]
```

Outcome:

The system can identify references between notes.

### M2 — Link Resolution

The system can locate the note being referenced.

Example:

```md
[[ESP32-S3]]
```

maps to:

```text
esp32-s3.md
```

Outcome:

Links become connected to actual knowledge objects.

### M3 — Relationship Creation

Detected links become graph relationships.

Example:

```text
Project X
    EXPLICIT_LINK
ESP32-S3
```

Outcome:

Notes become interconnected and traversable.

Final Output:

```text
Project X
    ->
ESP32-S3
```

---

# Feature: Backlinks

## Description

Automatically identifies notes that reference another note.

### M1 — Backlink Discovery

The system identifies incoming references.

Example:

```text
Project X -> ESP32-S3
Project Y -> ESP32-S3
```

Outcome:

The system knows ESP32-S3 is referenced by multiple notes.

### M2 — Backlink Retrieval

Backlinks can be requested through APIs.

Example:

```python
memory.backlinks("esp32-s3")
```

returns:

```text
Project X
Project Y
```

Outcome:

Agents can discover related information.

### M3 — Retrieval Expansion

Backlinks participate in context retrieval.

Example:

Search:

```text
ESP32-S3
```

returns:

```text
ESP32-S3
Project X
Project Y
```

Outcome:

Retrieved context becomes richer.

Final Output:

```text
ESP32-S3

Referenced By:
- Project X
- Project Y
```

---

# Feature: Graph Memory

## Description

Represents knowledge as connected nodes and relationships.

### M1 — Knowledge Connections

The system can store relationships between memories.

Example:

```text
Project X USES ESP32-S3
```

Outcome:

Knowledge becomes interconnected.

### M2 — Multi-Hop Navigation

The system can follow chains of relationships.

Example:

```text
Project X
    USES
ESP32-S3

ESP32-S3
    RELATED_TO
Embedded Systems
```

Outcome:

The system can discover indirectly connected information.

### M3 — Graph-Based Retrieval

Relationships are used during retrieval.

Example:

Search:

```text
robotics projects
```

returns:

```text
Project X
ESP32-S3
Embedded Systems
```

Outcome:

Graph relationships improve retrieval quality.

Final Output:

```text
Project X
 ├─ USES ─> ESP32-S3
 ├─ USES ─> Camera
 └─ PART_OF ─> Robotics
```

---

# Feature: Semantic Search

## Description

Retrieves memories based on meaning rather than exact words.

### M1 — Embedding Generation

Knowledge is converted into vector representations.

Outcome:

The system gains semantic understanding.

### M2 — Similarity Search

Similar concepts can be retrieved.

Example:

Search:

```text
wireless robot controller
```

returns:

```text
ESP32 robotics project
```

Outcome:

Natural language retrieval becomes possible.

### M3 — Hybrid Retrieval

Keyword search and semantic search work together.

Outcome:

Higher retrieval accuracy and relevance.

Final Output:

Natural language search across the knowledge base.

---

# Relationship Types

## Structural

```text
PART_OF
CONTAINS
PARENT_OF
CHILD_OF
```

## Dependency

```text
DEPENDS_ON
REQUIRES
USES
PROVIDES
IMPLEMENTS
```

## Semantic

```text
RELATED_TO
SIMILAR_TO
REFERENCES
MENTIONS
DESCRIBES
```

## Temporal

```text
PRECEDES
FOLLOWS
REPLACED_BY
DERIVED_FROM
```

## Causal

```text
CAUSES
INFLUENCES
RESULTS_IN
```

## Ownership

```text
CREATED_BY
OWNED_BY
ASSIGNED_TO
```

## Knowledge

```text
SUPPORTS
CONTRADICTS
CONFIRMS
QUESTIONED_BY
```

## AI Specific

```text
EXPLICIT_LINK
INFERRED_LINK
MEMORY_OF
OBSERVED_FROM
```

---

# Memory Storage Flow

## API

```python
memory.create()
```

## Flow

```text
Agent
  |
  v
Memory API
  |
  v
Markdown Writer
  |
  +--> Save Markdown
  |
  +--> Extract Links
  |
  +--> Extract Tags
  |
  +--> Extract Entities
  |
  +--> Generate Graph Relationships
  |
  +--> Generate Embeddings
  |
  +--> Store Metadata in SQLite
  |
  +--> Store Embeddings in Qdrant
```

Outcome:

A newly created memory becomes searchable, linked, and retrievable.

---

# Context Retrieval Flow

## API

```python
memory.retrieve(
    query,
    top_k=10,
    max_hops=2
)
```

## Flow

```text
Agent Query
      |
      v
Embedding Generation
      |
      v
Qdrant Similarity Search
      |
      v
Candidate Memories
      |
      v
Graph Expansion
      |
      v
Backlink Expansion
      |
      v
Ranking
      |
      v
Context Assembly
      |
      v
Return Context
```

Outcome:

Agents receive both directly relevant memories and connected supporting knowledge.

---

# Context Ranking

Ranking factors:

```text
semantic_similarity
importance
confidence
recency
access_frequency
graph_distance
```

Example:

final_score =  
0.40 semantic_similarity +  
0.20 importance +  
0.15 confidence +  
0.10 recency +  
0.10 access_frequency +  
0.05 graph_distance

---

# Public Memory APIs

```python
memory.create()
memory.update()
memory.delete()
memory.search()
memory.retrieve()
memory.related()
memory.backlinks()
memory.expand()
```

---

# V1 Goal

Deliver a local-first AI memory platform capable of:

- Markdown knowledge storage
    
- Wiki links
    
- Backlinks
    
- Graph relationships
    
- Full-text search
    
- Semantic retrieval
    
- Qdrant integration
    
- Agent memory APIs
    
- Multi-hop retrieval
    

while keeping markdown files as the canonical source of truth.