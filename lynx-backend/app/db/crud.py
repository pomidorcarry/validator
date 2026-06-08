from datetime import datetime
from pathlib import Path
from typing import Optional
import json
from sqlalchemy import select, func, delete

from .models_orm import (
    Project, Ruleset, ProjectCategory, ModelVersion, Artifact,
    Element, ElementMeasurement, Issue, AISuggestion, AuditLog,
    Report, TzVersion,
)
from . import base as _base
from .element_storage import load_raw as _load_raw, load_norm as _load_norm


async def create_model_version(
    model_version_id: str,
    project_id: str,
    model_name: str,
    ruleset_id: str,
    filename: str,
) -> dict:
    async with _base.async_session() as session:
        ver_result = await session.execute(
            select(func.max(ModelVersion.version_number))
            .where(ModelVersion.project_id == project_id)
        )
        max_ver = ver_result.scalar()
        if max_ver is None:
            next_ver = 0
        else:
            next_ver = max_ver + 1

        mv = ModelVersion(
            id=model_version_id,
            project_id=project_id,
            model_name=model_name,
            version_number=next_ver,
            ruleset_id=ruleset_id,
            source_filename=filename,
            status="queued",
        )
        session.add(mv)
        await session.commit()
        await session.refresh(mv)
        return {
            "id": mv.id,
            "project_id": mv.project_id,
            "model_name": mv.model_name,
            "version_number": mv.version_number,
            "status": mv.status,
        }


async def get_model_version(model_version_id: str) -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(ModelVersion).where(ModelVersion.id == model_version_id)
        )
        mv = result.scalar_one_or_none()
        if mv:
            return {
                "id": mv.id,
                "project_id": mv.project_id,
                "model_name": mv.model_name,
                "status": mv.status,
                "created_at": mv.created_at.isoformat() if mv.created_at else None,
            }
        return None


async def get_issues(model_version_id: str) -> list:
    async with _base.async_session() as session:
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Issue).where(Issue.model_version_id == model_version_id)
        )
        issues = result.scalars().all()
        # Load element names in batch
        element_ids = [i.element_id for i in issues if i.element_id]
        elements = {}
        if element_ids:
            from sqlalchemy import select as _select
            elem_result = await session.execute(
                _select(Element).where(Element.id.in_(element_ids))
            )
            for e in elem_result.scalars().all():
                elements[e.id] = e.name or ""
        return [
            {
                "id": i.id,
                "global_id": i.global_id,
                "severity": i.severity,
                "rule_key": i.rule_key,
                "message": i.message,
                "status": i.status,
                "element_name": elements.get(i.element_id, ""),
            }
            for i in issues
        ]


async def get_elements(model_version_id: str) -> list:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Element).where(Element.model_version_id == model_version_id)
        )
        elements = result.scalars().all()
        result_list = []
        for e in elements:
            raw = _load_raw(e.id)
            norm = _load_norm(e.id)
            result_list.append({
                "id": e.id,
                "global_id": e.global_id,
                "ifc_class": e.ifc_class,
                "name": e.name,
                "object_type": e.object_type,
                "type_name": e.type_name,
                "storey_name": e.storey_name,
                "system_name": e.system_name,
                "model_group": extract_model_group(raw, norm, e.ifc_class),
                "raw_psets_jsonb": raw,
                "normalized_jsonb": norm,
            })
        return result_list


def extract_model_group(raw_psets, normalized, ifc_class):
    if not raw_psets:
        return ifc_class
    keys = ["Модель", "Model", "Группа модели", "GruppaModeli", "ModelGroup", "Gruppa", "Group"]
    if isinstance(raw_psets, dict):
        for pset_name, props in raw_psets.items():
            if isinstance(props, dict):
                for key, val in props.items():
                    if key in keys and val and str(val).strip():
                        return str(val).strip()
                for key, val in props.items():
                    if key.lower().replace(" ", "") in ["модель", "модели", "model", "группа", "group"] and val and str(val).strip():
                        return str(val).strip()
    return ifc_class


