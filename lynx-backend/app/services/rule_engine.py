import re
import json
from typing import Any, Optional
from datetime import datetime
import uuid

from ..db.models import Element, Issue, ModelVersion, async_session, DEFAULT_CATEGORIES, extract_model_group

# Categories that are checked by rules (all except "Невалидируемое семейство")
VALID_CATEGORIES = [c.lower() for c in DEFAULT_CATEGORIES if c != "Невалидируемое семейство"]


RULE_OPERATORS = {
    "exists": lambda v, p: v is not None,
    "not_exists": lambda v, p: v is None,
    "eq": lambda v, p: v == p.get("value"),
    "neq": lambda v, p: v != p.get("value"),
    "in": lambda v, p: v in p.get("values", []),
    "not_in": lambda v, p: v not in p.get("values", []),
    "regex": lambda v, p: v is not None and re.search(p.get("pattern", ""), str(v)),
    "between": lambda v, p: v is not None and p.get("min", 0) <= v <= p.get("max", float("inf")),
    "gt": lambda v, p: v is not None and v > p.get("value"),
    "gte": lambda v, p: v is not None and v >= p.get("value"),
    "lt": lambda v, p: v is not None and v < p.get("value"),
    "lte": lambda v, p: v is not None and v <= p.get("value"),
}


def deep_get(obj: dict, path: str) -> Any:
    """Получение значения по пути через точку."""
    keys = path.split(".")
    value = obj
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def eval_rule(rule: dict, element: dict) -> tuple[bool, Optional[str]]:
    """Оценить правило для элемента."""
    applies_to = rule.get("applies_to", {})
    ifc_classes = applies_to.get("ifc_classes", [])
    if element.get("ifc_class") not in ifc_classes:
        return None, None
    
    where = applies_to.get("where", [])
    for cond in where:
        field = cond.get("field")
        op = cond.get("op")
        expected = cond.get("value")
        actual = deep_get(element, field)
        if op == "eq" and actual != expected:
            return None, None
    
    check = rule.get("check", {})
    field = check.get("field")
    op = check.get("op")
    
    if op not in RULE_OPERATORS:
        return None, None
    
    value = deep_get(element, field)
    evaluator = RULE_OPERATORS[op]
    passed = evaluator(value, check)
    
    if not passed:
        msg_template = rule.get("message_template", "Check failed")
        try:
            format_kwargs = {"field": field, "value": value}
            format_kwargs.update({k: v for k, v in check.items() if k not in ("field", "op")})
            message = msg_template.format(**format_kwargs)
        except Exception:
            message = msg_template
        return False, message
    
    return True, None


