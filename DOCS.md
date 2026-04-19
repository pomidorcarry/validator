# Lynx - Документация программной системы

> Текущая версия: **0.1.0**
> Дата: April 2026

---

## Общее описание

**Lynx** — гибридная openBIM-система для автоматической проверки BIM-моделей. Состоит из трёх основных компонентов:

1. **Revit-плагин** — экспортирует IFC из Revit и отправляет на сервер
2. **FastAPI Backend** — принимает, обрабатывает и проверяет модели
3. **Frontend (в разработке)** — визуализация и работа с результатами

---

## Архитектура системы

```
Revit Plugin          Backend API              Database
      │                   │                      │
      ▼                   ▼                      ▼
┌──────────┐      ┌──────────┐           ┌──────────┐
│ Export   │ ───► │ Upload  │ ──────►  │ SQLite  │
│ IFC     │      │ Process │           │ Storage │
└──────────┘      │ Validate│           │         │
                  │ Store   │           │         │
                  └────────┘           └──────────┘
```

---

# Часть 1: Revit Плагин (lynx-revit-plugin)

## Назначение

Плагин для Autodesk Revit 2025, который:
- Экспортирует текущую модель в формат IFC
- Отправляет экспортированный файл на сервер Lynx
- Позволяет настроить параметры подключения

## Структура папок и файлов

```
lynx-revit-plugin/
├── LynxRevitPlugin.csproj    # Проект Visual Studio
├── LynxRevitPlugin.addin     # Манифест для Revit
├── App.cs                    # Точка входа, создание UI
├── ExportIfcCommand.cs       # Команда экспорта IFC
├── SettingsCommand.cs        # Команда открытия настроек
└── SettingsForm.cs          # Форма настроек
```

## Описание файлов

### LynxRevitPlugin.csproj

Проект библиотеки для .NET Framework 4.8. Содержит ссылки на Revit API.

**Ключевые настройки:**
-TargetFramework: net48
- PlatformTarget: x64
- References: RevitAPI.dll, RevitAPIUI.dll, System.Net.Http

**Используемые сборки:**
- `Autodesk.Revit.UI` — для работы с UI Revit
- `Autodesk.Revit.Attributes` — атрибуты команд (Transaction, ExternalCommand)
- `Autodesk.Revit.DB` — для работы с документами и IFC экспорта

### LynxRevitPlugin.addin

XML-файл манифеста, который сообщает Revit о плагине.

**Содержимое:**
```xml
<RevitAddIns>
  <AddIn Type="Application">
    <Assembly>LynxRevitPlugin.dll</Assembly>
    <FullClassName>LynxRevitPlugin.App</FullClassName>
    <ClientId>9d993849-b038-468f-a02f-56b009d96df2</ClientId>
    <Name>Lynx Revit Plugin</Name>
    <VendorId>Lynx</VendorId>
  </AddIn>
</RevitAddIns>
```

### App.cs

Регистрирует плагин в Revit. Создаёт вкладку "Lynx" на ленте с двумя кнопками.

**Основные методы:**
- `OnStartup(UIControlledApplication app)` — создаёт UI при старте
- `OnShutdown(UIControlledApplication app)` — очистка при выходе

**UI создаётся через:**
- `app.CreateRibbonTab(string tabName)` — создание вкладки
- `app.CreateRibbonPanel(string tab, string panelName)` — создание панели
- `PushButtonData` — кнопки на панели

### ExportIfcCommand.cs

Основная команда экспорта. Реализует `IExternalCommand`.

**Атрибуты:**
```csharp
[Transaction(TransactionMode.Manual)]
public class ExportIfcCommand : IExternalCommand
```

**Методы:**

1. `Execute(ExternalCommandData, ref string, ElementSet)` — точка входа
   - Проверяет настройки сервера
   - Проверяет сохранённость документа
   - Запускает экспорт IFC
   - Отправляет файл на сервер

2. `GetExportFolder()` — возвращает путь для экспорта
   - Путь: `%APPDATA%\Lynx\IFC`

3. `ExportIfc(Document, folder, fileName)` — экспорт в IFC
   - Использует `IFCExportOptions`
   - Версия: IFC4
   - Включает базовые количества

