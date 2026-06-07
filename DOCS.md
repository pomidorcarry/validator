# Lynx — Документация программной системы

> Текущая версия: **0.3.0**
> Дата: May 2026

---

## Общее описание

**Lynx** — гибридная openBIM-система для автоматической проверки BIM-моделей. Состоит из трёх компонентов:

1. **Revit-плагин** — экспортирует IFC из Revit и отправляет на сервер
2. **FastAPI Backend** — принимает, обрабатывает, проверяет модели + AI-модули
3. **Frontend (Vanilla JS SPA)** — управление проектами, 3D-просмотр, редактирование ТЗ, AI-проверка

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│  Revit Plugin (C#, .NET 4.8)                                   │
│  Export IFC → Upload → Apply Fixes ← (fix_instructions)        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Lynx Backend (FastAPI, Python 3.13)                            │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ API Routers │  │  Services    │  │  DB (SQLite)          │   │
│  │ /v1/        │  │  ifc_norm    │  │  Project, ModelVersion│   │
│  │  models     │  │  rule_engine  │  │  Element, Issue       │   │
│  │  projects   │  │  tz_parser    │  │  TzVersion, Ruleset   │   │
│  │  tz         │  │  ai_check     │  │  AiCheck (file)      │   │
│  │  categories │  │  fix_generator│  │  FixSuggest (file)   │   │
│  │  ai-check   │  │  xkt_convert  │  │                      │   │
│  │  fix-suggest│  └──────────────┘  └───────────────────────┘   │
│  └─────────────┘                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Lynx Frontend (Vanilla JS, Vite, Three.js/xeokit)             │
│                                                                 │
│  Modules: navigation, projects, models, tzView,                 │
│           dataView, aiCheck, categories, themes, utils          │
└─────────────────────────────────────────────────────────────────┘
```

---

# Часть 1: Revit Плагин (lynx-revit-plugin)

## Назначение

Плагин для Autodesk Revit 2025 для:
- Экспорта модели в IFC4 и отправки на сервер Lynx
- Применения AI-исправлений (установка параметров элементов)

## Структура

```
lynx-revit-plugin/
├── LynxRevitPlugin.csproj     # .NET 4.8, Windows Forms
├── LynxRevitPlugin.addin      # Манифест Revit
├── App.cs                     # Вкладка "Lynx" с кнопками
├── ExportIfcCommand.cs        # Экспорт IFC + Upload
├── SettingsCommand.cs         # Настройки подключения
├── SettingsForm.cs            # WinForms форма настроек
├── ApplyFixesCommand.cs       # Применение AI-исправлений
├── FixReviewForm.cs           # WinForms предпросмотр fix'ов
├── ExportProgressForm.cs      # Прогресс экспорта
├── ProgressFileStream.cs      # Stream с прогрессом
└── ProgressFormHandle.cs      # Хендл формы прогресса
```

## Кнопки на панели Lynx

| Кнопка | Команда | Описание |
|--------|---------|----------|
| Экспорт в Lynx | ExportIfcCommand | IFC export → multipart upload |
| Настройки | SettingsCommand | URL, Project ID, Ruleset ID |
| Применить исправления | ApplyFixesCommand | Fetch approved fixes → apply |

## ApplyFixesCommand — логика

1. GET `/api/v1/projects/{id}/fix-suggestions?status=approved`
2. Показать FixReviewForm (чекбоксы, risk-индикация)
3. Для каждого выбранного fix'а:
   - Поиск элемента: IfcGUID → UniqueId → поиск по параметрам
   - `Transaction { LookupParameter(name).Set(value) }`
   - POST `/api/v1/projects/{id}/fix-suggestions/{fix_id}/result`
4. TaskDialog с итогом

---

# Часть 2: Backend (lynx-backend)

## Структура

```
lynx-backend/
├── app/
│   ├── main.py                    # FastAPI app + include_router
│   ├── core/
│   │   └── config.py              # Pydantic settings
│   ├── db/
│   │   └── models.py              # SQLAlchemy ORM + CRUD
│   ├── api/v1/
│   │   ├── health.py              # GET /health
│   │   ├── ai_status.py           # GET /ai/status
│   │   ├── projects_api.py        # CRUD проектов
│   │   ├── models_api.py          # CRUD моделей + sub-routes
│   │   ├── categories_api.py      # Категории элементов
│   │   ├── tz_api.py              # ТЗ: файлы, распознавание, история
│   │   ├── ai_check_api.py        # AI-проверка
│   │   └── fix_suggestions_api.py # AI-исправления
│   └── services/
│       ├── ifc_normalizer.py      # IfcOpenShell нормализация
│       ├── rule_engine.py         # Проверка правил
│       ├── xkt_converter.py       # IFC → XKT (xeokit)
│       └── ai/
│           ├── client.py          # AsyncOpenAI клиент
│           ├── tz_parser.py       # Парсинг ТЗ (PDF → AI → JSON)
│           ├── ai_check.py        # Сравнение элементов с ТЗ/СП
│           └── fix_generator.py   # AI-генерация инструкций по исправлению
├── pyproject.toml
├── requirements.txt
└── storage/                       # Файловое хранилище
    ├── raw/                       # IFC файлы
    ├── xkt/                       # XKT файлы (xeokit)
    ├── tz/                        # Загруженные ТЗ-файлы
    ├── ai_check/                  # Результаты AI-проверки
    └── fix_suggestions/           # AI-исправления
```

## API Endpoints

### Health & AI Status
- `GET /` — мета-информация
- `GET /api/v1/health` — здоровье
- `GET /api/v1/ai/status` — статус OpenAI (конфигурация + check)

### Projects
- `GET /api/v1/projects` — список
- `POST /api/v1/projects` — создать
- `GET /api/v1/projects/{id}` — детали
- `PUT /api/v1/projects/{id}` — обновить
- `DELETE /api/v1/projects/{id}` — удалить

### Project Categories
- `GET /api/v1/projects/{id}/categories` — список категорий
- `PUT /api/v1/projects/{id}/categories` — сохранить

### Models
- `POST /api/v1/models/upload` — загрузить IFC (202)
- `GET /api/v1/models` — список (фильтр `?project_id=`)
- `GET /api/v1/models/{id}` — детали
- `DELETE /api/v1/models/{id}` — удалить
- `DELETE /api/v1/models` — удалить все
- `GET /api/v1/models/{id}/status` — статус обработки
- `GET /api/v1/models/{id}/issues` — ошибки валидации
- `GET /api/v1/models/{id}/elements` — элементы модели
- `POST /api/v1/models/{id}/reprocess-rules` — перезапуск правил
- `GET /api/v1/models/{id}/ifc` — скачать IFC
- `GET /api/v1/models/{id}/xkt` — скачать XKT
- `PUT /api/v1/models/{id}/move` — переместить в другой проект

### TZ (Technical Specification)
- `GET /api/v1/projects/{id}/tz` — все поля + файлы
- `PUT /api/v1/projects/{id}/tz` — сохранить (JSON)
- `GET /api/v1/projects/{id}/tz/history` — история версий
- `POST /api/v1/projects/{id}/tz/upload` — загрузить PDF/Excel
- `GET /api/v1/projects/{id}/tz/files` — список файлов
- `DELETE /api/v1/projects/{id}/tz/files` — удалить файл
- `GET /api/v1/projects/{id}/tz/file` — скачать файл
- `POST /api/v1/projects/{id}/tz/parse` — AI-распознавание

### AI Check
- `POST /api/v1/projects/{id}/ai-check` — запустить AI-проверку
- `GET /api/v1/projects/{id}/ai-check` — получить результат
- `PATCH /api/v1/projects/{id}/ai-check/{idx}` — отклонить/восстановить проблему

### AI Fix Suggestions
- `POST /api/v1/projects/{id}/fix-suggestions` — сгенерировать fix'ы
- `GET /api/v1/projects/{id}/fix-suggestions` — список (фильтр `?status=`)
- `PATCH /api/v1/projects/{id}/fix-suggestions/{fix_id}` — approve/reject
- `PATCH /api/v1/projects/{id}/fix-suggestions` — batch approve
- `POST /api/v1/projects/{id}/fix-suggestions/{fix_id}/result` — Revit отчёт

## База данных (SQLite)

### Таблицы
1. **Project** — id, code, name, tz_general, tz_water_supply, tz_sewerage, tz_fire_fighting, tz_other, project_address, sections_count, floors_count, bim_requirements, pipeline_data (JSON), auto_bind_keywords, created_at
2. **ModelVersion** — id, project_id, ruleset_id, model_name, discipline, status, version_number, source_filename, ifc_hash, ifc_schema, export_profile, revit_version, plugin_version, source_file_name, processed_at
3. **Element** — id, model_version_id, global_id, ifc_id, ifc_class, name, object_type, predefined_type, type_name, storey_name, system_name, model_group, raw_psets_jsonb, normalized_jsonb
4. **ElementMeasurement** — id, element_id, key, value_num, unit
5. **Issue** — id, model_version_id, element_id, global_id, rule_key, severity, message, status, source_engine
6. **Ruleset** — id, name, version, status, source_text, ids_xml
7. **TzVersion** — id, project_id, version, data_jsonb, source, file_name, created_at
8. **Artifact** — id, model_version_id, artifact_type, path
9. **AuditLog** — id, entity_type, entity_id, action, payload_jsonb
10. **Report** — id, model_version_id, report_type, path, summary_jsonb

---

# Часть 3: Frontend (lynx-frontend)

## Структура (ES Modules)

```
lynx-frontend/
├── index.html              # Вся разметка + CSS (~800 строк)
├── src/
│   ├── main.js             # Entry point (~15 строк: импорты + init)
│   ├── utils.js            # escHtml, toast, modal, formatDate
│   ├── api.js              # API_BASE константа
│   ├── navigation.js       # showHome, showProject, goHome
│   ├── projects.js         # CRUD проектов, ТЗ, ключевые слова
│   ├── models.js           # Модели: загрузка, issues, viewer, bind
│   ├── categories.js       # Категории, константы, DEFAULT_CATEGORY_COLUMNS
│   ├── tzView.js           # Страница элементов модели
│   ├── dataView.js         # Данные проекта: категории, ТЗ, трубопроводы
│   ├── aiCheck.js          # AI-проверка + AI-исправления
│   ├── themes.js           # Темы (original/coffee), AI-статус
│   └── viewer.js           # Three.js 3D-рендерер
├── package.json            # Vite + three + three-ifc
└── vite.config.js          # Vite dev server (port 8080)
```

## Навигация (4 вьюхи)

| Вьюха | ID | Описание |
|-------|----|----------|
| Home | `#homeView` | Список проектов |
| Project | `#projectView` | Детальный просмотр + 3D + issues |
| TZ Elements | `#tzView` | Таблица элементов модели |
| Data | `#dataView` | Категории / ТЗ проекта / AI Check |

## Вкладки Data View

- **📋 Категории** — редактирование категорий и их параметров
- **📄 ТЗ проекта** — загрузка файлов, AI-распознавание, трубопроводные системы
- **🧠 Проверка с ИИ** — AI-проверка + AI-исправления (fix suggestions)

## AI Check (Проверка с ИИ)

Сравнивает элементы модели с ТЗ и СП 30, СП 31, СП 10, СП 485:
- Материалы, диаметры, изоляция, заполненность параметров
- Результат — список проблем с error/warning
- Проблемы можно отклонять (✕) и восстанавливать (↩)
- Состояние сохраняется на сервере

## AI Fix Suggestions (Исправления)

После проверки AI генерирует конкретные инструкции по исправлению:
- `set_param` — установить значение параметра
- `copy_param` — скопировать между параметрами
- `set_system` — назначить на систему
- У каждого fix'а: risk (low/medium/high), preview изменений
- Approve/reject через веб-интерфейс
- Revit-плагин забирает approved fix'ы и применяет

---

# Часть 4: Запуск

## 1. Backend

```bash
cd lynx-backend
pip install -r requirements.txt
# Настройка .env с OPENAI_API_KEY для AI-функций
uvicorn app.main:app --reload --port 8000
```

## 2. Frontend

```bash
cd lynx-frontend
npm install
npm run dev    # http://localhost:8080
```

## 3. Revit Plugin

1. Собрать `LynxRevitPlugin.csproj` (Release, x64)
2. Скопировать DLL + `.addin` в `%APPDATA%\Autodesk\Revit\Addins\2025\`
3. Открыть Revit → вкладка Lynx

---

# Версии компонентов

| Компонент | Версия | Описание |
|-----------|--------|----------|
| lynx-revit-plugin | 0.3.0 | Экспорт + AI-исправления |
| lynx-backend | 0.3.0 | Проекты, ТЗ, AI check, fix suggestions |
| lynx-frontend | 0.3.0 | SPA, 11 модулей, AI-проверка |

---

# Часть 5: Тестирование

## Backend (lynx-backend)

Фреймворк: **pytest** + pytest-asyncio (asyncio_mode = auto).  
Конфигурация: `lynx-backend/pyproject.toml` (раздел `[tool.pytest.ini_options]`).

### Запуск

```bash
cd lynx-backend
pytest tests/ -v          # все тесты
pytest tests/ -v -k rule   # фильтр по имени
pytest tests/test_api.py -v  # один файл
```

### Тестовые файлы

| Файл | Тестов | Описание |
|------|--------|----------|
| `tests/conftest.py` | — | Фикстуры: временная БД, временное хранилище, AsyncClient, override_settings |
| `tests/test_upload.py` | 13 | Загрузка IFC: большие файлы (1KB–10MB), пустые, конкурентные, отсутствие boundary, отсутствие заголовков, повреждённые данные, Revit ID map |
| `tests/test_api.py` | ~30 | Весь API: health, projects CRUD, модели, категории, TZ, AI status, vendor, изменения, CORS |
| `tests/test_db.py` | ~15 | БД: CRUD проектов, версий моделей, issues, категорий, move_model, auto-bind |
| `tests/test_rule_engine.py` | 40 | Rule engine: deep_get (5), операторы (20), eval_rule (7), default rules (8) |
| `tests/test_element_storage.py` | 5 | Сохранение/загрузка/удаление JSON-блобы, большие данные, JSON type roundtrip |
| `tests/test_services.py` | 5 | Auto-bind keywords, XKT noop, извлечение диаметра, извлечение материала |

### Что тестируется

- **test_upload.py**: корректность потоковой загрузки (stream → raw → multipart-парсинг), обработка ошибок парсинга, Edge Cases (Concurrent 5× requests)
- **test_api.py**: каждый endpoint возвращает корректный HTTP-статус и структуру JSON, CORS-заголовки
- **test_db.py**: CRUD-операции, каскадное удаление, перемещение модели между проектами, автоматическая привязка по ключевым словам
- **test_rule_engine.py**: all 8 operators (exists, not_exists, eq, neq, in, not_in, gt, gte, lt, lte, regex, between), eval_rule pipeline, проверка DEFAULT_RULES (целостность, уникальность, валидность severity/operator, все правила выполнимы для полного элемента)
- **test_element_storage.py**: JSON-сериализация на диск, большие вложенные объекты
- **test_services.py**: auto-bind (поиск ключевых слов в названии модели), извлечение диаметра из `raw_psets`

## Frontend (lynx-frontend)

Фреймворк: **Vitest** + jsdom.  
Конфигурация: `lynx-frontend/vitest.config.js`.

### Запуск

```bash
cd lynx-frontend
npm test              # однократный прогон
npm run test:watch    # watch mode
```

### Тестовые файлы

| Файл | Тестов | Описание |
|------|--------|----------|
| `src/__tests__/setup.js` | — | Загрузка DOM из index.html (body), общие моки |
| `src/__tests__/utils.test.js` | 13 | escHtml, formatDate, getStatusBadge, openModal/closeModal, showToast |
| `src/__tests__/api.test.js` | 1 | API_BASE константа |
| `src/__tests__/themes.test.js` | 5 | toggleTheme (coffee/original), CSS variables, toggleAiPopup, клик вне попапа |
| `src/__tests__/navigation.test.js` | 10 | showHome, showProject, goHome, onQuickSelectProject, breadcrumb, view переключение |
| `src/__tests__/categories.test.js` | 21 | buildCategoryIcons, getDefaultCols, extractProp, formatValue, categorizeElement, getColsForCategory |

### Что тестируется

- **utils.js**: HTML-экранирование (null/undefined/объекты/строки), форматирование дат, статус-бейджи, модальные окна (add/remove active class), toast-уведомления (показ + автозакрытие через 3s)
- **api.js**: константа `/api/v1` доступна через `window.API_BASE`
- **themes.js**: применение CSS-переменных при загрузке, переключение тем (original → coffee → original), обновление иконки кнопки, открытие/закрытие AI-попапа, клик вне попапа
- **navigation.js**: активация/деактивация вьюх (homeView, projectView, tzView, dataView), обновление breadcrumb, скрытие/показ quick select + кнопка нового проекта, очистка state в goHome
- **categories.js**: генерация иконок (циклические цвета, пустой список), дефолтные колонки для известных/неизвестных категорий, extractProp (по одному ключу, fallback, null, non-object, empty string), formatValue (числа 2 знака, запятая как разделитель, не-числа, null/undefined/whitespace), categorizeElement (подстрока, case-insensitive, empty model_group, fallback)
