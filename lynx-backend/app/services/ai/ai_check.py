import json
import logging
from collections import Counter

from .client import ai_chat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — эксперт BIM-инспектор по инженерным системам зданий. Твоя задача — проверить соответствие элементов BIM-модели техническому заданию (ТЗ) и сводам правил (СП).

## Нормативная база (СП)

### СП 30.13330.2020 "Внутренний водопровод и канализация зданий"
- Минимальный диаметр труб ХВС в магистралях: 50 мм; в стояках: 25 мм; в разводке: 15 мм
- Минимальный диаметр канализации: 50 мм для отводов от приборов, 100 мм для стояков
- Трубы ГВС должны иметь тепловую изоляцию
- Материалы: сталь, полипропилен (ППР, PPR), полиэтилен (ПНД, HDPE), металлопластик, сшитый полиэтилен (PEX)
- Для ХВС допустимы: сталь, ППР, ПНД, PEX, металлопластик
- Для ГВС допустимы: сталь, ППР (армированный), PEX, металлопластик (сшитый)
- Для канализации: чугун, полипропилен (ПП), ПВХ

### СП 31.13330.2021 "Водоснабжение. Наружные сети"
- Наружные сети водоснабжения: полиэтилен (ПНД, ПЭ100), сталь, чугун (ВЧШГ)
- Диаметры наружных сетей: от 50 мм до 1200 мм
- Материалы для питьевого водоснабжения должны иметь санитарно-эпидемиологическое заключение

### СП 10.13130.2020 "Внутреннее противопожарное водоснабжение"
- Пожарные краны: диаметр 50 мм (для зданий до 17 этажей) или 65 мм (выше 17 этажей)
- Расход: 2.5 л/с (пожарный кран)
- Материал труб: сталь (обычно электросварные или водогазопроводные)
- Диаметр стояков пожаротушения: не менее 50 мм
- Тепловая изоляция: не требуется (только защита от замерзания)
- Запорная арматура: стальная, чугунная

### СП 485.1311500.2020 "Системы противопожарной защиты. Установки пожаротушения автоматические"
- Спринклерные системы: трубы стальные электросварные, диаметр от 25 мм
- Для спринклеров: рабочее давление до 1.0 МПа
- Диаметры труб для спринклерных сетей: 25-200 мм
- Толщина стенки труб: от 2.0 до 4.0 мм в зависимости от диаметра

## ВАЖНО: проверка ТЗ
ТЗ содержит конкретные требования к материалам, диаметрам, изоляции для каждой системы.
ЧЕКЛИСТ ТРЕБОВАНИЙ ТЗ содержит строгие условия — проверь каждый элемент модели на соответствие этим условиям.

Если ТЗ указывает для системы "сталь на грувлоках" — это значит:
- Материал элементов системы ДОЛЖЕН быть сталь (steel)
- Тип соединения должен быть грувлок (grooved)
Любое отклонение от требований ТЗ — это ошибка (error).

## Формат ответа

Верни JSON-массив problems. Каждый элемент массива — объект:

{
  "rule_key": "viv.ai.<категория>.<тип>",
  "severity": "error" или "warning",
  "message": "понятное описание проблемы на русском",
  "details": "подробное техническое обоснование со ссылкой на ТЗ или СП",
  "element_ids": ["global_id_1", "global_id_2", "..."],
  "dismissed": false
}

⚠️ ВАЖНО: Для каждой проблемы обязательно укажи element_ids — массив global_id элементов, к которым относится проблема. Не оставляй пустым! GlobalId указан у каждого элемента в списке (поле gid=...).

Верни ТОЛЬКО JSON-массив. Если проблем нет — верни [].

ОБЯЗАТЕЛЬНО: Каждая проблема должна содержать element_ids с global_id элементов, к которым относится. Если проблема касается конкретного элемента — укажи его GlobalId. Если проблема общая для группы элементов (например, все элементы системы) — перечисли GlobalId всех затронутых элементов.

