from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from sqlalchemy import delete
import uuid
from contextlib import asynccontextmanager

from .core.config import settings
from .db.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "Lynx Backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    return {"status": "healthy"}


@app.get(f"{settings.api_prefix}/ai/status")
async def ai_status(check: bool = False):
    from .core.config import settings as _cfg
    
    configured = bool(_cfg.openai_api_key)
    result = {"configured": configured, "responsive": None, "error_detail": None}
    
    if configured and check:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=_cfg.openai_api_key)
            await client.models.list()
            result["responsive"] = True
        except openai.PermissionDeniedError as e:
            result["responsive"] = False
            result["error_detail"] = "Регион не поддерживается (403)"
        except openai.AuthenticationError as e:
            result["responsive"] = False
            result["error_detail"] = "Неверный API-ключ"
        except Exception as e:
            result["responsive"] = False
            result["error_detail"] = str(e)[:200]
    
    return result


@app.post(f"{settings.api_prefix}/models/upload", status_code=202)
async def upload_model(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    model_name: str = Form(...),
    ruleset_id: str = Form(...),
):
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(status_code=400, detail="Only IFC files allowed")

    model_version_id = str(uuid.uuid4())
    storage_dir = Path(settings.storage_path) / "raw"
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    dst = storage_dir / f"{model_version_id}.ifc"
    with dst.open("wb") as f:
        content = await file.read()
        f.write(content)

    from .services.ifc_normalizer import process_model_version
    from .db.models import create_model_version, list_projects as _list_projects
    
    # Auto-bind by keyword: check if model_name matches any project's auto_bind_keywords
    resolved_project_id = project_id
    model_name_lower = model_name.lower()
    all_projects = await _list_projects()
    for p in all_projects:
        keywords = (p.get("auto_bind_keywords") or "").strip()
        if not keywords:
            continue
        for kw in keywords.split(","):
            kw = kw.strip().lower()
            if kw and kw in model_name_lower:
                resolved_project_id = p["id"]
                break
        if resolved_project_id != project_id:
            break
    
    mv = await create_model_version(
        model_version_id=model_version_id,
        project_id=resolved_project_id,
        model_name=model_name,
        ruleset_id=ruleset_id,
        filename=file.filename,
    )
    
    background_tasks.add_task(process_model_version, model_version_id)
    import logging
    logging.info(f"Started background task for model {model_version_id}")

    return {"model_version_id": model_version_id, "status": "queued"}


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}")
async def get_model(model_version_id: str):
    from .db.models import get_model_version
    
    mv = await get_model_version(model_version_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return mv


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}/status")
async def get_model_status(model_version_id: str):
    from .db.models import get_model_version
    
    mv = await get_model_version(model_version_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"model_version_id": model_version_id, "status": mv["status"]}


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}/issues")
async def get_model_issues(model_version_id: str):
    from .db.models import get_issues
    
    issues = await get_issues(model_version_id)
    return {"issues": issues, "count": len(issues)}


@app.get(f"{settings.api_prefix}/models")
async def list_models(project_id: str = None):
    from .db.models import list_all_models
    
    models = await list_all_models(project_id=project_id)
    return {"models": models, "count": len(models)}


@app.delete(f"{settings.api_prefix}/models")
async def delete_all_models():
    from .db.models import async_session, ModelVersion, Element, Issue, Artifact
    
    async with async_session() as session:
        await session.execute(delete(Issue))
        await session.execute(delete(Element))
        await session.execute(delete(Artifact))
        await session.execute(delete(ModelVersion))
        await session.commit()
    
    import shutil
    raw = Path(settings.storage_path) / "raw"
    xkt = Path(settings.storage_path) / "xkt"
    for p in [raw, xkt]:
        if p.exists():
            for f in p.glob("*"):
                f.unlink()
    
    return {"deleted": True}


