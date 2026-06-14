/* ═══════════════════════════════════════════════════════════════════════
   preview.js — Note preview panel
   ═══════════════════════════════════════════════════════════════════════ */

const PreviewManager = (() => {
    let emptyEl = null;
    let noteEl = null;
    let titleEl = null;
    let pathEl = null;
    let tagsEl = null;
    let metaEl = null;
    let bodyEl = null;

    /**
     * Initialize preview panel element references.
     */
    function init() {
        emptyEl = document.getElementById('preview-empty');
        noteEl = document.getElementById('preview-note');
        titleEl = document.getElementById('preview-title');
        pathEl = document.getElementById('preview-path');
        tagsEl = document.getElementById('preview-tags');
        metaEl = document.getElementById('preview-meta');
        bodyEl = document.getElementById('preview-body');
    }

    /**
     * Load and display a note by its note_id.
     */
    async function loadNote(noteId) {
        if (!noteId) {
            showEmpty();
            return;
        }

        try {
            const resp = await fetch(`/api/notes/${noteId}`);
            if (resp.ok) {
                const note = await resp.json();
                displayNote(note);
                // Update URL hash for navigation
                updateHash(`#/note/${noteId}`);
                return;
            }
            // If note not found via notes API, try as vault file
            showEmpty();
        } catch (err) {
            console.error('Failed to load note:', err);
            showEmpty();
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load note', 'error');
            }
        }
    }

    /**
     * Load and display note from a file path (for tree clicks).
     */
    async function loadFile(filePath) {
        try {
            const params = new URLSearchParams({ path: filePath });
            const resp = await fetch(`/api/vault/read?${params}`);
            if (resp.ok) {
                const file = await resp.json();
                displayRawMarkdown(file.content, file.name, filePath);
            }
        } catch (err) {
            console.error('Failed to load file:', err);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load file', 'error');
            }
        }
    }

    /**
     * Display a structured note from the API.
     */
    function displayNote(note) {
        emptyEl.style.display = 'none';
        noteEl.style.display = 'block';

        titleEl.textContent = note.title || '(untitled)';
        pathEl.textContent = note.path || '';

        tagsEl.innerHTML = '';
        for (const tag of (note.tags || [])) {
            const pill = document.createElement('span');
            pill.className = 'tag-pill';
            pill.textContent = tag;
            tagsEl.appendChild(pill);
        }

        // Render metadata table
        renderMeta(note);

        const content = note.content || '';
        bodyEl.innerHTML = renderMarkdown(content);
    }

    /**
     * Display raw markdown content (from file read).
     */
    function displayRawMarkdown(content, name, path) {
        emptyEl.style.display = 'none';
        noteEl.style.display = 'block';

        titleEl.textContent = name || '(untitled)';
        pathEl.textContent = path || '';
        tagsEl.innerHTML = '';
        if (metaEl) metaEl.innerHTML = '';

        bodyEl.innerHTML = renderMarkdown(content);
    }

    /**
     * Render the note metadata table from note properties.
     * Shows created_at, updated_at, and frontmatter key-value pairs from metadata dict.
     */
    function renderMeta(note) {
        if (!metaEl) return;
        metaEl.innerHTML = '';

        const meta = [];
        if (note.created_at) meta.push(['Created', note.created_at]);
        if (note.updated_at) meta.push(['Updated', note.updated_at]);

        // Add frontmatter metadata from the metadata dict
        if (note.metadata && typeof note.metadata === 'object') {
            const skipKeys = new Set(['title', 'tags']);
            for (const [key, value] of Object.entries(note.metadata)) {
                if (!skipKeys.has(key.toLowerCase()) && value) {
                    // Capitalize first letter of key
                    const label = key.charAt(0).toUpperCase() + key.slice(1);
                    meta.push([label, String(value)]);
                }
            }
        }

        if (meta.length === 0) {
            metaEl.style.display = 'none';
            return;
        }

        metaEl.style.display = 'block';
        const table = document.createElement('table');
        table.className = 'meta-table';
        for (const [key, value] of meta) {
            const tr = document.createElement('tr');
            const tdKey = document.createElement('td');
            tdKey.textContent = key;
            const tdVal = document.createElement('td');
            tdVal.textContent = value;
            tr.appendChild(tdKey);
            tr.appendChild(tdVal);
            table.appendChild(tr);
        }
        metaEl.appendChild(table);
    }

    /**
     * Render markdown content with wiki link support and embedded images.
     * Converts [[note-name]] to clickable links that trigger note loading.
     * Converts ![[image.png]] to <img> tags using the vault image API.
     */
    function renderMarkdown(content) {
        // First pass: convert embedded images ![[image.png]] to <img> tags
        let processed = content.replace(
            /!\[\[([^\]]+\.(png|jpg|jpeg|gif|svg|webp))\]\]/gi,
            '<img class="vault-image" src="/api/vault/image?path=$1" alt="$1" loading="lazy" />'
        );

        // Second pass: convert wiki links [[note-name]] to clickable links
        processed = processed.replace(
            /\[\[([^\]]+)\]\]/g,
            '<a class="wiki-link" data-note="$1" href="#">$1</a>'
        );

        // Render through marked.js
        let html;
        if (typeof marked !== 'undefined') {
            html = marked.parse(processed);
        } else {
            html = `<pre>${escapeHtml(content)}</pre>`;
        }

        // Sanitize with DOMPurify if available
        if (typeof DOMPurify !== 'undefined') {
            html = DOMPurify.sanitize(html, {
                ADD_TAGS: ['img'],
                ADD_ATTR: ['src', 'alt', 'loading', 'class'],
            });
        }

        return html;
    }

    /**
     * Attach wiki link click handlers to the preview body.
     * Should be called after rendering markdown content.
     */
    function attachWikiLinkHandlers() {
        if (!bodyEl) return;
        bodyEl.querySelectorAll('.wiki-link').forEach((link) => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const noteId = link.dataset.note;
                if (noteId) {
                    loadNote(noteId);
                    // Highlight in graph
                    if (typeof GraphManager !== 'undefined') {
                        GraphManager.clearHighlights();
                        GraphManager.highlightMatches(new Set([noteId]));
                    }
                }
            });
        });
    }

    /**
     * Show the empty state.
     */
    function showEmpty() {
        emptyEl.style.display = '';
        noteEl.style.display = 'none';
        updateHash('');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Update the URL hash for navigation.
     */
    function updateHash(hash) {
        if (window.location.hash !== hash) {
            history.pushState({ noteId: hash }, '', hash || window.location.pathname);
        }
    }

    return { init, loadNote, loadFile, showEmpty, attachWikiLinkHandlers, displayNote };
})();