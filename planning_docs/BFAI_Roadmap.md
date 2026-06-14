# AI Memory System Roadmap


## Vision

Build a local-first AI-native memory platform inspired by Obsidian while extending it with:

- Graph memory
    
- Semantic retrieval
    
- Agent-oriented APIs
    
- Automatic relationship generation
    
- Human-readable markdown storage
    

### Core Principles

- Markdown is the source of truth
    
- SQLite stores graph relationships and metadata
    
- Qdrant stores embeddings
    
- Agents interact through APIs
    
- Local-first architecture
    

---

# Agile Delivery Strategy

Instead of implementing features exactly as listed in the specification, development is organized into vertical slices that produce a working system at every milestone.

This approach:

- Delivers usable functionality earlier
    
- Reduces architectural risk
    
- Allows validation of retrieval workflows before advanced AI features
    
- Makes the project manageable as a solo effort
    

---

# Epic 1 — Vault Foundation (8 SP)

Goal: Create a markdown-based knowledge vault.

## Stories

### 1.1 Vault Structure (1 SP)

- Create vault directory layout
    
- Configurable vault path
    

### 1.2 Markdown Loader (2 SP)

- Discover markdown files
    
- Load file contents
    
- Return note objects
    

### 1.3 Markdown Writer (2 SP)

- Create notes
    
- Update notes
    
- Delete notes
    

### 1.4 Note Metadata Model (3 SP)

Store:

- UUID
    
- Title
    
- Path
    
- Created timestamp
    
- Modified timestamp
    

**Outcome**

A working markdown knowledge base.

---

# Epic 2 — Parsing Engine (11 SP)

Goal: Convert markdown into structured memory objects.

## Stories

### 2.1 Markdown Parsing (3 SP)

Extract:

- Title
    
- Body
    
- Frontmatter
    

### 2.2 Tag Extraction (2 SP)

Extract:

```text
#robotics
#esp32
```

### 2.3 Wiki Link Extraction (3 SP)

Extract:

```text
[[ESP32-S3]]
[[Project X]]
```

### 2.4 Entity Extraction Framework (3 SP)

Initial entity types:

- Person
    
- Organization
    
- Technology
    
- Project
    

**Outcome**

Markdown becomes machine-readable knowledge.

---

# Epic 3 — Graph Storage (11 SP)

Goal: Store knowledge relationships.

## Stories

### 3.1 SQLite Schema (3 SP)

Tables:

- notes
    
- relationships
    
- tags
    

### 3.2 Relationship Storage (3 SP)

Store graph edges between notes.

### 3.3 Wiki Links → Relationships (2 SP)

Convert wiki links into:

```text
EXPLICIT_LINK
```

relationships.

### 3.4 Relationship Query API (3 SP)

Example:

```python
memory.related(note)
```

**Outcome**

Knowledge becomes interconnected.

---

# Epic 4 — Search (10 SP)

Goal: Find memories using keywords.

## Stories

### 4.1 Full Text Search (5 SP)

Implement SQLite FTS5.

### 4.2 Search API (2 SP)

```python
memory.search(query)
```

### 4.3 Ranking (3 SP)

Combine:

- Text relevance
    
- Recency
    
- Metadata
    

**Outcome**

Fast keyword retrieval.

---

# Epic 5 — Backlinks (5 SP)

Goal: Navigate incoming references.

## Stories

### 5.1 Backlink Query (2 SP)

```python
memory.backlinks(note)
```

### 5.2 Retrieval Expansion (3 SP)

Include backlinks during retrieval.

**Outcome**

Knowledge network becomes discoverable.

---

# Epic 6 — Semantic Memory (11 SP)

Goal: Enable meaning-based retrieval.

## Stories

### 6.1 Embedding Provider Interface (3 SP)

Support:

- OpenAI
    
- Ollama
    
- SentenceTransformers
    

### 6.2 Qdrant Integration (5 SP)

Store vectors.

### 6.3 Semantic Search (3 SP)

```python
memory.semantic_search(query)
```

**Outcome**

Natural language search across notes.

---

# Epic 7 — Hybrid Retrieval (15 SP)

Goal: Build agent-ready context retrieval.

## Stories

### 7.1 Retrieval Pipeline (5 SP)

