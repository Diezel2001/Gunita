# Gunita — Knowledge Explorer

> **Version:** 0.1.0 | **Status:** Planning
> **Parent Project:** [BFAI](../Project_Specifications.md) — A local-first AI-native memory and knowledge system

---

## 1. Overview

Gunita (Filipino: "memory") is the **web frontend and REST API** for the BFAI memory system. It provides visual exploration of the knowledge vault through an interactive force-directed graph, filesystem tree, full-text/semantic/hybrid search, and markdown note preview — all served as a local web application.

### Purpose

- Provide a visual, browser-based interface for browsing the BFAI knowledge base
- Expose a REST API that both the UI and external agents can consume
- Make the relationship graph between notes visible and explorable
- Support all search modes (keyword, semantic, hybrid) through a clean API
- Enable quick reindexing and monitoring of vault statistics

### Core Principles

- **Local-first** — runs on the user's machine; no cloud dependency
- **API-first** — every UI feature is backed by a REST endpoint (agents can call the same API)
- **Non-destructive** — the frontend never modifies vault files
- **Zero build tools** — frontend uses vanilla JS + vis.js (no npm, no bundler)
- **Shared backend** — Gunita imports the `bfai` Python package directly for all data access

---

## 2. Architecture

### High-Level Data Flow

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Vault Disk  │────▶│  Gunita (FastAPI)    │────▶│  Browser (SPA)   │
│  (.md files) │     │                      │     │                  │
│              │     │  ┌────────────────┐  │     │  - Graph (vis.js)│
│  SQLite DB   │────▶│  │ bfai Python API│  │────▶│  - Tree (DOM)    │
│  (bfai.db)   │     │  │ (memory.*, db) │  │     │  - Preview (HTML)│
│              │     │  └────────────────┘  │     │  - Search (fetch)│
│  Qdrant      │────▶│                      │     │  - Stats (fetch) │
│  (optional)  │     └──────────────────────┘     └──────────────────┘
└──────────────┘
```

### Module Structure

```
src/gunita/
├── __init__.py          # Package metadata, version
├── main.py              # CLI entry point (Typer)
├── server.py            # FastAPI app factory
├── config.py            # Settings from env vars
├── api/                 # REST API layer
│   ├── router.py        # Aggregates all sub-routers
│   ├── graph.py         # /api/graph/*
│   ├── notes.py         # /api/notes/*
│   ├── search.py        # /api/search/*
│   ├── vault.py         # /api/vault/*
│   └── stats.py         # /api/stats/*
├── static/              # Frontend assets (served by FastAPI)
│   ├── css/style.css
│   └── js/
│       ├── app.js       # Bootstrap + cross-module wiring
│       ├── graph.js     # vis-network graph visualization
│       ├── tree.js      # Vault file tree widget
│       ├── search.js    # Search bar + results dropdown
│       ├── preview.js   # Note preview panel
│       └── stats.js     # Status bar + reindex trigger
└── templates/
    └── index.html       # SPA shell
```

---

## 3. Application Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Search...________________________________] [●Keyword ○Sem ○Hy]  │
│                                                     [🔍 Search]    │
├──────────┬─────────────────────────────┬───────────────────────────┤
│          │                             │                           │
│  TREE    │      KNOWLEDGE GRAPH        │    NOTE PREVIEW           │
│  PANEL   │                             │    PANEL                  │
│          │   (vis-network,             │                           │
│  vault/  │    force-directed           │    Title: ...             │
│  ├ notes │    layout)                  │    Path: ...              │
│  │ ├ a   │                             │    Tags: [tag1] [tag2]   │
│  │ └ b   │   ○───○                     │    ───────────────────   │
│  ├ images│   │ \  │                    │    Content: ...           │
│  └ docs  │   ○───○                     │    ...                    │
│          │   │   /                     │                           │
│          │   ○                         │                           │
├──────────┴─────────────────────────────┴───────────────────────────┤
│ [🔄 Reindex]  Notes: 42  Rels: 156  Tags: 18  Files: 42          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. REST API Specification

### 4.1 Graph API

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/graph/` | Full knowledge graph | `limit`, `offset` |
| `GET` | `/api/graph/{note_id}` | Neighborhood around a note | `hops` (1-5) |

### 4.2 Notes API

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/notes/` | List all notes | `limit`, `offset` |
| `GET` | `/api/notes/{note_id}` | Get note detail + content | — |
| `GET` | `/api/notes/{note_id}/backlinks` | Get backlinks | — |

### 4.3 Search API

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/search/` | Search notes | `q`, `mode`, `limit` |

**Search modes:**
- `keyword` — Full-text search via SQLite FTS5 (`bfai.memory.search()`)
- `semantic` — Vector similarity via Qdrant (`bfai.memory.semantic_search()`)
- `hybrid` — Combined keyword + semantic + graph expansion (`bfai.memory.retrieve()`)

### 4.4 Vault API

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/vault/` | Vault directory tree | — |
| `GET` | `/api/vault/read` | Read file content | `path` |

### 4.5 Stats API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats/` | Vault statistics |
| `POST` | `/api/stats/reindex` | Trigger incremental reindex |

---

## 5. CLI Commands

| Command | Description |
|---------|-------------|
| `gunita webui` | Start server + open browser |
| `gunita serve` | Start server (headless, no browser) |
| `gunita status` | Show vault/Qdrant status in terminal |
| `gunita reindex` | Trigger reindex from CLI |

---

## 6. Configuration

All settings are loaded from environment variables with defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `GUNITA_HOST` | `127.0.0.1` | Server bind host |
| `GUNITA_PORT` | `8712` | Server port |
| `GUNITA_RELOAD` | `false` | Enable auto-reload for development |
| `GUNITA_GRAPH_MAX_NODES` | `500` | Max nodes to display in graph |
| `BFAI_VAULT_PATH` | `./vault` | Vault directory |
| `BFAI_DB_PATH` | `{vault}/metadata/bfai.db` | SQLite database path |
| `BFAI_QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |

---

## 7. Dependencies

### Runtime

| Package | Required | Purpose |
|---------|----------|---------|
| `bfai` (this project) | Yes | Core memory API |
| `fastapi` | Yes | Web framework |
| `uvicorn` | Yes | ASGI server |
| `jinja2` | Yes | Template engine |
| `typer` | Yes | CLI framework |
| `httpx` | Yes | HTTP client (Qdrant check) |
| `vis.js` (CDN) | Yes (browser) | Graph visualization |
| `marked.js` (CDN) | Yes (browser) | Markdown rendering |

### Optional

| Package | Purpose |
|---------|---------|
| `qdrant-client` + `sentence-transformers` | Enables semantic/hybrid search |
| `PySide6` | Original desktop GUI (optional alternative) |

---

## 8. Out of Scope (V1)

- Note editing / creation from the web UI
- User authentication (local-only — not needed)
- Real-time collaboration
- Custom graph layout persistence
- Export functionality
- WebSocket push updates (V2)

---

## 9. Future Enhancements (Post-V1)

- WebSocket for real-time graph updates
- Note creation/editing in the web UI
- Export graph as PNG/SVG
- Filter graph by tag or relationship type
- Dark/light theme toggle
- Full markdown rendering with images
- WebSocket-based live search (instant results)
- Mobile-responsive layout