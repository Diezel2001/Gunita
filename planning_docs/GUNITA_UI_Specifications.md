# Gunita — UI Specifications

**Version:** 0.3.0
**Last Updated:** 2026-06-14
**Status:** Active

---

## Design Language

### Design Philosophy

- **Minimalist and distraction-free** — No visual clutter, every element serves a purpose
- **Professional and technical** — Designed for engineers, researchers, and knowledge workers
- **Neutral color palette only** — No bright colors, no gradients, no playful aesthetics
- **Information density and clarity** — Maximize usable content area, compact layout
- **Dark mode first** — Primary theme is dark, light mode is secondary
- **Clean typography** — System fonts for performance, monospace for code
- **Plenty of whitespace** — Breathing room between elements despite density
- **Subtle animations only** — Transitions under 200ms, no flashy effects
- **No skeuomorphism** — Flat design, no textures or faux-3D
- **No excessive shadows** — Minimal, low-opacity shadows only
- **No consumer-app aesthetics** — This is a tool, not a toy

### Visual Style

| Attribute | Value |
|-----------|-------|
| **Style** | Modern knowledge-explorer interface |
| **Theme** | Dark mode first, light mode supported |
| **Typography** | System sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`) |
| **Mono font** | `'Cascadia Code', 'Fira Code', 'Consolas', monospace` |
| **Base font size** | 13px |
| **Color system** | CSS custom properties with neutral, desaturated palette |
| **Border radius** | 3–8px (subtle rounding) |
| **Spacing** | 4–16px grid (compact layout) |
| **Shadows** | Low-opacity, minimal (`rgba(0, 0, 0, 0.3)` at most) |
| **Gradients** | None — flat color fills only |

---

## Layout

### Overall Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Top Bar: Search + Mode Toggle + Theme Toggle + WS Status  │
├───────────┬───────────────────────────┬─────────────────────┤
│           │                           │                     │
│   Left    │      Center Panel         │     Right Panel     │
│   Panel   │      (3D Knowledge Graph) │   (Note Preview/    │
│  (Vault   │      Three.js + d3-force  │     Editor)         │
│   Tree)   │                           │                     │
│           │                           │                     │
│  240px    │       Flexible            │      340px          │
│  [min:160]│                           │   [min:240, max:600]│
│  [max:400]│                           │                     │
├───────────┴───────────────────────────┴─────────────────────┤
│  Status Bar: Reindex + Embed Toggle + Stats + Vectors      │
└─────────────────────────────────────────────────────────────┘
```

### Panels

| Panel | Default Width | Min | Max | Resizable | Content |
|-------|--------------|-----|-----|-----------|---------|
| **Left (Tree)** | 240px | 160px | 400px | ✅ Drag handle | Vault file tree, new note button |
| **Center (Graph)** | Flexible | — | — | ✅ Via adjacent panels | 3D force-directed knowledge graph |
| **Right (Preview)** | 340px | 240px | 600px | ✅ Drag handle | Note preview, editor, version history |

### Responsive Breakpoints

| Breakpoint | Behavior |
|------------|----------|
| `> 900px` | Three-panel horizontal layout (default) |
| `≤ 900px` | Stacked vertical layout: Graph → Tree → Preview |
| `≤ 600px` | Compact search modes, stacked graph export/filters |

---

## Components

### 1. Top Bar (`#topbar`)

| Element | Type | Description |
|---------|------|-------------|
| Search input | `input[type="text"]` | Full-width search field with placeholder |
| Mode toggles | `input[type="radio"]` × 3 | Keyword / Semantic / Hybrid radio buttons |
| Search button | `button` | Triggers search, shows "⏳ Searching..." during load |
| Theme toggle | `button` | Toggles dark/light mode (`🌓`) |
| WebSocket status | `span` | Shows connection status (`⚪` / `🟢` / `🔴`) |

**Dimensions:** Height 48px, background `--bg-secondary`

### 2. Status Bar (`#statusbar`)

