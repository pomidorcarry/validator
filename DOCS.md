# Lynx - Документация программной системы

> Текущая версия: **0.2.0**
> Дата: May 2026

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

### Models
1. `POST /api/v1/models/upload` — загрузка IFC (202 Accepted)
2. `GET /api/v1/models` — список всех моделей (с опциональным `?project_id=`)
3. `GET /api/v1/models/{model_version_id}` — информация о версии
4. `GET /api/v1/models/{model_version_id}/status` — статус обработки
5. `GET /api/v1/models/{model_version_id}/issues` — список ошибок
6. `GET /api/v1/models/{model_version_id}/elements` — элементы модели
7. `GET /api/v1/models/{model_version_id}/ifc` — скачать IFC файл
8. `GET /api/v1/models/{model_version_id}/xkt` — скачать XKT
9. `PUT /api/v1/models/{model_id}/move` — переместить модель в другой проект
10. `DELETE /api/v1/models/{model_version_id}` — удалить модель
11. `DELETE /api/v1/models` — удалить все модели

### Projects
12. `GET /api/v1/projects` — список проектов
13. `POST /api/v1/projects` — создать проект
14. `GET /api/v1/projects/{project_id}` — детали проекта
15. `PUT /api/v1/projects/{project_id}` — обновить проект (название, ТЗ)
16. `DELETE /api/v1/projects/{project_id}` — удалить проект

### Project Categories
17. `GET /api/v1/projects/{project_id}/categories` — список категорий для проекта
18. `PUT /api/v1/projects/{project_id}/categories` — сохранить категории для проекта

### System
19. `GET /api/v1/health` — проверка здоровья сервера

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
   - id, code, name, technical_specification (text), created_at

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

# Часть 3: Frontend (lynx-frontend)

## Назначение

Web-интерфейс для:
- Управления проектами (создание, редактирование, удаление)
- Управления BIM-моделями в рамках проектов
- Настройки технического задания (ТЗ) для каждого проекта
- Визуализации BIM-модели через three.js / three-ifc
- Просмотра и фильтрации ошибок валидации

## Структура

```
lynx-frontend/
├── index.html       # Основная HTML страница с проектами и 3D-viewer
├── src/
│   ├── main.js      # Логика: проекты, модели, навигация
│   └── viewer.js    # 3D-рендерер (three.js + IfcLoader)
├── package.json     # Vite + three.js + three-ifc
└── vite.config.js   # Конфиг Vite dev server
```

## Функционал

### Домашняя страница (список проектов)
- Показывает все проекты в виде карточек
- Каждый проект отображает: название, код, количество моделей, дату создания
- Кнопка "+ Новый проект" для создания
- Клик по проекту → переход в детальный просмотр

### Детальный просмотр проекта
- **Левая панель:**
  - Техническое задание (ТЗ) — редактируемое текстовое поле
  - Список моделей проекта с статусом обработки
  - Кнопки: загрузить IFC, переместить модель, удалить модель, привязать существующую модель
- **Центр:**
  - 3D viewer (three.js + IfcLoader)
  - Показывает выбранную модель
- **Правая панель:**
  - Инспектор элемента (Global ID, Класс IFC, Имя, Этаж, Система)
  - Список ошибок валидации для выбранной модели

### Страница ТЗ и элементов

Переименована в **"Заполнение элементов модели"**. Отображает таблицу элементов проекта из всех обработанных моделей.

- **Боковая панель:**
  - Разделы — группировка элементов по категориям строительных конструкций (определяется из IFC-параметра "Модель")
  - Информация о проекте (код, количество моделей, элементов, ключи автопривязки)
- **Основная область:**
  - Таблица элементов проекта
  - Фильтрация по категории (сайдбар + чипсы IFC-классов)
  - Поиск по имени, классу, этажу, системе
  - Категория элемента определяется по полю `model_group` (извлекается из IFC-параметра "Модель")
  - **Категорийно-зависимые столбцы**: для каждой категории свой набор свойств (Секция, Типоразмер, Толщина стенки и т.д.), заданный в `CATEGORY_COLUMNS`
  - **Кастомный горизонтальный скролл**: нативный `overflow-x: auto` со стилизованным `::-webkit-scrollbar` (толстый ползунок, скругления, зелёный hover). Drag-to-scroll с инерцией (grab-курсор, инерция 0.92/frame). Анимированная подсказка-иконка при переполнении.

### Страница "Данные о проекте и обработка ТЗ"

Управление категориями элементов модели:
- Просмотр и редактирование списка категорий
- Добавление новых категорий
- Удаление категорий
- Сохранение изменений в БД (привязка к проекту)
- Категории по умолчанию создаются при первом открытии

