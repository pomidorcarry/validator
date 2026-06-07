import json
import logging
from typing import Optional

from .client import ai_chat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — BIM-инженер Revit. Для каждой ошибки, найденной AI-проверкой, предложи конкретную инструкцию по исправлению в Revit API.

## Доступные действия (steps):
1. set_param — установить значение параметра элемента
   { "action": "set_param", "param": "BRU_Габарит", "value": "50", "value_type": "string" }
2. copy_param — скопировать значение из одного параметра в другой 
   { "action": "copy_param", "from_param": "BRU_Система", "to_param": "ADSK_Система", "value_type": "string" }
3. set_system — назначить элемент на механическую систему
   { "action": "set_system", "system_name": "В1", "system_type": "Пожарный водопровод" }

## Известные Revit-параметры (используй их):
- BRU_Габарит — габарит/типоразмер (текст, например "50", "DN100")
- BRU_Система — имя инженерной системы (текст)
- BRU_ЧастьСистемы — часть системы (текст)
- ADSK_Этаж — этаж (текст)
- ADSK_ГлобальныйИдентификатор — GUID элемента
- IfcGUID — IFC GUID (только чтение в Revit)
- Размер — размер/диаметр (текст)
- Диаметр — числовой диаметр (мм)
- Комментарии — поле для заметок

## Формат ответа:
Верни JSON-массив fix_suggestions. Каждый элемент:
{
  "fix_id": "auto-{index}",
  "issue_index": <индекс проблемы из входного списка>,
  "element_global_id": "GlobalId элемента из issues.element_ids[0]",
  "element_name": "имя элемента",
  "description": "понятное описание что и как исправляется на русском",
  "risk": "low/medium/high",
  "ifc_guid_hint": "Revit IfcGUID если известен (из raw_psets_jsonb)",
  "steps": [
    { "action": "...", "param": "...", "value": "...", "value_type": "string" }
  ]
}

Если для проблемы нет разумного исправления — пропусти её (не включай в массив).
Верни ТОЛЬКО JSON-массив. Не добавляй пояснений."""


async def generate_fixes(issues: list[dict], elements: list[dict], tz_data: dict) -> list[dict]:
    issue_text = _summarize_issues(issues, elements)
    if not issue_text:
        return []

    result = await ai_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Сгенерируй исправления для этих ошибок:\n\n{issue_text[:60000]}"},
        ],
        temperature=0.1,
        max_tokens=8192,
    )

    if not result:
        return []

    cleaned = result.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        cleaned = cleaned[first_nl + 1:] if first_nl != -1 else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        fixes = json.loads(cleaned)
        if not isinstance(fixes, list):
            logger.warning(f"Fix generator: expected list, got {type(fixes)}")
            return []
        import uuid
        for f in fixes:
            if "fix_id" not in f or not f["fix_id"]:
                f["fix_id"] = str(uuid.uuid4())[:8]
            f.setdefault("status", "pending")
            f.setdefault("steps", [])
            f.setdefault("risk", "medium")
            f.setdefault("applied_result", None)
            f.setdefault("element_global_id", "")
            f.setdefault("ifc_guid_hint", "")
        return fixes
    except json.JSONDecodeError:
        logger.error(f"Fix generator: invalid JSON: {result[:500]}")
        return []


def _summarize_issues(issues: list[dict], elements: list[dict]) -> str:
    if not issues:
        return ""
    
    elem_by_gid = {}
    for el in elements:
        gid = el.get("global_id") or ""
        if gid:
            elem_by_gid[gid] = el
    
    lines = []
    for i, issue in enumerate(issues):
        if issue.get("dismissed"):
            continue
        msg = issue.get("message", "")
        details = issue.get("details", "")
        element_ids = issue.get("element_ids") or []
        
        lines.append(f"[{i}] {msg}")
        if details:
            lines.append(f"    Подробности: {details[:300]}")
        
        if element_ids:
            for gid in element_ids[:3]:
                el = elem_by_gid.get(gid)
                if el:
                    raw = el.get("raw_psets_jsonb") or {}
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except json.JSONDecodeError:
                            raw = {}
                    name = el.get("name") or "(без имени)"
                    ifc_class = el.get("ifc_class") or "?"
                    system = el.get("system_name") or ""
                    ifc_guid = raw.get("IfcGUID", raw.get("Ifc GUID", ""))
                    
                    lines.append(f"    Элемент: {name} ({ifc_class})")
                    if system:
                        lines.append(f"    Система: {system}")
                    if ifc_guid:
                        lines.append(f"    IfcGUID: {ifc_guid}")
                    
                    psets = raw if isinstance(raw, dict) else {}
                    for pset_name, pset_data in psets.items():
                        if isinstance(pset_data, dict):
                            for k, v in list(pset_data.items())[:5]:
                                lines.append(f"    Параметр {pset_name}.{k}: {v}")
        
        lines.append("")
    
    return "\n".join(lines)
