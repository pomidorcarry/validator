import uuid
from pathlib import Path

import pytest


class TestUploadLargeFiles:
    """Critical: test that the stream-based upload handler works for various file sizes."""

    BOUNDARY = "----TestBoundary12345"

    async def _upload_multipart(self, client, body: bytes, boundary: str = None) -> tuple[int, dict]:
        b = boundary or self.BOUNDARY
        resp = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": f"multipart/form-data; boundary={b}"},
        )
        try:
            data = resp.json()
        except Exception:
            data = {}
        return resp.status_code, data

    def _build_upload(self, ifc_size: int, model_name: str = "TestUpload", boundary: str = None) -> bytes:
        b = boundary or self.BOUNDARY
        ifc_content = b"A" * ifc_size
        parts = [
            f"--{b}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n820377a6-9d06-486a-bf87-0c9fc815ef44\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"model_name\"\r\n\r\n{model_name}\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"ruleset_id\"\r\n\r\ndefault\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"model.ifc\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
            ifc_content,
            f"\r\n--{b}--\r\n".encode(),
        ]
        return b"".join(parts)

    @pytest.mark.parametrize("size_kb", [1, 10, 100, 1024])
    async def test_upload_various_sizes(self, client, size_kb):
        """Upload files from 1KB to 1MB."""
        size = size_kb * 1024
        body = self._build_upload(size, f"Upload{size_kb}KB")
        status, data = await self._upload_multipart(client, body)
        assert status == 202, f"Upload {size_kb}KB failed: {data}"
        assert "model_version_id" in data
        assert data["status"] == "queued"

    async def test_upload_large_file(self, client):
        """Upload a ~10MB file to stress the stream-based handler."""
        size = 10 * 1024 * 1024
        body = self._build_upload(size, "Large10MB")
        status, data = await self._upload_multipart(client, body)
        assert status == 202, f"Large upload failed: {data}"
        assert "model_version_id" in data

    async def test_upload_empty_file(self, client):
        """Upload with zero-byte IFC content."""
        body = self._build_upload(0, "Empty")
        status, data = await self._upload_multipart(client, body)
        assert status == 202
        assert "model_version_id" in data

    async def test_upload_missing_boundary(self, client):
        """Upload without multipart boundary (raw body)."""
        content = b"this is not multipart data"
        resp = await client.post(
            "/api/v1/models/upload",
            content=content,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "model_version_id" in data

    async def test_upload_missing_content_type(self, client):
        """Upload with no Content-Type header."""
        content = b"raw body content"
        resp = await client.post(
            "/api/v1/models/upload",
            content=content,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "model_version_id" in data

    async def test_upload_no_project_id(self, client):
        """Upload without project_id (should use default)."""
        b = self.BOUNDARY
        ifc_content = b"Hello IFC"
        parts = [
            f"--{b}\r\nContent-Disposition: form-data; name=\"model_name\"\r\n\r\nNoProject\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"m.ifc\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
            ifc_content,
            f"\r\n--{b}--\r\n".encode(),
        ]
        body = b"".join(parts)
        status, data = await self._upload_multipart(client, body)
        assert status == 202, f"No project_id upload failed: {data}"

    async def test_upload_poorly_formed_extra_newlines(self, client):
        """Upload with extra whitespace/newlines to test parser robustness."""
        b = self.BOUNDARY
        body = (
            f"\r\n\r\n--{b}\r\n"
            f'Content-Disposition: form-data; name="project_id"\r\n\r\n'
            f"proj-1\r\n"
            f"--{b}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="test.ifc"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
            b"IFC content here\r\n"
            f"--{b}--\r\n"
        ).encode()
        status, data = await self._upload_multipart(client, body)
        assert status == 202

    async def test_upload_concurrent(self, client):
        """Multiple uploads in quick succession."""
        results = []
        for i in range(5):
            body = self._build_upload(5000, f"Concurrent{i}")
            status, data = await self._upload_multipart(client, body)
            results.append((status, data))
        for status, data in results:
            assert status == 202
            assert "model_version_id" in data

    async def test_upload_corrupt_boundary(self, client):
        """Upload with boundary that doesn't match body."""
        content = b"garbage data here"
        resp = await client.post(
            "/api/v1/models/upload",
            content=content,
            headers={"Content-Type": "multipart/form-data; boundary=nonexistent"},
        )
        assert resp.status_code == 202

    async def test_upload_file_with_revit_ids(self, client):
        """Upload with element_id_map (Revit element ID map)."""
        b = self.BOUNDARY
        revit_map = '{"abc123": 12345, "def456": 67890}'
        ifc_content = b"IFC data with revit map"
        parts = [
            f"--{b}\r\nContent-Disposition: form-data; name=\"project_id\"\r\n\r\n820377a6-9d06-486a-bf87-0c9fc815ef44\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"model_name\"\r\n\r\nWithRevitMap\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"element_id_map\"\r\n\r\n{revit_map}\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"m.ifc\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
            ifc_content,
            f"\r\n--{b}--\r\n".encode(),
        ]
        body = b"".join(parts)
        status, data = await self._upload_multipart(client, body)
        assert status == 202


class TestUploadSaveToDisk:
    """Verify the uploaded file is actually saved to disk."""

    async def test_upload_saves_raw_file(self, client, test_storage):
        body = (
            b"--BOUND\r\n"
            b'Content-Disposition: form-data; name="file"; filename="test.ifc"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
            b"MOCK IFC DATA\r\n"
            b"--BOUND--\r\n"
        )
        resp = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=BOUND"},
        )
        assert resp.status_code == 202
        data = resp.json()
        mvid = data["model_version_id"]
        ifc_file = test_storage / "raw" / f"{mvid}.ifc"
        raw_file = test_storage / "raw" / f"{mvid}.raw"
        assert raw_file.exists() or ifc_file.exists(), "Neither .raw nor .ifc file was saved"

    async def test_upload_empty_body(self, client):
        """Empty body should still return 202 (handler catches all)."""
        resp = await client.post(
            "/api/v1/models/upload",
            content=b"",
            headers={"Content-Type": "multipart/form-data; boundary=TEST"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "model_version_id" in data

    async def test_backend_pool_not_exhausted_after_large_upload(self, client):
        """After a large upload, subsequent small requests should still work."""
        body = b"x" * (2 * 1024 * 1024)
        resp1 = await client.post(
            "/api/v1/models/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=BND"},
        )
        assert resp1.status_code == 202
        resp2 = await client.get("/api/v1/health")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "healthy"
