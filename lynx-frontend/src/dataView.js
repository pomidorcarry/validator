var dataCategories = [];

window.showDataPage = function() {
    if (!window.currentProjectId) return;
    document.getElementById('homeView').classList.remove('active');
    document.getElementById('projectView').classList.remove('active');
    document.getElementById('tzView').classList.remove('active');
    document.getElementById('dataView').classList.add('active');
    document.getElementById('breadcrumb').innerHTML = [
        '<span class="link" onclick="goHome()">Проекты</span>',
        '<span>/</span>',
        '<span class="link" onclick="showProject(\'' + window.currentProjectId + '\')">' + window.escHtml(window.getProjectName(window.currentProjectId)) + '</span>',
        '<span>/</span>',
        '<span class="current">Данные о проекте и обработка ТЗ</span>'
    ].join('');
    document.getElementById('projectQuickSelect').style.display = 'none';
    document.getElementById('btnNewProject').style.display = 'none';
    loadDataPage();
};

window.copyProjectId = function() {
    var id = window.currentProjectId || '';
    if (!id) { window.showToast('Нет активного проекта', 'error'); return; }
    navigator.clipboard.writeText(id).then(function() {
        window.showToast('Project ID скопирован: ' + id, 'success');
    }).catch(function() {
        // fallback for older browsers
        var ta = document.createElement('textarea');
        ta.value = id;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        window.showToast('Project ID скопирован: ' + id, 'success');
    });
};

async function loadDataPage() {
    try {
        var pResp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId);
        var p = await pResp.json();
        document.getElementById('dataMetaProjectName').textContent = p.name || '-';
        document.getElementById('dataMetaCode').textContent = p.code || '-';
        document.getElementById('dataMetaModels').textContent = p.models_count || '0';
    } catch(e) {}
    await loadDataCategories();
    countCategoryElements();
    // Reset to categories tab
    window.switchDataTab('categories');
}

