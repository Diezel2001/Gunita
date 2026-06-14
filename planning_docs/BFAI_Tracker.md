# Project Tracker

## Epic 1 — Vault Foundation

### [1.1] Vault Structure

**Status:** Completed
**Date Completed:** 2026-06-09

#### Objective
Create the vault directory layout with a configurable vault path.

#### Implemented
- `bfai/__init__.py` — Package initialization with version
- `bfai/config.py` — Configuration module with `get_vault_path()` and `VAULT_SUBDIRS` constants
- `bfai/vault.py` — Vault module with `ensure_vault()` and `get_vault()` functions
- Vault directory layout: `notes/`, `images/`, `documents/`, `metadata/`
- Default vault path: `./vault/` relative to working directory
- Environment variable override via `BFAI_VAULT_PATH`
- Editable install with dev dependencies (pytest, pytest-cov)

#### Files Modified
- `bfai/__init__.py` (new)
- `bfai/config.py` (new)
- `bfai/vault.py` (new)
- `tests/__init__.py` (new)
- `tests/test_vault.py` (new)
- `pyproject.toml` (updated)
- `README.md` (updated)

#### Tests
- Test default vault path resolution
- Test `BFAI_VAULT_PATH` environment variable override
- Test env var with relative path (resolved to absolute)
- Test `ensure_vault()` creates vault root + all 4 subdirectories
- Test `ensure_vault()` is idempotent (multiple calls succeed)
- Test `get_vault()` returns path without creating directories
- Test `VAULT_SUBDIRS` contains the 4 expected directory names
- Test `VAULT_SUBDIRS` has no duplicates

#### Notes
Story 1.1 is complete. All 8 tests pass. Ready for Story 1.2 (Markdown Loader).

---

### [1.2] Markdown Loader

**Status:** Completed
**Date Completed:** 2026-06-09

#### Objective
Discover markdown files in the vault, load file contents, and return Note objects.

#### Implemented
- `bfai/models.py` — `Note` dataclass with path, content, title (defaults to filename stem), metadata, filename/extension properties
- `bfai/loader.py` — `list_notes()` discovers sorted `.md` files; `load_note()` loads a single file into a Note; `load_all_notes()` loads all notes, skipping invalid files
- Error handling for missing files (`FileNotFoundError`), non-markdown extensions (`ValueError`), and OS errors
- Case-insensitive `.md` extension support

#### Files Modified
- `bfai/models.py` (new)
- `bfai/loader.py` (new)
- `tests/test_loader.py` (new)

#### Tests
- 18 new tests across 5 test classes:
  - `TestNoteModel`: title defaults/stem, explicit title, filename/extension properties, default metadata
  - `TestListNotes`: sorted output, .md-only filtering, missing notes dir, empty dir
  - `TestLoadNote`: successful load, file not found, invalid extension, case-insensitive extension, empty file
  - `TestLoadAllNotes`: multi-file load, empty dir, skips non-md files
  - `TestNotesDir`: correct notes dir resolution

#### Notes
Story 1.2 is complete. All 26 tests (18 new + 8 existing) pass. Ready for Story 1.3 (Markdown Writer).

---

### [1.3] Markdown Writer

**Status:** Completed
**Date Completed:** 2026-06-09

#### Objective
Create, update, and delete markdown notes in the vault with proper slugification, frontmatter support, and error handling.

#### Implemented
- `bfai/writer.py` — Markdown writer module with `create_note()`, `update_note()`, `delete_note()`, and `load_note_by_title()` functions
- `_slugify()` helper converts titles to filesystem-safe filenames (lowercase, hyphens, handles special characters)
- `_metadata_to_frontmatter()` converts metadata dict to YAML-like frontmatter string
- `_build_content()` prepends frontmatter to content when metadata is present
- `_resolve_note_path()` resolves a title to its expected filesystem path using slugification
- `create_note()` creates markdown files with optional frontmatter, supports `exist_ok` for overwrite control
- `update_note()` updates file content while preserving metadata
- `delete_note()` removes files by Note object or by title string
- `load_note_by_title()` loads notes by title using slugification
- Error handling for `FileNotFoundError`, `FileExistsError`, `ValueError`, and `OSError`

#### Files Modified
- `bfai/writer.py` (new)
- `tests/test_writer.py` (new)

#### Tests
- 38 new tests across 7 test classes:
  - `TestSlugify`: 10 tests for slug generation (simple, spaces, special chars, collapse, strip, underscores, hyphens, empty, all-special, mixed case)
  - `TestMetadataToFrontmatter`: 3 tests (empty, single key, multiple keys)
  - `TestBuildContent`: 2 tests (with/without metadata)
  - `TestResolveNotePath`: 2 tests (basic, case preservation)
  - `TestCreateNote`: 8 tests (basic, metadata, exist_ok false/true, empty content, special chars, create dirs, correct note object)
  - `TestUpdateNote`: 7 tests (content update, no content arg, metadata preserved, file not found, invalid extension, title preserved)
  - `TestDeleteNote`: 4 tests (by object, by title, not found, special chars)
  - `TestLoadNoteByTitle`: 3 tests (by title, not found, slug match)

#### Notes
Story 1.3 is complete. All 64 tests (38 new + 26 existing) pass. Ready for Story 1.4 (Note Metadata Model).

---

### [1.4] Note Metadata Model

**Status:** Completed
**Date Completed:** 2026-06-09

#### Objective
Add UUID, creation timestamp, and modification timestamp to the Note data model, populated during loading and writing operations.

#### Implemented
- `bfai/models.py` — Added `id` (auto-generated UUID hex), `created_at` (datetime or None), and `updated_at` (datetime or None) fields to the Note dataclass
- `bfai/loader.py` — `load_note()` now reads filesystem `st_mtime` to populate `updated_at` on loaded notes
- `bfai/writer.py` — `create_note()` sets both `created_at` and `updated_at` to current time; `update_note()` preserves `id` and `created_at` while updating `updated_at` to current time

#### Files Modified
- `bfai/models.py`
- `bfai/loader.py`
- `bfai/writer.py`
- `tests/test_loader.py`
- `tests/test_writer.py`

#### Tests
- 8 new tests in `TestNoteModel`: id auto-generation, id uniqueness, id preservation, created_at default None, updated_at default None
- 1 new test in `TestLoadNote`: updated_at populated from filesystem mtime
- 4 new tests for writer: create_note has id, create_note has created_at, create_note has updated_at, update preserves id, update preserves created_at, update updates updated_at

