import { loadIfcFromBuffer, initScene } from './viewer.js';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

let projects = [];
let models = [];
let elements = [];
let issues = [];
let currentProjectId = null;
let selectedModelId = null;
let editingProjectId = null;
let moveModelId = null;

// ── Navigation ──────────────────────────────────────────────────

function showHome() {
    document.getElementById('homeView').classList.add('active');
    document.getElementById('projectView').classList.remove('active');
    document.getElementById('tzView').classList.remove('active');
    document.getElementById('dataView').classList.remove('active');
    document.getElementById('breadcrumb').innerHTML = '<span class="link" onclick="goHome()">Проекты</span>';
    document.getElementById('projectQuickSelect').style.display = 'none';
    document.getElementById('btnNewProject').style.display = '';
    loadProjects();
}

function showProject(projectId) {
    currentProjectId = projectId;
    document.getElementById('homeView').classList.remove('active');
    document.getElementById('projectView').classList.add('active');
    
    const p = projects.find(x => x.id === projectId);
    document.getElementById('breadcrumb').innerHTML = `
        <span class="link" onclick="goHome()">Проекты</span>
        <span>/</span>
        <span class="current">${p ? p.name : '...'}</span>
    `;
    
    const qs = document.getElementById('projectQuickSelect');
    qs.style.display = '';
    qs.value = projectId;
    
    document.getElementById('btnNewProject').style.display = 'none';
    
    loadProjectDetail(projectId);
    loadModels(projectId);
}

window.showProject = showProject;
window.goHome = function() {
    currentProjectId = null;
    selectedModelId = null;
    showHome();
};

window.onQuickSelectProject = function(value) {
    if (value) showProject(value);
};

// ── Projects ────────────────────────────────────────────────────