# ── Projects ──

async def create_project(
    project_id: str,
    code: str,
    name: str,
    technical_specification: str = "",
    auto_bind_keywords: str = "",
) -> dict:
    async with _base.async_session() as session:
        p = Project(
            id=project_id,
            code=code,
            name=name,
            technical_specification=technical_specification,
            auto_bind_keywords=auto_bind_keywords,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "technical_specification": p.technical_specification,
            "auto_bind_keywords": p.auto_bind_keywords,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }


async def list_projects() -> list:
    async with _base.async_session() as session:
        projects = (await session.execute(
            select(Project).order_by(Project.created_at.desc())
        )).scalars().all()
        result = []
        for p in projects:
            count_result = await session.execute(
                select(func.count()).select_from(ModelVersion).where(ModelVersion.project_id == p.id)
            )
            result.append({
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "models_count": count_result.scalar() or 0,
                "technical_specification": p.technical_specification,
                "auto_bind_keywords": p.auto_bind_keywords,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })
        return result


async def get_project(project_id: str) -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        count_result = await session.execute(
            select(func.count()).select_from(ModelVersion).where(ModelVersion.project_id == project_id)
        )
        models_count = count_result.scalar() or 0
        return {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "technical_specification": p.technical_specification,
            "auto_bind_keywords": p.auto_bind_keywords,
            "models_count": models_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }


async def update_project(project_id: str, name: str = None, technical_specification: str = None,
                         auto_bind_keywords: str = None) -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        if name is not None:
            p.name = name
        if technical_specification is not None:
            p.technical_specification = technical_specification
        if auto_bind_keywords is not None:
            p.auto_bind_keywords = auto_bind_keywords
        await session.commit()
        await session.refresh(p)
        return {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "technical_specification": p.technical_specification,
            "auto_bind_keywords": p.auto_bind_keywords,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }


async def delete_project(project_id: str) -> bool:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return False
        await session.delete(p)
        await session.commit()
        return True


# ── Model helpers ──

async def list_all_models(project_id: Optional[str] = None) -> list:
    async with _base.async_session() as session:
        q = select(ModelVersion).order_by(ModelVersion.created_at.desc())
        if project_id:
            q = q.where(ModelVersion.project_id == project_id)
        result = await session.execute(q)
        models = result.scalars().all()
        return [
            {
                "id": m.id,
                "project_id": m.project_id,
                "model_name": m.model_name,
                "version_number": m.version_number,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "processed_at": m.processed_at.isoformat() if m.processed_at else None,
            }
            for m in models
        ]


async def move_model_to_project(model_id: str, target_project_id: str) -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(ModelVersion).where(ModelVersion.id == model_id)
        )
        mv = result.scalar_one_or_none()
        if not mv:
            return None
        mv.project_id = target_project_id
        await session.commit()
        await session.refresh(mv)
        return {
            "id": mv.id,
            "project_id": mv.project_id,
            "model_name": mv.model_name,
            "status": mv.status,
        }


DEFAULT_CATEGORIES = [
    "Труба металлическая",
    "Труба полимерная",
    "Металлическая соединительная деталь трубы",
    "Полимерная соединительная деталь трубы",
    "Арматура труб",
    "Оборудование",
    "Сантехнический прибор",
    "Изоляция рулонная",
    "Изоляция трубчатая",
    "Невалидируемое семейство",
]

