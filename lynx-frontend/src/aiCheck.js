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
            // Also load existing fixes
            loadExistingFixes();
        } else {
            showAiCheckStart();
        }
    } catch(e) {
        showAiCheckStart();
    }
}
window.loadAiCheck = loadAiCheck;

async function loadExistingFixes() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/fix-suggestions');
        if (!resp.ok) return;
        var data = await resp.json();
        _aiFixes = data.fixes || [];
        if (_aiFixes.length) {
            renderFixes();
        }
    } catch(e) {}
}

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

// ── Fix Suggestions ─────────────────────────────────────────────

var _aiFixes = [];

window.generateFixes = async function() {
    var btn = document.getElementById('btnGenerateFixes');
    btn.disabled = true;
    btn.textContent = '⏳ Генерация...';
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/fix-suggestions', {
            method: 'POST',
        });
        if (!resp.ok) {
            var err = '';
            try { var ej = await resp.json(); err = ej.detail || ''; } catch(e2) {}
            throw new Error(err || 'HTTP ' + resp.status);
        }
        var data = await resp.json();
        _aiFixes = data.fixes || [];
        renderFixes();
        window.showToast('Сгенерировано ' + _aiFixes.length + ' исправлений', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Сгенерировать исправления';
    }
};

function renderFixes() {
    var section = document.getElementById('aiFixSection');
    var list = document.getElementById('aiFixList');
    var status = document.getElementById('aiFixStatus');
    var btnApplyAll = document.getElementById('btnApplyAllFixes');
    var instr = document.getElementById('aiFixInstructions');
    
    if (!_aiFixes.length) {
        section.style.display = 'none';
        return;
    }
    
    section.style.display = 'block';
    
    var pending = _aiFixes.filter(function(f) { return f.status === 'pending'; }).length;
    var approved = _aiFixes.filter(function(f) { return f.status === 'approved'; }).length;
    var rejected = _aiFixes.filter(function(f) { return f.status === 'rejected'; }).length;
    var applied = _aiFixes.filter(function(f) { return f.status === 'applied'; }).length;
    
    var parts = [];
    if (pending) parts.push('ожидают: ' + pending);
    if (approved) parts.push('утверждено: ' + approved);
    if (rejected) parts.push('отклонено: ' + rejected);
    if (applied) parts.push('применено: ' + applied);
    status.textContent = parts.length ? parts.join(' · ') : 'Нет исправлений';
    btnApplyAll.style.display = pending > 0 ? '' : 'none';
    
    var html = '';
    _aiFixes.forEach(function(fix, i) {
        var riskLabel = { low: 'Низкий', medium: 'Средний', high: 'Высокий' };
        var riskClass = fix.risk || 'medium';
        var statusClass = fix.status || 'pending';
        var stepsHtml = '';
        if (fix.steps && fix.steps.length) {
            stepsHtml = '<div class="ai-fix-steps">' + fix.steps.map(function(s) {
                if (s.action === 'set_param') {
                    return '<div class="ai-fix-step">📌 <code>' + window.escHtml(s.param) + '</code> = <code>' + window.escHtml(s.value) + '</code></div>';
                } else if (s.action === 'copy_param') {
                    return '<div class="ai-fix-step">📋 <code>' + window.escHtml(s.from_param) + '</code> → <code>' + window.escHtml(s.to_param) + '</code></div>';
                } else if (s.action === 'set_system') {
                    return '<div class="ai-fix-step">🔗 Система: <code>' + window.escHtml(s.system_name) + '</code></div>';
                }
                return '<div class="ai-fix-step">' + window.escHtml(JSON.stringify(s)) + '</div>';
            }).join('') + '</div>';
        }
        
        var actionsHtml = '';
        if (fix.status === 'pending') {
            actionsHtml = '<div class="ai-fix-actions">' +
                '<button class="btn btn-sm" onclick="approveFix(' + i + ')" style="background:#34d399;color:#000">✓ Утвердить</button>' +
                '<button class="btn btn-sm btn-outline" onclick="rejectFix(' + i + ')">✕ Отклонить</button>' +
            '</div>';
        } else if (fix.status === 'approved') {
            actionsHtml = '<div class="ai-fix-actions">' +
                '<button class="btn btn-sm btn-outline" onclick="rejectFix(' + i + ')">↩ Отменить</button>' +
            '</div>';
        } else if (fix.status === 'rejected') {
            actionsHtml = '<div class="ai-fix-actions">' +
                '<button class="btn btn-sm btn-outline" onclick="approveFix(' + i + ')">↩ Восстановить</button>' +
            '</div>';
        } else if (fix.status === 'applied') {
            var result = fix.applied_result || {};
            actionsHtml = '<div class="ai-fix-actions"><span style="font-size:12px;color:#34d399">✓ Применено в Revit' +
                (result.error_message ? ': ' + window.escHtml(result.error_message) : '') + '</span></div>';
        } else if (fix.status === 'failed') {
            var result = fix.applied_result || {};
            actionsHtml = '<div class="ai-fix-actions"><span style="font-size:12px;color:var(--error)">✗ Ошибка: ' + window.escHtml(result.error_message || '') + '</span></div>';
        }
        
        html += '<div class="ai-fix-card ' + statusClass + '">' +
            '<div class="ai-fix-header">' +
                '<span class="ai-fix-risk ' + riskClass + '">' + riskLabel[riskClass] + '</span>' +
                '<span style="font-size:11px;color:var(--text-secondary);flex:1">' + window.escHtml(fix.issue_message || '') + '</span>' +
                '<span style="font-size:11px;color:var(--text-secondary)">#' + (fix.fix_id || '').substring(0, 8) + '</span>' +
            '</div>' +
            '<div class="ai-fix-desc">' + window.escHtml(fix.description || '') + '</div>' +
            '<div class="ai-fix-element">🔹 ' + window.escHtml(fix.element_name || fix.element_global_id || '') + '</div>' +
            stepsHtml +
            actionsHtml +
        '</div>';
    });
    list.innerHTML = html;
    
    // Show instructions if there are approved fixes
    var approvedFixes = _aiFixes.filter(function(f) { return f.status === 'approved'; });
    if (approvedFixes.length) {
        instr.style.display = 'block';
        document.getElementById('aiFixCodeOutput').value = JSON.stringify(approvedFixes, null, 2);
    } else {
        instr.style.display = 'none';
    }
}

window.approveFix = async function(index) {
    var fix = _aiFixes[index];
    if (!fix) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/fix-suggestions/' + fix.fix_id + '?status=approved', {
            method: 'PATCH',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        _aiFixes[index].status = 'approved';
        renderFixes();
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.rejectFix = async function(index) {
    var fix = _aiFixes[index];
    if (!fix) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/fix-suggestions/' + fix.fix_id + '?status=rejected', {
            method: 'PATCH',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        _aiFixes[index].status = 'rejected';
        renderFixes();
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.approveAllFixes = async function() {
    var pending = _aiFixes.filter(function(f) { return f.status === 'pending'; });
    if (!pending.length) return;
    var ids = pending.map(function(f) { return f.fix_id; });
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/fix-suggestions', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fix_ids: ids, status: 'approved' }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        pending.forEach(function(f) { f.status = 'approved'; });
        renderFixes();
        window.showToast('Утверждено ' + ids.length + ' исправлений', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.copyFixInstructions = function() {
    var ta = document.getElementById('aiFixCodeOutput');
    ta.select();
    document.execCommand('copy');
    window.showToast('Скопировано в буфер', 'success');
};