@app.delete(f"{settings.api_prefix}/models/{{model_version_id}}")
async def delete_model(model_version_id: str):
    from .db.models import async_session, ModelVersion, Element, Issue, Artifact
    
    async with async_session() as session:
        await session.execute(delete(Issue).where(Issue.model_version_id == model_version_id))
        await session.execute(delete(Element).where(Element.model_version_id == model_version_id))
        await session.execute(delete(Artifact).where(Artifact.model_version_id == model_version_id))
        await session.execute(delete(ModelVersion).where(ModelVersion.id == model_version_id))
        await session.commit()
    
    import shutil
    raw = Path(settings.storage_path) / "raw" / f"{model_version_id}.ifc"
    xkt = Path(settings.storage_path) / "xkt" / f"{model_version_id}.xkt"
    for f in [raw, xkt]:
        if f.exists():
            f.unlink()
    
    return {"deleted": model_version_id}


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}/elements")
async def get_model_elements(model_version_id: str):
    from .db.models import get_elements
    
    elements = await get_elements(model_version_id)
    return {"elements": elements, "count": len(elements)}


@app.post(f"{settings.api_prefix}/models/{{model_version_id}}/reprocess-rules")
async def reprocess_rules(model_version_id: str):
    from .services.rule_engine import run_rules
    from .db.models import async_session, Issue
    from sqlalchemy import delete
    
    async with async_session() as session:
        await session.execute(delete(Issue).where(Issue.model_version_id == model_version_id))
        await session.commit()
    
    count = await run_rules(model_version_id)
    return {"model_version_id": model_version_id, "issues_created": count}


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}/ifc")
async def get_model_ifc(model_version_id: str):
    from pathlib import Path
    
    ifc_path = Path(settings.storage_path) / "raw" / f"{model_version_id}.ifc"
    if not ifc_path.exists():
        raise HTTPException(status_code=404, detail="IFC file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(ifc_path),
        media_type="application/octet-stream",
        filename=f"{model_version_id}.ifc"
    )


@app.get(f"{settings.api_prefix}/models/{{model_version_id}}/xkt")
async def get_model_xkt(model_version_id: str):
    from pathlib import Path
    
    xkt_path = Path(settings.storage_path) / "xkt" / f"{model_version_id}.xkt"
    if not xkt_path.exists():
        raise HTTPException(status_code=404, detail="XKT file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(xkt_path),
        media_type="application/octet-stream",
        filename=f"{model_version_id}.xkt"
    )


# ── Projects ─────────────────────────────────────────────────────

@app.get(f"{settings.api_prefix}/projects")
async def list_projects():
    from .db.models import list_projects as _list_projects
    
    projects = await _list_projects()
    return {"projects": projects, "count": len(projects)}


@app.post(f"{settings.api_prefix}/projects", status_code=201)
async def create_project(
    code: str = Form(...),
    name: str = Form(...),
    technical_specification: str = Form(default=""),
    auto_bind_keywords: str = Form(default=""),
):
    from .db.models import create_project as _create_project
    
    project_id = str(uuid.uuid4())
    p = await _create_project(
        project_id=project_id,
        code=code,
        name=name,
        technical_specification=technical_specification,
        auto_bind_keywords=auto_bind_keywords,
    )
    return p


@app.get(f"{settings.api_prefix}/projects/{{project_id}}")
async def get_project(project_id: str):
    from .db.models import get_project as _get_project
    
    p = await _get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@app.put(f"{settings.api_prefix}/projects/{{project_id}}")
