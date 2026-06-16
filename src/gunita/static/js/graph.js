/* ═══════════════════════════════════════════════════════════════════════
   graph.js — 2D Knowledge graph visualization using force-graph
   ═══════════════════════════════════════════════════════════════════════ */
console.log("GRAPH JS LOADED", new Date());

const GraphManager = (() => {
    let graph = null;
    let onNodeClick = null;
    let _isLoading = false;
    let _hoveredNode = null;

    // Full data cache for filtering
    let _allNodes = [];
    let _allEdges = [];

    // Filter state
    let _disabledRelTypes = new Set();
    let _selectedTag = '';

    // Label visibility toggle
    let _showLabels = true;

    // Node ID set for quick lookup
    let _nodeIdSet = new Set();

    /**
     * Relationship type → color mapping (muted, neutral palette)
     */
    const REL_COLORS = {
        EXPLICIT_LINK:   '#6B8DAD',
        INFERRED_LINK:   '#6B7280',
        USES:            '#8B7BAD',
        DEPENDS_ON:      '#AD6B6B',
        REQUIRES:        '#AD6B6B',
        PROVIDES:        '#6B8DAD',
        IMPLEMENTS:      '#6B8DAD',
        PART_OF:         '#6BAD8D',
        CONTAINS:        '#AD8D6B',
        PARENT_OF:       '#8DAD7B',
        CHILD_OF:        '#8DAD7B',
        RELATED_TO:      '#6BADAD',
        REFERENCES:      '#ADAD7B',
        SIMILAR_TO:      '#6BADAD',
        MENTIONS:        '#ADAD7B',
        DESCRIBES:       '#8DAD7B',
        CAUSES:          '#AD6B6B',
        INFLUENCES:      '#AD8D6B',
        RESULTS_IN:      '#C86464',
        PRECEDES:        '#6B7280',
        FOLLOWS:         '#6B7280',
        REPLACED_BY:     '#9A5B6B',
        DERIVED_FROM:    '#A07B5B',
        CREATED_BY:      '#A0A8B3',
        OWNED_BY:        '#A0A8B3',
        ASSIGNED_TO:     '#A0A8B3',
        MEMORY_OF:       '#8B7BAD',
        OBSERVED_FROM:   '#8B7BAD',
        SUPPORTS:        '#6BAD9A',
        CONTRADICTS:     '#C86464',
        CONFIRMS:        '#6BAD9A',
        QUESTIONED_BY:   '#ADAD7B',
    };

    /**
     * Deterministic color from tag string (muted palette)
     */
    const TAG_COLORS = [
        '#5B7B9A', '#5B9A7B', '#A07B5B', '#8B7BAD', '#9A5B6B',
        '#6BADAD', '#8DAD7B', '#6B8DAD', '#ADAD7B', '#AD8D6B',
    ];

    function tagColor(tag) {
        if (!tag) return '#5B7B9A';
        let hash = 0;
        for (let i = 0; i < tag.length; i++) {
            hash = ((hash << 5) - hash) + tag.charCodeAt(i);
            hash |= 0;
        }
        return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
    }

    function relColor(type) {
        return REL_COLORS[type.toUpperCase()] || '#6B7280';
    }

    /**
     * Initialize the 2D graph in the given container element.
     */
    function init(container, clickCallback) {
        onNodeClick = clickCallback;

        // Create 2D force graph instance
        graph = ForceGraph()(container)
            // ── Node styling ──
            .nodeVal(node => {
                const label = node.title || node.id || '';
                return Math.max(8, label.length * 0.35);
            })
            .nodeColor(node => {
                // All nodes in gray
                if (node === _hoveredNode) return '#9CA3AF';
                return '#6B7280';
            })
            .nodeCanvasObject((node, ctx, globalScale) => {
                const label = node.title || node.id || '';
                const r = Math.max(8, label.length * 0.35);
                // Draw circle
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
                ctx.fillStyle = node.color || '#6B7280';
                ctx.fill();

                // Show chunk count badge if the node has multiple chunks
                if (node.chunk_count > 1) {
                    const badgeR = 5;
                    const badgeX = node.x + r * 0.7;
                    const badgeY = node.y - r * 0.7;
                    ctx.beginPath();
                    ctx.arc(badgeX, badgeY, badgeR, 0, 2 * Math.PI, false);
                    ctx.fillStyle = '#5B7B9A';
                    ctx.fill();
                    ctx.font = '7px Sans-Serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = '#E6E8EB';
                    ctx.fillText(String(node.chunk_count), badgeX, badgeY);
                }

                // Hide labels when zoomed out OR labels toggled off
                if (globalScale < 1.0 || !_showLabels) return;

                // Draw label text
                const fontSize = 8;
                ctx.font = `${fontSize}px Sans-Serif`;
                const textWidth = ctx.measureText(label).width;
                const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);

                ctx.fillStyle = 'rgba(22, 26, 32, 0.9)';
                ctx.fillRect(
                    node.x - bckgDimensions[0] / 2,
                    node.y - 2 * r - bckgDimensions[1],
                    bckgDimensions[0],
                    bckgDimensions[1]
                );

                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#E6E8EB';
                ctx.fillText(label, node.x, node.y - 2 * r - bckgDimensions[1] / 2);
            })
            .nodePointerAreaPaint((node, color, ctx) => {
                const label = node.title || node.id || '';
                const r = Math.max(8, label.length * 0.35);
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
                ctx.fillStyle = color;
                ctx.fill();
            })

            // ── Link styling ──
            .linkColor(link => relColor(link.rel_type))
            .linkWidth(0.5)
            .linkDirectionalArrowLength(3)
            .linkDirectionalArrowRelPos(1)
            .linkCurvature(0.1)

            // ── Forces ──
            .d3AlphaDecay(0.02)
            .d3VelocityDecay(0.3)

            // ── Interactions ──
            .onNodeClick(node => {
                if (onNodeClick) {
                    onNodeClick(node.note_id || node.id);
                }
                // Focus view on node
                graph.centerAt(node.x, node.y, 1000);
                graph.zoom(2.5, 1000);
            })
            .onNodeHover(node => {
                _hoveredNode = node;
                // Update hovered node color
                if (graph) graph.nodeColor(graph.nodeColor());
                // Update container cursor
                container.style.cursor = node ? 'pointer' : 'default';
            })
            .onBackgroundClick(() => {
                // Reset view to show all nodes
                graph.centerAt(0, 0, 1000);
                graph.zoom(1, 1000);
            });

        // Enable node drag
        graph.d3Force('charge').strength(-180);
        graph.d3Force('link').distance(180);

        // Initialize legend toggle
        initLegendToggle();
        // Initialize graph filters
        initFilters();
    }

    /**
     * Show a loading state in the graph container.
     */
    function setLoading(container, loading) {
        _isLoading = loading;
        if (!container) return;
        const overlay = container.querySelector('.graph-loading');
        if (loading) {
            if (!overlay) {
                const div = document.createElement('div');
                div.className = 'graph-loading';
                div.innerHTML = '<div class="spinner"></div><span>Loading graph...</span>';
                container.appendChild(div);
            }
        } else {
            if (overlay) overlay.remove();
        }
    }

    /**
     * Load graph data from the API.
     */
    async function loadGraph() {
        const containerEl = document.getElementById('graph-container');
        try {
            setLoading(containerEl, true);
            const resp = await fetch('/api/graph/');
            const data = await resp.json();

            _allNodes = (data.nodes || []).map(n => ({
                id: n.note_id,
                note_id: n.note_id,
                title: n.title,
                tags: n.tags || [],
                degree: n.degree || 0,
                chunk_count: n.chunk_count || 0,
                _isMatch: false,
            }));

            _allEdges = (data.edges || []).map(e => ({
                source: e.source_id,
                target: e.target_id,
                rel_type: e.rel_type,
            }));

            _nodeIdSet = new Set(_allNodes.map(n => n.id));

            // Filter out edges referencing non-existent nodes
            _allEdges = _allEdges.filter(e =>
                _nodeIdSet.has(typeof e.source === 'object' ? e.source.id : e.source) &&
                _nodeIdSet.has(typeof e.target === 'object' ? e.target.id : e.target)
            );

            // Show/hide empty state
            const emptyEl = document.getElementById('graph-empty');
            if (emptyEl) {
                emptyEl.style.display = _allNodes.length === 0 ? 'block' : 'none';
            }

            // Populate tag filter dropdown
            populateTagFilter(_allNodes);
            // Populate relationship type filter checkboxes
            populateRelFilter(_allEdges);

            applyFilters();

        } catch (err) {
            console.error('Failed to load graph:', err);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load graph', 'error');
            }
        } finally {
            setLoading(containerEl, false);
        }
    }

    /**
     * Apply current filters to the graph.
     */
    function applyFilters() {
        // Filter edges by disabled relationship types
        const filteredEdges = _allEdges.filter(e => {
            const rel = (typeof e.rel_type === 'string') ? e.rel_type.toUpperCase() : '';
            return !_disabledRelTypes.has(rel);
        });

        // Collect node IDs that are connected by visible edges
        const visibleNodeIds = new Set();
        filteredEdges.forEach(e => {
            const sid = typeof e.source === 'object' ? e.source.id : e.source;
            const tid = typeof e.target === 'object' ? e.target.id : e.target;
            visibleNodeIds.add(sid);
            visibleNodeIds.add(tid);
        });

        // Filter nodes by selected tag
        let filteredNodes = _allNodes;
        if (_selectedTag) {
            filteredNodes = _allNodes.filter(n => (n.tags || []).includes(_selectedTag));
        }

        // Only show nodes that are either tag-filtered or connected by visible edges.
        // When no edges exist at all (disconnected graph), show all nodes as isolated dots.
        const finalNodes = filteredNodes.filter(n =>
            visibleNodeIds.size === 0 || visibleNodeIds.has(n.id) || _selectedTag
        );

        const finalNodeIds = new Set(finalNodes.map(n => n.id));

        // Filter edges to only include those between final nodes
        const finalEdges = filteredEdges.filter(e => {
            const sid = typeof e.source === 'object' ? e.source.id : e.source;
            const tid = typeof e.target === 'object' ? e.target.id : e.target;
            return finalNodeIds.has(sid) && finalNodeIds.has(tid);
        });

        if (graph) {
            graph.graphData({ nodes: finalNodes, links: finalEdges });
        }

        // Show/hide empty state based on filtered results
        const emptyEl = document.getElementById('graph-empty');
        if (emptyEl) {
            emptyEl.style.display = finalNodes.length === 0 ? 'block' : 'none';
        }
    }

    /**
     * Highlight a set of note IDs (search matches).
     */
    function highlightMatches(noteIds) {
        // Reset all matches
        _allNodes.forEach(n => { n._isMatch = false; });
        // Set matches
        _allNodes.forEach(n => {
            if (noteIds.has(n.id) || noteIds.has(n.note_id)) {
                n._isMatch = true;
            }
        });

        // Update graph colors
        if (graph) graph.nodeColor(graph.nodeColor());

        // Focus view on first match
        if (noteIds.size > 0) {
            const firstId = [...noteIds][0];
            const node = _allNodes.find(n => n.id === firstId || n.note_id === firstId);
            if (node && node.x !== undefined) {
                graph.centerAt(node.x, node.y, 1500);
                graph.zoom(2.5, 1500);
            }
        }
    }

    /**
     * Clear all highlights and reset visuals.
     */
    function clearHighlights() {
        _allNodes.forEach(n => { n._isMatch = false; });
        if (graph) graph.nodeColor(graph.nodeColor());
    }

    /**
     * Focus view on a specific node (used by search).
     */
    function focusNode(nodeId) {
        const node = _allNodes.find(n => n.id === nodeId || n.note_id === nodeId);
        if (node && node.x !== undefined) {
            graph.centerAt(node.x, node.y, 1000);
            graph.zoom(2.5, 1000);
        }
    }

    /**
     * Focus on a specific node and mark it with a chunk to highlight.
     */
    function focusNodeChunk(nodeId, chunkId) {
        const node = _allNodes.find(n => n.id === nodeId || n.note_id === nodeId);
        if (node && node.x !== undefined) {
            graph.centerAt(node.x, node.y, 1000);
            graph.zoom(2.5, 1000);
        }
    }

    /**
     * Toggle label visibility on/off.
     * The _showLabels variable is read directly by the render function
     * on each animation frame, so no explicit re-render is needed.
     */
    function toggleLabels(show) {
        _showLabels = show;
    }

    /**
     * Get current label visibility state.
     */
    function areLabelsVisible() {
        return _showLabels;
    }

    /**
     * Initialize legend collapse/expand toggle.
     */
    function initLegendToggle() {
        const toggle = document.getElementById('legend-toggle');
        if (!toggle) return;
        toggle.addEventListener('click', () => {
            const items = document.querySelector('.legend-items');
            const icon = document.querySelector('.legend-collapse-icon');
            if (items) items.classList.toggle('collapsed');
            if (icon) icon.classList.toggle('collapsed');
        });
    }

    /**
     * Initialize graph filter controls.
     */
    function initFilters() {
        // Edge filter toggle
        const relToggle = document.getElementById('rel-filter-toggle');
        const relList = document.getElementById('rel-filter-list');
        if (relToggle && relList) {
            relToggle.addEventListener('click', () => {
                const arrow = relToggle.querySelector('.filter-toggle-arrow');
                const visible = relList.style.display !== 'none';
                relList.style.display = visible ? 'none' : 'block';
                if (arrow) arrow.classList.toggle('open', !visible);
            });
        }

        // Tag filter toggle
        const tagToggle = document.getElementById('tag-filter-toggle');
        const tagList = document.getElementById('tag-filter-list');
        if (tagToggle && tagList) {
            tagToggle.addEventListener('click', () => {
                const arrow = tagToggle.querySelector('.filter-toggle-arrow');
                const visible = tagList.style.display !== 'none';
                tagList.style.display = visible ? 'none' : 'block';
                if (arrow) arrow.classList.toggle('open', !visible);
            });
        }

        // Tag filter select change
        const tagSelect = document.getElementById('tag-filter-select');
        if (tagSelect) {
            tagSelect.addEventListener('change', (e) => {
                _selectedTag = e.target.value;
                applyFilters();
            });
        }

        // Cluster by tag toggle
        const clusterCheckbox = document.getElementById('cluster-checkbox');
        if (clusterCheckbox) {
            clusterCheckbox.addEventListener('change', () => {
                applyFilters();
            });
        }

        // Node label toggle
        const labelCheckbox = document.getElementById('label-checkbox');
        if (labelCheckbox) {
            labelCheckbox.addEventListener('change', (e) => {
                _showLabels = e.target.checked;
                toggleLabels(_showLabels);
            });
        }

        // Graph export buttons
        initExportButtons();
    }

    /**
     * Populate relationship type filter checkboxes.
     */
    function populateRelFilter(edges) {
        const relList = document.getElementById('rel-filter-list');
        if (!relList) return;
        relList.innerHTML = '';

        const relTypes = new Set();
        edges.forEach(e => relTypes.add(e.rel_type.toUpperCase()));

        const sorted = [...relTypes].sort();
        for (const rel of sorted) {
            const label = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = true;
            cb.value = rel;
            cb.style.accentColor = relColor(rel);
            cb.addEventListener('change', (e) => {
                if (e.target.checked) {
                    _disabledRelTypes.delete(rel);
                } else {
                    _disabledRelTypes.add(rel);
                }
                applyFilters();
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(` ${rel}`));
            relList.appendChild(label);
        }
    }

    /**
     * Populate tag filter dropdown from nodes.
     */
    function populateTagFilter(nodes) {
        const select = document.getElementById('tag-filter-select');
        if (!select) return;

        const tags = new Set();
        nodes.forEach(n => (n.tags || []).forEach(t => tags.add(t)));

        // Clear existing options except first
        while (select.options.length > 1) {
            select.remove(1);
        }

        const sorted = [...tags].sort();
        for (const tag of sorted) {
            const opt = document.createElement('option');
            opt.value = tag;
            opt.textContent = tag;
            select.appendChild(opt);
        }
    }

    // ─── Graph Export ──────────────────────────────────────────────

    function initExportButtons() {
        const pngBtn = document.getElementById('export-png');
        const svgBtn = document.getElementById('export-svg');
        if (pngBtn) {
            pngBtn.addEventListener('click', exportPNG);
        }
        if (svgBtn) {
            svgBtn.addEventListener('click', exportSVG);
        }
    }

    function exportPNG() {
        if (!graph) return;
        try {
            const canvas = graph.renderer();
            if (!canvas) return;

            const link = document.createElement('a');
            link.download = 'gunita-graph.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Graph exported as PNG', 'success');
            }
        } catch (e) {
            console.error('PNG export failed:', e);
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to export graph as PNG', 'error');
            }
        }
    }

    function exportSVG() {
        // 2D canvas doesn't natively support SVG export without a library;
        // capture as PNG instead
        exportPNG();
    }

    /**
     * Get the underlying force-graph instance (for external use).
     */
    function getNetwork() {
        return graph;
    }

    return {
        init, loadGraph, highlightMatches, clearHighlights, focusNode,
        focusNodeChunk, toggleLabels, areLabelsVisible,
        getNetwork, isLoading: () => _isLoading,
    };
})();