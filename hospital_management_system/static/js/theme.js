document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('themeToggle');
    const lightModeBtn = document.getElementById('lightModeBtn');
    const darkModeBtn = document.getElementById('darkModeBtn');
    const body = document.body;

    function updatePillButtons(isDark) {
        if (lightModeBtn && darkModeBtn) {
            if (isDark) {
                lightModeBtn.classList.remove('active');
                darkModeBtn.classList.add('active');
            } else {
                lightModeBtn.classList.add('active');
                darkModeBtn.classList.remove('active');
            }
        }
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.add(savedTheme);
        updatePillButtons(true);
    } else {
        updatePillButtons(false);
    }

    if (themeToggle) {
        const icon = themeToggle.querySelector('i');
        
        // Initial icon state
        if (body.classList.contains('dark-mode')) {
            icon.classList.replace('fa-moon', 'fa-sun');
        }

        themeToggle.addEventListener('click', () => {
            body.classList.toggle('dark-mode');
            const isDark = body.classList.contains('dark-mode');
            
            if (isDark) {
                icon.classList.replace('fa-moon', 'fa-sun');
            } else {
                icon.classList.replace('fa-sun', 'fa-moon');
            }
            
            updatePillButtons(isDark);
            localStorage.setItem('theme', isDark ? 'dark-mode' : '');
        });
    }

    if (lightModeBtn && darkModeBtn) {
        lightModeBtn.addEventListener('click', () => {
            body.classList.remove('dark-mode');
            updatePillButtons(false);
            localStorage.setItem('theme', '');
            if (themeToggle) {
                const icon = themeToggle.querySelector('i');
                if (icon) icon.classList.replace('fa-sun', 'fa-moon');
            }
        });

        darkModeBtn.addEventListener('click', () => {
            body.classList.add('dark-mode');
            updatePillButtons(true);
            localStorage.setItem('theme', 'dark-mode');
            if (themeToggle) {
                const icon = themeToggle.querySelector('i');
                if (icon) icon.classList.replace('fa-moon', 'fa-sun');
            }
        });
    }
});

