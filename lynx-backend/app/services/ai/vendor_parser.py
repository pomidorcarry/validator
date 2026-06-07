import json
import logging
from pathlib import Path

from .client import ai_chat

logger = logging.getLogger(__name__)

VENDOR_SYSTEM_PROMPT = """Ты — инженер-снабженец. Из текста ведомости (vendor list / список производителей) выдели рекомендуемых производителей по каждой инженерной системе.

Верни JSON. Каждое поле — строка с перечнем производителей через запятую или пустая строка "":

{
  "tz_manufacturers": "ПОЛНЫЙ текст раздела о производителях из документа — дословно",
  "general_notes": "общие указания: требования к сертификации, качеству, гарантии, разрешительным документам",
  "water_supply_manufacturers": "рекомендуемые производители для водоснабжения (трубы, фитинги, запорная арматура): название каждой фирмы, страна, краткая характеристика продукции",
  "sewerage_manufacturers": "рекомендуемые производители для канализации (трубы, фитинги): названия, страна, характеристика",
  "fire_fighting_manufacturers": "рекомендуемые производители для пожаротушения: названия, страна, характеристика",
  "heating_manufacturers": "рекомендуемые производители для отопления (радиаторы, трубы, котлы, насосы): названия, страна, характеристика",
  "ventilation_manufacturers": "рекомендуемые производители для вентиляции и кондиционирования (воздуховоды, диффузоры, клапаны, чиллеры, фанкойлы): названия, страна, характеристика",
  "electrical_manufacturers": "рекомендуемые производители для электроснабжения (кабели, щиты, выключатели, светильники): названия, страна, характеристика",
  "low_current_manufacturers": "рекомендуемые производители для слаботочных систем (СКС, ОПС, СКУД): названия, страна, характеристика",
  "pumps_manufacturers": "рекомендуемые производители насосного оборудования (циркуляционные, повысительные, дренажные, пожарные): названия, страна",
  "valves_manufacturers": "рекомендуемые производители запорно-регулирующей арматуры (задвижки, затворы, клапаны, краны): названия, страна",
  "insulation_manufacturers": "рекомендуемые производители изоляционных материалов: названия, страна",
  "water_treatment_manufacturers": "рекомендуемые производители водоподготовки и фильтрации: названия, страна",
  "automation_manufacturers": "рекомендуемые производители средств автоматизации (контроллеры, датчики, исполнительные механизмы): названия, страна"
}

Для каждого раздела перечисли ВСЕХ производителей, указанных в документе. Если производителей для раздела нет — оставь пустую строку. Не добавляй пояснений, только JSON."""


async def parse_vendor_document(text: str) -> dict:
    if not text.strip():
        return {k: "" for k in (
            "tz_manufacturers", "general_notes",
            "water_supply_manufacturers", "sewerage_manufacturers",
            "fire_fighting_manufacturers", "heating_manufacturers",
            "ventilation_manufacturers", "electrical_manufacturers",
            "low_current_manufacturers", "pumps_manufacturers",
            "valves_manufacturers", "insulation_manufacturers",
            "water_treatment_manufacturers", "automation_manufacturers",
        )}

    logger.info("Parsing vendor document...")
    result = await ai_chat(
        messages=[
            {"role": "system", "content": VENDOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки из документа информацию о рекомендуемых производителях:\n\n{text[:40000]}"},
        ],
        temperature=0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )
    if not result:
        logger.error("Vendor parse: AI returned empty result")
        return {}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = (
            "tz_manufacturers", "general_notes",
            "water_supply_manufacturers", "sewerage_manufacturers",
            "fire_fighting_manufacturers", "heating_manufacturers",
            "ventilation_manufacturers", "electrical_manufacturers",
            "low_current_manufacturers", "pumps_manufacturers",
            "valves_manufacturers", "insulation_manufacturers",
            "water_treatment_manufacturers", "automation_manufacturers",
        )
        result_dict = {}
        for k in keys:
            val = parsed.get(k)
            if isinstance(val, str):
                result_dict[k] = val
            elif isinstance(val, (dict, list)):
                result_dict[k] = json.dumps(val, ensure_ascii=False)
            else:
                result_dict[k] = ""
        logger.info(f"Vendor parse complete: {len(result_dict)} sections")
        return result_dict
    except json.JSONDecodeError:
        logger.error(f"Vendor parse: invalid JSON: {result[:300]}")
        return {}


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl != -1 else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def extract_text_from_file(path: str) -> str:
    from .tz_parser import extract_text_from_file as _extract
    return _extract(path)
