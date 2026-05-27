import json
import logging

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

## Формат ответа

Верни JSON-массив problems. Каждый элемент массива — объект:

{
  "rule_key": "viv.ai.<категория>.<тип>",
  "severity": "error" или "warning",
  "message": "понятное описание проблемы на русском",
  "details": "подробное техническое обоснование со ссылкой на ТЗ или СП",
  "element_ids": ["global_id элемента (если привязано к конкретному элементу)"]
  "dismissed": false
}

Верни ТОЛЬКО JSON-массив. Если проблем нет — верни [].

Анализируй следующие аспекты:
1. Материалы труб не соответствуют ТЗ (например, в ТЗ указан ППР, а в модели сталь)
2. Диаметры выходят за диапазон, указанный в ТЗ
3. Отсутствует изоляция там, где ТЗ её требует (ГВС, холодные трубопроводы)
4. Элементы имеют пустые/незаполненные критические параметры (система, материал, диаметр)
5. Имена элементов не соответствуют стандарту именования из ТЗ
6. Отсутствуют обязательные системы, указанные в ТЗ
7. Параметры противоречат СП (диаметр меньше минимального, недопустимый материал)"""


async def run_ai_check(project_id: str, elements: list[dict], tz_data: dict) -> list[dict]:
    elements_summary = _summarize_elements(elements)
    tz_summary = _summarize_tz(tz_data)

    prompt_parts = [
        "## Элементы BIM-модели (агрегированные по системе):",
        elements_summary,
        "",
        "## Техническое задание проекта:",
        tz_summary,
    ]
    user_prompt = "\n".join(prompt_parts)

    full_text = user_prompt
    # Truncate if too long (keep last ~80000 chars)
    if len(full_text) > 80000:
        full_text = full_text[-80000:]

    result = await ai_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Проверь соответствие элементов BIM-модели техническому заданию и нормам СП. Найди несостыковки, ошибки, пропуски.\n\n{full_text}"},
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
        problems = json.loads(cleaned)
        if not isinstance(problems, list):
            logger.warning(f"AI check: expected list, got {type(problems)}")
            return []
        for p in problems:
            p.setdefault("dismissed", False)
            p.setdefault("element_ids", [])
        return problems
    except json.JSONDecodeError:
        logger.error(f"AI check: invalid JSON response: {result[:500]}")
        return []


def _summarize_elements(elements: list[dict]) -> str:
    if not elements:
        return "Нет элементов в модели."

    # Group by system_name
    systems = {}
    for el in elements:
        sys = el.get("system_name") or "Без системы"
        if sys not in systems:
            systems[sys] = {"count": 0, "ifc_classes": set(), "materials": set(), "diameters": set(), "names": []}
        systems[sys]["count"] += 1
        systems[sys]["ifc_classes"].add(el.get("ifc_class") or "?")
        systems[sys]["names"].append(el.get("name") or "(без имени)")

        raw = el.get("raw_psets_jsonb") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}

        # Extract material from canonical or raw
        mat = el.get("canonical", {}).get("material") or ""
        if not mat:
            mat = raw.get("Pset_PipeSegmentCommon", {}).get("Material") or ""
        if not mat:
            mat = raw.get("Material", "") or ""
        if mat:
            systems[sys]["materials"].add(str(mat))

        # Extract diameter
        dia = el.get("canonical", {}).get("diameter_mm")
        if dia is not None:
            systems[sys]["diameters"].add(str(dia))

    lines = []
    for sys_name, info in sorted(systems.items()):
        classes = ", ".join(sorted(info["ifc_classes"]))
        materials = ", ".join(sorted(info["materials"])) or "не указан"
        diameters = ", ".join(sorted(info["diameters"])) or "не указан"
        names_sample = info["names"][:5]
        names_str = ", ".join(names_sample)
        if len(info["names"]) > 5:
            names_str += f" ... и ещё {len(info['names']) - 5}"

        lines.append(
            f"Система: {sys_name}\n"
            f"  Количество элементов: {info['count']}\n"
            f"  IFC-классы: {classes}\n"
            f"  Материалы: {materials}\n"
            f"  Диаметры (мм): {diameters}\n"
            f"  Примеры имён: {names_str}"
        )
    return "\n".join(lines)


def _summarize_tz(tz_data: dict) -> str:
    parts = []

    if tz_data.get("tz_general"):
        parts.append(f"Общее описание:\n{tz_data['tz_general']}")
    if tz_data.get("tz_water_supply"):
        parts.append(f"Водоснабжение:\n{tz_data['tz_water_supply']}")
    if tz_data.get("tz_sewerage"):
        parts.append(f"Водоотведение:\n{tz_data['tz_sewerage']}")
    if tz_data.get("tz_fire_fighting"):
        parts.append(f"Пожаротушение:\n{tz_data['tz_fire_fighting']}")
    if tz_data.get("bim_requirements"):
        parts.append(f"BIM-требования:\n{tz_data['bim_requirements']}")
    if tz_data.get("project_address"):
        parts.append(f"Адрес: {tz_data['project_address']}")
    if tz_data.get("sections_count"):
        parts.append(f"Количество секций: {tz_data['sections_count']}")
    if tz_data.get("floors_count"):
        parts.append(f"Количество этажей: {tz_data['floors_count']}")

    # Pipeline data
    pd = tz_data.get("pipeline_data") or {}
    sys_labels = {"water_supply": "Водоснабжение", "sewerage": "Водоотведение", "fire_fighting": "Пожаротушение"}
    sec_labels = {"mains": "Магистрали", "risers": "Стояки", "distribution": "Разводка"}
    for sys_key, sys_label in sys_labels.items():
        sys_data = pd.get(sys_key) or {}
        sys_lines = []
        for sec_key, sec_label in sec_labels.items():
            sec_data = sys_data.get(sec_key) or {}
            vals = []
            if sec_data.get("material"):
                vals.append(f"материал: {sec_data['material']}")
            if sec_data.get("diameter"):
                vals.append(f"диаметр: {sec_data['diameter']}")
            if sec_data.get("insulation"):
                vals.append(f"изоляция: {sec_data['insulation']}")
            if vals:
                sys_lines.append(f"  {sec_label}: {', '.join(vals)}")
        if sys_lines:
            parts.append(f"ТЗ {sys_label}:\n" + "\n".join(sys_lines))

    return "\n\n".join(parts) if parts else "ТЗ не заполнено."