Анализируй следующие аспекты в порядке приоритета:
1. Материалы элементов не соответствуют требованиям ТЗ (материал должен быть строго как в ТЗ для этой системы)
2. Диаметры элементов выходят за диапазон, указанный в ТЗ (проверить каждый элемент по его DN)
3. Отсутствует изоляция там, где ТЗ её требует
4. Элементы имеют пустые/незаполненные критические параметры (система, материал, диаметр). Если у большинства элементов в системе материал не указан "(не указан)" — это повод для warning: "Не удалось определить материал элементов, невозможно проверить соответствие ТЗ"
5. Имена элементов не соответствуют стандарту именования из ТЗ
6. Отсутствуют обязательные системы, указанные в ТЗ
7. Параметры противоречат СП (диаметр меньше минимального, недопустимый материал)"""


async def run_ai_check(project_id: str, elements: list[dict], tz_data: dict) -> list[dict]:
    requirements = _build_requirements_checklist(tz_data)
    elements_summary = _summarize_elements(elements)
    tz_summary = _summarize_tz(tz_data)

    prompt_parts = [
        "## ЧЕКЛИСТ ТРЕБОВАНИЙ ТЗ (обязательная проверка для каждой системы):",
        requirements,
        "",
        "## Элементы BIM-модели (сгруппированы по системе):",
        elements_summary,
        "",
        "## Полное описание ТЗ:",
        tz_summary,
    ]
    user_prompt = "\n".join(prompt_parts)

    full_text = user_prompt
    if len(full_text) > 80000:
        full_text = full_text[-80000:]

    logger.info(f"=== AI CHECK PROMPT (len={len(full_text)}) ===")
    logger.info(f"SYSTEM PROMPT:\n{SYSTEM_PROMPT[:1000]}")
    logger.info(f"USER PROMPT:\n{full_text[:3000]}")
    logger.info(f"=== END PROMPT ===")

    result = await ai_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Проверь соответствие элементов BIM-модели техническому заданию и нормам СП. Найди несостыковки, ошибки, пропуски.\n\n{full_text}"},
        ],
        temperature=0.1,
        max_tokens=8192,
    )

    logger.info(f"=== AI CHECK RESPONSE ===")
    logger.info(f"{result}")
    logger.info(f"=== END RESPONSE ===")

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
        problems = json.loads(cleaned)
        if not isinstance(problems, list):
            logger.warning(f"AI check: expected list, got {type(problems)}")
            return []
        for p in problems:
            p.setdefault("dismissed", False)
            p.setdefault("element_ids", [])
            if not p["element_ids"]:
                logger.warning(f"AI check: problem {p.get('rule_key','?')} has empty element_ids, attempting to fill")
                _fill_element_ids(p, elements)
                if not p["element_ids"]:
                    logger.warning(f"AI check: still empty element_ids for {p.get('rule_key','?')}: {p.get('message','')[:80]}")
        return problems
    except json.JSONDecodeError:
        logger.error(f"AI check: invalid JSON response: {result[:500]}")
        return []


def _extract_material(el: dict) -> str:
    raw = el.get("raw_psets_jsonb") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    mat = el.get("canonical", {}).get("material") or ""
    if not mat:
        mat = raw.get("Pset_PipeSegmentCommon", {}).get("Material") or ""
    if not mat:
        mat = raw.get("Pset_PipeFittingCommon", {}).get("Material") or ""
    if not mat:
        mat = raw.get("Material", "") or ""
    # Search ALL psets for any key related to material
    if not mat:
        material_keys = ["Material", "Материал", "PipeMaterial", "BRU_Материал", "mat", "MAT"]
        for pset_name, pset_data in raw.items():
            if not isinstance(pset_data, dict):
                continue
            for key in material_keys:
                val = pset_data.get(key)
                if val and str(val).strip():
                    mat = str(val).strip()
                    break
            if mat:
                break
    return str(mat)


def _extract_diameter(el: dict):
    dia = el.get("canonical", {}).get("diameter_mm")
    if dia is not None:
        return dia
    raw = el.get("raw_psets_jsonb") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    for pset in raw.values():
        if isinstance(pset, dict):
            for k, v in pset.items():
                kl = k.lower()
                if "диаметр" in kl or "diameter" in kl or "dn" == kl.strip().lower():
                    try:
                        return float(str(v).replace(",", ".").replace("DN", "").replace("dn", "").strip())
                    except (ValueError, TypeError):
                        pass
    return None


def _fill_element_ids(problem: dict, elements: list[dict]):
    """Try to fill element_ids from elements list if AI didn't provide them."""
    import re
    msg = (problem.get("message") or "") + " " + (problem.get("details") or "")
    msg_lower = msg.lower()

    # Build a lookup: element name -> list of global_ids
    name_to_ids = {}
    for el in elements:
        name = (el.get("name") or "").strip()
        gid = el.get("global_id") or ""
        if name and gid:
            name_to_ids.setdefault(name.lower(), set()).add(gid)

    # Try to match by element name mentioned in the message
    found = set()
    for el in elements:
        el_name = (el.get("name") or "").strip()
        gid = el.get("global_id") or ""
        if not gid:
            continue
        # Check if the element name appears in the message
        if el_name and el_name.lower() in msg_lower:
            found.add(gid)

    if found:
        problem["element_ids"] = sorted(found)


