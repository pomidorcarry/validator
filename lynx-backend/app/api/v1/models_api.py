from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from pathlib import Path
from sqlalchemy import delete
import uuid
import logging
import json as json_mod

from ...core.config import settings

router = APIRouter(tags=["models"])


@router.post("/models/upload", status_code=202)
async def upload_model(
    background_tasks: BackgroundTasks,
    request: Request,
):
    model_version_id = str(uuid.uuid4())
    storage_dir = Path(settings.storage_path) / "raw"
    storage_dir.mkdir(parents=True, exist_ok=True)

    content_type = request.headers.get("content-type", "")
    boundary = ""
    if "boundary=" in content_type:
        boundary = content_type.split("boundary=")[-1].strip().strip('"').strip("'")

    raw_path = storage_dir / f"{model_version_id}.raw"
    file_size = 0
    with open(raw_path, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            file_size += len(chunk)

    logging.info(f"Raw body saved: {file_size} bytes for {model_version_id}")

    async def process_raw_upload(mvid: str, raw_path: Path, boundary: str):
        try:
            project_id = "820377a6-9d06-486a-bf87-0c9fc815ef44"
            model_name = "RevitUpload"
            ruleset_id = "default"
            filename = None

            with open(raw_path, "rb") as f:
                raw_data = f.read()

            if boundary:
                parts = raw_data.split(f"--{boundary}".encode())
                for part in parts:
                    if b"Content-Disposition:" not in part:
                        continue
                    header_end = part.find(b"\r\n\r\n")
                    if header_end < 0:
                        continue
                    header_section = part[:header_end].decode("utf-8", errors="replace")
                    body = part[header_end + 4:]
                    body = body.rstrip(b"\r\n--")
                    body = body.rstrip(b"\r\n")

                    field_name = ""
                    is_file = False
                    fname = ""
                    for line in header_section.split("\r\n"):
                        if line.lower().startswith("content-disposition:"):
                            for piece in line.split(";"):
                                piece = piece.strip()
                                if piece.startswith("name="):
                                    field_name = piece.split("=", 1)[1].strip('"').strip("'")
                                if piece.startswith("filename="):
                                    is_file = True
                                    fname = piece.split("=", 1)[1].strip('"').strip("'")

                    if is_file and body:
                        filename = fname
                        dst = storage_dir / f"{mvid}.ifc"
                        with open(dst, "wb") as outf:
                            outf.write(body)
                    elif field_name == "project_id":
                        project_id = body.decode("utf-8", errors="replace").strip()
                    elif field_name == "model_name":
                        model_name = body.decode("utf-8", errors="replace").strip()
                    elif field_name == "ruleset_id":
                        ruleset_id = body.decode("utf-8", errors="replace").strip()
                    elif field_name == "element_id_map":
                        value = body.decode("utf-8", errors="replace").strip()
                        if value:
                            try:
                                revit_map = json_mod.loads(value)
                                map_path = storage_dir / f"{mvid}.revit_ids.json"
                                with open(map_path, "w", encoding="utf-8") as mf:
                                    mf.write(json_mod.dumps(revit_map, ensure_ascii=False))
                            except Exception:
                                pass

            logging.info(f"Raw multipart parsed: pid={project_id} name={model_name} file={filename}")

            resolved = project_id
            from ...db.models import list_projects as _list_projects
            all_projects = await _list_projects()
            for p in all_projects:
                keywords = (p.get("auto_bind_keywords") or "").strip()
                if not keywords:
                    continue
                for kw in keywords.split(","):
                    kw = kw.strip().lower()
                    if kw and kw in model_name.lower():
                        resolved = p["id"]
                        break
                if resolved != project_id:
                    break

            from ...db.models import create_model_version
            mv = await create_model_version(
                model_version_id=mvid,
                project_id=resolved,
                model_name=model_name,
                ruleset_id=ruleset_id,
                filename=filename or "model.ifc",
            )

            from ...services.ifc_normalizer import process_model_version
            await process_model_version(mvid)

            raw_path.unlink(missing_ok=True)
        except Exception as e:
            logging.error(f"Background multipart parse failed for {mvid}: {e}", exc_info=True)
            raise

    if settings.demo_mode:
        async def process_raw_upload_demo(mvid: str, raw_path: Path, boundary: str):
            try:
                project_id = "820377a6-9d06-486a-bf87-0c9fc815ef44"
                model_name = "RevitUpload"
                ruleset_id = "default"
                filename = None

                with open(raw_path, "rb") as f:
                    raw_data = f.read()

                if boundary:
                    parts = raw_data.split(f"--{boundary}".encode())
                    for part in parts:
                        if b"Content-Disposition:" not in part:
                            continue
                        header_end = part.find(b"\r\n\r\n")
                        if header_end < 0:
                            continue
                        header_section = part[:header_end].decode("utf-8", errors="replace")
                        body = part[header_end + 4:]
                        body = body.rstrip(b"\r\n--")
                        body = body.rstrip(b"\r\n")

                        field_name = ""
                        for line in header_section.split("\r\n"):
                            if line.lower().startswith("content-disposition:"):
                                for piece in line.split(";"):
                                    piece = piece.strip()
                                    if piece.startswith("name="):
                                        field_name = piece.split("=", 1)[1].strip('"').strip("'")
                                    if piece.startswith("filename="):
                                        filename = piece.split("=", 1)[1].strip('"').strip("'")

                        if field_name == "project_id":
                            project_id = body.decode("utf-8", errors="replace").strip()
                        elif field_name == "model_name":
                            model_name = body.decode("utf-8", errors="replace").strip()

                import shutil
                seed_ifc = None
                for f in sorted(storage_dir.glob("*.ifc"), key=lambda p: p.stat().st_mtime, reverse=True):
                    seed_ifc = f
                    break
                if seed_ifc:
                    dst = storage_dir / f"{mvid}.ifc"
                    shutil.copy2(str(seed_ifc), str(dst))
                    logging.info(f"Demo: copied seed IFC {seed_ifc.name} → {mvid}.ifc")
                else:
                    logging.warning("Demo: no seed IFC found, using uploaded file")

                from ...db.models import create_model_version
                mv = await create_model_version(
                    model_version_id=mvid,
                    project_id=project_id,
                    model_name=model_name,
                    ruleset_id=ruleset_id,
                    filename=filename or "model.ifc",
                )

                from ...services.ifc_normalizer import process_model_version
                await process_model_version(mvid)

                raw_path.unlink(missing_ok=True)
            except Exception as e:
                logging.error(f"Demo upload failed for {mvid}: {e}", exc_info=True)

        background_tasks.add_task(process_raw_upload_demo, model_version_id, raw_path, boundary)
    else:
        background_tasks.add_task(process_raw_upload, model_version_id, raw_path, boundary)
    logging.info(f"Upload background task queued for {model_version_id}, size={file_size}")
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