```text
Query
→ Vector Search
→ Keyword Search
→ Merge Results
```

### 7.2 Graph Expansion (5 SP)

Traverse:

- 1-hop
    
- 2-hop
    

relationships.

### 7.3 Context Assembly (5 SP)

```python
memory.retrieve()
```

returns ranked context bundles.

**Outcome**

Agents receive relevant and connected memories.

---

# Epic 8 — Memory API Layer (9 SP)

Goal: Provide a stable interface for applications and agents.

## Stories

### 8.1 Create API (2 SP)

```python
memory.create()
```

### 8.2 Update API (2 SP)

```python
memory.update()
```

### 8.3 Delete API (2 SP)

```python
memory.delete()
```

### 8.4 Retrieve API (3 SP)

```python
memory.retrieve()
```

**Outcome**

Applications no longer interact with files directly.

---

# Epic 9 — Synchronization (10 SP)

Goal: Keep indexes synchronized automatically.

## Stories

### 9.1 File Watcher (5 SP)

Detect:

- Create
    
- Modify
    
- Delete
    
- Rename
    

events.

### 9.2 Incremental Reindexing (5 SP)

Reprocess only changed notes.

**Outcome**

Vault and indexes remain consistent.

---

# Epic 10 — AI-Native Features (26 SP)

Goal: Extend beyond traditional note-taking systems.

## Stories

### 10.1 Inferred Relationships (8 SP)

Generate:

```text
RELATED_TO
DEPENDS_ON
SIMILAR_TO
```

using LLMs and embeddings.

### 10.2 Memory Importance Scoring (5 SP)

Calculate memory significance.

### 10.3 Temporal Relationships (5 SP)

Generate:

```text
PRECEDES
FOLLOWS
DERIVED_FROM
```

relationships.

### 10.4 Conflict Detection (8 SP)

Identify contradictory memories.

**Outcome**

The memory system begins reasoning about knowledge.

---

# Retrieval Ranking

Candidate memories are ranked using:

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

## AI-Specific

```text
EXPLICIT_LINK
INFERRED_LINK
MEMORY_OF
OBSERVED_FROM
```

---

# Milestones

## Milestone 1 — Knowledge Base

Epics:

- Vault Foundation
    
- Parsing Engine
    

Deliverable:

- Markdown storage
    
- Tags
    
- Wiki links
    
- Structured note parsing
    

---

## Milestone 2 — Graph Memory

Epics:

- Graph Storage
    
- Search
    
- Backlinks
    

Deliverable:

- Connected notes
    
- Graph relationships
    
- Full-text search
    
- Backlink navigation
    

---

## Milestone 3 — Semantic Memory

Epics:

- Semantic Memory
    

Deliverable:

- Embeddings
    
- Qdrant integration
    
- Semantic retrieval
    

---

## Milestone 4 — Agent Retrieval

Epics:

- Hybrid Retrieval
    
- Memory API Layer
    

Deliverable:

- Agent-facing memory APIs
    
- Multi-hop retrieval
    
- Context assembly
    

---

## Milestone 5 — Synchronization

Epics:

- Synchronization
    

Deliverable:

- Automatic reindexing
    
- Live vault updates
    

---

## Milestone 6 — AI-Native Memory

Epics:

- AI-Native Features
    

Deliverable:

- Inferred relationships
    
- Memory importance scoring
    
- Temporal reasoning
    
- Conflict detection
    

---

# Total Estimated Size

|Epic|Story Points|
|---|--:|
|Vault Foundation|8|
|Parsing Engine|11|
|Graph Storage|11|
|Search|10|
|Backlinks|5|
|Semantic Memory|11|
|Hybrid Retrieval|15|
|Memory API Layer|9|
|Synchronization|10|
|AI-Native Features|26|
|**Total**|**116 SP**|

## V1 Release Target

A practical V1 consists of Milestones 1–4:

- Markdown storage
    
- Wiki links
    
- Graph memory
    
- Full-text search
    
- Semantic search
    
- Qdrant integration
    
- Agent APIs
    
- Multi-hop retrieval
    

Estimated effort:

**80 story points**

This provides a complete AI memory platform before advanced AI-native reasoning features are added.