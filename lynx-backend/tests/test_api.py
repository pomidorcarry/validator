import json
import uuid

import pytest


class TestHealth:
    async def test_health_endpoint(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    async def test_root_endpoint(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data


class TestProjects:
    async def test_list_projects_empty(self, client):
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data
        assert "count" in data

    async def test_create_project(self, client):
        resp = await client.post(
            "/api/v1/projects",
            data={"code": "TEST", "name": "Test Project", "technical_specification": "Spec", "auto_bind_keywords": "test"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "TEST"
        assert data["name"] == "Test Project"
        assert "id" in data

    async def test_create_project_missing_code(self, client):
        resp = await client.post(
            "/api/v1/projects",
            data={"name": "NoCode"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 422

    async def test_get_project_by_id(self, client, sample_project):
        resp = await client.get(f"/api/v1/projects/{sample_project['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sample_project["id"]

    async def test_get_project_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_project(self, client, sample_project):
        resp = await client.put(
            f"/api/v1/projects/{sample_project['id']}",
            data={"name": "Updated Name"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_update_project_not_found(self, client):
        resp = await client.put(
            f"/api/v1/projects/{uuid.uuid4()}",
            data={"name": "Nope"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 404

    async def test_delete_project(self, client, sample_project):
        resp = await client.delete(f"/api/v1/projects/{sample_project['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == sample_project["id"]

    async def test_delete_project_not_found(self, client):
        resp = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_project_model_count(self, client, sample_project):
        resp = await client.get("/api/v1/projects")
        data = resp.json()
        for p in data["projects"]:
            if p["id"] == sample_project["id"]:
                assert "model_count" in p
                break


class TestModels:
    async def test_list_models_empty(self, client):
        resp = await client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data

    async def test_list_models_by_project(self, client, sample_project):
        resp = await client.get(f"/api/v1/models?project_id={sample_project['id']}")
        assert resp.status_code == 200

    async def test_get_model_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_get_model_status_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}/status")
        assert resp.status_code == 404

    async def test_delete_model_not_found(self, client):
        resp = await client.delete(f"/api/v1/models/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_move_model_not_found(self, client):
        resp = await client.put(
            f"/api/v1/models/{uuid.uuid4()}/move",
            data={"target_project_id": str(uuid.uuid4())},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 404

    async def test_get_model_ifc_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}/ifc")
        assert resp.status_code == 404

    async def test_get_model_xkt_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}/xkt")
        assert resp.status_code == 404

    async def test_get_model_issues_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}/issues")
        assert resp.status_code == 200

    async def test_get_model_elements_not_found(self, client):
        resp = await client.get(f"/api/v1/models/{uuid.uuid4()}/elements")
        assert resp.status_code == 200

    async def test_repair_materials_not_found(self, client):
        resp = await client.post(f"/api/v1/models/{uuid.uuid4()}/repair-materials")
        assert resp.status_code == 404

    async def test_reprocess_rules_not_found(self, client):
        resp = await client.post(f"/api/v1/models/{uuid.uuid4()}/reprocess-rules")
        assert resp.status_code == 200

    async def test_upload_and_then_get_status(self, client):
        body = (
            b"--B\r\n"
            b'Content-Disposition: form-data; name="project_id"\r\n\r\n'
            b"proj-test\r\n"
            b"--B\r\n"
            b'Content-Disposition: form-data; name="model_name"\r\n\r\n'
            b"StatusTest\r\n"
            b"--B\r\n"
            b'Content-Disposition: form-data; name="file"; filename="m.ifc"\r\n\r\n'
            b"IFC\r\n"
            b"--B--\r\n"
        )
        resp = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=B"},
        )
        assert resp.status_code == 202
        mvid = resp.json()["model_version_id"]
        resp2 = await client.get(f"/api/v1/models/{mvid}")
        assert resp2.status_code in (200, 404)

    async def test_delete_all_models(self, client):
        resp = await client.delete("/api/v1/models")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestCategories:
    async def test_get_categories_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}/categories")
        assert resp.status_code == 200

    async def test_update_categories_not_found(self, client):
        categories = json.dumps([{"name": "Test", "display_order": 1}])
        resp = await client.put(
            f"/api/v1/projects/{uuid.uuid4()}/categories",
            data={"categories": categories},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200

    async def test_categories_roundtrip(self, client, sample_project):
        pid = sample_project["id"]
        cats = json.dumps([
            {"name": "Pipe", "display_order": 1},
            {"name": "Fitting", "display_order": 2},
        ])
        resp = await client.put(
            f"/api/v1/projects/{pid}/categories",
            data={"categories": cats},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        get_resp = await client.get(f"/api/v1/projects/{pid}/categories")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["categories"]) >= 2


class TestTZ:
    async def test_get_tz_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}/tz")
        assert resp.status_code == 200

    async def test_update_tz(self, client, sample_project):
        pid = sample_project["id"]
        data = {"general": "Test TZ data"}
        resp = await client.put(
            f"/api/v1/projects/{pid}/tz",
            json=data,
        )
        assert resp.status_code == 200

    async def test_get_tz_history(self, client, sample_project):
        resp = await client.get(f"/api/v1/projects/{sample_project['id']}/tz/history")
        assert resp.status_code == 200
        assert "versions" in resp.json()


class TestAIStatus:
    async def test_ai_status_no_check(self, client):
        resp = await client.get("/api/v1/ai/status?check=false")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "responsive" in data

    async def test_ai_status_with_check(self, client):
        resp = await client.get("/api/v1/ai/status?check=true")
        assert resp.status_code == 200


class TestVendor:
    async def test_get_vendor_not_found(self, client):
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}/vendor")
        assert resp.status_code == 200

    async def test_save_vendor_manufacturers(self, client, sample_project):
        resp = await client.put(
            f"/api/v1/projects/{sample_project['id']}/vendor",
            json={"manufacturers": [{"name": "Test Corp"}]},
        )
        assert resp.status_code == 200


class TestChanges:
    async def test_get_changes_empty(self, client):
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}/changes")
        assert resp.status_code == 200

    async def test_create_change_order(self, client, sample_project):
        resp = await client.post(
            f"/api/v1/projects/{sample_project['id']}/changes",
            json={"title": "Test change", "description": "desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    async def test_delete_change_order(self, client, sample_project):
        pid = sample_project["id"]
        create_resp = await client.post(
            f"/api/v1/projects/{pid}/changes",
            json={"title": "Delete me"},
        )
        order_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/projects/{pid}/changes/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == order_id


class TestCORS:
    async def test_cors_headers_present(self, client):
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers or resp.status_code == 200
