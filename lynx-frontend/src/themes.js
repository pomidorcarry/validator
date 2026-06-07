// ── AI Status ─────────────────────────────────────────────────

async function checkAiStatus(fullCheck) {
    var dot = document.getElementById('aiStatusDot');
    var cfgEl = document.getElementById('aiStatusConfigured');
    var respEl = document.getElementById('aiStatusResponsive');
    var btn = document.getElementById('aiCheckBtn');

    dot.className = 'dot checking';
    cfgEl.textContent = 'Проверка...';
    cfgEl.className = 'ai-popup-value checking';
    respEl.textContent = '—';
    respEl.className = 'ai-popup-value unknown';
    if (btn) btn.disabled = true;

    var errEl = document.getElementById('aiStatusError');

    try {
        var url = window.API_BASE + '/ai/status?check=' + (fullCheck ? 'true' : 'false');
        var r = await fetch(url);
        var data = await r.json();

        cfgEl.textContent = data.configured ? '✅ Настроен' : '❌ Не настроен';
        cfgEl.className = 'ai-popup-value ' + (data.configured ? 'ok' : 'fail');
        dot.className = 'dot ' + (data.configured ? 'ok' : 'fail');

        if (data.responsive === true) {
            respEl.textContent = '✅ Отвечает';
            respEl.className = 'ai-popup-value ok';
            dot.className = 'dot ok';
        } else if (data.responsive === false) {
            respEl.textContent = '❌ ' + (data.error_detail || 'Не отвечает');
            respEl.className = 'ai-popup-value fail';
            dot.className = 'dot fail';
        } else if (data.configured) {
            respEl.textContent = '— (нажмите "Проверить")';
            respEl.className = 'ai-popup-value unknown';
            dot.className = 'dot ok';
        }
        if (errEl) errEl.style.display = 'none';
    } catch (e) {
        cfgEl.textContent = '⚠ Ошибка';
        cfgEl.className = 'ai-popup-value fail';
        respEl.textContent = '⚠ Нет связи';
        respEl.className = 'ai-popup-value fail';
        dot.className = 'dot fail';
    }
    if (btn) btn.disabled = false;
}

window.toggleAiPopup = function() {
    var popup = document.getElementById('aiPopup');
    var isOpen = popup.classList.contains('open');
    popup.classList.toggle('open');
    if (!isOpen) {
        checkAiStatus(false);
    }
};

document.addEventListener('click', function(e) {
    var wrap = document.querySelector('.ai-status-wrap');
    if (wrap && !wrap.contains(e.target)) {
        var popup = document.getElementById('aiPopup');
        if (popup) popup.classList.remove('open');
    }
});

setTimeout(function() { checkAiStatus(false); }, 2000);

// ── Theme switching ────────────────────────────────────────────

var THEMES = {
    original: {
        name: 'Оригинальная',
        icon: '⬟',
        vars: {
            '--bg': '#0b0914',
            '--bg-body': 'radial-gradient(ellipse at 50% 0%, #1e1233 0%, #0b0914 70%)',
            '--panel': '#121018',
            '--border': '#2a2030',
            '--text': '#e0dce8',
            '--text-secondary': '#8880a0',
            '--accent': '#8b5cf6',
            '--error': '#ff6b6b',
            '--warning': '#ffb74d',
            '--accent-light': '#8b5cf618',
            '--accent-hover': '#7c3aed',
        }
    },
    coffee: {
        name: 'Coffee',
        icon: '☕',
        vars: {
            '--bg': '#2b2420',
            '--bg-body': '#2b2420',
            '--panel': '#352d28',
            '--border': '#4a413a',
            '--text': '#e8ddd0',
            '--text-secondary': '#a69988',
            '--accent': '#3a9d5c',
            '--error': '#c94a4a',
            '--warning': '#c9943a',
            '--accent-light': '#3a9d5c18',
            '--accent-hover': '#47b96e',
        }
    }
};

var currentTheme = localStorage.getItem('lynx-theme') || 'original';

function applyTheme(themeId) {
    var theme = THEMES[themeId];
    if (!theme) return;
    var root = document.documentElement;
    for (var key in theme.vars) {
        root.style.setProperty(key, theme.vars[key]);
    }
    var btn = document.getElementById('btnThemeToggle');
    if (btn) btn.textContent = theme.icon;
    currentTheme = themeId;
    localStorage.setItem('lynx-theme', themeId);
}

window.toggleTheme = function() {
    var next = currentTheme === 'original' ? 'coffee' : 'original';
    applyTheme(next);
};

applyTheme(currentTheme);
