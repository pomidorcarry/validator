import json
import logging
import asyncio
import re
from pathlib import Path

from .client import ai_chat

logger = logging.getLogger(__name__)

# ─── Phase 1: split document into thematic sections ───────────────

SPLIT_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Прочитай техническое задание и распредели его текст по тематическим разделам.

Верни JSON. Каждое поле должно содержать ТОЛЬКО соответствующий текст из документа, скопированный максимально дословно:

1. "general_section" — общая информация о проекте: общие положения, цели и задачи, адрес, этажность, количество секций, состав проекта, общие требования, генплан
2. "water_sewer_section" — водоснабжение (ХВС, ГВС), водоотведение, канализация, пожаротушение, внутренний водопровод, насосные станции: материалы труб, диаметры, изоляция, арматура, оборудование
3. "bim_section" — BIM-требования: LOD, форматы файлов, классификатор, требования к модели, обмен данными, EIR, BEP, параметры элементов
4. "equipment_section" — оборудование: насосы, котлы, теплообменники, резервуары, запорно-регулирующая арматура, приборы учёта
5. "materials_insulation_section" — материалы и изоляция: общие требования к материалам труб, фитингов, изоляции, антикоррозийная защита, окраска
6. "testing_section" — испытания: гидравлические испытания, промывка, опрессовка, пусконаладочные работы, требования к качеству
7. "standards_section" — нормативные документы: ссылки на СП, СНиП, ГОСТ, ISO, на которые ссылается ТЗ
8. "other_section" — всё остальное: отопление, вентиляция, кондиционирование, электрика, слаботочные системы, автоматизация, архитектурные решения, конструкции

Если какого-то раздела нет в документе — верни пустую строку "". Не добавляй пояснений, только JSON."""


async def _split_sections(full_text: str, max_input: int = 40000) -> dict:
    prompt_text = full_text[:max_input]
    result = await ai_chat(
        messages=[
            {"role": "system", "content": SPLIT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Распредели текст технического задания по разделам:\n\n{prompt_text}"},
        ],
        temperature=0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )
    if not result:
        return {}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {
            "general_section": _safe_str(parsed.get("general_section")),
            "water_sewer_section": _safe_str(parsed.get("water_sewer_section")),
            "bim_section": _safe_str(parsed.get("bim_section")),
            "equipment_section": _safe_str(parsed.get("equipment_section")),
            "materials_insulation_section": _safe_str(parsed.get("materials_insulation_section")),
            "testing_section": _safe_str(parsed.get("testing_section")),
            "standards_section": _safe_str(parsed.get("standards_section")),
            "other_section": _safe_str(parsed.get("other_section")),
        }
    except json.JSONDecodeError:
        logger.error(f"Split phase: AI returned invalid JSON: {result[:300]}")
        return {}


# ─── Phase 2a: extract general info ───────────────────────────────

GENERAL_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста раздела технического задания выдели ВСЮ общую информацию о проекте максимально подробно.

Верни JSON со следующими полями. Все поля — строки (НЕ массивы). Если данных нет — пустая строка "":

{
  "project_name": "полное наименование объекта строительства",
  "project_type": "тип объекта (жилой дом, административное здание, ТРЦ, промобъект и т.д.)",
  "project_purpose": "назначение и функциональное описание объекта",
  "project_address": "адрес или местоположение объекта строительства",
  "sections_count": "количество секций/блок-секций (напр. '3 секции')",
  "floors_count": "количество этажей (напр. '17 этажей'), включая подземные",
  "underground_floors": "количество подземных этажей",
  "building_height": "высота здания (м), если указана",
  "total_area": "общая площадь здания (м²)",
  "construction_year": "планируемый год ввода/строительства",
  "structural_system": "конструктивная схема (монолитный ж/б каркас, кирпич, металлокаркас и т.п.)",
  "tz_general": "ПОЛНЫЙ текст раздела общих положений (скопируй дословно, не сокращай)"
}"""


