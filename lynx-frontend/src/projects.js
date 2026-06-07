window.projects = [];
window.currentProjectId = null;
let editingProjectId = null;

// ── Projects ────────────────────────────────────────────────────

async function loadProjects() {
    const el = document.getElementById('projectList');
    el.innerHTML = '<div class="empty-state">Загрузка...</div>';

    try {
        const resp = await fetch(`${window.API_BASE}/projects`);
        const data = await resp.json();
        window.projects = data.projects || [];
        renderProjects();
        renderQuickSelect();
    } catch (e) {
        el.innerHTML = `<div class="empty-state">Ошибка: ${e.message}</div>`;
    }
}
window.loadProjects = loadProjects;

function renderProjects() {
    const el = document.getElementById('projectList');
    if (!window.projects.length) {
        el.innerHTML = `
            <div class="empty-state">
                <div class="big">📁</div>
                <p>Нет проектов</p>
                <p style="margin-top:8px;font-size:13px">Создайте первый проект</p>
            </div>
        `;
        return;
    }
    el.innerHTML = window.projects.map(function(p) { return [
        '<div class="project-card" onclick="showProject(\'' + p.id + '\')">',
            '<div class="project-card-title">' + window.escHtml(p.name) + '</div>',
            '<div class="project-card-code">' + window.escHtml(p.code) + '</div>',
            '<div class="project-card-meta">',
                '<span>📦 ' + (p.models_count ?? 0) + ' моделей</span>',
                '<span>📅 ' + window.formatDate(p.created_at) + '</span>',
            '</div>',
            '<button class="project-card-delete" onclick="event.stopPropagation();window.deleteProject(\'' + p.id + '\')" title="Удалить проект">✕</button>',
        '</div>'
    ].join(''); }).join('');
}

function renderQuickSelect() {
    const qs = document.getElementById('projectQuickSelect');
    qs.innerHTML = '<option value="">— Быстрый переход —</option>' +
        window.projects.map(function(p) {
            return '<option value="' + p.id + '"' + (p.id === window.currentProjectId ? ' selected' : '') + '>' + window.escHtml(p.name) + '</option>';
        }).join('');
}

async function loadProjectDetail(projectId) {
    try {
        const resp = await fetch(`${window.API_BASE}/projects/${projectId}`);
        const p = await resp.json();
        const kw = p.auto_bind_keywords || '';
        document.getElementById('keywordsContent').textContent = kw || 'не заданы';
    } catch (e) {
    }
}
window.loadProjectDetail = loadProjectDetail;

// ── Project CRUD ────────────────────────────────────────────────

window.showCreateProjectModal = function() {
    editingProjectId = null;
    document.getElementById('projectModalTitle').textContent = 'Новый проект';
    document.getElementById('projectCode').value = '';
    document.getElementById('projectName').value = '';
    document.getElementById('projectTz').value = '';
    document.getElementById('projectKeywords').value = '';
    document.getElementById('projectSaveBtn').textContent = 'Создать';
    window.openModal('projectModal');
};

window.showEditProjectModal = function(id) {
    const p = window.projects.find(x => x.id === id);
    if (!p) return;
    editingProjectId = id;
    document.getElementById('projectModalTitle').textContent = 'Редактировать проект';
    document.getElementById('projectCode').value = p.code;
    document.getElementById('projectName').value = p.name;
    document.getElementById('projectTz').value = p.technical_specification || '';
    document.getElementById('projectKeywords').value = p.auto_bind_keywords || '';
    document.getElementById('projectSaveBtn').textContent = 'Сохранить';
    window.openModal('projectModal');
};

window.saveProject = async function() {
    const code = document.getElementById('projectCode').value.trim();
    const name = document.getElementById('projectName').value.trim();
    const tz = document.getElementById('projectTz').value.trim();
    const kw = document.getElementById('projectKeywords').value.trim();
    if (!code || !name) { window.showToast('Заполните код и название', 'error'); return; }

    try {
        if (editingProjectId) {
            const form = new URLSearchParams();
            form.set('name', name);
            form.set('technical_specification', tz);
            form.set('auto_bind_keywords', kw);
            const resp = await fetch(`${window.API_BASE}/projects/${editingProjectId}`, {
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
            const resp = await fetch(`${window.API_BASE}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: form,
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
        }
        window.closeModal('projectModal');
        window.showToast('Проект сохранён', 'success');
        loadProjects();
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

window.deleteProject = async function(id) {
    if (!confirm('Удалить проект и все его модели?')) return;
    try {
        const resp = await fetch(`${window.API_BASE}/projects/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Проект удалён', 'success');
        if (window.currentProjectId === id) window.goHome();
        else loadProjects();
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Keywords ────────────────────────────────────────────────────

window.showEditKeywordsModal = function() {
    const el = document.getElementById('keywordsContent');
    document.getElementById('keywordsEditor').value = el.textContent === 'не заданы' ? '' : el.textContent;
    window.openModal('keywordsModal');
};

window.saveKeywords = async function() {
    const kw = document.getElementById('keywordsEditor').value.trim();
    try {
        const form = new URLSearchParams();
        form.set('auto_bind_keywords', kw);
        const resp = await fetch(`${window.API_BASE}/projects/${window.currentProjectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.closeModal('keywordsModal');
        window.showToast('Ключи сохранены', 'success');
        loadProjectDetail(window.currentProjectId);
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── getProjectName ──────────────────────────────────────────────

function getProjectName(id) {
    var p = window.projects.find(function(x) { return x.id === id; });
    return p ? p.name : '...';
}
window.getProjectName = getProjectName;
