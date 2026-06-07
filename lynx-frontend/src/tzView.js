var tzAllElements = [];
var tzActiveCategory = '';
var tzSearchQuery = '';

window.showTzPage = function() {
    if (!window.currentProjectId) return;
    document.getElementById('tzView').classList.add('active');
    document.getElementById('breadcrumb').innerHTML = [
        '<span class="link" onclick="goHome()">Проекты</span>',
        '<span>/</span>',
        '<span class="link" onclick="showProject(\'' + window.currentProjectId + '\')">' + window.escHtml(window.getProjectName(window.currentProjectId)) + '</span>',
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
    window.showProject(window.currentProjectId);
};

async function loadTzPage() {
    await window.loadCategories();
    try {
        var pResp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId);
        var p = await pResp.json();
        document.getElementById('tzMetaCode').textContent = p.code || '-';
        document.getElementById('tzMetaModels').textContent = p.models_count || '0';
        document.getElementById('tzMetaKeywords').textContent = p.auto_bind_keywords || '-';
    } catch (e) {
        // fallback
    }
    loadTzElements();
}
window.loadTzPage = loadTzPage;

var tzSelectedModelId = '';

async function loadTzElements() {
    document.getElementById('tzPageTitle').textContent = 'Элементы';
    document.getElementById('tzPageMeta').textContent = 'Загрузка...';
    document.getElementById('tzModelSelector').disabled = true;

    var allCatElems = {};
    for (var i = 0; i < window.CATEGORIES.length; i++) {
        allCatElems[window.CATEGORIES[i]] = [];
    }

    var allIfcClasses = {};
    var totalCount = 0;

    try {
        var mResp = await fetch(window.API_BASE + '/models?project_id=' + window.currentProjectId);
        var mData = await mResp.json();
        var projectModels = mData.models || [];
        document.getElementById('tzModelCount').textContent = projectModels.length;

        // Populate model selector
        var sel = document.getElementById('tzModelSelector');
        var prevVal = tzSelectedModelId || (window.selectedModelId ? window.selectedModelId : '');
        sel.innerHTML = '<option value="">— Все модели —</option>' +
            projectModels.map(function(m) {
                var label = window.escHtml(m.model_name) + ' v' + (m.version_number !== null && m.version_number !== undefined ? m.version_number : '?');
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
                var eResp = await fetch(window.API_BASE + '/models/' + m.id + '/elements');
                var eData = await eResp.json();
                var elems = eData.elements || [];
                for (var j = 0; j < elems.length; j++) {
                    var el = elems[j];
                    el._modelName = m.model_name;
                    el._modelVersion = m.version_number;
                    var cat = window.categorizeElement(el);
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
    for (var i = 0; i < window.CATEGORIES.length; i++) {
        tzAllElements = tzAllElements.concat(allCatElems[window.CATEGORIES[i]]);
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
    for (var i = 0; i < window.CATEGORIES.length; i++) {
        var cat = window.CATEGORIES[i];
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
    if (tzActiveCategory && window.CATEGORIES.indexOf(tzActiveCategory) >= 0) {
        filteredList = tzAllElements.filter(function(e) { return window.categorizeElement(e) === tzActiveCategory; });
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
    if (cat && window.CATEGORIES.indexOf(cat) >= 0) {
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
            var cat = window.categorizeElement(e);
            return cat === tzActiveCategory || e.ifc_class === tzActiveCategory;
        });
    }

    if (tzSearchQuery) {
        filtered = filtered.filter(function(e) {
            var name = (e.name || '').toLowerCase();
            var cls = (e.ifc_class || '').toLowerCase();
            var storey = (e.storey_name || '').toLowerCase();
            var system = (e.system_name || '').toLowerCase();
            var cat = window.categorizeElement(e).toLowerCase();
            // Also search through raw_psets values
            var psetsStr = JSON.stringify(e.raw_psets_jsonb || {}).toLowerCase();
            return name.indexOf(tzSearchQuery) >= 0 || cls.indexOf(tzSearchQuery) >= 0 ||
                storey.indexOf(tzSearchQuery) >= 0 || system.indexOf(tzSearchQuery) >= 0 ||
                cat.indexOf(tzSearchQuery) >= 0 || psetsStr.indexOf(tzSearchQuery) >= 0;
        });
    }

    // Determine columns based on active category
    var activeCatCols = tzActiveCategory && window.CATEGORIES.indexOf(tzActiveCategory) >= 0
        ? window.getColsForCategory(tzActiveCategory) : [];
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

    var cols = tzActiveCategory && window.CATEGORIES.indexOf(tzActiveCategory) >= 0
        ? window.getColsForCategory(tzActiveCategory) : [
            { label: 'Часть системы', keys: ['BRU_ЧастьСистемы', 'Bru_ЧастьСистемы', 'Часть системы', 'SystemPart'] },
            { label: 'Система', keys: ['BRU_Система', 'Bru_Система', 'Система', 'System'] },
            { label: 'Этаж', keys: ['ADSK_Этаж', 'Этаж', 'Storey', 'Level'] },
        ];

    container.innerHTML = filtered.map(function(e) {
        var cat = window.categorizeElement(e);
        var c = window.CATEGORY_ICONS[cat] || { color: '#6b7280', icon: '?' };
        var propsHtml = cols.map(function(col) {
            var val;
            if (col.composite) {
                var parts = [];
                for (var si = 0; si < col.composite.length; si++) {
                    for (var di = 0; di < cols.length; di++) {
                        if (cols[di].label === col.composite[si]) {
                            var srcVal = window.extractProp(e.raw_psets_jsonb, cols[di].keys);
                            if (srcVal !== null && srcVal !== undefined) parts.push(String(srcVal).trim());
                            break;
                        }
                    }
                }
                val = parts.length ? parts.join(' ') : null;
            } else {
                val = window.extractProp(e.raw_psets_jsonb, col.keys);
            }
            var displayVal = window.formatValue(val);
            var emptyCls = displayVal ? '' : ' empty';
            return '<div class="tz-card-prop"><span class="tz-card-prop-key">' + window.escHtml(col.label) + ':</span><span class="tz-card-prop-val' + emptyCls + '">' + window.escHtml(displayVal || '\u2014') + '</span></div>';
        }).join('');
        return '<div class="tz-card" onclick="tzSelectElement(\'' + window.escHtml(e.global_id) + '\')">' +
            '<div class="tz-card-header">' +
                '<span class="class-icon" style="border-color:' + c.color + ';background:' + c.color + '"></span>' +
                '<span class="tz-card-name">' + window.escHtml(e.name || '(без имени)') + '</span>' +
                '<span class="tz-card-cat">' + window.escHtml(cat) + '</span>' +
            '</div>' +
            '<div class="tz-card-props">' + propsHtml + '</div>' +
        '</div>';
    }).join('');

    document.getElementById('tzCount').textContent = filtered.length;
}

window.tzSelectElement = function(globalId) {
    window.goToProject();
};
