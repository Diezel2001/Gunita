# Gunita — Development Tracker

> **Current Phase:** 4 (Advanced Features) — Complete
> **Started:** 2026-06-13
> **Last Updated:** 2026-06-13

---

## Progress Overview

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 0: Skeleton | ✅ Complete | 100% |
| Phase 1: Core API | ✅ Complete | 100% |
| Phase 2: Frontend Integration | ✅ Complete | 100% |
| Phase 3: Polish & Reliability | ✅ Complete | 100% |
| Phase 4: Advanced Features | ✅ Complete | 100% |

---

## Phase 4: Advanced Features — Complete

| Task | Status | Notes |
|------|--------|-------|
| WebSocket: real-time graph updates | ✅ | `ws_manager` broadcasts in `server.py`, `ws.js` client with auto-reconnect + ping keepalive |
| WebSocket: live search results | ✅ | `WsManager` subscribes on connect, handles `search_results` + `graph_updated` messages |
| Note creation in web UI | ✅ | `POST /api/notes/` + modal dialog (＋ button + Ctrl+N) |
| Note editing in web UI | ✅ | `PUT /api/notes/{note_id}` + inline editor (✏️ button + Ctrl+E) |
| Graph export as PNG | ✅ | `exportPNG()` via `canvas.toDataURL()` → download |
| Graph export as SVG | ✅ | `exportSVG()` wraps PNG data in SVG wrapper → download |
| Dark/light theme toggle | ✅ | CSS custom properties (`[data-theme]`), `theme.js` with localStorage persistence |
| Full markdown with embedded images | ✅ | `![[image.png]]` → `<img>` via `/api/vault/image` endpoint + DOMPurify sanitization |
| Mobile-responsive layout | ✅ | CSS `@media (max-width: 900px)` stacks panels vertically, resize handles switch to row-resize |
| Agent API key authentication | ✅ | `X-API-Key` header verification via `fastapi.security.APIKeyHeader`, optional via `GUNITA_API_KEY` env var |
| Note versioning / diff view | ✅ | Version snapshots in `vault/metadata/versions/`, `GET /api/notes/{id}/versions` + `GET /api/notes/{id}/diff` |
| Graph clustering by tag | ✅ | `#cluster-checkbox` toggle in graph filters UI (vis-network group support) |
| Timeline view for temporal relationships | ✅ | `EditorManager.loadTimeline()` shows PRECEDES/FOLLOWS/DERIVED_FROM edges chronologically |
| Cross-vault support | ✅ | `GUNITA_EXTRA_VAULTS` env var, `GET /api/vault/vaults`, security checks against all vault paths |
| Note deletion | ✅ | `DELETE /api/notes/{note_id}` removes file + DB record |

---

## UI Features Tracker

### Layout & Theme
| Feature | Status | Notes |
|---------|--------|-------|
| Three-panel layout (tree / graph / preview) | ✅ | CSS flexbox-based responsive layout |
| Dark theme | ✅ | VS Code-inspired color scheme (`#1e1e1e` base) |
| Light theme | ✅ | CSS custom properties swap via `[data-theme="light"]`, localStorage persistence |
| Theme toggle button | ✅ | 🌓 button in topbar, respects system `prefers-color-scheme` |
| Custom scrollbars | ✅ | Styled webkit scrollbars with light theme variant |
| Top search bar with mode toggle | ✅ | Keyword / Semantic / Hybrid radio buttons |
| Status bar (bottom) | ✅ | Notes count, rels, tags, files, Qdrant status |
| Reindex button | ✅ | In status bar, shows loading state during reindex |
| Resizable panels | ✅ | Drag-to-resize dividers between tree/graph/preview |
| Keyboard shortcuts (Ctrl+K, Ctrl+N, Ctrl+E) | ✅ | Quick search, new note, edit note |
| Auto-refresh stats | ✅ | Background polling every 60 seconds |
| URL-based navigation | ✅ | `/#/note/{note_id}` deep-links |
| Browser history (back/forward) | ✅ | popstate listener for navigation |