| Element | Type | Description |
|---------|------|-------------|
| Reindex button | `button` | Triggers incremental reindex, shows "⏳ Reindexing..." |
| Embed toggle | `checkbox` + label | Enable vector embedding during reindex |
| Notes count | `span` | "Notes: N" |
| Relationships | `span` | "Rels: N" |
| Tags count | `span` | "Tags: N" |
| Files count | `span` | "Files: N (M unindexed)" — orange when unindexed > 0 |
| Qdrant status | `span` | "Qdrant: 🟢" or "Qdrant: ⚫" |
| Vector count | `span` | "Vectors: N" |
| Last reindex | `span` | "Last: timestamp" |

**Dimensions:** Height 32px, background `--bg-secondary`

### 3. Vault Tree Panel (`#tree-panel`)

| Element | Description |
|---------|-------------|
| Panel header | "📁 Vault" + "＋" new note button |
| Tree nodes | Recursive file/folder structure with expand/collapse toggles |
| Node icons | 📂/📁 folders, 📄 files, with toggle arrows (▶/▼) |
| Active state | Blue background highlight on selected node |
| Empty state | "No files in vault" message |

**Interaction:** Click node → loads file in preview panel

### 4. 3D Knowledge Graph Panel (`#graph-panel`)

**Centerpiece visualization** using `3d-force-graph` (Three.js + d3-force-3d).

| Element | Description |
|---------|-------------|
| Graph container | Full-panel 3D force-directed graph |
| Export buttons | 📷 PNG (top-right, semi-transparent) |
| Edge filter | Collapsible list of relationship types with checkboxes |
| Tag filter | Collapsible dropdown to filter by tag |
| Cluster toggle | Checkbox to cluster nodes by tag |
| Legend | Collapsible color-coded relationship type legend |
| Empty state | "🕸️ No notes in graph" centered message |
| Loading overlay | Semi-transparent overlay with spinner during data load |

#### Nodes

- **Default:** Small spheres, grayish (`#4A5568`)
- **Tagged:** Muted tag color from palette
- **Hovered:** `#5B7B9A` (accent blue)
- **Selected/matched:** `#5B9A7B` (accent green)
- **Size:** Based on connection count (`3 + degree × 1.5`)
- **Opacity:** 0.9
- **Resolution:** 12-sided spheres
- **Tooltip:** HTML overlay showing note title on hover
- **Draggable:** Nodes can be repositioned in 3D space

#### Edges

- **Width:** 0.5px
- **Opacity:** 0.3
- **Arrows:** Subtle directional arrows (length: 3)
- **Curvature:** 0.1 (slight curve for readability)
- **Color:** Mapped to relationship type

#### Camera Controls

| Control | Action |
|---------|--------|
| Left drag | Orbit around center |
| Right drag | Pan |
| Scroll | Zoom in/out |
| Click node | Focus camera + open note preview |
| Double-click node | Open note preview |
| Hover node | Highlight node + show title tooltip |
| Drag node | Reposition in 3D space |

**Camera animation:** Smooth 1000ms transition on focus/search

**Search integration:** `focusNode()` animates camera to target node

#### Edge Colors by Relationship

| Relationship | Color | Hex |
|-------------|-------|-----|
| Link (EXPLICIT_LINK) | Slate blue | `#6B8DAD` |
| Dependency | Muted red | `#AD6B6B` |
| Structural | Muted green | `#6BAD8D` |
| Semantic | Muted cyan | `#6BADAD` |
| Causal | Muted amber | `#AD8D6B` |
| Temporal | Gray | `#6B7280` |
| Person | Light gray | `#A0A8B3` |
| Other | Medium gray | `#6B7280` |

### 5. Preview Panel (`#preview-panel`)

| State | Content |
|-------|---------|
| **Empty** | "📝 Select a note to preview" + "Ctrl+K to search" hint |
| **Preview** | Title, path, tags (pill badges), metadata table, markdown body |
| **Editor** | Title input, tags input, textarea, Save/Cancel buttons |
| **Version history** | Version list (number, date, hash, size) + diff view |
| **Timeline** | Relationship timeline with colored dots and connecting lines |

**Preview actions bar:** ✏️ Edit + 🕐 Version history (shown when note is loaded)

### 6. Search Results Dropdown (`#search-results`)

| Element | Description |
|---------|-------------|
| Container | Absolute-positioned, centered below search bar |
| Result item | Title (bold), section heading (italic, blue, left-bordered), path (gray), snippet (if available) |
| Max height | 400px with vertical scroll |
| Width | 600px (95vw on mobile) |
| Shadow | `0 4px 12px rgba(0, 0, 0, 0.3)` |