async def update_project(
    project_id: str,
    name: str = Form(default=None),
    technical_specification: str = Form(default=None),
    auto_bind_keywords: str = Form(default=None),
):
    from .db.models import update_project as _update_project
    
    p = await _update_project(
        project_id=project_id,
        name=name,
        technical_specification=technical_specification,
        auto_bind_keywords=auto_bind_keywords,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@app.delete(f"{settings.api_prefix}/projects/{{project_id}}")
async def delete_project(project_id: str):
    from .db.models import delete_project as _delete_project
    
    ok = await _delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": project_id}


# ── Model move ───────────────────────────────────────────────────

@app.put(f"{settings.api_prefix}/models/{{model_id}}/move")
async def move_model(model_id: str, target_project_id: str = Form(...)):
    from .db.models import move_model_to_project
    
    mv = await move_model_to_project(model_id, target_project_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return mv


# ── Project Categories ──────────────────────────────────────────

@app.get(f"{settings.api_prefix}/projects/{{project_id}}/categories")
async def get_project_categories(project_id: str):
    from .db.models import list_project_categories
    
    cats = await list_project_categories(project_id)
    return {"categories": cats, "count": len(cats)}


@app.put(f"{settings.api_prefix}/projects/{{project_id}}/categories")
async def update_project_categories(project_id: str, categories: str = Form(...)):
    from .db.models import save_project_categories
    import json
    
    try:
        cat_list = json.loads(categories)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    cats = await save_project_categories(project_id, cat_list)
    return {"categories": cats, "count": len(cats)}


# ── TZ (Technical Specification) ─────────────────────────────────


@app.get(f"{settings.api_prefix}/projects/{{project_id}}/tz")
async def get_project_tz(project_id: str):
    from .db.models import get_project_tz as _get_tz
    
    tz = await _get_tz(project_id)
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@app.put(f"{settings.api_prefix}/projects/{{project_id}}/tz")
async def update_project_tz(project_id: str, data: dict):
    from .db.models import update_project_tz as _update_tz
    
    tz = await _update_tz(project_id, data, source="manual")
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@app.post(f"{settings.api_prefix}/projects/{{project_id}}/tz/upload", status_code=201)
async def upload_tz_file(project_id: str, file: UploadFile = File(...)):
    from .db.models import get_project_tz as _get_tz, update_project_tz as _update_tz
    
    allowed = (".pdf", ".xlsx", ".xls")
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and Excel files allowed")
    
    from datetime import datetime
    import uuid
    
    tz_dir = Path(settings.storage_path) / "tz" / project_id
    tz_dir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{ts}_{uuid.uuid4().hex[:8]}{ext}"
    dst = tz_dir / stored_name
    
    with dst.open("wb") as f:
        content = await file.read()
        f.write(content)
    
    now = datetime.utcnow()
    await _update_tz(project_id, {
        "tz_file_name": file.filename,
        "tz_file_path": str(dst),
        "tz_file_uploaded_at": now,
    }, source="upload")
    
    return {
        "file_name": file.filename,
        "file_path": str(dst),
        "uploaded_at": now.isoformat(),
    }


@app.post(f"{settings.api_prefix}/projects/{{project_id}}/tz/parse")
async def parse_tz_file(project_id: str):
    from .db.models import get_project_tz as _get_tz, update_project_tz as _update_tz
    from .services.ai.tz_parser import extract_text_from_file, parse_tz_document
    
    tz = await _get_tz(project_id)
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    file_path = tz.get("tz_file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=400, detail="No TZ file uploaded")
    
    text = extract_text_from_file(file_path)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")
    
    parsed = await parse_tz_document(text)
    result = await _update_tz(project_id, parsed, source="ai")
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get(f"{settings.api_prefix}/projects/{{project_id}}/tz/file")
async def download_tz_file(project_id: str):
    from .db.models import get_project_tz as _get_tz
    from fastapi.responses import FileResponse
    
    tz = await _get_tz(project_id)
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    file_path = tz.get("tz_file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="TZ file not found")
    
    return FileResponse(
        path=file_path,
        filename=tz.get("tz_file_name") or Path(file_path).name,
    )


@app.get(f"{settings.api_prefix}/projects/{{project_id}}/tz/history")
async def get_tz_history(project_id: str):
    from .db.models import get_tz_history as _get_history
    
    history = await _get_history(project_id)
    return {"versions": history, "count": len(history)}