async function loadDataCategories() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/categories');
        var data = await resp.json();
        dataCategories = (data.categories || []).map(function(c) {
            var cols = (c.columns && c.columns.length > 0) ? c.columns : window.getDefaultCols(c.name);
            // Migrate existing saved columns: add group from defaults if missing
            var defaults = window.getDefaultCols(c.name);
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
        var mResp = await fetch(window.API_BASE + '/models?project_id=' + window.currentProjectId);
        var mData = await mResp.json();
        var models = mData.models || [];
        for (var mi = 0; mi < models.length; mi++) {
            if (models[mi].status !== 'processed') continue;
            var eResp = await fetch(window.API_BASE + '/models/' + models[mi].id + '/elements');
            var eData = await eResp.json();
            var elems = eData.elements || [];
            for (var ei = 0; ei < elems.length; ei++) {
                var cat = window.categorizeElement(elems[ei]);
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
    document.getElementById('aiCheckResults').style.display = tab === 'ai-check' ? '' : 'none';
    document.getElementById('dataVendorTab').style.display = tab === 'vendor' ? '' : 'none';
    document.getElementById('dataChangesTab').style.display = tab === 'changes' ? '' : 'none';
    document.querySelector('.categories-only').style.display = tab === 'categories' ? '' : 'none';
    document.querySelector('.tz-only').style.display = tab === 'tz' ? '' : 'none';
    document.querySelector('.ai-check-only').style.display = tab === 'ai-check' ? '' : 'none';
    document.querySelector('.changes-only').style.display = tab === 'changes' ? '' : 'none';
    var labels = {
        'categories': 'Настройка категорий элементов модели',
        'tz': 'Редактирование технического задания',
        'ai-check': 'Проверка модели с использованием ИИ',
        'vendor': 'Анализ рекомендуемых производителей',
        'changes': 'Создание и отправка приказов на изменение модели в Revit',
    };
    document.getElementById('dataPageMeta').textContent = labels[tab] || '';
    if (tab === 'tz') loadTzSection();
    if (tab === 'ai-check') window.loadAiCheck();
    if (tab === 'vendor') loadVendorSection();
    if (tab === 'changes') window.loadChangesTab();
};

// ── TZ section: load, save, upload, AI parse ───────────────────

var _activePipelineSys = 'all';

function _emptyPipeline() {
    return { systems: [] };
}


// ── Manufacturers helpers ──

var _MFR_FIELDS = {};

function _loadManufacturers(mfr) {
    mfr = mfr || {};
    _MFR_FIELDS = {};
    var map = [
        ['mfr_ws_pumps','water_supply','pumps'], ['mfr_ws_valves','water_supply','valves'],
        ['mfr_ws_pipe','water_supply','pipe_fittings'], ['mfr_ws_insulation','water_supply','insulation'],
        ['mfr_ws_manifold','water_supply','manifold'], ['mfr_ws_additional','water_supply','additional'],
        ['mfr_sw_pumps','sewerage','pumps'], ['mfr_sw_valves','sewerage','valves'],
        ['mfr_sw_pipe','sewerage','pipe_fittings'], ['mfr_sw_insulation','sewerage','insulation'],
        ['mfr_sw_additional','sewerage','additional'],
        ['mfr_ff_pumps','fire_fighting','pumps'], ['mfr_ff_valves','fire_fighting','valves'],
        ['mfr_ff_pipe','fire_fighting','pipe_fittings'], ['mfr_ff_insulation','fire_fighting','insulation'],
        ['mfr_ff_additional','fire_fighting','additional'],
    ];
    map.forEach(function(row) {
        var elId = row[0], cat = row[1], key = row[2];
        _MFR_FIELDS[elId] = [cat, key];
        var el = document.getElementById(elId);
        if (el) el.value = ((mfr[cat] && mfr[cat][key]) || '');
    });
}

function _saveManufacturers() {
    var mfr = { water_supply: {}, sewerage: {}, fire_fighting: {} };
    for (var elId in _MFR_FIELDS) {
        var el = document.getElementById(elId);
        if (!el) continue;
        var cat = _MFR_FIELDS[elId][0], key = _MFR_FIELDS[elId][1];
        mfr[cat][key] = el.value;
    }
    return mfr;
}

function _renderPipelineSystems(filter) {
    filter = filter || 'all';
    var pd = window._tzPipelineData || _emptyPipeline();
    var systems = pd.systems || [];
    if (filter !== 'all') {
        systems = systems.filter(function(s) { return s.category === filter; });
    }
    var catLabels = { water_supply: '🚰 Водоснабжение', sewerage: '🧪 Водоотведение', fire_fighting: '🔥 Пожаротушение' };
    var container = document.getElementById('pipelineSystemsList');
    if (!systems.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-secondary);font-size:13px">Нет систем. Нажмите «+ Добавить систему»</div>';
        return;
    }
    container.innerHTML = systems.map(function(sys) {
        return '<div class="pipeline-system-card" data-sys-id="' + sys.id + '" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 16px">' +
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">' +
                '<span style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase">' + (catLabels[sys.category] || sys.category) + '</span>' +
                '<button onclick="removePipelineSystem(\'' + sys.id + '\')" style="background:none;border:none;color:var(--text-danger, #ef4444);font-size:18px;cursor:pointer;padding:0 4px" title="Удалить систему">✕</button>' +
            '</div>' +
            '<div style="display:grid;grid-template-columns:1fr 2fr 2fr 2fr 2fr;gap:8px;align-items:end">' +
                '<div><label style="font-size:11px;color:var(--text-secondary);display:block;margin-bottom:2px">Система</label>' +
                '<input class="pipe-sys-name" value="' + window.escHtml(sys.name || '') + '" placeholder="В1" style="width:100%;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px" /></div>' +
                '<div><label style="font-size:11px;color:var(--text-secondary);display:block;margin-bottom:2px">Материал</label>' +
                '<input class="pipe-sys-mat" value="' + window.escHtml(sys.material || '') + '" placeholder="сталь, чугун..." style="width:100%;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px" /></div>' +
                '<div><label style="font-size:11px;color:var(--text-secondary);display:block;margin-bottom:2px">Диаметры</label>' +
                '<input class="pipe-sys-dia" value="' + window.escHtml(sys.diameters || '') + '" placeholder="DN50, DN65..." style="width:100%;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px" /></div>' +
                '<div><label style="font-size:11px;color:var(--text-secondary);display:block;margin-bottom:2px">Изоляция</label>' +
                '<input class="pipe-sys-ins" value="' + window.escHtml(sys.insulation || '') + '" placeholder="минвата 50мм..." style="width:100%;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px" /></div>' +
                '<div><label style="font-size:11px;color:var(--text-secondary);display:block;margin-bottom:2px">Прокладка</label>' +
                '<input class="pipe-sys-lay" value="' + window.escHtml(sys.laying || '') + '" placeholder="подземная, надземная..." style="width:100%;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px" /></div>' +
            '</div>' +
        '</div>';
    }).join('');
}

function _readPipelineSystems() {
    var pd = JSON.parse(JSON.stringify(window._tzPipelineData || _emptyPipeline()));
    var systems = [];
    document.querySelectorAll('#pipelineSystemsList .pipeline-system-card').forEach(function(card) {
        var id = card.getAttribute('data-sys-id');
        var oldSys = (pd.systems || []).find(function(s) { return s.id === id; });
        systems.push({
            id: id,
            category: oldSys ? oldSys.category : 'water_supply',
            name: card.querySelector('.pipe-sys-name').value,
            material: card.querySelector('.pipe-sys-mat').value,
            diameters: card.querySelector('.pipe-sys-dia').value,
            insulation: card.querySelector('.pipe-sys-ins').value,
            laying: card.querySelector('.pipe-sys-lay').value,
        });
    });
    return { systems: systems };
}

// Sync only visible cards' values from DOM into _tzPipelineData
// without touching hidden systems (avoids losing them on tab switch)
function _saveVisibleToMemory() {
    var all = window._tzPipelineData;
    if (!all) return;
    document.querySelectorAll('#pipelineSystemsList .pipeline-system-card').forEach(function(card) {
        var id = card.getAttribute('data-sys-id');
        var match = (all.systems || []).find(function(s) { return s.id === id; });
        if (match) {
            match.name = card.querySelector('.pipe-sys-name').value;
            match.material = card.querySelector('.pipe-sys-mat').value;
            match.diameters = card.querySelector('.pipe-sys-dia').value;
            match.insulation = card.querySelector('.pipe-sys-ins').value;
            match.laying = card.querySelector('.pipe-sys-lay').value;
        }
    });
}

window.switchPipelineTab = function(sys) {
    _saveVisibleToMemory();
    _activePipelineSys = sys;
    document.querySelectorAll('.pipeline-tab').forEach(function(t) {
        t.classList.toggle('active', t.getAttribute('data-sys') === sys);
    });
    _renderPipelineSystems(sys);
};

window.addPipelineSystem = function() {
    if (!window._tzPipelineData) window._tzPipelineData = _emptyPipeline();
    if (!window._tzPipelineData.systems) window._tzPipelineData.systems = [];
    var cat = document.getElementById('newSystemCategory').value;
    var newId = 'sys_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
    window._tzPipelineData.systems.push({ id: newId, category: cat, name: '', material: '', diameters: '', insulation: '', laying: '' });
    _renderPipelineSystems(_activePipelineSys);
};

window.removePipelineSystem = function(id) {
    if (!confirm('Удалить систему?')) return;
    if (!window._tzPipelineData) window._tzPipelineData = _emptyPipeline();
    if (!window._tzPipelineData.systems) window._tzPipelineData.systems = [];
    window._tzPipelineData.systems = window._tzPipelineData.systems.filter(function(s) { return s.id !== id; });
    _renderPipelineSystems(_activePipelineSys);
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
        var date = f.uploaded_at ? new Date(f.uploaded_at + 'Z').toLocaleString('ru-RU') : '';
        var selected = f.stored_name === _selectedTzFile;
        var label = f.display_name || f.stored_name;
        return '<label style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;background:' + (selected ? 'var(--accent-light)' : 'transparent') + ';cursor:pointer">' +
            '<input type="radio" name="tzFile" value="' + f.stored_name + '" ' + (selected ? 'checked' : '') + ' onchange="selectTzFile(\'' + f.stored_name + '\')" />' +
            '<span style="flex:1;font-size:13px">' + window.escHtml(label) + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + size + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + date + '</span>' +
            '<span style="cursor:pointer;color:var(--text-danger, #ef4444);font-size:16px;padding:0 6px;font-weight:bold" onclick="event.stopPropagation();deleteTzFile(\'' + f.stored_name + '\')" title="Удалить файл">✕</span>' +
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
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz');
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
        _activePipelineSys = 'all';
        document.querySelectorAll('.pipeline-tab').forEach(function(t) {
            t.classList.toggle('active', t.getAttribute('data-sys') === 'all');
        });
        _renderPipelineSystems(_activePipelineSys);

        // File list
        _tzFileList = data.tz_files || [];
        if (_tzFileList.length && !_selectedTzFile) {
            _selectedTzFile = _tzFileList[0].stored_name;
        }
        _renderTzFileList();

        loadTzHistory();
    } catch (e) {
        window.showToast('Ошибка загрузки ТЗ: ' + e.message, 'error');
    }
}

async function loadTzHistory() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz/history');
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
            var date = v.created_at ? new Date(v.created_at + 'Z').toLocaleString('ru-RU') : '';
            return '<div class="tz-history-item">' +
                '<span>Версия ' + v.version + '</span>' +
                '<span class="tz-history-source">' + src + '</span>' +
                '<span style="color:var(--text-secondary)">' + date + '</span>' +
            '</div>';
        }).join('');
    } catch(e) {}
}

