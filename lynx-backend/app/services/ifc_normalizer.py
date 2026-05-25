import ifcopenshell
from ifcopenshell.util import element as el_util
from ifcopenshell.util import unit as unit_util
from typing import Optional
from datetime import datetime
from pathlib import Path
import logging

from ..db.models import ModelVersion, Element, async_session

logger = logging.getLogger(__name__)

MVP_CLASSES = [
    "IfcPipeSegment",
    "IfcPipeFitting",
    "IfcValve",
    "IfcFlowTerminal",
]


def extract_diameter_from_psets(psets: dict) -> Optional[float]:
    """Извлечение диаметра из pset свойств."""
    search_keys = [
        "NominalDiameter",
        "Reference",
        "Diameter",
        "Size",
        "DN",
        "BRU_Габарит элемента",
        "Bru_Габарит элемента",
    ]
    
    for pset_name, pset_data in psets.items():
        if not isinstance(pset_data, dict):
            continue
        for key in search_keys:
            if key in pset_data:
                val = pset_data[key]
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
    
    return None


def normalize_element(e, model, scale_to_mm: float = 1000.0) -> dict:
    """Нормализация одного элемента."""
    psets = el_util.get_psets(e)
    
    diameter_val = extract_diameter_from_psets(psets)
    diameter_mm = None
    if diameter_val is not None:
        diameter_mm = diameter_val * scale_to_mm
    
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
                elements.append(normalized)
        
        async with async_session() as session:
            for el_data in elements:
                el = Element(
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
                    raw_psets_jsonb=el_data["raw_psets"],
                    normalized_jsonb=el_data["canonical"],
                )
                session.add(el)
            
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