DEFAULT_RULES = [
    # ── Existing rules ──
    {
        "rule_key": "viv.pipe.name.required",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "name", "op": "exists"},
        "severity": "error",
        "message_template": "Название элемента обязательно",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.diameter.exists",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "canonical.size_filled", "op": "eq", "value": True},
        "severity": "error",
        "message_template": "Размер элемента не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.system.required",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "system_name", "op": "exists"},
        "severity": "error",
        "message_template": "Система не указана",
        "priority": 200,
    },
    # ── Common position params (all IFC classes) ──
    {
        "rule_key": "viv.param.section",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.ADSK_Номер секции", "op": "exists"},
        "severity": "error",
        "message_template": "Секция не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.part",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.BRU_ЧастьСистемы", "op": "exists"},
        "severity": "error",
        "message_template": "Часть системы не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.system",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.BRU_Система", "op": "exists"},
        "severity": "error",
        "message_template": "Система не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.storey",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.ADSK_Этаж", "op": "exists"},
        "severity": "error",
        "message_template": "Этаж не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.cube_short",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.CUBE_Сокращение для системы", "op": "exists"},
        "severity": "error",
        "message_template": "CUBE_Сокращение для системы не указано",
        "priority": 200,
    },
    # ── IfcPipeSegment ──
    {
        "rule_key": "viv.pipe.vid",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "params.BRU_Вид", "op": "exists"},
        "severity": "error",
        "message_template": "Вид не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.size",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "params.Размер", "op": "exists"},
        "severity": "error",
        "message_template": "Размер не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.wall",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "params.Толщина стенки", "op": "exists"},
        "severity": "error",
        "message_template": "Толщина стенки не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.length",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "params.Длина", "op": "exists"},
        "severity": "error",
        "message_template": "Длина не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.stage",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcFlowTerminal"], "where": []},
        "check": {"field": "params.Стадия возведения", "op": "exists"},
        "severity": "error",
        "message_template": "Стадия возведения не указана",
        "priority": 200,
    },
    {
        "rule_key": "viv.param.isolation",
        "applies_to": {"ifc_classes": ["IfcPipeSegment", "IfcPipeFitting"], "where": []},
        "check": {"field": "params.Толщина изоляции", "op": "exists"},
        "severity": "error",
        "message_template": "Толщина изоляции не указана",
        "priority": 200,
    },
    # ── IfcPipeFitting ──
    {
        "rule_key": "viv.fitting.type",
        "applies_to": {"ifc_classes": ["IfcPipeFitting"], "where": []},
        "check": {"field": "params.BRU_Тип", "op": "exists"},
        "severity": "error",
        "message_template": "Тип не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.fitting.vid",
        "applies_to": {"ifc_classes": ["IfcPipeFitting"], "where": []},
        "check": {"field": "params.BRU_Вид", "op": "exists"},
        "severity": "error",
        "message_template": "Вид не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.fitting.size",
        "applies_to": {"ifc_classes": ["IfcPipeFitting"], "where": []},
        "check": {"field": "params.BRU_Габарит элемента", "op": "exists"},
        "severity": "error",
        "message_template": "Размер не указан",
        "priority": 200,
    },
    # ── IfcValve ──
    {
        "rule_key": "viv.valve.type",
        "applies_to": {"ifc_classes": ["IfcValve"], "where": []},
        "check": {"field": "params.BRU_Тип", "op": "exists"},
        "severity": "error",
        "message_template": "Тип не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.valve.vid",
        "applies_to": {"ifc_classes": ["IfcValve"], "where": []},
        "check": {"field": "params.BRU_Вид", "op": "exists"},
        "severity": "error",
        "message_template": "Вид не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.valve.size",
        "applies_to": {"ifc_classes": ["IfcValve"], "where": []},
        "check": {"field": "params.BRU_Габарит элемента", "op": "exists"},
        "severity": "error",
        "message_template": "Размер не указан",
        "priority": 200,
    },
    # ── IfcFlowTerminal ──
    {
        "rule_key": "viv.terminal.type",
        "applies_to": {"ifc_classes": ["IfcFlowTerminal"], "where": []},
        "check": {"field": "params.BRU_Тип", "op": "exists"},
        "severity": "error",
        "message_template": "Тип не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.terminal.vid",
        "applies_to": {"ifc_classes": ["IfcFlowTerminal"], "where": []},
        "check": {"field": "params.BRU_Вид", "op": "exists"},
        "severity": "error",
        "message_template": "Вид не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.terminal.size",
        "applies_to": {"ifc_classes": ["IfcFlowTerminal"], "where": []},
        "check": {"field": "params.BRU_Габарит элемента", "op": "exists"},
        "severity": "error",
        "message_template": "Размер не указан",
        "priority": 200,
    },

]


async def run_rules(model_version_id: str, rules: list[dict] = None):
    """Запуск правил против элементов модели."""
    if rules is None:
        rules = DEFAULT_RULES
    
    async with async_session() as session:
        from sqlalchemy import select
        
        result = await session.execute(
            select(Element).where(Element.model_version_id == model_version_id)
        )
        elements = result.scalars().all()
        
        issues_created = 0
        for rule in rules:
            for el in elements:
                normalized = el.normalized_jsonb or {}
                raw_psets = el.raw_psets_jsonb or {}
                params = {}
                if isinstance(raw_psets, dict):
                    for pset_data in raw_psets.values():
                        if isinstance(pset_data, dict):
                            for k, v in pset_data.items():
                                if k not in params:
                                    params[k] = v
                # Skip elements in "Невалидируемое семейство"
                model_group = extract_model_group(raw_psets, normalized, el.ifc_class)
                if model_group:
                    mg_lower = model_group.strip().lower()
                    is_valid = any(cat in mg_lower for cat in VALID_CATEGORIES)
                else:
                    is_valid = False
                if not is_valid:
                    continue
                
                el_dict = {
                    "global_id": el.global_id,
                    "ifc_class": el.ifc_class,
                    "name": el.name,
                    "system_name": el.system_name,
                    "canonical": {
                        **normalized,
                        "size_filled": normalized.get("size_filled", normalized.get("diameter_mm") is not None),
                    },
                    "params": params,
                }
                
                passed, msg = eval_rule(rule, el_dict)
                
                if passed is None:
                    continue
                
                if not passed:
                    issue = Issue(
                        model_version_id=model_version_id,
                        element_id=el.id,
                        global_id=el.global_id,
                        rule_key=rule["rule_key"],
                        severity=rule.get("severity", "error"),
                        message=msg or rule.get("message_template", "Check failed"),
                        source_engine="python_rule",
                    )
                    session.add(issue)
                    issues_created += 1
        
        await session.commit()
        return issues_created