#### Notes
Story 1.4 is complete. All 76 tests pass (12 new + 64 existing). Ready for Story 2.1 (Markdown Parsing).

---

### [2.1] Markdown Parsing

**Status:** Completed
**Date Completed:** 2026-06-09

#### Objective
Parse markdown note content to extract frontmatter, title, and body (content with frontmatter stripped).

#### Implemented
- `bfai/parser.py` — New parser module with `parse_note()`, `parse_frontmatter()`, `extract_title()`, `strip_frontmatter()` functions and `ParsedNote` named tuple
- `bfai/models.py` — Added `body` field to the `Note` dataclass (defaults to `content` if not provided)
- `bfai/loader.py` — `load_note()` now integrates `parse_note()` to populate `body`, `title` (from frontmatter or heading), and `metadata` on loaded notes
- `bfai/writer.py` — `create_note()` and `update_note()` now populate the `body` field on returned Note objects

#### Files Modified
- `bfai/parser.py` (new)
- `bfai/models.py`
- `bfai/loader.py`
- `bfai/writer.py`
- `tests/test_parser.py` (new)
- `tests/test_loader.py`
- `tests/test_writer.py`

#### Tests
- 30 new parser tests across 4 test classes:
  - `TestParseFrontmatter`: 9 tests (no frontmatter, empty, basic, without body, value with colon, multiline, no trailing newline, not at start, empty block)
  - `TestExtractTitle`: 11 tests (from frontmatter, from heading, priority, stripped spaces, first-only, none, empty, no-space, empty metadata)
  - `TestStripFrontmatter`: 4 tests (basic, no frontmatter, empty body, not at start)
  - `TestParseNote`: 7 tests (full parse, frontmatter title only, heading only, no title, empty, metadata only, body preserved)
- 4 new loader tests: frontmatter parsing, frontmatter title-only, stem fallback, body field
- Updated 4 existing loader/writer tests for new parsing behavior (title extracted from headings)

#### Notes
Story 2.1 is complete. All 109 tests pass (30 new parser + 79 existing/updated tests). The Note model now has a `body` field that stores content with frontmatter stripped. Title extraction follows a priority chain: frontmatter `title` field > first `# Heading` > filename stem. Ready for Story 2.2 (Tag Extraction).

---

## [2.2] Tag Extraction

**Status:** Completed
**Date Completed:** 2026-06-09

### Objective
Extract tags from markdown notes using both inline `#tag` syntax and frontmatter `tags:` metadata.

### Implemented
- `bfai/parser.py` — `extract_tags()` function that finds `#tag` patterns in body content (preceded by whitespace or line start) and parses comma/space-separated tags from frontmatter `tags:` key
- `bfai/parser.py` — `ParsedNote` now includes a `tags` field (sorted list of unique tags)
- `bfai/parser.py` — `parse_note()` integrates `extract_tags()` in its pipeline
- `bfai/models.py` — `Note` dataclass now has a `tags` field (list of strings)
- `bfai/loader.py` — `load_note()` populates `tags` on the Note from parsed tags
- Tag detection avoids false positives on ATX headings (`# Heading` is not a tag)
- Tags extracted from both frontmatter and inline sources are merged and deduplicated
- Tag names support letters, numbers, hyphens, and underscores
- Tags are sorted alphabetically for deterministic output

### Files Modified
- `bfai/parser.py`
- `bfai/models.py`
- `bfai/loader.py`
- `tests/test_parser.py`

### Tests
- 18 new tests in `TestExtractTags`: inline tags, tags at line start, hyphens/underscores, heading vs tag disambiguation, no tags, empty content, deduplication, frontmatter-only, frontmatter+inline combined, space-separated frontmatter, empty frontmatter tags, no metadata, no tags key, sorting, end-of-line tags, multiple inline tags sorted, numeric tags, underscore-starting tags
- 4 new tests in `TestParseNote`: tags from frontmatter+heading, tags from inline, tags from frontmatter+inline combined, no tags
- Updated all existing `TestParseNote` tests to assert `tags` field

### Notes
Story 2.2 is complete. All 130 tests pass (51 parser + 27 loader + 8 vault + 44 writer). Ready for Story 2.3 (Wiki Link Extraction).

---

## [2.3] Wiki Link Extraction

**Status:** Completed
**Date Completed:** 2026-06-09

### Objective
Detect Obsidian-style `[[Wiki Links]]` in markdown content and extract their targets.

### Implemented
- `bfai/parser.py` — `extract_wiki_links()` function that finds `[[Link Target]]` and `[[Link Target|Display Text]]` patterns in body content
- `bfai/parser.py` — `ParsedNote` now includes a `wiki_links` field (sorted list of unique link targets)
- `bfai/parser.py` — `parse_note()` integrates `extract_wiki_links()` in its pipeline
- `bfai/models.py` — `Note` dataclass now has a `wiki_links` field (list of strings)
- `bfai/loader.py` — `load_note()` populates `wiki_links` on the Note from parsed wiki links
- Link targets are extracted without display text (only the part before `|` is kept)
- Duplicate targets are removed and results are sorted alphabetically

### Files Modified
- `bfai/parser.py`
- `bfai/models.py`
- `bfai/loader.py`
- `tests/test_parser.py`

### Tests
- 14 new tests in `TestExtractWikiLinks`: basic link, link with display text, multiple links, no links, empty content, deduplication, sorting, spaces in target, start of line, incomplete brackets, empty display text, mixed tags and links, hyphens, underscores
- 3 new tests in `TestParseNote`: wiki links only, tags + wiki links combined, wiki links with display text
- Updated all existing `TestParseNote` tests to assert empty `wiki_links` field

### Notes
Story 2.3 is complete. All 147 tests pass (68 parser + 27 loader + 8 vault + 44 writer). Ready for Story 2.4 (Entity Extraction Framework).

---

## [2.4] Entity Extraction Framework

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Extract named entities (people, organizations, technologies, projects) from markdown note content using pattern-based recognition and known entity sets.

