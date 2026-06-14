/* ═══════════════════════════════════════════════════════════════════════
   stats.js — Status bar and reindex trigger
   ═══════════════════════════════════════════════════════════════════════ */

const StatsManager = (() => {
    let _autoRefreshInterval = null;

    /**
     * Fetch and display vault statistics.
     * Also wires Qdrant status to search module.
     */
    async function refreshStats() {
        try {
            const resp = await fetch('/api/stats/');
            const stats = await resp.json();

            document.getElementById('stat-notes').textContent = `Notes: ${stats.notes_count}`;
            document.getElementById('stat-rels').textContent = `Rels: ${stats.relationships_count}`;
            document.getElementById('stat-tags').textContent = `Tags: ${stats.tags_count}`;
            document.getElementById('stat-files').textContent = `Files: ${stats.files_on_disk}`;

            const unindexed = stats.unindexed_count || 0;
            const filesEl = document.getElementById('stat-files');
            if (unindexed > 0) {
                filesEl.textContent += ` (${unindexed} unindexed)`;
                filesEl.style.color = '#FF9800';
            } else {
                filesEl.style.color = '';
            }

            document.getElementById('stat-qdrant').textContent =
                stats.qdrant_connected ? 'Qdrant: 🟢' : 'Qdrant: ⚫';

            const vectorEl = document.getElementById('stat-vectors');
            if (vectorEl) {
                vectorEl.textContent = `Vectors: ${stats.vector_count || 0}`;
            }

            if (stats.last_reindex) {
                document.getElementById('stat-last-reindex').textContent = `Last: ${stats.last_reindex}`;
            }

            // Wire Qdrant status to search module
            if (typeof SearchManager !== 'undefined' && SearchManager.setQdrantStatus) {
                SearchManager.setQdrantStatus(stats.qdrant_connected);
            }

        } catch (err) {
            console.error('Failed to load stats:', err);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load vault stats', 'error');
            }
        }
    }

    /**
     * Trigger a vault reindex.
     */
    async function triggerReindex() {
        const btn = document.getElementById('reindex-btn');
        btn.classList.add('reindexing');
        btn.textContent = '⏳ Reindexing...';
        btn.disabled = true;

        try {
            const embedCheckbox = document.getElementById('reindex-embed');
            const embed = embedCheckbox ? embedCheckbox.checked : false;
            const params = new URLSearchParams();
            if (embed) params.set('embed', 'true');

            const resp = await fetch(`/api/stats/reindex?${params}`, { method: 'POST' });
            if (!resp.ok) {
                throw new Error(`Reindex failed with status ${resp.status}`);
            }
            const result = await resp.json();

            // Reload everything after reindex
            await refreshStats();
            await GraphManager.loadGraph();
            await TreeManager.loadTree();

            if (typeof ToastManager !== 'undefined') {
                let msg = result.added > 0
                    ? `Reindex complete: ${result.added} notes indexed`
                    : 'Reindex complete: no changes';
                if (result.embedded) {
                    msg += ' (with embeddings)';
                }
                ToastManager.show(msg, 'success');
            }
        } catch (err) {
            console.error('Reindex failed:', err);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Reindex failed', 'error');
            }
        } finally {
            btn.classList.remove('reindexing');
            btn.textContent = '🔄 Reindex';
            btn.disabled = false;
        }
    }

    /**
     * Start auto-refreshing stats every 60 seconds.
     */
    function startAutoRefresh() {
        if (_autoRefreshInterval) clearInterval(_autoRefreshInterval);
        _autoRefreshInterval = setInterval(() => {
            if (!document.hidden) {
                refreshStats();
            }
        }, 60000); // 60 seconds
    }

    /**
     * Stop auto-refresh.
     */
    function stopAutoRefresh() {
        if (_autoRefreshInterval) {
            clearInterval(_autoRefreshInterval);
            _autoRefreshInterval = null;
        }
    }

    /**
     * Initialize the reindex button handler and auto-refresh.
     */
    function init() {
        const btn = document.getElementById('reindex-btn');
        btn.addEventListener('click', triggerReindex);

        // Start auto-refresh
        startAutoRefresh();
    }

    return { init, refreshStats, triggerReindex, startAutoRefresh, stopAutoRefresh };
})();