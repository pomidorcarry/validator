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
    if (tab === 'ai-check') window.loadAiCheck();
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
            '<td><input class="pipe-mat" data-sys="' + sys + '" data-sec="' + sec + '" value="' + window.escHtml(secData.material || '') + '" placeholder="-"></td>' +
            '<td><input class="pipe-dia" data-sys="' + sys + '" data-sec="' + sec + '" value="' + window.escHtml(secData.diameter || '') + '" placeholder="-"></td>' +
            '<td><input class="pipe-ins" data-sys="' + sys + '" data-sec="' + sec + '" value="' + window.escHtml(secData.insulation || '') + '" placeholder="-"></td>' +
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
            '<span style="flex:1;font-size:13px">' + window.escHtml(label) + '</span>' +
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
                        (mat ? 'мат: ' + window.escHtml(mat) : '') + (dia ? ', d: ' + window.escHtml(dia) : '') + (ins ? ', изол: ' + window.escHtml(ins) : '') + '</div>';
                }
            });
        });
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
