import json
import logging
import os
from pathlib import Path

from .client import ai_chat

SYSTEM_PROMPT = """Ты — инженер BIM-специалист. Из текста технического задания на проектирование инженерных систем выдели 5 разделов:

1. general — общее описание проекта, его цели, состав, требования к BIM-модели в целом
2. water_supply — раздел водоснабжения (холодное и горячее водоснабжение)
3. sewerage — раздел водоотведения и канализации
4. fire_fighting — раздел пожаротушения
5. other — прочие инженерные решения (отопление, вентиляция, электрика, автоматизация и т.д.)

Если какого-то раздела нет в тексте — верни для него пустую строку.
Ответ верни строго в формате JSON:
{"tz_general": "...", "tz_water_supply": "...", "tz_sewerage": "...", "tz_fire_fighting": "...", "tz_other": "..."}
Не добавляй пояснений, только JSON."""


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
        logging.error(f"PDF extraction error: {e}")
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
        logging.error(f"Excel extraction error: {e}")
        return ""


def extract_text_from_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in (".xlsx", ".xls"):
        return extract_text_from_excel(path)
    else:
        return ""


async def parse_tz_document(text: str) -> dict:
    if not text.strip():
        return {
            "tz_general": "",
            "tz_water_supply": "",
            "tz_sewerage": "",
            "tz_fire_fighting": "",
            "tz_other": "",
        }

    result = await ai_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Распарси следующее техническое задание:\n\n{text[:32000]}"},
        ],
        response_format={"type": "json_object"},
    )

    if not result:
        return {
            "tz_general": text[:500],
            "tz_water_supply": "",
            "tz_sewerage": "",
            "tz_fire_fighting": "",
            "tz_other": "",
        }

    try:
        parsed = json.loads(result)
        return {
            "tz_general": parsed.get("tz_general", ""),
            "tz_water_supply": parsed.get("tz_water_supply", ""),
            "tz_sewerage": parsed.get("tz_sewerage", ""),
            "tz_fire_fighting": parsed.get("tz_fire_fighting", ""),
            "tz_other": parsed.get("tz_other", ""),
        }
    except json.JSONDecodeError:
        logging.error(f"AI returned invalid JSON: {result[:200]}")
        return {
            "tz_general": result[:500],
            "tz_water_supply": "",
            "tz_sewerage": "",
            "tz_fire_fighting": "",
            "tz_other": "",
        }
