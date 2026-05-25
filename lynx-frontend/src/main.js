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
                '<div class="model-item-title">' + escHtml(m.model_name) + '</div>',
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
    el.innerHTML = issues.map(i =>
        `<div class="issue-item ${i.severity}" onclick="showInspector('${i.global_id}')">
            <div class="issue-header">
                <span class="issue-badge ${i.severity}">${i.severity}</span>
                <span class="issue-key">${escHtml(i.rule_key)}</span>
            </div>
            <div class="issue-message">${escHtml(i.message)}</div>
        </div>`
    ).join('');
}

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
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Этаж', keys: ['Этаж', 'Storey', 'Level'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'PipeType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
        { label: 'Толщина стенки', keys: ['Толщина стенки', 'WallThickness'] },
        { label: 'Длина, мм', keys: ['Длина', 'Length'] },
        { label: 'Стадия', keys: ['Стадия проектирования', 'DesignStage'] },
    ],
    'Труба полимерная': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'PipeType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
        { label: 'Толщина стенки', keys: ['Толщина стенки', 'WallThickness'] },
        { label: 'Длина, мм', keys: ['Длина', 'Length'] },
    ],
    'Металлическая соединительная деталь трубы': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'FittingType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
    ],
    'Полимерная соединительная деталь трубы': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'FittingType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
    ],
    'Арматура труб': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'ValveType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
        { label: 'Материал', keys: ['Материал', 'Material'] },
    ],
    'Арматура': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'ValveType'] },
        { label: 'Размер', keys: ['Размер', 'Size', 'DN', 'NominalDiameter'] },
        { label: 'Материал', keys: ['Материал', 'Material'] },
    ],
    'Оборудование': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Часть системы', keys: ['Часть системы', 'SystemPart', 'PartOfSystem', 'System'] },
        { label: 'Тип', keys: ['Тип', 'EquipmentType', 'Type'] },
        { label: 'Мощность', keys: ['Мощность', 'Power', 'PowerConsumption'] },
        { label: 'Производительность', keys: ['Производительность', 'Performance', 'FlowRate'] },
    ],
    'Сантехнический прибор': [
        { label: 'Секция', keys: ['Секция', 'Section'] },
        { label: 'Вид', keys: ['Вид', 'Type', 'FixtureType'] },
        { label: 'Подключение', keys: ['Подключение', 'Connection', 'ConnectionType'] },
    ],
    'Изоляция рулонная': [
        { label: 'Толщина', keys: ['Толщина', 'Thickness'] },
        { label: 'Материал', keys: ['Материал', 'Material'] },
        { label: 'Тип', keys: ['Тип', 'Type', 'InsulationType'] },
    ],
    'Изоляция трубчатая': [
        { label: 'Толщина', keys: ['Толщина', 'Thickness'] },
        { label: 'Материал', keys: ['Материал', 'Material'] },
        { label: 'Тип', keys: ['Тип', 'Type', 'InsulationType'] },
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
    for (var psetName in rawPsets) {
        var props = rawPsets[psetName];
        if (!props || typeof props !== 'object') continue;
        for (var ki = 0; ki < keys.length; ki++) {
            var val = props[keys[ki]];
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

async function loadTzElements() {
    document.getElementById('tzPageTitle').textContent = 'Элементы';
    document.getElementById('tzPageMeta').textContent = 'Загрузка элементов из всех моделей проекта...';

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

        for (var i = 0; i < projectModels.length; i++) {
            var m = projectModels[i];
            if (m.status !== 'processed') continue;
            try {
                var eResp = await fetch(API_BASE + '/models/' + m.id + '/elements');
                var eData = await eResp.json();
                var elems = eData.elements || [];
                for (var j = 0; j < elems.length; j++) {
                    var el = elems[j];
                    el._modelName = m.model_name;
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
    document.getElementById('tzPageMeta').textContent = 'Всего элементов: ' + totalCount + ' · Классов IFC: ' + ifcClassNames.length;

    renderTzSections(allCatElems);
    renderTzClassFilter(ifcClassNames);
    tzRenderTable();
}

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
            { label: 'Этаж', keys: ['Этаж', 'Storey', 'Level'] },
            { label: 'Система', keys: ['Система', 'System'] },
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
            { label: 'Этаж', keys: ['Этаж', 'Storey', 'Level'] },
            { label: 'Система', keys: ['Система', 'System'] },
        ];

    container.innerHTML = filtered.map(function(e) {
        var cat = categorizeElement(e);
        var c = CATEGORY_ICONS[cat] || { color: '#6b7280', icon: '?' };
        var propsHtml = cols.map(function(col) {
            var val = extractProp(e.raw_psets_jsonb, col.keys);
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
            return { name: c.name, columns: (c.columns && c.columns.length) ? c.columns : getDefaultCols(c.name) };
        });
    } catch(e) {
        dataCategories = [];
    }
    renderDataCategories();
}

async function countCategoryElements() {
    // Count elements per category by fetching all project elements
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
    // Update counts in the rendered list
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
    document.querySelector('.categories-only').style.display = tab === 'categories' ? '' : 'none';
    document.querySelector('.tz-only').style.display = tab === 'tz' ? '' : 'none';
    document.getElementById('dataPageMeta').textContent = tab === 'categories'
        ? 'Настройка категорий элементов модели'
        : 'Редактирование технического задания';
    if (tab === 'tz') loadTzSection();
};

// ── TZ section: load, save, upload, AI parse ───────────────────

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

        var fileInfo = document.getElementById('tzFileInfo');
        var btnDl = document.getElementById('btnDownloadTz');
        if (data.tz_file_name) {
            var dateStr = data.tz_file_uploaded_at ? new Date(data.tz_file_uploaded_at).toLocaleString('ru-RU') : '';
            fileInfo.textContent = 'Файл: ' + data.tz_file_name + (dateStr ? ' (загружен ' + dateStr + ')' : '');
            btnDl.style.display = '';
        } else {
            fileInfo.textContent = 'Файл не загружен';
            btnDl.style.display = 'none';
        }

        // Load history in background
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
    var data = {
        tz_general: document.getElementById('tzGeneral').value,
        tz_water_supply: document.getElementById('tzWaterSupply').value,
        tz_sewerage: document.getElementById('tzSewerage').value,
        tz_fire_fighting: document.getElementById('tzFireFighting').value,
        tz_other: document.getElementById('tzOther').value,
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

window.parseTzAi = async function() {
    var btn = document.getElementById('btnParseTz');
    btn.disabled = true;
    btn.textContent = '⏳ Распознавание...';
    try {
        var resp = await fetch(API_BASE + '/projects/' + currentProjectId + '/tz/parse', {
            method: 'POST',
        });
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return null; });
            throw new Error((err && err.detail) || 'HTTP ' + resp.status);
        }
        var data = await resp.json();
        document.getElementById('tzGeneral').value = data.tz_general || '';
        document.getElementById('tzWaterSupply').value = data.tz_water_supply || '';
        document.getElementById('tzSewerage').value = data.tz_sewerage || '';
        document.getElementById('tzFireFighting').value = data.tz_fire_fighting || '';
        document.getElementById('tzOther').value = data.tz_other || '';
        showToast('ТЗ распознано через ИИ', 'success');
        loadTzHistory();
    } catch (e) {
        showToast('Ошибка распознавания: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Распознать через ИИ';
    }
};

window.downloadTzFile = function() {
    window.open(API_BASE + '/projects/' + currentProjectId + '/tz/file', '_blank');
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
        var colsHtml = cols.map(function(col, ci) {
            var keysStr = (col.keys || []).join(', ');
            return '<div class="data-col-row" data-ci="' + ci + '">' +
                '<input class="data-col-label" value="' + escHtml(col.label) + '" placeholder="Название" />' +
                '<input class="data-col-keys" value="' + escHtml(keysStr) + '" placeholder="ключи через запятую" />' +
                '<span class="data-col-del" onclick="deleteColumn(' + i + ',' + ci + ')" title="Удалить параметр">✕</span>' +
            '</div>';
        }).join('');
        var expandId = 'data-cat-expand-' + i;
        return '<div class="data-cat-item" data-index="' + i + '">' +
            '<span class="cat-handle" onclick="toggleCatExpand(\'' + expandId + '\')">▶</span>' +
            '<span class="class-icon" style="border-color:' + c.color + ';background:' + c.color + '"></span>' +
            '<span class="cat-name" onclick="editCategoryName(' + i + ', this)">' + escHtml(cat.name) + '</span>' +
            '<span class="cat-count">...</span>' +
            '<span class="cat-del" onclick="deleteCategory(' + i + ')" title="Удалить">✕</span>' +
        '</div>' +
        '<div class="data-cat-columns" id="' + expandId + '">' +
            '<div class="data-col-header">' +
                '<span style="flex:2">Параметр</span>' +
                '<span style="flex:2">Ключи IFC</span>' +
                '<span style="width:24px"></span>' +
            '</div>' +
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
    dataCategories[catIdx].columns.push({ label: '', keys: [], format: null });
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
        item.querySelectorAll('.data-col-row').forEach(function(row) {
            var label = row.querySelector('.data-col-label').value.trim();
            var keysStr = row.querySelector('.data-col-keys').value.trim();
            if (!label) return;
            var keys = keysStr ? keysStr.split(',').map(function(k) { return k.trim(); }).filter(Boolean) : [label];
            cols.push({ label: label, keys: keys });
        });
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
