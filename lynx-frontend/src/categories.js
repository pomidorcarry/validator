// ── Categories ──────────────────────────────────────────────────

window.CATEGORIES = [];
window.CATEGORY_ICONS = {};

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
window.buildCategoryIcons = buildCategoryIcons;

// Category-specific column configs: which IFC properties to show per category
window.__CATEGORY_COLUMNS = [];

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
window.getDefaultCols = getDefaultCols;

function getColsForCategory(cat) {
    for (var i = 0; i < window.__CATEGORY_COLUMNS.length; i++) {
        if (window.__CATEGORY_COLUMNS[i].cat === cat) return window.__CATEGORY_COLUMNS[i].cols;
    }
    return [];
}
window.getColsForCategory = getColsForCategory;

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
window.extractProp = extractProp;

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
window.formatValue = formatValue;

async function loadCategories() {
    if (!window.currentProjectId) return [];
    try {
        var resp = await fetch(window.API_BASE + '/projects/' + window.currentProjectId + '/categories');
        var data = await resp.json();
        var list = data.categories.map(function(c) { return c.name; });
        window.CATEGORIES = list;
        window.CATEGORY_ICONS = buildCategoryIcons(list);
        window.__CATEGORY_COLUMNS = data.categories.map(function(c) {
            return { cat: c.name, cols: (c.columns && c.columns.length) ? c.columns : getDefaultCols(c.name) };
        });
        return list;
    } catch(e) {
        return window.CATEGORIES.length ? window.CATEGORIES : ['Невалидируемое семейство'];
    }
}
window.loadCategories = loadCategories;

function categorizeElement(el) {
    var group = (el.model_group || '').trim().toLowerCase();
    for (var i = 0; i < window.CATEGORIES.length; i++) {
        if (group.indexOf(window.CATEGORIES[i].toLowerCase()) >= 0) {
            return window.CATEGORIES[i];
        }
    }
    return 'Невалидируемое семейство';
}
window.categorizeElement = categorizeElement;