### Автопривязка моделей по ключевым словам
При загрузке модели (`POST /api/v1/models/upload`) сервер проверяет название модели на совпадение с `auto_bind_keywords` всех проектов (регистронезависимо). Если ключевое слово найдено — модель автоматически привязывается к соответствующему проекту, игнорируя переданный `project_id`.

### Категории строительных конструкций
Определяются по IFC-параметру **"Модель"** (поле `model_group` в БД). Значение параметра должно совпадать с названием категории.
1. **Труба металлическая** — металлические трубопроводы
2. **Труба полимерная** — полимерные трубопроводы
3. **Металлическая соединительная деталь трубы** — фитинги
4. **Полимерная соединительная деталь трубы** — полимерные фитинги
5. **Арматура труб** — запорная арматура, клапаны, задвижки
6. **Оборудование** — насосы, теплообменники, котлы
7. **Сантехнический прибор** — раковины, унитазы, ванны
8. **Изоляция рулонная** — рулонная теплоизоляция
9. **Изоляция трубчатая** — трубчатая теплоизоляция
10. **Невалидируемое семейство** — элементы без известной категории

### Управление проектами
- **Создание:** код, название, опциональное ТЗ
- **Редактирование:** изменение названия и ТЗ
- **Удаление:** с подтверждением
- **Быстрый переход:** выпадающий список в хедере

### Управление моделями
- **Загрузка IFC:** через модальное окно (название, файл, ruleset_id)
- **Перемещение между проектами:** через модальное окно с выбором целевого проекта
- **Удаление:** с подтверждением
- **Просмотр 3D:** модели со статусом "processed" загружаются в viewer

## API вызовы (фронтенд)

```javascript
GET    /api/v1/projects                → список проектов
POST   /api/v1/projects                → создать проект
GET    /api/v1/projects/{id}           → детали проекта
PUT    /api/v1/projects/{id}           → обновить проект
DELETE /api/v1/projects/{id}           → удалить проект

GET    /api/v1/models?project_id={id}  → модели проекта
POST   /api/v1/models/upload           → загрузить IFC
PUT    /api/v1/models/{id}/move        → переместить модель
DELETE /api/v1/models/{id}             → удалить модель
GET    /api/v1/models/{id}/issues      → ошибки модели
GET    /api/v1/models/{id}/elements    → элементы модели
GET    /api/v1/models/{id}/ifc         → скачать IFC
```

## Запуск Frontend

```bash
cd lynx-frontend
npm install
npm run dev    # http://localhost:8080
```

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
| lynx-revit-plugin | 0.1.0 | Revit IFC экспорт + отправка |
| lynx-backend | 0.2.0 | Проекты, ТЗ, перемещение моделей |
| lynx-frontend | 0.2.0 | Домашняя страница, проекты, ТЗ |

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

```bash
cd lynx-frontend
npm install
npm run dev
```
Откройте `http://localhost:8080`

### Работа с проектами

1. На домашней странице нажмите **"+ Новый проект"**
2. Заполните код (напр. PRJ-001) и название
3. Опционально добавьте Техническое задание
4. После создания кликните на проект
5. В детальном просмотре загрузите IFC-модель
6. ТЗ можно редактировать нажатием на иконку ✎
7. Модели можно перемещать между проектами через кнопку ↗

## 3. Использование плагина

1. Откройте Revit 2025
2. Перейдите на вкладку **Lynx**
3. Нажмите **Настройки** для настройки URL (по умолчанию `http://localhost:8000`)
4. Сохраните документ (должен быть сохранён)
5. Нажмите **Экспорт в Lynx**
6. Дождитесь завершения экспорта и отправки
7. Откройте Frontend для просмотра результатов

## 4. Проверка с ИИ

Функция **"Проверка с ИИ"** сравнивает элементы BIM-модели с техническим заданием (ТЗ) и сводами правил (СП 30, СП 31, СП 10, СП 485).

1. Перейдите в **"Данные о проекте и обработка ТЗ"** → **"Проверка с ИИ"**
2. Нажмите **"Проверить"**
3. AI анализирует:
   - Соответствие материалов труб ТЗ и СП
   - Диаметры труб (минимальные/максимальные по СП)
   - Наличие изоляции (ГВС, холодные трубопроводы)
   - Заполненность критических параметров (система, материал, диаметр)
   - Именование элементов
   - Наличие обязательных систем
4. Результат — список проблем с severity (error/warning)
5. Можно отклонить проблему (✕) или восстановить (↩)
6. Состояние отклонения сохраняется между сессиями

Результаты проверки кешируются на сервере. Для повторной проверки нажмите **"Обновить проверку"**.

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