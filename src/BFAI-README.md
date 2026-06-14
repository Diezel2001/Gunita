# BFAI — Brain For AI

A AI-native memory and knowledge system for Agent Memory/Context Management.

# BFAI Usage Guide

> **Version:** 0.1.0 | **Status:** Feature-complete V1 (91.4%)  
> **Remaining (planned):** AI-Native Features (Inferred Relationships, Importance Scoring, Temporal Relationships, Conflict Detection)

## Requirements Overview

### ✅ Required (Core — works immediately)

- **Python 3.11+**
- **No external database needed** — BFAI uses **SQLite** (bundled with Python) for graph storage, full-text search (FTS5), and metadata. The SQLite database is created automatically in `vault/metadata/bfai.db`.
- **No server setup** — the vault is just markdown files on disk.

### ⚡ Optional (adds semantic search)

These are only needed if you want vector/semantic search features (`semantic_search()`, `hybrid_search()`, `retrieve()` with hybrid mode):

- **Qdrant** — a vector database for semantic embeddings. You need a running Qdrant instance (Docker or native) **and** the `qdrant-client` pip package.
- **An embedding provider** — one of:
  - `sentence-transformers` (local, no external services)
  - `ollama` (local LLM server)
  - `openai` (cloud API)

All core features (**create**, **update**, **delete**, **search** (keyword/FTS5), **related**, **backlinks**, **expand**) work **without** Qdrant or any embedding provider.

---

## Table of Contents

