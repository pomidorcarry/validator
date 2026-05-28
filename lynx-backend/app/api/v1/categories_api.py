from fastapi import APIRouter, Form, HTTPException

router = APIRouter(tags=["categories"])


@router.get("/projects/{project_id}/categories")
async def get_project_categories(project_id: str):
    from ...db.models import list_project_categories

    cats = await list_project_categories(project_id)
    return {"categories": cats, "count": len(cats)}


@router.put("/projects/{project_id}/categories")
async def update_project_categories(project_id: str, categories: str = Form(...)):
    from ...db.models import save_project_categories
    import json

    try:
        cat_list = json.loads(categories)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    cats = await save_project_categories(project_id, cat_list)
    return {"categories": cats, "count": len(cats)}
