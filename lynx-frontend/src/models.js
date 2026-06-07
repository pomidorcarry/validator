import { loadIfcFromBuffer, initScene } from './viewer.js';

let models = [];
let elements = [];
let issues = [];
window.selectedModelId = null;
let allServerModels = [];
let bindSelectedModelId = null;
let moveModelId = null;

// ── Bind Existing Model ─────────────────────────────────────────

window.showBindModelModal = function() {
    bindSelectedModelId = null;
    document.getElementById('bindSearch').value = '';
    document.getElementById('bindModelList').innerHTML = '<div class="empty-state">Загрузка...</div>';
    window.openModal('bindModal');
    loadBindModelList();
};

async function loadBindModelList() {
    try {
        const resp = await fetch(`${window.API_BASE}/models`);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        allServerModels = data.models || [];
        renderBindModelList('');
    } catch (e) {
        document.getElementById('bindModelList').innerHTML = '<div class="empty-state">Ошибка: ' + e.message + '</div>';
    }
}

window.filterBindModels = function() {
    var q = document.getElementById('bindSearch').value.toLowerCase();
    renderBindModelList(q);
};

function renderBindModelList(query) {
    var el = document.getElementById('bindModelList');
    var currentIds = new Set(models.map(function(m) { return m.id; }));
    var filtered = allServerModels.filter(function(m) {
        if (currentIds.has(m.id)) return false;
        if (query && m.model_name.toLowerCase().indexOf(query) < 0) return false;
        return true;
    });
    if (!filtered.length) {
        el.innerHTML = '<div class="empty-state">Нет доступных моделей</div>';
        return;
    }
    el.innerHTML = filtered.map(function(m) {
        var cls = m.id === bindSelectedModelId ? ' style="background:var(--bg);border-color:var(--accent)"' : '';
        return '<label class="project-radio-item"' + cls + '>' +
            '<input type="radio" name="bindModel" value="' + m.id + '" onclick="bindSelectModel(\'' + m.id + '\')" />' +
            '<span><strong>' + window.escHtml(m.model_name) + '</strong> <span style="color:var(--text-secondary);font-size:12px">(' + window.getStatusBadge(m.status) + ')</span></span>' +
        '</label>';
    }).join('');
}

window.bindSelectModel = function(id) {
    bindSelectedModelId = id;
};

window.confirmBindModel = function() {
    var checked = document.querySelector('input[name="bindModel"]:checked');
    if (!checked) { window.showToast('Выберите модель', 'error'); return; }
    bindSelectedModelId = checked.value;
    doBindModel(bindSelectedModelId);
};

