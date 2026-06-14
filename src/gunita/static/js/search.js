/* ═══════════════════════════════════════════════════════════════════════
   search.js — Search bar and results
   ═══════════════════════════════════════════════════════════════════════ */

const SearchManager = (() => {
    let resultsContainer = null;
    let onResultSelect = null;
    let _qdrantAvailable = false;

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

        // Hide results on click outside
        document.addEventListener('click', (e) => {
            if (!resultsContainer.contains(e.target) && !e.target.closest('#search-form')) {
                resultsContainer.style.display = 'none';
            }
        });
    }

    /**
     * Update Qdrant availability status.
     * When Qdrant is down, semantic and hybrid modes are disabled.
     */
    function setQdrantStatus(connected) {
        _qdrantAvailable = connected;
        const semanticRadio = document.querySelector('input[name="mode"][value="semantic"]');
        const hybridRadio = document.querySelector('input[name="mode"][value="hybrid"]');
        const keywordRadio = document.querySelector('input[name="mode"][value="keyword"]');

        if (semanticRadio) {
            semanticRadio.disabled = !connected;
            semanticRadio.parentElement.style.opacity = connected ? '1' : '0.4';
            semanticRadio.parentElement.title = connected ? '' : 'Requires Qdrant';
        }
        if (hybridRadio) {
            hybridRadio.disabled = !connected;
            hybridRadio.parentElement.style.opacity = connected ? '1' : '0.4';
            hybridRadio.parentElement.title = connected ? '' : 'Requires Qdrant';
        }

        // If current selection is disabled, fall back to keyword
        if (!connected) {
            const currentMode = document.querySelector('input[name="mode"]:checked');
            if (currentMode && currentMode.value !== 'keyword') {
                if (keywordRadio) keywordRadio.checked = true;
            }
        }
    }

    /**
     * Execute a search query.
     */
    async function executeSearch() {
        const input = document.getElementById('search-input');
        const query = input.value.trim();
        if (!query) return;

        const checkedMode = document.querySelector('input[name="mode"]:checked');
        let mode = checkedMode?.value || 'keyword';

        // Enforce keyword mode if Qdrant is down
        if ((mode === 'semantic' || mode === 'hybrid') && !_qdrantAvailable) {
            mode = 'keyword';
            const keywordRadio = document.querySelector('input[name="mode"][value="keyword"]');
            if (keywordRadio) keywordRadio.checked = true;
        }

        const btn = document.getElementById('search-btn');
        const originalText = btn.textContent;
        btn.textContent = '⏳ Searching...';
        btn.disabled = true;

        try {
            const params = new URLSearchParams({ q: query, mode: mode, limit: '20' });
            const resp = await fetch(`/api/search/?${params}`);
            const data = await resp.json();

            displayResults(data.results || [], query);

            // Highlight all matched notes on the graph
            if (data.results && data.results.length > 0) {
                const ids = new Set(data.results.map((r) => r.note_id));
                GraphManager.highlightMatches(ids);
            }
        } catch (err) {
            console.error('Search failed:', err);
            resultsContainer.innerHTML =
                `<div class="search-result-item"><span class="search-result-title">Search failed — please try again</span></div>`;
            resultsContainer.style.display = 'block';
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Search failed', 'error');
            }
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    /**
     * Display search results in the dropdown.
     */
    function displayResults(results, query) {
        resultsContainer.innerHTML = '';

        if (results.length === 0) {
            resultsContainer.innerHTML =
                `<div class="search-result-item"><span class="search-result-title">No results found for "${escapeHtml(query)}"</span></div>`;
            resultsContainer.style.display = 'block';
            return;
        }

        for (const r of results) {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const headingHtml = r.section_heading
                ? `<div class="search-result-heading">${escapeHtml(r.section_heading)}</div>`
                : '';
            item.innerHTML = `
                <div class="search-result-title">${escapeHtml(r.title)}</div>
                ${headingHtml}
                <div class="search-result-path">${escapeHtml(r.path)}</div>
                ${r.snippet ? `<div class="search-result-snippet">${escapeHtml(r.snippet)}</div>` : ''}
            `;
            item.addEventListener('click', () => {
                resultsContainer.style.display = 'none';
                if (onResultSelect) onResultSelect(r.note_id);
            });
            resultsContainer.appendChild(item);
        }

        resultsContainer.style.display = 'block';
    }

    /**
     * Simple HTML escaping to prevent XSS from search results.
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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