window.saveTzSection = async function() {
    // Merge visible card values into memory, keep hidden systems intact
    _saveVisibleToMemory();
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
        pipeline_data: pd,
    };
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('ТЗ сохранено', 'success');
        loadTzHistory();
    } catch (e) {
        window.showToast('Ошибка сохранения: ' + e.message, 'error');
    }
};

window.uploadTzFile = async function(file) {
    if (!file) return;
    var form = new FormData();
    form.append('file', file);
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz/upload', {
            method: 'POST',
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Файл загружен', 'success');
        loadTzSection();
    } catch (e) {
        window.showToast('Ошибка загрузки файла: ' + e.message, 'error');
    }
};

window.downloadTzFile = function() {
    if (!_selectedTzFile) return;
    window.open(window.API_BASE + '/projects/' + window.currentProjectId + '/tz/file?filename=' + encodeURIComponent(_selectedTzFile), '_blank');
};

window.deleteTzFile = async function(storedName) {
    if (!confirm('Удалить файл ' + storedName + '?')) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz/files?filename=' + encodeURIComponent(storedName), {
            method: 'DELETE',
        });
        if (!resp.ok) {
            var err = await resp.json().catch(function(){return null});
            throw new Error((err && err.detail) || 'HTTP ' + resp.status);
        }
        if (_selectedTzFile === storedName) {
            _selectedTzFile = '';
        }
        window.showToast('Файл удалён', 'success');
        loadTzSection();
    } catch (e) {
        window.showToast('Ошибка удаления: ' + e.message, 'error');
    }
};