### Graph Visualization (`graph.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Force-directed layout (vis-network) | ✅ | forceAtlas2Based physics solver |
| Node color by tag | ✅ | Deterministic hash-based color selection |
| Node sizing by degree | ✅ | 12px base + 3px per connection (max 42px) |
| Edge color by relationship type | ✅ | 9 category color mappings |
| Node click → select + preview | ✅ | Wires to preview panel |
| Hover tooltips on nodes | ✅ | Shows title, ID, connections, tags |
| Hover tooltips on edges | ✅ | Shows relationship type |
| Graph legend overlay | ✅ | Floating legend in bottom-right corner |
| Graph legend toggle (collapse/expand) | ✅ | Click header to toggle with animation |
| Search match highlighting | ✅ | Green border on matching nodes + focus |
| Clear highlights | ✅ | Resets all node borders to default |
| Edge filter by relationship type | ✅ | Checkbox list to show/hide edge categories |
| Filter by tag | ✅ | Dropdown to filter nodes by tag |
| Empty state message | ✅ | "No notes in graph" with icon when empty |
| Graph export as PNG | ✅ | 📷 button → canvas.toDataURL → download |
| Graph export as SVG | ✅ | 🖼️ button → SVG wrapper → download |
| Graph clustering by tag | ✅ | Cluster by Tag checkbox toggle |

### Vault Tree (`tree.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Recursive directory rendering | ✅ | Fetches from `/api/vault/` |
| Directory expand/collapse | ✅ | Toggle arrow (▼/▶) |
| File type icons | ✅ | 📁 directories, 📄 notes, 📎 other files |
| Click `.md` file → preview | ✅ | Loads via `/api/vault/read` |
| Active file highlighting | ✅ | Blue background on selected file |

### Search (`search.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Search form submission | ✅ | Enter or click 🔍 button |
| Dropdown results panel | ✅ | Overlay with result items |
| Result click → preview | ✅ | Loads note + highlights in graph |
| Click outside → dismiss | ✅ | Hides dropdown on outside click |
| Mode toggle (keyword/semantic/hybrid) | ✅ | Radio button selection |
| Empty query guard | ✅ | Prevents empty searches |
| Result snippets/excerpts | ✅ | Shows matching text snippet under each result |

### Note Preview (`preview.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Note title display | ✅ | Large bold heading |
| Path display | ✅ | Relative path in muted text |
| Tag pills | ✅ | Styled pill badges |
| Metadata table | ✅ | Shows created_at, updated_at, frontmatter key-value pairs |
| Markdown rendering (marked.js) | ✅ | Full markdown → HTML |
| Wiki link rendering | ✅ | `[[note-name]]` → clickable link, click loads note |
| Embedded image display | ✅ | `![[image.png]]` → `<img>` via `/api/vault/image` |
| XSS sanitization | ✅ | DOMPurify sanitization of rendered markdown |
| Empty state message | ✅ | Styled empty state with icon and shortcut hint |

### Note Editor (`editor.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| New note modal | ✅ | ＋ button / Ctrl+N → modal with title, content, tags |
| Inline note editing | ✅ | ✏️ button / Ctrl+E → textarea editor with title + tags |
| Save note | ✅ | POST (create) or PUT (update) with graph/tree refresh |
| Cancel editing | ✅ | Cancel button / Escape key |
| Version history | ✅ | 🕐 button → version list with timestamps |
| Diff view | ✅ | Click version → diff with added/removed/unchanged lines |
| Timeline view | ✅ | Temporal relationship visualization |

### Status Bar (`stats.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Notes count display | ✅ | From `/api/stats/` |
| Relationships count | ✅ | From `/api/stats/` |
| Tags count | ✅ | From `/api/stats/` |
| Files on disk count | ✅ | Orange warning if unindexed |
| Qdrant status indicator | ✅ | 🟢 connected / ⚫ unavailable |
| Reindex trigger | ✅ | POST to `/api/stats/reindex` |
| Post-reindex refresh | ✅ | Reloads stats + graph + tree |
| Auto-refresh (60s) | ✅ | Background polling, pauses when tab hidden |

### SPA & App Bootstrap (`app.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Module wiring (callbacks) | ✅ | Connects graph ↔ tree ↔ search ↔ preview ↔ editor ↔ ws ↔ theme |
| DOM-ready initialization | ✅ | Handles both states (loading vs loaded) |
| Error-free bootstrap | ✅ | Graceful init of all modules |
| URL routing / hash navigation | ✅ | `/#/note/{note_id}` deep-link support |
| Browser history (back/forward) | ✅ | popstate listener for navigation |
| Keyboard shortcuts (Ctrl+K, Ctrl+N, Ctrl+E) | ✅ | Focus search, new note, edit note |
| Resizable panels | ✅ | Drag-to-resize dividers |
| Loading spinners | ✅ | Overlay spinner during graph/tree/search loads |
| Toast notifications on errors | ✅ | Non-intrusive toasts for all API failures |
| Auto-refresh stats (periodic) | ✅ | `StatsManager.startAutoRefresh()` every 60s |
| WebSocket integration | ✅ | Auto-reconnect, live graph updates |
| Theme initialization | ✅ | `ThemeManager.init()` on startup |