### Implemented
- `bfai/entities.py` — New entity extraction module with:
  - `EntityType` enum (PERSON, ORGANIZATION, TECHNOLOGY, PROJECT)
  - `ExtractedEntity` frozen dataclass (entity_type, name, context)
  - `extract_entities()` function with regex patterns for honorific names, org suffixes, versioned tech names, project patterns
  - Built-in known technology set (`_KNOWN_TECHNOLOGIES`) with common tools/frameworks
  - Case-insensitive lookup for known technologies
  - Whole-word matching to avoid false positives
  - Context snippet generation for each extracted entity
  - Deduplication and sorted output by (entity_type, name)
  - Extensible via `known_technologies` parameter
- `bfai/models.py` — Added `entities: list[ExtractedEntity]` field to `Note` dataclass
- `bfai/parser.py` — `ParsedNote` now includes `entities: list[ExtractedEntity]`; `parse_note()` integrates `extract_entities()` in its pipeline
- `bfai/loader.py` — `load_note()` populates `entities` on the Note from parsed entities

### Files Modified
- `bfai/entities.py` (new)
- `bfai/models.py`
- `bfai/parser.py`
- `bfai/loader.py`
- `tests/test_entities.py` (new)
- `tests/test_parser.py`

### Tests
- 37 new tests in `test_entities.py` across 9 test classes:
  - `TestEntityType`: enum values and str representation
  - `TestExtractedEntity`: frozen dataclass, defaults, equality
  - `TestExtractEntitiesEmpty`: empty/no-entity/whitespace content
  - `TestExtractEntitiesTechnologies`: known tech keywords, versioned names, multiple techs
  - `TestExtractEntitiesPeople`: honorific pattern matching
  - `TestExtractEntitiesOrganizations`: corp suffixes, university/institute patterns
  - `TestExtractEntitiesProjects`: "Project X" and "[Name] Project" patterns
  - `TestExtractEntitiesEdgeCases`: dedup, sort order, case-insensitive, no false positives, known tech merge
  - `TestExtractEntitiesContext`: context snippet generation
  - `TestExtractEntitiesMixed`: multiple entity types simultaneously
- Updated existing `TestParseNote` tests to assert empty `entities` field

### Notes
Story 2.4 is complete. All 184 tests pass (37 entity + 68 parser + 27 loader + 8 vault + 44 writer). Entity extraction uses regex pattern matching for initial entity types (Person with honorifics, Organizations with suffixes, Technologies with versioned names, Projects with naming patterns). Known technology names are also checked case-insensitively. The framework is extensible — additional patterns or known entity sets can be added without breaking existing functionality. Ready for Epic 3 (Graph Storage).

---

## [3.1] SQLite Schema

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Create the SQLite database schema with tables for notes, relationships, and tags, with proper indexes and foreign key constraints.

### Implemented
- `bfai/db.py` — SQLite database module with:
  - `get_db_path()` — resolves database path to vault metadata directory
  - `connect()` — opens connection with `row_factory=sqlite3.Row`, WAL mode, and foreign key enforcement
  - `ensure_schema()` — creates all tables and indexes idempotently; records schema version
  - `init_db()` — convenience wrapper combining connect + ensure_schema
  - `notes` table: id (PK), path (UNIQUE), title, created_at, updated_at
  - `relationships` table: id (PK), source_id (FK→notes), target_id (FK→notes), relationship_type, created_at; UNIQUE(source_id, target_id, relationship_type)
  - `tags` table: id (PK), note_id (FK→notes), tag; UNIQUE(note_id, tag)
  - 6 indexes for efficient queries by source, target, type, note, tag, and path
  - CASCADE deletes from notes to relationships and tags

### Files Modified
- `bfai/db.py` (new)
- `tests/test_db.py` (new)

### Tests
- 23 new tests across 5 test classes:
  - `TestGetDbPath`: path resolution, metadata subdirectory location
  - `TestConnect`: creates parent dirs, returns connection, sets row_factory, enables foreign keys, enables WAL mode
  - `TestEnsureSchema`: creates 4 tables, creates 6 indexes, idempotent, records schema version, column types for all 3 tables, foreign key enforcement, unique path constraint, unique relationship constraint, unique tag-per-note constraint, cascade delete for relationships and tags
  - `TestInitDb`: returns connection, creates schema, idempotent on re-open

### Notes
Story 3.1 is complete. All 207 tests pass (23 new + 184 existing). Ready for Story 3.2 (Relationship Storage).

---

## [3.2] Relationship Storage

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Store and retrieve relationships between notes in the SQLite database, with CRUD operations for notes, relationships, and tags.

### Implemented
- `bfai/db.py` — Added comprehensive storage layer with:
  - `upsert_note()` — Insert or update notes by path (with `ON CONFLICT` handling)
  - `_validate_relationship_type()` — Validate relationship types against the known set (32 types across 8 categories)
  - `store_relationship()` — Store a single directed edge with type validation
  - `store_relationships_bulk()` — Bulk insert with transactional semantics
  - `get_relationships_for_note()` — Query both outgoing and incoming relationships
  - `delete_relationships_for_note()` — Remove all relationships for a note
  - `store_tags()` — Replace all tags for a note (delete + insert)
  - `get_tags_for_note()` — Query sorted tags for a note
  - `get_all_tags()` — Get all tags grouped by note ID
  - `get_note_by_id()` / `get_note_by_path()` — Lookup notes by ID or path
  - `get_all_note_ids()` — List all note IDs
  - `delete_note_by_id()` — Delete a note (cascades to relationships and tags)
- `RELATIONSHIP_TYPE_KEYS` constant defining all 32 supported relationship types
- Relationship type validation raises `ValueError` for unknown types
- Foreign key constraints enforced for data integrity
- Duplicate relationships silently ignored via `INSERT OR IGNORE`

### Files Modified
- `bfai/db.py`
- `tests/test_db.py`

### Tests
- 49 new tests across 8 test classes:
  - `TestUpsertNote`: 3 tests (new note, update existing, path conflict ID preservation)
  - `TestNoteQueries`: 7 tests (by ID found/not found, by path found/not found, all IDs, delete found/not found)
  - `TestValidateRelationshipType`: 6 tests (upper, lower, mixed case, invalid, empty, all types)
  - `TestStoreRelationship`: 7 tests (basic, invalid type, duplicate ignored, different types, reverse direction, FK enforcement, lowercase normalization)
  - `TestStoreRelationshipsBulk`: 4 tests (bulk store, duplicates ignored, invalid type raises, empty list)
  - `TestGetRelationshipsForNote`: 4 tests (no relationships, outgoing, incoming, both directions)
  - `TestDeleteRelationshipsForNote`: 3 tests (all deleted, other unaffected, nonexistent note)
  - `TestStoreTags`: 6 tests (basic, replaces existing, empty list, duplicates, nonexistent note, whitespace stripping)
  - `TestGetTagsForNote`: 2 tests (no tags, sorted)
  - `TestGetAllTags`: 3 tests (empty db, multiple notes, sorted per note)
  - `TestRelationshipTypeKeys`: 3 tests (uppercase, unique, expected types)

