import ifcopenshell
from ifcopenshell.util import element as el_util
from ifcopenshell.util import unit as unit_util
from typing import Optional
from datetime import datetime
from pathlib import Path
import uuid
import logging

from ..db.models import ModelVersion, Element
from ..db.base import async_session
from ..db.element_storage import save_raw, save_norm

logger = logging.getLogger(__name__)

MVP_CLASSES = [
    "IfcPipeSegment",
    "IfcPipeFitting",
    "IfcValve",
    "IfcFlowTerminal",
    "IfcCovering",
    "IfcBuildingElementProxy",
]


def extract_diameter_from_psets(psets: dict) -> tuple[Optional[float], bool]:
    """Извлечение диаметра из pset свойств.
    Returns (numeric_diameter_mm_or_None, is_any_size_filled)."""
    search_keys = [
        "NominalDiameter",
        "Diameter",
        "DN",
        "BRU_Габарит элемента",
        "Bru_Габарит элемента",
        "DN_OutsideDiameter",
        "OD",
    ]
    
    has_any_value = False
    for pset_name, pset_data in psets.items():
        if not isinstance(pset_data, dict):
            continue
        for key in search_keys:
            if key in pset_data:
                val = pset_data[key]
                if val is not None and str(val).strip():
                    has_any_value = True
                    try:
                        return float(val), True
                    except (ValueError, TypeError):
                        pass
    
    return None, has_any_value


def extract_material_from_element(e) -> Optional[str]:
    """Извлечение материала из IfcRelAssociatesMaterial или Pset-свойств."""
    # 1. Try IfcRelAssociatesMaterial → IfcMaterial
    try:
        if hasattr(e, "HasAssociations") and e.HasAssociations:
            for assoc in e.HasAssociations:
                if assoc.is_a("IfcRelAssociatesMaterial"):
                    mat = assoc.RelatingMaterial
                    if mat is None:
                        continue
                    if mat.is_a("IfcMaterial"):
                        return mat.Name
                    # IfcMaterialConstituentSet, IfcMaterialLayerSetUsage, etc.
                    if hasattr(mat, "ForLayerSet") and mat.ForLayerSet:
                        for layer in mat.ForLayerSet.MaterialLayers:
                            if layer.Material:
                                return layer.Material.Name
                    if hasattr(mat, "MaterialConstituents") and mat.MaterialConstituents:
                        for c in mat.MaterialConstituents:
                            if c.Material:
                                return c.Material.Name
    except Exception:
        pass

    # 2. Fallback: scan psets for material keys
    try:
        psets = el_util.get_psets(e)
        material_keys = ["Material", "Материал", "PipeMaterial", "BRU_Материал"]
        for pset_name, pset_data in psets.items():
            if not isinstance(pset_data, dict):
                continue
            for key in material_keys:
                val = pset_data.get(key)
                if val and str(val).strip() and str(val).strip().lower() not in ("", "-", "не указан", "undefined"):
                    return str(val).strip()
    except Exception:
        pass

    return None


def normalize_element(e, model, scale_to_mm: float = 1000.0) -> dict:
    """Нормализация одного элемента."""
    psets = el_util.get_psets(e)
    
    diameter_val, size_filled = extract_diameter_from_psets(psets)
    diameter_mm = None
    if diameter_val is not None:
        diameter_mm = diameter_val * scale_to_mm
    
    material = extract_material_from_element(e)
    
    storey = None
    # 1. Try spatial containment (standard IFC way)
    try:
        if hasattr(e, "ContainedInSpatialStructure") and e.ContainedInSpatialStructure:
            rels = e.ContainedInSpatialStructure
            if len(rels) > 0:
                rel = rels[0] if isinstance(rels, (list, tuple)) else rels
                if hasattr(rel, "RelatingStructure") and rel.RelatingStructure:
                    storey = rel.RelatingStructure.Name
    except:
        pass
    # 2. Fallback to ADSK_Этаж and common keys from psets
    if not storey and psets:
        for pset_name, props in psets.items():
            if isinstance(props, dict):
                for key in ["ADSK_Этаж", "Этаж", "Storey", "Level"]:
                    val = props.get(key)
                    if val and str(val).strip():
                        storey = str(val).strip()
                        break
            if storey:
                break
    
    system = None
    try:
        if e.ProvidesAssociations:
            for assoc in e.ProvidesAssociations:
                if assoc.is_a("IfcRelAssignsToGroup"):
                    if assoc.RelatingGroup and assoc.RelatingGroup.is_a("IfcSystem"):
                        system = assoc.RelatingGroup.Name
    except:
        pass
    # 2. Fallback to BRU_Система and common keys from psets
    if not system and psets:
        for pset_name, props in psets.items():
            if isinstance(props, dict):
                for key in ["BRU_Система", "Bru_Система", "Система", "System"]:
                    val = props.get(key)
                    if val and str(val).strip():
                        system = str(val).strip()
                        break
            if system:
                break
    
    return {
        "global_id": e.GlobalId,
        "ifc_id": e.id(),
        "ifc_class": e.is_a(),
        "name": getattr(e, "Name", None),
        "object_type": getattr(e, "ObjectType", None),
        "predefined_type": getattr(e, "PredefinedType", None),
        "type_name": getattr(e, "ObjectType", None),
        "storey_name": storey,
        "system_name": system,
        "raw_psets": psets,
        "canonical": {
            "diameter_mm": diameter_mm,
            "size_filled": size_filled,
            "material": material,
        },
}


