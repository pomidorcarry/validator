// ── AI Check ─────────────────────────────────────────────────────

var _aiCheckProblems = [];

async function loadAiCheck() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/ai-check');
        if (!resp.ok) return;
        var data = await resp.json();
        if (data.has_result && data.problems && data.problems.length) {
            _aiCheckProblems = data.problems;
            renderAiCheckProblems();
        } else {
            showAiCheckStart();
        }
    } catch(e) {
        showAiCheckStart();
    }
}
window.loadAiCheck = loadAiCheck;

function showAiCheckStart() {
    document.getElementById('aiCheckCenter').style.display = 'flex';
    document.getElementById('aiCheckResults').style.display = 'none';
    document.getElementById('aiCheckBtn').disabled = false;
    document.getElementById('aiCheckBtn').textContent = '🔍 Проверить';
    document.getElementById('aiCheckStatus').textContent = 'Сравнение элементов BIM-модели с ТЗ и нормами СП';
}

function showAiCheckLoading() {
    document.getElementById('aiCheckCenter').style.display = 'flex';
    document.getElementById('aiCheckResults').style.display = 'none';
    document.getElementById('aiCheckBtn').disabled = true;
    document.getElementById('aiCheckBtn').textContent = '⏳ Проверка...';
    document.getElementById('aiCheckStatus').textContent = 'Анализ элементов модели, ТЗ и норм СП...';
}

function renderAiCheckProblems() {
    document.getElementById('aiCheckCenter').style.display = 'none';
    document.getElementById('aiCheckResults').style.display = 'block';
    document.getElementById('aiCheckBtn').disabled = false;
    document.getElementById('aiCheckBtn').textContent = '🔍 Проверить';

    var errorCount = 0;
    var warningCount = 0;
    var dismissedCount = 0;
    _aiCheckProblems.forEach(function(p) {
        if (p.dismissed) { dismissedCount++; return; }
        if (p.severity === 'error') errorCount++;
        else warningCount++;
    });

    var counter = document.getElementById('aiCheckCounter');
    var parts = [];
    if (errorCount) parts.push('<span style="color:var(--error)">' + errorCount + ' ошибок</span>');
    if (warningCount) parts.push('<span style="color:var(--warning)">' + warningCount + ' предупреждений</span>');
    if (dismissedCount) parts.push('<span style="color:var(--text-secondary)">' + dismissedCount + ' отклонено</span>');
    counter.innerHTML = 'Найдено: ' + (parts.length ? parts.join(' · ') : 'проблем не обнаружено ✓');

    if (!_aiCheckProblems.length) {
        document.getElementById('aiCheckProblemList').innerHTML =
            '<div class="ai-check-empty"><div class="big-icon">✅</div><p>Проблем не обнаружено</p></div>';
        return;
    }

    var html = '';
    _aiCheckProblems.forEach(function(p, i) {
        var sevClass = p.severity === 'error' ? 'error' : 'warning';
        var dismissed = p.dismissed ? ' dismissed' : '';
        var dismissIcon = p.dismissed ? '↩' : '✕';
        var dismissTitle = p.dismissed ? 'Восстановить' : 'Отклонить';
        html +=
            '<div class="ai-problem-card' + dismissed + '" data-index="' + i + '">' +
                '<div class="ai-problem-severity ' + sevClass + '"></div>' +
                '<div class="ai-problem-body">' +
                    '<div class="ai-problem-msg">' + window.escHtml(p.message) + '</div>' +
                    (p.details ? '<div class="ai-problem-details">' + window.escHtml(p.details) + '</div>' : '') +
                    (p.rule_key ? '<div class="ai-problem-rule">' + window.escHtml(p.rule_key) + '</div>' : '') +
                '</div>' +
                '<button class="ai-problem-dismiss" onclick="toggleAiProblem(' + i + ')" title="' + dismissTitle + '">' + dismissIcon + '</button>' +
            '</div>';
    });
    document.getElementById('aiCheckProblemList').innerHTML = html;
}

window.runAiCheck = async function() {
    if (!window.currentProjectId) return;
    showAiCheckLoading();
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/ai-check', {
            method: 'POST',
        });
        if (!resp.ok) {
            var errDetail = '';
            try { var errJson = await resp.json(); errDetail = errJson.detail || ''; } catch(e2) {}
            throw new Error(errDetail || 'HTTP ' + resp.status);
        }
        var data = await resp.json();
        _aiCheckProblems = data.problems || [];
        renderAiCheckProblems();
        if (!_aiCheckProblems.length) {
            window.showToast('Проверка завершена — проблем не найдено', 'success');
        } else {
            window.showToast('Найдено ' + _aiCheckProblems.length + ' замечаний', _aiCheckProblems.some(function(p) { return p.severity === 'error'; }) ? 'error' : 'success');
        }
    } catch(e) {
        showAiCheckStart();
        window.showToast('Ошибка проверки: ' + e.message, 'error');
    }
};

window.toggleAiProblem = async function(index) {
    var problem = _aiCheckProblems[index];
    if (!problem) return;
    var newState = !problem.dismissed;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/ai-check/' + index + '?dismissed=' + newState, {
            method: 'PATCH',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        _aiCheckProblems[index].dismissed = newState;
        renderAiCheckProblems();
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};