window.parseTzAi = async function() {
    var btn = document.getElementById('btnParseTz');
    if (!_selectedTzFile) {
        window.showToast('Выберите файл для распознавания', 'error');
        return;
    }
    btn.disabled = true;
    btn.textContent = '⏳ Распознавание...';
    try {
        var url = window.API_BASE + '/projects/' + window.currentProjectId + '/tz/parse?filename=' + encodeURIComponent(_selectedTzFile);
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
        html += '<input class="form-input preview-tz-field" id="pv_address" value="' + window.escHtml(data.project_address || '') + '" /></div>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Секций</label><input class="form-input preview-tz-field" id="pv_sections" value="' + window.escHtml(data.sections_count || '') + '" /></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Этажей</label><input class="form-input preview-tz-field" id="pv_floors" value="' + window.escHtml(data.floors_count || '') + '" /></div>';
        html += '</div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">BIM-требования</label>';
        html += '<input class="form-input preview-tz-field" id="pv_bim" value="' + window.escHtml(data.bim_requirements || '') + '" /></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Общее описание</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_general" rows="3">' + window.escHtml(data.tz_general || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Водоснабжение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_ws" rows="2">' + window.escHtml(data.tz_water_supply || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Водоотведение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_sew" rows="2">' + window.escHtml(data.tz_sewerage || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Пожаротушение</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_ff" rows="2">' + window.escHtml(data.tz_fire_fighting || '') + '</textarea></div>';
        html += '<div class="form-group"><label class="form-label" style="font-size:12px;text-transform:uppercase;color:var(--text-secondary)">Прочие</label>';
        html += '<textarea class="form-textarea preview-tz-field" id="pv_other" rows="2">' + window.escHtml(data.tz_other || '') + '</textarea></div>';

        // Pipeline data preview — show individual systems
        var pd = data.pipeline_data || {};
        var systems = pd.systems || [];
        var catLabels = { water_supply: '🚰 Водоснабжение', sewerage: '🧪 Водоотведение', fire_fighting: '🔥 Пожаротушение' };
        html += '<div style="margin-top:12px"><div style="font-size:12px;text-transform:uppercase;color:var(--text-secondary);font-weight:600;margin-bottom:8px">Трубопроводные системы</div>';
        if (systems.length) {
            systems.forEach(function(sys, idx) {
                html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px;flex-wrap:wrap">' +
                    '<span style="font-size:12px;font-weight:600;color:var(--accent);min-width:140px">' + (catLabels[sys.category] || sys.category) + '</span>' +
                    '<input class="form-input preview-tz-field" id="pv_sys_' + idx + '_name" value="' + window.escHtml(sys.name || '') + '" placeholder="Система" style="max-width:100px" />' +
                    '<input class="form-input preview-tz-field" id="pv_sys_' + idx + '_mat" value="' + window.escHtml(sys.material || '') + '" placeholder="Материал" style="max-width:140px" />' +
                    '<input class="form-input preview-tz-field" id="pv_sys_' + idx + '_dia" value="' + window.escHtml(sys.diameters || '') + '" placeholder="Диаметры" style="max-width:140px" />' +
                    '<input class="form-input preview-tz-field" id="pv_sys_' + idx + '_ins" value="' + window.escHtml(sys.insulation || '') + '" placeholder="Изоляция" style="max-width:140px" />' +
                    '<input class="form-input preview-tz-field" id="pv_sys_' + idx + '_lay" value="' + window.escHtml(sys.laying || '') + '" placeholder="Прокладка" style="max-width:140px" />' +
                '</div>';
            });
        } else {
            html += '<div style="font-size:12px;color:var(--text-secondary)">AI не определил системы</div>';
        }
        html += '</div>';

        // Raw GPT response & prompt
        if (data._raw_gpt || data._raw_prompt) {
            html += '<details style="margin-top:16px">' +
                '<summary style="cursor:pointer;font-size:12px;color:var(--text-secondary)">📜 Промпт и ответ GPT</summary>' +
                (data._raw_prompt ? '<div style="margin-top:8px"><div style="font-size:11px;text-transform:uppercase;color:var(--text-secondary);margin-bottom:4px">Промпт (system + user):</div>' +
                '<pre style="padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;font-size:11px;line-height:1.4;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto">' + window.escHtml(data._raw_prompt) + '</pre></div>' : '') +
                (data._raw_gpt ? '<div style="margin-top:8px"><div style="font-size:11px;text-transform:uppercase;color:var(--text-secondary);margin-bottom:4px">Ответ GPT:</div>' +
                '<pre style="padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;font-size:11px;line-height:1.4;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto">' + window.escHtml(data._raw_gpt) + '</pre></div>' : '') +
            '</details>';
        }

        document.getElementById('tzPreviewContent').innerHTML = html;
        window.openModal('tzPreviewModal');
    } catch (e) {
        window.showToast('Ошибка распознавания: ' + e.message, 'error');
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
    var pdPreview = window._tzPreviewData && window._tzPreviewData.pipeline_data;
    if (pdPreview) {
        var previewSystems = pdPreview.systems || [];
        // Read AI systems from preview modal (user may have edited them)
        var aiSystems = [];
        previewSystems.forEach(function(sys, idx) {
            var nameEl = document.getElementById('pv_sys_' + idx + '_name');
            if (!nameEl) return;
            aiSystems.push({
                id: sys.id || '',
                category: sys.category || 'water_supply',
                name: nameEl.value,
                material: (document.getElementById('pv_sys_' + idx + '_mat') || {}).value || '-',
                diameters: (document.getElementById('pv_sys_' + idx + '_dia') || {}).value || '-',
                insulation: (document.getElementById('pv_sys_' + idx + '_ins') || {}).value || '-',
                laying: (document.getElementById('pv_sys_' + idx + '_lay') || {}).value || '-',
            });
        });
        if (aiSystems.length) {
            // Merge with existing systems — skip if name+category already exists
            var existing = window._tzPipelineData || { systems: [] };
            if (!existing.systems) existing.systems = [];
            var existingKeys = {};
            existing.systems.forEach(function(s) {
                existingKeys[s.category + '|' + s.name] = true;
            });
            aiSystems.forEach(function(aiSys) {
                var key = aiSys.category + '|' + aiSys.name;
                if (!existingKeys[key]) {
                    existing.systems.push({
                        id: aiSys.id || ('sys_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)),
                        category: aiSys.category,
                        name: aiSys.name,
                        material: aiSys.material,
                        diameters: aiSys.diameters,
                        insulation: aiSys.insulation,
                        laying: aiSys.laying,
                    });
                }
            });
            var hasAny = existing.systems.some(function(s) { return s.name && s.name !== '-'; });
            if (hasAny) data.pipeline_data = existing;
        }
    }

    if (Object.keys(data).length === 0) {
        window.showToast('Нет данных для сохранения', 'warning');
        window.closeModal('tzPreviewModal');
        return;
    }

    // Save to DB
    fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/tz', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
    .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        window.showToast('ТЗ сохранено', 'success');
        window.closeModal('tzPreviewModal');
        loadTzSection();
        loadTzHistory();
        return r.json();
    })
    .catch(function(e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    });
};

// ── Data Categories Editor ────────────────────────────────────

function renderDataCategories() {
    var el = document.getElementById('dataCatList');
    if (!dataCategories.length) {
        el.innerHTML = '<div class="empty-message" style="padding:40px;text-align:center;color:var(--text-secondary)">Нет категорий. Добавьте новую.</div>';
        return;
    }
    el.innerHTML = dataCategories.map(function(cat, i) {
        var c = window.CATEGORY_ICONS[cat.name] || { color: '#6b7280', icon: '?' };
        var cols = cat.columns || [];
        var colsHtml = '';
        function renderColRow(col, origIdx) {
            var delBtn = '<span class="data-col-del" onclick="deleteColumn(' + i + ',' + origIdx + ')" title="Удалить параметр">✕</span>';
            if (col.composite) {
                var hint = 'составной: ' + col.composite.join(' + ');
                return '<div class="data-col-row" data-ci="' + origIdx + '">' +
                    '<input class="data-col-label" value="' + window.escHtml(col.label) + '" placeholder="Название" />' +
                    '<span class="data-col-composite-hint">' + window.escHtml(hint) + '</span>' +
                    delBtn +
                '</div>';
            }
            var keysStr = (col.keys || []).join(', ');
            return '<div class="data-col-row" data-ci="' + origIdx + '">' +
                '<input class="data-col-label" value="' + window.escHtml(col.label) + '" placeholder="Название" />' +
                '<input class="data-col-keys" value="' + window.escHtml(keysStr) + '" placeholder="ключи через запятую" />' +
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
            '<span class="cat-name" onclick="editCategoryName(' + i + ', this)">' + window.escHtml(cat.name) + '</span>' +
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
                window.showToast('Категория с таким именем уже существует', 'error');
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
        window.showToast('Категория уже существует', 'error');
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
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/categories', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Категории и параметры сохранены', 'success');
        var names = dataCategories.map(function(c) { return c.name; });
        window.CATEGORIES = names;
        window.CATEGORY_ICONS = window.buildCategoryIcons(names);
        // Rebuild __CATEGORY_COLUMNS from saved data
        window.__CATEGORY_COLUMNS = dataCategories.map(function(c) {
            return { cat: c.name, cols: (c.columns && c.columns.length) ? c.columns : window.getDefaultCols(c.name) };
        });
        await loadDataCategories();
        countCategoryElements();
    } catch (e) {
        window.showToast('Ошибка: ' + e.message, 'error');
    }
};

// ── Vendor section ─────────────────────────────────────────────

var _vendorFiles = [];
var _selectedVendorFile = '';
var _vendorResult = null;

function _renderVendorFileList() {
    var el = document.getElementById('vendorFileList');
    var btnParse = document.getElementById('btnParseVendor');
    var btnDl = document.getElementById('btnDownloadVendor');
    if (!_vendorFiles.length) {
        el.innerHTML = 'Файлов нет — загрузите PDF или Excel с ведомостью производителей';
        btnParse.disabled = true;
        btnDl.style.display = 'none';
        return;
    }
    btnParse.disabled = false;
    var html = _vendorFiles.map(function(f) {
        var size = f.size_bytes < 1024 ? f.size_bytes + ' B' : (f.size_bytes / 1024).toFixed(1) + ' KB';
        var date = f.uploaded_at ? new Date(f.uploaded_at + 'Z').toLocaleString('ru-RU') : '';
        var selected = f.stored_name === _selectedVendorFile;
        var label = f.display_name || f.stored_name;
        return '<label style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;background:' + (selected ? 'var(--accent-light)' : 'transparent') + ';cursor:pointer">' +
            '<input type="radio" name="vendorFile" value="' + f.stored_name + '" ' + (selected ? 'checked' : '') + ' onchange="selectVendorFile(\'' + f.stored_name + '\')" />' +
            '<span style="flex:1;font-size:13px">' + window.escHtml(label) + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + size + '</span>' +
            '<span style="font-size:11px;color:var(--text-secondary)">' + date + '</span>' +
            '<span style="cursor:pointer;color:var(--text-secondary);opacity:0.4;font-size:14px;padding:0 4px" onclick="event.stopPropagation();deleteVendorFile(\'' + f.stored_name + '\')" title="Удалить">✕</span>' +
        '</label>';
    }).join('');
    el.innerHTML = html;
    btnDl.style.display = _selectedVendorFile ? '' : 'none';
}

window.selectVendorFile = function(storedName) {
    _selectedVendorFile = storedName;
    _renderVendorFileList();
};

window.uploadVendorFile = async function(file) {
    if (!file) return;
    var form = new FormData();
    form.append('file', file);
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/vendor/upload', {
            method: 'POST',
            body: form,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Файл загружен', 'success');
        await loadVendorSection();
    } catch (e) {
        window.showToast('Ошибка загрузки: ' + e.message, 'error');
    }
};

window.downloadVendorFile = function() {
    if (!_selectedVendorFile) return;
    window.open(window.API_BASE + '/projects/' + window.currentProjectId + '/vendor/file?filename=' + encodeURIComponent(_selectedVendorFile), '_blank');
};

window.deleteVendorFile = async function(storedName) {
    if (!confirm('Удалить файл ' + storedName + '?')) return;
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/vendor/files?filename=' + encodeURIComponent(storedName), {
            method: 'DELETE',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        if (_selectedVendorFile === storedName) _selectedVendorFile = '';
        window.showToast('Файл удалён', 'success');
        await loadVendorSection();
    } catch (e) {
        window.showToast('Ошибка удаления: ' + e.message, 'error');
    }
};

