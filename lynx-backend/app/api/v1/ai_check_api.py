from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ai-check"])


@router.post("/projects/{project_id}/ai-check")
async def run_ai_check(project_id: str):
    from ...core.config import settings as _settings

    if _settings.demo_mode:
        import json as _json
        from pathlib import Path
        demo_errors_path = Path(__file__).parent.parent.parent.parent / "demo_errors.json"
        if demo_errors_path.exists():
            demo_data = _json.loads(demo_errors_path.read_text(encoding="utf-8"))
            v1_problems = demo_data.get("v1", {}).get("ai_problems", [])
            from ...db.models import save_ai_check_result
            await save_ai_check_result(project_id, v1_problems)
            return {"problems": v1_problems, "count": len(v1_problems), "demo": True}

    from ...services.ai.ai_check import run_ai_check as _run_ai_check
    from ...db.models import get_project as _get_project

    project = await _get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from ...db.models import list_all_models
    all_models = await list_all_models(project_id=project_id)
    processed_models = [m for m in all_models if m.get("status") == "processed"]

    if not processed_models:
        raise HTTPException(
            status_code=400,
            detail="Нет обработанных моделей в проекте. Сначала загрузите и обработайте IFC-модель."
        )

    from ...db.models import get_elements
    all_elements = []
    for m in processed_models:
        elems = await get_elements(m["id"])
        all_elements.extend(elems)

    from ...db.models import get_project_tz as _get_tz
    tz_data = await _get_tz(project_id)
    if tz_data is None:
        tz_data = {}

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"AI check: {len(all_elements)} elements, {len(processed_models)} models for project {project_id}")

    problems = await _run_ai_check(project_id, all_elements, tz_data)

    from ...db.models import save_ai_check_result, get_ai_check_result
    await save_ai_check_result(project_id, problems)

    return {"problems": problems, "count": len(problems)}


@router.get("/projects/{project_id}/ai-check")
async def get_ai_check(project_id: str):
    from ...core.config import settings as _settings

    # In demo mode, always serve fresh data from demo_errors.json
    if _settings.demo_mode:
        import json as _json
        from pathlib import Path
        demo_path = Path(__file__).parent.parent.parent.parent / "demo_errors.json"
        if demo_path.exists():
            demo_data = _json.loads(demo_path.read_text(encoding="utf-8"))
            problems = demo_data.get("v1", {}).get("ai_problems", [])
            return {"problems": problems, "count": len(problems), "demo": True}
        return {"problems": [], "count": 0, "demo": True}

    from ...db.models import get_ai_check_result as _get_result
    result = await _get_result(project_id)
    if result is None:
        return {"problems": [], "count": 0, "has_result": False}
    return {"problems": result.get("problems", []), "count": len(result.get("problems", [])), "has_result": True}


@router.patch("/projects/{project_id}/ai-check/{problem_index}")
async def dismiss_ai_problem(project_id: str, problem_index: int, dismissed: bool = True):
    from ...db.models import get_ai_check_result, save_ai_check_result
    result = await get_ai_check_result(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No AI check result found")

    problems = result.get("problems", [])
    if problem_index < 0 or problem_index >= len(problems):
        raise HTTPException(status_code=404, detail="Problem not found")

    problems[problem_index]["dismissed"] = dismissed
    await save_ai_check_result(project_id, problems)

    return {"dismissed": dismissed, "problem_index": problem_index}
