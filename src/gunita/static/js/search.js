/* ═══════════════════════════════════════════════════════════════════════
   search.js — Search bar and results (grouped by note)
   ═══════════════════════════════════════════════════════════════════════ */

const SearchManager = (() => {
    let resultsContainer = null;
    let onResultSelect = null;
    let _qdrantAvailable = false;
    let _currentMode = 'keyword';

    /**
     * Initialize the search component.
     */
    function init(resultsEl, selectCallback) {
        resultsContainer = resultsEl;
        onResultSelect = selectCallback;

        // Handle search form submit
        const form = document.getElementById('search-form');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            executeSearch();
        });

        // Handle mode selector change
        const modeSelect = document.getElementById('search-mode-select');
        if (modeSelect) {
            modeSelect.addEventListener('change', () => {
                _currentMode = modeSelect.value;
            });
            _currentMode = modeSelect.value;
        }

        // Hide results on click outside
        document.addEventListener('click', (e) => {
            if (!resultsContainer.contains(e.target) && !e.target.closest('#search-form')) {
                resultsContainer.style.display = 'none';
            }
        });
    }

    /**
     * Update Qdrant availability status.
     * When Qdrant is down, semantic, hybrid, and retrieve modes are disabled.
     */
    function setQdrantStatus(connected) {
        _qdrantAvailable = connected;
        const modeSelect = document.getElementById('search-mode-select');

        if (!modeSelect) return;

        // Enable/disable options that require Qdrant
        for (const option of modeSelect.options) {
            if (option.value === 'semantic' || option.value === 'hybrid' || option.value === 'retrieve') {
                option.disabled = !connected;
            }
        }

        // If current selection is disabled, fall back to keyword
        if (!connected && modeSelect.value !== 'keyword') {
            modeSelect.value = 'keyword';
            _currentMode = 'keyword';
        }
    }

    /**
     * Execute a search query.
     */
    async function executeSearch() {
        const input = document.getElementById('search-input');
        const query = input.value.trim();
        if (!query) return;

        const modeSelect = document.getElementById('search-mode-select');
        let mode = modeSelect?.value || 'keyword';
        _currentMode = mode;

        // Enforce keyword mode if Qdrant is down and mode requires it
        if ((mode === 'semantic' || mode === 'hybrid' || mode === 'retrieve') && !_qdrantAvailable) {
            mode = 'keyword';
            _currentMode = 'keyword';
            if (modeSelect) modeSelect.value = 'keyword';
        }

        const btn = document.getElementById('search-btn');
        const originalText = btn.textContent;
        btn.textContent = '⏳ Searching...';
        btn.disabled = true;

        try {
            const params = new URLSearchParams({ q: query, mode: mode, limit: '20' });
            const resp = await fetch(`/api/search/?${params}`);

            if (mode === 'retrieve') {
                const data = await resp.json();
                displayRetrieveResults(data, query);

                // Highlight matched notes on the graph (direct matches only)
                if (data.direct_matches && data.direct_matches.length > 0) {
                    const ids = new Set(data.direct_matches.map((r) => r.note_id));
                    GraphManager.highlightMatches(ids);
                }
            } else {
                const data = await resp.json();
                displayResults(data.results || [], query);

                // Highlight all matched notes on the graph
                if (data.results && data.results.length > 0) {
                    const ids = new Set(data.results.map((r) => r.note_id));
                    GraphManager.highlightMatches(ids);
                }
            }
        } catch (err) {
            console.error('Search failed:', err);
            resultsContainer.innerHTML =
                `<div class="search-empty-state">Search failed — please try again</div>`;
            resultsContainer.style.display = 'block';
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Search failed', 'error');
            }
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    // ─── Helpers ──────────────────────────────────────────────────────

    /**
     * Group an array of results by note_id.
     * Returns an array of { noteId, title, path, chunks } objects.
     */
    function groupByNote(results) {
        const map = new Map();
        for (const r of results) {
            if (!map.has(r.note_id)) {
                map.set(r.note_id, {
                    noteId: r.note_id,
                    title: r.title || '',
                    path: r.path || '',
                    chunks: [],
                });
            }
            map.get(r.note_id).chunks.push(r);
        }
        return Array.from(map.values());
    }

    /**
     * Create a collapsible group header element (no arrow icon).
     */
    function createGroupHeader(title, chunkCount, isExpanded, onToggle) {
        const header = document.createElement('div');
        header.className = 'search-group-header';

        const titleEl = document.createElement('span');
        titleEl.className = 'search-group-title';
        titleEl.textContent = title;
        header.appendChild(titleEl);

        if (chunkCount > 1) {
            const countEl = document.createElement('span');
            countEl.className = 'search-group-chunk-count';
            countEl.textContent = `${chunkCount} chunks`;
            header.appendChild(countEl);
        }

        header.addEventListener('click', (e) => {
            e.stopPropagation();
            onToggle();
        });

        return header;
    }

    /**
     * Toggle a group body's visibility.
     */
    function toggleGroup(bodyEl) {
        const isVisible = bodyEl.style.display !== 'none';
        bodyEl.style.display = isVisible ? 'none' : 'block';
    }

    /**
     * Clamp text to a maximum number of characters, adding ellipsis.
     */
    function clampText(text, maxLen = 140) {
        if (!text || text.length <= maxLen) return text || '';
        return text.slice(0, maxLen) + '…';
    }

    /**
     * Simple HTML escaping to prevent XSS from search results.
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ─── Standard Search Results ──────────────────────────────────────

    /**
     * Display standard search results in the dropdown, grouped by note.
     */
    function displayResults(results, query) {
        resultsContainer.innerHTML = '';

        if (results.length === 0) {
            resultsContainer.innerHTML =
                `<div class="search-empty-state">No results found for "${escapeHtml(query)}"</div>`;
            resultsContainer.style.display = 'block';
            return;
        }

        const groups = groupByNote(results);

        groups.forEach((group, idx) => {
            const groupEl = document.createElement('div');
            groupEl.className = 'search-group';

            const isExpanded = idx === 0; // Top group expanded, rest collapsed

            // Header
            const headerEl = createGroupHeader(
                group.title,
                group.chunks.length,
                isExpanded,
                () => toggleGroup(bodyEl)
            );
            groupEl.appendChild(headerEl);

            // Body
            const bodyEl = document.createElement('div');
            bodyEl.className = 'search-group-body';
            bodyEl.style.display = isExpanded ? 'block' : 'none';

            group.chunks.forEach((chunk) => {
                const item = document.createElement('div');
                item.className = 'search-chunk-item';

                const topRow = document.createElement('div');
                topRow.className = 'search-chunk-top';

                const headingEl = document.createElement('span');
                headingEl.className = 'search-chunk-heading';
                headingEl.textContent = chunk.section_heading || chunk.heading_path?.slice(-1)[0] || 'Top section';
                topRow.appendChild(headingEl);

                if (chunk.score > 0) {
                    const scoreEl = document.createElement('span');
                    scoreEl.className = 'search-chunk-score';
                    scoreEl.textContent = chunk.score.toFixed(2);
                    topRow.appendChild(scoreEl);
                }

                item.appendChild(topRow);

                // Show snippet (clamped text) if available
                const textToShow = chunk.snippet || chunk.text || '';
                if (textToShow) {
                    const snippetEl = document.createElement('div');
                    snippetEl.className = 'search-chunk-text';
                    snippetEl.textContent = clampText(textToShow, 200);
                    item.appendChild(snippetEl);
                }

                // Click → navigate to chunk
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    resultsContainer.style.display = 'none';
                    if (onResultSelect) {
                        const chunkContext = chunk.chunk_id
                            ? { chunkId: chunk.chunk_id, headingPath: chunk.heading_path || [] }
                            : null;
                        onResultSelect(chunk.note_id, chunkContext);
                    }
                });

                bodyEl.appendChild(item);
            });

            groupEl.appendChild(bodyEl);
            resultsContainer.appendChild(groupEl);
        });

        resultsContainer.style.display = 'block';
    }

    // ─── Retrieve Results ─────────────────────────────────────────────

    /**
     * Display retrieve (agent context) results — grouped by note for
     * direct matches, then supporting knowledge (backlinks + graph neighbors).
     */
    function displayRetrieveResults(data, query) {
        resultsContainer.innerHTML = '';

        const direct = data.direct_matches || [];
        const supporting = data.supporting_knowledge || [];

        // Section: Header
        const header = document.createElement('div');
        header.className = 'retrieve-section';
        header.innerHTML = `
            <div class="retrieve-section-header">
                <span class="retrieve-section-icon">🧠</span>
                Agent Context for "${escapeHtml(query)}"
                <span class="retrieve-count">${data.total || 0} items</span>
            </div>
        `;
        resultsContainer.appendChild(header);

        // Section: Direct Matches (grouped by note)
        if (direct.length > 0) {
            const section = document.createElement('div');
            section.className = 'retrieve-section';

            const sectionHeader = document.createElement('div');
            sectionHeader.className = 'retrieve-section-header retrieve-subheader';
            sectionHeader.innerHTML = `
                <span>🎯 Direct Matches</span>
                <span class="retrieve-count">${direct.length}</span>
            `;
            section.appendChild(sectionHeader);

            const groups = groupByNote(direct);

            groups.forEach((group, idx) => {
                const groupEl = document.createElement('div');
                groupEl.className = 'retrieve-group';

                const isExpanded = idx === 0;

                // Group header (no arrow icon)
                const headerEl = document.createElement('div');
                headerEl.className = 'retrieve-group-header';

                const titleEl = document.createElement('span');
                titleEl.className = 'retrieve-group-title';
                titleEl.textContent = group.title;
                headerEl.appendChild(titleEl);

                if (group.chunks.length > 1) {
                    const countEl = document.createElement('span');
                    countEl.className = 'retrieve-group-chunk-count';
                    countEl.textContent = `${group.chunks.length} chunks`;
                    headerEl.appendChild(countEl);
                }

                headerEl.addEventListener('click', () => {
                    toggleGroup(bodyEl);
                });

                groupEl.appendChild(headerEl);

                // Group body
                const bodyEl = document.createElement('div');
                bodyEl.className = 'retrieve-group-body';
                bodyEl.style.display = isExpanded ? 'block' : 'none';

                group.chunks.forEach((r) => {
                    const card = document.createElement('div');
                    card.className = 'retrieve-direct-card';

                    // Top row: section heading + score badge
                    const topRow = document.createElement('div');
                    topRow.className = 'retrieve-card-top';

                    const cardTitle = document.createElement('span');
                    cardTitle.className = 'retrieve-card-title';
                    cardTitle.textContent = r.section_heading || r.heading_path?.slice(-1)[0] || 'Top section';
                    topRow.appendChild(cardTitle);

                    if (r.score > 0) {
                        const scoreBadge = document.createElement('span');
                        scoreBadge.className = 'retrieve-score-badge';
                        scoreBadge.textContent = r.score.toFixed(2);
                        topRow.appendChild(scoreBadge);
                    }

                    card.appendChild(topRow);

                    // Match type badge
                    if (r.match_type) {
                        const typeBadge = document.createElement('span');
                        typeBadge.className = `retrieve-match-badge badge-${r.match_type}`;
                        typeBadge.textContent = r.match_type.toUpperCase();
                        card.appendChild(typeBadge);
                    }

                    // Heading path breadcrumb
                    if (r.heading_path && r.heading_path.length > 0) {
                        const hp = document.createElement('div');
                        hp.className = 'retrieve-heading-path';
                        hp.innerHTML = '🏷 ' + r.heading_path.map(h => escapeHtml(h)).join(' › ');
                        card.appendChild(hp);
                    }

                    // Snippet (clamped text)
                    const textToShow = r.snippet || r.text || '';
                    if (textToShow) {
                        const snippet = document.createElement('div');
                        snippet.className = 'retrieve-snippet';
                        snippet.textContent = clampText(textToShow, 200);
                        card.appendChild(snippet);
                    }

                    // Expandable chunk text (when r.text is available)
                    if (r.text) {
                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'retrieve-text-toggle';
                        toggleBtn.textContent = '▾ Show full chunk';
                        toggleBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            const existing = card.querySelector('.retrieve-chunk-text');
                            if (existing) {
                                existing.remove();
                                toggleBtn.textContent = '▾ Show full chunk';
                            } else {
                                const chunkText = document.createElement('div');
                                chunkText.className = 'retrieve-chunk-text';
                                chunkText.textContent = r.text;
                                card.appendChild(chunkText);
                                toggleBtn.textContent = '▴ Hide full chunk';
                            }
                        });
                        card.appendChild(toggleBtn);
                    }

                    // Click to navigate
                    card.addEventListener('click', (e) => {
                        // Don't navigate if clicking the toggle button
                        if (e.target.closest('.retrieve-text-toggle')) return;
                        resultsContainer.style.display = 'none';
                        if (onResultSelect) {
                            const chunkContext = r.chunk_id
                                ? { chunkId: r.chunk_id, headingPath: r.heading_path || [] }
                                : null;
                            onResultSelect(r.note_id, chunkContext);
                        }
                    });

                    bodyEl.appendChild(card);
                });

                groupEl.appendChild(bodyEl);
                section.appendChild(groupEl);
            });

            resultsContainer.appendChild(section);
        }

        // Section: Supporting Knowledge
        if (supporting.length > 0) {
            const section = document.createElement('div');
            section.className = 'retrieve-section';

            const sectionHeader = document.createElement('div');
            sectionHeader.className = 'retrieve-section-header retrieve-subheader';
            sectionHeader.innerHTML = `
                <span>🔗 Supporting Knowledge</span>
                <span class="retrieve-count">${supporting.length}</span>
            `;
            section.appendChild(sectionHeader);

            // Sub-section: Backlinks
            const backlinks = supporting.filter(s => s.source === 'backlink');
            if (backlinks.length > 0) {
                const sub = document.createElement('div');
                sub.className = 'retrieve-supporting-subsection';
                sub.innerHTML = `<div class="retrieve-supporting-label">📎 Referenced By (Backlinks)</div>`;
                const pillContainer = document.createElement('div');
                pillContainer.className = 'retrieve-backlink-row';
                for (const bl of backlinks) {
                    const pill = document.createElement('div');
                    pill.className = 'retrieve-backlink-pill';
                    pill.innerHTML = `
                        <span class="retrieve-rel-badge">${escapeHtml(bl.relationship_type || 'LINK')}</span>
                        <span class="retrieve-pill-title">${escapeHtml(bl.title)}</span>
                    `;
                    pill.addEventListener('click', () => {
                        resultsContainer.style.display = 'none';
                        if (onResultSelect) onResultSelect(bl.note_id, null);
                    });
                    pillContainer.appendChild(pill);
                }
                sub.appendChild(pillContainer);
                section.appendChild(sub);
            }

            // Sub-section: Graph Neighbors
            const graphItems = supporting.filter(s => s.source === 'graph');
            if (graphItems.length > 0) {
                const sub = document.createElement('div');
                sub.className = 'retrieve-supporting-subsection';
                sub.innerHTML = `<div class="retrieve-supporting-label">🕸 Connected Knowledge (Graph)</div>`;
                const scrollRow = document.createElement('div');
                scrollRow.className = 'retrieve-graph-scroll';
                for (const g of graphItems) {
                    const card = document.createElement('div');
                    const hopClass = g.hop_depth === 1 ? 'hop-1' : 'hop-2';
                    card.className = `retrieve-graph-card ${hopClass}`;
                    card.innerHTML = `
                        <div class="retrieve-hop-badge">${g.hop_depth} hop${g.hop_depth > 1 ? 's' : ''} away</div>
                        <div class="retrieve-graph-card-title">${escapeHtml(g.title)}</div>
                    `;
                    card.addEventListener('click', () => {
                        resultsContainer.style.display = 'none';
                        if (onResultSelect) onResultSelect(g.note_id, null);
                    });
                    scrollRow.appendChild(card);
                }
                sub.appendChild(scrollRow);
                section.appendChild(sub);
            }

            resultsContainer.appendChild(section);
        }

        // Empty state
        if (direct.length === 0 && supporting.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'search-empty-state';
            empty.innerHTML = `No results found for "${escapeHtml(query)}"`;
            resultsContainer.appendChild(empty);
        }

        resultsContainer.style.display = 'block';
    }

    /**
     * Highlight matched note IDs from search results.
     */
    function highlightResults(results) {
        const ids = new Set(results.map((r) => r.note_id));
        GraphManager.highlightMatches(ids);
    }

    return { init, executeSearch, highlightResults, setQdrantStatus };
})();