async function doBindModel(modelId) {
    try {
        const form = new URLSearchParams();
        form.set('target_project_id', window.currentProjectId);
        const resp = await fetch(`${window.API_BASE}/models/${modelId}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.closeModal('bindModal');
        window.showToast('Модель привязана к проекту', 'success');
        window.selectedModelId = null;
        loadModels(window.currentProjectId);
        window.loadProjects();
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
}

// ── Models ──────────────────────────────────────────────────────

async function loadModels(projectId) {
    const el = document.getElementById('modelList');
    el.innerHTML = '<div class="empty-state">Загрузка...</div>';

    try {
        const resp = await fetch(`${window.API_BASE}/models?project_id=${projectId}`);
        const data = await resp.json();
        models = data.models || [];
        renderModels();
        if (models.length && !window.selectedModelId) {
            selectModel(models[0].id);
        } else if (!models.length) {
            const placeholder = document.getElementById('viewerPlaceholder');
            placeholder.textContent = 'Нет моделей — загрузите IFC';
            placeholder.style.display = '';
        }
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Ошибка: ${e.message}</div>`;
    }
}
window.loadModels = loadModels;

function renderModels() {
    const el = document.getElementById('modelList');
    if (!models.length) {
        el.innerHTML = '<div class="empty-state">Нет моделей</div>';
        return;
    }
    el.innerHTML = models.map(m => [
        '<div class="model-item ' + (m.id === window.selectedModelId ? 'active' : '') + '" onclick="selectModel(\'' + m.id + '\')">',
            '<div class="model-item-info">',
                '<div class="model-item-title">' + window.escHtml(m.model_name) + ' v' + (m.version_number !== null && m.version_number !== undefined ? m.version_number : '?') + '</div>',
                '<div class="model-item-meta">',
                    '<span class="status-badge ' + m.status + '">' + window.getStatusBadge(m.status) + '</span>',
                    window.formatDate(m.created_at),
                '</div>',
            '</div>',
            '<div class="model-item-actions">',
                '<button class="model-move-btn" onclick="event.stopPropagation();showMoveModelModal(\'' + m.id + '\')" title="Переместить">↗</button>',
                '<button class="model-delete-btn" onclick="event.stopPropagation();deleteModel(\'' + m.id + '\')" title="Удалить">✕</button>',
            '</div>',
        '</div>'
    ].join('')).join('');
}

window.selectModel = async function(id) {
    window.selectedModelId = id;
    renderModels();
    const m = models.find(x => x.id === id);
    const placeholder = document.getElementById('viewerPlaceholder');

    if (m?.status === 'processed') {
        placeholder.textContent = 'Загрузка IFC...';
        placeholder.style.display = '';
        await load3D(id);
    } else {
        placeholder.textContent = `Статус: ${m?.status || '-'}`;
        placeholder.style.display = '';
    }

    if (m) {
        await loadIssues(id);
        await loadElements(id);
    }
};

async function load3D(modelId) {
    const placeholder = document.getElementById('viewerPlaceholder');
    try {
        const resp = await fetch(`${window.API_BASE}/models/${modelId}/ifc`);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const buffer = new Uint8Array(await resp.arrayBuffer());
        await loadIfcFromBuffer(buffer);
        placeholder.style.display = 'none';
    } catch (e) {
        console.error('3D error:', e);
        placeholder.textContent = 'Ошибка 3D: ' + e.message;
    }
}

// ── Upload Model ────────────────────────────────────────────────

window.showUploadModelModal = function() {
    document.getElementById('uploadModelName').value = '';
    document.getElementById('uploadFile').value = '';
    document.getElementById('uploadRulesetId').value = 'default';
    window.openModal('uploadModal');
};

window.uploadModel = async function() {
    const name = document.getElementById('uploadModelName').value.trim();
    const fileInput = document.getElementById('uploadFile');
    const rulesetId = document.getElementById('uploadRulesetId').value.trim();

    if (!name || !fileInput.files.length) {
        window.showToast('Заполните название и выберите файл', 'error');
        return;
    }

    const form = new FormData();
    form.set('project_id', window.currentProjectId);
    form.set('model_name', name);
    form.set('ruleset_id', rulesetId);
    form.set('file', fileInput.files[0]);

    try {
        const resp = await fetch(`${window.API_BASE}/models/upload`, { method: 'POST', body: form });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.closeModal('uploadModal');
        window.showToast('Модель загружена, начата обработка', 'success');
        loadModels(window.currentProjectId);
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Move Model ──────────────────────────────────────────────────

window.showMoveModelModal = function(modelId) {
    moveModelId = modelId;
    const el = document.getElementById('moveProjectList');
    var items = window.projects.filter(function(p) { return p.id !== window.currentProjectId; }).map(function(p) {
        return '<label class="project-radio-item">' +
            '<input type="radio" name="targetProject" value="' + p.id + '" />' +
            '<span>' + window.escHtml(p.name) + ' (' + window.escHtml(p.code) + ')</span>' +
        '</label>';
    }).join('');
    el.innerHTML = items || '<div class="empty-state">Нет других проектов</div>';
    window.openModal('moveModal');
};

window.confirmMoveModel = async function() {
    const checked = document.querySelector('input[name="targetProject"]:checked');
    if (!checked) { window.showToast('Выберите проект', 'error'); return; }
    const targetId = checked.value;
    try {
        const form = new URLSearchParams();
        form.set('target_project_id', targetId);
        const resp = await fetch(`${window.API_BASE}/models/${moveModelId}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.closeModal('moveModal');
        window.showToast('Модель перемещена', 'success');
        window.selectedModelId = null;
        if (window.currentProjectId) {
            loadModels(window.currentProjectId);
        }
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Delete Model ────────────────────────────────────────────────

window.deleteModel = async function(modelId) {
    if (!confirm('Удалить модель?')) return;
    try {
        const resp = await fetch(`${window.API_BASE}/models/${modelId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Модель удалена', 'success');
        if (window.selectedModelId === modelId) window.selectedModelId = null;
        loadModels(window.currentProjectId);
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Issues & Elements ───────────────────────────────────────────

async function loadIssues(modelId) {
    try {
        const resp = await fetch(`${window.API_BASE}/models/${modelId}/issues`);
        const data = await resp.json();
        issues = data.issues || [];
        renderIssues();
    } catch (e) {
        document.getElementById('issuesList').innerHTML = '<div class="empty-state">Ошибка</div>';
    }
}

function renderIssues() {
    const el = document.getElementById('issuesList');
    if (!issues.length) { el.innerHTML = '<div class="empty-state">Нет ошибок</div>'; return; }

    var groups = {};
    for (var i = 0; i < issues.length; i++) {
        var key = issues[i].rule_key + '|||' + issues[i].message;
        if (!groups[key]) groups[key] = { rule_key: issues[i].rule_key, message: issues[i].message, severity: issues[i].severity, items: [] };
        groups[key].items.push(issues[i]);
    }

    el.innerHTML = Object.keys(groups).map(function(key) {
        var g = groups[key];
        var groupId = 'ig_' + key.replace(/[^a-z0-9_]/gi, '_');
        var count = g.items.length;
        var firstItem = g.items[0];
        return '<div class="issue-group">' +
            '<div class="issue-group-header" onclick="toggleIssueGroup(\'' + groupId + '\')">' +
                '<span class="issue-group-toggle">▶</span>' +
                '<span class="issue-badge ' + g.severity + '">' + g.severity + '</span>' +
                '<span class="issue-key">' + window.escHtml(g.rule_key) + '</span>' +
                '<span class="issue-group-count">' + count + '</span>' +
            '</div>' +
            '<div class="issue-group-items" id="' + groupId + '">' +
                g.items.map(function(item) {
                    return '<div class="issue-item ' + item.severity + '" onclick="showInspector(\'' + item.global_id + '\')">' +
                        '<div class="issue-message">' + window.escHtml(item.message) + '</div>' +
                        '<div class="issue-element-id">' + window.escHtml(item.global_id || '') + '</div>' +
                    '</div>';
                }).join('') +
            '</div>' +
        '</div>';
    }).join('');
}

window.toggleIssueGroup = function(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('collapsed');
    var toggle = el.previousElementSibling.querySelector('.issue-group-toggle');
    if (toggle) toggle.textContent = el.classList.contains('collapsed') ? '▶' : '▼';
};

async function loadElements(modelId) {
    try {
        const resp = await fetch(`${window.API_BASE}/models/${modelId}/elements`);
        const data = await resp.json();
        elements = data.elements || [];
    } catch (e) {
        elements = [];
    }
}

window.showInspector = function(globalId) {
    const el = elements.find(x => x.global_id === globalId);
    if (!el) return;
    document.getElementById('inspector').innerHTML =
        Object.entries({
            'Global ID': el.global_id,
            'Класс IFC': el.ifc_class,
            'Имя': el.name || '-',
            'Этаж': el.storey_name || '-',
            'Система': el.system_name || '-',
        }).map(([k, v]) =>
            `<div class="inspector-row"><span class="inspector-label">${k}</span><span class="inspector-value">${v}</span></div>`
        ).join('');
};
