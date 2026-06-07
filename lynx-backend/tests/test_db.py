import uuid

import pytest


class TestProjectCRUD:
    async def test_create_project_with_all_fields(self, session):
        from app.db.models import create_project
        proj = await create_project(
            code="FULL",
            name="Full Project",
            technical_specification="Detailed spec here",
            auto_bind_keywords="kw1,kw2,kw3",
        )
        assert proj["code"] == "FULL"
        assert proj["name"] == "Full Project"
        assert proj["auto_bind_keywords"] == "kw1,kw2,kw3"
        assert "id" in proj
        assert "created_at" in proj

    async def test_create_project_minimal(self, session):
        from app.db.models import create_project
        proj = await create_project(code="MIN", name="Minimal")
        assert proj["code"] == "MIN"
        assert proj["name"] == "Minimal"

    async def test_list_projects(self, session):
        from app.db.models import create_project, list_projects
        await create_project(code="A1", name="Alpha")
        await create_project(code="B2", name="Beta")
        projects = await list_projects()
        assert len(projects) >= 2
        codes = [p["code"] for p in projects]
        assert "A1" in codes
        assert "B2" in codes

    async def test_get_project(self, session):
        from app.db.models import create_project, get_project
        proj = await create_project(code="GET", name="Get Test")
        fetched = await get_project(proj["id"])
        assert fetched is not None
        assert fetched["id"] == proj["id"]
        assert fetched["name"] == "Get Test"

    async def test_get_project_not_found(self, session):
        from app.db.models import get_project
        result = await get_project("nonexistent-id")
        assert result is None

    async def test_update_project(self, session):
        from app.db.models import create_project, update_project
        proj = await create_project(code="UPD", name="Original")
        updated = await update_project(proj["id"], name="Updated", technical_specification="New spec")
        assert updated["name"] == "Updated"
        assert updated["technical_specification"] == "New spec"

    async def test_update_project_partial(self, session):
        from app.db.models import create_project, update_project
        proj = await create_project(code="PART", name="Partial", technical_specification="Old spec")
        updated = await update_project(proj["id"], name="OnlyName")
        assert updated["name"] == "OnlyName"
        assert updated["technical_specification"] == "Old spec"

    async def test_delete_project(self, session):
        from app.db.models import create_project, delete_project, get_project
        proj = await create_project(code="DEL", name="Delete Me")
        result = await delete_project(proj["id"])
        assert result["deleted"] == proj["id"]
        fetched = await get_project(proj["id"])
        assert fetched is None

    async def test_delete_project_not_found(self, session):
        from app.db.models import delete_project
        result = await delete_project("no-such-id")
        assert result is None


class TestModelVersionCRUD:
    async def test_create_model_version(self, session, sample_project):
        from app.db.models import create_model_version
        mvid = str(uuid.uuid4())
        mv = await create_model_version(
            model_version_id=mvid,
            project_id=sample_project["id"],
            model_name="TestModel",
            ruleset_id="default",
            filename="test.ifc",
        )
        assert mv["id"] == mvid
        assert mv["model_name"] == "TestModel"
        assert mv["status"] == "uploaded"

    async def test_create_model_version_auto_version(self, session, sample_project):
        from app.db.models import create_model_version
        mvid1 = str(uuid.uuid4())
        mv1 = await create_model_version(mvid1, sample_project["id"], "V1", "default", "f1.ifc")
        mvid2 = str(uuid.uuid4())
        mv2 = await create_model_version(mvid2, sample_project["id"], "V2", "default", "f2.ifc")
        assert mv2["version_number"] > mv1["version_number"]

    async def test_get_model_version(self, session, sample_model_version):
        from app.db.models import get_model_version
        fetched = await get_model_version(sample_model_version["id"])
        assert fetched is not None
        assert fetched["id"] == sample_model_version["id"]

    async def test_get_model_version_not_found(self, session):
        from app.db.models import get_model_version
        result = await get_model_version("no-such-id")
        assert result is None

    async def test_list_all_models(self, session, sample_project, sample_model_version):
        from app.db.models import list_all_models
        models = await list_all_models()
        assert len(models) >= 1
        ids = [m["id"] for m in models]
        assert sample_model_version["id"] in ids

    async def test_list_models_by_project(self, session, sample_project, sample_model_version):
        from app.db.models import list_all_models, create_model_version
        from app.db.models import create_project
        other_proj = await create_project(code="OTHER", name="Other Project")
        other_mv = await create_model_version(
            str(uuid.uuid4()), other_proj["id"], "OtherModel", "default", "o.ifc"
        )
        models = await list_all_models(project_id=sample_project["id"])
        ids = [m["id"] for m in models]
        assert sample_model_version["id"] in ids
        assert other_mv["id"] not in ids

    async def test_move_model_to_project(self, session, sample_project, sample_model_version):
        from app.db.models import create_project, move_model_to_project
        other = await create_project(code="TARGET", name="Target Project")
        result = await move_model_to_project(sample_model_version["id"], other["id"])
        assert result is not None
        assert result["project_id"] == other["id"]

    async def test_move_model_to_project_not_found(self, session):
        from app.db.models import move_model_to_project
        result = await move_model_to_project("no-model", "no-project")
        assert result is None


class TestIssues:
    async def test_create_and_list_issues(self, session, sample_model_version):
        from app.db.models import get_issues
        from app.db.models_orm import Issue
        from app.db.base import async_session, AsyncSession
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession as SASession

        issues = await get_issues(sample_model_version["id"])
        assert isinstance(issues, list)

    async def test_get_issues_empty(self, session):
        from app.db.models import get_issues
        issues = await get_issues("no-such-model")
        assert isinstance(issues, list)
        assert len(issues) == 0


class TestCategories:
    async def test_list_categories_default(self, session, sample_project):
        from app.db.models import list_project_categories
        cats = await list_project_categories(sample_project["id"])
        assert len(cats) >= 1
        for cat in cats:
            assert "name" in cat
            assert "display_order" in cat

    async def test_save_and_list_categories(self, session, sample_project):
        from app.db.models import list_project_categories, save_project_categories
        new_cats = [
            {"name": "Custom A", "display_order": 1, "columns_config": {}},
            {"name": "Custom B", "display_order": 2, "columns_config": {}},
        ]
        result = await save_project_categories(sample_project["id"], new_cats)
        assert result is not None
        fetched = await list_project_categories(sample_project["id"])
        names = [c["name"] for c in fetched]
        assert "Custom A" in names
        assert "Custom B" in names
<｜｜DSML｜｜parameter name="description" string="true">Write test_db.py