def _summarize_elements(elements: list[dict]) -> str:
    if not elements:
        return "Нет элементов в модели."

    systems = {}
    for el in elements:
        sys = el.get("system_name") or "Без системы"
        if sys not in systems:
            systems[sys] = {
                "count": 0,
                "ifc_classes": set(),
                "materials": Counter(),
                "diameters": Counter(),
                "elements": [],
            }
        s = systems[sys]
        s["count"] += 1
        s["ifc_classes"].add(el.get("ifc_class") or "?")

        mat = _extract_material(el)
        if mat:
            s["materials"][mat] += 1
        else:
            s["materials"]["(не указан)"] += 1

        dia = _extract_diameter(el)
        if dia is not None:
            s["diameters"][f"{dia:.0f}"] += 1
        else:
            s["diameters"]["(не указан)"] += 1

        s["elements"].append({
            "gid": el.get("global_id") or "?",
            "name": el.get("name") or "(без имени)",
            "mat": mat or "?",
            "dia": f"{dia:.0f}" if dia is not None else "?",
        })

    lines = []
    for sys_name, info in sorted(systems.items()):
        classes = ", ".join(sorted(info["ifc_classes"]))
        mat_breakdown = "; ".join(f"{m}={c}" for m, c in info["materials"].most_common())
        dia_breakdown = "; ".join(f"DN{d}={c}" for d, c in info["diameters"].most_common())

        lines.append(
            f"Система: {sys_name} (всего {info['count']} элементов)\n"
            f"  IFC-классы: {classes}\n"
            f"  Материалы (распределение): {mat_breakdown}\n"
            f"  Диаметры (распределение): {dia_breakdown}"
        )

        # Show individual elements for systems with ≤100 elements
        if info["count"] <= 100:
            for el_sm in info["elements"]:
                lines.append(f"    - {el_sm['name']} | мат={el_sm['mat']} | DN={el_sm['dia']} | gid={el_sm['gid']}")
        else:
            sample = info["elements"][:10]
            for el_sm in sample:
                lines.append(f"    - {el_sm['name']} | мат={el_sm['mat']} | DN={el_sm['dia']} | gid={el_sm['gid']}")
            lines.append(f"    ... и ещё {info['count'] - 10} элементов")

    return "\n".join(lines)


def _build_requirements_checklist(tz_data: dict) -> str:
    parts = []
    pd = tz_data.get("pipeline_data") or {}
    sys_map = {"water_supply": "Водоснабжение", "sewerage": "Водоотведение", "fire_fighting": "Пожаротушение"}
    sec_map = {"mains": "Магистрали", "risers": "Стояки", "distribution": "Разводка"}

    # Structured requirements from pipeline_data
    for sys_key, sys_label in sys_map.items():
        sys_data = pd.get(sys_key) or {}
        reqs = []
        for sec_key, sec_label in sec_map.items():
            sec = sys_data.get(sec_key) or {}
            conds = []
            if sec.get("material"):
                conds.append(f"материал = '{sec['material']}'")
            if sec.get("diameter"):
                raw = str(sec["diameter"]).replace(",", ".").replace("DN", "").strip()
                try:
                    val = float(raw)
                    conds.append(f"диаметр ≤ {val:.0f} мм")
                except ValueError:
                    conds.append(f"диаметр = {sec['diameter']}")
            if sec.get("insulation") and sec["insulation"].strip().lower() not in ("нет", "-", ""):
                conds.append(f"изоляция = '{sec['insulation']}'")
            if conds:
                reqs.append(f"  - {sec_label}: «{' | '.join(conds)}»")
        if reqs:
            parts.append(f"{sys_label}:\n" + "\n".join(reqs))

    # Extract explicit technical requirements from free-text fields
    details = tz_data.get("tz_details") or {}
    text_fields = [
        ("tz_water_supply", "Водоснабжение"),
        ("tz_sewerage", "Водоотведение"),
        ("tz_fire_fighting", "Пожаротушение"),
        ("tz_other", "Прочие системы"),
        ("tz_general", "Общие требования"),
    ]
    for key, label in text_fields:
        text = details.get(key) or tz_data.get(key) or ""
        text = text.strip()
        if text and len(text) > 10:
            parts.append(f"{label} (описание): {text[:600]}")

    # BIM requirements
    bim = details.get("bim_requirements") or tz_data.get("bim_requirements") or ""
    if bim:
        parts.append(f"BIM-требования: {bim[:300]}")

    if not parts:
        return "ТЗ не заполнено — проверка только по СП."

    return "\n\n".join(parts)