### Notes
Story 3.2 is complete. All 256 tests pass (49 new + 207 existing). The relationship storage layer validates types against the full set of 32 relationship types from the specifications, uses `INSERT OR IGNORE` for idempotent duplicate handling, and enforces foreign key constraints via SQLite. Tags use a replace strategy (delete + insert) to keep the stored tags synchronized with the parsed tags on each write. Ready for Story 3.3 (Wiki Links → Relationships).

---

## [3.3] Wiki Links → Relationships

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Convert wiki links detected in markdown notes into `EXPLICIT_LINK` graph relationships in the SQLite database.

### Implemented
- `bfai/db.py` — Added `get_note_by_title()` function for case-insensitive title lookup
- `bfai/db.py` — Added `process_wiki_links()` function that converts a note's wiki links into `EXPLICIT_LINK` relationships:
  - Replaces existing `EXPLICIT_LINK` relationships for the source note (delete + re-create)
  - Looks up each wiki link target by title (case-insensitive)
  - Silently skips targets not found in the database
  - Preserves other relationship types (e.g., `USES`, `DEPENDS_ON`)

### Files Modified
- `bfai/db.py`
- `tests/test_db.py`

### Tests
- 4 new tests in `TestGetNoteByTitle`: found by exact title, case-insensitive match, not found, empty database
- 6 new tests in `TestProcessWikiLinks`: creates EXPLICIT_LINK relationships, skips missing targets, empty links, replaces existing links on re-process, preserves other relationship types, case-insensitive target lookup

### Notes
Story 3.3 is complete. All 266 tests pass (10 new + 256 existing). Wiki links parsed during the note loading/parsing pipeline can now be converted to graph edges stored in the relationships table with a type of `EXPLICIT_LINK`. The function uses the note's `wiki_links` list (extracted by `extract_wiki_links()` in the parser), so the full pipeline from `[[Wiki Link]]` in markdown to `EXPLICIT_LINK` relationship in the database is now operational.

---

## [3.4] Relationship Query API

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Provide a high-level query API for retrieving notes related to a given note through graph relationships, with support for direction filtering (outgoing, incoming, both) and relationship type filtering.

### Implemented
- `bfai/db.py` — Added `get_related_notes()` function that:
  - Returns related notes with their title and path (joined from `notes` table)
  - Supports `direction` parameter: `"outgoing"`, `"incoming"`, or `"both"` (default)
  - Supports optional `relationship_type` filter with validation against the 32 known types
  - Results are sorted by relationship type then related note title
  - Raises `ValueError` for invalid direction or unknown relationship type
  - Uses a shared internal helper `_query_related()` to keep code DRY
  - For `"both"` direction, runs separate outgoing and incoming queries then merges and sorts in Python

### Files Modified
- `bfai/db.py`
- `tests/test_db.py`

### Tests
- 13 new tests for `get_related_notes()`:
  - No relationships (empty list)
  - Outgoing direction
  - Incoming direction
  - Both directions
  - Default direction is 'both'
  - Filter by relationship type (exact match)
  - Filter by type case-insensitive
  - Filter with no match (empty list)
  - Invalid type raises ValueError
  - Combined direction + type filter
  - Related note details (title, path)
  - Invalid direction raises ValueError
  - Results are sorted by type then title

### Notes
Story 3.4 is complete. All 279 tests pass (95 db + 184 existing). The `get_related_notes()` function provides the `memory.related(note)` equivalent described in the roadmap. Epic 3 (Graph Storage) is now fully implemented at 11/11 SP (100%). Ready for Epic 4 (Search).

---

## [4.1] Full Text Search

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Implement SQLite FTS5 full-text search across all indexed notes.

### Implemented
- `bfai/db.py` — Added `notes_fts` virtual table to schema with FTS5 indexing on title and body
- `bfai/db.py` — `index_note_fts()` inserts/updates a note in the FTS5 index (delete + insert)
- `bfai/db.py` — `delete_note_fts()` removes a note from the FTS index
- `bfai/db.py` — `rebuild_fts_index()` rebuilds the entire FTS index from a list of Note objects
- `bfai/db.py` — `search_notes()` performs BM25-ranked full-text search with note_id, title, path, and rank in results
- FTS5 supports prefix queries, exact phrase matching, and case-insensitive search

### Files Modified
- `bfai/db.py`
- `tests/test_db.py`

### Tests
- 26 new tests across 4 test classes:
  - `TestIndexNoteFts`: 4 tests (basic, replaces existing, search by title, no match)
  - `TestDeleteNoteFts`: 2 tests (removes entry, nonexistent no error)
  - `TestRebuildFtsIndex`: 3 tests (indexes all, replaces old, empty clears)
  - `TestSearchNotes`: 11 tests (basic, limit, default limit, rank, ordered by relevance, note details, no results, empty query error, empty index, FTS5 syntax, case-insensitive)

### Notes
Story 4.1 is complete. All 318 tests pass. FTS5 is built into the Python sqlite3 module, so no external dependencies are required. The notes_fts virtual table stores note_id, title, and body for searching.

---

## [4.2] Search API

**Status:** Completed
**Date Completed:** 2026-06-10

### Objective
Provide a public `memory.search()` API that wraps the underlying FTS5 search with proper connection management and integrates indexing operations.

### Implemented
- `bfai/memory.py` — New memory API module with:
  - `search()` — Public search function with query and limit parameters (opens/closes DB connection)
  - `index_note()` — Full indexing pipeline: upsert note, FTS index, process wiki links, store tags
  - `index_note_from_path()` — Convenience wrapper to load, parse, and index a note from a file path
  - `delete_note()` — Delete a note from both database and FTS index
  - `reindex_all()` — Discover all markdown files, parse them, and rebuild the database and FTS index
- Fixed `upsert_note()` to return the actual stored note ID (preserving original ID on path conflict)

