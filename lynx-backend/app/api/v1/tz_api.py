from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from pathlib import Path

from ...core.config import settings

router = APIRouter(tags=["tz"])


@router.get("/projects/{project_id}/tz")
async def get_project_tz(project_id: str):
    from ...db.models import get_project_tz as _get_tz

    tz = await _get_tz(project_id)
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@router.put("/projects/{project_id}/tz")
async def update_project_tz(project_id: str, data: dict = Body(...)):
    from ...db.models import update_project_tz as _update_tz

    tz = await _update_tz(project_id, data, source="manual")
    if tz is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tz


@router.post("/projects/{project_id}/tz/upload", status_code=201)
async def upload_tz_file(project_id: str, file: UploadFile = File(...)):
    allowed = (".pdf", ".xlsx", ".xls")
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and Excel files allowed")

    from datetime import datetime
    import uuid

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    tz_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{ts}_{uuid.uuid4().hex[:8]}{ext}"
    dst = tz_dir / stored_name

    with dst.open("wb") as f:
        content = await file.read()
        f.write(content)

    import json as _json
    meta_file = dst.with_name(dst.name + ".meta")
    meta_file.write_text(_json.dumps({"original_name": file.filename}))

    now = datetime.utcnow()
    return {
        "file_name": file.filename,
        "stored_name": stored_name,
        "file_path": str(dst),
        "uploaded_at": now.isoformat(),
    }


@router.get("/projects/{project_id}/tz/files")
async def list_tz_files(project_id: str):
    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls"):
            from datetime import datetime
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            display_name = f.stem
            meta_file = f.with_name(f.name + ".meta")
            if meta_file.exists():
                try:
                    import json as _json
                    meta = _json.loads(meta_file.read_text(encoding="utf-8"))
                    display_name = meta.get("original_name", f.stem)
                except Exception:
                    pass
            files.append({
                "stored_name": f.name,
                "display_name": display_name,
                "size_bytes": f.stat().st_size,
                "uploaded_at": mtime.isoformat(),
            })
    return {"files": files}


@router.delete("/projects/{project_id}/tz/files")
async def delete_tz_file(project_id: str, filename: str = ""):
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    file_path = tz_dir / filename
    meta_path = tz_dir / (filename + ".meta")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    if meta_path.exists():
        meta_path.unlink()

    return {"deleted": filename}


# ─── Demo mode ─────────────────────────────────────────────────────
# When True, /tz/parse returns a hardcoded demo response instead of calling AI.
DEMO_MODE = True


