// ── Changes (Внесение изменений в проект) ─────────────────────

var _changeOrders = [];
var _availableFixes = [];

window.loadChangesTab = function() {
    loadChangesPage();
};

async function loadChangesPage() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes');
        if (resp.ok) {
            var data = await resp.json();
            _changeOrders = data.orders || [];
        }
    } catch(e) {}
    // Load available fixes from AI check and rule-based issues
    await loadAvailableFixes();
    renderChangesPage();
}

async function loadAvailableFixes() {
    _availableFixes = [];
    // 1. Get AI check issues (non-dismissed)
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/ai-check');
        if (resp.ok) {
            var data = await resp.json();
            if (data.problems) {
                data.problems.forEach(function(p, i) {
                    if (p.dismissed) return;
                    var eids = p.element_ids;
                    if (!eids || !eids.length) {
                        eids = p.global_id ? [p.global_id] : [];
                    }
                    _availableFixes.push({
                        source: 'ai_check',
                        source_index: i,
                        element_name: p.element_name || '',
                        element_ids: eids,
                        cube_id: p.cube_id || '',
                        revit_element_ids: p.revit_element_ids || (p.revit_element_id ? [p.revit_element_id] : []),
                        global_id: p.global_id || '',
                        message: p.message || '',
                        details: p.details || '',
                        severity: p.severity || 'warning',
                        rule_key: p.rule_key || '',
                    });
                });
            }
        }
    } catch(e) {}
    // 2. Get rule-based issues from the selected model
    var modelId = window.selectedModelId;
    if (modelId) {
        try {
            var resp = await fetch(window.API_BASE + '/models/' + modelId + '/issues');
            if (resp.ok) {
                var data = await resp.json();
                if (data.issues) {
                    data.issues.forEach(function(issue, i) {
                        if (issue.status === 'resolved' || issue.status === 'dismissed') return;
                        _availableFixes.push({
                            source: 'rule_based',
                            source_index: i,
                            element_name: issue.element_name || '',
                            element_ids: issue.global_id ? [issue.global_id] : [],
                            cube_id: issue.cube_id || '',
                            revit_element_ids: issue.revit_element_ids || (issue.revit_element_id ? [issue.revit_element_id] : []),
                            global_id: issue.global_id || '',
                            message: issue.message || '',
                            details: issue.details || '',
                            severity: issue.severity || 'error',
                            rule_key: issue.rule_key || '',
                        });
                    });
                }
            }
        } catch(e) {}
    }
}