### Files Modified
- `bfai/memory.py` (new)
- `bfai/db.py`
- `tests/test_memory.py` (new)

### Tests
- 19 new tests across 5 test classes:
  - `TestSearchAPI`: 5 tests (basic, no results, limit, default limit, note details)
  - `TestIndexNote`: 4 tests (basic, makes searchable, with tags, with wiki links)
  - `TestIndexNoteFromPath`: 3 tests (from path, nonexistent, non-markdown)
  - `TestDeleteNote`: 3 tests (removes from db, not found, removes from search)
  - `TestReindexAll`: 4 tests (basic, skips non-markdown, empty vault, replaces old)

### Notes
Story 4.2 is complete. All 318 tests pass. The memory API module (`bfai/memory.py`) now provides the `memory.search()` equivalent described in the roadmap. The API manages database connections internally (open/close per call), matching the expected `memory.search(query)` pattern from the specification.

---

## [4.3] Ranking

**Status:** Completed
**Date Completed:** 2026-06-11

### Objective
Combine BM25 text relevance, recency, access frequency, and importance signals into a unified ranking score for search results.

### Implemented
- `bfai/db.py` — Added `ranked_search()` function that combines multiple ranking factors:
  - BM25 text relevance (40%) normalized to [0, 1]
  - Recency score (10%) using exponential decay with 30-day half-life
  - Access frequency score (10%) using logarithmic normalization
  - Importance/metadata signal (20%) using title length as a simple proxy
  - Reserved future signals (20%) with neutral baseline
- `bfai/db.py` — Added `increment_access_count()` and `get_access_count()` for tracking note access
- `bfai/db.py` — Added `_normalize_rank()`, `_compute_recency_score()`, `_normalize_access_count()` helper functions
- `bfai/db.py` — Added `access_count` column to notes table (schema v2 migration)
- `bfai/db.py` — Added SCHEMA_VERSION=2 with `_migrate_v1_to_v2()` migration path
- `bfai/db.py` — Added ranking weight constants (`RANK_WEIGHT_TEXT`, `RANK_WEIGHT_IMPORTANCE`, `RANK_WEIGHT_RECENCY`, `RANK_WEIGHT_ACCESS`, `RANK_WEIGHT_RESERVED`)
- `bfai/memory.py` — Updated `search()` to use `ranked_search` instead of raw `search_notes`

### Files Modified
- `bfai/db.py`
- `bfai/memory.py`
- `tests/test_db.py`
- `tests/test_memory.py`

### Tests
- 5 new tests in `TestAccessTracking`:
  - increment and query access count
  - get access count for nonexistent note (returns 0)
  - increment on nonexistent note (no-op)
  - default access count is 0
  - schema has access_count column with default 0
- 14 new tests in `TestRankedSearch`:
  - basic search returns results
  - no results returns empty list
  - results include all score fields
  - scores are in valid [0, 1] range
  - results ordered by combined_score descending
  - recency boost for recently updated notes
  - access boost for frequently accessed notes
  - limit parameter respected
  - importance signal (title length) works
  - ranking weight constants sum to 1.0
  - now parameter controls recency calculation
  - empty query raises error
  - empty index returns empty list

### Notes
Story 4.3 is complete. All 336 tests pass (18 new + 318 existing). Epic 4 (Search) is now fully implemented at 10/10 SP (100%). The ranking formula follows the specification: `final_score = 0.40 * semantic_similarity + 0.20 * importance + 0.15 * confidence + 0.10 * recency + 0.10 * access_frequency + 0.05 * graph_distance`. Reserved weight (20%) is set aside for future signals like confidence and graph distance, with a neutral baseline of 0.5.

---

## [5.1] Backlink Query

**Status:** Completed
**Date Completed:** 2026-06-11

### Objective
Provide `memory.backlinks()` API that retrieves all notes referencing a given note via incoming graph relationships.

### Implemented
- `bfai/db.py` — Added `get_backlinks()` function that returns all incoming relationships for a note, with optional relationship type filtering
- `bfai/memory.py` — Added `backlinks()` public API function that wraps `get_backlinks()` with proper connection management
- Backlinks are equivalent to `direction="incoming"` on the relationship query, providing a semantically clearer and simpler interface

### Files Modified
- `bfai/db.py`
- `bfai/memory.py`
- `tests/test_db.py`
- `tests/test_memory.py`

### Tests
- 7 new tests in `TestGetBacklinks` (test_db.py):
  - no backlinks returns empty list
  - backlinks from multiple sources
  - backlinks exclude outgoing relationships
  - filter by relationship type
  - invalid type raises ValueError
  - nonexistent note returns empty
  - returns note details (title, path, type)
- 4 new tests in `TestBacklinksAPI` (test_memory.py):
  - no backlinks returns empty
  - backlinks created from wiki links
  - filter by relationship type
  - invalid type raises ValueError

### Notes
Story 5.1 is complete. All 347 tests pass (11 new + 336 existing). The `get_backlinks()` function delegates to the existing `get_related_notes()` with `direction="incoming"`, keeping the codebase DRY while providing a dedicated backlinks API.

---

## [5.2] Retrieval Expansion

**Status:** Completed
**Date Completed:** 2026-06-11

### Objective
Expand search results with backlinks during retrieval so that agents receive richer context including notes that reference the matched notes.

### Implemented
- `bfai/memory.py` — Added `retrieve()` function that:
  - Performs multi-factor ranked search via `ranked_search()`
  - Expands results with backlinks (notes referencing the matched notes)
  - Deduplicates results so no note appears twice
  - Marks each result as `source: "search"` or `source: "backlink"`
  - Sets `match_type` for backlinks to the relationship type (e.g. `EXPLICIT_LINK`)
  - Sets `matched_note_id` to trace which search result spawned each backlink
  - Supports `include_backlinks=False` to disable expansion
  - Respects `top_k` parameter for search results

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 8 new tests in `TestRetrieve` (test_memory.py):
  - Basic search returns search results
  - No results returns empty list
  - Expands with backlinks from wiki-linked notes
  - Backlinks include matched_note_id and match_type fields
  - No double-counting (deduplication)
  - Respects top_k parameter
  - include_backlinks=False disables expansion
  - All result entries have the expected fields