4. `UploadIfcToServer(ifcPath, settings, doc)` — отправка на сервер
   - multipart/form-data
   - POST на `{serverUrl}/api/v1/models/upload`
   - Параметры: project_id, model_name, ruleset_id, discipline

**Параметры отправки:**
- `project_id` — ID проекта (из настроек)
- `model_name` — название модели (doc.Title)
- `ruleset_id` — ID набора правил (из настроек)
- `discipline` — "VIV" (вентиляция)
- `revit_version` — версия Revit
- `plugin_version` — версия плагина "0.1.0"

### SettingsCommand.cs

Команда открытия формы настроек. Реализует `IExternalCommand`.

**Атрибуты:**
```csharp
[Transaction(TransactionMode.ReadOnly)]
public class SettingsCommand : IExternalCommand
```

### SettingsForm.cs

WinForms форма для настроек подключения.

**Поля:**
- `serverUrlTextBox` — URL сервера
- `projectIdTextBox` — ID проекта
- `rulesetIdTextBox` — ID правил

**Методы:**
- `LoadSettings()` — загрузка настроек из файла
- `SaveSettings()` — сохранение настроек в файл

**Файл настроек:** `%APPDATA%\Lynx\LynxSettings.txt`
```
ServerUrl=http://localhost:8000
ProjectId=default
RulesetId=default
```

## Установка плагина

1. Скомпилировать в Release x64
2. Скопировать DLL и .addin в:
   `%APPDATA%\Autodesk\Revit\Addins\2025\`

---

# Часть 2: Backend (lynx-backend)

## Назначение

FastAPI сервер, который:
- Принимает IFC файлы
- Сохраняет и версионирует модели
- Нормализует IFC в структурированный индекс
- Проверяет модель по правилам
- Предоставляет API для работы с результатами

## Структура папок и файлов

```
lynx-backend/
├── app/
│   ├── main.py                 # Точка входа FastAPI
│   ├── core/
│   │   └── config.py          # Настройки приложения
│   ├── db/
│   │   └── models.py         # SQLAlchemy модели БД
│   └── services/
│       ├── ifc_normalizer.py # Нормализация IFC
│       └── rule_engine.py     # Проверка правил
├── pyproject.toml            # Конфигурация проекта
├── requirements.txt         # За��исимости
└── storage/               # Хранилище файлов
    └── raw/               # IFC файлы