DEFAULT_COLUMNS = {
    "Труба металлическая": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "PipeType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
        {"label": "Толщина стенки", "keys": ["Толщина стенки", "WallThickness"], "group": "structural", "format": {"decimals": 2}},
        {"label": "Длина, мм", "keys": ["Длина", "Length"], "group": "structural", "format": {"decimals": 1}},
    ],
    "Труба полимерная": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "PipeType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
        {"label": "Толщина стенки", "keys": ["Толщина стенки", "WallThickness"], "group": "structural", "format": {"decimals": 2}},
        {"label": "Длина, мм", "keys": ["Длина", "Length"], "group": "structural", "format": {"decimals": 1}},
    ],
    "Металлическая соединительная деталь трубы": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type"], "group": "structural", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "FittingType", "ValveType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["BRU_Габарит элемента", "Bru_Габарит элемента", "Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
    ],
    "Полимерная соединительная деталь трубы": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type"], "group": "structural", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "FittingType", "ValveType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["BRU_Габарит элемента", "Bru_Габарит элемента", "Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
    ],
    "Арматура труб": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type"], "group": "structural", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "ValveType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["BRU_Габарит элемента", "Bru_Габарит элемента", "Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
    ],
    "Арматура": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type"], "group": "structural", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "ValveType"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["BRU_Габарит элемента", "Bru_Габарит элемента", "Размер", "Size", "DN", "NominalDiameter"], "group": "structural", "format": None},
    ],
    "Оборудование": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "EquipmentType", "Type"], "group": "structural", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type"], "group": "structural", "format": None},
        {"label": "Размер", "keys": ["BRU_Габарит элемента", "Bru_Габарит элемента", "Размер", "Size", "DN"], "group": "structural", "format": None},
    ],
    "Сантехнический прибор": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Вид", "keys": ["BRU_Вид", "Bru_Вид", "Вид", "Type", "FixtureType"], "group": "structural", "format": None},
    ],
    "Изоляция рулонная": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Толщина", "keys": ["Толщина", "Thickness"], "group": "structural", "format": {"decimals": 2}},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type", "InsulationType"], "group": "structural", "format": None},
    ],
    "Изоляция трубчатая": [
        {"label": "Секция", "keys": ["ADSK_Номер секции", "Секция", "Section"], "group": "position", "format": None},
        {"label": "Часть системы", "keys": ["BRU_ЧастьСистемы"], "group": "position", "format": None},
        {"label": "Система", "keys": ["BRU_Система"], "group": "position", "format": None},
        {"label": "Этаж", "keys": ["ADSK_Этаж", "Этаж", "Storey", "Level"], "group": "position", "format": None},
        {"label": "CUBE_Сокращение", "keys": ["CUBE_Сокращение для системы", "Сокращение для системы"], "group": "position", "format": None},
        {"label": "Толщина", "keys": ["Толщина", "Thickness"], "group": "structural", "format": {"decimals": 2}},
        {"label": "Тип", "keys": ["BRU_Тип", "Bru_Тип", "Тип", "Type", "InsulationType"], "group": "structural", "format": None},
    ],
    "Невалидируемое семейство": [],
}


async def list_project_categories(project_id: str) -> list:
    async with _base.async_session() as session:
        result = await session.execute(
            select(ProjectCategory)
            .where(ProjectCategory.project_id == project_id)
            .order_by(ProjectCategory.display_order)
        )
        cats = result.scalars().all()
        if not cats:
            return [
                {"name": name, "order": i, "columns": DEFAULT_COLUMNS.get(name, [])}
                for i, name in enumerate(DEFAULT_CATEGORIES)
            ]

        def _merge_defaults(saved_cols: list, cat_name: str) -> list:
            defaults = DEFAULT_COLUMNS.get(cat_name, [])
            merged = []
            for col in saved_cols:
                if "group" not in col or not col.get("group"):
                    default_group = "structural"
                    for d in defaults:
                        if d["label"] == col.get("label"):
                            default_group = d.get("group", "structural")
                            break
                    col["group"] = default_group
                merged.append(col)
            existing_labels = {c.get("label") for c in merged}
            for d in defaults:
                if d["label"] not in existing_labels:
                    new_col = {
                        "label": d["label"],
                        "group": d.get("group", "structural"),
                    }
                    if "composite" in d:
                        new_col["composite"] = list(d["composite"])
                    else:
                        new_col["keys"] = list(d.get("keys", []))
                    if "format" in d:
                        new_col["format"] = d["format"]
                    merged.append(new_col)
            return merged

        return [
            {
                "name": c.name,
                "order": c.display_order,
                "columns": _merge_defaults(c.columns_config, c.name) if c.columns_config is not None else DEFAULT_COLUMNS.get(c.name, []),
            }
            for c in cats
        ]