async function loadProjects() {
    const el = document.getElementById('projectList');
    el.innerHTML = '<div class="empty-state">Загрузка...</div>';
    
    try {
        const resp = await fetch(`${API_BASE}/projects`);
        const data = await resp.json();
        projects = data.projects || [];
        renderProjects();
        renderQuickSelect();
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Ошибка: ${e.message}</div>`;
    }
}

function renderProjects() {
    const el = document.getElementById('projectList');
    if (!projects.length) {
        el.innerHTML = `
            <div class="empty-state">
                <div class="big">📁</div>
                <p>Нет проектов</p>
                <p style="margin-top:8px;font-size:13px">Создайте первый проект</p>
            </div>
        `;
        return;
    }
    el.innerHTML = projects.map(function(p) { return [
        '<div class="project-card" onclick="showProject(\'' + p.id + '\')">',
            '<div class="project-card-title">' + escHtml(p.name) + '</div>',
            '<div class="project-card-code">' + escHtml(p.code) + '</div>',
            '<div class="project-card-meta">',
                '<span>📦 ' + (p.models_count ?? 0) + ' моделей</span>',
                '<span>📅 ' + formatDate(p.created_at) + '</span>',
            '</div>',
        '</div>'
    ].join(''); }).join('');
}

function renderQuickSelect() {
    const qs = document.getElementById('projectQuickSelect');
    qs.innerHTML = '<option value="">— Быстрый переход —</option>' +
        projects.map(function(p) {
            return '<option value="' + p.id + '"' + (p.id === currentProjectId ? ' selected' : '') + '>' + escHtml(p.name) + '</option>';
        }).join('');
}

async function loadProjectDetail(projectId) {
    try {
        const resp = await fetch(`${API_BASE}/projects/${projectId}`);
        const p = await resp.json();
        const tz = p.technical_specification || '';
        document.getElementById('tzContent').textContent = tz || 'Техническое задание не задано';
        document.getElementById('tzContent').classList.toggle('empty', !tz);
        const kw = p.auto_bind_keywords || '';
        document.getElementById('keywordsContent').textContent = kw || 'не заданы';
    } catch (e) {
        document.getElementById('tzContent').textContent = 'Ошибка загрузки';
    }
}

// ── Project CRUD ────────────────────────────────────────────────

window.showCreateProjectModal = function() {
    editingProjectId = null;
    document.getElementById('projectModalTitle').textContent = 'Новый проект';
    document.getElementById('projectCode').value = '';
    document.getElementById('projectName').value = '';
    document.getElementById('projectTz').value = '';
    document.getElementById('projectKeywords').value = '';
    document.getElementById('projectSaveBtn').textContent = 'Создать';
    openModal('projectModal');
};

window.showEditProjectModal = function(id) {
    const p = projects.find(x => x.id === id);
    if (!p) return;
    editingProjectId = id;
    document.getElementById('projectModalTitle').textContent = 'Редактировать проект';
    document.getElementById('projectCode').value = p.code;
    document.getElementById('projectName').value = p.name;
    document.getElementById('projectTz').value = p.technical_specification || '';
    document.getElementById('projectKeywords').value = p.auto_bind_keywords || '';
    document.getElementById('projectSaveBtn').textContent = 'Сохранить';
    openModal('projectModal');
};

window.saveProject = async function() {
    const code = document.getElementById('projectCode').value.trim();
    const name = document.getElementById('projectName').value.trim();
    const tz = document.getElementById('projectTz').value.trim();
    const kw = document.getElementById('projectKeywords').value.trim();
    if (!code || !name) { showToast('Заполните код и название', 'error'); return; }

    try {
        if (editingProjectId) {
            const form = new URLSearchParams();
            form.set('name', name);
            form.set('technical_specification', tz);
            form.set('auto_bind_keywords', kw);
            const resp = await fetch(`${API_BASE}/projects/${editingProjectId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: form,
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
        } else {
            const form = new URLSearchParams();
            form.set('code', code);
            form.set('name', name);
            form.set('technical_specification', tz);
            form.set('auto_bind_keywords', kw);
            const resp = await fetch(`${API_BASE}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: form,
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
        }
        closeModal('projectModal');
        showToast('Проект сохранён', 'success');
        loadProjects();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

window.deleteProject = async function(id) {
    if (!confirm('Удалить проект и все его модели?')) return;
    try {
        const resp = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        showToast('Проект удалён', 'success');
        if (currentProjectId === id) goHome();
        else loadProjects();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── TZ Editing ──────────────────────────────────────────────────

window.showEditTzModal = function() {
    const tz = document.getElementById('tzContent').textContent;
    document.getElementById('tzEditor').value = tz === 'Техническое задание не задано' ? '' : tz;
    openModal('tzModal');
};

window.saveTz = async function() {
    const tz = document.getElementById('tzEditor').value;
    try {
        const form = new URLSearchParams();
        form.set('technical_specification', tz);
        const resp = await fetch(`${API_BASE}/projects/${currentProjectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        closeModal('tzModal');
        showToast('ТЗ сохранено', 'success');
        loadProjectDetail(currentProjectId);
        if (document.getElementById('tzView').classList.contains('active')) {
            loadTzPage();
        }
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Keywords ────────────────────────────────────────────────────

window.showEditKeywordsModal = function() {
    const el = document.getElementById('keywordsContent');
    document.getElementById('keywordsEditor').value = el.textContent === 'не заданы' ? '' : el.textContent;
    openModal('keywordsModal');
};

window.saveKeywords = async function() {
    const kw = document.getElementById('keywordsEditor').value.trim();
    try {
        const form = new URLSearchParams();
        form.set('auto_bind_keywords', kw);
        const resp = await fetch(`${API_BASE}/projects/${currentProjectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        closeModal('keywordsModal');
        showToast('Ключи сохранены', 'success');
        loadProjectDetail(currentProjectId);
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Bind Existing Model ─────────────────────────────────────────

var allServerModels = [];
var bindSelectedModelId = null;

window.showBindModelModal = function() {
    bindSelectedModelId = null;
    document.getElementById('bindSearch').value = '';
    document.getElementById('bindModelList').innerHTML = '<div class="empty-state">Загрузка...</div>';
    openModal('bindModal');
    loadBindModelList();
};

async function loadBindModelList() {
    try {
        const resp = await fetch(`${API_BASE}/models`);
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
            '<span><strong>' + escHtml(m.model_name) + '</strong> <span style="color:var(--text-secondary);font-size:12px">(' + getStatusBadge(m.status) + ')</span></span>' +
        '</label>';
    }).join('');
}

window.bindSelectModel = function(id) {
    bindSelectedModelId = id;
};

window.confirmBindModel = function() {
    var checked = document.querySelector('input[name="bindModel"]:checked');
    if (!checked) { showToast('Выберите модель', 'error'); return; }
    bindSelectedModelId = checked.value;
    doBindModel(bindSelectedModelId);
};

async function doBindModel(modelId) {
    try {
        const form = new URLSearchParams();
        form.set('target_project_id', currentProjectId);
        const resp = await fetch(`${API_BASE}/models/${modelId}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        closeModal('bindModal');
        showToast('Модель привязана к проекту', 'success');
        selectedModelId = null;
        loadModels(currentProjectId);
        loadProjects();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
}

// ── Models ──────────────────────────────────────────────────────

async function loadModels(projectId) {
    const el = document.getElementById('modelList');
    el.innerHTML = '<div class="empty-state">Загрузка...</div>';
    
    try {
        const resp = await fetch(`${API_BASE}/models?project_id=${projectId}`);
        const data = await resp.json();
        models = data.models || [];
        renderModels();
        if (models.length && !selectedModelId) {
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

function renderModels() {
    const el = document.getElementById('modelList');
    if (!models.length) {
        el.innerHTML = '<div class="empty-state">Нет моделей</div>';
        return;
    }
    el.innerHTML = models.map(m => [
        '<div class="model-item ' + (m.id === selectedModelId ? 'active' : '') + '" onclick="selectModel(\'' + m.id + '\')">',
            '<div class="model-item-info">',
                '<div class="model-item-title">' + escHtml(m.model_name) + ' v' + (m.version_number !== null && m.version_number !== undefined ? m.version_number : '?') + '</div>',
                '<div class="model-item-meta">',
                    '<span class="status-badge ' + m.status + '">' + getStatusBadge(m.status) + '</span>',
                    formatDate(m.created_at),
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
    selectedModelId = id;
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
        const resp = await fetch(`${API_BASE}/models/${modelId}/ifc`);
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
    openModal('uploadModal');
};

window.uploadModel = async function() {
    const name = document.getElementById('uploadModelName').value.trim();
    const fileInput = document.getElementById('uploadFile');
    const rulesetId = document.getElementById('uploadRulesetId').value.trim();
    
    if (!name || !fileInput.files.length) {
        showToast('Заполните название и выберите файл', 'error');
        return;
    }
    
    const form = new FormData();
    form.set('project_id', currentProjectId);
    form.set('model_name', name);
    form.set('ruleset_id', rulesetId);
    form.set('file', fileInput.files[0]);
    
    try {
        const resp = await fetch(`${API_BASE}/models/upload`, { method: 'POST', body: form });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        closeModal('uploadModal');
        showToast('Модель загружена, начата обработка', 'success');
        loadModels(currentProjectId);
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Move Model ──────────────────────────────────────────────────

window.showMoveModelModal = function(modelId) {
    moveModelId = modelId;
    const el = document.getElementById('moveProjectList');
    var items = projects.filter(function(p) { return p.id !== currentProjectId; }).map(function(p) {
        return '<label class="project-radio-item">' +
            '<input type="radio" name="targetProject" value="' + p.id + '" />' +
            '<span>' + escHtml(p.name) + ' (' + escHtml(p.code) + ')</span>' +
        '</label>';
    }).join('');
    el.innerHTML = items || '<div class="empty-state">Нет других проектов</div>';
    openModal('moveModal');
};

window.confirmMoveModel = async function() {
    const checked = document.querySelector('input[name="targetProject"]:checked');
    if (!checked) { showToast('Выберите проект', 'error'); return; }
    const targetId = checked.value;
    try {
        const form = new URLSearchParams();
        form.set('target_project_id', targetId);
        const resp = await fetch(`${API_BASE}/models/${moveModelId}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        closeModal('moveModal');
        showToast('Модель перемещена', 'success');
        selectedModelId = null;
        if (currentProjectId) {
            loadModels(currentProjectId);
        }
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Delete Model ────────────────────────────────────────────────

window.deleteModel = async function(modelId) {
    if (!confirm('Удалить модель?')) return;
    try {
        const resp = await fetch(`${API_BASE}/models/${modelId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        showToast('Модель удалена', 'success');
        if (selectedModelId === modelId) selectedModelId = null;
        loadModels(currentProjectId);
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Issues & Elements ───────────────────────────────────────────

async function loadIssues(modelId) {
    try {
        const resp = await fetch(`${API_BASE}/models/${modelId}/issues`);
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
                '<span class="issue-key">' + escHtml(g.rule_key) + '</span>' +
                '<span class="issue-group-count">' + count + '</span>' +
            '</div>' +
            '<div class="issue-group-items" id="' + groupId + '">' +
                g.items.map(function(item) {
                    return '<div class="issue-item ' + item.severity + '" onclick="showInspector(\'' + item.global_id + '\')">' +
                        '<div class="issue-message">' + escHtml(item.message) + '</div>' +
                        '<div class="issue-element-id">' + escHtml(item.global_id || '') + '</div>' +
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
        const resp = await fetch(`${API_BASE}/models/${modelId}/elements`);
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

// ── Utils ───────────────────────────────────────────────────────

function escHtml(s) {
    if (s === null || s === undefined) return '';
    if (typeof s === 'object') {
        try { s = JSON.stringify(s, null, 2); } catch(e) { s = String(s); }
    } else {
        s = String(s);
    }
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(s) {
    try { return new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }); }
    catch { return '-'; }
}

function getStatusBadge(s) {
    const map = { processed: '✓ Готово', queued: '⏳ В очереди', failed: '✗ Ошибка', uploaded: '📤 Загружен' };
    return map[s] || s;
}

function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

window.closeModal = closeModal;

let toastTimer = null;
function showToast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show ' + (type || '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = 'toast'; }, 3000);
}

// ── TZ / Elements Page ──────────────────────────────────────────

var CATEGORIES = [];
var CATEGORY_ICONS = {};

var categoryColors = ['#3b82f6','#06b6d4','#8b5cf6','#ec4899','#f59e0b','#10b981','#14b8a6','#f97316','#ef4444','#6b7280'];

function buildCategoryIcons(list) {
    var icons = {};
    for (var i = 0; i < list.length; i++) {
        var name = list[i];
        var c = categoryColors[i % categoryColors.length];
        icons[name] = { color: c, icon: '' };
    }
    return icons;
}

// Category-specific column configs: which IFC properties to show per category
var __CATEGORY_COLUMNS = [];

var DEFAULT_CATEGORY_COLUMNS = {
    'Труба металлическая': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'PipeType'], group: 'structural' },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },
        { label: 'Толщина стенки', keys: ['Толщина стенки', 'WallThickness'], group: 'structural' },
        { label: 'Длина, мм', keys: ['Длина', 'Length'], group: 'structural' },
    ],
    'Труба полимерная': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'PipeType'], group: 'structural' },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },
        { label: 'Толщина стенки', keys: ['Толщина стенки', 'WallThickness'], group: 'structural' },
        { label: 'Длина, мм', keys: ['Длина', 'Length'], group: 'structural' },
    ],
    'Металлическая соединительная деталь трубы': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type'], group: 'structural' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'FittingType', 'ValveType'], group: 'structural' },
        { label: 'Размер', keys: ['BRU_Габарит элемента', 'Bru_Габарит элемента', 'Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },

    ],
    'Полимерная соединительная деталь трубы': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type'], group: 'structural' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'FittingType', 'ValveType'], group: 'structural' },
        { label: 'Размер', keys: ['BRU_Габарит элемента', 'Bru_Габарит элемента', 'Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },

    ],
    'Арматура труб': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type'], group: 'structural' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'ValveType'], group: 'structural' },
        { label: 'Размер', keys: ['BRU_Габарит элемента', 'Bru_Габарит элемента', 'Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },

    ],
    'Арматура': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type'], group: 'structural' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'ValveType'], group: 'structural' },
        { label: 'Размер', keys: ['BRU_Габарит элемента', 'Bru_Габарит элемента', 'Размер', 'Size', 'DN', 'NominalDiameter'], group: 'structural' },

    ],
    'Оборудование': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'EquipmentType', 'Type'], group: 'structural' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type'], group: 'structural' },
        { label: 'Размер', keys: ['BRU_Габарит элемента', 'Bru_Габарит элемента', 'Размер', 'Size', 'DN'], group: 'structural' },
    ],
    'Сантехнический прибор': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Вид', keys: ['BRU_Вид', 'Bru_Вид', 'Вид', 'Type', 'FixtureType'], group: 'structural' },
    ],
    'Изоляция рулонная': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Толщина', keys: ['Толщина', 'Thickness'], group: 'structural' },

        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type', 'InsulationType'], group: 'structural' },
    ],
    'Изоляция трубчатая': [
        { label: 'Секция', keys: ['ADSK_Номер секции', 'Секция', 'Section'], group: 'position' },
        { label: 'Часть системы', keys: ['BRU_ЧастьСистемы'], group: 'position' },
        { label: 'Система', keys: ['BRU_Система'], group: 'position' },
        { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'], group: 'position' },
        { label: 'CUBE_Сокращение', keys: ['CUBE_Сокращение для системы', 'Сокращение для системы'], group: 'position' },
        { label: 'Толщина', keys: ['Толщина', 'Thickness'], group: 'structural' },

        { label: 'Тип', keys: ['BRU_Тип', 'Bru_Тип', 'Тип', 'Type', 'InsulationType'], group: 'structural' },
    ],
};

function getDefaultCols(catName) {
    return DEFAULT_CATEGORY_COLUMNS[catName] || [];
}

function getColsForCategory(cat) {
    for (var i = 0; i < __CATEGORY_COLUMNS.length; i++) {
        if (__CATEGORY_COLUMNS[i].cat === cat) return __CATEGORY_COLUMNS[i].cols;
    }
    return [];
}

function extractProp(rawPsets, keys) {
    if (!rawPsets || typeof rawPsets !== 'object') return null;
    // Try each key across ALL psets first (priority by key order)
    for (var ki = 0; ki < keys.length; ki++) {
        var key = keys[ki];
        for (var psetName in rawPsets) {
            var props = rawPsets[psetName];
            if (!props || typeof props !== 'object') continue;
            var val = props[key];
            if (val !== undefined && val !== null && String(val).trim() !== '') {
                return val;
            }
        }
    }
    return null;
}

function formatValue(val) {
    if (val === null || val === undefined) return null;
    var s = String(val).trim();
    if (!s) return null;
    var num = parseFloat(s.replace(',', '.'));
    if (!isNaN(num)) {
        return num.toFixed(2);
    }
    return s;
}

async function loadCategories() {
    if (!currentProjectId) return [];
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/categories');
        var data = await resp.json();
        var list = data.categories.map(function(c) { return c.name; });
        CATEGORIES = list;
        CATEGORY_ICONS = buildCategoryIcons(list);
        __CATEGORY_COLUMNS = data.categories.map(function(c) {
            return { cat: c.name, cols: (c.columns && c.columns.length) ? c.columns : getDefaultCols(c.name) };
        });
        return list;
    } catch(e) {
        return CATEGORIES.length ? CATEGORIES : ['Невалидируемое семейство'];
    }
}

var tzAllElements = [];
var tzActiveCategory = '';
var tzSearchQuery = '';

window.showTzPage = function() {
    if (!currentProjectId) return;
    document.getElementById('homeView').classList.remove('active');
    document.getElementById('projectView').classList.remove('active');
    document.getElementById('tzView').classList.add('active');
    document.getElementById('dataView').classList.remove('active');
    document.getElementById('breadcrumb').innerHTML = [
        '<span class="link" onclick="goHome()">Проекты</span>',
        '<span>/</span>',
        '<span class="link" onclick="showProject(\'' + currentProjectId + '\')">' + escHtml(getProjectName(currentProjectId)) + '</span>',
        '<span>/</span>',
        '<span class="current">Заполнение элементов модели</span>'
    ].join('');
    document.getElementById('projectQuickSelect').style.display = 'none';
    document.getElementById('btnNewProject').style.display = 'none';
    loadTzPage();
};

window.goToProject = function() {
    document.getElementById('tzView').classList.remove('active');
    document.getElementById('dataView').classList.remove('active');
    showProject(currentProjectId);
};

function getProjectName(id) {
    var p = projects.find(function(x) { return x.id === id; });
    return p ? p.name : '...';
}

async function loadTzPage() {
    await loadCategories();
    try {
        var pResp = await fetch(API_BASE + '/projects/' + currentProjectId);
        var p = await pResp.json();
        document.getElementById('tzMetaCode').textContent = p.code || '-';
        document.getElementById('tzMetaModels').textContent = p.models_count || '0';
        document.getElementById('tzMetaKeywords').textContent = p.auto_bind_keywords || '-';
    } catch (e) {
        // fallback
    }
    loadTzElements();
}

function categorizeElement(el) {
    var group = (el.model_group || '').trim().toLowerCase();
    for (var i = 0; i < CATEGORIES.length; i++) {
        if (group.indexOf(CATEGORIES[i].toLowerCase()) >= 0) {
            return CATEGORIES[i];
        }
    }
    return 'Невалидируемое семейство';
}

var tzSelectedModelId = '';

async function loadTzElements() {
    document.getElementById('tzPageTitle').textContent = 'Элементы';
    document.getElementById('tzPageMeta').textContent = 'Загрузка...';
    document.getElementById('tzModelSelector').disabled = true;

    var allCatElems = {};
    for (var i = 0; i < CATEGORIES.length; i++) {
        allCatElems[CATEGORIES[i]] = [];
    }

    var allIfcClasses = {};
    var totalCount = 0;

    try {
        var mResp = await fetch(API_BASE + '/models?project_id=' + currentProjectId);
        var mData = await mResp.json();
        var projectModels = mData.models || [];
        document.getElementById('tzModelCount').textContent = projectModels.length;

        // Populate model selector
        var sel = document.getElementById('tzModelSelector');
        var prevVal = tzSelectedModelId || (selectedModelId ? selectedModelId : '');
        sel.innerHTML = '<option value="">— Все модели —</option>' +
            projectModels.map(function(m) {
                var label = escHtml(m.model_name) + ' v' + (m.version_number !== null && m.version_number !== undefined ? m.version_number : '?');
                return '<option value="' + m.id + '">' + label + '</option>';
            }).join('');
        sel.value = prevVal;
        if (!sel.value) {
            // Auto-select first processed model if none selected
            var first = projectModels.find(function(m) { return m.status === 'processed'; });
            if (first) { sel.value = first.id; tzSelectedModelId = first.id; }
        } else {
            tzSelectedModelId = prevVal;
        }

        // Determine which models to load
        var modelsToLoad = [];
        if (tzSelectedModelId) {
            var found = projectModels.find(function(m) { return m.id === tzSelectedModelId; });
            if (found) modelsToLoad = [found];
        } else {
            modelsToLoad = projectModels;
        }

        for (var i = 0; i < modelsToLoad.length; i++) {
            var m = modelsToLoad[i];
            if (m.status !== 'processed') continue;
            try {
                var eResp = await fetch(API_BASE + '/models/' + m.id + '/elements');
                var eData = await eResp.json();
                var elems = eData.elements || [];
                for (var j = 0; j < elems.length; j++) {
                    var el = elems[j];
                    el._modelName = m.model_name;
                    el._modelVersion = m.version_number;
                    var cat = categorizeElement(el);
                    if (allCatElems[cat]) {
                        allCatElems[cat].push(el);
                    } else {
                        allCatElems['Невалидируемое семейство'].push(el);
                    }
                    allIfcClasses[el.ifc_class || 'Unknown'] = (allIfcClasses[el.ifc_class || 'Unknown'] || 0) + 1;
                    totalCount++;
                }
            } catch(e) {}
        }
    } catch(e) {
        document.getElementById('tzTable').innerHTML = '<div class="empty-message">Ошибка загрузки: ' + e.message + '</div>';
        document.getElementById('tzModelSelector').disabled = false;
        return;
    }

    // Flatten by category order
    tzAllElements = [];
    for (var i = 0; i < CATEGORIES.length; i++) {
        tzAllElements = tzAllElements.concat(allCatElems[CATEGORIES[i]]);
    }

    var ifcClassNames = Object.keys(allIfcClasses).sort();
    document.getElementById('tzCount').textContent = totalCount;
    document.getElementById('tzClassCount').textContent = ifcClassNames.length;
    var modelLabel = tzSelectedModelId ? '' : 'всех моделей — ';
    document.getElementById('tzPageMeta').textContent = 'Элементов: ' + totalCount + ' · Классов IFC: ' + ifcClassNames.length;
    document.getElementById('tzModelSelector').disabled = false;

    renderTzSections(allCatElems);
    renderTzClassFilter(ifcClassNames);
    tzRenderTable();
}

window.onTzModelChange = function(modelId) {
    tzSelectedModelId = modelId || '';
    tzActiveCategory = '';
    tzSearchQuery = '';
    document.getElementById('tzSearchInput').value = '';
    loadTzElements();
};

function renderTzSections(allCatElems) {
    // Sidebar sections
    var el = document.getElementById('tzSectionList');
    var html = '<div class="tz-section-link" onclick="tzSetCategory(\'\')"><span class="dot green"></span> Все (' + tzAllElements.length + ')</div>';
    for (var i = 0; i < CATEGORIES.length; i++) {
        var cat = CATEGORIES[i];
        var cnt = allCatElems[cat] ? allCatElems[cat].length : 0;
        var dotClass = cnt > 20 ? 'green' : (cnt > 0 ? 'yellow' : 'gray');
        html += '<div class="tz-section-link" onclick="tzSetCategory(\'' + cat + '\')"><span class="dot ' + dotClass + '"></span> ' + cat + ' (' + cnt + ')</div>';
    }
    el.innerHTML = html;
}

function renderTzClassFilter(ifcClassNames) {
    var el = document.getElementById('tzClassFilter');
    var html = '<span style="font-size:11px;color:var(--text-secondary);margin-right:8px;padding-top:4px">Фильтр по IFC:</span>';
    html += '<span class="tz-class-chip' + (tzActiveCategory === '' ? ' active' : '') + '" onclick="tzSetCategory(\'\')">Все <span class="count">' + tzAllElements.length + '</span></span>';
    var filteredList = tzAllElements;
    if (tzActiveCategory && CATEGORIES.indexOf(tzActiveCategory) >= 0) {
        filteredList = tzAllElements.filter(function(e) { return categorizeElement(e) === tzActiveCategory; });
    }
    var classCounts = {};
    for (var i = 0; i < filteredList.length; i++) {
        var cls = filteredList[i].ifc_class || 'Unknown';
        classCounts[cls] = (classCounts[cls] || 0) + 1;
    }
    var names = Object.keys(classCounts).sort();
    for (var i = 0; i < names.length; i++) {
        var active = names[i] === tzActiveCategory ? ' active' : '';
        html += '<span class="tz-class-chip' + active + '" onclick="tzSetCategory(\'' + names[i] + '\')">' + names[i] + ' <span class="count">' + classCounts[names[i]] + '</span></span>';
    }
    el.innerHTML = html;
}

window.tzSetCategory = function(cat) {
    tzActiveCategory = cat;
    var chips = document.querySelectorAll('.tz-class-chip');
    for (var i = 0; i < chips.length; i++) chips[i].classList.remove('active');
    var links = document.querySelectorAll('.tz-section-link');
    for (var i = 0; i < links.length; i++) links[i].classList.remove('active');
    if (cat && CATEGORIES.indexOf(cat) >= 0) {
        var target = Array.from(document.querySelectorAll('.tz-section-link')).find(function(l) {
            return l.textContent.indexOf(cat) >= 0;
        });
        if (target) target.classList.add('active');
    }
    renderTzClassFilter([]);
    tzRenderTable();
};

window.tzFilterElements = function() {
    tzSearchQuery = document.getElementById('tzSearchInput').value.toLowerCase();
    tzRenderTable();
};

function tzRenderTable() {
    var filtered = tzAllElements;

    if (tzActiveCategory) {
        filtered = filtered.filter(function(e) {
            var cat = categorizeElement(e);
            return cat === tzActiveCategory || e.ifc_class === tzActiveCategory;
        });
    }

    if (tzSearchQuery) {
        filtered = filtered.filter(function(e) {
            var name = (e.name || '').toLowerCase();
            var cls = (e.ifc_class || '').toLowerCase();
            var storey = (e.storey_name || '').toLowerCase();
            var system = (e.system_name || '').toLowerCase();
            var cat = categorizeElement(e).toLowerCase();
            // Also search through raw_psets values
            var psetsStr = JSON.stringify(e.raw_psets_jsonb || {}).toLowerCase();
            return name.indexOf(tzSearchQuery) >= 0 || cls.indexOf(tzSearchQuery) >= 0 ||
                storey.indexOf(tzSearchQuery) >= 0 || system.indexOf(tzSearchQuery) >= 0 ||
                cat.indexOf(tzSearchQuery) >= 0 || psetsStr.indexOf(tzSearchQuery) >= 0;
        });
    }

    // Determine columns based on active category
    var activeCatCols = tzActiveCategory && CATEGORIES.indexOf(tzActiveCategory) >= 0
        ? getColsForCategory(tzActiveCategory) : [];
    // When "Все", show a default set
    if (!tzActiveCategory) {
        activeCatCols = [
            { label: 'Часть системы', keys: ['BRU_ЧастьСистемы', 'Bru_ЧастьСистемы', 'Часть системы', 'SystemPart'] },
            { label: 'Система', keys: ['BRU_Система', 'Bru_Система', 'Система', 'System'] },
            { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'] },
        ];
    }

    var container = document.getElementById('tzTable');

    if (!filtered.length) {
        container.innerHTML = '<div class="empty-message">Нет элементов</div>';
        document.getElementById('tzCount').textContent = '0';
        return;
    }

    var cols = tzActiveCategory && CATEGORIES.indexOf(tzActiveCategory) >= 0
        ? getColsForCategory(tzActiveCategory) : [
            { label: 'Часть системы', keys: ['BRU_ЧастьСистемы', 'Bru_ЧастьСистемы', 'Часть системы', 'SystemPart'] },
            { label: 'Система', keys: ['BRU_Система', 'Bru_Система', 'Система', 'System'] },
            { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'] },
        ];

    container.innerHTML = filtered.map(function(e) {
        var cat = categorizeElement(e);
        var c = CATEGORY_ICONS[cat] || { color: '#6b7280', icon: '?' };
        var propsHtml = cols.map(function(col) {
            var val;
            if (col.composite) {
                var parts = [];
                for (var si = 0; si < col.composite.length; si++) {
                    for (var di = 0; di < cols.length; di++) {
                        if (cols[di].label === col.composite[si]) {
                            var srcVal = extractProp(e.raw_psets_jsonb, cols[di].keys);
                            if (srcVal !== null && srcVal !== undefined) parts.push(String(srcVal).trim());
                            break;
                        }
                    }
                }
                val = parts.length ? parts.join(' ') : null;
            } else {
                val = extractProp(e.raw_psets_jsonb, col.keys);
            }
            var displayVal = formatValue(val);
            var emptyCls = displayVal ? '' : ' empty';
            return '<div class="tz-card-prop"><span class="tz-card-prop-key">' + escHtml(col.label) + ':</span><span class="tz-card-prop-val' + emptyCls + '">' + escHtml(displayVal || '\u2014') + '</span></div>';
        }).join('');
        return '<div class="tz-card" onclick="tzSelectElement(\'' + escHtml(e.global_id) + '\')">' +
            '<div class="tz-card-header">' +
                '<span class="class-icon" style="border-color:' + c.color + ';background:' + c.color + '"></span>' +
                '<span class="tz-card-name">' + escHtml(e.name || '(без имени)') + '</span>' +
                '<span class="tz-card-cat">' + escHtml(cat) + '</span>' +
            '</div>' +
            '<div class="tz-card-props">' + propsHtml + '</div>' +
        '</div>';
    }).join('');

    document.getElementById('tzCount').textContent = filtered.length;
}

window.tzSelectElement = function(globalId) {
    goToProject();
};

// ── Data Page (Данные о проекте и обработка ТЗ) ────────────────

var dataCategories = [];

window.showDataPage = function() {
    if (!currentProjectId) return;
    document.getElementById('homeView').classList.remove('active');
    document.getElementById('projectView').classList.remove('active');
    document.getElementById('tzView').classList.remove('active');
    document.getElementById('dataView').classList.add('active');
    document.getElementById('breadcrumb').innerHTML = [
        '<span class="link" onclick="goHome()">Проекты</span>',
        '<span>/</span>',
        '<span class="link" onclick="showProject(\'' + currentProjectId + '\')">' + escHtml(getProjectName(currentProjectId)) + '</span>',
        '<span>/</span>',
        '<span class="current">Данные о проекте и обработка ТЗ</span>'
    ].join('');
    document.getElementById('projectQuickSelect').style.display = 'none';
    document.getElementById('btnNewProject').style.display = 'none';
    loadDataPage();
};

async function loadDataPage() {
    try {
        var pResp = await fetch(API_BASE + '/projects/' + currentProjectId);
        var p = await pResp.json();
        document.getElementById('dataMetaProjectName').textContent = p.name || '-';
        document.getElementById('dataMetaCode').textContent = p.code || '-';
        document.getElementById('dataMetaModels').textContent = p.models_count || '0';
    } catch(e) {}
    await loadDataCategories();
    countCategoryElements();
    // Reset to categories tab
    switchDataTab('categories');
}

async function loadDataCategories() {
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/categories');
        var data = await resp.json();
        dataCategories = (data.categories || []).map(function(c) {
            var cols = (c.columns && c.columns.length > 0) ? c.columns : getDefaultCols(c.name);
            // Migrate existing saved columns: add group from defaults if missing
            var defaults = getDefaultCols(c.name);
            cols = cols.map(function(col) {
                if (!col.group) {
                    // Look up group from default by label match
                    var def = defaults.find(function(d) { return d.label === col.label; });
                    col.group = def ? def.group : 'structural';
                }
                return col;
            });
            // Ensure position params exist from defaults
            defaults.filter(function(d) { return d.group === 'position'; }).forEach(function(def) {
                var exists = cols.some(function(col) { return col.label === def.label; });
                if (!exists) {
                    var newCol = { label: def.label, group: 'position' };
                    if (def.composite) {
                        newCol.composite = def.composite.slice();
                    } else if (def.keys) {
                        newCol.keys = def.keys.slice();
                    }
                    cols.push(newCol);
                }
            });
            return { name: c.name, columns: cols };
        });
    } catch(e) {
        dataCategories = [];
    }
    renderDataCategories();
}

async function countCategoryElements() {
    // Count elements per category from ALL models (data page shows project-wide stats)
    var counts = {};
    for (var i = 0; i < dataCategories.length; i++) counts[dataCategories[i].name] = 0;
    try {
        var mResp = await fetch(API_BASE + '/models?project_id=' + currentProjectId);
        var mData = await mResp.json();
        var models = mData.models || [];
        for (var mi = 0; mi < models.length; mi++) {
            if (models[mi].status !== 'processed') continue;
            var eResp = await fetch(API_BASE + '/models/' + models[mi].id + '/elements');
            var eData = await eResp.json();
            var elems = eData.elements || [];
            for (var ei = 0; ei < elems.length; ei++) {
                var cat = categorizeElement(elems[ei]);
                if (counts[cat] !== undefined) counts[cat]++;
                else if (counts['Невалидируемое семейство'] !== undefined) counts['Невалидируемое семейство']++;
            }
        }
    } catch(e) {}
    var items = document.querySelectorAll('.data-cat-item');
    for (var i = 0; i < items.length; i++) {
        var nameEl = items[i].querySelector('.cat-name');
        var countEl = items[i].querySelector('.cat-count');
        if (nameEl && countEl) {
            var name = nameEl.textContent;
            var cnt = counts[name] !== undefined ? counts[name] : 0;
            countEl.textContent = cnt;
        }
    }
    document.getElementById('dataMetaElements').textContent = Object.values(counts).reduce(function(a,b){return a+b;}, 0);
}

// ── Tab switching in Data page ─────────────────────────────────

window.switchDataTab = function(tab) {
    document.querySelectorAll('.data-tab').forEach(function(t) {
        t.classList.toggle('active', t.getAttribute('data-tab') === tab);
    });
    document.getElementById('dataCategoriesTab').style.display = tab === 'categories' ? '' : 'none';
    document.getElementById('dataTzTab').style.display = tab === 'tz' ? '' : 'none';
    document.getElementById('dataAiCheckTab').style.display = tab === 'ai-check' ? '' : 'none';
    document.querySelector('.categories-only').style.display = tab === 'categories' ? '' : 'none';
    document.querySelector('.tz-only').style.display = tab === 'tz' ? '' : 'none';
    document.querySelector('.ai-check-only').style.display = tab === 'ai-check' ? '' : 'none';
    var labels = {
        'categories': 'Настройка категорий элементов модели',
        'tz': 'Редактирование технического задания',
        'ai-check': 'Проверка модели с использованием ИИ',
    };
    document.getElementById('dataPageMeta').textContent = labels[tab] || '';
    if (tab === 'tz') loadTzSection();
    if (tab === 'ai-check') loadAiCheck();
};

// ── TZ section: load, save, upload, AI parse ───────────────────

var _activePipelineSys = 'water_supply';

function _emptyPipeline() {
    return {
        water_supply: { mains: {}, risers: {}, distribution: {} },
        sewerage: { mains: {}, risers: {}, distribution: {} },
        fire_fighting: { mains: {}, risers: {}, distribution: {} },
    };
}

function _renderPipelineTable(sys) {
    var sysLabels = { water_supply: 'Водоснабжение', sewerage: 'Водоотведение', fire_fighting: 'Пожаротушение' };
    var sectionLabels = { mains: 'Магистрали', risers: 'Стояки', distribution: 'Разводка' };
    var sections = ['mains', 'risers', 'distribution'];
    var pd = window._tzPipelineData || _emptyPipeline();
    var sysData = pd[sys] || {};

    var tbody = document.getElementById('pipelineTbody');
    tbody.innerHTML = sections.map(function(sec) {
        var secData = sysData[sec] || {};
        return '<tr>' +
            '<td style="font-weight:600;white-space:nowrap">' + sectionLabels[sec] + '</td>' +
            '<td><input class="pipe-mat" data-sys="' + sys + '" data-sec="' + sec + '" value="' + escHtml(secData.material || '') + '" placeholder="-"></td>' +
            '<td><input class="pipe-dia" data-sys="' + sys + '" data-sec="' + sec + '" value="' + escHtml(secData.diameter || '') + '" placeholder="-"></td>' +
            '<td><input class="pipe-ins" data-sys="' + sys + '" data-sec="' + sec + '" value="' + escHtml(secData.insulation || '') + '" placeholder="-"></td>' +
        '</tr>';
    }).join('');
}

function _readPipelineFromTable() {
    var pd = _emptyPipeline();
    document.querySelectorAll('#pipelineTbody input').forEach(function(inp) {
        var sys = inp.getAttribute('data-sys');
        var sec = inp.getAttribute('data-sec');
        var cls = inp.className;
        var val = inp.value;
        if (!pd[sys]) pd[sys] = {};
        if (!pd[sys][sec]) pd[sys][sec] = {};
        if (cls.indexOf('pipe-mat') >= 0) pd[sys][sec].material = val;
        else if (cls.indexOf('pipe-dia') >= 0) pd[sys][sec].diameter = val;
        else if (cls.indexOf('pipe-ins') >= 0) pd[sys][sec].insulation = val;
    });
    return pd;
}

window.switchPipelineTab = function(sys) {
    _activePipelineSys = sys;
    document.querySelectorAll('.pipeline-tab').forEach(function(t) {
        t.classList.toggle('active', t.getAttribute('data-sys') === sys);
    });
    _readPipelineFromTable();
    _renderPipelineTable(sys);
};

var _tzFileList = [];
var _selectedTzFile = '';

function _renderTzFileList() {
    var el = document.getElementById('tzFileList');
    var btnParse = document.getElementById('btnParseTz');
    var btnDl = document.getElementById('btnDownloadTz');
    if (!_tzFileList.length) {
        el.innerHTML = 'Файлов нет — загрузите PDF или Excel';
        btnParse.disabled = true;
        btnDl.style.display = 'none';
        return;
    }
    btnParse.disabled = false;
        var html = _tzFileList.map(function(f) {
        var size = f.size_bytes < 1024 ? f.size_bytes + ' B' : (f.size_bytes / 1024).toFixed(1) + ' KB';
        var date = f.uploaded_at ? new Date(f.uploaded_at).toLocaleString('ru-RU') : '';
        var selected = f.stored_name === _selectedTzFile;
        var label = f.display_name || f.stored_name;
        return '<label style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;background:' + (selected ? 'var(--accent-light)' : 'transparent') + ';cursor:pointer">' +
            '<input type="radio" name="tzFile" value="' + f.stored_name + '" ' + (selected ? 'checked' : '') + ' onchange="selectTzFile(\'' + f.stored_name + '\')" />' +
            '<span style="flex:1;font-size:13px">' + escHtml(label) + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + size + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + date + '</span>' +
            '<span style="cursor:pointer;color:var(--text-secondary);opacity:0.4;font-size:14px;padding:0 4px" onclick="event.stopPropagation();deleteTzFile(\'' + f.stored_name + '\')" title="Удалить файл">✕</span>' +
        '</label>';
    }).join('');
    el.innerHTML = html;
    btnDl.style.display = _selectedTzFile ? '' : 'none';
}

window.selectTzFile = function(storedName) {
    _selectedTzFile = storedName;
    _renderTzFileList();
};

async function loadTzSection() {
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();

        document.getElementById('tzGeneral').value = data.tz_general || '';
        document.getElementById('tzWaterSupply').value = data.tz_water_supply || '';
        document.getElementById('tzSewerage').value = data.tz_sewerage || '';
        document.getElementById('tzFireFighting').value = data.tz_fire_fighting || '';
        document.getElementById('tzOther').value = data.tz_other || '';
        document.getElementById('projectAddress').value = data.project_address || '';
        document.getElementById('sectionsCount').value = data.sections_count || '';
        document.getElementById('floorsCount').value = data.floors_count || '';
        document.getElementById('bimRequirements').value = data.bim_requirements || '';

        window._tzPipelineData = data.pipeline_data || _emptyPipeline();
        _activePipelineSys = 'water_supply';
        document.querySelectorAll('.pipeline-tab').forEach(function(t) {
            t.classList.toggle('active', t.getAttribute('data-sys') === 'water_supply');
        });
        _renderPipelineTable(_activePipelineSys);

        // File list
        _tzFileList = data.tz_files || [];
        if (_tzFileList.length && !_selectedTzFile) {
            _selectedTzFile = _tzFileList[0].stored_name;
        }
        _renderTzFileList();

        loadTzHistory();
    } catch (e) {
        showToast('Ошибка загрузки ТЗ: ' + e.message, 'error');
    }
}

async function loadTzHistory() {
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz/history');
        if (!resp.ok) return;
        var data = await resp.json();
        var list = document.getElementById('tzHistoryList');
        if (!data.versions || !data.versions.length) {
            list.innerHTML = '<div style="color:var(--text-secondary);font-size:12px">Нет версий</div>';
            return;
        }
        var sourceLabels = { ai: 'AI', manual: 'Вручную', upload: 'Загрузка' };
        list.innerHTML = data.versions.map(function(v) {
            var src = sourceLabels[v.source] || v.source;
            var date = v.created_at ? new Date(v.created_at).toLocaleString('ru-RU') : '';
            return '<div class="tz-history-item">' +
                '<span>Версия ' + v.version + '</span>' +
                '<span class="tz-history-source">' + src + '</span>' +
                '<span style="color:var(--text-secondary)">' + date + '</span>' +
            '</div>';
        }).join('');
    } catch(e) {}
}

window.saveTzSection = async function() {
    _readPipelineFromTable();
    var data = {
        tz_general: document.getElementById('tzGeneral').value,
        tz_water_supply: document.getElementById('tzWaterSupply').value,
        tz_sewerage: document.getElementById('tzSewerage').value,
        tz_fire_fighting: document.getElementById('tzFireFighting').value,
        tz_other: document.getElementById('tzOther').value,
        project_address: document.getElementById('projectAddress').value,
        sections_count: document.getElementById('sectionsCount').value,
        floors_count: document.getElementById('floorsCount').value,
        bim_requirements: document.getElementById('bimRequirements').value,
        pipeline_data: window._tzPipelineData || _emptyPipeline(),
    };
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        showToast('ТЗ сохранено', 'success');
        loadTzHistory();
    } catch (e) {
        showToast('Ошибка сохранения: ' + e.message, 'error');
    }
};

window.uploadTzFile = async function(file) {
    if (!file) return;
    var form = new FormData();
    form.append('file', file);
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz/upload', {
            method: 'POST',
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        showToast('Файл загружен', 'success');
        loadTzSection();
    } catch (e) {
        showToast('Ошибка загрузки файла: ' + e.message, 'error');
    }
};

window.downloadTzFile = function() {
    if (!_selectedTzFile) return;
    window.open(API_BASE + '/projects/' + currentProjectId + '/tz/file?filename=' + encodeURIComponent(_selectedTzFile), '_blank');
};

window.deleteTzFile = async function(storedName) {
    if (!confirm('Удалить файл ' + storedName + '?')) return;
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz/files?filename=' + encodeURIComponent(storedName), {
            method: 'DELETE',
        });
        if (!resp.ok) {
            var err = await resp.json().catch(function(){return null});
            throw new Error((err && err.detail) || 'HTTP ' + resp.status);
        }
        if (_selectedTzFile === storedName) {
            _selectedTzFile = '';
        }
        showToast('Файл удалён', 'success');
        loadTzSection();
    } catch (e) {
        showToast('Ошибка удаления: ' + e.message, 'error');
    }
};

window.parseTzAi = async function() {
    var btn = document.getElementById('btnParseTz');
    if (!_selectedTzFile) {
        showToast('Выберите файл для распознавания', 'error');
        return;
    }
    btn.disabled = true;
    btn.textContent = '⏳ Распознавание...';
    try {
        var url = API_BASE + '/projects/' + currentProjectId + '/tz/parse?filename=' + encodeURIComponent(_selectedTzFile);
        var resp = await fetch(url, { method: 'POST' });
        if (!resp.ok) {
            var errBody = '';
            try { var errJson = await resp.json(); errBody = errJson.detail || JSON.stringify(errJson); } catch(e2) { errBody = await resp.text(); }
            throw new Error(errBody || 'HTTP ' + resp.status);
        }
        var data = await resp.json();

        // Store parsed data for preview modal
        window._tzPreviewData = data;

        // Build preview HTML
        var html = '';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Адрес объекта</label>';
        html += '<input class="form-input preview-tz-field" id="pv_address" value="' + escHtml(data.project_address || '') + '" /></div>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Секций</label><input class="form-input preview-tz-field" id="pv_sections" value="' + escHtml(data.sections_count || '') + '" /></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Этажей</label><input class="form-input preview-tz-field" id="pv_floors" value="' + escHtml(data.floors_count || '') + '" /></div>';
        html += '</div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">BIM-требования</label>';
        html += '<input class="form-input preview-tz-field" id="pv_bim" value="' + escHtml(data.bim_requirements || '') + '" /></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Общее описание</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_general" rows="3">' + escHtml(data.tz_general || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Водоснабжение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_ws" rows="2">' + escHtml(data.tz_water_supply || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Водоотведение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_sew" rows="2">' + escHtml(data.tz_sewerage || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Пожаротушение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_ff" rows="2">' + escHtml(data.tz_fire_fighting || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Прочие</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_other" rows="2">' + escHtml(data.tz_other || '') + '</textarea></div>';

        // Pipeline data preview - simple fields for each system
        var pd = data.pipeline_data || {};
        var sysList = ['water_supply', 'sewerage', 'fire_fighting'];
        var sysLabels = { water_supply: 'Водоснабжение', sewerage: 'Водоотведение', fire_fighting: 'Пожаротушение' };
        var secLabels = { mains: 'Магистрали', risers: 'Стояки', distribution: 'Разводка' };
        html += '<div style="margin-top:12px"><div style="font-size:12px;text-transform:uppercase;color:var(--text-secondary);font-weight:600;margin-bottom:8px">Трубопроводы</div>';
        sysList.forEach(function(sys) {
            var sysData = pd[sys] || {};
            ['mains', 'risers', 'distribution'].forEach(function(sec) {
                var s = sysData[sec] || {};
                var mat = s.material || '';
                var dia = s.diameter || '';
                var ins = s.insulation || '';
                if (mat || dia || ins) {
                    html += '<div style="font-size:12px;margin-bottom:4px"><span style="color:var(--text-secondary)">' + sysLabels[sys] + ' / ' + secLabels[sec] + ':</span> ' +
                        (mat ? 'мат: ' + escHtml(mat) : '') + (dia ? ', d: ' + escHtml(dia) : '') + (ins ? ', изол: ' + escHtml(ins) : '') + '</div>';
                }
            });
        });
        html += '</div>';

        // Raw GPT response & prompt
        if (data._raw_gpt || data._raw_prompt) {
            html += '<details style="margin-top:16px">' +
                '<summary style="cursor:pointer;font-size:12px;color:var(--text-secondary)">📜 Промпт и ответ GPT</summary>' +
                (data._raw_prompt ? '<div style="margin-top:8px"><div style="font-size:11px;text-transform:uppercase;color:var(--text-secondary);margin-bottom:4px">Промпт (system + user):</div>' +
                '<pre style="padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;font-size:11px;line-height:1.4;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto">' + escHtml(data._raw_prompt) + '</pre></div>' : '') +
                (data._raw_gpt ? '<div style="margin-top:8px"><div style="font-size:11px;text-transform:uppercase;color:var(--text-secondary);margin-bottom:4px">Ответ GPT:</div>' +
                '<pre style="padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;font-size:11px;line-height:1.4;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto">' + escHtml(data._raw_gpt) + '</pre></div>' : '') +
            '</details>';
        }

        document.getElementById('tzPreviewContent').innerHTML = html;
        openModal('tzPreviewModal');
    } catch (e) {
        showToast('Ошибка распознавания: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Распознать выбранный';
    }
};

window.applyTzPreview = function() {
    function gv(id) { return document.getElementById(id).value; }
    var fields = {
        tz_general: gv('pv_general'),
        tz_water_supply: gv('pv_ws'),
        tz_sewerage: gv('pv_sew'),
        tz_fire_fighting: gv('pv_ff'),
        tz_other: gv('pv_other'),
        project_address: gv('pv_address'),
        sections_count: gv('pv_sections'),
        floors_count: gv('pv_floors'),
        bim_requirements: gv('pv_bim'),
    };
    // Only send non-empty fields — don't overwrite existing data with blanks
    var data = {};
    for (var key in fields) {
        if (fields[key].trim()) {
            data[key] = fields[key];
        }
    }
    var pd = window._tzPreviewData && window._tzPreviewData.pipeline_data;
    if (pd) {
        var hasData = false;
        ['water_supply','sewerage','fire_fighting'].forEach(function(sys) {
            ['mains','risers','distribution'].forEach(function(sec) {
                var s = (pd[sys]||{})[sec]||{};
                if (s.material || s.diameter || s.insulation) hasData = true;
            });
        });
        if (hasData) data.pipeline_data = pd;
    }

    if (Object.keys(data).length === 0) {
        showToast('Нет данных для сохранения', 'warning');
        closeModal('tzPreviewModal');
        return;
    }

    // Save to DB
    fetch(API_BASE + '/projects/' + currentProjectId + '/tz', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
    .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        showToast('ТЗ сохранено', 'success');
        closeModal('tzPreviewModal');
        loadTzSection();
        loadTzHistory();
        return r.json();
    })
    .catch(function(e) {
        showToast('Ошибка: ' + e.message, 'error');
    });
};

// ── AI Check ─────────────────────────────────────────────────────

var _aiCheckProblems = [];

async function loadAiCheck() {
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/ai-check');
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
                    '<div class="ai-problem-msg">' + escHtml(p.message) + '</div>' +
                    (p.details ? '<div class="ai-problem-details">' + escHtml(p.details) + '</div>' : '') +
                    (p.rule_key ? '<div class="ai-problem-rule">' + escHtml(p.rule_key) + '</div>' : '') +
                '</div>' +
                '<button class="ai-problem-dismiss" onclick="toggleAiProblem(' + i + ')" title="' + dismissTitle + '">' + dismissIcon + '</button>' +
            '</div>';
    });
    document.getElementById('aiCheckProblemList').innerHTML = html;
}

window.runAiCheck = async function() {
    if (!currentProjectId) return;
    showAiCheckLoading();
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/ai-check', {
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
            showToast('Проверка завершена — проблем не найдено', 'success');
        } else {
            showToast('Найдено ' + _aiCheckProblems.length + ' замечаний', _aiCheckProblems.some(function(p) { return p.severity === 'error'; }) ? 'error' : 'success');
        }
    } catch(e) {
        showAiCheckStart();
        showToast('Ошибка проверки: ' + e.message, 'error');
    }
};