**Interaction:** Click result → loads note in preview, animates camera to node in 3D graph

### 7. New Note Modal (`#new-note-modal`)

| Element | Description |
|---------|-------------|
| Overlay | Semi-transparent black backdrop |
| Modal | Centered card (500px width, max 90vw) |
| Title input | Note title |
| Content textarea | Markdown content (200px min height) |
| Tags input | Comma-separated tags |
| Actions | Create (primary blue) / Cancel buttons |

### 8. Toast Notifications (`#toast-container`)

| Type | Color | Icon |
|------|-------|------|
| Success | `--accent-green` left border | ✓ |
| Error | `#C86464` left border | ✗ |
| Warning | `#B89B5B` left border | ⚠ |
| Info | `--accent-blue` left border | ℹ |

**Behavior:** Slide in from right, auto-dismiss, stacked vertically at bottom-right

---

## Interactions

### Animations & Transitions

| Element | Transition | Duration |
|---------|-----------|----------|
| Panel resizer hover | Background color | 150ms ease |
| Filter toggle arrow | Rotate transform | 150ms ease |
| Legend collapse | max-height + opacity | 200ms ease |
| Toast enter | opacity + translateX | 300ms ease |
| Toast exit | opacity + translateX | 300ms ease |
| 3D graph camera focus | Position interpolation | 1000ms |
| Search button loading | Text change | Instant |
| Reindex button loading | Text change + opacity | Instant |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Focus search input |
| `Ctrl/Cmd + N` | Open new note modal |
| `Ctrl/Cmd + E` | Edit current note |
| `Escape` | Close modals / cancel edit |

### Drag Interactions

| Handle | Action | Constraints |
|--------|--------|-------------|
| Left resizer (`#resizer-left`) | Resize tree panel width | min: 160px, max: 400px |
| Right resizer (`#resizer-right`) | Resize preview panel width | min: 240px, max: 600px |
| 3D graph nodes | Reposition in 3D space | Free movement |

**Visual feedback:** Resizer turns `--accent-blue` on hover, cursor changes to `col-resize`

### Optimistic Updates

| Action | Behavior |
|--------|----------|
| Create note | Modal closes immediately, tree/graph reload, toast shown |
| Save edit | Editor closes, preview refreshes, toast shown |
| Reindex | Button shows loading state, stats refresh on completion |
| Delete note | Confirmation, tree/graph refresh, toast shown |

---

## Search Modes

| Mode | Backend | Behavior |
|------|---------|----------|
| **Keyword** | SQLite FTS5 | BM25 full-text search with multi-factor ranking |
| **Semantic** | Qdrant + embedding provider | Vector similarity search with chunked embeddings |
| **Hybrid** | FTS5 + Qdrant combined | Weighted merge (30% keyword + 70% semantic) |

**Fallback:** If Qdrant is unavailable, semantic/hybrid modes auto-fallback to keyword mode. Radio buttons are visually disabled (40% opacity).

**Deduplication:** Semantic and hybrid results are deduplicated by `note_id` — highest-scoring chunk per note is returned with its `section_heading`.

---

## Theme System

### Color Palette (Dark Theme — default)

Engineer-grade, neutral palette with desaturated accents:

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#0F1115` | Page background, near-black |
| `--bg-secondary` | `#161A20` | Surface (panels, cards) |
| `--bg-tertiary` | `#1D222B` | Elevated surface (modals, dropdowns) |
| `--bg-hover` | `#232A34` | Hover state |
| `--bg-active` | `#1A2A3A` | Active/selected state |
| `--text-primary` | `#E6E8EB` | Primary text |
| `--text-secondary` | `#A0A8B3` | Secondary text, labels |
| `--text-muted` | `#6B7280` | Muted text, placeholders |
| `--accent-blue` | `#5B7B9A` | Muted slate blue — primary accent |
| `--accent-green` | `#5B9A7B` | Desaturated teal — success states |
| `--accent-border` | `#2A313C` | Borders, subtle dividers |
| `--border-color` | `#2A313C` | Panel borders, separators |