async def save_project_categories(project_id: str, categories: list) -> list:
    async with _base.async_session() as session:
        old_result = await session.execute(
            select(ProjectCategory)
            .where(ProjectCategory.project_id == project_id)
            .order_by(ProjectCategory.display_order)
        )
        old_cats = old_result.scalars().all()
        old_names = [c.name for c in old_cats]

        rename_map = {}
        new_entries = []
        for i, cat in enumerate(categories):
            name = cat if isinstance(cat, str) else cat.get("name")
            if not name:
                continue
            columns = cat.get("columns") if isinstance(cat, dict) else None
            new_entries.append({"name": name, "columns": columns})
            if i < len(old_names) and old_names[i] != name:
                rename_map[old_names[i]] = name

        if not old_names:
            for i, entry in enumerate(new_entries):
                if i < len(DEFAULT_CATEGORIES) and DEFAULT_CATEGORIES[i] != entry["name"]:
                    rename_map[DEFAULT_CATEGORIES[i]] = entry["name"]

        await session.execute(
            delete(ProjectCategory).where(ProjectCategory.project_id == project_id)
        )
        for i, entry in enumerate(new_entries):
            session.add(ProjectCategory(
                project_id=project_id,
                name=entry["name"],
                display_order=i,
                columns_config=entry["columns"],
            ))

        if rename_map:
            mv_result = await session.execute(
                select(ModelVersion.id).where(ModelVersion.project_id == project_id)
            )
            mv_ids = [row[0] for row in mv_result.fetchall()]
            if mv_ids:
                elements = (await session.execute(
                    select(Element).where(Element.model_version_id.in_(mv_ids))
                )).scalars().all()

                for el in elements:
                    rp = _load_raw(el.id)
                    if rp and isinstance(rp, dict):
                        changed = False
                        for pset_name, props in rp.items():
                            if isinstance(props, dict):
                                for key, val in list(props.items()):
                                    val_str = str(val).strip() if val else ""
                                    if val_str in rename_map:
                                        props[key] = rename_map[val_str]
                                        changed = True
                        if changed:
                            from .element_storage import save_raw as _save_raw
                            _save_raw(el.id, rp)

        await session.commit()
        return await list_project_categories(project_id)


# ── TZ (Technical Specification) ──

