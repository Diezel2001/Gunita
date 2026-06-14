# Gunita — Knowledge Explorer

A local-first web UI and REST API for the BFAI, an AI-native memory and knowledge system for Agent Memory/Context Management.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running Gunita](#running-gunita)
- [CLI Commands](#cli-commands)
- [Usage Flow](#usage-flow)
- [API Reference](#api-reference)
- [WebSocket](#websocket)
- [Project Structure](#project-structure)
- [Features](#features)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Architecture](#architecture)
- [Development](#development)

---

## Prerequisites

- **Python 3.11+** (tested on 3.12)
- **uv** or **pip** for Python package management
- A BFAI vault directory (`./vault/`) with markdown notes
- **Qdrant** (optional) — enables semantic and hybrid search
- **SQLite** — used by the BFAI backend for relationships, tags, and full-text search

### System Requirements

| Resource | Minimum |
|----------|---------|
| CPU | Any modern processor |
| RAM | 256 MB (server) |
| Disk | Vault files + SQLite DB |
| Network | Localhost only (no external network needed) |

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repo-url> && cd BFAI
```

### 2. Install Dependencies

Using **uv** (recommended):

```bash
# Install core dependencies
uv pip install -r pyproject.toml

# Install web dependencies (FastAPI, uvicorn, etc.)
uv pip install ".[web]"
```

Or using **pip**:

```bash
pip install -e ".[web]"
```

### 3. Set Up the Vault

If you don't have a vault yet, create one:

```bash
mkdir -p vault/notes vault/documents vault/images vault/metadata
```

Add some markdown notes to `vault/notes/`. Example:

```markdown
# My First Note

This is my first knowledge note.

#tag1 #tag2 [[another-note]]
```

### 4. Initialize the Database

Run the reindex to populate the SQLite database from your vault:

```bash
gunita reindex
```

Or use Python directly:

```python
from bfai.sync import incremental_reindex
incremental_reindex("./vault")
```

### 5. (Optional) Start Qdrant for Semantic Search

If you want semantic or hybrid search:

```bash
# Using Docker
docker run -d -p 6333:6333 qdrant/qdrant

# Or using docker-compose (if available)
docker-compose up -d qdrant
```

---

## Configuration

All settings are loaded from environment variables with sensible defaults. You can create a `.env` file in the project root:

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GUNITA_HOST` | `127.0.0.1` | Server bind host |
| `GUNITA_PORT` | `8712` | Server port |
| `GUNITA_RELOAD` | `false` | Enable auto-reload for development |
| `GUNITA_GRAPH_MAX_NODES` | `500` | Max nodes to display in graph |
| `GUNITA_API_KEY` | (empty) | API key for external agent authentication |
| `GUNITA_EXTRA_VAULTS` | (empty) | Comma-separated list of additional vault paths |
| `BFAI_VAULT_PATH` | `./vault` | Vault directory |
| `BFAI_DB_PATH` | `{vault}/metadata/bfai.db` | SQLite database path |
| `BFAI_QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |

### Example `.env` file

```env
GUNITA_HOST=127.0.0.1
GUNITA_PORT=8712
BFAI_VAULT_PATH=./vault
BFAI_QDRANT_URL=http://localhost:6333
GUNITA_API_KEY=my-secret-key
GUNITA_EXTRA_VAULTS=/home/user/other-vault,/mnt/shared/vault
```

---

## Running Gunita

### Start with Web UI (opens browser)

```bash
gunita webui
```

### Start Server only (headless)

```bash
gunita serve
```

The server will be available at `http://127.0.0.1:8712` (default).

### Check System Status

```bash
gunita status
```

### Reindex the Vault

```bash
gunita reindex
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `gunita webui` | Start server and open browser |
| `gunita serve` | Start server (headless, no browser) |
| `gunita status` | Show vault/Qdrant status in terminal |
| `gunita reindex` | Trigger incremental reindex of the vault |

---

## Usage Flow

### 1. **Explore the Knowledge Graph**

The center panel shows a force-directed graph of your notes. Each node is a note, sized by its number of connections.

- **Click a node** → loads the note in the preview panel
- **Hover** → shows tooltip with title, ID, connections, and tags
- **Drag** → pan the graph; scroll to zoom
- **Export** → Click PNG or SVG buttons in the top-right to download the graph

### 2. **Browse the Vault Tree**

The left panel shows the filesystem tree of your vault.

- **Click a .md file** → loads it in the preview panel
- **Expand/collapse** folders with the arrow toggle
- **＋ button** → Create a new note (also `Ctrl+N`)

### 3. **Search Notes**

Use the search bar at the top:

- **Keyword mode** (default) — Full-text search via SQLite FTS5
- **Semantic mode** — Vector similarity search via Qdrant (requires Qdrant)
- **Hybrid mode** — Combined keyword + semantic + graph expansion (requires Qdrant)
- **shortcut**: Press `Ctrl+K` to focus the search bar from anywhere

### 4. **Read & Edit Notes**

The right panel shows note content:

- **Preview** — Rendered markdown with wiki links, images, and metadata
- **Edit** — Click ✏️ (or `Ctrl+E`) to switch to the editor
- **Save** — Click 💾 to save changes (creates a version snapshot)

### 5. **View Version History**

- Click the 🕐 button in the preview header
- Click a version to see a color-coded diff between that version and the previous

### 6. **Switch Themes**

- Click the 🌓 button in the top-right to toggle between dark and light themes
- Your preference is saved and persists across sessions

---

## API Reference

### REST API

All endpoints are available under `/api/`. See [Specifications](GUNITA_Specifications.md) for full details.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/graph/` | GET | Full knowledge graph |
| `/api/graph/{note_id}` | GET | Neighborhood around a note |
| `/api/notes/` | GET | List all notes |
| `/api/notes/` | POST | Create a new note |
| `/api/notes/{note_id}` | GET | Get note detail |
| `/api/notes/{note_id}` | PUT | Update a note |
| `/api/notes/{note_id}` | DELETE | Delete a note |
| `/api/notes/{note_id}/backlinks` | GET | Get backlinks |
| `/api/notes/{note_id}/versions` | GET | Get version history |
| `/api/notes/{note_id}/diff` | GET | Get diff between versions |
| `/api/search/` | GET | Search notes |
| `/api/vault/` | GET | Vault directory tree |
| `/api/vault/read` | GET | Read a file's content |
| `/api/vault/vaults` | GET | List all vaults |
| `/api/vault/image` | GET | Serve an image from vault |
| `/api/stats/` | GET | Vault statistics |
| `/api/stats/reindex` | POST | Trigger reindex |

### WebSocket

Connect to `ws://localhost:8712/ws` for live updates.

- Send `{"type": "ping"}` → receive `{"type": "pong"}`
- Send `{"type": "subscribe_graph"}` → receive graph updates

### Authentication

If `GUNITA_API_KEY` is set, external agents must provide the key via the `X-API-Key` header:

```bash
curl -H "X-API-Key: my-secret-key" http://127.0.0.1:8712/api/notes/
```

---

## WebSocket

The WebSocket endpoint provides real-time updates:

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| `ping` | Client → Server | Keep-alive heartbeat |
| `pong` | Server → Client | Heartbeat response |
| `subscribe_graph` | Client → Server | Subscribe to graph updates |
| `graph_updated` | Server → Client | Notifies that the graph has changed |
| `refresh_needed` | Server → Client | Requests client to reload data |

Auto-reconnect is built-in (3-second delay after disconnect, 25-second ping interval).

---

## Project Structure

```
src/
├── GUNITA_Specifications.md      # Full API + architecture spec
├── GUNITA_Roadmap.md             # 4-phase development roadmap
├── GUNITA_Tracker.md             # Progress tracker
├── README.md                     # This file
└── gunita/                       # Python package
    ├── __init__.py               # Package metadata
    ├── main.py                   # CLI entry point (Typer)
    ├── server.py                 # FastAPI app factory + WebSocket + auth
    ├── config.py                 # Configuration (env vars)
    ├── api/
    │   ├── __init__.py           # API package
    │   ├── router.py             # Router aggregator
    │   ├── graph.py              # Graph API endpoints
    │   ├── notes.py              # Notes CRUD + versioning + diff
    │   ├── search.py             # Search API endpoints
    │   ├── vault.py              # Vault tree + file read + cross-vault
    │   └── stats.py              # Statistics + reindex
    ├── static/
    │   ├── css/
    │   │   └── style.css         # Themes (dark/light) + responsive layout
    │   └── js/
    │       ├── app.js            # App bootstrap + module wiring
    │       ├── graph.js          # vis-network graph + export + clustering
    │       ├── tree.js           # Vault tree widget
    │       ├── search.js         # Search bar + results
    │       ├── preview.js        # Note preview + embedded images
    │       ├── editor.js         # Note editor + versioning + timeline
    │       ├── stats.js          # Status bar + auto-refresh
    │       ├── toast.js          # Toast notifications
    │       ├── ws.js             # WebSocket client
    │       └── theme.js          # Dark/light theme toggle
    └── templates/
        └── index.html            # SPA shell
```

---

## Features

### Core (Phases 0–3)
- **Force-directed knowledge graph** with vis-network
- **Filesystem vault tree** with expand/collapse
- **Three search modes**: keyword, semantic, hybrid
- **Markdown rendering** with wiki links
- **Note metadata table** with frontmatter
- **Keyboard shortcuts** (Ctrl+K for search)
- **Resizable panels** with drag-to-resize
- **Auto-refresh stats** every 60 seconds
- **URL-based navigation** with browser history

### Advanced (Phase 4)
- **WebSocket live updates** for real-time graph sync
- **Note creation/editing** in-browser with markdown editor
- **Graph export** as PNG and SVG
- **Dark/light theme toggle** with localStorage persistence
- **Mobile-responsive layout** with vertical stacking
- **Agent API key authentication** via `X-API-Key` header
- **Note versioning & diff view** with color-coded diffs
- **Timeline view** for temporal relationships (PRECEDES, FOLLOWS)
- **Graph clustering by tag**
- **Embedded image support** via `![[image.png]]` wiki-style embeds
- **Cross-vault support** via `GUNITA_EXTRA_VAULTS`
- **XSS protection** via DOMPurify sanitization

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` / `Cmd+K` | Focus search bar |
| `Ctrl+N` / `Cmd+N` | Create new note |
| `Ctrl+E` / `Cmd+E` | Edit current note |
| `Escape` | Close modals / cancel edit |

---

## Architecture

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Vault Disk  │────▶│  Gunita (FastAPI)    │────▶│  Browser (SPA)   │
│  (.md files) │     │                      │     │                  │
│              │     │  ┌────────────────┐  │     │  - Graph (vis.js)│
│  SQLite DB   │────▶│  │ bfai Python API│  │────▶│  - Tree (DOM)    │
│  (bfai.db)   │     │  │ (memory.*, db) │  │     │  - Preview (HTML)│
│              │     │  └────────────────┘  │     │  - Editor (textarea)│
│  Qdrant      │────▶│                      │     │  - Search (fetch)│
│  (optional)  │     │  WebSocket (/ws)     │     │  - Stats (fetch) │
│              │     │  Auth (API Key)      │     │  - Theme toggle  │
└──────────────┘     └──────────────────────┘     └──────────────────┘
```

### Data Flow

1. **Vault** → markdown files on disk
2. **BFAI backend** → SQLite indexes, FTS5 search, relationship graph
3. **Gunita server** → FastAPI REST API + WebSocket
4. **Browser SPA** → vanilla JS + vis-network + marked.js + DOMPurify
5. **External agents** → REST API with optional API key authentication

---

## Development

### Run in development mode

```bash
GUNITA_RELOAD=true gunita serve
```

This enables auto-reloading when source files change.

### Run tests

```bash
# From the project root
python -m pytest tests/ -v
```

### Project dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `jinja2` | Template engine |
| `typer` | CLI framework |
| `httpx` | HTTP client (Qdrant check) |
| `vis-network` (CDN) | Graph visualization |
| `marked.js` (CDN) | Markdown rendering |
| `DOMPurify` (CDN) | XSS sanitization |

### Customizing the Theme

The theme is controlled by CSS custom properties. To add a new theme:

1. Add a new `[data-theme="your-theme"]` block in `style.css`
2. Update `theme.js` to recognize the new theme name
3. All components will automatically pick up the new variables

---

*Gunita — "memory" in Filipino. Built for local-first knowledge exploration.*