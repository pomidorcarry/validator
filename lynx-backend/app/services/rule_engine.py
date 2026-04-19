import re
import json
from typing import Any, Optional
from datetime import datetime
import uuid

from ..db.models import Element, Issue, ModelVersion, async_session


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
        "check": {"field": "canonical.diameter_mm", "op": "exists"},
        "severity": "error",
        "message_template": "Диаметр элемента не указан",
        "priority": 200,
    },
    {
        "rule_key": "viv.pipe.diameter.range",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "canonical.diameter_mm", "op": "between", "min": 20, "max": 500},
        "severity": "warning",
        "message_template": "Диаметр должен быть в диапазоне 20..500 мм",
        "priority": 300,
    },
    {
        "rule_key": "viv.pipe.system.required",
        "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
        "check": {"field": "system_name", "op": "exists"},
        "severity": "error",
        "message_template": "Система не указана",
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
                el_dict = {
                    "global_id": el.global_id,
                    "ifc_class": el.ifc_class,
                    "name": el.name,
                    "system_name": el.system_name,
                    "normalized_jsonb": el.normalized_jsonb or {},
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