async def process_model_version(model_version_id: str):
    """Обработка версии модели - нормализация и проверка."""
    from ..core.config import settings
    from sqlalchemy import select, update
    
    logger.info(f"Starting processing for {model_version_id}")
    
    storage_path = Path(settings.storage_path)
    ifc_path = storage_path / "raw" / f"{model_version_id}.ifc"
    
    if not ifc_path.exists():
        logger.error(f"IFC file not found: {ifc_path}")
        async with async_session() as session:
            await session.execute(
                update(ModelVersion)
                .where(ModelVersion.id == model_version_id)
                .values(status="failed", error_message="IFC file not found")
            )
            await session.commit()
        return
    
    # Load Revit element ID map (GlobalId → Revit ElementId integer)
    revit_id_map = {}
    revit_map_path = storage_path / "raw" / f"{model_version_id}.revit_ids.json"
    if revit_map_path.exists():
        try:
            import json
            with open(revit_map_path, "r", encoding="utf-8") as f:
                revit_id_map = json.load(f)
            if isinstance(revit_id_map, dict):
                # Ensure all values are int
                revit_id_map = {k: int(v) for k, v in revit_id_map.items()}
            logger.info(f"Loaded Revit ID map with {len(revit_id_map)} entries")
        except Exception as e:
            logger.warning(f"Failed to load Revit ID map: {e}")
            revit_id_map = {}
    
    try:
        model = ifcopenshell.open(str(ifc_path))
        
        schema = model.schema
        logger.info(f"IFC schema: {schema}")
        
        scale_to_mm = unit_util.calculate_unit_scale(model, "LENGTHUNIT") * 1000.0
        
        elements = []
        for ifc_class in MVP_CLASSES:
            elements_in_class = model.by_type(ifc_class)
            logger.info(f"Found {len(elements_in_class)} elements of type {ifc_class}")
            for e in elements_in_class:
                normalized = normalize_element(e, model, scale_to_mm)
                gid = normalized.get("global_id", "")
                revit_el_id = None
                if gid and gid in revit_id_map:
                    revit_el_id = revit_id_map[gid]
                    normalized["revit_element_id"] = revit_el_id
                elements.append(normalized)
        
        async with async_session() as session:
            for el_data in elements:
                el_id = str(uuid.uuid4())
                canonical = el_data.get("canonical", {})
                if el_data.get("revit_element_id") is not None:
                    canonical["revit_element_id"] = el_data["revit_element_id"]
                el = Element(
                    id=el_id,
                    model_version_id=model_version_id,
                    global_id=el_data["global_id"],
                    ifc_id=el_data["ifc_id"],
                    ifc_class=el_data["ifc_class"],
                    name=el_data["name"],
                    object_type=el_data["object_type"],
                    predefined_type=el_data["predefined_type"],
                    type_name=el_data["type_name"],
                    storey_name=el_data["storey_name"],
                    system_name=el_data["system_name"],
                    raw_psets_jsonb={},
                    normalized_jsonb=canonical,
                )
                session.add(el)
                save_raw(el_id, el_data["raw_psets"])
                save_norm(el_id, canonical)
            
            await session.execute(
                update(ModelVersion)
                .where(ModelVersion.id == model_version_id)
                .values(
                    status="processed",
                    processed_at=datetime.utcnow(),
                    ifc_schema=schema,
                )
            )
            await session.commit()
        
        logger.info(f"Processed model {model_version_id}: {len(elements)} elements")
        
        from .rule_engine import run_rules
        issues_count = await run_rules(model_version_id)
        logger.info(f"Created {issues_count} issues")
        
        from .xkt_converter import generate_xkt
        xkt_success = await generate_xkt(model_version_id)
        if xkt_success:
            logger.info(f"XKT generated for {model_version_id}")
        
        logger.info(f"Completed processing for {model_version_id}")
        
    except Exception as e:
        logger.error(f"Error processing {model_version_id}: {str(e)}")
        async with async_session() as session:
            await session.execute(
                update(ModelVersion)
                .where(ModelVersion.id == model_version_id)
                .values(status="failed", error_message=str(e))
            )
            await session.commit()


async def repair_materials(model_version_id: str) -> int:
    """Извлечение материалов для уже обработанной модели и обновление norm-файлов."""
    from ..core.config import settings
    from ..db.element_storage import load_norm, save_norm
    
    storage_path = Path(settings.storage_path)
    ifc_path = storage_path / "raw" / f"{model_version_id}.ifc"
    if not ifc_path.exists():
        logger.warning(f"IFC file not found for material repair: {ifc_path}")
        return 0
    
    try:
        model = ifcopenshell.open(str(ifc_path))
    except Exception as e:
        logger.error(f"Cannot open IFC for material repair: {e}")
        return 0
    
    from ..db.models import Element as ElementORM
    from sqlalchemy import select
    
    async with async_session() as session:
        result = await session.execute(
            select(ElementORM).where(ElementORM.model_version_id == model_version_id)
        )
        db_elements = result.scalars().all()
    
    if not db_elements:
        logger.warning(f"No elements found for model {model_version_id}")
        return 0
    
    # Build IFC ID → element ID map
    ifc_id_map = {}
    for el in db_elements:
        if el.ifc_id is not None:
            ifc_id_map[el.ifc_id] = el.id
    
    # Extract materials from IFC
    found_material_count = 0
    for ifc_id, el_id in ifc_id_map.items():
        ifc_el = model.by_id(ifc_id) if ifc_id else None
        if ifc_el is None:
            continue
        mat = extract_material_from_element(ifc_el)
        if mat:
            norm = load_norm(el_id)
            norm["material"] = str(mat)
            save_norm(el_id, norm)
            found_material_count += 1
    
    logger.info(f"Material repair for {model_version_id}: updated {found_material_count}/{len(db_elements)} elements")
    return found_material_count