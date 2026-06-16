/* ═══════════════════════════════════════════════════════════════════════
   app.js — Application bootstrap and cross-module wiring
   ═══════════════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    /**
     * Called when a graph node is clicked.
     * Loads the note into the preview panel.
     */
    function handleNodeClick(noteId, chunkContext) {
        if (chunkContext && chunkContext.chunkId) {
            PreviewManager.loadNote(noteId, { chunkId: chunkContext.chunkId });
        } else {
            PreviewManager.loadNote(noteId);
        }
        // After loading, attach wiki link handlers
        setTimeout(() => {
            PreviewManager.attachWikiLinkHandlers();
        }, 100);
    }

    /**
     * Called when a tree file is clicked.
     * Loads the file content into the preview panel.
     */
    function handleFileSelect(filePath) {
        PreviewManager.loadFile(filePath);
        // After loading, attach wiki link handlers
        setTimeout(() => {
            PreviewManager.attachWikiLinkHandlers();
        }, 100);
    }

    /**
     * Called when a search result is clicked.
     * Shows the note in preview and highlights it in the graph.
     */
    function handleSearchResultSelect(noteId, chunkContext) {
        if (chunkContext && chunkContext.chunkId) {
            PreviewManager.loadNote(noteId, { chunkId: chunkContext.chunkId });
            // Focus and mark the chunk on the graph node
            GraphManager.clearHighlights();
            GraphManager.highlightMatches(new Set([noteId]));
            if (typeof GraphManager.focusNodeChunk === 'function') {
                GraphManager.focusNodeChunk(noteId, chunkContext.chunkId);
            }
        } else {
            PreviewManager.loadNote(noteId);
            GraphManager.clearHighlights();
            GraphManager.highlightMatches(new Set([noteId]));
        }
        // Attach wiki link handlers after loading
        setTimeout(() => {
            PreviewManager.attachWikiLinkHandlers();
        }, 100);
    }

    /**
     * Initialize keyboard shortcuts.
     * Ctrl/Cmd+K → focus search input.
     * Ctrl/Cmd+N → new note.
     * Ctrl/Cmd+E → edit current note.
     * L (not in input) → toggle graph labels.
     * Escape → close modals/cancel edit.
     */
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+K or Cmd+K (Mac) — focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const input = document.getElementById('search-input');
                if (input) {
                    input.focus();
                    input.select();
                }
            }
            // Ctrl+N or Cmd+N — new note
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                if (typeof EditorManager !== 'undefined') {
                    EditorManager.showNewNoteModal();
                }
            }
            // Ctrl+E or Cmd+E — edit current note
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                const actions = document.getElementById('preview-actions');
                if (actions && actions.style.display !== 'none') {
                    const editBtn = document.getElementById('edit-note-btn');
                    if (editBtn) editBtn.click();
                }
            }
            // L key — toggle graph node labels (when not in an input/textarea)
            if (e.key === 'l' && !e.ctrlKey && !e.metaKey && !e.altKey) {
                const active = document.activeElement;
                const isInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable);
                if (!isInput) {
                    e.preventDefault();
                    const labelCheckbox = document.getElementById('label-checkbox');
                    if (labelCheckbox) {
                        labelCheckbox.checked = !labelCheckbox.checked;
                        labelCheckbox.dispatchEvent(new Event('change'));
                    }
                }
            }
        });
    }

    /**
     * Initialize resizable panels with drag handles.
     */
    function initResizablePanels() {
        const treePanel = document.getElementById('tree-panel');
        const graphPanel = document.getElementById('graph-panel');
        const previewPanel = document.getElementById('preview-panel');
        const resizerLeft = document.getElementById('resizer-left');
        const resizerRight = document.getElementById('resizer-right');

        if (resizerLeft && treePanel && graphPanel) {
            initDrag(resizerLeft, treePanel, 'left');
        }
        if (resizerRight && graphPanel && previewPanel) {
            initDrag(resizerRight, previewPanel, 'right');
        }
    }

    /**
     * Initialize a single drag-to-resize handler.
     * @param {HTMLElement} resizer - The resizer handle element.
     * @param {HTMLElement} panel - The panel to resize (left or right).
     * @param {'left'|'right'} side - Which side the panel is on.
     */
    function initDrag(resizer, panel, side) {
        let startX = 0;
        let startWidth = 0;

        function onMouseDown(e) {
            e.preventDefault();
            startX = e.clientX;
            startWidth = panel.getBoundingClientRect().width;
            resizer.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        }

        function onMouseMove(e) {
            const dx = e.clientX - startX;
            let newWidth;
            if (side === 'left') {
                newWidth = startWidth + dx;
            } else {
                newWidth = startWidth - dx;
            }

            // Enforce min/max constraints
            const minW = parseInt(getComputedStyle(panel).minWidth) || 160;
            const maxW = parseInt(getComputedStyle(panel).maxWidth) || 600;
            newWidth = Math.max(minW, Math.min(maxW, newWidth));

            panel.style.width = newWidth + 'px';

            // Trigger vis-network resize after a brief delay
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 50);
        }

        function onMouseUp() {
            resizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        resizer.addEventListener('mousedown', onMouseDown);
    }

    /**
     * Initialize browser history integration (back/forward).
     * Handles popstate events to navigate between notes.
     */
    function initBrowserHistory() {
        window.addEventListener('popstate', (e) => {
            const hash = window.location.hash;
            if (hash && hash.startsWith('#/note/')) {
                const noteId = hash.replace('#/note/', '');
                if (noteId) {
                    PreviewManager.loadNote(noteId);
                    // Highlight in graph
                    GraphManager.clearHighlights();
                    GraphManager.highlightMatches(new Set([noteId]));
                    setTimeout(() => {
                        PreviewManager.attachWikiLinkHandlers();
                    }, 100);
                }
            } else {
                PreviewManager.showEmpty();
                GraphManager.clearHighlights();
            }
        });

        // Check if there's a hash on initial load
        const initialHash = window.location.hash;
        if (initialHash && initialHash.startsWith('#/note/')) {
            const noteId = initialHash.replace('#/note/', '');
            if (noteId) {
                // Defer note loading until after graph is loaded
                setTimeout(() => {
                    PreviewManager.loadNote(noteId);
                    GraphManager.clearHighlights();
                    GraphManager.highlightMatches(new Set([noteId]));
                    setTimeout(() => {
                        PreviewManager.attachWikiLinkHandlers();
                    }, 200);
                }, 500);
            }
        }
    }

    /**
     * Show the preview actions bar (edit, version history buttons).
     */
    function showPreviewActions() {
        const actions = document.getElementById('preview-actions');
        if (actions) actions.style.display = 'flex';
    }

    /**
     * Hide the preview actions bar.
     */
    function hidePreviewActions() {
        const actions = document.getElementById('preview-actions');
        if (actions) actions.style.display = 'none';
    }

    /**
     * Bootstrap all modules.
     */
    function init() {
        // Initialize toast notification system first
        ToastManager.init();

        // Initialize theme
        ThemeManager.init();

        // Wire up modules with callbacks
        const graphContainer = document.getElementById('graph-container');
        GraphManager.init(graphContainer, handleNodeClick);

        const treeContainer = document.getElementById('tree-container');
        TreeManager.init(treeContainer, handleFileSelect);

        // Create the search results dropdown container
        const resultsDiv = document.createElement('div');
        resultsDiv.id = 'search-results';
        document.body.appendChild(resultsDiv);
        SearchManager.init(resultsDiv, handleSearchResultSelect);

        PreviewManager.init();
        StatsManager.init();

        // Initialize editor module and quick-add bindings
        EditorManager.init();
        EditorManager.bindQuickAddHandlers();

        // Initialize WebSocket for live updates
        WsManager.init({
            onGraphUpdate: (msg) => {
                // When graph is updated (via WebSocket), reload graph data
                if (msg.action === 'create' || msg.action === 'update' || msg.action === 'delete') {
                    GraphManager.loadGraph();
                    TreeManager.loadTree();
                    StatsManager.refreshStats();
                    if (typeof ToastManager !== 'undefined') {
                        ToastManager.show(`Graph updated (${msg.action})`, 'info');
                    }
                }
            },
            onSearchUpdate: (msg) => {
                // Handle live search results
                if (msg.results && typeof SearchManager !== 'undefined') {
                    // Search results received via WebSocket
                }
            },
        });

        // Load initial data
        GraphManager.loadGraph();
        TreeManager.loadTree();
        StatsManager.refreshStats();

        // Initialize Phase 3 features
        initKeyboardShortcuts();
        initResizablePanels();
        initBrowserHistory();

        // Show a welcome toast
        setTimeout(() => {
            ToastManager.show('Gunita v0.2.0 loaded — explore your vault', 'info', 3000);
        }, 1500);
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();