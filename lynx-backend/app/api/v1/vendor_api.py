import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Body

from ...core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vendor"])

_VENDOR_STORAGE_DIR: Path | None = None


def _get_vendor_dir() -> Path:
    global _VENDOR_STORAGE_DIR
    if _VENDOR_STORAGE_DIR is None:
        _VENDOR_STORAGE_DIR = Path(settings.storage_path) / "vendor"
    _VENDOR_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return _VENDOR_STORAGE_DIR


def _project_dir(project_id: str) -> Path:
    d = _get_vendor_dir() / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(project_id: str) -> Path:
    return _project_dir(project_id) / "_meta.json"


def _result_path(project_id: str) -> Path:
    return _project_dir(project_id) / "_parsed.json"


def _load_meta(project_id: str) -> dict:
    p = _meta_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"files": [], "selected": ""}


def _save_meta(project_id: str, meta: dict):
    with open(_meta_path(project_id), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False, indent=2))


def _load_result(project_id: str) -> dict | None:
    p = _result_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_result(project_id: str, data: dict):
    with open(_result_path(project_id), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/projects/{project_id}/vendor")
async def get_vendor(project_id: str):
    """Get vendor list: files + parsed result + editable manufacturers."""
    meta = _load_meta(project_id)
    data = _load_result(project_id) or {}
    manufacturers = data.get("_manufacturers", {}) if isinstance(data, dict) else {}
    result = {k: v for k, v in data.items() if k != "_manufacturers"} if isinstance(data, dict) else {}
    return {
        "files": meta.get("files", []),
        "selected": meta.get("selected", ""),
        "result": result,
        "manufacturers": manufacturers,
    }


@router.post("/projects/{project_id}/vendor/upload", status_code=201)
async def upload_vendor_file(project_id: str, file: UploadFile = File(...)):
    allowed = (".pdf", ".xlsx", ".xls")
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and Excel files allowed")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{ts}_{uuid.uuid4().hex[:8]}{ext}"
    dst = _project_dir(project_id) / stored_name

    with dst.open("wb") as f:
        content = await file.read()
        f.write(content)

    meta = _load_meta(project_id)
    # Add file entry (keep latest first)
    entry = {
        "stored_name": stored_name,
        "display_name": file.filename,
        "size_bytes": len(content),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    meta["files"].insert(0, entry)
    meta["selected"] = stored_name
    _save_meta(project_id, meta)

    logger.info(f"Vendor file uploaded: {file.filename} -> {stored_name} for project {project_id}")
    return entry


@router.get("/projects/{project_id}/vendor/file")
async def download_vendor_file(project_id: str, filename: str = ""):
    from fastapi.responses import FileResponse

    meta = _load_meta(project_id)
    if not filename:
        filename = meta.get("selected", "")
    if not filename:
        raise HTTPException(status_code=404, detail="No vendor file selected")

    file_path = _project_dir(project_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Vendor file not found")

    # Find display name
    display_name = filename
    for f in meta.get("files", []):
        if f.get("stored_name") == filename:
            display_name = f.get("display_name", filename)
            break

    return FileResponse(path=str(file_path), filename=display_name)


@router.delete("/projects/{project_id}/vendor/files")
async def delete_vendor_file(project_id: str, filename: str = ""):
    meta = _load_meta(project_id)
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    file_path = _project_dir(project_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    meta["files"] = [f for f in meta["files"] if f.get("stored_name") != filename]
    if meta.get("selected") == filename:
        meta["selected"] = meta["files"][0]["stored_name"] if meta["files"] else ""
    _save_meta(project_id, meta)

    logger.info(f"Vendor file deleted: {filename} for project {project_id}")
    return {"deleted": filename}


@router.put("/projects/{project_id}/vendor")
async def save_vendor_manufacturers(project_id: str, data: dict = Body(...)):
    """Save editable manufacturer fields."""
    current = _load_result(project_id) or {}
    if not isinstance(current, dict):
        current = {}
    manufacturers = data.get("manufacturers", {})
    current["_manufacturers"] = manufacturers
    _save_result(project_id, current)
    return {"ok": True}


# Demo vendor data
_DEMO_VENDOR_RESULT = {
    "general_notes": "ТЗ MLB 01-04. Основные производители инженерного оборудования.",
    "water_supply_manufacturers": (
        "Насосы: Wilo, Grundfos. "
        "Арматура: Danfoss, Valtec, ADL, Naval, Broen Ballomax, Bugatti, Flamco, Giacomini. "
        "Трубы: РосТурПласт (ПП PN20/PN25), ГОСТ 9941-81 (нерж. сталь). "
        "Изоляция: K-Flex, Armacell, Energoflex Super Protect, Изодом. "
        "Коллекторы: АкваСмарт, Пульсар. "
        "Счётчики: Пульсар."
    ),
    "sewerage_manufacturers": (
        "Насосы: Sololift (Grundfos). "
        "Трубы: РосТурПласт (ПП), SML (чугун), НПВХ ГОСТ 54475-2011, ПЭ ГОСТ 18599-2001. "
        "Изоляция: K-Flex (ливневка). "
        "Воронки: HUTTERER & LECHNER. "
        "Противопожарные муфты: Rehau, Огракс, Огнеза."
    ),
    "fire_fighting_manufacturers": (
        "Насосы: Wilo, Grundfos. "
        "Трубы: ГОСТ 3262-75 (водогазопроводные), ГОСТ 10704-91 (электросварные). "
        "Шкафы: НПО Пульс (ШПК-Пульс). "
        "Оросители: Спецавтоматика, Бийск (СВУ, ДВУ)."
    ),
}
_DEMO_VENDOR_MANUFACTURERS = {
    "water_supply": {
        "pumps": "Wilo, Grundfos",
        "valves": "Danfoss, Valtec, ADL, Naval, Broen Ballomax, Bugatti, Flamco, Giacomini",
        "pipe_fittings": "РосТурПласт (ПП, СП), ГОСТ 9941-81 (нерж. сталь)",
        "insulation": "K-Flex, Armacell, Energoflex Super Protect, Изодом",
        "manifold": "АкваСмарт, Пульсар",
        "additional": "Счётчики воды Пульсар, манометры кл. точности 1,5, гильзы стальные",
    },
    "sewerage": {
        "pumps": "Sololift (Grundfos)",
        "valves": "-",
        "pipe_fittings": "РосТурПласт (ПП), SML (чугун), НПВХ ГОСТ 54475-2011, ПЭ ГОСТ 18599-2001",
        "insulation": "K-Flex (ливневая канализация)",
        "additional": "Воронки HUTTERER & LECHNER, противопожарные муфты Rehau / Огракс / Огнеза",
    },
    "fire_fighting": {
        "pumps": "Wilo, Grundfos",
        "valves": "Задвижки с обрезиненным клином и электроприводом, клапаны обратные чугунные межфланцевые",
        "pipe_fittings": "ГОСТ 3262-75 (водогазопроводные), ГОСТ 10704-91 (электросварные)",
        "insulation": "-",
        "additional": "Шкафы пожарные НПО Пульс (ШПК-Пульс), оросители СВУ/ДВУ (Спецавтоматика, Бийск)",
    },
}


@router.post("/projects/{project_id}/vendor/parse")
async def parse_vendor_file(project_id: str, filename: str = ""):
    from ...api.v1.tz_api import DEMO_MODE
    if DEMO_MODE:
        result = dict(_DEMO_VENDOR_RESULT)
        result["_manufacturers"] = dict(_DEMO_VENDOR_MANUFACTURERS)
        _save_result(project_id, result)
        # Return both result + manufacturers for frontend
        return {**result, "_manufacturers": _DEMO_VENDOR_MANUFACTURERS}

    from ...services.ai.vendor_parser import extract_text_from_file, parse_vendor_document

    meta = _load_meta(project_id)
    if not meta["files"]:
        raise HTTPException(status_code=400, detail="No vendor files uploaded")

    if filename:
        file_path = _project_dir(project_id) / filename
    else:
        selected = meta.get("selected", "")
        file_path = _project_dir(project_id) / selected if selected else None
        if not file_path or not file_path.exists():
            # Pick first file
            first = meta["files"][0]
            file_path = _project_dir(project_id) / first["stored_name"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Vendor file not found")

    text = extract_text_from_file(str(file_path))
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    parsed = await parse_vendor_document(text)
    parsed["_source_file"] = file_path.name
    _save_result(project_id, parsed)

    logger.info(f"Vendor document parsed for project {project_id}")
    return parsed