async def get_project_tz(project_id: str) -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None

        from pathlib import Path
        from ..core.config import settings as _cfg
        tz_dir = Path(_cfg.storage_path) / "tz" / project_id
        file_list = []
        if tz_dir.exists():
            from datetime import datetime
            import json as _json
            for f in sorted(tz_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.is_file() and f.suffix.lower() in (".pdf", ".xlsx", ".xls"):
                    display_name = f.stem
                    meta_file = f.with_name(f.name + ".meta")
                    if meta_file.exists():
                        try:
                            meta = _json.loads(meta_file.read_text(encoding="utf-8"))
                            display_name = meta.get("original_name", f.stem)
                        except Exception:
                            pass
                    file_list.append({
                        "stored_name": f.name,
                        "display_name": display_name,
                        "size_bytes": f.stat().st_size,
                        "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })

        result2 = await session.execute(
            select(TzVersion)
            .where(TzVersion.project_id == project_id)
            .order_by(TzVersion.version.desc())
            .limit(1)
        )
        latest_tz = result2.scalar_one_or_none()
        tz_details = dict(latest_tz.data_jsonb) if latest_tz and isinstance(latest_tz.data_jsonb, dict) else {}

        result = {
            "tz_general": p.tz_general or "",
            "tz_water_supply": p.tz_water_supply or "",
            "tz_sewerage": p.tz_sewerage or "",
            "tz_fire_fighting": p.tz_fire_fighting or "",
            "tz_other": p.tz_other or "",
            "project_address": p.project_address or "",
            "sections_count": p.sections_count or "",
            "floors_count": p.floors_count or "",
            "bim_requirements": p.bim_requirements or "",
            "pipeline_data": p.pipeline_data or {},
            "tz_files": file_list,
            "tz_details": tz_details,
        }
        return result


async def update_project_tz(project_id: str, data: dict, source: str = "manual") -> Optional[dict]:
    async with _base.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None

        for field in ("tz_general", "tz_water_supply", "tz_sewerage", "tz_fire_fighting", "tz_other",
                      "tz_file_name", "tz_file_path", "project_address", "sections_count",
                      "floors_count", "bim_requirements"):
            if field in data:
                setattr(p, field, data[field])
        if "tz_file_uploaded_at" in data:
            p.tz_file_uploaded_at = data["tz_file_uploaded_at"]
        if "pipeline_data" in data:
            p.pipeline_data = data["pipeline_data"]

        await session.commit()
        await session.refresh(p)

        version_result = await session.execute(
            select(func.count()).select_from(TzVersion).where(TzVersion.project_id == project_id)
        )
        ver_num = (version_result.scalar() or 0) + 1
        # Store the FULL data dict in data_jsonb (not just summary fields)
        full_data = dict(data) if isinstance(data, dict) else {}
        session.add(TzVersion(
            project_id=project_id,
            version=ver_num,
            data_jsonb=full_data,
            source=source,
            file_name=p.tz_file_name,
        ))
        await session.commit()

        return {
            "tz_general": p.tz_general or "",
            "tz_water_supply": p.tz_water_supply or "",
            "tz_sewerage": p.tz_sewerage or "",
            "tz_fire_fighting": p.tz_fire_fighting or "",
            "tz_other": p.tz_other or "",
            "project_address": p.project_address or "",
            "sections_count": p.sections_count or "",
            "floors_count": p.floors_count or "",
            "bim_requirements": p.bim_requirements or "",
            "pipeline_data": p.pipeline_data or {},
            "tz_file_name": p.tz_file_name,
        }


# ── AI Check Result (file-based storage) ──

from pathlib import Path as _Path
AI_CHECK_DIR: Optional[_Path] = None


def _ensure_ai_check_dir() -> _Path:
    global AI_CHECK_DIR
    if AI_CHECK_DIR is None:
        from ..core.config import settings as _cfg
        AI_CHECK_DIR = _Path(_cfg.storage_path) / "ai_check"
        AI_CHECK_DIR.mkdir(parents=True, exist_ok=True)
    return AI_CHECK_DIR


async def save_ai_check_result(project_id: str, problems: list) -> None:
    import json as _json
    from datetime import datetime
    d = _ensure_ai_check_dir()
    path = d / f"{project_id}.json"
    path.write_text(_json.dumps({
        "project_id": project_id,
        "problems": problems,
        "updated_at": datetime.utcnow().isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


async def get_ai_check_result(project_id: str) -> Optional[dict]:
    import json as _json
    d = _ensure_ai_check_dir()
    path = d / f"{project_id}.json"
    if not path.exists():
        return None
    try:
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


async def get_tz_history(project_id: str) -> list:
    async with _base.async_session() as session:
        result = await session.execute(
            select(TzVersion)
            .where(TzVersion.project_id == project_id)
            .order_by(TzVersion.version.desc())
            .limit(50)
        )
        versions = result.scalars().all()
        return [
            {
                "id": v.id,
                "version": v.version,
                "source": v.source,
                "file_name": v.file_name,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "data": v.data_jsonb,
            }
            for v in versions
        ]
