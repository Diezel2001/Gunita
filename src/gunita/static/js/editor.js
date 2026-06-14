/* ═══════════════════════════════════════════════════════════════════════
   editor.js — Note editor (create + edit) with versioning support
   ═══════════════════════════════════════════════════════════════════════ */

const EditorManager = (() => {
    let _currentNoteId = null;
    let _isEditing = false;
    let _onSaved = null;

    /**
     * Initialize editor UI elements and event handlers.
     */
    function init(saveCallback) {
        _onSaved = saveCallback || null;

        // New note button
        const newBtn = document.getElementById('new-note-btn');
        if (newBtn) {
            newBtn.addEventListener('click', showNewNoteModal);
        }

        // New note modal actions
        const createBtn = document.getElementById('new-note-create');
        if (createBtn) {
            createBtn.addEventListener('click', handleCreateNote);
        }
        const cancelBtn = document.getElementById('new-note-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', hideNewNoteModal);
        }

        // Editor save/cancel
        const saveBtn = document.getElementById('editor-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', handleSave);
        }
        const cancelEditBtn = document.getElementById('editor-cancel');
        if (cancelEditBtn) {
            cancelEditBtn.addEventListener('click', cancelEdit);
        }

        // Edit button in preview header
        const editBtn = document.getElementById('edit-note-btn');
        if (editBtn) {
            editBtn.addEventListener('click', () => {
                if (_currentNoteId) {
                    startEditing(_currentNoteId);
                }
            });
        }

        // Version history button
        const versionBtn = document.getElementById('version-history-btn');
        if (versionBtn) {
            versionBtn.addEventListener('click', () => {
                if (_currentNoteId) {
                    loadVersionHistory(_currentNoteId);
                }
            });
        }

        // Close modal on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideNewNoteModal();
                cancelEdit();
            }
        });
    }

    // ─── New Note Modal ─────────────────────────────────────────────

    function showNewNoteModal() {
        const modal = document.getElementById('new-note-modal');
        if (modal) {
            modal.style.display = 'flex';
            document.getElementById('new-note-title').value = '';
            document.getElementById('new-note-content').value = '';
            document.getElementById('new-note-tags').value = '';
            document.getElementById('new-note-title').focus();
        }
    }

    function hideNewNoteModal() {
        const modal = document.getElementById('new-note-modal');
        if (modal) modal.style.display = 'none';
    }

    async function handleCreateNote() {
        const title = document.getElementById('new-note-title').value.trim();
        const content = document.getElementById('new-note-content').value;
        const tagsStr = document.getElementById('new-note-tags').value.trim();

        if (!title) {
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Please enter a title', 'warning');
            }
            return;
        }

        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

        try {
            const resp = await fetch('/api/notes/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content, tags }),
            });

            if (resp.ok) {
                const result = await resp.json();
                if (typeof ToastManager !== 'undefined') {
                    ToastManager.show(`Note created: ${result.title}`, 'success');
                }
                hideNewNoteModal();
                // Reload graph and tree
                if (typeof GraphManager !== 'undefined') GraphManager.loadGraph();
                if (typeof TreeManager !== 'undefined') TreeManager.loadTree();
                if (typeof StatsManager !== 'undefined') StatsManager.refreshStats();
                // Optionally load the new note
                if (result.note_id && typeof PreviewManager !== 'undefined') {
                    PreviewManager.loadNote(result.note_id);
                    setTimeout(() => PreviewManager.attachWikiLinkHandlers(), 100);
                }
                // Broadcast via WebSocket
                if (typeof WsManager !== 'undefined' && WsManager.isConnected()) {
                    WsManager.send({ type: 'graph_updated', action: 'create', note_id: result.note_id });
                }
            } else {
                const err = await resp.json();
                if (typeof ToastManager !== 'undefined') {
                    ToastManager.show(err.detail || 'Failed to create note', 'error');
                }
            }
        } catch (e) {
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to create note', 'error');
            }
        }
    }

    // ─── Note Editing ───────────────────────────────────────────────

    async function startEditing(noteId) {
        _currentNoteId = noteId;

        try {
            const resp = await fetch(`/api/notes/${noteId}`);
            if (!resp.ok) return;
            const note = await resp.json();

            // Switch to editor view
            _showEditor();

            // Populate editor fields
            document.getElementById('editor-title').value = note.title || '';
            document.getElementById('editor-tags').value = (note.tags || []).join(', ');
            document.getElementById('editor-content').value = note.content || '';

            _isEditing = true;
        } catch (e) {
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load note for editing', 'error');
            }
        }
    }

    function _showEditor() {
        document.getElementById('preview-empty').style.display = 'none';
        document.getElementById('preview-note').style.display = 'none';
        document.getElementById('preview-versions').style.display = 'none';
        document.getElementById('preview-timeline').style.display = 'none';
        document.getElementById('preview-editor').style.display = 'block';
    }

    function cancelEdit() {
        _isEditing = false;
        document.getElementById('preview-editor').style.display = 'none';
        if (_currentNoteId) {
            // Switch back to preview
            document.getElementById('preview-note').style.display = 'block';
            document.getElementById('preview-empty').style.display = 'none';
        } else {
            document.getElementById('preview-empty').style.display = '';
        }
    }

    async function handleSave() {
        const title = document.getElementById('editor-title').value.trim();
        const content = document.getElementById('editor-content').value;
        const tagsStr = document.getElementById('editor-tags').value.trim();
        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

        if (!_currentNoteId) {
            // Create new note
            try {
                const resp = await fetch('/api/notes/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: title || 'Untitled', content, tags }),
                });
                if (resp.ok) {
                    const result = await resp.json();
                    if (typeof ToastManager !== 'undefined') {
                        ToastManager.show(`Note created: ${result.title}`, 'success');
                    }
                    _currentNoteId = result.note_id;
                } else {
                    const err = await resp.json();
                    if (typeof ToastManager !== 'undefined') {
                        ToastManager.show(err.detail || 'Failed to create note', 'error');
                    }
                    return;
                }
            } catch (e) {
                if (typeof ToastManager !== 'undefined') {
                    ToastManager.show('Failed to create note', 'error');
                }
                return;
            }
        } else {
            // Update existing note
            try {
                const resp = await fetch(`/api/notes/${_currentNoteId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: title || undefined, content, tags }),
                });
                if (resp.ok) {
                    if (typeof ToastManager !== 'undefined') {
                        ToastManager.show('Note saved', 'success');
                    }
                } else {
                    const err = await resp.json();
                    if (typeof ToastManager !== 'undefined') {
                        ToastManager.show(err.detail || 'Failed to save note', 'error');
                    }
                    return;
                }
            } catch (e) {
                if (typeof ToastManager !== 'undefined') {
                    ToastManager.show('Failed to save note', 'error');
                }
                return;
            }
        }

        _isEditing = false;
        document.getElementById('preview-editor').style.display = 'none';

        // Reload everything
        if (typeof GraphManager !== 'undefined') GraphManager.loadGraph();
        if (typeof TreeManager !== 'undefined') TreeManager.loadTree();
        if (typeof StatsManager !== 'undefined') StatsManager.refreshStats();

        // Load the saved note in preview
        if (_currentNoteId && typeof PreviewManager !== 'undefined') {
            PreviewManager.loadNote(_currentNoteId);
            setTimeout(() => PreviewManager.attachWikiLinkHandlers(), 100);
        }

        // Broadcast via WebSocket
        if (typeof WsManager !== 'undefined' && WsManager.isConnected()) {
            WsManager.send({ type: 'graph_updated', action: 'update', note_id: _currentNoteId });
        }

        if (_onSaved) _onSaved();
    }

    // ─── Version History ────────────────────────────────────────────

    async function loadVersionHistory(noteId) {
        const previewNote = document.getElementById('preview-note');
        const previewEmpty = document.getElementById('preview-empty');
        const editor = document.getElementById('preview-editor');
        const versions = document.getElementById('preview-versions');
        const timeline = document.getElementById('preview-timeline');

        // Hide other views
        previewNote.style.display = 'none';
        previewEmpty.style.display = 'none';
        editor.style.display = 'none';
        timeline.style.display = 'none';
        versions.style.display = 'block';

        const versionsList = document.getElementById('versions-list');
        const diffView = document.getElementById('diff-view');
        const diffContent = document.getElementById('diff-content');
        const diffTitle = document.getElementById('diff-title');

        try {
            const resp = await fetch(`/api/notes/${noteId}/versions`);
            if (!resp.ok) {
                versionsList.innerHTML = '<p class="empty-title">No versions found</p>';
                return;
            }
            const data = await resp.json();
            const vers = data.versions || [];

            if (vers.length === 0) {
                versionsList.innerHTML = '<p class="empty-title">No version history available</p>';
                return;
            }

            versionsList.innerHTML = '';
            vers.forEach((v) => {
                const item = document.createElement('div');
                item.className = 'version-item';
                item.innerHTML = `
                    <span class="version-number">v${v.version}</span>
                    <span class="version-date">${new Date(v.saved_at).toLocaleString()}</span>
                    <span class="version-hash">${v.content_hash}</span>
                    <span class="version-size">${v.content_length} chars</span>
                `;
                item.addEventListener('click', () => {
                    // Load diff between this and previous
                    if (v.version > 1) {
                        loadDiff(noteId, v.version - 1, v.version);
                    } else {
                        // Just show the version content
                        if (typeof ToastManager !== 'undefined') {
                            ToastManager.show(`Viewing version ${v.version}`, 'info');
                        }
                    }
                });
                versionsList.appendChild(item);
            });
        } catch (e) {
            versionsList.innerHTML = '<p class="empty-title">Failed to load version history</p>';
        }
    }

    async function loadDiff(noteId, oldVersion, newVersion) {
        const diffView = document.getElementById('diff-view');
        const diffContent = document.getElementById('diff-content');
        const diffTitle = document.getElementById('diff-title');

        try {
            const resp = await fetch(`/api/notes/${noteId}/diff?old_version=${oldVersion}&new_version=${newVersion}`);
            if (!resp.ok) {
                if (typeof ToastManager !== 'undefined') {
                    ToastManager.show('Failed to load diff', 'error');
                }
                return;
            }
            const data = await resp.json();

            diffTitle.textContent = `Diff: v${data.old_version} → v${data.new_version}`;
            diffView.style.display = 'block';
            diffContent.innerHTML = '';

            const table = document.createElement('div');
            table.className = 'diff-table';
            for (const line of (data.lines || [])) {
                const lineEl = document.createElement('div');
                lineEl.className = `diff-line diff-${line.type}`;
                lineEl.innerHTML = `<span class="diff-line-num">${line.old_line || ''} / ${line.new_line || ''}</span><span class="diff-line-content">${_escapeHtml(line.content)}</span>`;
                table.appendChild(lineEl);
            }
            diffContent.appendChild(table);
        } catch (e) {
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load diff', 'error');
            }
        }
    }

    // ─── Timeline View ──────────────────────────────────────────────

    async function loadTimeline(noteId) {
        const previewNote = document.getElementById('preview-note');
        const previewEmpty = document.getElementById('preview-empty');
        const editor = document.getElementById('preview-editor');
        const versions = document.getElementById('preview-versions');
        const timeline = document.getElementById('preview-timeline');

        // Hide other views
        previewNote.style.display = 'none';
        previewEmpty.style.display = 'none';
        editor.style.display = 'none';
        versions.style.display = 'none';
        timeline.style.display = 'block';

        const timelineContent = document.getElementById('timeline-content');

        try {
            // Get graph events by fetching graph data for this note
            const resp = await fetch(`/api/graph/${noteId}?hops=1`);
            if (!resp.ok) {
                timelineContent.innerHTML = '<p class="empty-title">No timeline data available</p>';
                return;
            }
            const data = await resp.json();
            const nodes = data.nodes || [];
            const edges = data.edges || [];

            // Filter temporal edges (PRECEDES, FOLLOWS, DERIVED_FROM)
            const temporalTypes = new Set(['PRECEDES', 'FOLLOWS', 'DERIVED_FROM', 'REPLACED_BY']);
            const temporalEdges = edges.filter(e => temporalTypes.has(e.rel_type));

            timelineContent.innerHTML = '';

            if (temporalEdges.length === 0) {
                timelineContent.innerHTML = '<p class="empty-title">No temporal relationships found</p>';
                return;
            }

            const timelineItems = document.createElement('div');
            timelineItems.className = 'timeline-items';

            temporalEdges.forEach(e => {
                const nodeMap = {};
                nodes.forEach(n => { nodeMap[n.note_id] = n; });

                const sourceNode = nodeMap[e.source_id];
                const targetNode = nodeMap[e.target_id];

                if (sourceNode && targetNode) {
                    const item = document.createElement('div');
                    item.className = 'timeline-item';
                    const isForward = e.source_id === noteId;
                    item.innerHTML = `
                        <div class="timeline-dot ${e.rel_type.toLowerCase()}"></div>
                        <div class="timeline-line"></div>
                        <div class="timeline-body">
                            <span class="timeline-rel">${isForward ? '→' : '←'} ${e.rel_type}</span>
                            <span class="timeline-note">${isForward ? targetNode.title : sourceNode.title}</span>
                        </div>
                    `;
                    timelineItems.appendChild(item);
                }
            });

            timelineContent.appendChild(timelineItems);
        } catch (e) {
            timelineContent.innerHTML = '<p class="empty-title">Failed to load timeline</p>';
        }
    }

    function _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return { init, startEditing, cancelEdit, loadVersionHistory, loadTimeline, showNewNoteModal };
})();