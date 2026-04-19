# Lynx MVP - Гибридная openBIM-система

> **Always load at the start of each chat:**
> - For Python: Load skill `python-patterns` from `.opencode/skills/python_dev`
> - For C# / Revit: Load skill `revit-extension` from `.opencode/skills/revit-extension`
> - Use MCP context7 for documentation lookup
> - Read this agents.md file for architecture details
> - **При всех значимых изменениях обновляй документацию в DOCS.md**

---

## Executive Summary

**Lynx** — гибридная openBIM-система для автоматической проверки BIM-моделей:

1. **Revit-плагин** экспортирует IFC и отправляет на сервер
2. **FastAPI backend** принимает, версионирует и обрабатывает модель
3. **IfcOpenShell/Ifc2Sql** нормализует IFC в индекс элементов
4. **Rule Engine** выполняет формальные проверки (IDS + Python)
5. **AI-модуль** помогает формализовать ТЗ, сопоставлять параметры, искать аномалии
6. **xeokit Viewer** визуализирует модель и связывает с issues

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop Layer (Revit Plugin)                             │
│  - IFC Export via Document.Export()                         │
│  - multipart/form-data upload via HttpClient                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Server Layer (FastAPI)                                   │
│  - Upload API, Storage, Versioning                        │
│  - IFC Normalization (IfcOpenShell)                     │
│  - Rule Engine (IDS + Python)                           │
│  - AI Module (semantic mapping, anomaly detection)       │
│  - Report Generation                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend Layer                                         │
│  - xeokit XKT Viewer                                   │
│  - Issue List, Rule Editor, AI Suggestions              │
│  - Diff/History View                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Desktop | C#, Revit API, HttpClient | IFC export & upload |
| Backend | FastAPI, Pydantic, SQLAlchemy | REST API, validation |
| DB | SQLite (MVP) / PostgreSQL | Storage, elements, issues |
| IFC Parsing | IfcOpenShell, Ifc2Sql | Normalization |
| Rules | IfcTester, Python eval | Formal checks |
| AI | LLM + RAG, sklearn | Semantic mapping, anomaly |
| Vector Store | FAISS (MVP) / Weaviate | Embeddings |
| Viewer | xeokit, XKT | 3D visualization |

---

## Project Structure

```
Lynx/
├── lynx-revit-plugin/           # C# Revit add-in
│   ├── LynxRevitPlugin.csproj
│   ├── LynxRevitPlugin.addin
│   ├── Commands/
│   │   └── ExportIfcCommand.cs
│   └── Services/
│       └── IfcExporter.cs
│
├── lynx-backend/             # Python FastAPI server
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── models.py
│   │   │       ├── issues.py
│   │   │       └── rules.py
│   │   ├── services/
│   │   │   ├── ifc_normalizer.py
│   │   │   ├── rule_engine.py
│   │   │   ├── ai_module.py
│   │   │   └── report_generator.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   └── migrations/
│   │   └── core/
│   │       └── config.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── pyproject.toml
│   └── requirements.txt
│
└── lynx-frontend/          # React/Vue + xeokit
    ├── src/
    │   ├── components/
    │   ├── views/
    │   └── services/
    └── package.json
```

---

## API Endpoints

### Models API
- `POST /api/v1/models/upload` — загрузка IFC (202 Accepted)
- `GET /api/v1/models/{model_version_id}` — получить модель
- `GET /api/v1/models/{model_version_id}/status` — статус обработки
- `POST /api/v1/models/{model_version_id}/reprocess` — перезапуск

### Issues API
- `GET /api/v1/models/{model_version_id}/issues` — список issues
- `GET /api/v1/issues/{issue_id}` — детали issue

### Rules API
- `GET /api/v1/rulesets` — список rulesets
- `POST /api/v1/rulesets` — создать ruleset
- `PUT /api/v1/rulesets/{id}` — обновить правило

### AI API
- `POST /api/v1/ai/semantic-mapping` — предложить mapping
- `POST /api/v1/ai/anomaly-detection` — найти аномалии
- `POST /api/v1/ai/draft-rule` — сгенерировать правило из ТЗ

### Reports API
- `GET /api/v1/models/{model_version_id}/report` — получить отчёт

---

## Database Schema

### Tables
- **projects** — id, code, name, created_at
- **rulesets** — id, name, version, status, source_text, ids_xml
- **model_versions** — id, project_id, ruleset_id, status, source_filename, ifc_hash, processed_at
- **artifacts** — id, model_version_id, artifact_type, path
- **elements** — id, model_version_id, global_id, ifc_class, name, raw_psets_jsonb, normalized_jsonb
- **element_measurements** — id, element_id, key, value_num, unit
- **issues** — id, model_version_id, element_id, rule_key, severity, message, status
- **ai_suggestions** — id, model_version_id, suggestion_type, candidate_jsonb, score, state
- **audit_log** — id, entity_type, entity_id, action, payload_jsonb
- **reports** — id, model_version_id, report_type, path, summary_jsonb