### WebSocket (`ws.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Auto-connect on page load | ✅ | `ws://` or `wss://` based on protocol |
| Auto-reconnect | ✅ | 3-second delay after disconnect |
| Ping/pong heartbeat | ✅ | 25-second interval |
| Graph update notifications | ✅ | `graph_updated` message → reload graph + tree + stats |
| Status indicator | ✅ | 🟢 connected / ⚫ disconnected in topbar |

### Theme Toggle (`theme.js`)
| Feature | Status | Notes |
|---------|--------|-------|
| Dark theme (default) | ✅ | VS Code-inspired colors |
| Light theme | ✅ | White/grey colors with adjusted accents |
| Toggle button | ✅ | 🌓 in topbar |
| localStorage persistence | ✅ | Remembers across sessions |
| System preference detection | ✅ | Uses `prefers-color-scheme` on first visit |

### Authentication (Server)
| Feature | Status | Notes |
|---------|--------|-------|
| API key header verification | ✅ | `X-API-Key` via FastAPI Security |
| Optional authentication | ✅ | Only enforced when `GUNITA_API_KEY` is set |
| 401/403 error responses | ✅ | Clear error messages |

---

## Changelog

### 2026-06-13 (Phase 4 — Advanced Features)
- **WebSocket live updates**: Added `/ws` endpoint with `ConnectionManager` for broadcasting graph/search updates. Auto-reconnect client with heartbeat.
- **Note CRUD**: Full create (`POST`), update (`PUT`), delete (`DELETE`) API endpoints in `notes.py` with `bfai.writer` integration. Frontend has modal for new notes and inline editor for editing.
- **Graph export**: PNG export via `canvas.toDataURL()`, SVG export via SVG wrapper with embedded PNG data. Export buttons in graph panel.
- **Dark/light theme**: CSS custom properties with `[data-theme]` attribute. `theme.js` manages toggle with localStorage persistence and system preference detection. All components adapted for both themes.
- **Embedded images**: `![[image.png]]` wiki-style embeds converted to `<img>` tags via new `/api/vault/image` endpoint. DOMPurify sanitization.
- **Mobile-responsive layout**: CSS media queries stack panels vertically on screens < 900px. Resizer handles switch to row-resize. Search results and modals adapt to viewport.
- **Agent API key authentication**: Optional `GUNITA_API_KEY` env var enables `X-API-Key` header verification on all API endpoints.
- **Note versioning/diff**: Version snapshots saved to `vault/metadata/versions/{note}/v{N}.md`. API endpoints for listing versions and generating unified diffs. Frontend shows version list and color-coded diff view.
- **Timeline view**: `EditorManager.loadTimeline()` displays temporal relationships (PRECEDES, FOLLOWS, DERIVED_FROM, REPLACED_BY) in a chronological timeline UI.
- **Graph clustering**: "Cluster by Tag" checkbox in graph filters UI for tag-based node grouping.
- **Cross-vault support**: `GUNITA_EXTRA_VAULTS` env var for multiple vault paths. `GET /api/vault/vaults` lists available vaults. Security checks validate paths against all allowed vaults.
- **DOMPurify XSS protection**: Added CDN import for DOMPurify, used to sanitize all rendered markdown content.
- **New JS modules**: `ws.js` (WebSocket), `theme.js` (theme toggle), `editor.js` (note editor + versioning + timeline).
- **Config updates**: Added `api_key`, `extra_vaults`, `all_vault_paths` to `Settings`. Version bumped to v0.2.0.

### 2026-06-13 (Phase 3 — Polish & Reliability)
- **Keyboard shortcuts**: Added `Ctrl+K` / `Cmd+K` to focus search input from anywhere.
- **Resizable panels**: Added two drag-to-resize dividers between tree/graph/preview panels.
- **Empty state illustrations**: Graph shows empty state when no nodes. Preview shows styled empty state.
- **Auto-refresh stats**: Stats bar polls `/api/stats/` every 60 seconds.
- **Graph legend toggle**: Click legend header to collapse/expand.
- **URL-based navigation**: Notes load with `/#/note/{note_id}` hash.
- **Browser history integration**: `popstate` listener enables back/forward.
- **Note metadata table**: Preview shows metadata with created_at, updated_at.
- **Graph filters**: Relationship type checkboxes, tag dropdown.
- **Search result snippets**: CSS styling for search result snippets.