```

## Описание файлов

### app/main.py

Точка входа FastAPI приложения.

**API Endpoints:**

1. `POST /api/v1/models/upload` — загрузка IFC
   - Принимает multipart/form-data
   - Возвращает 202 Accepted
   - Запускает фоновую обработку

2. `GET /api/v1/models/{model_version_id}` — получить информацию о версии

3. `GET /api/v1/models/{model_version_id}/status` — статус обработки

4. `GET /api/v1/models/{model_version_id}/issues` — список ошибок

5. `GET /api/v1/health` — проверка здоровья сервера

### app/core/config.py

Настройки приложения через Pydantic Settings.

**Параметры:**
```python
app_name: str = "Lynx Backend"
version: str = "0.1.0"
api_prefix: str = "/api/v1"
host: str = "0.0.0.0"
port: int = 8000
storage_path: str = "./storage"
database_url: str = "sqlite+aiosqlite:///./lynx.db"
max_file_size_mb: int = 100
```

### app/db/models.py

SQLAlchemy модели для SQLite базы данных.

**Таблицы:**

1. **Project** — проекты
   - id, code, name, created_at

2. **Ruleset** — наборы правил
   - id, name, version, status, source_text, ids_xml

3. **ModelVersion** — версии моделей
   - id, project_id, ruleset_id, model_name, discipline
   - status: uploaded → queued → processing → processed/failed
   - source_filename, ifc_hash, ifc_schema, export_profile

4. **Element** — элементы модели
   - id, model_version_id, global_id, ifc_id, ifc_class
   - name, object_type, predefined_type, type_name
   - storey_name, system_name
   - raw_psets_jsonb, normalized_jsonb

5. **ElementMeasurement** — измерения элементов
   - element_id, measurement_key, value_num, unit

6. **Issue** — найденные проблемы
   - id, model_version_id, element_id, global_id
   - issue_type, severity, rule_key, status, message
   - source_engine

7. **AISuggestion** — предложения ИИ
   - id, model_version_id, suggestion_type
   - candidate_jsonb, score, state

8. **Report** — отчёты
   - id, model_version_id, report_type, path, summary_jsonb

### app/services/ifc_normalizer.py

Нормализация IFC файла в структурированный индекс.

**Ключевые классы:**
- `MVP_CLASSES` — целевые типы элементов
  ```python
  ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"]
  ```

**Функции:**

1. `extract_diameter_from_psets(psets)` — извлечение диаметра
   - Ищет в: NominalDiameter, Reference, Diameter, Size, DN

2. `normalize_element(e, model, scale_to_mm)` — нормализация одного элемента
   - Извлекает: global_id, ifc_class, name, psets
   - Вычисляет: diameter_mm, storey_name, system_name

3. `process_model_version(model_version_id)` — обработка модели
   - Открывает IFC через IfcOpenShell
   - Нормализует элементы
   - Сохраняет в БД

**Выходной JSON элемента:**
```json
{
  "global_id": "3bJQxL4Jf8zvA4HkQ1yN2V",
  "ifc_class": "IfcPipeSegment",
  "name": "Труба В1 DN50",
  "storey_name": "L2",
  "system_name": "В1",
  "raw_psets": { ... },
  "canonical": {
    "diameter_mm": 50.0
  }
}
```

### app/services/rule_engine.py

Движок проверки правил.

**Операторы:**
- `exists`, `not_exists`
- `eq`, `neq`
- `in`, `not_in`
- `regex`
- `between`
- `gt`, `gte`, `lt`, `lte`

**Структура правила:**
```json
{
  "rule_key": "viv.pipe.diameter.required_range",
  "applies_to": {
    "ifc_classes": ["IfcPipeSegment"],
    "where": [{"field": "system_name", "op": "eq", "value": "В1"}]
  },
  "check": {
    "field": "canonical.diameter_mm",
    "op": "between",
    "min": 20,
    "max": 500
  },
  "severity": "error",
  "message_template": "Диаметр должен быть в диапазоне 20..500 мм"
}
```

**Встроенные правила:**
1. `viv.pipe.name.required` — наличие имени
2. `viv.pipe.diameter.exists` — наличие диаметра
3. `viv.pipe.diameter.range` — диапазон 20-500мм
4. `viv.pipe.system.required` — наличие системы

## Запуск Backend

```bash
cd lynx-backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Сервер запускается на `http://localhost:8000`.

---

# Часть 3: Frontend (lynx-frontend) — Планируется

## Назначение

Web-интерфейс для:
- Визуализации BIM-модели
- Просмотра и фильтрации ошибок
- Управления правилами
- Работы с ИИ-подсказками

## Фактическая структура

```
lynx-frontend/
├── index.html    # Основная HTML страница
```

## Описание	index.html

Простая HTML страница с:
- Списком моделей слева
- 3D viewer (placeholder) по центру
- Инспектором элемента и списком ошибок справа
- Автозагрузка каждые 10 секунд

**API вызовы:**
```javascript
GET /api/v1/models           → список моделей
GET /api/v1/models/{id}/status
GET /api/v1/models/{id}/elements
GET /api/v1/models/{id}/issues
```

**Запуск:** открыть в браузере `lynx-frontend/index.html`

---

# Взаимодействие компонентов

##流程 обработки модели

```
1. Пользователь нажимает "Экспорт в Lynx" в Revit
            │
            ▼
2. Плагин экспортирует IFC (с транзакцией)
   - Файл сохраняется в %APPDATA%\Lynx\IFC
            │
            ▼
3. Плагин отправляет файл на сервер
   - POST /api/v1/models/upload
   - multipart/form-data
            │
            ▼
4. Сервер принимает файл (202 Accepted)
   - Сохраняет в storage/raw/{uuid}.ifc
   - Создаёт запись в model_versions
   - Запускает фоновую обработку
            │
            ▼
5. IfcOpenShell нормализует IFC
   - Извлекает элементы нужных классов
   - Вычисляет канонические поля (diameter_mm)
   - Сохраняет в таблицу elements
            │
            ▼
6. Rule Engine проверяет модель
   - Прогоняет все правила
   - Создаёт issues для нарушений
            │
            ▼
7. Frontend получает результаты
   - Показывает ошибки
   - Подсвечивает проблемные элементы
```

