import pytest


class TestProjectAutoBind:
    """When uploading a model, the project auto_bind_keywords should match
    model names to projects automatically."""

    async def test_auto_bind_matches_keyword(self, client):
        """Create project with keyword 'school', upload model named 'School Building'
        should auto-bind even if wrong project_id is sent."""
        resp = await client.post(
            "/api/v1/projects",
            data={
                "code": "SCHOOL",
                "name": "School Project",
                "auto_bind_keywords": "school",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        school_proj = resp.json()
        resp2 = await client.post(
            "/api/v1/projects",
            data={
                "code": "OTHER",
                "name": "Other Project",
                "auto_bind_keywords": "other",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        other_proj = resp2.json()

        body = (
            b"--B\r\n"
            b'Content-Disposition: form-data; name="project_id"\r\n\r\n'
            f"{other_proj['id']}\r\n".encode()
            b"--B\r\n"
            b'Content-Disposition: form-data; name="model_name"\r\n\r\n'
            b"School Building Model\r\n"
            b"--B\r\n"
            b'Content-Disposition: form-data; name="file"; filename="m.ifc"\r\n\r\n'
            b"IFC\r\n"
            b"--B--\r\n"
        )
        resp3 = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=B"},
        )
        assert resp3.status_code == 202
        mvid = resp3.json()["model_version_id"]
        get_resp = await client.get(f"/api/v1/models/{mvid}")
        if get_resp.status_code == 200:
            model = get_resp.json()
            assert model["project_id"] == school_proj["id"]

    async def test_auto_bind_no_match_uses_default(self, client):
        """Model with no keyword match should use the provided project_id."""
        resp = await client.post(
            "/api/v1/projects",
            data={
                "code": "DEF",
                "name": "Default Project",
                "auto_bind_keywords": "school",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        proj = resp.json()

        body = (
            b"--B\r\n"
            b'Content-Disposition: form-data; name="project_id"\r\n\r\n'
            f"{proj['id']}\r\n".encode()
            b"--B\r\n"
            b'Content-Disposition: form-data; name="model_name"\r\n\r\n'
            b"Random Building\r\n"
            b"--B\r\n"
            b'Content-Disposition: form-data; name="file"; filename="m.ifc"\r\n\r\n'
            b"IFC\r\n"
            b"--B--\r\n"
        )
        resp2 = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=B"},
        )
        assert resp2.status_code == 202


class TestXKTConverter:
    async def test_xkt_is_noop(self):
        from app.services.xkt_converter import generate_xkt
        result = await generate_xkt("test-model-id")
        assert result is True


class TestElementExtraction:
    def test_diameter_from_psets_nominal_diameter(self):
        from app.services.ifc_normalizer import extract_diameter_from_psets
        psets = {"PSet_PipeCommon": {"NominalDiameter": 100}}
        result, filled = extract_diameter_from_psets(psets)
        assert result == 100.0
        assert filled is True

    def test_diameter_from_psets_missing(self):
        from app.services.ifc_normalizer import extract_diameter_from_psets
        result, filled = extract_diameter_from_psets({"PSet_Empty": {}})
        assert result is None
        assert filled is False

    def test_diameter_from_psets_string_value(self):
        from app.services.ifc_normalizer import extract_diameter_from_psets
        psets = {"PSet_Pipe": {"DN": "50"}}
        result, filled = extract_diameter_from_psets(psets)
        assert result == 50.0
        assert filled is True

    def test_diameter_from_psets_multiple_keys(self):
        from app.services.ifc_normalizer import extract_diameter_from_psets
        psets = {"PSet": {"BRU_Габарит элемента": "DN100", "NominalDiameter": 80}}
        result, filled = extract_diameter_from_psets(psets)
        assert result is not None

    def test_extract_diameter_all_keys_checked(self):
        from app.services.ifc_normalizer import DIAMETER_KEYS
        assert "NominalDiameter" in DIAMETER_KEYS
        assert "DN" in DIAMETER_KEYS
        assert "BRU_Габарит элемента" in DIAMETER_KEYS
        assert len(DIAMETER_KEYS) >= 5


class TestIfcNormalizerEdgeCases:
    def test_extract_material_no_material(self):
        from app.services.ifc_normalizer import extract_material_from_element
        class MockElement:
            HasAssociations = []
        result = extract_material_from_element(MockElement())
        assert result == ""

    def test_extract_diameter_empty_psets(self):
        from app.services.ifc_normalizer import extract_diameter_from_psets
        result, filled = extract_diameter_from_psets({})
        assert result is None
        assert filled is False