### 2026-06-13 (Phase 2 — Frontend Integration)
- **Graph Visualization**: Synced frontend `REL_COLORS` with backend. Loading spinners, error toasters.
- **Vault Tree**: Loading spinner, empty states, performance optimization.
- **Search**: Qdrant awareness, mode switching, XSS protection.
- **Preview**: Wiki link rendering, error handling.
- **Status Bar**: Qdrant status, reindex button, toast notifications.
- **Toast System**: Non-intrusive notifications with auto-dismiss.

### 2026-06-13 (Phase 1)
- **Graph API**: Full graph + neighborhood endpoints with BFS traversal.
- **Notes API**: Paginated listing, detail, backlinks.
- **Search API**: Keyword, semantic, hybrid with graceful fallback.
- **Stats API**: Aggregate counts, reindex, Qdrant check.

### 2026-06-13 (Phase 0)
- Created Gunita project skeleton, API stubs, HTML/CSS/JS frontend, planning docs.

---

## File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `src/gunita/__init__.py` | ~12 | Package metadata |
| `src/gunita/main.py` | ~166 | CLI entry point |
| `src/gunita/server.py` | ~188 | FastAPI app factory + WebSocket + auth |
| `src/gunita/config.py` | ~82 | Configuration (auth, extra vaults) |
| `src/gunita/api/__init__.py` | ~2 | API package |
| `src/gunita/api/router.py` | ~25 | Router aggregator |
| `src/gunita/api/graph.py` | ~238 | Graph endpoints |
| `src/gunita/api/notes.py` | ~480 | Notes CRUD + versioning + diff |
| `src/gunita/api/search.py` | ~180 | Search endpoints |
| `src/gunita/api/vault.py` | ~160 | Vault tree + file read + cross-vault + image |
| `src/gunita/api/stats.py` | ~100 | Stats + reindex |
| `src/gunita/templates/index.html` | ~178 | SPA shell with editor, modal, export |
| `src/gunita/static/css/style.css` | ~600 | Themes + responsive + new components |
| `src/gunita/static/js/app.js` | ~230 | App bootstrap + all module wiring |
| `src/gunita/static/js/graph.js` | ~500 | vis-network + export + clustering |
| `src/gunita/static/js/tree.js` | ~139 | Vault tree widget |
| `src/gunita/static/js/search.js` | ~160 | Search bar |
| `src/gunita/static/js/preview.js` | ~240 | Preview + embedded images + DOMPurify |
| `src/gunita/static/js/editor.js` | ~340 | Note editor + versioning + timeline |
| `src/gunita/static/js/stats.js` | ~124 | Status bar |
| `src/gunita/static/js/toast.js` | ~89 | Toast notifications |
| `src/gunita/static/js/ws.js` | ~100 | WebSocket client |
| `src/gunita/static/js/theme.js` | ~55 | Theme toggle |

---

## API Test Results (2026-06-13)

All endpoints verified with real vault data (16 notes, 23 relationships, 56 tags):

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /api/graph/` | ✅ 200 | 16 nodes, 23 edges |
| `GET /api/graph/{note_id}` | ✅ 200 | 10 nodes, 13 edges (1-hop) |
| `GET /api/notes/` | ✅ 200 | 16 notes (paginated) |
| `GET /api/notes/{note_id}` | ✅ 200 | Full content + metadata |
| `GET /api/notes/{note_id}/backlinks` | ✅ 200 | Backlink list |
| `POST /api/notes/` | ✅ 201 | Creates note in vault |
| `PUT /api/notes/{note_id}` | ✅ 200 | Updates note with version |
| `DELETE /api/notes/{note_id}` | ✅ 200 | Removes note |
| `GET /api/notes/{note_id}/versions` | ✅ 200 | Version list |
| `GET /api/notes/{note_id}/diff` | ✅ 200 | Unified diff |
| `GET /api/search/?q=python` | ✅ 200 | 8 results |
| `GET /api/stats/` | ✅ 200 | Full vault stats |
| `GET /api/vault/` | ✅ 200 | Directory tree |
| `GET /api/vault/vaults` | ✅ 200 | Vault list |
| `GET /api/vault/image` | ✅ 200 | Image file served |
| `WS /ws` | ✅ | WebSocket connected |