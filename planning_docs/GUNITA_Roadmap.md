# Gunita — Development Roadmap

> **Parent Project:** BFAI Memory System
> **Status:** Phase 4 Complete (All Phases Done)

---

## Phase 0: Skeleton & Project Setup ✅

**Goal:** Establish project structure, CLI entry points, and skeleton modules.

- [x] Remove old PySide6 frontend (`frontend/`)
- [x] Create `src/gunita/` package structure
- [x] Create CLI with Typer (`gunita webui`, `gunita serve`, `gunita status`, `gunita reindex`)
- [x] Create FastAPI app factory with static file serving
- [x] Create configuration module (env-var based)
- [x] Create API route stubs with Pydantic models:
  - [x] `/api/graph/` — Graph endpoints
  - [x] `/api/notes/` — Note endpoints
  - [x] `/api/search/` — Search endpoints
  - [x] `/api/vault/` — Vault tree + file read
  - [x] `/api/stats/` — Statistics + reindex
- [x] Create HTML template (SPA shell)
- [x] Create CSS (dark theme, three-panel layout)
- [x] Create JavaScript modules (graph, tree, search, preview, stats, app)
- [x] Create planning docs (Specifications, Roadmap, Tracker)
- [x] Update `pyproject.toml` with gunita entry point + `[web]` dependencies

---

## Phase 1: Core API Implementation ✅

**Goal:** Wire up API endpoints to actual BFAI backend.

### 1.1 Graph API
- [x] Implement `GET /api/graph/` — fetch all notes + relationships from `bfai.db`
- [x] Implement `GET /api/graph/{note_id}` — multi-hop neighborhood traversal
- [x] Add relationship type → color mapping in response
- [x] Handle empty vault gracefully

### 1.2 Notes API
- [x] Implement `GET /api/notes/` — paginated note listing
- [x] Implement `GET /api/notes/{note_id}` — load note detail + content via `bfai.loader`
- [x] Implement `GET /api/notes/{note_id}/backlinks` — via `bfai.db.get_backlinks`
- [x] Add markdown content rendering option

### 1.3 Search API
- [x] Implement keyword search via `bfai.memory.search()`
- [x] Implement semantic search via `bfai.memory.semantic_search()`
- [x] Implement hybrid search via `bfai.memory.retrieve()`
- [x] Graceful fallback when Qdrant is unavailable
- [x] Add result snippets/excerpts

### 1.4 Stats API
- [x] Implement `GET /api/stats/` — aggregate counts from db
- [x] Implement `POST /api/stats/reindex` — trigger `bfai.sync.incremental_reindex()`
- [x] Add Qdrant connectivity check

### 1.5 Vault API
- [x] Implement `GET /api/vault/` — directory tree walker (already working)
- [x] Implement `GET /api/vault/read` — file reader with path security check (already working)

---

## Phase 2: Frontend Integration

**Goal:** Connect frontend JavaScript to live API data.

### 2.1 Graph Visualization
- [ ] Test vis-network rendering with real data
- [ ] Verify node sizing based on degree
- [ ] Verify edge color coding by relationship type
- [ ] Test node click → preview panel integration
- [ ] Add search match highlighting on graph

### 2.2 Vault Tree
- [ ] Test recursive tree rendering
- [ ] Verify `.md` file click → preview
- [ ] Add collapsible folder behavior
- [ ] Test with large vault (>100 files)

### 2.3 Search
- [ ] Test search form submission
- [ ] Verify dropdown results display
- [ ] Test result click → preview + graph highlight
- [ ] Test mode switching (keyword/semantic/hybrid)
- [ ] Disable semantic/hybrid when Qdrant is down

### 2.4 Preview Panel
- [ ] Test markdown rendering (via marked.js)
- [ ] Verify code block formatting
- [ ] Test wiki link rendering
- [ ] Test tag pill display

### 2.5 Status Bar
- [ ] Verify stats display on load
- [ ] Test reindex button → status refresh
- [ ] Show unindexed file count

---

## Phase 3: Polish & Reliability ✅

**Goal:** Production-quality UX and error handling.

- [x] Error handling for API failures (toast notifications)
- [x] Loading spinners for async operations
- [x] Keyboard shortcuts (Cmd/Ctrl+K for search)
- [x] Resizable panels (drag to resize)
- [x] Empty state illustrations/messages
- [x] Auto-refresh stats periodically (every 60s)
- [x] Graph legend toggle (hide/show)
- [x] URL-based navigation (e.g., `/#/note/esp32-s3`)
- [x] Browser history integration (back/forward)

---

## Phase 4: Advanced Features ✅

**Goal:** Extended capabilities for power users.

- [x] WebSocket live graph updates
- [x] Note creation/editing in the web UI
- [x] Graph export (PNG/SVG)
- [x] Filter graph by tag or relationship type
- [x] Dark/light theme toggle
- [x] Full markdown rendering with embedded images
- [x] Responsive mobile layout
- [x] Agent API key authentication (for external agents)
- [x] Note versioning / diff view

---

## Release Milestones

| Milestone | Target | Status |
|-----------|--------|--------|
| **v0.1.0-alpha** | Skeleton + working API endpoints | ✅ Done |
| **v0.1.0-beta** | All API endpoints functional + frontend wired up | ✅ Done |
| **v0.1.0** | Full feature parity with PySide6 GUI + polish | ✅ Done |
| **v0.2.0** | Advanced features (WebSocket, editing, themes) | ✅ Done |
