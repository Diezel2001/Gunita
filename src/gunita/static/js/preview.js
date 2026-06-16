/* ═══════════════════════════════════════════════════════════════════════
   preview.js — Note preview panel with chunk highlighting
   ═══════════════════════════════════════════════════════════════════════ */

const PreviewManager = (() => {
    let emptyEl = null;
    let noteEl = null;
    let titleEl = null;
    let pathEl = null;
    let tagsEl = null;
    let metaEl = null;
    let bodyEl = null;

    // Pending highlight info after loadNote
    let _pendingHighlight = null;

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
     * @param {string} noteId - The note ID to load.
     * @param {object} [options] - Optional highlight options.
     * @param {string} [options.chunkId] - Specific chunk ID to highlight.
     * @param {string[]} [options.headingPath] - Heading path to scroll to.
     */
    async function loadNote(noteId, options) {
        if (!noteId) {
            showEmpty();
            return;
        }

        _pendingHighlight = null;

        try {
            const resp = await fetch(`/api/notes/${noteId}`);
            if (resp.ok) {
                const note = await resp.json();

                // If we have a chunk to highlight, fetch chunks for the note
                if (options && options.chunkId) {
                    try {
                        const chunksResp = await fetch(`/api/notes/${noteId}/chunks`);
                        if (chunksResp.ok) {
                            const chunksData = await chunksResp.json();
                            const targetChunk = chunksData.chunks.find(
                                c => c.chunk_id === options.chunkId
                            );
                            if (targetChunk) {
                                _pendingHighlight = {
                                    chunkId: options.chunkId,
                                    headingPath: targetChunk.heading_path,
                                    headingText: targetChunk.section_heading,
                                };
                            }
                        }
                    } catch (e) {
                        console.warn('Failed to fetch chunks for highlighting:', e);
                    }
                } else if (options && options.headingPath) {
                    // If we have a heading path but no chunkId, use the heading
                    _pendingHighlight = {
                        chunkId: null,
                        headingPath: options.headingPath,
                        headingText: options.headingPath[options.headingPath.length - 1] || '',
                    };
                }

                displayNote(note);
                // Update URL hash for navigation
                updateHash(`#/note/${noteId}`);

                // Scroll to highlighted chunk after render
                if (_pendingHighlight) {
                    setTimeout(() => {
                        scrollToChunk(_pendingHighlight);
                        _pendingHighlight = null;
                    }, 200);
                }

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

        // If we have a pending highlight, render with chunk markers
        if (_pendingHighlight) {
            bodyEl.innerHTML = renderMarkdownWithChunkMarkers(
                content,
                _pendingHighlight.chunkId,
                _pendingHighlight.headingPath
            );
        } else {
            bodyEl.innerHTML = renderMarkdown(content);
        }

        // Wire up quick-add button if available
        const quickAddBtn = document.getElementById('quick-add-btn');
        if (quickAddBtn && note.note_id) {
            quickAddBtn.style.display = '';
            quickAddBtn.onclick = () => {
                if (typeof EditorManager !== 'undefined' && EditorManager.showQuickAdd) {
                    EditorManager.showQuickAdd(note.note_id);
                }
            };
        }
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
     */
    function renderMeta(note) {
        if (!metaEl) return;
        metaEl.innerHTML = '';

        const meta = [];
        if (note.created_at) meta.push(['Created', note.created_at]);
        if (note.updated_at) meta.push(['Updated', note.updated_at]);

        if (note.metadata && typeof note.metadata === 'object') {
            const skipKeys = new Set(['title', 'tags']);
            for (const [key, value] of Object.entries(note.metadata)) {
                if (!skipKeys.has(key.toLowerCase()) && value) {
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
     * Render markdown with chunk marker divs around each heading section.
     * This allows us to scroll to and highlight a specific chunk.
     *
     * @param {string} content - Raw markdown content.
     * @param {string|null} targetChunkId - The chunk ID to highlight.
     * @param {string[]} targetHeadingPath - The heading path of the target chunk.
     * @returns {string} HTML string with chunk markers.
     */
    function renderMarkdownWithChunkMarkers(content, targetChunkId, targetHeadingPath) {
        if (!targetChunkId) {
            return renderMarkdown(content);
        }

        // Split content by headings to identify sections
        const headingRegex = /^(#{1,6}\s+.*)$/gm;
        const sections = [];
        let lastIndex = 0;
        let currentSection = '';
        let currentHeading = '';

        // Parse content into sections
        const lines = content.split('\n');
        for (const line of lines) {
            if (headingRegex.test(line)) {
                // Store the previous section
                if (currentSection || currentHeading) {
                    sections.push({ heading: currentHeading, body: currentSection });
                }
                currentHeading = line;
                currentSection = '';
                // Reset regex lastIndex since we used exec-based approach
                headingRegex.lastIndex = 0;
            } else {
                currentSection += line + '\n';
            }
        }
        // Store the last section
        if (currentHeading || currentSection) {
            sections.push({ heading: currentHeading, body: currentSection });
        }

        // Render each section, wrapping the target section in a highlight marker
        let html = '';
        for (const section of sections) {
            // Determine if this section matches the target heading
            const isTargetSection = _isTargetSection(section.heading, targetHeadingPath);

            // Render the heading
            if (section.heading) {
                const headingHtml = renderMarkdown(section.heading.trim()) ||
                    escapeHtml(section.heading.trim());
                html += headingHtml;
            }

            // Render the body, wrapped in a highlight marker if target
            const bodyHtml = renderMarkdown(section.body.trim());
            if (isTargetSection) {
                html += `<div class="chunk-highlight" data-chunk-id="${targetChunkId}">${bodyHtml}</div>`;
            } else {
                html += bodyHtml;
            }
        }

        return html;
    }

    /**
     * Check if a heading matches the last element of a target heading path.
     */
    function _isTargetSection(headingText, targetHeadingPath) {
        if (!targetHeadingPath || targetHeadingPath.length === 0 || !headingText) {
            return false;
        }
        // Extract heading text without the # prefix
        const cleanHeading = headingText.replace(/^#+\s+/, '').trim();
        const targetHeading = targetHeadingPath[targetHeadingPath.length - 1].trim();

        // Compare normalized versions
        return cleanHeading.toLowerCase() === targetHeading.toLowerCase();
    }

    /**
     * Scroll to and animate a highlighted chunk element in the preview.
     */
    function scrollToChunk(highlightInfo) {
        if (!bodyEl || !highlightInfo) return;

        const { chunkId } = highlightInfo;
        if (!chunkId) return;

        const el = bodyEl.querySelector(`[data-chunk-id="${chunkId}"]`);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // Add flash animation
            el.classList.add('chunk-highlight-active');
            setTimeout(() => {
                el.classList.remove('chunk-highlight-active');
            }, 2500);
        }
    }

    /**
     * Attach wiki link click handlers to the preview body.
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