window.toggleAiProblem = async function(index) {
    var problem = _aiCheckProblems[index];
    if (!problem) return;
    var newState = !problem.dismissed;
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/ai-check/' + index + '?dismissed=' + newState, {
            method: 'PATCH',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        _aiCheckProblems[index].dismissed = newState;
        renderAiCheckProblems();
    } catch(e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

function renderDataCategories() {
    var el = document.getElementById('dataCatList');
    if (!dataCategories.length) {
        el.innerHTML = '<div class="empty-message" style="padding:40px;text-align:center;color:var(--text-secondary)">Нет категорий. Добавьте новую.</div>';
        return;
    }
    el.innerHTML = dataCategories.map(function(cat, i) {
        var c = CATEGORY_ICONS[cat.name] || { color: '#6b7280', icon: '?' };
        var cols = cat.columns || [];
        var colsHtml = '';
        function renderColRow(col, origIdx) {
            var delBtn = '<span class="data-col-del" onclick="deleteColumn(' + i + ',' + origIdx + ')" title="Удалить параметр">✕</span>';
            if (col.composite) {
                var hint = 'составной: ' + col.composite.join(' + ');
                return '<div class="data-col-row" data-ci="' + origIdx + '">' +
                    '<input class="data-col-label" value="' + escHtml(col.label) + '" placeholder="Название" />' +
                    '<span class="data-col-composite-hint">' + escHtml(hint) + '</span>' +
                    delBtn +
                '</div>';
            }
            var keysStr = (col.keys || []).join(', ');
            return '<div class="data-col-row" data-ci="' + origIdx + '">' +
                '<input class="data-col-label" value="' + escHtml(col.label) + '" placeholder="Название" />' +
                '<input class="data-col-keys" value="' + escHtml(keysStr) + '" placeholder="ключи через запятую" />' +
                delBtn +
            '</div>';
        }
        // Position parameters group
        var posCols = cols.filter(function(col) { return col.group === 'position'; });
        if (posCols.length) {
            colsHtml += '<div class="data-col-group-header">Параметры положения</div>';
            colsHtml += posCols.map(function(col, ci) {
                return renderColRow(col, cols.indexOf(col));
            }).join('');
        }
        // Structural parameters group
        var structCols = cols.filter(function(col) { return col.group !== 'position'; });
        if (structCols.length) {
            colsHtml += '<div class="data-col-group-header">Структурные параметры</div>';
            colsHtml += structCols.map(function(col, ci) {
                return renderColRow(col, cols.indexOf(col));
            }).join('');
        }
        var expandId = 'data-cat-expand-' + i;
        return '<div class="data-cat-item" data-index="' + i + '">' +
            '<span class="cat-handle" onclick="toggleCatExpand(\'' + expandId + '\')">▶</span>' +
            '<span class="class-icon" style="border-color:' + c.color + ';background:' + c.color + '"></span>' +
            '<span class="cat-name" onclick="editCategoryName(' + i + ', this)">' + escHtml(cat.name) + '</span>' +
            '<span class="cat-count">...</span>' +
            '<span class="cat-del" onclick="deleteCategory(' + i + ')" title="Удалить">✕</span>' +
        '</div>' +
        '<div class="data-cat-columns" id="' + expandId + '">' +
            colsHtml +
            '<div class="data-col-add" onclick="addColumn(' + i + ')">+ Добавить параметр</div>' +
        '</div>';
    }).join('');
}

window.toggleCatExpand = function(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('open');
};

window.addColumn = function(catIdx) {
    if (!dataCategories[catIdx]) return;
    if (!dataCategories[catIdx].columns) dataCategories[catIdx].columns = [];
    dataCategories[catIdx].columns.push({ label: '', keys: [], group: 'structural' });
    renderDataCategories();
    // Auto-open the section
    var expandId = 'data-cat-expand-' + catIdx;
    var el = document.getElementById(expandId);
    if (el) el.classList.add('open');
};

window.deleteColumn = function(catIdx, colIdx) {
    if (!dataCategories[catIdx]) return;
    var cols = dataCategories[catIdx].columns;
    if (!cols) return;
    cols.splice(colIdx, 1);
    renderDataCategories();
};

window.editCategoryName = function(index, el) {
    var current = dataCategories[index].name;
    var input = document.createElement('input');
    input.className = 'cat-name-input';
    input.value = current;
    input.style.cssText = 'flex:1;padding:4px 8px;background:var(--bg);border:1px solid var(--accent);border-radius:4px;color:var(--text);font-size:13px';
    el.replaceWith(input);
    input.focus();
    input.select();

    function commit() {
        var val = input.value.trim();
        if (val && val !== current) {
            // Check for duplicates
            var dup = dataCategories.find(function(c, idx) {
                return idx !== index && c.name.toLowerCase() === val.toLowerCase();
            });
            if (dup) {
                showToast('Категория с таким именем уже существует', 'error');
                input.value = current;
            } else {
                dataCategories[index].name = val;
            }
        }
        renderDataCategories();
    }

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { e.preventDefault(); renderDataCategories(); }
    });
};

