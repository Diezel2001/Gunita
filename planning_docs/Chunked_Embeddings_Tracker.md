# Chunked Embeddings — Implementation Plan & Tracker

**Status:** In Progress
**Created:** 2026-06-14
**Description:** Implement paragraph-level chunking for note embeddings in Qdrant. Chunks are grouped by section headings, then split by paragraphs within each section. Embeddings are re-generated and replaced when a note is modified.

---

## Chunking Strategy

### Chunk ID Convention
Each chunk gets a deterministic ID: `{note_id}_chunk_{index}` (e.g., `abc123_chunk_0`, `abc123_chunk_1`).

### Chunking Algorithm: Section → Paragraph
1. **Split by section headings** (`#`, `##`, `###`, etc.)
2. **Within each section, split by paragraphs** (double newlines `\n\n`)
3. **Each paragraph becomes a separate chunk**, with the section heading prepended for context
4. **Single-paragraph sections** → 1 chunk (heading + paragraph)

### Example

Input:
```markdown
# Intro
Some intro text.
## Setup
Step 1...

Step 2...
## Details
Long explanation paragraph 1.

Long explanation paragraph 2.
```

Resulting chunks:
| Chunk ID | Content |
|----------|---------|
| `{id}_chunk_0` | `# Intro\nSome intro text.` |
| `{id}_chunk_1` | `## Setup\nStep 1...` |
| `{id}_chunk_2` | `## Setup\nStep 2...` |
| `{id}_chunk_3` | `## Details\nLong explanation paragraph 1.` |
| `{id}_chunk_4` | `## Details\nLong explanation paragraph 2.` |

### Re-embedding Flow
1. Delete all existing chunks for the note via `note_id` payload filter
2. Re-chunk the note
3. Batch-upsert new chunk embeddings

### Search Deduplication
Group search results by `note_id`, keep the highest-scoring chunk per note.

---

## Tags

| Tag | Meaning |
|-----|---------|
| `✅ DONE` | Task is implemented and verified |
| `⬜ PENDING` | Task is not yet started |
| `🔄 IN PROGRESS` | Task is currently being worked on |

---

## Phase 1: Completed Tasks (Already Implemented)

- [x] `✅ DONE` **Add `--vault-path` CLI option to all Gunita commands** — `src/gunita/main.py` now accepts `--vault-path` / `-v` on `webui`, `serve`, `status`, `reindex`. Falls back to `BFAI_VAULT_PATH` env var → `./vault` default.
- [x] `✅ DONE` **Add `--vault-path` argument to `ingest.py`** — `src/scripts/ingest.py` now accepts `--vault-path` / `-v`.
- [x] `✅ DONE` **Add `--embed` flag to `incremental_reindex()`** — `src/bfai/sync.py` `incremental_reindex()` now accepts `embed` and `provider_name` params. When `embed=True`, only changed notes are embedded.
- [x] `✅ DONE` **Add `--embed` flag to `gunita reindex` CLI command** — `src/gunita/main.py` reindex command now accepts `--embed` / `-e` and `--provider` / `-p`.
- [x] `✅ DONE` **Add `--embed` flag to `ingest.py`** — `src/scripts/ingest.py` now accepts `--embed` / `-e` and `--provider` / `-p`.
- [x] `✅ DONE` **Fix `ensure_vault` dict access bug in `gunita/main.py`** — `ensure_vault()` returns a `Path`, not a dict. Fixed `vault["root"]` → `vault` and `vault["notes_path"]` → `vault / "notes"`.
- [x] `✅ DONE` **Fix `database_path` str vs Path issue in `gunita/main.py`** — `connect(str(settings.database_path))` → `connect(settings.database_path)`.
- [x] `✅ DONE` **Design paragraph chunking approach** — Section→Paragraph hierarchy. Chunk IDs: `{note_id}_chunk_{index}`.

---

## Phase 2: VectorStore Infrastructure

- [x] `✅ DONE` **Add `delete_by_payload()` method to `VectorStore`** — `src/bfai/vectorstore.py`
  - Added method using Qdrant's `Filter` with `FieldCondition`/`MatchValue` to filter by payload
  - Deletes all vectors where a given key matches a value (e.g., `note_id == X`)

