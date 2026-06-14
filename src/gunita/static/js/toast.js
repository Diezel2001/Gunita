/* ═══════════════════════════════════════════════════════════════════════
   toast.js — Non-intrusive toast notifications
   ═══════════════════════════════════════════════════════════════════════ */

const ToastManager = (() => {
    let container = null;
    const TOAST_DURATION = 4000; // 4 seconds
    const MAX_TOASTS = 5;

    /**
     * Initialize the toast container.
     */
    function init() {
        container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
    }

    /**
     * Show a toast notification.
     * @param {string} message - The message to display.
     * @param {'success'|'error'|'info'|'warning'} type - The toast type.
     * @param {number} duration - Duration in ms before auto-dismiss.
     */
    function show(message, type = 'info', duration = TOAST_DURATION) {
        if (!container) init();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = type === 'success' ? '✓'
            : type === 'error' ? '✕'
            : type === 'warning' ? '⚠'
            : 'ℹ';

        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${escapeHtml(message)}</span>
            <button class="toast-close" title="Dismiss">&times;</button>
        `;

        // Close button handler
        toast.querySelector('.toast-close').addEventListener('click', () => {
            dismiss(toast);
        });

        container.appendChild(toast);

        // Trigger enter animation
        requestAnimationFrame(() => {
            toast.classList.add('toast-visible');
        });

        // Auto-dismiss
        setTimeout(() => {
            dismiss(toast);
        }, duration);

        // Limit total toasts
        while (container.children.length > MAX_TOASTS) {
            container.removeChild(container.firstChild);
        }
    }

    /**
     * Dismiss a toast with animation.
     */
    function dismiss(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.remove('toast-visible');
        toast.classList.add('toast-exit');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return { init, show };
})();