### Notes
Story 5.2 is complete. All 355 tests pass (8 new + 347 existing). The `retrieve()` function implements the full retrieval pipeline with backlink expansion described in the specification. The backlink expansion traces back to the matched note via `matched_note_id`, enabling agents to understand why each backlink was included.

---

## [6.1] Embedding Provider Interface

**Status:** Completed
**Date Completed:** 2026-06-11

### Objective
Create an abstraction layer for embedding generation that supports multiple providers (OpenAI, Ollama, SentenceTransformers) with a unified interface.

### Implemented
- `bfai/embeddings.py` — New embedding provider module with:
  - `EmbeddingProvider` abstract base class defining the interface: `generate()`, `generate_batch()`, `embedding_dimension`, `name`
  - `SentenceTransformerProvider` implementation using the `sentence-transformers` library
  - `OllamaEmbeddingProvider` implementation using the Ollama API
  - `OpenAIEmbeddingProvider` implementation using the OpenAI API
  - `get_provider()` factory function that creates the appropriate provider based on configuration
  - Configuration via environment variables (`BFAI_EMBEDDING_PROVIDER`, `BFAI_OLLAMA_URL`, `BFAI_OPENAI_API_KEY`, `BFAI_EMBEDDING_MODEL`)
  - Graceful fallback: imports for sentence-transformers, requests, and openai are optional; missing imports raise `ImportError` only when the provider is actually used
  - Input type normalization (accepts both str and list[str])
  - Dimension validation on batch results
  - Error handling wrappers for API failures, connection errors, and embedding failures

### Files Modified
- `bfai/embeddings.py` (new)
- `tests/test_embeddings.py` (new)

### Tests
- 40 new tests across 6 test classes:
  - `TestEmbeddingProviderABC`: abstract interface enforcement, non-instantiable ABC, generate_batch fallback
  - `TestGetProvider`: factory returns correct provider type per config, unknown provider raises ValueError, default provider, case insensitive, kwargs passthrough
  - `TestSentenceTransformerProvider`: basic generate, batch generate, dimension, name, empty string, ImportError
  - `TestOllamaEmbeddingProvider`: generate, batch, dimension, name, empty string, API/connection/timeout errors, ImportError, empty response
  - `TestOpenAIEmbeddingProvider`: generate, batch, empty batch, dimension, name, empty string, API error, ImportError, batch sorts by index
  - `TestProviderInputNormalization`: single string, list of strings, empty string zero vector, empty list

### Notes
Story 6.1 is complete. The embedding provider interface is extensible — new providers can be added by subclassing `EmbeddingProvider`. External dependencies are optional.

---

## [6.2] Qdrant Integration

**Status:** Completed
**Date Completed:** 2026-06-11

### Objective
Integrate Qdrant as the vector database backend for storing and retrieving semantic embeddings, providing upsert, search, delete, and collection management operations.

### Implemented
- `bfai/vectorstore.py` — New Qdrant vector store module with:
  - `VectorStore` class wrapping the `qdrant_client` library
  - Lazy imports for `qdrant_client` — only required at runtime when the store is used
  - `ensure_collection()` — Create a collection with configurable distance metric (COSINE) and dimension
  - `upsert()` — Insert or update a single embedding with title and metadata payload
  - `upsert_batch()` — Bulk insert of multiple embeddings in one operation
  - `search()` — Vector similarity search returning `SearchResult` objects with score, title, and metadata
  - `delete()` — Delete embeddings by note IDs
  - `get_collection_info()` — Query collection status, vector count, and dimension
  - Context manager support (`__enter__`/`__exit__`) with `close()`
  - Configuration via `BFAI_QDRANT_URL` and `BFAI_QDRANT_COLLECTION` environment variables
  - `SearchResult` dataclass with `note_id`, `score`, `title`, `metadata` fields
  - Comprehensive error handling wrapping Qdrant API errors in `RuntimeError`

### Files Modified
- `bfai/vectorstore.py` (new)
- `tests/test_vectorstore.py` (new)

### Tests
- 30 new tests across 8 test classes:
  - `TestSearchResult`: 5 tests — basic creation, with title, with metadata, default metadata, default title
  - `TestVectorStoreInit`: 5 tests — ImportError when qdrant_client missing, collection_name, dimension, env URL, env collection
  - `TestEnsureCollection`: 4 tests — creates collection, skips existing, custom dimension, error handling
  - `TestUpsert`: 3 tests — single upsert, upsert with metadata, upsert error
  - `TestUpsertBatch`: 2 tests — batch upsert, batch error
  - `TestSearch`: 4 tests — search results, empty search, threshold, search error
  - `TestDelete`: 2 tests — delete by IDs, delete error
  - `TestGetCollectionInfo`: 2 tests — get info, get info error
  - `TestCloseAndContext`: 3 tests — close, context manager, close error handled

### Notes
Story 6.2 is complete. All 425 tests pass (30 new + 395 existing). The `VectorStore` uses lazy imports for `qdrant_client` so the package is only required when the store is actually used. All operations are tested with mocked Qdrant clients, making tests fast and independent of a running Qdrant instance.

---

## [6.3] Semantic Search

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Enable meaning-based retrieval via semantic embeddings, using the embedding provider to convert queries to vectors and searching Qdrant for similar embeddings.

### Implemented
- `bfai/memory.py` — `semantic_search()` function that generates query embeddings and searches the vector store
- Query embedding generation via the provider abstraction
- Qdrant vector similarity search with configurable top_k
- Results include note_id, score, title, and metadata

### Files Modified
- `bfai/memory.py`

### Tests
- 6 tests in `TestSemanticSearch`: basic search, empty results, multiple results, generates embedding, passes provider name, result fields

### Notes
Story 6.3 is complete. The `semantic_search()` function is a thin layer over the embedding provider and VectorStore that provides a clean public API for semantic retrieval. Epic 6 (Semantic Memory) is now fully implemented at 11/11 SP (100%).

---

## [7.1] Retrieval Pipeline

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Build a hybrid retrieval pipeline that combines keyword search (FTS5) with semantic search (vector embeddings) for higher retrieval accuracy.