- [x] `✅ DONE` **Verify `upsert_batch()` supports chunk ID format** — `src/bfai/vectorstore.py`
  - `upsert_batch()` already supports custom point IDs and metadata_list — works for `{note_id}_chunk_{index}` format

---

## Phase 3: Chunking Logic

- [x] `✅ DONE` **Implement `chunk_note()` function** — `src/bfai/memory.py`
  - Splits by markdown headings, then by paragraphs within each section
  - Handles preamble, empty sections, notes with no headings
  - Returns list of `Chunk` objects with deterministic IDs

- [x] `✅ DONE` **Define `Chunk` dataclass** — `src/bfai/models.py`
  - Fields: `chunk_id`, `text`, `note_id`, `section_heading`, `chunk_index`

- [x] `✅ DONE` **Update `_embed_note()` to use chunking** — `src/bfai/memory.py`
  - Calls `chunk_note()` to split, `generate_batch()` for embeddings, `upsert_batch()` for storage
  - Removes old chunks before embedding new ones
  - Payload includes `note_id`, `title`, `chunk_index`, `section_heading`, `tags`

- [x] `✅ DONE` **Update `_remove_embedding()` to delete all chunks** — `src/bfai/memory.py`
  - Uses `delete_by_payload("note_id", note_id)` with fallback to legacy single-vector delete

---

## Phase 4: Search & Retrieval

- [x] `✅ DONE` **Update `semantic_search()` to deduplicate by `note_id`** — `src/bfai/memory.py`
  - Fetches extra results (top_k × 5), groups by `note_id` from payload metadata
  - Keeps highest-scoring chunk per note, returns deduplicated results

- [x] `✅ DONE` **Update `hybrid_search()` to handle chunked results** — `src/bfai/memory.py`
  - Already works correctly since `semantic_search()` now returns deduplicated note-level results
  - Keyword + semantic merge by `note_id` handles chunked results naturally

---

## Phase 5: Re-embedding Integration

- [x] `✅ DONE` **Update `incremental_reindex()` to use chunked embeddings** — `src/bfai/sync.py`
  - Calls `_embed_note()` which now chunks automatically; change detection unchanged

- [x] `✅ DONE` **Update `ingest.py` to use chunked embeddings** — `src/scripts/ingest.py`
  - Calls `_embed_note()` which now chunks automatically

- [x] `✅ DONE` **Update `create()` in `memory.py` to use chunked embeddings** — `src/bfai/memory.py`
  - Calls `_embed_note()` which now chunks automatically

- [x] `✅ DONE` **Update `update()` in `memory.py` to re-embed chunks on change** — `src/bfai/memory.py`
  - Calls `_embed_note()` which removes old chunks and creates new ones automatically

---

## Phase 6: Testing

- [ ] `⬜ PENDING` **Write unit tests for `chunk_note()`** — `tests/test_memory.py`
  - Test single heading, multiple headings, no headings
  - Test single paragraph, multiple paragraphs
  - Test empty sections, edge cases

- [ ] `⬜ PENDING` **Write unit tests for `delete_by_payload()`** — `tests/test_vectorstore.py`
  - Test deletion of multiple chunks by note_id

- [ ] `⬜ PENDING` **Write unit tests for `_embed_note()` with chunking** — `tests/test_memory.py`
  - Test that multiple chunks are created and stored in Qdrant

- [ ] `⬜ PENDING` **Write unit tests for `semantic_search()` deduplication** — `tests/test_memory.py`
  - Test that search results are deduplicated by note_id

- [ ] `⬜ PENDING` **Integration test: embed → modify → re-embed** — `tests/test_memory.py`
  - Test the full flow: create note → embed → modify note → re-embed → verify old chunks removed and new chunks created

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Completed Tasks | 8 | ✅ All Done |
| Phase 2: VectorStore Infrastructure | 2 | ✅ All Done |
| Phase 3: Chunking Logic | 4 | ✅ All Done |
| Phase 4: Search & Retrieval | 2 | ✅ All Done |
| Phase 5: Re-embedding Integration | 4 | ✅ All Done |
| Phase 6: Testing | 5 | ⬜ Pending |
| **Total** | **25** | **20 Done / 5 Pending** |
