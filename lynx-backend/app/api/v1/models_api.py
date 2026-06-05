from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from pathlib import Path
from sqlalchemy import delete
import uuid

from ...core.config import settings

router = APIRouter(tags=["models"])


@router.post("/models/upload", status_code=202)
async def upload_model(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    model_name: str = Form(...),
    ruleset_id: str = Form(...),
    element_id_map: str = Form("{}"),
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

    # Save Revit element ID map (GlobalId → Revit ElementId)
    import json
    try:
        revit_map = json.loads(element_id_map)
    except json.JSONDecodeError:
        revit_map = {}
    if revit_map:
        map_path = storage_dir / f"{model_version_id}.revit_ids.json"
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(revit_map, f, ensure_ascii=False)

    from ...services.ifc_normalizer import process_model_version
    from ...db.models import create_model_version, list_projects as _list_projects

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


@router.get("/models")
async def list_models(project_id: str = None):
    from ...db.models import list_all_models

    models = await list_all_models(project_id=project_id)
    return {"models": models, "count": len(models)}


@router.delete("/models")
async def delete_all_models():
    from ...db.base import async_session
    from ...db.models import ModelVersion, Element, Issue, Artifact

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


@router.get("/models/{model_version_id}")
async def get_model(model_version_id: str):
    from ...db.models import get_model_version

    mv = await get_model_version(model_version_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return mv


@router.delete("/models/{model_version_id}")
async def delete_model(model_version_id: str):
    from ...db.base import async_session
    from ...db.models import ModelVersion, Element, Issue, Artifact

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


@router.get("/models/{model_version_id}/status")
async def get_model_status(model_version_id: str):
    from ...db.models import get_model_version

    mv = await get_model_version(model_version_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"model_version_id": model_version_id, "status": mv["status"]}


@router.get("/models/{model_version_id}/issues")
async def get_model_issues(model_version_id: str):
    from ...db.models import get_issues

    issues = await get_issues(model_version_id)
    return {"issues": issues, "count": len(issues)}


@router.get("/models/{model_version_id}/elements")
async def get_model_elements(model_version_id: str):
    from ...db.models import get_elements

    elements = await get_elements(model_version_id)
    return {"elements": elements, "count": len(elements)}


@router.post("/models/{model_version_id}/repair-materials")
async def repair_materials(model_version_id: str):
    from ...services.ifc_normalizer import repair_materials as _repair

    count = await _repair(model_version_id)
    return {"model_version_id": model_version_id, "elements_updated": count}


@router.post("/models/{model_version_id}/reprocess-rules")
async def reprocess_rules(model_version_id: str):
    from ...services.rule_engine import run_rules
    from ...db.base import async_session
    from ...db.models import Issue
    from sqlalchemy import delete

    async with async_session() as session:
        await session.execute(delete(Issue).where(Issue.model_version_id == model_version_id))
        await session.commit()

    count = await run_rules(model_version_id)
    return {"model_version_id": model_version_id, "issues_created": count}


@router.get("/models/{model_version_id}/ifc")
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


@router.get("/models/{model_version_id}/xkt")
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


@router.put("/models/{model_id}/move")
async def move_model(model_id: str, target_project_id: str = Form(...)):
    from ...db.models import move_model_to_project

    mv = await move_model_to_project(model_id, target_project_id)
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    return mv