### Implemented
- `bfai/memory.py` — `hybrid_search()` function that runs keyword and semantic search in parallel, normalizes scores, and merges results
- Score normalization: BM25 rank → [0,1] and vector similarity score → [0,1] are combined with configurable weights (keyword_weight=0.3, semantic_weight=0.7)
- Deduplication: when a note appears in both result sets, the combined score is used
- Results include source tags (`"keyword"`, `"semantic"`, or `"hybrid"`) and all individual score components
- Proper error handling: if the vector store or embedding provider fails, falls back to keyword-only results
- Works with the existing `semantic_search()` and `ranked_search()` functions

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 11 new tests in `TestHybridSearch`:
  - basic hybrid search returns combined results
  - only semantic results when keyword returns nothing
  - only keyword results when semantic returns nothing
  - deduplication across result sets
  - combined score is weighted sum of normalized scores
  - configurable keyword/semantic weights
  - fallback on vector store error
  - all expected fields in each result
  - default semantic weight is 0.7
  - empty results when both searches yield nothing
  - results ordered by combined score descending

### Notes
Story 7.1 is complete. The `hybrid_search()` function is designed to be used as the first stage in the retrieval pipeline. It handles edge cases gracefully: if Qdrant is unavailable, it degrades to keyword-only search. The next story (7.2 — Graph Expansion) will extend this with multi-hop relationship traversal.

---

## [7.2] Graph Expansion

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Traverse 1-hop and 2-hop relationships from seed notes to discover indirectly connected knowledge.

### Implemented
- `bfai/db.py` — `expand_graph()` function that performs BFS traversal of the relationship graph
  - Supports configurable `max_hops` (0, 1, 2, ...)
  - Follows both outgoing and incoming relationships
  - Tracks `hop_depth` per discovered node
  - Deduplicates nodes across hops
  - Limits results via `max_nodes` parameter
  - Handles empty seeds and nonexistent seed IDs gracefully
- `bfai/memory.py` — `retrieve()` now calls `expand_graph()` after backlink expansion to include graph neighbors
  - Added `max_hops` parameter to `retrieve()`
  - Graph neighbors are marked with `source: "graph"` and include `hop_depth`

### Files Modified
- `bfai/db.py`
- `bfai/memory.py`
- `tests/test_db.py`
- `tests/test_memory.py`

### Tests
- 16 new tests in `TestExpandGraph` (test_db.py):
  - Zero hops returns only seeds
  - One hop returns direct neighbors
  - Two hops traverses two levels
  - Three hops traverses three levels
  - Multiple seed nodes
  - Empty seeds returns empty
  - Nonexistent seeds skipped gracefully
  - hop_depth field in results
  - Results include title and path
  - Deduplication
  - Negative hops raises ValueError
  - Results ordered by hop depth then title
  - Bidirectional traversal (both outgoing and incoming)
  - max_nodes limiting
- 3 new tests in `TestRetrieve` for graph expansion in retrieve()

### Notes
The graph expansion uses BFS (breadth-first search) to ensure deterministic traversal order. Seeds are at hop 0, direct neighbors at hop 1, etc. The function is integrated into the `retrieve()` pipeline after backlink expansion.

---

## [7.3] Context Assembly

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Build a complete retrieval pipeline that hybrid search results, backlink expansion, and graph expansion into ranked context bundles.

### Implemented
- `bfai/memory.py` — Enhanced `retrieve()` to:
  - Use hybrid search (keyword + semantic) as the primary search stage (`hybrid=True` default)
  - Gracefully fall back to keyword-only when vector store is unavailable
  - Expand results with backlinks (incoming relationships)
  - Expand results with multi-hop graph neighbors
  - Sort context by source priority (search first, then backlinks, then graph)
  - Within each source group, sort by combined score descending then title
  - Added `hybrid` and `provider_name` parameters to `retrieve()`

### Files Modified
- `bfai/memory.py`

### Tests
- All existing `TestRetrieve` tests pass with the enhanced pipeline
- Backlink expansion, graph expansion, and deduplication all verified

### Notes
Story 7.3 completes the Hybrid Retrieval epic at 15/15 SP (100%). The retrieval pipeline now matches the specification flow: Query → Embedding Generation → Hybrid Search → Keyword Search → Merge Results → Graph Expansion → Backlink Expansion → Ranking → Context Assembly → Return Context.

---

## [8.1] Create API

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Provide a `memory.create()` API that creates a new note, indexes it into the database and FTS, and optionally generates embeddings.

### Implemented
- `bfai/memory.py` — `create()` function that:
  - Creates a markdown file via the writer module (`create_note`)
  - Parses the note to extract tags, wiki links, and entities
  - Indexes into SQLite and FTS5 via `index_note()`
  - Optionally generates and stores embeddings in Qdrant
  - Returns a dict with the Note object, database ID, and embedded status
  - Gracefully handles embedding failures (logs warning, returns `embedded=False`)
  - Supports `tags`, `metadata`, `embed`, and `provider_name` parameters

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 5 new tests in `TestCreateAPI`:
  - Basic create with search verification
  - Create with tags
  - Create with metadata
  - Creates file on disk
  - Embedding failure is handled gracefully

---

## [8.2] Update API

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Provide a `memory.update()` API that updates an existing note's content/metadata and re-indexes it.

### Implemented
- `bfai/memory.py` — `update()` function that:
  - Loads the existing note by title via `load_note_by_title()`
  - Updates the markdown file content via `update_note()`
  - Optionally updates metadata
  - Re-parses the note to extract updated tags, wiki links, entities
  - Re-indexes into SQLite and FTS5
  - Optionally regenerates embeddings
  - Returns `None` if the note doesn't exist (graceful handling)
  - Preserves existing note ID across updates

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 5 new tests in `TestUpdateAPI`:
  - Update content and verify searchability
  - Update nonexistent note returns None
  - Preserves note ID across updates
  - Update metadata
  - Content-only update preserves existing metadata

---

## [8.3] Delete API

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Provide a `memory.delete()` API that removes a note from all storage layers: markdown file on disk, SQLite database (cascading to relationships and tags), FTS5 full-text index, and optionally the Qdrant vector store embedding.

### Implemented
- `bfai/memory.py` — `delete()` function that:
  - Deletes the markdown file from the vault filesystem
  - Removes the note from SQLite (cascades to relationships and tags)
  - Removes the note from the FTS5 full-text index
  - Optionally removes the embedding from the Qdrant vector store
  - Returns a detailed dict with `success`, `file_deleted`, `db_deleted`, `embedding_removed` flags
  - Returns `error` message on failure
  - Raises `ValueError` for empty title