async def _extract_general(section_text: str, raw_full: str = "") -> dict:
    if not section_text.strip():
        return _empty_general()

    result = await ai_chat(
        messages=[
            {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки максимально подробную общую информацию о проекте из этого раздела ТЗ:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return _empty_general(section_text[:1000])

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {
            "project_name": _safe_str(parsed.get("project_name")),
            "project_type": _safe_str(parsed.get("project_type")),
            "project_purpose": _safe_str(parsed.get("project_purpose")),
            "project_address": _safe_str(parsed.get("project_address")),
            "sections_count": _safe_str(parsed.get("sections_count")),
            "floors_count": _safe_str(parsed.get("floors_count")),
            "underground_floors": _safe_str(parsed.get("underground_floors")),
            "building_height": _safe_str(parsed.get("building_height")),
            "total_area": _safe_str(parsed.get("total_area")),
            "construction_year": _safe_str(parsed.get("construction_year")),
            "structural_system": _safe_str(parsed.get("structural_system")),
            "tz_general": _safe_str(parsed.get("tz_general")) or section_text[:3000],
        }
    except json.JSONDecodeError:
        logger.error(f"General extract: invalid JSON: {result[:200]}")
        return _empty_general(section_text[:1000])


def _empty_general(fallback: str = ""):
    return {
        "project_name": "", "project_type": "", "project_purpose": "",
        "project_address": "", "sections_count": "", "floors_count": "",
        "underground_floors": "", "building_height": "", "total_area": "",
        "construction_year": "", "structural_system": "",
        "tz_general": fallback or "",
    }


# ─── Phase 2b: extract water / sewer / fire info ──────────────────

FIND_AND_EXTRACT_SYSTEMS_PROMPT = """Ты — инженер-сантехник. Проанализируй текст технического задания и найди ВСЕ обозначения систем водоснабжения (ХВС, ГВС), водоотведения (канализации) и пожаротушения.

В тексте ТЗ могут быть обозначения как простые (В1, В2, К1, К2), так и составные (В1.1, В1.2, К1.1, Т3, Т4, Т3.1, Т4.1, П1 и т.д.). Ищи ВСЕ варианты.

Для каждой найденной системы:
- category: "water_supply" для В1, В2, В3, В1.1, В2.1, Т3, Т4, Т3.1, Т4.1 и т.п.
- category: "sewerage" для К1, К1.1, К2, К2.1, К3 и т.п.
- category: "fire_fighting" для П1, П2 и т.п.
- name: точное обозначение системы (напр. "В1", "В1.1", "К1")
- material: материал труб, если указан в ТЗ
- diameters: диаметры трубопроводов, если указаны (напр. "DN50", "DN65, DN100")
- insulation: тип и толщина изоляции, если указана
- laying: способ прокладки, если указан (подземная, надземная, подвесная, в канале)

ВАЖНО: Если по какому-то полю в тексте ТЗ НЕТ информации — ставь прочерк "-".
Не оставляй пустые строки "" — используй только "-" для отсутствующих данных.

Верни JSON строго по этой структуре (без пояснений, только JSON):

{
  "tz_water_supply": "ПОЛНЫЙ текст раздела водоснабжения (ХВС, ГВС) из ТЗ — скопируй дословно, не сокращай",
  "tz_sewerage": "ПОЛНЫЙ текст раздела водоотведения и канализации из ТЗ — скопируй дословно, не сокращай",
  "tz_fire_fighting": "ПОЛНЫЙ текст раздела пожаротушения из ТЗ — скопируй дословно, не сокращай",
  "systems": [
    {
      "category": "water_supply",
      "name": "В1",
      "material": "сталь",
      "diameters": "DN50",
      "insulation": "-",
      "laying": "-"
    },
    {
      "category": "water_supply",
      "name": "В1.1",
      "material": "-",
      "diameters": "-",
      "insulation": "-",
      "laying": "-"
    }
  ]
}"""


_EMPTY_PIPELINE = {
    "systems": [],
}


_SYSTEM_RE = re.compile(r'(?<![а-яА-Яa-zA-Z])([ВКТП])(\d+(?:\.\d+)?)\b')

_CATEGORY_BY_LETTER = {
    'В': 'water_supply',
    'Т': 'water_supply',
    'К': 'sewerage',
    'П': 'fire_fighting',
}


def _regex_find_systems(text: str) -> list[dict]:
    """Find system designations missed by AI using regex as fallback."""
    found = set()
    systems = []
    for letter, num in _SYSTEM_RE.findall(text):
        name = letter + num
        key = name.lower()
        if key in found:
            continue
        found.add(key)
        cat = _CATEGORY_BY_LETTER.get(letter)
        if not cat:
            continue
        systems.append({
            "category": cat,
            "name": name,
            "material": "-",
            "diameters": "-",
            "insulation": "-",
            "laying": "-",
        })
    return systems


def _merge_systems(ai_systems: list[dict], regex_systems: list[dict]) -> list[dict]:
    """Merge AI and regex system lists: deduplicate by name+category,
    keep AI data when available, fill rest with regex entries."""
    seen = {}
    for s in ai_systems:
        key = (s.get("name", "").lower(), s.get("category", ""))
        if key[0]:
            seen[key] = s
    for s in regex_systems:
        key = (s.get("name", "").lower(), s.get("category", ""))
        if key[0] and key not in seen:
            seen[key] = s
    return list(seen.values())


async def _extract_water_sewer(section_text: str) -> dict:
    if not section_text.strip():
        return {"tz_water_supply": "", "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": FIND_AND_EXTRACT_SYSTEMS_PROMPT},
            {"role": "user", "content": f"Найди ВСЕ системы водоснабжения, водоотведения и пожаротушения в этом разделе ТЗ и извлеки по каждой все доступные данные. Если данных нет — ставь прочерк:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_water_supply": section_text[:1000], "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)

        # Extract full text sections
        tz_ws = _safe_str(parsed.get("tz_water_supply"))
        tz_sew = _safe_str(parsed.get("tz_sewerage"))
        tz_ff = _safe_str(parsed.get("tz_fire_fighting"))

        # Extract systems from AI
        ai_systems_raw = parsed.get("systems", [])
        if not isinstance(ai_systems_raw, list):
            ai_systems_raw = []

        # Also check pipeline_data.systems for backward compatibility
        pd = parsed.get("pipeline_data")
        if isinstance(pd, dict):
            pd_systems = pd.get("systems", [])
            if isinstance(pd_systems, list):
                ai_systems_raw = ai_systems_raw + pd_systems

        # Deduplicate AI systems by name+category
        seen_ai = {}
        for s in ai_systems_raw:
            if not isinstance(s, dict):
                continue
            key = (s.get("name", "").strip().lower(), s.get("category", ""))
            if key[0]:
                seen_ai[key] = s
        ai_systems = list(seen_ai.values())

        # Fallback: find systems via regex
        regex_systems = _regex_find_systems(section_text)

        # Merge: AI data takes priority, regex fills gaps
        merged = _merge_systems(ai_systems, regex_systems)

        # Build final systems array with "-" for missing fields
        final_systems = []
        for s in merged:
            final_systems.append({
                "id": "",
                "category": s.get("category", "water_supply"),
                "name": _dash_if_empty(s.get("name", "")),
                "material": _dash_if_empty(s.get("material", "")),
                "diameters": _dash_if_empty(s.get("diameters", s.get("diameter", ""))),
                "insulation": _dash_if_empty(s.get("insulation", "")),
                "laying": _dash_if_empty(s.get("laying", s.get("laying_method", ""))),
            })

        return {
            "tz_water_supply": tz_ws,
            "tz_sewerage": tz_sew,
            "tz_fire_fighting": tz_ff,
            "pipeline_data": {"systems": final_systems},
        }
    except json.JSONDecodeError:
        logger.error(f"Water/sewer extract: invalid JSON: {result[:200]}")
        return {"tz_water_supply": section_text[:1000], "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}


# ─── Phase 2c: extract BIM requirements ───────────────────────────

BIM_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста технического задания выдели ВСЕ требования к информационной модели здания максимально подробно.

Верни JSON. Если данных нет — пустая строка "":

{
  "bim_requirements": "ПОЛНЫЙ текст раздела BIM-требований из ТЗ — дословно",
  "lod_requirements": "требования к уровням детализации LOD (по дисциплинам: архитектура, КР, ОВиК, ВК, ЭОМ): какие LOD для каких разделов",
  "file_formats": "требования к форматам файлов (RVT, IFC, DWG, DWF, PDF, и т.д.)",
  "classification": "требования к классификатору (OmniClass, UniClass, КСИ и т.п.)",
  "software_versions": "требования к версиям ПО (Revit, AutoCAD, Navisworks и т.д.)",
  "eir_requirements": "требования EIR (Employer's Information Requirements)",
  "bep_requirements": "требования BEP (BIM Execution Plan)",
  "cde_platform": "платформа CDE (общая среда данных): Autodesk Docs, BIM 360, Revizto и т.п.",
  "parameter_requirements": "требования к параметрам элементов: состав, правила заполнения, общие параметры",
  "naming_conventions": "требования к именованию файлов, видов, листов, элементов",
  "coordination_requirements": "требования к координации и коллизионной проверке",
  "quantity_takeoff": "требования к спецификациям и ведомостям объёмов работ",
  "delivery_milestones": "сроки и этапы предоставления моделей"
}"""


async def _extract_bim(section_text: str) -> dict:
    if not section_text.strip():
        return {k: "" for k in ("bim_requirements", "lod_requirements", "file_formats", "classification", "software_versions", "eir_requirements", "bep_requirements", "cde_platform", "parameter_requirements", "naming_conventions", "coordination_requirements", "quantity_takeoff", "delivery_milestones")}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": BIM_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки максимально подробно BIM-требования из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"bim_requirements": section_text[:1000], "lod_requirements": "", "file_formats": "", "classification": "", "software_versions": "", "eir_requirements": "", "bep_requirements": "", "cde_platform": "", "parameter_requirements": "", "naming_conventions": "", "coordination_requirements": "", "quantity_takeoff": "", "delivery_milestones": ""}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = ("bim_requirements", "lod_requirements", "file_formats", "classification", "software_versions", "eir_requirements", "bep_requirements", "cde_platform", "parameter_requirements", "naming_conventions", "coordination_requirements", "quantity_takeoff", "delivery_milestones")
        return {k: _safe_str(parsed.get(k)) for k in keys}
    except json.JSONDecodeError:
        logger.error(f"BIM extract: invalid JSON: {result[:200]}")
        return {"bim_requirements": section_text[:1000]}


# ─── Phase 2d: extract equipment details ──────────────────────────

EQUIPMENT_SYSTEM_PROMPT = """Ты — инженер-сантехник. Из текста технического задания выдели ВСЕ данные по оборудованию инженерных систем.

Верни JSON. Если данных нет — пустая строка "":

{
  "tz_equipment": "ПОЛНЫЙ текст раздела об оборудовании из ТЗ — дословно",
  "pumps_water": "насосы водоснабжения: тип (циркуляционный, повысительный), марка, подача (м³/ч), напор (м), мощность (кВт), количество, расположение",
  "pumps_sewer": "насосы канализационные (фекальные, дренажные): тип, марка, подача, напор, мощность, количество",
  "pumps_fire": "насосы пожарные: тип (основной, жокей), марка, подача, напор, мощность, количество",
  "boilers": "котлы/водонагреватели: тип (электрический, газовый), марка, мощность (кВт), объём (л), количество",
  "heat_exchangers": "теплообменники: тип (пластинчатый, кожухотрубный), марка, мощность, количество",
  "tanks": "резервуары/баки: тип, объём (м³/л), материал, расположение (подвал, техэтаж)",
  "water_treatment": "водоподготовка: фильтры, умягчители, обезжелезиватели — тип, марка, производительность",
  "valves_general": "арматура общая: типы (задвижки, затворы, клапаны, краны), материал корпуса, DN, PN, тип привода (ручной, электрический)",
  "control_valves": "регулирующая арматура: клапаны регулирующие, балансировочные, термостатические — DN, PN, Kv, тип привода",
  "measuring_devices": "приборы учёта и измерения: счетчики воды, тепла, манометры, термометры — тип, DN, расположение",
  "fittings_data": "фитинги и соединительные детали: типы (отводы, переходы, тройники, фланцы), материалы, сортамент"
}"""


async def _extract_equipment(section_text: str) -> dict:
    if not section_text.strip():
        return {k: "" for k in ("tz_equipment", "pumps_water", "pumps_sewer", "pumps_fire", "boilers", "heat_exchangers", "tanks", "water_treatment", "valves_general", "control_valves", "measuring_devices", "fittings_data")}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": EQUIPMENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки максимально подробно данные об оборудовании из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_equipment": section_text[:1000]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = ("tz_equipment", "pumps_water", "pumps_sewer", "pumps_fire", "boilers", "heat_exchangers", "tanks", "water_treatment", "valves_general", "control_valves", "measuring_devices", "fittings_data")
        return {k: _safe_str(parsed.get(k)) for k in keys}
    except json.JSONDecodeError:
        logger.error(f"Equipment extract: invalid JSON: {result[:200]}")
        return {"tz_equipment": section_text[:1000]}


# ─── Phase 2e: extract materials / insulation ─────────────────────

MATERIALS_SYSTEM_PROMPT = """Ты — инженер-сантехник. Из текста ТЗ выдели данные по материалам труб, фитингов и изоляции.

Верни JSON:
{
  "tz_materials": "весь текст раздела о материалах из ТЗ — дословно",
  "pipe_materials_cold_water": "материалы труб ХВС (полипропилен PP-R, сшитый полиэтилен PEX, металлопластик, сталь, медь, нержавейка)",
  "pipe_materials_hot_water": "материалы труб ГВС и их отличия от ХВС",
  "pipe_materials_sewer": "материалы труб канализации (ПВХ, ПП, чугунные, керамические)",
  "pipe_materials_fire": "материалы труб пожаротушения (стальные электросварные, бесшовные, оцинкованные)",
  "insulation_cold": "изоляция ХВС: тип, толщина (мм), требования к пароизоляции",
  "insulation_hot": "изоляция ГВС и отопления: тип, толщина (мм), температурный режим",
  "insulation_sewer": "изоляция канализации: тип, толщина, шумозащита",
  "insulation_fire": "изоляция пожаротушения: тип, толщина, огнестойкость",
  "anticorrosion": "антикоррозийная защита: тип покрытия, количество слоёв, грунтовка, окраска",
  "coloring_marking": "окраска и маркировка труб: цвета по стандарту, надписи, стрелки направления",
  "insulation_standards": "нормативные документы по изоляции и материалам"
}"""


async def _extract_materials(section_text: str) -> dict:
    if not section_text.strip():
        return {k: "" for k in ("tz_materials", "pipe_materials_cold_water", "pipe_materials_hot_water", "pipe_materials_sewer", "pipe_materials_fire", "insulation_cold", "insulation_hot", "insulation_sewer", "insulation_fire", "anticorrosion", "coloring_marking", "insulation_standards")}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": MATERIALS_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки данные о материалах и изоляции из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_materials": section_text[:1000]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = ("tz_materials", "pipe_materials_cold_water", "pipe_materials_hot_water", "pipe_materials_sewer", "pipe_materials_fire", "insulation_cold", "insulation_hot", "insulation_sewer", "insulation_fire", "anticorrosion", "coloring_marking", "insulation_standards")
        return {k: _safe_str(parsed.get(k)) for k in keys}
    except json.JSONDecodeError:
        logger.error(f"Materials extract: invalid JSON: {result[:200]}")
        return {"tz_materials": section_text[:1000]}


# ─── Phase 2f: extract testing requirements ───────────────────────

TESTING_SYSTEM_PROMPT = """Ты — инженер. Из текста ТЗ выдели требования к испытаниям и пусконаладочным работам.

Верни JSON:
{
  "tz_testing": "весь текст раздела об испытаниях из ТЗ — дословно",
  "hydrostatic_pressure": "гидравлические испытания: пробное давление (МПа/кгс/см²), продолжительность, методика",
  "flushing": "промывка и дезинфекция трубопроводов: требования, реагенты",
  "leak_test": "испытания на герметичность: давление, метод (пневматический/гидравлический)",
  "commissioning": "пусконаладочные работы: состав, требования к документации",
  "quality_control": "контроль качества: методы (радиографический, ультразвуковой), объём контроля сварных швов",
  "testing_standards": "нормативные документы по испытаниям"
}"""


async def _extract_testing(section_text: str) -> dict:
    if not section_text.strip():
        return {k: "" for k in ("tz_testing", "hydrostatic_pressure", "flushing", "leak_test", "commissioning", "quality_control", "testing_standards")}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": TESTING_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки требования к испытаниям из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_testing": section_text[:1000]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = ("tz_testing", "hydrostatic_pressure", "flushing", "leak_test", "commissioning", "quality_control", "testing_standards")
        return {k: _safe_str(parsed.get(k)) for k in keys}
    except json.JSONDecodeError:
        logger.error(f"Testing extract: invalid JSON: {result[:200]}")
        return {"tz_testing": section_text[:1000]}


# ─── Phase 2g: extract standards ──────────────────────────────────

STANDARDS_SYSTEM_PROMPT = """Ты — инженер. Из текста ТЗ выдели ВСЕ ссылки на нормативные документы.

Верни JSON:
{
  "tz_standards": "весь текст из ТЗ со ссылками на нормы — дословно",
  "sp_list": "перечень СП (Сводов Правил): каждый с номером и названием",
  "snip_list": "перечень СНиП: каждый с номером и названием",
  "gost_list": "перечень ГОСТ: каждый с номером и названием",
  "iso_list": "перечень ISO и международных стандартов",
  "other_standards": "прочие нормы (СанПиН, НПБ, ВСН, ТУ, ведомственные нормы)"
}"""


async def _extract_standards(section_text: str) -> dict:
    if not section_text.strip():
        return {k: "" for k in ("tz_standards", "sp_list", "snip_list", "gost_list", "iso_list", "other_standards")}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": STANDARDS_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки ВСЕ нормативные ссылки из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_standards": section_text[:1000]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        keys = ("tz_standards", "sp_list", "snip_list", "gost_list", "iso_list", "other_standards")
        return {k: _safe_str(parsed.get(k)) for k in keys}
    except json.JSONDecodeError:
        logger.error(f"Standards extract: invalid JSON: {result[:200]}")
        return {"tz_standards": section_text[:1000]}


# ─── Phase 2h: extract other systems ──────────────────────────────

OTHER_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста технического задания выдели информацию о прочих инженерных системах.

Верни JSON:
{
  "tz_other": "весь текст о прочих системах из ТЗ — дословно (отопление, вентиляция, кондиционирование, электрика, слаботочные системы, автоматизация и т.д.)"
}"""


async def _extract_other(section_text: str) -> dict:
    if not section_text.strip():
        return {"tz_other": ""}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": OTHER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки информацию о прочих инженерных системах:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    if not result:
        return {"tz_other": section_text[:1000]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {"tz_other": _safe_str(parsed.get("tz_other"))}
    except json.JSONDecodeError:
        logger.error(f"Other extract: invalid JSON: {result[:200]}")
        return {"tz_other": section_text[:1000]}


# ─── Helpers ──────────────────────────────────────────────────────

def _dash_if_empty(val: str) -> str:
    """Return '-' if val is empty/None/whitespace, else val."""
    return "-" if not val or not val.strip() else val


def _safe_str(val, default=""):
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
        return default if s in ("{}", "[]") else s
    return str(val)


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl != -1 else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


# ─── File extraction ──────────────────────────────────────────────

def extract_text_from_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
        return "\n\n".join(texts)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""


def extract_text_from_excel(path: str) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        texts = []
        for sheet in wb.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                vals = [str(v) for v in row if v is not None]
                if vals:
                    rows.append(" | ".join(vals))
            texts.append(f"--- Лист: {sheet.title} ---\n" + "\n".join(rows))
        return "\n\n".join(texts)
    except Exception as e:
        logger.error(f"Excel extraction error: {e}")
        return ""


def extract_text_from_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in (".xlsx", ".xls"):
        return extract_text_from_excel(path)
    return ""


# ─── Orchestrator ─────────────────────────────────────────────────

_DEFAULT_RETURN = {
    # General
    "project_name": "", "project_type": "", "project_purpose": "",
    "project_address": "", "sections_count": "", "floors_count": "",
    "underground_floors": "", "building_height": "", "total_area": "",
    "construction_year": "", "structural_system": "",
    "tz_general": "",
    # Water/Sewer/Fire
    "tz_water_supply": "", "tz_sewerage": "", "tz_fire_fighting": "",
    # BIM
    "bim_requirements": "", "lod_requirements": "", "file_formats": "",
    "classification": "", "software_versions": "", "eir_requirements": "",
    "bep_requirements": "", "cde_platform": "", "parameter_requirements": "",
    "naming_conventions": "", "coordination_requirements": "", "quantity_takeoff": "",
    "delivery_milestones": "",
    # Equipment
    "tz_equipment": "", "pumps_water": "", "pumps_sewer": "", "pumps_fire": "",
    "boilers": "", "heat_exchangers": "", "tanks": "", "water_treatment": "",
    "valves_general": "", "control_valves": "", "measuring_devices": "", "fittings_data": "",
    # Materials
    "tz_materials": "", "pipe_materials_cold_water": "", "pipe_materials_hot_water": "",
    "pipe_materials_sewer": "", "pipe_materials_fire": "",
    "insulation_cold": "", "insulation_hot": "", "insulation_sewer": "", "insulation_fire": "",
    "anticorrosion": "", "coloring_marking": "", "insulation_standards": "",
    # Testing
    "tz_testing": "", "hydrostatic_pressure": "", "flushing": "", "leak_test": "",
    "commissioning": "", "quality_control": "", "testing_standards": "",
    # Standards
    "tz_standards": "", "sp_list": "", "snip_list": "", "gost_list": "", "iso_list": "", "other_standards": "",
    # Other
    "tz_other": "",
    # Pipeline data
    "pipeline_data": _EMPTY_PIPELINE,
}


async def parse_tz_document(text: str) -> dict:
    if not text.strip():
        return dict(_DEFAULT_RETURN)

    logger.info("Phase 1: splitting document into sections...")
    sections = await _split_sections(text)

    # Fire all extraction phases in parallel
    logger.info("Phase 2: extracting info from each section in parallel...")
    general_task = _extract_general(sections.get("general_section", ""))
    ws_task = _extract_water_sewer(sections.get("water_sewer_section", ""))
    bim_task = _extract_bim(sections.get("bim_section", ""))
    equipment_task = _extract_equipment(sections.get("equipment_section", ""))
    materials_task = _extract_materials(sections.get("materials_insulation_section", ""))
    testing_task = _extract_testing(sections.get("testing_section", ""))
    standards_task = _extract_standards(sections.get("standards_section", ""))
    other_task = _extract_other(sections.get("other_section", ""))

    (general, ws, bim, equipment, materials, testing, standards, other) = await asyncio.gather(
        general_task, ws_task, bim_task, equipment_task, materials_task, testing_task, standards_task, other_task,
    )

    result = dict(_DEFAULT_RETURN)
    result.update(general)
    result.update(ws)
    result.update(bim)
    result.update(equipment)
    result.update(materials)
    result.update(testing)
    result.update(standards)
    result["tz_other"] = other.get("tz_other") or ""

    # Sanitize pipeline_data
    pd = result.get("pipeline_data", _EMPTY_PIPELINE)
    if not isinstance(pd, dict):
        pd = {"systems": []}
    raw_systems = pd.get("systems", [])
    if not isinstance(raw_systems, list):
        raw_systems = []
    cleaned = []
    for s in raw_systems:
        if not isinstance(s, dict):
            continue
        cleaned.append({
            "id": s.get("id", ""),
            "category": s.get("category", "water_supply"),
            "name": _dash_if_empty(s.get("name", "")),
            "material": _dash_if_empty(s.get("material", "")),
            "diameters": _dash_if_empty(s.get("diameters", s.get("diameter", ""))),
            "insulation": _dash_if_empty(s.get("insulation", "")),
            "laying": _dash_if_empty(s.get("laying", s.get("laying_method", ""))),
        })
    pd["systems"] = cleaned
    result["pipeline_data"] = pd

    non_empty = {k: v for k, v in result.items() if isinstance(v, str) and v.strip()}
    logger.info(f"TZ parsing complete: {len(non_empty)} non-empty fields, "
                f"total ~{sum(len(v) for v in non_empty.values())} chars")

    return result