def _demo_tz_response() -> dict:
    return {
        # ── General ──
        "project_name": "MLB 01-04",
        "project_type": "жилой дом с коммерческими помещениями",
        "project_purpose": "жилой дом с подземной автостоянкой, коммерческими помещениями на 1-м этаже, КУИ",
        "project_address": "Город Москва, класс продукта В",
        "sections_count": "не указано (см. альбом концепции)",
        "floors_count": "до 32 этажей (по зонам стояков: до 75 м / до 100 м)",
        "underground_floors": "1 (техподполье/подвал + автостоянка)",
        "building_height": "",
        "total_area": "",
        "construction_year": "",
        "structural_system": "монолитный ж/б каркас",
        "tz_general": "1.1 Требования к объемно-планировочным решениям:\n"
            "Жилая часть: количество и типология квартир — согласно утвержденной Заказчиком квартирографии.\n"
            "Высота подвала — 3,67 м; первого этажа — 4,2 м; типового этажа — 3,0 м; последнего жилого — 3,02 м; техпомещения — 2,55 м; техэтажа с надстройкой — 3,02 м.\n"
            "Коммерческие помещения: витражное остекление, минимум инженерных сетей в центрах, отделочные работы после ввода.\n"
            "Техподполье: свободные зоны — под кладовые. Исключить транзиты инженерных систем через кладовые.\n"
            "Автостоянка: одноуровневая, закрытая, неотапливаемая. Высота 2,7 м. Ширина проезда 5,0 м.\n"
            "1.2 Площади и расположение инженерных помещений: ИТП, Насосная, Электрощитовые, Венткамеры.\n"
            "1.5 Шумоизоляция — нормативный уровень, виброразвязка оборудования.\n"
            "1.7 Мусороудаление — без мусоропроводов, ТКО на специализированных площадках.\n"
            "1.8 Доп. функции автостоянки: скрытая прокладка проводки к м.местам, резерв 5% под зарядные станции (5 кВт).\n"
            "1.9 Система доступа МГН — согласно СП 59.13330.\n"
            "1.10 Надбавку к проектной длине на отходы не предусматривать.",
        # ── Water / Sewer / Fire ──
        "tz_water_supply": "Системы водоснабжения:\n"
            "Система холодного водоснабжения коллекторная однозонная. Магистраль из труб ПП PN20 неармированных "
            "и ПП PN25 армированных стекловолокном в тепловой изоляции из вспененного каучука толщиной 13 мм для ХВС. "
            "Прокладка трубопроводов открытая, крепление сантехническими хомутами. "
            "Стояк из труб ПП PN25 до 28м DN50 (1-9 эт.), до 50м DN63 (1-16 эт.), до 75м DN50 (1-12/13-24 2 зоны). "
            "Система холодного водоснабжения коллекторная двухзонная. "
            "Система горячего водоснабжения коллекторная однозонная/двухзонная. "
            "Стояки ГВС ПП PN25: до 28м DN50 + цирк. DN25; до 50м DN63 + цирк. DN32; до 75м DN50 + цирк. DN32. "
            "Магистрали из труб ПП PN25 с изоляцией 19 мм для ГВС. "
            "Разводка из труб СП (сшитый полиэтилен) PN10, изоляция 9 мм. "
            "Насосная станция питьевого водоснабжения: Wilo, Grundfos. "
            "Обвязка из стальной нержавеющей трубы ГОСТ 9941-81, диаметры 22-220 мм, изоляция 13 мм. "
            "Коллекторы водоснабжения заводского изготовления: АкваСмарт, Пульсар. "
            "Индивидуальные узлы учета. Производители арматуры: Danfoss, Valtec, ADL, Naval, Broen Ballomax, Bugatti.",
        "tz_sewerage": "Системы водоотведения:\n"
            "Система бытовой канализации до 75м: магистраль из труб ПП раструбных, "
            "выпуски Ø110 НПВХ. Стояк ПП DN110 (1-24 эт.). "
            "Раздельные системы для жилья и коммерческих помещений. "
            "Система бытовой канализации свыше 75м: магистраль из труб чугунных безраструбных SML, "
            "выпуски НПВХ Ø110, стояк ПП DN125 (1-32 эт.). "
            "Система производственной канализации: отдельная для помещений общественного питания. "
            "Система ливневой канализации: ПЭ/ПП DN50/DN110, изоляция вспененный каучук 9мм. "
            "Оконечное сантехническое оборудование КУИ. "
            "Обозначения систем: К1, К1н, К1.1, К2, К2.1, К3, К13н, К14, К15, К15нп.",
        "tz_fire_fighting": "Системы пожаротушения:\n"
            "Система внутреннего пожарного водопровода однозонная: стояк DN57 (1-16 эт.), "
            "магистраль из труб стальных неоцинкованных водогазопроводных ГОСТ 3262-75 "
            "(15х2,8; 20х2,8; 25х3,2; 32х3,2; 40х3,5) и электросварных ГОСТ 10704-91 "
            "(57х3,5; 76х3,5; 89х4,0; 108х4,0; 133х4,5; 159х4,5; 219х4,5). "
            "Система ВПВ двухзонная: DN57 (1-16 / 1-24 эт.). "
            "Система ВПВ двухзонная с АПТ: DN89 (1-16 / 1-32 эт.). "
            "Система АПТ паркинг: спринклерная кольцевая воздушная. "
            "Оросители: СВУ, ДВУ (Спецавтоматика, Бийск). "
            "Насосные станции пожаротушения: Wilo, Grundfos. "
            "Шкафы пожарные: НПО Пульс, модели ШПК-Пульс. "
            "Грунтовка трубопроводов. "
            "Обозначения систем: В2.1 (Жилье), В2.2 (Жилье), В2.3 (Ритейл), В2.4 (Паркинг), "
            "В2.5 (Паркинг_АПТ), В2.6 (Сухотруб), В2.7 (Кладовые_АПТ).",
        # ── BIM ──
        "bim_requirements": "", "lod_requirements": "", "file_formats": "",
        "classification": "", "software_versions": "", "eir_requirements": "",
        "bep_requirements": "", "cde_platform": "", "parameter_requirements": "",
        "naming_conventions": "", "coordination_requirements": "", "quantity_takeoff": "",
        "delivery_milestones": "",
        # ── Equipment detail fields ──
        "tz_equipment": "",
        "pumps_water": "Насосная станция питьевого водоснабжения: Wilo, Grundfos. "
            "Комплексные установки в полной комплектации. Обвязка из нерж. стали ГОСТ 9941-81.",
        "pumps_sewer": "Насосная установка Sololift (для КУИ).",
        "pumps_fire": "Насосные станции пожаротушения: Wilo, Grundfos. Комплексные установки.",
        "boilers": "ИТП — см. подраздел Тепломеханические решения.",
        "heat_exchangers": "ИТП — см. подраздел Тепломеханические решения.",
        "tanks": "",
        "water_treatment": "",
        "valves_general": "Задвижки с обрезиненным клином фланцевые, фильтры сетчатые чугунные, "
            "клапаны обратные чугунные межфланцевые. Краны шаровые латунные муфтовые (DN15-DN32). "
            "Клапаны редукционные, термостатические. Воздухоотводчики автоматические.",
        "control_valves": "Клапаны латунные термостатические DN20-DN25 для коллекторов циркуляции.",
        "measuring_devices": "Счетчики водоснабжения с импульсным выходом: Пульсар. "
            "Манометры класс точности 1,5. Краны трехходовые для манометра DN15.",
        "fittings_data": "Отводы под углами 15°/45°/90° из нержавеющей стали. "
            "Комбинированные муфты ПП-НР. Фитинги прессовые и надвижные для СП.",
        # ── Materials ──
        "tz_materials": "Материалы труб:\n"
            "ХВС: ПП PN20 неармированные, ПП PN25 армированные стекловолокном. "
            "ГВС: ПП PN25 армированные стекловолокном. "
            "Нержавеющая сталь ГОСТ 9941-81 для обвязки насосных и второй зоны. "
            "Разводка по квартирам: сшитый полиэтилен СП PN10. "
            "Пожаротушение: стальные неоцинкованные водогазопроводные ГОСТ 3262-75 "
            "и электросварные ГОСТ 10704-91. "
            "Канализация: ПП раструбные, чугунные безраструбные SML, НПВХ (выпуски), ПЭ (ливневка).",
        "pipe_materials_cold_water": "ПП PN20 неармированные, ПП PN25 армированные стекловолокном, "
            "нержавеющая сталь ГОСТ 9941-81",
        "pipe_materials_hot_water": "ПП PN25 армированные стекловолокном, "
            "нержавеющая сталь ГОСТ 9941-81",
        "pipe_materials_sewer": "ПП раструбные, чугунные безраструбные SML, "
            "НПВХ (выпуски Ø110), ПЭ (ливневка)",
        "pipe_materials_fire": "Стальные неоцинкованные водогазопроводные ГОСТ 3262-75, "
            "электросварные ГОСТ 10704-91",
        "insulation_cold": "Вспененный каучук 13 мм",
        "insulation_hot": "Вспененный каучук 19 мм",
        "insulation_sewer": "Вспененный каучук 9 мм (только ливневая канализация)",
        "insulation_fire": "-",
        "anticorrosion": "Грунтовка трубопроводов пожаротушения. Покраска по дизайн-проекту.",
        "coloring_marking": "Покраска будет выполняться по дизайн-проекту",
        "insulation_standards": "K-Flex, Armacell, Energoflex Super Protect",
        # ── Testing ──
        "tz_testing": "",
        "hydrostatic_pressure": "",
        "flushing": "",
        "leak_test": "",
        "commissioning": "",
        "quality_control": "",
        "testing_standards": "",
        # ── Standards ──
        "tz_standards": "",
        "sp_list": "СП 30.13330.2020, СП 59.13330",
        "snip_list": "",
        "gost_list": "ГОСТ 3262-75, ГОСТ 10704-91, ГОСТ 9941-81, ГОСТ 18599-2001, "
            "ГОСТ 32415-2013, ГОСТ 54475-2011",
        "iso_list": "",
        "other_standards": "",
        # ── Other ──
        "tz_other": "",
        # ── Pipeline data ──
        "pipeline_data": {
            "systems": [
                # ── Water supply ──
                {
                    "id": "sys_demo_01", "category": "water_supply", "name": "В1",
                    "material": "ПП PN20/PN25 + нерж. сталь",
                    "diameters": "DN50, DN63 (стояки); DN15-DN220 (обвязка)",
                    "insulation": "вспененный каучук 13мм",
                    "laying": "открытая, под потолком техподполья",
                },
                {
                    "id": "sys_demo_02", "category": "water_supply", "name": "В1.1",
                    "material": "ПП PN25 (1 зона) / нерж. сталь (2 зона)",
                    "diameters": "DN50 (1-12 эт), DN63 (1-16 эт)",
                    "insulation": "вспененный каучук 13мм",
                    "laying": "открытая",
                },
                {
                    "id": "sys_demo_03", "category": "water_supply", "name": "Т3",
                    "material": "ПП PN25",
                    "diameters": "DN50/DN63 (стояк ГВС); DN25/DN32 (циркуляция)",
                    "insulation": "вспененный каучук 19мм",
                    "laying": "открытая",
                },
                {
                    "id": "sys_demo_04", "category": "water_supply", "name": "Т3.1",
                    "material": "ПП PN25",
                    "diameters": "DN25/DN32",
                    "insulation": "вспененный каучук 19мм",
                    "laying": "открытая",
                },
                {
                    "id": "sys_demo_05", "category": "water_supply", "name": "Т4",
                    "material": "ПП PN25 (1 зона) / нерж. сталь (2 зона)",
                    "diameters": "DN50/DN63 (ГВС); DN32 (циркуляция)",
                    "insulation": "вспененный каучук 13/19мм",
                    "laying": "открытая",
                },
                {
                    "id": "sys_demo_06", "category": "water_supply", "name": "Т4.1",
                    "material": "ПП PN25 / нерж. сталь",
                    "diameters": "DN32",
                    "insulation": "вспененный каучук 19мм",
                    "laying": "открытая",
                },
                # ── Fire fighting ──
                {
                    "id": "sys_demo_07", "category": "fire_fighting", "name": "В2.1",
                    "material": "сталь неоцинк. ГОСТ 3262-75 / ГОСТ 10704-91",
                    "diameters": "DN57 (стояк); DN15-DN219 (магистраль)",
                    "insulation": "-",
                    "laying": "открытая, ниша МОП",
                },
                {
                    "id": "sys_demo_08", "category": "fire_fighting", "name": "В2.2",
                    "material": "сталь неоцинк. ГОСТ 3262-75 / ГОСТ 10704-91",
                    "diameters": "DN57 (2 зоны: 1-16 / 1-24 эт)",
                    "insulation": "-",
                    "laying": "открытая",
                },
                {
                    "id": "sys_demo_09", "category": "fire_fighting", "name": "В2.3",
                    "material": "сталь неоцинк. ГОСТ 3262-75 / ГОСТ 10704-91",
                    "diameters": "DN15-DN219",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_10", "category": "fire_fighting", "name": "В2.4",
                    "material": "сталь неоцинк.",
                    "diameters": "DN15-DN219",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_11", "category": "fire_fighting", "name": "В2.5",
                    "material": "сталь неоцинк. ГОСТ 10704-91",
                    "diameters": "DN89 (стояк 1-32 эт)",
                    "insulation": "-",
                    "laying": "кольцевая воздушная",
                },
                {
                    "id": "sys_demo_12", "category": "fire_fighting", "name": "В2.6",
                    "material": "сталь неоцинк.",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_13", "category": "fire_fighting", "name": "В2.7",
                    "material": "сталь неоцинк.",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
                # ── Sewerage ──
                {
                    "id": "sys_demo_14", "category": "sewerage", "name": "К1",
                    "material": "ПП раструбные / чугун SML",
                    "diameters": "DN110 (стояк до 75м); DN125 (свыше 75м)",
                    "insulation": "-",
                    "laying": "нижняя разводка, под потолком техэтажа",
                },
                {
                    "id": "sys_demo_15", "category": "sewerage", "name": "К1н",
                    "material": "-",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_16", "category": "sewerage", "name": "К1.1",
                    "material": "ПП раструбные",
                    "diameters": "DN110",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_17", "category": "sewerage", "name": "К2",
                    "material": "ПЭ / ПП раструбные",
                    "diameters": "DN50/DN110",
                    "insulation": "вспененный каучук 9мм",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_18", "category": "sewerage", "name": "К2.1",
                    "material": "чугун SML",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_19", "category": "sewerage", "name": "К3",
                    "material": "ПП раструбные",
                    "diameters": "DN110",
                    "insulation": "-",
                    "laying": "отдельный выпуск",
                },
                {
                    "id": "sys_demo_20", "category": "sewerage", "name": "К14",
                    "material": "-",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
                {
                    "id": "sys_demo_21", "category": "sewerage", "name": "К15",
                    "material": "-",
                    "diameters": "-",
                    "insulation": "-",
                    "laying": "-",
                },
            ],
        },
        # ── Raw prompt / GPT for debug ──
        "_raw_prompt": "[DEMO] Система водоснабжения, водоотведения и пожаротушения — 21 система",
        "_raw_gpt": (
            "Демо-ответ: найдена 21 система.\n"
            "Водоснабжение (6): В1, В1.1, Т3, Т3.1, Т4, Т4.1\n"
            "Пожаротушение (7): В2.1–В2.7\n"
            "Водоотведение (8): К1, К1н, К1.1, К2, К2.1, К3, К14, К15\n"
            "Все поля заполнены согласно ТЗ MLB 01-04."
        ),
        "_source_file": "20260605_172825_d417984d.pdf",
    }


@router.post("/projects/{project_id}/tz/parse")
async def parse_tz_file(project_id: str, filename: str = ""):
    if DEMO_MODE:
        return _demo_tz_response()

    from ...services.ai.tz_parser import extract_text_from_file, parse_tz_document

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        raise HTTPException(status_code=400, detail="No TZ files found for this project")

    if filename:
        file_path = tz_dir / filename
    else:
        tz_files = sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        tz_files = [f for f in tz_files if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls")]
        if not tz_files:
            raise HTTPException(status_code=400, detail="No TZ files found")
        file_path = tz_files[0]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="TZ file not found")

    text = extract_text_from_file(str(file_path))
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    parsed = await parse_tz_document(text)
    parsed["_source_file"] = file_path.name
    return parsed


@router.get("/projects/{project_id}/tz/file")
async def download_tz_file(project_id: str, filename: str = ""):
    from fastapi.responses import FileResponse

    tz_dir = Path(settings.storage_path) / "tz" / project_id
    if not tz_dir.exists():
        raise HTTPException(status_code=404, detail="No TZ files found")

    if filename:
        file_path = tz_dir / filename
    else:
        tz_files = sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        tz_files = [f for f in tz_files if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls")]
        if not tz_files:
            raise HTTPException(status_code=404, detail="No TZ files found")
        file_path = tz_files[0]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="TZ file not found")

    display_name = file_path.name[20:] if "_" in file_path.name and len(file_path.name) > 20 else file_path.name
    return FileResponse(path=str(file_path), filename=display_name)


@router.get("/projects/{project_id}/tz/history")
async def get_tz_history(project_id: str):
    from ...db.models import get_tz_history as _get_history

    history = await _get_history(project_id)
    return {"versions": history, "count": len(history)}
