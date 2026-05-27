import json
import logging
import asyncio
from pathlib import Path

from .client import ai_chat

logger = logging.getLogger(__name__)

# ─── Phase 1: split document into thematic sections ───────────────

SPLIT_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Прочитай техническое задание и распредели его текст по тематическим разделам.

Верни JSON со следующими полями. Каждое поле должно содержать ТОЛЬКО соответствующий текст из документа, скопированный максимально дословно:

1. "general_section" — весь текст из документа, относящийся к общей информации о проекте: общие положения, цели и задачи, адрес, этажность, количество секций, состав проекта, общие требования
2. "water_sewer_section" — весь текст, относящийся к водоснабжению (ХВС, ГВС), водоотведению, канализации, пожаротушению (материалы труб, диаметры, изоляция)
3. "bim_section" — весь текст, относящийся к BIM-требованиям: LOD, форматы файлов, классификатор, требования к модели, обмен данными
4. "other_section" — весь текст, не попавший в предыдущие разделы (отопление, вентиляция, электрика, слаботочные системы и т.д.)

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
            "other_section": _safe_str(parsed.get("other_section")),
        }
    except json.JSONDecodeError:
        logger.error(f"Split phase: AI returned invalid JSON: {result[:300]}")
        return {}


# ─── Phase 2a: extract general info ───────────────────────────────

GENERAL_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста раздела технического задания выдели общую информацию о проекте.

Верни JSON со следующими полями (все поля — строки, НЕ массивы и НЕ объекты):
{
  "tz_general": "общее описание проекта: цели, состав, общие требования",
  "project_address": "адрес объекта строительства",
  "sections_count": "количество секций (напр. '3')",
  "floors_count": "количество этажей (напр. '17')"
}

Если данных нет — верни пустую строку "". Не добавляй пояснений, только JSON."""


async def _extract_general(section_text: str) -> dict:
    if not section_text.strip():
        return {"tz_general": "", "project_address": "", "sections_count": "", "floors_count": ""}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки общую информацию из этого раздела ТЗ:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
    )
    if not result:
        return {"tz_general": section_text[:500], "project_address": "", "sections_count": "", "floors_count": ""}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {
            "tz_general": _safe_str(parsed.get("tz_general")),
            "project_address": _safe_str(parsed.get("project_address")),
            "sections_count": _safe_str(parsed.get("sections_count")),
            "floors_count": _safe_str(parsed.get("floors_count")),
        }
    except json.JSONDecodeError:
        logger.error(f"General extract: invalid JSON: {result[:200]}")
        return {"tz_general": section_text[:500], "project_address": "", "sections_count": "", "floors_count": ""}


# ─── Phase 2b: extract water / sewer / fire info ──────────────────

WATER_SEWER_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста раздела технического задания выдели информацию о водоснабжении, водоотведении и пожаротушении.

Верни JSON:
{
  "tz_water_supply": "текст из ТЗ по разделу водоснабжения (ХВС, ГВС) — скопируй дословно",
  "tz_sewerage": "текст из ТЗ по разделу водоотведения и канализации",
  "tz_fire_fighting": "текст из ТЗ по разделу пожаротушения",
  "pipeline_data": {
    "water_supply": {
      "mains": { "material": "материал магистралей ХВС/ГВС", "diameter": "диаметры магистралей", "insulation": "изоляция магистралей" },
      "risers": { "material": "материал стояков", "diameter": "диаметры стояков", "insulation": "изоляция стояков" },
      "distribution": { "material": "материал разводки", "diameter": "диаметры разводки", "insulation": "изоляция разводки" }
    },
    "sewerage": {
      "mains": { "material": "...", "diameter": "...", "insulation": "..." },
      "risers": { "material": "...", "diameter": "...", "insulation": "..." },
      "distribution": { "material": "...", "diameter": "...", "insulation": "..." }
    },
    "fire_fighting": {
      "mains": { "material": "...", "diameter": "...", "insulation": "..." },
      "risers": { "material": "...", "diameter": "...", "insulation": "..." },
      "distribution": { "material": "...", "diameter": "...", "insulation": "..." }
    }
  }
}

Для pipeline_data: заполни ТОЛЬКО то, что явно написано. Если про участок ничего не сказано — оставь пустую строку.
tz_water_supply, tz_sewerage, tz_fire_fighting — строки (копия текста из ТЗ). Не добавляй пояснений, только JSON."""


_EMPTY_PIPELINE = {
    "water_supply": {"mains": {}, "risers": {}, "distribution": {}},
    "sewerage": {"mains": {}, "risers": {}, "distribution": {}},
    "fire_fighting": {"mains": {}, "risers": {}, "distribution": {}},
}


