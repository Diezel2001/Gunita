/* ═══════════════════════════════════════════════════════════════════════
   tree.js — Vault file tree widget
   ═══════════════════════════════════════════════════════════════════════ */

const TreeManager = (() => {
    let container = null;
    let onFileSelect = null;

    /**
     * Initialize the tree panel.
     */
    function init(containerEl, clickCallback) {
        container = containerEl;
        onFileSelect = clickCallback;
    }

    /**
     * Load and render the vault file tree from the API.
     */
    async function loadTree() {
        container.innerHTML = '<div class="tree-loading"><div class="spinner"></div><span>Loading vault...</span></div>';

        try {
            const resp = await fetch('/api/vault/');
            const tree = await resp.json();
            container.innerHTML = '';

            if (!tree.children || tree.children.length === 0) {
                container.innerHTML = '<div class="tree-empty">Vault is empty</div>';
                return;
            }

            const fragment = document.createDocumentFragment();
            fragment.appendChild(renderNode(tree, 0));
            container.appendChild(fragment);
        } catch (err) {
            console.error('Failed to load vault tree:', err);
            container.innerHTML = '<div class="tree-empty">Failed to load vault</div>';
            if (typeof ToastManager !== 'undefined') {
                ToastManager.show('Failed to load vault tree', 'error');
            }
        }
    }

    /**
     * Recursively render a tree node.
     * Uses document fragment for performance with large trees.
     */
    function renderNode(node, depth) {
        const div = document.createElement('div');
        div.className = 'tree-node';

        const label = document.createElement('div');
        label.className = 'tree-node-label';
        label.style.paddingLeft = (depth * 4) + 'px';

        if (node.type === 'directory' && node.children && node.children.length > 0) {
            const toggle = document.createElement('span');
            toggle.className = 'tree-toggle';
            toggle.textContent = '▼';
            label.appendChild(toggle);

            const icon = document.createElement('span');
            icon.className = 'tree-icon';
            icon.textContent = '📁';
            label.appendChild(icon);

            const nameSpan = document.createElement('span');
            nameSpan.textContent = node.name;
            label.appendChild(nameSpan);

            const childrenDiv = document.createElement('div');
            childrenDiv.className = 'tree-children';

            for (const child of node.children) {
                childrenDiv.appendChild(renderNode(child, depth + 1));
            }

            let expanded = true;
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                expanded = !expanded;
                childrenDiv.style.display = expanded ? '' : 'none';
                toggle.textContent = expanded ? '▼' : '▶';
            });

            div.appendChild(label);
            div.appendChild(childrenDiv);

        } else if (node.is_note) {
            const toggle = document.createElement('span');
            toggle.className = 'tree-toggle';
            toggle.textContent = '';
            label.appendChild(toggle);

            const icon = document.createElement('span');
            icon.className = 'tree-icon';
            icon.textContent = '📄';
            label.appendChild(icon);

            const nameSpan = document.createElement('span');
            nameSpan.textContent = node.name.replace('.md', '');
            label.appendChild(nameSpan);

            label.addEventListener('click', () => {
                // Remove previous active
                container.querySelectorAll('.tree-node-label.active').forEach((el) => {
                    el.classList.remove('active');
                });
                label.classList.add('active');
                if (onFileSelect) onFileSelect(node.path);
            });

            div.appendChild(label);

        } else {
            // Non-md file or empty directory — show but don't interact
            const toggle = document.createElement('span');
            toggle.className = 'tree-toggle';
            toggle.textContent = '';
            label.appendChild(toggle);

            const icon = document.createElement('span');
            icon.className = 'tree-icon';
            icon.textContent = node.type === 'directory' ? '📁' : '📎';
            label.appendChild(icon);

            const nameSpan = document.createElement('span');
            nameSpan.textContent = node.name;
            label.appendChild(nameSpan);

            div.appendChild(label);
        }

        return div;
    }

    return { init, loadTree };
})();