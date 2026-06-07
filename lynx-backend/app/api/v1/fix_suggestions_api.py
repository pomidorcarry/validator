import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from ...core.config import settings
from ...db import models as db_models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fix-suggestions"])


FIX_DIR: Optional[Path] = None


def _ensure_fix_dir() -> Path:
    global FIX_DIR
    if FIX_DIR is None:
        d = Path(settings.storage_path) / "fix_suggestions"
        d.mkdir(parents=True, exist_ok=True)
        FIX_DIR = d
    return FIX_DIR


def _load_fixes(project_id: str) -> list:
    p = _ensure_fix_dir() / f"{project_id}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text("utf-8"))
        return data.get("fixes", [])
    except Exception:
        return []


def _save_fixes(project_id: str, fixes: list) -> None:
    from datetime import datetime
    p = _ensure_fix_dir() / f"{project_id}.json"
    p.write_text(json.dumps({
        "project_id": project_id,
        "fixes": fixes,
        "updated_at": datetime.utcnow().isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/projects/{project_id}/fix-suggestions")
async def generate_fix_suggestions(project_id: str):
    """Generate fix suggestions from AI check results."""
    from ...core.config import settings as _settings

    if _settings.demo_mode:
        import json as _json
        from pathlib import Path
        demo_errors_path = Path(__file__).parent.parent.parent.parent / "demo_errors.json"
        if demo_errors_path.exists():
            demo_data = _json.loads(demo_errors_path.read_text(encoding="utf-8"))
            fixes = demo_data.get("v1", {}).get("fix_suggestions", [])
            ai_problems = demo_data.get("v1", {}).get("ai_problems", [])
            for fix in fixes:
                issue_idx = fix.get("issue_index")
                if issue_idx is not None and 0 <= issue_idx < len(ai_problems):
                    fix["issue_message"] = ai_problems[issue_idx].get("message", "")
                    fix["issue_severity"] = ai_problems[issue_idx].get("severity", "warning")
            _save_fixes(project_id, fixes)
            return {"fixes": fixes, "count": len(fixes), "demo": True}

    from ..services.ai.fix_generator import generate_fixes as _generate

    project = await db_models.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ai_result = await db_models.get_ai_check_result(project_id)
    if not ai_result:
        raise HTTPException(status_code=400, detail="No AI check results found. Run AI check first.")
    
    all_issues = ai_result.get("problems", [])
    unresolved = [i for i in all_issues if not i.get("dismissed")]
    if not unresolved:
        return {"fixes": [], "count": 0, "message": "Нет нерешенных проблем"}
    
    all_models = await db_models.list_all_models(project_id=project_id)
    processed = [m for m in all_models if m.get("status") == "processed"]
    all_elements = []
    for m in processed:
        elems = await db_models.get_elements(m["id"])
        all_elements.extend(elems)
    
    tz_data = await db_models.get_project_tz(project_id) or {}
    
    fixes = await _generate(unresolved, all_elements, tz_data)
    
    for fix in fixes:
        issue_idx = fix.get("issue_index")
        if issue_idx is not None and 0 <= issue_idx < len(all_issues):
            fix["issue_message"] = all_issues[issue_idx].get("message", "")
            fix["issue_severity"] = all_issues[issue_idx].get("severity", "warning")
    
    _save_fixes(project_id, fixes)
    
    return {"fixes": fixes, "count": len(fixes)}


@router.get("/projects/{project_id}/fix-suggestions")
async def get_fix_suggestions(
    project_id: str,
    status: str = "",
):
    """Get fix suggestions, optionally filtered by status."""
    fixes = _load_fixes(project_id)
    if status:
        fixes = [f for f in fixes if f.get("status") == status]
    return {"fixes": fixes, "count": len(fixes)}


@router.patch("/projects/{project_id}/fix-suggestions/{fix_id}")
async def update_fix_suggestion(
    project_id: str,
    fix_id: str,
    status: str = "approved",
):
    """Approve or reject a fix suggestion."""
    if status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Status must be: approved, rejected, or pending")
    
    fixes = _load_fixes(project_id)
    found = False
    for fix in fixes:
        if fix.get("fix_id") == fix_id:
            fix["status"] = status
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail=f"Fix {fix_id} not found")
    
    _save_fixes(project_id, fixes)
    return {"fix_id": fix_id, "status": status}


@router.patch("/projects/{project_id}/fix-suggestions")
async def batch_update_fixes(
    project_id: str,
    fix_ids: list[str],
    status: str = "approved",
):
    """Approve/reject multiple fixes at once."""
    if status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Status must be: approved, rejected, or pending")
    
    fixes = _load_fixes(project_id)
    updated = []
    for fix in fixes:
        if fix.get("fix_id") in fix_ids:
            fix["status"] = status
            updated.append(fix["fix_id"])
    
    _save_fixes(project_id, fixes)
    return {"updated": updated, "count": len(updated)}


@router.post("/projects/{project_id}/fix-suggestions/{fix_id}/result")
async def report_fix_result(
    project_id: str,
    fix_id: str,
    success: bool = True,
    error_message: str = "",
):
    """Revit plugin reports the result of applying a fix."""
    fixes = _load_fixes(project_id)
    found = False
    for fix in fixes:
        if fix.get("fix_id") == fix_id:
            fix["applied_result"] = {
                "success": success,
                "error_message": error_message,
                "applied_at": __import__("datetime").datetime.utcnow().isoformat(),
            }
            if success:
                fix["status"] = "applied"
            else:
                fix["status"] = "failed"
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail=f"Fix {fix_id} not found")
    
    _save_fixes(project_id, fixes)
    return {"fix_id": fix_id, "status": fix["status"], "success": success}
