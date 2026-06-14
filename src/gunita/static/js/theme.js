/* ═══════════════════════════════════════════════════════════════════════
   theme.js — Dark/light theme toggle with localStorage persistence
   ═══════════════════════════════════════════════════════════════════════ */

const ThemeManager = (() => {
    const STORAGE_KEY = 'gunita-theme';
    let _currentTheme = 'dark';

    /**
     * Initialize theme from saved preference or system default.
     */
    function init() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved === 'light' || saved === 'dark') {
            _currentTheme = saved;
        } else {
            // Check system preference
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
                _currentTheme = 'light';
            }
        }
        apply(_currentTheme);
        setupToggle();
    }

    /**
     * Apply the theme to the document.
     */
    function apply(theme) {
        _currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);

        // Update toggle button icon
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.textContent = theme === 'dark' ? '🌙' : '☀️';
            btn.title = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
        }
    }

    /**
     * Toggle between dark and light themes.
     */
    function toggle() {
        const next = _currentTheme === 'dark' ? 'light' : 'dark';
        apply(next);
    }

    /**
     * Set up the theme toggle button click handler.
     */
    function setupToggle() {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', toggle);
        }
    }

    /**
     * Get the current theme.
     */
    function getTheme() {
        return _currentTheme;
    }

    return { init, toggle, getTheme };
})();