1. [What Is BFAI?](#what-is-bfai)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Embedding Providers](#embedding-providers)
6. [API Reference](#api-reference)
   - [create()](#1-create)
   - [update()](#2-update)
   - [delete()](#3-delete)
   - [search()](#4-search)
   - [semantic_search()](#5-semantic_search)
   - [hybrid_search()](#6-hybrid_search)
   - [retrieve()](#7-retrieve)
   - [related()](#8-related)
   - [backlinks()](#9-backlinks)
   - [expand()](#10-expand)
7. [Practical Scripts](#practical-scripts)
   - [Ingest a Directory of Markdown Files](#script-1-bulk-ingest-markdown-files)
   - [Interactive Knowledge Explorer](#script-2-interactive-knowledge-explorer)
   - [Sync & Watch Vault for Changes](#script-3-file-watcher-daemon)
   - [Embedding-Based Similarity Search](#script-4-semantic-similarity-search)
   - [Agent Context Retrieval](#script-5-agent-context-retriever)
8. [Vault Structure](#vault-structure)
9. [Relationship Types](#relationship-types)
10. [Testing](#testing)

---

## What Is BFAI?

BFAI (Brain For AI) is a **local-first, AI-native memory and knowledge system** inspired by Obsidian. It stores knowledge as plain markdown files and layers on top:

- **Graph memory** — notes connected by relationships (stored in SQLite)
- **Semantic memory** — meaning-based retrieval via vector embeddings (stored in Qdrant)
- **Agent-oriented APIs** — a unified `memory.*` API so agents don't need to read files directly
- **Automatic synchronization** — detects file changes and re-indexes incrementally

### Architecture

```
Markdown Vault  (your .md files — the source of truth)
      |
      v
Parser & Indexer  (tags, wiki links, entities)
      |
      +---- SQLite  (graph relationships, metadata, FTS5 full-text search)
      |
      +---- Qdrant  (semantic embeddings for vector search)
      |
      v
Memory API Layer  (memory.create(), memory.search(), memory.retrieve(), ...)
      |
      v
Agents / Applications
```

---

## Installation

### Prerequisites

- Python 3.11+
- pip

### Basic Install

```bash
# Clone the repository
cd BFAI

# Install with dev dependencies
pip install -e ".[dev]"
```

### Optional Dependencies (for Semantic Search)

Install at least one embedding provider and Qdrant:

```bash
# SentenceTransformers (local, no external services)
pip install sentence-transformers

# Qdrant vector database client
pip install qdrant-client

# Or for Ollama (local LLM server)
pip install requests

# Or for OpenAI
pip install openai
```

You can also install everything at once:

```bash
pip install -e ".[dev]" sentence-transformers qdrant-client requests openai
```

### Running Qdrant

For semantic search, you need a running Qdrant instance. The easiest way is via Docker:

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
```

Or without Docker, install Qdrant natively — see [qdrant.tech](https://qdrant.tech).

---

## Quick Start

```python
from bfai.memory import create, search, retrieve, reindex_all
from bfai.vault import ensure_vault

# 1. Initialize the vault
vault_path = ensure_vault()
print(f"Vault ready at: {vault_path}")

# 2. Create a few notes
create(
    title="ESP32-S3 Robot Controller",
    content="""
# ESP32-S3 Robot Controller

Using an [[ESP32-S3]] to build a wireless robot controller.

#robotics #esp32

The project uses MicroPython and WebSockets for real-time control.
Key components:
- ESP32-S3 microcontroller
- L298N motor driver
- 6V battery pack
""",
    tags=["robotics", "esp32", "iot"],
)

create(
    title="Project Overview",
    content="""
# Robotics Project Overview

This is a collection of [[ESP32-S3 Robot Controller]] related projects.
Focusing on embedded systems and IoT.

#robotics #embedded-systems
""",
)

# 3. Reindex everything
reindex_all()

# 4. Search by keyword
results = search("robot controller")
for r in results:
    print(f"  [{r['combined_score']:.3f}] {r['title']}")

# 5. Full context retrieval (hybrid search + backlinks + graph neighbors)
context = retrieve("wireless robot", top_k=5, max_hops=2)
for item in context:
    print(f"  [{item['source']:>8}] {item['title']}")
```

---

## Configuration

BFAI is configured through environment variables. You can set them in your shell, or — much more conveniently — use a **`.env` file** at the project root. BFAI loads `.env` automatically on startup via `python-dotenv`.

### Quick Start with .env

Copy the example file and edit to suit:

```bash
cp .env.example .env
```

Then fill in the values you need. The `.env` file is ignored by git (listed in `.gitignore`), so your secrets stay local.

### All Configuration Variables

| Variable | Default | Description |
|---|---|---|
| `BFAI_VAULT_PATH` | `./vault/` (relative to CWD) | Path to the markdown vault |
| `BFAI_EMBEDDING_PROVIDER` | `"sentence-transformers"` | `"sentence-transformers"`, `"ollama"`, or `"openai"` |
| `BFAI_EMBEDDING_MODEL` | provider-specific | Model name (e.g. `"all-MiniLM-L6-v2"` for sentence-transformers) |
| `BFAI_OLLAMA_URL` | `"http://localhost:11434"` | Ollama server URL |
| `BFAI_OPENAI_API_KEY` | — | OpenAI API key |
| `BFAI_QDRANT_URL` | `"http://localhost:6333"` | Qdrant server URL |
| `BFAI_QDRANT_COLLECTION` | `"bfai"` | Qdrant collection name |

### Example .env file

```env
# Vault path
BFAI_VAULT_PATH=./vault

# Embedding provider (sentence-transformers, ollama, or openai)
BFAI_EMBEDDING_PROVIDER=sentence-transformers
BFAI_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Ollama (only needed if using provider=ollama)
# BFAI_OLLAMA_URL=http://localhost:11434

# OpenAI (only needed if using provider=openai)
# BFAI_OPENAI_API_KEY=sk-...

# Qdrant vector database
BFAI_QDRANT_URL=http://localhost:6333
BFAI_QDRANT_COLLECTION=bfai
```

> **Note:** Environment variables set directly in your shell take precedence over those in `.env`. This lets you override values temporarily without editing the file.

---

## Embedding Providers

### SentenceTransformers (default, local)

No external services needed. Embeddings are generated on your machine.

```python
from bfai.embeddings import get_provider

provider = get_provider(name="sentence-transformers")
vector = provider.generate("Your text here")
print(f"Dimension: {provider.embedding_dimension}")
```

Uses the model specified in `BFAI_EMBEDDING_MODEL` (default: `all-MiniLM-L6-v2`, 384 dimensions).

### Ollama

Requires a running Ollama server:

```bash
ollama pull nomic-embed-text
```

```python
provider = get_provider(name="ollama")
```

### OpenAI

```bash
export BFAI_OPENAI_API_KEY=sk-...
```

```python
provider = get_provider(name="openai")
```

---

## API Reference

All public APIs are in the `bfai.memory` module. Import them directly:

```python
from bfai.memory import create, update, delete, search, semantic_search
from bfai.memory import hybrid_search, retrieve, related, backlinks, expand
from bfai.memory import reindex_all, index_note_from_path
```

---

### 1. `create()`

Create a new note and index it into the system.

```python
create(
    title: str,
    content: str,
    *,
    tags: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    embed: bool = False,
    provider_name: str | None = None,
) -> dict
```

**Returns** a dict with `note` (Note object), `id` (database ID), `embedded` (bool).

```python
result = create(
    title="My Note",
    content="# Hello\nThis is my first note.",
    tags=["example"],
    metadata={"author": "me"},
    embed=True,                          # also create a vector embedding
    provider_name="sentence-transformers",
)
print(f"Created note with ID: {result['id']}")
print(f"Embedding stored: {result['embedded']}")
```

---

### 2. `update()`

Update an existing note's content and/or metadata, then re-index.

```python
update(
    title: str,
    content: str | None = None,
    *,
    metadata: dict[str, str] | None = None,
    tags: list[str] | None = None,
    re_embed: bool = False,
    provider_name: str | None = None,
) -> dict | None
```

**Returns** the result dict if found, or `None` if the note doesn't exist.

```python
# Update content only
result = update("My Note", content="# Updated\nNew content here.")

# Update content + metadata + re-embed
result = update(
    "My Note",
    content="# Updated\nNew content.",
    metadata={"status": "reviewed", "version": "2"},
    tags=["updated", "example"],
    re_embed=True,
)

if result:
    print(f"Updated: {result['id']}")
else:
    print("Note not found")
```

---

### 3. `delete()`

Completely remove a note from all storage layers.

```python
delete(
    title: str,
    *,
    remove_embedding: bool = False,
    provider_name: str | None = None,
) -> dict
```

**Returns** a dict with `success`, `file_deleted`, `db_deleted`, `embedding_removed` flags.

```python
result = delete("My Note", remove_embedding=True)
print(f"Deleted: {result['success']}")
print(f"  File: {result['file_deleted']}")
print(f"  DB:   {result['db_deleted']}")
print(f"  Vec:  {result['embedding_removed']}")
```

---

### 4. `search()`

Full-text search across all indexed notes using BM25 ranking with recency and access frequency boosting.

```python
search(query: str, limit: int = 20) -> list[dict]
```

Supports FTS5 query syntax — exact phrases (`"in quotes"`), prefix queries (`prefix*`).

```python
results = search("wireless robot controller", limit=10)
for r in results:
    print(f"  [{r['combined_score']:.3f}] {r['title']} "
          f"(recency={r['recency_score']:.2f}, "
          f"access={r['access_score']:.2f})")
```

---

### 5. `semantic_search()`

Meaning-based retrieval using vector embeddings.

```python
semantic_search(
    query: str,
    top_k: int = 10,
    *,
    provider_name: str | None = None,
    vector_store: object | None = None,
) -> list[dict]
```

**Requires:** An embedding provider (`sentence-transformers`, `ollama`, or `openai`) and a running Qdrant instance.

```python
results = semantic_search("wireless robot", top_k=5)
for r in results:
    print(f"  [{r['score']:.3f}] {r['title']}")
```

---

### 6. `hybrid_search()`

Combines keyword (FTS5) and semantic (vector) search with configurable weighting.

```python
hybrid_search(
    query: str,
    top_k: int = 10,
    *,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
    provider_name: str | None = None,
) -> list[dict]
```

Gracefully falls back to keyword-only if Qdrant is unavailable.

```python
results = hybrid_search("robot controller", top_k=10)
for r in results:
    print(f"  [{r['combined_score']:.3f}] {r['title']} "
          f"(source={r['source']}, "
          f"kw={r['keyword_score']:.3f}, "
          f"sem={r['semantic_score']:.3f})")
```

---

### 7. `retrieve()`

The primary context retrieval API for agents. Runs a full pipeline:

```
Query → Hybrid Search → Backlink Expansion → Graph Expansion → Sorting → Context Bundle
```

```python
retrieve(
    query: str,
    top_k: int = 10,
    *,
    include_backlinks: bool = True,
    max_hops: int = 2,
    hybrid: bool = True,
    provider_name: str | None = None,
) -> list[dict]
```

Each result item includes `source` (one of `"search"`, `"backlink"`, or `"graph"`), `match_type`, and `matched_note_id` for traceability.

```python
context = retrieve("ESP32", top_k=5, max_hops=2)
for item in context:
    print(f"  [{item['source']:>8}] {item['title']} "
          f"(hop={item.get('hop_depth', '-')})")
```

---

### 8. `related()`

Get notes directly connected to a given note via graph relationships.

```python
related(
    note_id: str,
    *,
    direction: str = "both",
    relationship_type: str | None = None,
) -> list[dict]
```

- `direction`: `"outgoing"`, `"incoming"`, or `"both"` (default)
- `relationship_type`: filter by a specific type (e.g. `"USES"`, `"EXPLICIT_LINK"`)

```python
# Find everything connected to a note
results = related(note_id, direction="both")
for r in results:
    print(f"  [{r['relationship_type']}] {r['related_title']}")

# Only get EXPLICIT_LINK relationships
links = related(note_id, direction="outgoing", relationship_type="EXPLICIT_LINK")
```

---

### 9. `backlinks()`

Get all notes that reference a given note (incoming relationships).

```python
backlinks(
    note_id: str,
    *,
    relationship_type: str | None = None,
) -> list[dict]
```

```python
bl = backlinks(note_id)
for b in bl:
    print(f"  Referenced by: {b['related_title']} ({b['relationship_type']})")
```

---

### 10. `expand()`

Traverse the relationship graph from one or more seed notes using BFS.

```python
expand(
    seed_ids: list[str],
    max_hops: int = 2,
    max_nodes: int = 50,
) -> list[dict]
```

Returns nodes with `hop_depth` (0 = seed, 1 = direct neighbor, 2 = neighbor-of-neighbor, etc.).

```python
seeds = [note_id1, note_id2]
graph = expand(seeds, max_hops=2, max_nodes=20)

for node in graph:
    indent = "  " * node["hop_depth"]
    print(f"{indent}[hop {node['hop_depth']}] {node['title']}")
```

---

## Practical Scripts

Ready-to-use scripts are located in the **`scripts/`** directory. Run them from the project root:

### Script 1: Bulk Ingest Markdown Files

Bulk-import markdown files from any directory into your BFAI vault.

```bash
python scripts/ingest.py /path/to/your/markdown/files
```

Defaults to `./vault/notes` if no path is provided.

---

### Script 2: Interactive Knowledge Explorer

An interactive REPL for searching, retrieving, and browsing your knowledge graph.

```bash
python scripts/explorer.py
```

Commands: `search <query>`, `retrieve <query>`, `backlinks <id>`, `related <id>`, `quit`

---

### Script 3: File Watcher Daemon

Watches your vault for changes and automatically re-indexes modified/deleted/renamed notes.

```bash
python scripts/watch.py
```

Press `Ctrl+C` to stop.

---

### Script 4: Semantic Similarity Search

Finds notes by meaning using vector embeddings.

> **Requires:** A running Qdrant instance and an embedding provider (sentence-transformers, ollama, or OpenAI).

```bash
python scripts/semantic.py "wireless robot control system"
```

Defaults to `"machine learning"` if no query is provided.

---

### Script 5: Agent Context Retriever

Builds a comprehensive context bundle for AI agents (direct matches + backlinks + graph neighbors).

```bash
python scripts/agent_context.py "What do I know about ESP32?"
```

Example output:

```
# Knowledge Context
Query: What do I know about ESP32?

## Direct Matches
1. ESP32-S3 Robot Controller

## Supporting Knowledge
  [BACKLINK] Project Overview
  [GRAPH] Embedded Systems (hop 1)
  [GRAPH] IoT Platforms (hop 2)
```

---

## Vault Structure

```
vault/
├── notes/          # Markdown knowledge notes (the source of truth)
├── images/         # Supporting images
├── documents/      # Supporting documents
└── metadata/       # System metadata (SQLite database lives here)
```

The SQLite database (`bfai.db`) is stored in `vault/metadata/` and contains:

- **notes** table — note metadata (title, path, timestamps, access count)
- **relationships** table — graph edges between notes with 32 relationship types
- **tags** table — tags per note
- **notes_fts** virtual table — FTS5 full-text index on title + body

---

## Relationship Types

All 32 supported relationship types across 8 categories:

| Category | Types |
|---|---|
| **Structural** | `PART_OF`, `CONTAINS`, `PARENT_OF`, `CHILD_OF` |
| **Dependency** | `DEPENDS_ON`, `REQUIRES`, `USES`, `PROVIDES`, `IMPLEMENTS` |
| **Semantic** | `RELATED_TO`, `SIMILAR_TO`, `REFERENCES`, `MENTIONS`, `DESCRIBES` |
| **Temporal** | `PRECEDES`, `FOLLOWS`, `REPLACED_BY`, `DERIVED_FROM` |
| **Causal** | `CAUSES`, `INFLUENCES`, `RESULTS_IN` |
| **Ownership** | `CREATED_BY`, `OWNED_BY`, `ASSIGNED_TO` |
| **Knowledge** | `SUPPORTS`, `CONTRADICTS`, `CONFIRMS`, `QUESTIONED_BY` |
| **AI-Specific** | `EXPLICIT_LINK`, `INFERRED_LINK`, `MEMORY_OF`, `OBSERVED_FROM` |

Wiki links (`[[Note Title]]`) in markdown are automatically converted to `EXPLICIT_LINK` relationships when indexed.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bfai -v

# Run a specific test file
pytest tests/test_memory.py -v

# Run a specific test
pytest tests/test_memory.py::TestCreateAPI -v
```

All 425+ tests should pass with a working install.

---

## What's Planned (Not Yet Implemented)

The following features are in the roadmap but not yet built:

- **Inferred Relationships** — LLM-based automatic relationship discovery between notes
- **Memory Importance Scoring** — automated significance calculation for ranking
- **Temporal Relationships** — automatic `PRECEDES`/`FOLLOWS` derivation from content
- **Conflict Detection** — identifying contradictory memories across notes

These extend the system with AI-native reasoning capabilities but are **not required** for the system to be useful. The current V1 is a complete, production-usable knowledge memory platform.