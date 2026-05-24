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
    from .db.models import create_model_version
    
    mv = await create_model_version(
        model_version_id=model_version_id,
        project_id=project_id,
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
async def list_models():
    from .db.models import list_all_models
    
    models = await list_all_models()
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