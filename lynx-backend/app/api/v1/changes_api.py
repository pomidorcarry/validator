import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body

from ...core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["changes"])

_STORAGE_DIR: Path | None = None
_REVIT_ID_MAP: dict | None = None


def _get_revit_id_map() -> dict:
    """Load all Revit GlobalId → ElementId mappings from storage."""
    global _REVIT_ID_MAP
    if _REVIT_ID_MAP is not None:
        return _REVIT_ID_MAP
    _REVIT_ID_MAP = {}
    raw_dir = Path(settings.storage_path) / "raw"
    if raw_dir.exists():
        for f in sorted(raw_dir.glob("*.revit_ids.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    for gid, rid in data.items():
                        _REVIT_ID_MAP[gid] = int(rid)
            except Exception as e:
                logger.warning(f"Failed to load Revit ID map {f}: {e}")
    logger.info(f"Loaded {len(_REVIT_ID_MAP)} Revit element ID mappings")
    return _REVIT_ID_MAP


def _get_dir() -> Path:
    global _STORAGE_DIR
    if _STORAGE_DIR is None:
        _STORAGE_DIR = Path(settings.storage_path) / "changes"
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORAGE_DIR


def _project_dir(project_id: str) -> Path:
    d = _get_dir() / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _data_path(project_id: str) -> Path:
    return _project_dir(project_id) / "_changes.json"


def _load(project_id: str) -> dict:
    p = _data_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"orders": []}


def _save(project_id: str, data: dict):
    with open(_data_path(project_id), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


@router.get("/projects/{project_id}/changes")
async def get_changes(project_id: str):
    """Get all change orders (приказы) for a project."""
    return _load(project_id)


@router.post("/projects/{project_id}/changes")
async def create_change_order(project_id: str, data: dict = Body(...)):
    """Create a new change order with selected fixes."""
    store = _load(project_id)
    order = {
        "id": uuid.uuid4().hex[:12],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "title": data.get("title", "Приказ #" + str(len(store["orders"]) + 1)),
        "status": "draft",
        "fixes": data.get("fixes", []),
    }
    # Ensure each fix has an id
    for fix in order["fixes"]:
        if not fix.get("id"):
            fix["id"] = uuid.uuid4().hex[:12]
        if not fix.get("status"):
            fix["status"] = "pending"
    store["orders"].insert(0, order)
    _save(project_id, store)
    return order


@router.patch("/projects/{project_id}/changes/{order_id}")
async def update_change_order(project_id: str, order_id: str, data: dict = Body(...)):
    """Update a change order (status, title, fix statuses)."""
    store = _load(project_id)
    for order in store["orders"]:
        if order["id"] == order_id:
            if "title" in data:
                order["title"] = data["title"]
            if "status" in data:
                order["status"] = data["status"]
            if "fixes" in data:
                for incoming in data["fixes"]:
                    for existing in order["fixes"]:
                        if existing["id"] == incoming.get("id"):
                            if "status" in incoming:
                                existing["status"] = incoming["status"]
                            if "actions" in incoming:
                                existing["actions"] = incoming["actions"]
                            break
            _save(project_id, store)
            return order
    raise HTTPException(status_code=404, detail="Order not found")


@router.delete("/projects/{project_id}/changes/{order_id}")
async def delete_change_order(project_id: str, order_id: str):
    """Delete a change order."""
    store = _load(project_id)
    store["orders"] = [o for o in store["orders"] if o["id"] != order_id]
    _save(project_id, store)
    return {"deleted": order_id}


# ── Step generation from fix message ──

# Map fix message keywords to Revit parameter steps
_STEP_RULES = [
    # Material changes
    (r"(?i)(материал|material)", lambda m: [
        {"action": "set_param", "param": "BRU_Материал", "value": _extract_target(m), "value_type": "string"},
    ]),
    # Diameter changes
    (r"(?i)(диаметр|diameter|dn\d)", lambda m: [
        {"action": "set_param", "param": "BRU_Диаметр", "value": _extract_diameter(m), "value_type": "number"},
    ]),
    # Insulation changes
    (r"(?i)(изоляци|insulation)", lambda m: [
        {"action": "set_param", "param": "BRU_ТипИзоляции", "value": _extract_insulation_type(m), "value_type": "string"},
        {"action": "set_param", "param": "BRU_ДиаметрИзоляции", "value": _extract_insulation_diameter(m), "value_type": "number"},
    ]),
    # System/прокладка changes
    (r"(?i)(прокладк|laying|тип прокладки)", lambda m: [
        {"action": "set_param", "param": "BRU_ТипПрокладки", "value": _extract_target(m), "value_type": "string"},
    ]),
    # Pressure
    (r"(?i)(давлени|pressure)", lambda m: [
        {"action": "set_param", "param": "BRU_РабочееДавление", "value": _extract_number(m), "value_type": "number"},
    ]),
    # Temperature
    (r"(?i)(температур|temperature)", lambda m: [
        {"action": "set_param", "param": "BRU_Температура", "value": _extract_number(m), "value_type": "number"},
    ]),
    # System name
    (r"(?i)(систем|system|В\d|К\d|Т\d|П\d)", lambda m: [
        {"action": "set_system", "system_name": _extract_system(m)},
    ]),
    # Copy from one param to another
    (r"(?i)(копирова|copy|перенести)", lambda m: [
        {"action": "copy_param", "from_param": _extract_from_param(m), "to_param": _extract_to_param(m)},
    ]),
]


def _extract_target(text: str) -> str:
    """Try to extract what material/value is specified as target."""
    import re
    # Look for phrases like: "на ПЭ", "заменить на ПЭ", "должен быть ПЭ", "ПЭ", "сталь"
    m = re.search(r"(?:на|должен быть|должна быть|должно быть|-) ([\w\s.-]+)", text)
    if m:
        return m.group(1).strip()
    # Try to match known materials
    for mat in ["ПЭ", "ПП", "сталь", "чугун", "нержавеющая сталь", "нерж. сталь",
                "медь", "полипропилен", "полиэтилен", "ПНД", "оцинкованная сталь",
                "K-Flex", "Armacell", "Energoflex", "минвата", "минеральная вата"]:
        if mat.lower() in text.lower():
            return mat
    return "-"


def _extract_diameter(text: str) -> str:
    import re
    m = re.search(r"(\d{2,4})\s*мм", text)
    if m:
        return m.group(1)
    m = re.search(r"DN\s*(\d+)", text)
    if m:
        return m.group(1)
    return "100"


def _extract_number(text: str) -> str:
    import re
    m = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if m:
        return m.group(1).replace(",", ".")
    return "1.0"


def _extract_system(text: str) -> str:
    import re
    m = re.search(r"(В\d[\d\.]*|К\d[\d\.]*|Т\d[\d\.]*|П\d[\d\.]*)", text)
    if m:
        return m.group(1)
    return "—"


def _extract_insulation_type(text: str) -> str:
    import re
    for t in ["K-Flex", "Armacell", "Energoflex", "минвата", "минеральная вата",
              "пенополиуретан", "ППУ", "каучук", "вспененный каучук"]:
        if t.lower() in text.lower():
            return t
    m = re.search(r"(?:изоляция|изоляци[иею])\s*[—\-–]\s*(\w[\w\s\-]*)", text)
    if m:
        return m.group(1).strip()
    return "K-Flex"


def _extract_insulation_diameter(text: str) -> str:
    import re
    m = re.search(r"изоляци.+?(\d{2,4})\s*мм", text)
    if m:
        return m.group(1)
    return "50"


def _extract_from_param(text: str) -> str:
    import re
    m = re.search(r"из\s+(\w+)", text)
    return m.group(1) if m else "ADSK_Марка"


def _extract_to_param(text: str) -> str:
    import re
    m = re.search(r"в\s+(\w+)", text)
    return m.group(1) if m else "BRU_Марка"


def _generate_steps(fix: dict) -> list:
    """Generate structured steps from fix message using rules."""
    import re
    msg = fix.get("message", "") + " " + (fix.get("details", "") or "")
    steps = []
    seen_actions = set()

    for pattern, builder in _STEP_RULES:
        if re.search(pattern, msg):
            new_steps = builder(msg)
            for s in new_steps:
                key = (s["action"], s.get("param", s.get("system_name", "")))
                if key not in seen_actions:
                    seen_actions.add(key)
                    steps.append(s)

    return steps


def _get_element_ids(fix: dict) -> list:
    """Get element_ids (GlobalIds) from fix, handling backward compat."""
    eids = fix.get("element_ids", [])
    if not eids and fix.get("element_global_id"):
        eids = [fix["element_global_id"]]
    return eids


def _get_revit_element_ids(fix: dict) -> list:
    """Resolve Revit ElementIds from element_ids using the global lookup map."""
    revit_ids = fix.get("revit_element_ids", [])
    if revit_ids:
        return revit_ids
    gids = _get_element_ids(fix)
    if not gids:
        return []
    revit_map = _get_revit_id_map()
    return [revit_map.get(gid) for gid in gids if revit_map.get(gid) is not None]


def _render_instruction(fix: dict, steps: list) -> str:
    """Render human-readable instruction from steps."""
    eids = _get_element_ids(fix)
    element = fix.get("element_name", eids[0] if eids else "неизвестный элемент")
    msg = fix.get("message", "")
    lines = [f"Инструкция по исправлению: {msg}"]
    lines.append(f"Элемент: {element}")
    if fix.get("rule_key"):
        lines.append(f"Правило: {fix['rule_key']}")
    if fix.get("details"):
        lines.append(f"Дополнительно: {fix['details']}")
    lines.append("")
    if steps:
        lines.append("Программные шаги:")
        for i, s in enumerate(steps, 1):
            if s["action"] == "set_param":
                lines.append(f"  {i}. Установить параметр {s['param']} = {s['value']}")
            elif s["action"] == "copy_param":
                lines.append(f"  {i}. Скопировать {s['from_param']} → {s['to_param']}")
            elif s["action"] == "set_system":
                lines.append(f"  {i}. Назначить систему {s['system_name']}")
    else:
        lines.append("Программные шаги не определены — требуются уточнения.")
        lines.append("1. Откройте Revit и найдите элемент.")
        lines.append("2. Исправьте вручную согласно описанию замечания.")

    return "\n".join(lines)


@router.post("/projects/{project_id}/changes/{order_id}/elaborate")
async def elaborate_change_order(project_id: str, order_id: str, data: dict = Body(...)):
    """Generate detailed instructions + structured steps for fixes."""
    store = _load(project_id)
    for order in store["orders"]:
        if order["id"] == order_id:
            fix_ids = data.get("fix_ids", [])
            results = []
            for fix in order.get("fixes", []):
                if not fix_ids or fix.get("id") in fix_ids:
                    steps = _generate_steps(fix)
                    instruction = _render_instruction(fix, steps)
                    fix["instruction"] = instruction
                    fix["steps"] = steps
                    fix["elaborated"] = True
                    # Resolve and store Revit ElementIds
                    revit_ids = _get_revit_element_ids(fix)
                    if revit_ids:
                        fix["revit_element_ids"] = revit_ids
                    results.append({
                        "fix_id": fix["id"],
                        "instruction": instruction,
                        "steps": steps,
                    })
            _save(project_id, store)
            return {"instructions": results}
    raise HTTPException(status_code=404, detail="Order not found")


@router.get("/projects/{project_id}/changes/for-revit")
async def get_changes_for_revit(project_id: str):
    """Get sent orders formatted for Revit plugin consumption."""
    store = _load(project_id)
    sent_orders = [o for o in store["orders"] if o.get("status") in ("sent", "applied")]
    return {
        "orders": [{
            "id": o["id"],
            "title": o.get("title", ""),
            "created_at": o.get("created_at", ""),
            "fixes": [{
                "fix_id": f.get("id", ""),
                "element_name": f.get("element_name", ""),
                "element_ids": _get_element_ids(f),
                "revit_element_ids": _get_revit_element_ids(f),
                "message": f.get("message", ""),
                "instruction": f.get("instruction", ""),
                "steps": f.get("steps", []),
                "status": f.get("status", "pending"),
                "rule_key": f.get("rule_key", ""),
            } for f in o.get("fixes", []) if f.get("status") in ("approved", "pending")],
        } for o in sent_orders]
    }


@router.post("/projects/{project_id}/changes/{order_id}/mark-applied")
async def mark_order_applied_in_revit(project_id: str, order_id: str, data: dict = Body(...)):
    """Mark an order and its fixes as applied from Revit plugin."""
    store = _load(project_id)
    for order in store["orders"]:
        if order["id"] == order_id:
            order["status"] = "applied"
            fix_ids = data.get("fix_ids", [])
            for fix in order.get("fixes", []):
                if not fix_ids or fix.get("id") in fix_ids:
                    fix["status"] = "applied"
            _save(project_id, store)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Order not found")
