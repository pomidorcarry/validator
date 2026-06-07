# Lynx — repo guide

## Quick start

```bash
# Backend (Python 3.11+, port 8000)
cd lynx-backend
pip install -r requirements.txt
# Required for AI: create .env with OPENAI_API_KEY=sk-...
uvicorn app.main:app --reload --port 8000

# Frontend (Vanilla JS + Vite, port 8080)
cd lynx-frontend
npm install
npm run dev        # vite --host 0.0.0.0 --port 8080

# Revit plugin (C# .NET 4.8, x64)
# Build Release|x64 in Visual Studio, then copy LynxRevitPlugin.dll + .addin
# to %APPDATA%\Autodesk\Revit\Addins\2025\
```

## Architecture

```
lynx-revit-plugin/    C# Revit 2025 add-in (.NET 4.8, WinForms)
  App.cs              Ribbon tab "Lynx" with 3 buttons
  ExportIfcCommand    IFC export → multipart upload
  SettingsCommand     URL / Project ID / Ruleset ID config
  ApplyFixesCommand   GET approved fix suggestions → apply via Transaction

lynx-backend/         FastAPI (async, SQLAlchemy + aiosqlite)
  app/main.py         includes 10 routers (health, ai_status, projects,
                      models, categories, tz, ai_check, fix_suggestions,
                      vendor, changes)
  app/core/config.py  Pydantic Settings from .env; loads HTTP_PROXY/HTTPS_PROXY
                      from .env before init (so httpx/openai pick them up)
  app/db/
    base.py           async engine, init_db(), migration logic (auto-ALTER)
    models_orm.py     ORM: Project, Ruleset, ProjectCategory, ModelVersion,
                      Artifact, Element, ElementMeasurement, Issue,
                      AISuggestion, AuditLog, Report, TzVersion
    models.py         re-exports ORM + CRUD
    element_storage.py JSON blobs stored on filesystem (not DB columns)
    crud.py           all CRUD functions
  app/services/
    ifc_normalizer.py IfcOpenShell normalization
    rule_engine.py    IDS + custom checks
    xkt_converter.py  IFC → XKT (xeokit)
    ai/               client.py, tz_parser.py, ai_check.py, fix_generator.py,
                      vendor_parser.py
  storage/            raw/ xkt/ tz/ ai_check/ fix_suggestions/ elements/

lynx-frontend/        Vanilla JS SPA (ES Modules, no framework)
  src/main.js         entry point (~15 lines: imports + init)
  src/api.js          API_BASE constant
  src/viewer.js       Three.js 3D renderer (xeokit not used)
  11 more modules: navigation, projects, models, tzView, dataView,
                   aiCheck, categories, changesView, themes, utils
```

## Key facts

- **No README.md** — full docs are in `DOCS.md` (Russian). Update it for significant changes.
- **Frontend is plain JS**, not React/Vue. Vite serves on port 8080.
- **Backend async SQLite** — DB auto-created on first run (`init_db` in lifespan). Migration logic in `base.py` runs `ALTER TABLE` automatically.
- **Element JSON** — `raw_psets_jsonb` and `normalized_jsonb` are migrated from DB to `storage/elements/*.json` files. Check `element_storage.py` before querying.
- **AI requires `.env`** with `OPENAI_API_KEY`. Proxy env vars in `.env` are loaded before pydantic-settings (affects httpx/openai).
- **Config uses `.opencode/config.json`** — skills: `revit-extension-development`, `dotnet-backend`, `agent-development`. Skill files at `.opencode/skills/`.
- **Context7 MCP** configured in `opencode.json` for library docs (IfcOpenShell, Revit API, FastAPI, etc.).
- Revit plugin references DLLs from `C:\Program Files\Autodesk\Revit 2025\` — adjust paths for other versions.
- `.gitignore` excludes: `lynx.db`, `storage/*/*.ifc/xkt/pdf/xlsx`, `.env`, `node_modules/`, `dist/`, `bin/`, `obj/`, `.opencode/`.

## Workflow

- **Revit plugin (C#/.NET)** — edit & build locally in Visual Studio. `lynx-revit-plugin/` is the source.
  Copy built `.dll` + `.addin` to `%APPDATA%\Autodesk\Revit\Addins\2025\` to test.
- **Backend (Python)** — deploy changes directly to server at `/opt/lynx/lynx-backend/`.
  Sync file(s) via SSH, then `systemctl restart lynx-backend`.
- **Frontend (JS/Vite)** — make changes locally or on server, then `cd /opt/lynx/lynx-frontend && npm run build` on server.
- **Server details** — Hetzner VPS at `157.22.175.197`, root SSH access, `lynxbim.duckdns.org`.
  Nginx at `/etc/nginx/sites-available/lynx`, systemd service `lynx-backend.service`.
- **Git** — remote is `git@github.com:pomidorcarry/validator.git` (SSH). Server has deploy key for push.