def _summarize_tz(tz_data: dict) -> str:
    parts = []
    details = tz_data.get("tz_details") or {}

    for key, label in [("project_name", "Название проекта"), ("project_type", "Тип объекта"),
                        ("project_purpose", "Назначение"), ("project_address", "Адрес"),
                        ("sections_count", "Количество секций"), ("floors_count", "Этажей"),
                        ("underground_floors", "Подземных этажей"), ("building_height", "Высота здания"),
                        ("total_area", "Общая площадь"), ("structural_system", "Конструктивная схема")]:
        val = details.get(key) or tz_data.get(key) or ""
        if val:
            parts.append(f"{label}: {val}")

    if details.get("tz_general") or tz_data.get("tz_general"):
        general = details.get("tz_general") or tz_data["tz_general"]
        parts.append(f"Общее описание:\n{general}")

    for key, label in [("tz_water_supply", "Водоснабжение"), ("tz_sewerage", "Водоотведение"),
                        ("tz_fire_fighting", "Пожаротушение"), ("tz_other", "Прочие системы")]:
        val = details.get(key) or tz_data.get(key) or ""
        if val:
            parts.append(f"{label}:\n{val}")

    bim = details.get("bim_requirements") or tz_data.get("bim_requirements") or ""
    if bim:
        parts.append(f"BIM-требования:\n{bim}")
    for key, label in [("lod_requirements", "LOD"), ("file_formats", "Форматы файлов"),
                        ("classification", "Классификатор"), ("software_versions", "Версии ПО"),
                        ("parameter_requirements", "Требования к параметрам"),
                        ("naming_conventions", "Именование"), ("coordination_requirements", "Координация"),
                        ("cde_platform", "CDE платформа")]:
        val = details.get(key) or ""
        if val:
            parts.append(f"  {label}: {val}")

    if details.get("tz_equipment") or tz_data.get("tz_equipment"):
        equip = details.get("tz_equipment") or tz_data.get("tz_equipment") or ""
        parts.append(f"Оборудование:\n{equip}")

    if details.get("tz_materials"):
        parts.append(f"Материалы:\n{details['tz_materials']}")
    for key, label in [("pipe_materials_cold_water", "Трубы ХВС"), ("pipe_materials_hot_water", "Трубы ГВС"),
                        ("pipe_materials_sewer", "Трубы канализации"), ("pipe_materials_fire", "Трубы ПТ"),
                        ("insulation_cold", "Изоляция ХВС"), ("insulation_hot", "Изоляция ГВС"),
                        ("insulation_sewer", "Изоляция канализации"), ("insulation_fire", "Изоляция ПТ"),
                        ("anticorrosion", "Антикоррозия"), ("coloring_marking", "Окраска/маркировка")]:
        val = details.get(key) or ""
        if val:
            parts.append(f"  {label}: {val}")

    if details.get("tz_testing"):
        parts.append(f"Испытания:\n{details['tz_testing']}")

    if details.get("tz_standards"):
        parts.append(f"Нормативные документы:\n{details['tz_standards']}")

    pd = tz_data.get("pipeline_data") or {}
    sys_labels = {"water_supply": "Водоснабжение", "sewerage": "Водоотведение", "fire_fighting": "Пожаротушение"}
    sec_labels = {"mains": "Магистрали", "risers": "Стояки", "distribution": "Разводка"}
    for sys_key, sys_label in sys_labels.items():
        sys_data = pd.get(sys_key) or {}
        sys_lines = []
        if sys_data.get("description"):
            sys_lines.append(f"  Описание: {sys_data['description']}")
        for sec_key, sec_label in sec_labels.items():
            sec_data = sys_data.get(sec_key) or {}
            vals = []
            if sec_data.get("material"):
                vals.append(f"мат: {sec_data['material']}")
            if sec_data.get("diameter"):
                vals.append(f"DN: {sec_data['diameter']}")
            if sec_data.get("insulation"):
                vals.append(f"изол: {sec_data['insulation']}")
            if sec_data.get("pressure_class"):
                vals.append(f"PN: {sec_data['pressure_class']}")
            if vals:
                sys_lines.append(f"  {sec_label}: {', '.join(vals)}")
        if sys_lines:
            parts.append(f"ТЗ {sys_label}:\n" + "\n".join(sys_lines))

    return "\n\n".join(parts) if parts else "ТЗ не заполнено."
