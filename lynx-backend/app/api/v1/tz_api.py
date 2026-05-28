from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path

from ...core.config import settings

router = APIRouter(tags=["tz"])


@router.get("/projects/{project_id}/tz")
async def get_project_tz(project_id: str):
    from ...db.models import get_project_tz as _get_tz

    tz = await _get_tz(project_id)
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@router.put("/projects/{project_id}/tz")
async def update_project_tz(project_id: str, data: dict):
    from ...db.models import update_project_tz as _update_tz

    tz = await _update_tz(project_id, data, source="manual")
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@router.post("/projects/{project_id}/tz/upload", status_code=201)
async def upload_tz_file(project_id: str, file: UploadFile = File(...)):
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

    import json as _json
    meta_file = dst.with_name(dst.name + ".meta")
    meta_file.write_text(_json.dumps({"original_name": file.filename}))

    now = datetime.utcnow()
    return {
        "file_name": file.filename,
        "stored_name": stored_name,
        "file_path": str(dst),
        "uploaded_at": now.isoformat(),
    }


@router.get("/projects/{project_id}/tz/files")
async def list_tz_files(project_id: str):
    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls"):
            from datetime import datetime
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            display_name = f.stem
            meta_file = f.with_name(f.name + ".meta")
            if meta_file.exists():
                try:
                    import json as _json
                    meta = _json.loads(meta_file.read_text())
                    display_name = meta.get("original_name", f.stem)
                except Exception:
                    pass
            files.append({
                "stored_name": f.name,
                "display_name": display_name,
                "size_bytes": f.stat().st_size,
                "uploaded_at": mtime.isoformat(),
            })
    return {"files": files}


@router.delete("/projects/{project_id}/tz/files")
async def delete_tz_file(project_id: str, filename: str = ""):
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    file_path = tz_dir / filename
    meta_path = tz_dir / (filename + ".meta")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    if meta_path.exists():
        meta_path.unlink()

    return {"deleted": filename}


@router.post("/projects/{project_id}/tz/parse")
async def parse_tz_file(project_id: str, filename: str = ""):
    from ...services.ai.tz_parser import extract_text_from_file, parse_tz_document

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        raise HTTPException(status_code=400, detail="No TZ files found for this project")

    if filename:
        file_path = tz_dir / filename
    else:
        tz_files = sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        tz_files = [f for f in tz_files if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls")]
        if not tz_files:
            raise HTTPException(status_code=400, detail="No TZ files found")
        file_path = tz_files[0]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="TZ file not found")

    text = extract_text_from_file(str(file_path))
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    parsed = await parse_tz_document(text)
    parsed["_source_file"] = file_path.name
    return parsed


@router.get("/projects/{project_id}/tz/file")
async def download_tz_file(project_id: str, filename: str = ""):
    from fastapi.responses import FileResponse

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        raise HTTPException(status_code=404, detail="No TZ files found")

    if filename:
        file_path = tz_dir / filename
    else:
        tz_files = sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        tz_files = [f for f in tz_files if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls")]
        if not tz_files:
            raise HTTPException(status_code=404, detail="No TZ files found")
        file_path = tz_files[0]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="TZ file not found")

    display_name = file_path.name[20:] if "_" in file_path.name and len(file_path.name) > 20 else file_path.name
    return FileResponse(path=str(file_path), filename=display_name)


@router.get("/projects/{project_id}/tz/history")
async def get_tz_history(project_id: str):
    from ...db.models import get_tz_history as _get_history

    history = await _get_history(project_id)
    return {"versions": history, "count": len(history)}
