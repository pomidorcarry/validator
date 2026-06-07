"""Standalone script: extract materials from IFC and update element norm files."""
import sys, json, sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, Path(__file__).parent.as_posix())

import ifcopenshell
from ifcopenshell.util import element as el_util

STORAGE = Path(__file__).parent / "storage"
DB_PATH = Path(__file__).parent / "lynx.db"


def extract_material(ifc_elem) -> str | None:
    try:
        if hasattr(ifc_elem, "HasAssociations") and ifc_elem.HasAssociations:
            for assoc in ifc_elem.HasAssociations:
                if assoc.is_a("IfcRelAssociatesMaterial"):
                    mat = assoc.RelatingMaterial
                    if mat is None:
                        continue
                    if mat.is_a("IfcMaterial"):
                        return mat.Name
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

    try:
        psets = el_util.get_psets(ifc_elem)
        material_keys = ["Material", "Материал", "PipeMaterial", "BRU_Материал", "mat", "MAT"]
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


def main():
    model_id = sys.argv[1] if len(sys.argv) > 1 else ""

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    if model_id:
        cur.execute("SELECT id, model_name, version_number FROM model_versions WHERE id = ?", (model_id,))
    else:
        cur.execute("SELECT id, model_name, version_number FROM model_versions WHERE status = 'processed' ORDER BY created_at DESC LIMIT 1")

    row = cur.fetchone()
    if not row:
        print("No model found")
        return

    vid, vname, vnum = row
    print(f"Processing model: {vname} v{vnum} (id={vid})")

    ifc_path = STORAGE / "raw" / f"{vid}.ifc"
    if not ifc_path.exists():
        print(f"IFC file not found: {ifc_path}")
        return

    model = ifcopenshell.open(str(ifc_path))

    cur.execute("SELECT id, ifc_id FROM elements WHERE model_version_id = ?", (vid,))
    db_elements = cur.fetchall()

    ifc_id_map = {int(eid): uid for uid, eid in db_elements if eid is not None}

    updated = 0
    for ifc_id_int, elem_uid in ifc_id_map.items():
        ifc_elem = model.by_id(ifc_id_int)
        mat = extract_material(ifc_elem)
        if mat:
            norm_path = STORAGE / "elements" / f"{elem_uid}_norm.json"
            if norm_path.exists():
                norm = json.loads(norm_path.read_text("utf-8"))
                norm["material"] = str(mat)
                norm_path.write_text(json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
                updated += 1

    conn.close()
    print(f"Updated material for {updated}/{len(db_elements)} elements")


if __name__ == "__main__":
    main()