async def _extract_water_sewer(section_text: str) -> dict:
    if not section_text.strip():
        return {"tz_water_supply": "", "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": WATER_SEWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки информацию о водоснабжении, водоотведении и пожаротушении:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
    )
    if not result:
        return {"tz_water_supply": section_text[:500], "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        pd = parsed.get("pipeline_data")
        if not isinstance(pd, dict):
            pd = _EMPTY_PIPELINE
        return {
            "tz_water_supply": _safe_str(parsed.get("tz_water_supply")),
            "tz_sewerage": _safe_str(parsed.get("tz_sewerage")),
            "tz_fire_fighting": _safe_str(parsed.get("tz_fire_fighting")),
            "pipeline_data": pd,
        }
    except json.JSONDecodeError:
        logger.error(f"Water/sewer extract: invalid JSON: {result[:200]}")
        return {"tz_water_supply": section_text[:500], "tz_sewerage": "", "tz_fire_fighting": "", "pipeline_data": _EMPTY_PIPELINE}


# ─── Phase 2c: extract BIM requirements ───────────────────────────

BIM_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста раздела технического задания выдели требования к BIM-модели.

Верни JSON:
{
  "bim_requirements": "требования к BIM-модели: уровень детализации LOD, форматы файлов, классификатор, требования к параметрам, EIR, BEP и т.д."
}

Поле bim_requirements — строка. Если данных нет — пустая строка "". Не добавляй пояснений, только JSON."""


async def _extract_bim(section_text: str) -> dict:
    if not section_text.strip():
        return {"bim_requirements": ""}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": BIM_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки BIM-требования из этого раздела:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
    )
    if not result:
        return {"bim_requirements": section_text[:500]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {"bim_requirements": _safe_str(parsed.get("bim_requirements"))}
    except json.JSONDecodeError:
        logger.error(f"BIM extract: invalid JSON: {result[:200]}")
        return {"bim_requirements": section_text[:500]}


# ─── Phase 2d: extract other systems ──────────────────────────────

OTHER_SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста технического задания выдели информацию о прочих инженерных системах.

Верни JSON:
{
  "tz_other": "все прочие инженерные решения кроме водоснабжения, водоотведения, пожаротушения и BIM (отопление, вентиляция, кондиционирование, электрика, слаботочные системы, автоматизация и т.д.)"
}

Поле tz_other — строка. Если данных нет — пустая строка "". Не добавляй пояснений, только JSON."""


async def _extract_other(section_text: str) -> dict:
    if not section_text.strip():
        return {"tz_other": ""}

    result = await ai_chat(
        messages=[
            {"role": "system", "content": OTHER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Извлеки информацию о прочих инженерных системах:\n\n{section_text[:24000]}"},
        ],
        temperature=0,
    )
    if not result:
        return {"tz_other": section_text[:500]}

    cleaned = _clean_json(result)
    try:
        parsed = json.loads(cleaned)
        return {"tz_other": _safe_str(parsed.get("tz_other"))}
    except json.JSONDecodeError:
        logger.error(f"Other extract: invalid JSON: {result[:200]}")
        return {"tz_other": section_text[:500]}


# ─── Helpers ──────────────────────────────────────────────────────

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
    "tz_general": "",
    "tz_water_supply": "",
    "tz_sewerage": "",
    "tz_fire_fighting": "",
    "tz_other": "",
    "project_address": "",
    "sections_count": "",
    "floors_count": "",
    "bim_requirements": "",
    "pipeline_data": _EMPTY_PIPELINE,
}


async def parse_tz_document(text: str) -> dict:
    if not text.strip():
        return dict(_DEFAULT_RETURN)

    logger.info("Phase 1: splitting document into sections...")
    sections = await _split_sections(text)

    # Fire all extraction phases in parallel
    logger.info("Phase 2: extracting info from each section...")
    general_task = _extract_general(sections.get("general_section", ""))
    ws_task = _extract_water_sewer(sections.get("water_sewer_section", ""))
    bim_task = _extract_bim(sections.get("bim_section", ""))
    other_task = _extract_other(sections.get("other_section", ""))
    # Also send general section to extract other (fallback for tz_other)
    other_fallback = _extract_other(sections.get("general_section", ""))

    general, ws, bim, other, other_fb = await asyncio.gather(
        general_task, ws_task, bim_task, other_task, other_fallback,
    )

    result = dict(_DEFAULT_RETURN)
    result.update(general)
    result.update(ws)
    result.update(bim)
    # Prefer dedicated other_section, fall back to general_section
    result["tz_other"] = other.get("tz_other") or other_fb.get("tz_other") or ""

    # Sanitize pipeline_data
    pd = result.get("pipeline_data", _EMPTY_PIPELINE)
    if not isinstance(pd, dict):
        pd = _EMPTY_PIPELINE
    for sys_name in ("water_supply", "sewerage", "fire_fighting"):
        sys_data = pd.get(sys_name, {})
        if not isinstance(sys_data, dict):
            pd[sys_name] = {"mains": {}, "risers": {}, "distribution": {}}
        for part in ("mains", "risers", "distribution"):
            p = sys_data.get(part, {})
            if not isinstance(p, dict):
                pd[sys_name][part] = {}
    result["pipeline_data"] = pd

    logger.info(f"TZ parsing complete: general={len(result['tz_general'])} chars, "
                f"water={len(result['tz_water_supply'])} chars, "
                f"sewer={len(result['tz_sewerage'])} chars, "
                f"bim={len(result['bim_requirements'])} chars")

    return result