window.addCategory = function() {
    var input = document.getElementById('dataNewCatName');
    var name = input.value.trim();
    if (!name) return;
    if (dataCategories.find(function(c) { return c.name.toLowerCase() === name.toLowerCase(); })) {
        showToast('Категория уже существует', 'error');
        return;
    }
    dataCategories.push({ name: name, columns: [] });
    input.value = '';
    renderDataCategories();
};

window.deleteCategory = function(index) {
    dataCategories.splice(index, 1);
    renderDataCategories();
};

window.saveCategories = async function() {
    // Read columns from UI before saving
    document.querySelectorAll('.data-cat-item').forEach(function(item, idx) {
        var cols = [];
        // data-cat-columns is a sibling (not child) of data-cat-item
        var expandId = 'data-cat-expand-' + idx;
        var colsEl = document.getElementById(expandId);
        if (colsEl) {
            colsEl.querySelectorAll('.data-col-row').forEach(function(row) {
                var label = row.querySelector('.data-col-label').value.trim();
                if (!label) return;
                var ci = parseInt(row.getAttribute('data-ci'));
                var existing = dataCategories[idx] && dataCategories[idx].columns[ci];
                var group = existing && existing.group ? existing.group : 'structural';
                if (existing && existing.composite) {
                    // Composite column — preserve definition
                    cols.push({ label: label, composite: existing.composite.slice(), group: group });
                    return;
                }
                var keysStr = row.querySelector('.data-col-keys').value.trim();
                var keys = keysStr ? keysStr.split(',').map(function(k) { return k.trim(); }).filter(Boolean) : [label];
                cols.push({ label: label, keys: keys, group: group });
            });
        }
        if (dataCategories[idx]) {
            dataCategories[idx].columns = cols;
        }
    });

    var payload = dataCategories.map(function(c) {
        return { name: c.name, columns: c.columns };
    });
    try {
        var form = new URLSearchParams();
        form.set('categories', JSON.stringify(payload));
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/categories', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        showToast('Категории и параметры сохранены', 'success');
        var names = dataCategories.map(function(c) { return c.name; });
        CATEGORIES = names;
        CATEGORY_ICONS = buildCategoryIcons(names);
        // Rebuild __CATEGORY_COLUMNS from saved data
        __CATEGORY_COLUMNS = dataCategories.map(function(c) {
            return { cat: c.name, cols: (c.columns && c.columns.length) ? c.columns : getDefaultCols(c.name) };
        });
        await loadDataCategories();
        countCategoryElements();
    } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
    }
};

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
        var url = API_BASE + '/ai/status?check=' + (fullCheck ? 'true' : 'false');
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

showHome();
