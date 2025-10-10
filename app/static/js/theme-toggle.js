(function () {
    const storageKey = 'settlenet-theme';
    const themes = ['neural', 'midnight'];
    const themeLabels = {
        neural: 'Neural Canopy',
        midnight: 'Midnight Prism'
    };

    const body = document.body;
    if (!body) {
        return;
    }

    const toggles = Array.from(document.querySelectorAll('[data-theme-toggle]'));
    if (!toggles.length) {
        return;
    }

    const defaultTheme = body.dataset.theme && themes.includes(body.dataset.theme)
        ? body.dataset.theme
        : themes[0];

    const storedTheme = safelyGetStoredTheme();
    const initialTheme = storedTheme && themes.includes(storedTheme) ? storedTheme : defaultTheme;

    applyTheme(initialTheme);

    toggles.forEach((button) => {
        button.addEventListener('click', () => {
            const currentTheme = body.dataset.theme && themes.includes(body.dataset.theme)
                ? body.dataset.theme
                : defaultTheme;
            const nextTheme = getNextTheme(currentTheme);
            applyTheme(nextTheme);
            safelyStoreTheme(nextTheme);
        });
    });

    function applyTheme(theme) {
        body.dataset.theme = theme;
        updateToggleLabels(theme);
    }

    function updateToggleLabels(theme) {
        const nextTheme = getNextTheme(theme);
        toggles.forEach((button) => {
            const label = button.querySelector('[data-theme-toggle-text]');
            if (label) {
                label.textContent = `Switch to ${themeLabels[nextTheme]}`;
            }
            button.setAttribute('aria-label', `Activate ${themeLabels[nextTheme]} theme`);
        });
    }

    function getNextTheme(current) {
        const currentIndex = themes.indexOf(current);
        if (currentIndex === -1) {
            return themes[0];
        }
        return themes[(currentIndex + 1) % themes.length];
    }

    function safelyStoreTheme(theme) {
        try {
            window.localStorage.setItem(storageKey, theme);
        } catch (error) {
            console.warn('Unable to persist theme preference', error);
        }
    }

    function safelyGetStoredTheme() {
        try {
            return window.localStorage.getItem(storageKey);
        } catch (error) {
            console.warn('Unable to read stored theme preference', error);
            return null;
        }
    }
})();