---

## Normalized Element Format

```json
{
  "global_id": "3bJQxL4Jf8zvA4HkQ1yN2V",
  "ifc_class": "IfcPipeSegment",
  "name": "Труба В1 DN50",
  "type_name": "Pipe DN50 Steel",
  "storey_name": "L2",
  "system_name": "В1",
  "raw_props": {
    "Pset_PipeSegmentCommon": {
      "Reference": "DN50",
      "Status": "NEW"
    }
  },
  "canonical": {
    "diameter_mm": 50.0,
    "diameter_source": "UserPset.Diameter",
    "material": "Steel"
  }
}
```

---

## Rule Engine

### Rule Format (JSON)
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

### Supported Operators
- `exists`, `not_exists`
- `eq`, `neq`
- `in`, `not_in`
- `regex`
- `between`
- `gt`, `gte`, `lt`, `lte`

### Priority System
| Priority | Type | Purpose |
|----------|------|--------|
| 100 | schema/pre-check | Валидность IFC |
| 200 | critical mandatory | Обязательные параметры |
| 300 | naming/classification | Именование, классификация |
| 400 | informational | Предупреждения |
| 500 | AI hints | AI-подсказки |

---

## AI Module

### Functions
1. **Draft Rules from Text** — из ТЗ генерировать candidate rule
2. **Semantic Mapping** — сопоставить неизвестные свойства с canonical
3. **Anomaly Detection** — найти аномальные значения

### Anomaly Detection Algorithm
- **IsolationForest** — первый выбор для MVP
- **OneClassSVM** — для однородных датасетов

### AI Workflow
```
AI generates candidate → Validator checks → Dry-run → User approval → Audit Log
```

### AI State Machine
- draft → validated_structure → tested_on_sample → approved/rejected → expired

---

## Development Roadmap

### Sprint A: Revit Export/Upload
- Плагин экспортирует IFC
- Отправляет на сервер
- **Критерий**: 202 Accepted, файл в storage

### Sprint B: Backend Ingestion
- model_versions, artifacts
- Статусы обработки
- **Критерий**: uploaded → queued → processing → processed/failed

### Sprint C: IFC Normalization
- elements index
- canonical fields
- **Критерий**: 4 класса стабильно извлекаются

### Sprint D: Rule Engine
- IDS + 10-15 Python checks
- Issues в БД, JSON/HTML report
- **Критерий**: осмысленные errors/warnings

### Sprint E: Viewer/UI
- XKT загрузка
- Привязка issues к объектам
- **Критерий**: клик по issue → подсветка объекта

### Sprint F: AI Mapping + Anomaly
- Candidate mappings
- Anomaly list
- **Критерий**: AI suggestions в UI, approval flow

### Sprint G: Diff/History
- Сравнение версий
- **Критерий**: new/resolved/persistent в report

### Sprint H: Tests/Demo
- E2E demo
- Метрики
- **Критерий**: стенд для защиты

---

## MVP Categories & Checks

### Categories (MVP)
- IfcPipeSegment
- IfcPipeFitting
- IfcValve
- IfcFlowTerminal

### Checks (~15-25 rules)
1. Наличие имени
2. Regex имени
3. Наличие системы
4. Наличие диаметра
5. Диапазон диаметра (20-500mm)
6. Согласованность name ↔ diameter_mm
7. Допустимые материалы
8. Обязательные pset-поля
9. Заполненность классификации
10. Аномальные значения в группе

---

## Testing Metrics

| Metric | Purpose |
|--------|--------|
| Precision | Доля корректных замечаний |
| Recall | Доля найденных ошибок |
| F1 | Баланс precision/recall |
| Time-to-check | Время от upload до отчёта |
| Rule authoring time | Время создания правила |
| AI acceptance rate | Доля утверждённых AI |
| Issue-to-element latency | Время клик → подсветка |

---

## Deployment

### MVP Setup
```
1 backend FastAPI
SQLite or PostgreSQL
Local/S3 file storage
BackgroundTasks for processing
```

### Security
- HTTPS/TLS
- JWT for UI/API
- Service token for plugin
- File size limits
- Extension whitelist

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|----------|
| Нестабильность IFC | Фиксированный профиль экспорта, узкий scope |
| Неполные свойства | Normalized index, source-path tracking |
| Переоценка LLM | AI only proposes, rules approve |
| Viewer pipeline | Freeze конвертера, тестирование |

---

## Context7 Resources

Для документации использовать MCP context7:
- `/ifcopenshell/ifcopenshell` — IfcOpenShell API
- `/autodesk/revit-api` — Revit API
- `/tiplerlabs/xeokit` — xeokit Viewer
- `/fastapi/fastapi` — FastAPI
- `/python/fastapi` — Pydantic validation
- `/scikit-learn/scikit-learn` — Anomaly detection