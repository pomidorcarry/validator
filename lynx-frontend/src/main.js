import { loadIfcFromBuffer } from './viewer.js';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

let models = [];
let elements = [];
let selectedModelId = null;

async function loadModels() {
    try {
        const resp = await fetch(`${API_BASE}/models`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        models = data.models || [];
        renderModelList();
        if (models.length && !selectedModelId) {
            selectModel(models[0].id);
        }
    } catch (e) {
        document.getElementById('modelList').innerHTML = '<div class="empty-state">Ошибка: ' + e.message + '</div>';
    }
}

function renderModelList() {
    const el = document.getElementById('modelList');
    if (!models.length) { el.innerHTML = '<div class="empty-state">Нет моделей</div>'; return; }
    el.innerHTML = models.map(m => 
        `<div class="model-item ${m.id === selectedModelId ? 'active' : ''}" onclick="selectModel('${m.id}')">
            <div class="model-item-title">${m.model_name}</div>
            <div class="model-item-meta">${formatDate(m.created_at)} · ${getStatusBadge(m.status)}</div>
        </div>`
    ).join('');
}

async function selectModel(id) {
    selectedModelId = id;
    const m = models.find(x => x.id === id);
    document.getElementById('modelName').textContent = m?.model_name || '-';
    const st = document.getElementById('modelStatus');
    st.textContent = m?.status || '-';
    st.className = 'status-badge ' + (m?.status || '');
    
    await loadIssues(id);
    await loadElements(id);
    
    if (m?.status === 'processed') {
        await load3D(id);
    }
}

async function load3D(modelId) {
    const placeholder = document.getElementById('viewerPlaceholder');
    placeholder.textContent = 'Загрузка IFC...';
    
    try {
        const resp = await fetch(`${API_BASE}/models/${modelId}/ifc`);
        const buffer = await resp.arrayBuffer();
        
        await loadIfcFromBuffer(buffer);
        
        placeholder.style.display = 'none';
    } catch(e) {
        console.error('3D error:', e);
        placeholder.textContent = 'Ошибка 3D: ' + e.message;
    }
}

async function loadIssues(modelId) {
    try {
        const resp = await fetch(`${API_BASE}/models/${modelId}/issues`);
        const data = await resp.json();
        renderIssues(data.issues || []);
    } catch(e) {
        document.getElementById('issuesList').innerHTML = '<div class="empty-state">Ошибка</div>';
    }
}

function renderIssues(issues) {
    const el = document.getElementById('issuesList');
    if (!issues.length) { el.innerHTML = '<div class="empty-state">Нет ошибок</div>'; return; }
    el.innerHTML = issues.map(i => 
        `<div class="issue-item ${i.severity}" onclick="showInspector('${i.global_id}')">
            <div class="issue-header">
                <span class="issue-badge ${i.severity}">${i.severity}</span>
                <span class="issue-key">${i.rule_key}</span>
            </div>
            <div class="issue-message">${i.message}</div>
        </div>`
    ).join('');
}

async function loadElements(modelId) {
    try {
        const resp = await fetch(`${API_BASE}/models/${modelId}/elements`);
        const data = await resp.json();
        elements = data.elements || [];
    } catch(e) {
        elements = [];
    }
}

function showInspector(globalId) {
    const el = elements.find(x => x.global_id === globalId);
    if (!el) return;
    
    const data = {
        'Global ID': el.global_id,
        'Класс IFC': el.ifc_class,
        'Имя': el.name || '-',
        'Этаж': el.storey_name || '-',
        'Система': el.system_name || '-',
    };
    
    document.getElementById('inspector').innerHTML = 
        Object.entries(data).map(([k, v]) => 
            `<div class="inspector-row"><span class="inspector-label">${k}</span><span class="inspector-value">${v}</span></div>`
        ).join('');
}

function formatDate(s) {
    try {
        return new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
    } catch { return '-'; }
}

function getStatusBadge(s) {
    const map = { processed: '✓', queued: '⏳', failed: '✗' };
    return map[s] || s;
}

window.selectModel = selectModel;
window.showInspector = showInspector;

loadModels();