## API контракт

### Загрузка модели
```
POST /api/v1/models/upload
Content-Type: multipart/form-data

Поля:
- file: .ifc файл
- project_id: string
- model_name: string  
- ruleset_id: string
- discipline: string (VIV)
- revit_version: string

Ответ (202):
{
  "model_version_id": "uuid",
  "status": "queued"
}
```

### Получение ошибок
```
GET /api/v1/models/{model_version_id}/issues

Ответ:
{
  "issues": [
    {
      "id": "uuid",
      "global_id": "string",
      "severity": "error|warning",
      "rule_key": "string",
      "message": "string",
      "status": "open"
    }
  ],
  "count": number
}
```

---

# Конфигурация и настройки

## Переменные окружения

Для Backend (`.env`):
```
APP_NAME=Lynx Backend
VERSION=0.1.0
API_PREFIX=/api/v1
HOST=0.0.0.0
PORT=8000
STORAGE_PATH=./storage
DATABASE_URL=sqlite+aiosqlite:///./lynx.db
```

Для Плагина (файл настроек):
```
ServerUrl=http://localhost:8000
ProjectId=default
RulesetId=default
```

---

# Ограничения и известные проблемы

## Текущие ограничения

1. **Revit Плагин**
   - Только Revit 2025
   - Документ должен быть сохранён
   - IFC экспорт только в IFC4

2. **Backend**
   - Только SQLite (для MVP)
   - Обработка в одном потоке
   - Ограничение размера файла 100MB

3. **Нормализация**
   - Только классы: IfcPipeSegment, IfcPipeFitting, IfcValve, IfcFlowTerminal
   - Ограниченный набор свойств

---

# Разработка и расширение

## Добавление нового правила

1. Добавить в `rule_engine.py` в `DEFAULT_RULES`:
```python
{
    "rule_key": "unique.key",
    "applies_to": {"ifc_classes": ["IfcClass"], "where": []},
    "check": {"field": "canonical.field", "op": "operator", ...},
    "severity": "error|warning",
    "message_template": "Сообщение об ошибке"
}
```

2. Перезапустить сервер

## Добавление нового IFC класса

1. Добавить класс в `MVP_CLASSES` в `ifc_normalizer.py`
2. Добавить правила для класса
3. Обновить нормализацию если нужно

## Запуск тестов

```bash
cd lynx-backend
pytest
```

---

# Версии компонентов

| Компонент | Версия | Описание |
|-----------|-------|----------|
| lynx-revit-plugin | 0.1.0 | Первая версия плагина |
| lynx-backend | 0.1.0 | Базовая функциональность |
| lynx-frontend | 0.1.0 | MVP UI |

---

# Порядок запуска

## 1. Запуск Backend

```bash
cd lynx-backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Сервер запускается на `http://localhost:8000`

## 2. Запуск Frontend

Просто откройте файл в браузере:
```
lynx-frontend/index.html
```

Или запустите через Python:
```bash
python -m http.server 8080 -d lynx-frontend
```
Откройте `http://localhost:8080`

## 3. Использование плагина

1. Откройте Revit 2025
2. Перейдите на вкладку **Lynx**
3. Нажмите **Настройки** для настройки URL (по умолчанию `http://localhost:8000`)
4. Сохраните документ (должен быть сохранён)
5. Нажмите **Экспорт в Lynx**
6. Дождитесь завершения экспорта и отправки
7. Откройте Frontend для просмотра результатов

## Проверка в браузере

1. Откройте `lynx-frontend/index.html`
2. Выберите модель из списка
3. Просмотрите ошибки в правой панели
4. Нажмите на ошибку для подсветки элемента

---

# Контакты и поддержка

- **Автор**: Lynx Team
- **Версия API**: v1
- **Документация**: this file