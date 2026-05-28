from fastapi import APIRouter, Form, HTTPException
import uuid

router = APIRouter(tags=["projects"])


@router.get("/projects")
async def list_projects():
    from ...db.models import list_projects as _list_projects

    projects = await _list_projects()
    return {"projects": projects, "count": len(projects)}


@router.post("/projects", status_code=201)
async def create_project(
    code: str = Form(...),
    name: str = Form(...),
    technical_specification: str = Form(default=""),
    auto_bind_keywords: str = Form(default=""),
):
    from ...db.models import create_project as _create_project

    project_id = str(uuid.uuid4())
    p = await _create_project(
        project_id=project_id,
        code=code,
        name=name,
        technical_specification=technical_specification,
        auto_bind_keywords=auto_bind_keywords,
    )
    return p


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    from ...db.models import get_project as _get_project

    p = await _get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    name: str = Form(default=None),
    technical_specification: str = Form(default=None),
    auto_bind_keywords: str = Form(default=None),
):
    from ...db.models import update_project as _update_project

    p = await _update_project(
        project_id=project_id,
        name=name,
        technical_specification=technical_specification,
        auto_bind_keywords=auto_bind_keywords,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    from ...db.models import delete_project as _delete_project

    ok = await _delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": project_id}