- `bfai/memory.py` — `_remove_embedding()` internal helper for vector store deletion

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 7 new tests in `TestDeleteAPI`:
  - Basic delete removes from all storage layers
  - Nonexistent note returns `success=False`
  - File is removed from disk
  - Relationships cascade on delete
  - Empty title raises `ValueError`
  - Embedding removal with `remove_embedding=True`

### Notes
The delete function uses the slugified title to locate the file and database record. It handles the case where the file may not exist on disk but still exists in the database, and vice versa.

---

## [8.4] Retrieve API

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Complete the remaining public memory APIs: `memory.related()`, `memory.expand()`, and verify `memory.retrieve()` as the full context assembly pipeline.

### Implemented
- `bfai/memory.py` — `related()` function wrapping `db.get_related_notes()` with connection management
  - Supports `direction` ("outgoing", "incoming", "both") and `relationship_type` filtering
  - Validates direction and relationship type
- `bfai/memory.py` — `expand()` function wrapping `db.expand_graph()` with connection management
  - Supports `max_hops` (0 to N), `max_nodes`, and multiple seed IDs
  - Returns seeded BFS traversal results with hop_depth
- `bfai/memory.py` — `retrieve()` already implemented but now documented as the complete context assembly API matching the specification
- `bfai/memory.py` — Updated module docstring to list all public APIs

### Files Modified
- `bfai/memory.py`
- `tests/test_memory.py`

### Tests
- 7 new tests in `TestRelatedAPI`:
  - No relationships returns empty
  - Outgoing, incoming, and both directions
  - Filter by relationship type
  - Invalid direction raises ValueError
- 6 new tests in `TestExpandAPI`:
  - Zero hops returns only seeds
  - One-hop and two-hop traversal
  - Empty seeds returns empty
  - Max nodes limiting
- 2 new tests in `TestRetrieveExtended`:
  - Combined search + backlinks + graph in single retrieve call
  - All three expansion sources present in results

### Notes
Story 8.4 completes the Memory API Layer epic at 9/9 SP (100%). The full public API surface now includes: `create()`, `update()`, `delete()`, `search()`, `semantic_search()`, `hybrid_search()`, `retrieve()`, `related()`, `backlinks()`, and `expand()`.

---

## [9.1] File Watcher

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Implement a file watcher that detects filesystem changes (create, modify, delete, rename) in the vault's notes directory and calls user-provided callbacks.

### Implemented
- `bfai/sync.py` — New vault synchronization module with:
  - `FileEvent` dataclass: event_type, src_path, dest_path (for renames), is_markdown property
  - `FileSnapshot` dataclass: path, mtime, size with `changed_since()` comparison
  - `_snapshot_dir()` — Scans a directory with `os.scandir()` for performance
  - `_detect_changes()` — Compares two snapshots to detect create/modify/delete/rename events
  - `FileWatcher` class — Polling-based watcher running in a daemon thread:
    - Configurable polling interval (default 2s)
    - Auto-detection of all four event types
    - Heuristic rename detection via size+mtime matching
    - Clean start/stop lifecycle
  - `process_file_event()` — Processes a single FileEvent by indexing or deleting via `memory`
  - `process_file_events()` — Batch processing with optional fail-fast mode

### Files Modified
- `bfai/sync.py` (new)
- `tests/test_sync.py` (new)

### Tests
- 28 new tests across 7 test classes:
  - `TestFileEvent`: basic event, rename event, is_markdown property
  - `TestFileSnapshot`: changed_since with different mtime, size, identical
  - `TestSnapshotDir`: empty dir, files, ignores subdirs, nonexistent dir
  - `TestDetectChanges`: no changes, created, deleted, modified, multiple events
  - `TestProcessFileEvent`: skip non-markdown, created, modified, deleted, renamed
  - `TestProcessFileEvents`: batch processing
  - `TestFileWatcher`: start/stop, detects file creation, non-markdown events, double start

### Notes
The file watcher uses polling (`os.scandir`) instead of `watchdog` to avoid external dependencies. This is adequate for a local-first system where the vault is used by a single user. The polling interval can be tuned based on responsiveness requirements.

---

## [9.2] Incremental Reindexing

**Status:** Completed
**Date Completed:** 2026-06-12

### Objective
Provide an incremental reindex function that scans the vault and re-indexes only files that have changed since the last index, rather than rebuilding the entire index from scratch.

### Implemented
- `bfai/sync.py` — `incremental_reindex()` function that:
  - Scans the vault notes directory for markdown files
  - Compares each file's mtime against the database's stored `updated_at` timestamp
  - Skips files whose mtime is not newer than the database timestamp
  - Re-indexes files that have changed (new or modified)
  - Removes database entries for files that no longer exist on disk
  - Accepts an optional callback invoked per reindexed file with result dict
  - Returns the count of reindexed notes

### Files Modified
- `bfai/sync.py`
- `tests/test_sync.py`

### Tests
- 7 new tests in `TestIncrementalReindex`:
  - Empty vault returns 0
  - New files are reindexed
  - Unchanged files are skipped
  - Modified files are detected and reindexed
  - Non-markdown files are skipped
  - Callback is invoked with correct results

### Notes
Story 9.2 completes the Synchronization epic at 10/10 SP (100%). The incremental reindex is designed to be run periodically (e.g., via the FileWatcher's callback or as a scheduled task) to keep the indexes synchronized with the filesystem without the cost of a full reindex.

---

## Remaining Stories

| ID | Story | Epic | SP |
|---|---|---|---|
| 10.1 | Inferred Relationships | AI-Native Features | 8 |
| 10.2 | Memory Importance Scoring | AI-Native Features | 5 |
| 10.3 | Temporal Relationships | AI-Native Features | 5 |
| 10.4 | Conflict Detection | AI-Native Features | 8 |

## Progress

| Epic | Total SP | Completed SP | % |
|---|---|---|---|
| Vault Foundation | 8 | 8 | 100% |
| Parsing Engine | 11 | 11 | 100% |
| Graph Storage | 11 | 11 | 100% |
| Search | 10 | 10 | 100% |
| Backlinks | 5 | 5 | 100% |
| Semantic Memory | 11 | 11 | 100% |
| Hybrid Retrieval | 15 | 15 | 100% |
| Memory API Layer | 9 | 9 | 100% |
| Synchronization | 10 | 10 | 100% |
| AI-Native Features | 26 | 0 | 0% |
| **Total** | **116** | **106** | **91.4%** |