window.parseVendorAi = async function() {
    var btn = document.getElementById('btnParseVendor');
    if (!_selectedVendorFile) {
        window.showToast('Выберите файл для анализа', 'error');
        return;
    }
    btn.disabled = true;
    btn.textContent = '⏳ Анализ...';
    try {
        var url = window.API_BASE + '/projects/' + window.currentProjectId + '/vendor/parse?filename=' + encodeURIComponent(_selectedVendorFile);
        var resp = await fetch(url, { method: 'POST' });
        if (!resp.ok) {
            var errBody = '';
            try { var errJson = await resp.json(); errBody = errJson.detail || JSON.stringify(errJson); } catch(e2) { errBody = await resp.text(); }
            throw new Error(errBody || 'HTTP ' + resp.status);
        }
        var parsed = await resp.json();
        _vendorResult = {};
        for (var k in parsed) {
            if (k === '_manufacturers') continue;
            _vendorResult[k] = parsed[k];
        }
        _renderVendorResult();
        if (parsed._manufacturers) {
            _loadManufacturers(parsed._manufacturers);
        }
        window.showToast('Анализ завершён', 'success');
    } catch (e) {
        window.showToast('Ошибка анализа: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Проанализировать производителей';
    }
};

function _renderVendorResult() {
    var el = document.getElementById('vendorResult');
    if (!_vendorResult || Object.keys(_vendorResult).length === 0) {
        el.innerHTML = '<div class="empty-message">Нет данных. Загрузите файл и нажмите "Проанализировать".</div>';
        return;
    }

    var html = '';
    var sections = [
        { key: 'general_notes', label: 'Общие указания' },
        { key: 'water_supply_manufacturers', label: '🚰 Водоснабжение' },
        { key: 'sewerage_manufacturers', label: '🧪 Водоотведение' },
        { key: 'fire_fighting_manufacturers', label: '🔥 Пожаротушение' },
        { key: 'heating_manufacturers', label: '🌡 Отопление' },
        { key: 'ventilation_manufacturers', label: '💨 Вентиляция и кондиционирование' },
        { key: 'electrical_manufacturers', label: '⚡ Электроснабжение' },
        { key: 'low_current_manufacturers', label: '🔌 Слаботочные системы' },
        { key: 'pumps_manufacturers', label: '🔄 Насосное оборудование' },
        { key: 'valves_manufacturers', label: '🔧 Запорно-регулирующая арматура' },
        { key: 'insulation_manufacturers', label: '📦 Изоляционные материалы' },
        { key: 'water_treatment_manufacturers', label: '💧 Водоподготовка' },
        { key: 'automation_manufacturers', label: '🤖 Автоматизация' },
    ];

    sections.forEach(function(s) {
        var val = _vendorResult[s.key];
        if (val && val.trim()) {
            html += '<div style="margin-bottom:12px">' +
                '<div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:4px">' + s.label + '</div>' +
                '<div style="font-size:13px;line-height:1.5;padding:8px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;white-space:pre-wrap">' + window.escHtml(val) + '</div>' +
            '</div>';
        }
    });

    if (!html) {
        html = '<div class="empty-message">AI не извлёк данных о производителях из файла</div>';
    }

    el.innerHTML = html;
}

async function loadVendorSection() {
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/vendor');
        if (!resp.ok) return;
        var data = await resp.json();
        _vendorFiles = data.files || [];
        _selectedVendorFile = data.selected || (_vendorFiles.length ? _vendorFiles[0].stored_name : '');
        _vendorResult = data.result || null;
        _renderVendorFileList();
        _renderVendorResult();
        _loadManufacturers(data.manufacturers || {});
        document.getElementById('vendorFields').style.display = 'block';
    } catch (e) {
        // ignore
    }
}

window.saveVendorSection = async function() {
    var mfr = _saveManufacturers();
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/vendor', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ manufacturers: mfr }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        window.showToast('Производители сохранены', 'success');
    } catch (e) {
        window.showToast('Ошибка сохранения: ' + e.message, 'error');
    }
};