**Semantic colors (not in CSS vars):**
| Color | Hex | Usage |
|-------|-----|-------|
| Error red | `#C86464` | Error toasts, diff removed |
| Warning amber | `#B89B5B` | Warning toasts |
| Derived orange | `#A07B5B` | Timeline "derived from" |
| Replaced rose | `#9A5B6B` | Timeline "replaced by" |

### Light Theme

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#FAFBFC` | Page background |
| `--bg-secondary` | `#F1F3F5` | Surface |
| `--bg-tertiary` | `#E5E8EB` | Elevated surface |
| `--bg-hover` | `#DEE2E6` | Hover state |
| `--bg-active` | `#D0D8E2` | Active/selected state |
| `--text-primary` | `#1A1D21` | Primary text |
| `--text-secondary` | `#5A6270` | Secondary text |
| `--text-muted` | `#9CA3AF` | Muted text |
| `--accent-blue` | `#4A6A8A` | Primary accent |
| `--accent-green` | `#4A8A6A` | Success states |
| `--accent-border` | `#D1D5DB` | Borders |
| `--border-color` | `#D1D5DB` | Separators |

---

## API Endpoints Used by UI

| Method | Endpoint | Used By | Description |
|--------|----------|---------|-------------|
| GET | `/api/stats/` | `StatsManager` | Vault statistics (notes, rels, tags, files, vectors, Qdrant status) |
| POST | `/api/stats/reindex?embed=&provider=` | `StatsManager` | Trigger incremental reindex with optional embedding |
| GET | `/api/search/?q=&mode=&limit=` | `SearchManager` | Search notes (keyword/semantic/hybrid) |
| GET | `/api/graph/` | `GraphManager` | Load 3D graph data (nodes + edges) |
| GET | `/api/notes/` | `TreeManager` | List vault files |
| GET | `/api/notes/{id}` | `PreviewManager` | Load a single note |
| GET | `/api/notes/{id}/versions` | `EditorManager` | Version history |
| POST | `/api/notes/` | `EditorManager` | Create a new note |
| PUT | `/api/notes/{id}` | `EditorManager` | Update a note |
| DELETE | `/api/notes/{id}` | `EditorManager` | Delete a note |
| WS | `/ws` | `WsManager` | Live updates (graph changes, search results) |

---

## File Structure

```
src/gunita/
├── static/
│   ├── css/
│   │   └── style.css           # All styles (dark/light themes, responsive)
│   └── js/
│       ├── app.js              # Bootstrap, cross-module wiring, keyboard shortcuts
│       ├── editor.js           # Note create/edit with versioning
│       ├── graph.js            # 3D force-directed graph (3d-force-graph/Three.js)
│       ├── preview.js          # Note preview with markdown rendering
│       ├── search.js           # Search bar + results dropdown
│       ├── stats.js            # Status bar + reindex trigger
│       ├── theme.js            # Dark/light theme toggle
│       ├── toast.js            # Toast notification system
│       ├── tree.js             # Vault file tree
│       └── ws.js               # WebSocket live updates
├── templates/
│   └── index.html              # Main HTML template
├── api/
│   ├── graph.py                # Graph API endpoints
│   ├── notes.py                # Notes CRUD API
│   ├── router.py               # API router aggregation
│   ├── search.py               # Search API (keyword/semantic/hybrid)
│   ├── stats.py                # Stats + reindex API
│   └── vault.py                # Vault file operations
├── server.py                   # FastAPI app factory
└── config.py                   # Settings (host, port, vault path, Qdrant)
```

### External Dependencies (CDN)

| Library | Version | Purpose |
|---------|---------|---------|
| `3d-force-graph` | 1.73.4 | 3D knowledge graph (wraps Three.js + d3-force-3d) |
| `marked` | latest | Markdown rendering |
| `DOMPurify` | 3.0.6 | XSS protection for rendered HTML |

---

## Accessibility Notes

| Feature | Status |
|---------|--------|
| Keyboard navigation | ✅ Shortcuts for search, new note, edit |
| Focus management | ⚠️ Search auto-focuses on Ctrl+K |
| Screen reader | ❌ No ARIA labels yet |
| High contrast | ⚠️ Dark mode only (light mode available but secondary) |
| Reduced motion | ❌ No `prefers-reduced-motion` handling yet |
| 3D graph accessibility | ❌ No keyboard navigation within graph |