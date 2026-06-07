import json

import pytest

from app.db.element_storage import (
    save_raw,
    save_norm,
    load_raw,
    load_norm,
    delete,
    has_storage,
)


class TestElementStorage:
    async def test_save_and_load_raw(self, test_storage):
        eid = "elem-001"
        data = {"global_id": "abc123", "ifc_class": "IfcPipeSegment"}
        await save_raw(eid, data)
        loaded = await load_raw(eid)
        assert loaded is not None
        assert loaded["global_id"] == "abc123"
        assert loaded["ifc_class"] == "IfcPipeSegment"

    async def test_save_and_load_norm(self, test_storage):
        eid = "elem-002"
        data = {"name": "Pipe-1", "diameter": 50}
        await save_norm(eid, data)
        loaded = await load_norm(eid)
        assert loaded is not None
        assert loaded["name"] == "Pipe-1"

    async def test_has_storage(self, test_storage):
        eid = "elem-003"
        assert await has_storage(eid) is False
        await save_raw(eid, {"data": "test"})
        assert await has_storage(eid) is True

    async def test_delete(self, test_storage):
        eid = "elem-004"
        await save_raw(eid, {"data": "x"})
        await save_norm(eid, {"data": "y"})
        await delete(eid)
        assert await has_storage(eid) is False
        assert await load_raw(eid) is None
        assert await load_norm(eid) is None

    async def test_load_raw_not_found(self, test_storage):
        result = await load_raw("nonexistent")
        assert result is None

    async def test_load_norm_not_found(self, test_storage):
        result = await load_norm("nonexistent")
        assert result is None

    async def test_delete_not_found(self, test_storage):
        await delete("no-such-elem")

    async def test_save_large_data(self, test_storage):
        eid = "elem-large"
        data = {"key": "x" * 100000}
        await save_raw(eid, data)
        loaded = await load_raw(eid)
        assert loaded is not None
        assert len(loaded["key"]) == 100000

    async def test_save_and_load_json_types(self, test_storage):
        eid = "elem-types"
        data = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"a": {"b": "c"}},
        }
        await save_norm(eid, data)
        loaded = await load_norm(eid)
        assert loaded["string"] == "hello"
        assert loaded["number"] == 42
        assert loaded["float"] == 3.14
        assert loaded["bool"] is True
        assert loaded["null"] is None
        assert loaded["list"] == [1, 2, 3]
        assert loaded["nested"]["a"]["b"] == "c"