window.runRuleBasedCheck = async function() {
    var modelId = window.selectedModelId;
    if (!modelId) {
        window.showToast('Нет выбранной модели в проекте', 'error');
        return;
    }
    try {
        var resp = await fetch(window.API_BASE + '/models/' + modelId + '/reprocess-rules', {
            method: 'POST',
        });
        if (!resp.ok) {
            var err = '';
            try { var ej = await resp.json(); err = ej.detail || ''; } catch(e2) {}
            throw new Error(err || 'HTTP ' + resp.status);
        }
        var data = await resp.json();
        window.showToast('Rule-based проверка завершена: ' + (data.count || 0) + ' замечаний', 'success');
        // Reload page to show new issues
        await loadChangesPage();
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

function renderChangesPage() {
    var container = document.getElementById('changesContent');
    if (!container) return;

    var html = '';

    // ── Available fixes section ──
    var aiFixes = _availableFixes.filter(function(f) { return f.source === 'ai_check'; });
    var ruleFixes = _availableFixes.filter(function(f) { return f.source === 'rule_based'; });

    html += '<div class="changes-section">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">';
    html += '<div style="font-size:14px;font-weight:600">📋 Доступные замечания к включению</div>';
    if (aiFixes.length || ruleFixes.length) {
        html += '<button class="btn btn-primary" onclick="showAddAllToOrderModal()" style="font-size:12px">➕ Добавить все в приказ</button>';
    }
    html += '</div>';

    if (_availableFixes.length === 0) {
        html += '<div class="empty-message" style="padding:24px;text-align:center;color:var(--text-secondary);font-size:13px">';
        html += 'Нет доступных замечаний. Запустите <strong>проверку с ИИ</strong> на вкладке "🧠 Проверка с ИИ"';
        html += ' или нажмите <button class="btn-sm" onclick="runRuleBasedCheck()" style="font-size:11px;vertical-align:middle">📐 Запустить rule-based проверку</button>';
        html += ' для текущей модели.';
        html += '</div>';
    } else {
        if (aiFixes.length) {
            html += '<div style="display:flex;align-items:center;justify-content:space-between;margin:8px 0 6px">';
            html += '<div style="font-size:13px;font-weight:600;color:var(--accent)">🧠 Проверка с ИИ (' + aiFixes.length + ')</div>';
            html += '</div>';
            html += '<div class="changes-fix-list">';
            aiFixes.forEach(function(fix, i) {
                var sevIcon = fix.severity === 'error' ? '🔴' : '🟡';
                var sevClass = fix.severity === 'error' ? 'error' : 'warning';
                var cubeStr = fix.cube_id ? fix.cube_id : '';
                var revitStr = (fix.revit_element_ids || []).length ? fix.revit_element_ids.join(', ') : '';
                var ifcStr = (fix.element_ids || []).length ? fix.element_ids.join(', ') : fix.global_id || '';
                html +=
                    '<div class="changes-fix-card">' +
                        '<div class="changes-fix-severity ' + sevClass + '">' + sevIcon + '</div>' +
                        '<div class="changes-fix-body">' +
                            '<div class="changes-fix-msg">' + window.escHtml(fix.message) + '</div>' +
                            '<div class="changes-fix-meta">' +
                                (fix.element_name ? '<span class="changes-fix-element">' + window.escHtml(fix.element_name) + '</span>' : '') +
                                (cubeStr ? '<span class="changes-fix-id" style="font-size:11px;color:#f59e0b">🧊 CUBE: ' + window.escHtml(cubeStr) + '</span>' : '') +
                                (revitStr ? '<span class="changes-fix-id" style="font-size:11px;color:#52d399">⚙ Revit: ' + window.escHtml(revitStr) + '</span>' : '') +
                                (ifcStr ? '<span class="changes-fix-id" style="font-size:10px;color:var(--text-secondary)">🏷 IFC: ' + window.escHtml(ifcStr) + '</span>' : '') +
                                (fix.rule_key ? '<span class="changes-fix-rule">' + window.escHtml(fix.rule_key) + '</span>' : '') +
                            '</div>' +
                        '</div>' +
                        '<button class="btn-sm" onclick="addFixToNewOrder(' + i + ')" style="white-space:nowrap">➕</button>' +
                    '</div>';
            });
            html += '</div>';
        }
        if (ruleFixes.length) {
            html += '<div style="display:flex;align-items:center;justify-content:space-between;margin:12px 0 6px">';
            html += '<div style="font-size:13px;font-weight:600;color:var(--accent)">📐 Rule-based (' + ruleFixes.length + ')</div>';
            html += '<button class="btn-sm" onclick="runRuleBasedCheck()" style="font-size:11px">🔄 Запустить rule-based проверку</button>';
            html += '</div>';
            html += '<div class="changes-fix-list">';
            ruleFixes.forEach(function(fix, i) {
                var sevIcon = fix.severity === 'error' ? '🔴' : '🟡';
                var sevClass = fix.severity === 'error' ? 'error' : 'warning';
                var flatIndex = aiFixes.length + i;
                var cubeStr = fix.cube_id ? fix.cube_id : '';
                var revitStr = (fix.revit_element_ids || []).length ? fix.revit_element_ids.join(', ') : '';
                var ifcStr = (fix.element_ids || []).length ? fix.element_ids.join(', ') : fix.global_id || '';
                html +=
                    '<div class="changes-fix-card">' +
                        '<div class="changes-fix-severity ' + sevClass + '">' + sevIcon + '</div>' +
                        '<div class="changes-fix-body">' +
                            '<div class="changes-fix-msg">' + window.escHtml(fix.message) + '</div>' +
                            '<div class="changes-fix-meta">' +
                                (fix.element_name ? '<span class="changes-fix-element">' + window.escHtml(fix.element_name) + '</span>' : '') +
                                (cubeStr ? '<span class="changes-fix-id" style="font-size:11px;color:#f59e0b">🧊 CUBE: ' + window.escHtml(cubeStr) + '</span>' : '') +
                                (revitStr ? '<span class="changes-fix-id" style="font-size:11px;color:#52d399">⚙ Revit: ' + window.escHtml(revitStr) + '</span>' : '') +
                                (ifcStr ? '<span class="changes-fix-id" style="font-size:10px;color:var(--text-secondary)">🏷 IFC: ' + window.escHtml(ifcStr) + '</span>' : '') +
                                (fix.rule_key ? '<span class="changes-fix-rule">' + window.escHtml(fix.rule_key) + '</span>' : '') +
                            '</div>' +
                        '</div>' +
                        '<button class="btn-sm" onclick="addFixToNewOrder(' + flatIndex + ')" style="white-space:nowrap">➕</button>' +
                    '</div>';
            });
            html += '</div>';
        }
    }
    html += '</div>';

    // ── Existing orders ──
    html += '<div class="changes-section" style="margin-top:20px">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">';
    html += '<div style="font-size:14px;font-weight:600">📦 Приказы на внесение изменений</div>';
    html += '<button class="btn" onclick="showCreateOrderModal()" style="font-size:12px">➕ Создать приказ</button>';
    html += '</div>';

    if (_changeOrders.length === 0) {
        html += '<div class="empty-message" style="padding:24px;text-align:center;color:var(--text-secondary);font-size:13px">Нет созданных приказов. Добавьте замечания и создайте приказ.</div>';
    } else {
        html += '<div class="changes-order-list">';
        _changeOrders.forEach(function(order) {
            var statusLabel = { draft: 'Черновик', sent: 'Отправлен', applied: 'Применён', rolled_back: 'Отменён' };
            var statusClass = order.status || 'draft';
            var totalFixes = (order.fixes || []).length;
            var approvedFixes = (order.fixes || []).filter(function(f) { return f.status === 'approved'; }).length;
            var pendingFixes = (order.fixes || []).filter(function(f) { return f.status === 'pending'; }).length;
            html +=
                '<div class="changes-order-card" data-id="' + order.id + '">' +
                    '<div class="changes-order-header">' +
                        '<div>' +
                            '<div class="changes-order-title">' + window.escHtml(order.title) + '</div>' +
                            '<div class="changes-order-date">' + (order.created_at ? order.created_at.slice(0, 16).replace('T', ' ') : '') + '</div>' +
                        '</div>' +
                        '<div class="changes-order-status ' + statusClass + '">' + (statusLabel[order.status] || order.status) + '</div>' +
                    '</div>' +
                    '<div class="changes-order-stats">' +
                        'Исправлений: ' + totalFixes + ' · Утверждено: ' + approvedFixes + ' · Ожидает: ' + pendingFixes +
                    '</div>' +
                    '<div class="changes-order-actions">' +
                        '<button class="btn-sm" onclick="openOrderDetail(\'' + order.id + '\')">📂 Открыть</button>' +
                        '<button class="btn-sm btn-outline" onclick="deleteOrder(\'' + order.id + '\')" style="color:var(--error)">🗑 Удалить</button>' +
                    '</div>' +
                '</div>';
        });
        html += '</div>';
    }
    html += '</div>';

    container.innerHTML = html;
}

window.refreshChangesPage = function() {
    loadChangesPage();
};

// ── Helpers ──

function getDraftOrder() {
    for (var i = 0; i < _changeOrders.length; i++) {
        if (_changeOrders[i].status === 'draft') return _changeOrders[i];
    }
    return null;
}

function isFixInOrder(order, fix) {
    return (order.fixes || []).some(function(f) {
        return f.source === fix.source && f.source_index === fix.source_index;
    });
}

async function appendFixesToOrder(order, fixes, successMsg) {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + order.id, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ append_fixes: fixes }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var updated = await resp.json();
        // Update local order copy
        order.fixes = updated.fixes;
        renderChangesPage();
        window.showToast(successMsg || 'Замечания добавлены в приказ', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
}

// ── Actions ──

window.addFixToNewOrder = function(index) {
    var fix = _availableFixes[index];
    if (!fix) return;
    var draft = getDraftOrder();
    if (draft) {
        if (isFixInOrder(draft, fix)) {
            window.showToast('Это замечание уже добавлено в приказ «' + draft.title + '»', 'info');
            return;
        }
        var now = new Date().toISOString();
        var newFix = {
            id: Math.random().toString(36).slice(2, 14),
            source: fix.source,
            source_index: fix.source_index,
            element_name: fix.element_name,
            element_ids: fix.element_ids || [],
            message: fix.message,
            details: fix.details,
            severity: fix.severity,
            rule_key: fix.rule_key,
            status: 'pending',
            actions: [],
            created_at: now,
        };
        appendFixesToOrder(draft, [newFix], 'Замечание добавлено в приказ «' + draft.title + '»');
    } else {
        var now = new Date().toISOString();
        var order = {
            title: 'Приказ #' + (_changeOrders.length + 1),
            fixes: [{
                id: Math.random().toString(36).slice(2, 14),
                source: fix.source,
                source_index: fix.source_index,
                element_name: fix.element_name,
                element_ids: fix.element_ids || [],
                message: fix.message,
                details: fix.details,
                severity: fix.severity,
                rule_key: fix.rule_key,
                status: 'pending',
                actions: [],
                created_at: now,
            }]
        };
        createOrderAndRefresh(order);
    }
};

window.showAddAllToOrderModal = function() {
    if (_availableFixes.length === 0) {
        window.showToast('Нет доступных замечаний', 'error');
        return;
    }
    var draft = getDraftOrder();
    if (draft) {
        var now = new Date().toISOString();
        var toAdd = [];
        var skipped = 0;
        _availableFixes.forEach(function(fix) {
            if (isFixInOrder(draft, fix)) {
                skipped++;
            } else {
                toAdd.push({
                    id: Math.random().toString(36).slice(2, 14),
                    source: fix.source,
                    source_index: fix.source_index,
                    element_name: fix.element_name,
                    element_ids: fix.element_ids || [],
                    message: fix.message,
                    details: fix.details,
                    severity: fix.severity,
                    rule_key: fix.rule_key,
                    status: 'pending',
                    actions: [],
                    created_at: now,
                });
            }
        });
        if (toAdd.length === 0) {
            window.showToast('Все замечания уже добавлены в приказ «' + draft.title + '»' + (skipped > 0 ? ' (' + skipped + ')' : ''), 'info');
            return;
        }
        var msg = 'Добавить ' + toAdd.length + ' замечаний в приказ «' + draft.title + '»?';
        if (skipped > 0) msg += ' (' + skipped + ' уже есть)';
        if (!confirm(msg)) return;
        appendFixesToOrder(draft, toAdd, 'Добавлено ' + toAdd.length + ' замечаний в приказ «' + draft.title + '»');
    } else {
        var title = prompt('Название приказа:', 'Приказ #' + (_changeOrders.length + 1) + ' (все замечания)');
        if (!title) return;
        var now = new Date().toISOString();
        var order = {
            title: title,
            fixes: _availableFixes.map(function(fix) { return {
                id: Math.random().toString(36).slice(2, 14),
                source: fix.source,
                source_index: fix.source_index,
                element_name: fix.element_name,
                element_ids: fix.element_ids || [],
                message: fix.message,
                details: fix.details,
                severity: fix.severity,
                rule_key: fix.rule_key,
                status: 'pending',
                actions: [],
                created_at: now,
            };})
        };
        createOrderAndRefresh(order);
    }
};

window.showCreateOrderModal = function() {
    var title = prompt('Название приказа:', 'Приказ #' + (_changeOrders.length + 1));
    if (!title) return;
    var order = { title: title, fixes: [] };
    createOrderAndRefresh(order);
};

async function createOrderAndRefresh(order) {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(order),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var created = await resp.json();
        _changeOrders.unshift(created);
        renderChangesPage();
        window.showToast('Приказ создан', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
}

window.deleteOrder = async function(orderId) {
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    var msg = 'Удалить приказ?';
    if (order && order.status !== 'draft') {
        msg = 'Приказ уже ' + ({ sent: 'отправлен', applied: 'применён', rolled_back: 'откачен' }[order.status] || order.status) + '. Удалить всё равно?';
    }
    if (!confirm(msg)) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId, {
            method: 'DELETE',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        _changeOrders = _changeOrders.filter(function(o) { return o.id !== orderId; });
        renderChangesPage();
        window.showToast('Приказ удалён', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Order detail modal ──

window.openOrderDetail = function(orderId) {
    var order = null;
    for (var i = 0; i < _changeOrders.length; i++) {
        if (_changeOrders[i].id === orderId) {
            order = _changeOrders[i];
            break;
        }
    }
    if (!order) return;
    renderOrderDetailModal(order);
};

function renderOrderDetailModal(order) {
    var overlay = document.getElementById('orderDetailModal');
    var content = document.getElementById('orderDetailContent');
    if (!overlay || !content) return;

    var statusLabel = { draft: 'Черновик', sent: 'Отправлен', applied: 'Применён', rolled_back: 'Отменён' };
    var statusClass = order.status || 'draft';
    var fixes = order.fixes || [];

    var html = '';
    html += '<div class="order-detail-header">';
    html += '<div style="font-size:16px;font-weight:600">' + window.escHtml(order.title) + '</div>';
    html += '<div style="display:flex;align-items:center;gap:12px;margin-top:4px">';
    html += '<span class="changes-order-status ' + statusClass + '">' + (statusLabel[order.status] || order.status) + '</span>';
    html += '<span style="font-size:12px;color:var(--text-secondary)">' + (order.created_at ? order.created_at.slice(0, 16).replace('T', ' ') : '') + '</span>';
    html += '</div>';
    html += '</div>';

    if (fixes.length === 0) {
        html += '<div class="empty-message" style="padding:24px;text-align:center;color:var(--text-secondary)">Нет исправлений в этом приказе</div>';
    } else {
        html += '<div style="margin-top:16px;display:flex;flex-direction:column;gap:8px">';
        fixes.forEach(function(fix, idx) {
            var sevIcon = fix.severity === 'error' ? '🔴' : '🟡';
            var sevClass = fix.severity === 'error' ? 'error' : 'warning';
            var sourceLabel = fix.source === 'ai_check' ? '🧠 AI' : '📐 Rule';
            var fixStatusLabel = { pending: '⏳', approved: '✅', rejected: '❌', applied: '✔️' };
            var fixStatusClass = fix.status || 'pending';
            var elemIds = fix.element_ids || (fix.element_global_id ? [fix.element_global_id] : []);
            var revitIds = fix.revit_element_ids || [];
            var elemHtml = '';
            if (fix.element_name) {
                elemHtml += '<span class="changes-fix-element">' + window.escHtml(fix.element_name) + '</span>';
            }
            if (revitIds.length) {
                elemHtml += '<span class="changes-fix-element" style="font-size:11px;color:#f59e0b">';
                elemHtml += 'Revit ID: ' + revitIds.join(', ');
                elemHtml += '</span>';
            } else if (elemIds.length) {
                elemHtml += '<span class="changes-fix-element" style="font-size:10px;color:var(--text-secondary)">';
                elemHtml += 'IFC: ' + elemIds.map(function(id) { return window.escHtml(id); }).join(', ');
                elemHtml += '</span>';
            }
            html +=
                '<div class="order-fix-card">' +
                    '<div class="order-fix-row">' +
                        '<div class="changes-fix-severity ' + sevClass + '">' + sevIcon + '</div>' +
                        '<div class="order-fix-body">' +
                            '<div class="changes-fix-msg">' + window.escHtml(fix.message) + '</div>' +
                            '<div class="changes-fix-meta">' +
                                '<span class="changes-fix-source">' + sourceLabel + '</span>' +
                                elemHtml +
                                (fix.rule_key ? '<span class="changes-fix-rule">' + window.escHtml(fix.rule_key) + '</span>' : '') +
                            '</div>' +
                            (fix.details ? '<div class="changes-fix-details">' + window.escHtml(fix.details) + '</div>' : '') +
                            (fix.actions && fix.actions.length ? renderFixActions(fix.actions) : '') +
                        '</div>' +
                        '<div class="order-fix-status ' + fixStatusClass + '">' + (fixStatusLabel[fix.status] || '⏳') + '</div>' +
                    '</div>' +
                    (fix.instruction ? '<div class="order-fix-instruction" style="margin-top:6px;padding:8px;background:var(--panel);border:1px solid var(--border);border-radius:4px;font-size:11px;line-height:1.5;white-space:pre-wrap">' + window.escHtml(fix.instruction) + '</div>' : '') +
                    (order.status === 'draft' ? '<div class="order-fix-buttons">' +
                        (fix.status === 'pending' ? '<button class="btn-sm" onclick="approveFixInOrder(\'' + order.id + '\',' + idx + ')">✅ Утвердить</button>' : '') +
                        (fix.status === 'pending' ? '<button class="btn-sm btn-outline" onclick="rejectFixInOrder(\'' + order.id + '\',' + idx + ')" style="color:var(--error)">❌ Отклонить</button>' : '') +
                        (fix.status !== 'rejected' && fix.status !== 'applied' ? '<button class="btn-sm" onclick="elaborateFixInOrder(\'' + order.id + '\',' + idx + ')" style="border-color:var(--accent);color:var(--accent)">💡 Продумать</button>' : '') +
                        (fix.status === 'approved' || fix.status === 'applied' ? '<span style="font-size:12px;color:var(--text-secondary)">Утверждено ✓</span>' : '') +
                        (fix.status === 'rejected' ? '<span style="font-size:12px;color:var(--text-secondary)">Отклонено</span>' : '') +
                    '</div>' : '') +
                '</div>';
        });
        html += '</div>';
    }

    // Action buttons — only for draft orders
    html += '<div class="order-detail-actions" style="margin-top:20px;display:flex;gap:8px;flex-wrap:wrap">';
    if (order.status === 'draft') {
        html += '<button class="btn btn-primary" onclick="sendAndApplyOrder(\'' + order.id + '\')">🚀 Отправить в Revit и реализовать</button>';
        html += '<button class="btn" onclick="elaborateAllInOrder(\'' + order.id + '\')" style="border-color:var(--accent);color:var(--accent)">💡 Продумать все</button>';
    }
    html += '<button class="btn btn-outline" onclick="closeModal(\'orderDetailModal\')">Закрыть</button>';
    html += '</div>';

    content.innerHTML = html;
    overlay.classList.add('active');
}

function renderFixActions(actions) {
    if (!actions || !actions.length) return '';
    var html = '<div style="margin-top:6px;padding:6px 8px;background:var(--bg);border-radius:4px;font-size:11px;font-family:monospace">';
    actions.forEach(function(a) {
        html += '<div>' + window.escHtml(a.parameter || '') + ': ' + window.escHtml(a.current_value || '') + ' → ' + window.escHtml(a.new_value || '') + '</div>';
    });
    html += '</div>';
    return html;
}

// ── Order actions ──

window.approveFixInOrder = async function(orderId, fixIndex) {
    await updateFixStatus(orderId, fixIndex, 'approved');
};

window.rejectFixInOrder = async function(orderId, fixIndex) {
    await updateFixStatus(orderId, fixIndex, 'rejected');
};

async function updateFixStatus(orderId, fixIndex, status) {
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    if (!order || !order.fixes[fixIndex]) return;
    order.fixes[fixIndex].status = status;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fixes: [{ id: order.fixes[fixIndex].id, status: status }]
            }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        renderOrderDetailModal(order);
        renderChangesPage();
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
}

window.sendAndApplyOrder = async function(orderId) {
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    if (!order) return;
    if (!confirm('Отправить приказ в Revit и отметить как применённый? После этого приказ станет доступен только для чтения.')) return;
    // Auto-approve all pending fixes
    var updatedFixes = [];
    (order.fixes || []).forEach(function(f) {
        if (f.status === 'pending') {
            f.status = 'approved';
            updatedFixes.push({ id: f.id, status: 'approved' });
        }
    });
    try {
        // Approve pending fixes
        if (updatedFixes.length) {
            var r1 = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fixes: updatedFixes }),
            });
            if (!r1.ok) throw new Error('HTTP ' + r1.status);
        }
        // Mark order as applied (also makes it available to for-revit endpoint)
        var r2 = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'applied' }),
        });
        if (!r2.ok) throw new Error('HTTP ' + r2.status);
        order.status = 'applied';
        // Mark all non-rejected fixes as applied
        (order.fixes || []).forEach(function(f) {
            if (f.status !== 'rejected') f.status = 'applied';
        });
        renderOrderDetailModal(order);
        renderChangesPage();
        window.showToast('Приказ отправлен в Revit и помечен как применённый', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.rollbackOrder = async function(orderId) {
    if (!confirm('Откатить приказ? Изменения будут отменены в Revit.')) return;
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    if (!order) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'rolled_back' }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        order.status = 'rolled_back';
        renderOrderDetailModal(order);
        renderChangesPage();
        window.showToast('Приказ откачен', 'success');
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Elaborate (Продумать) ──

window.elaborateFixInOrder = async function(orderId, fixIdx) {
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    if (!order || !order.fixes[fixIdx]) return;
    var fix = order.fixes[fixIdx];
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId + '/elaborate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fix_ids: [fix.id] }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();
        if (data.instructions && data.instructions[0]) {
            fix.instruction = data.instructions[0].instruction;
            fix.elaborated = true;
            renderOrderDetailModal(order);
            window.showToast('Инструкция сгенерирована', 'success');
        }
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.elaborateAllInOrder = async function(orderId) {
    var order = _changeOrders.find(function(o) { return o.id === orderId; });
    if (!order) return;
    var fixIds = (order.fixes || []).map(function(f) { return f.id; });
    if (!fixIds.length) {
        window.showToast('Нет исправлений для генерации инструкций', 'error');
        return;
    }
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/changes/' + orderId + '/elaborate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fix_ids: fixIds }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();
        if (data.instructions) {
            data.instructions.forEach(function(inst) {
                var match = (order.fixes || []).find(function(f) { return f.id === inst.fix_id; });
                if (match) {
                    match.instruction = inst.instruction;
                    match.elaborated = true;
                }
            });
            renderOrderDetailModal(order);
            window.showToast('Инструкции сгенерированы', 'success');
        }
    } catch(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Implement (now merged into sendAndApplyOrder) ──
