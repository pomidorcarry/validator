from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .models_orm import Base

engine = None
async_engine = None
async_session = None


async def init_db():
    global engine, async_engine, async_session
    from ..core.config import settings

    async_engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        def _migrate(conn):
            import sqlalchemy as sa
            import json as _json
            insp = sa.inspect(conn)
            cats_cols = [c["name"] for c in insp.get_columns("project_categories")]
            if "columns_config" not in cats_cols:
                conn.execute(sa.text("ALTER TABLE project_categories ADD COLUMN columns_config JSON"))
            proj_cols = [c["name"] for c in insp.get_columns("projects")]
            tz_cols = ["tz_file_name", "tz_file_path", "tz_file_uploaded_at",
                        "tz_general", "tz_water_supply", "tz_sewerage",
                        "tz_fire_fighting", "tz_other"]
            for col in tz_cols:
                if col not in proj_cols:
                    conn.execute(sa.text(f"ALTER TABLE projects ADD COLUMN {col} TEXT"))
            proj_cols2 = [c["name"] for c in insp.get_columns("projects")]
            for col in ("project_address", "sections_count", "floors_count", "bim_requirements"):
                if col not in proj_cols2:
                    conn.execute(sa.text(f"ALTER TABLE projects ADD COLUMN {col} TEXT"))
            if "pipeline_data" not in proj_cols2:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN pipeline_data JSON"))
            proj_cols3 = [c["name"] for c in insp.get_columns("projects")]
            if "other_docs_summary" not in proj_cols3:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN other_docs_summary TEXT"))
            mv_cols = [c["name"] for c in insp.get_columns("model_versions")]
            if "version_number" not in mv_cols:
                conn.execute(sa.text("ALTER TABLE model_versions ADD COLUMN version_number INTEGER"))
            null_rows = conn.execute(
                sa.text("SELECT id, project_id, created_at FROM model_versions WHERE version_number IS NULL ORDER BY project_id, created_at")
            ).fetchall()
            if null_rows:
                project_counters = {}
                for row in null_rows:
                    pid = row[1]
                    if pid not in project_counters:
                        project_counters[pid] = 0
                    ver = project_counters[pid]
                    conn.execute(
                        sa.text("UPDATE model_versions SET version_number = :ver WHERE id = :id"),
                        {"ver": ver, "id": row[0]}
                    )
                    project_counters[pid] = ver + 1
            _size_keys = ["NominalDiameter", "Diameter", "DN",
                          "BRU_Габарит элемента", "Bru_Габарит элемента",
                          "Размер", "Габарит", "DN_OutsideDiameter", "OD"]
            rows = conn.execute(
                sa.text("SELECT e.id, e.normalized_jsonb, e.raw_psets_jsonb FROM elements e WHERE e.normalized_jsonb IS NOT NULL")
            ).fetchall()
            for eid, nb, rp in rows:
                try:
                    nb_parsed = _json.loads(nb) if isinstance(nb, str) else nb
                except Exception:
                    nb_parsed = nb
                if not isinstance(nb_parsed, dict):
                    continue
                nb_parsed.pop("size_filled", None)
                sf = False
                if rp:
                    try:
                        rp_parsed = _json.loads(rp) if isinstance(rp, str) else rp
                    except Exception:
                        rp_parsed = rp
                    if isinstance(rp_parsed, dict):
                        for _pn, _props in rp_parsed.items():
                            if isinstance(_props, dict):
                                for _k in _size_keys:
                                    if _k in _props:
                                        _v = _props[_k]
                                        if _v is not None and str(_v).strip():
                                            sf = True
                                            break
                            if sf:
                                break
                if sf:
                    nb_parsed["size_filled"] = True
                    conn.execute(
                        sa.text("UPDATE elements SET normalized_jsonb = :nb WHERE id = :id"),
                        {"nb": _json.dumps(nb_parsed, ensure_ascii=False), "id": eid}
                    )
            _diam_keys = ["NominalDiameter", "Diameter", "DN",
                          "BRU_Габарит элемента", "Bru_Габарит элемента",
                          "DN_OutsideDiameter", "OD"]
            rows = conn.execute(
                sa.text("SELECT e.id, e.normalized_jsonb, e.raw_psets_jsonb FROM elements e WHERE e.raw_psets_jsonb IS NOT NULL")
            ).fetchall()
            for eid, nb, rp in rows:
                if rp is None:
                    continue
                try:
                    nb_parsed = _json.loads(nb) if isinstance(nb, str) else nb
                except Exception:
                    continue
                if not isinstance(nb_parsed, dict):
                    continue
                if nb_parsed.get("diameter_mm") is not None:
                    continue
                try:
                    rp_parsed = _json.loads(rp) if isinstance(rp, str) else rp
                except Exception:
                    continue
                if not isinstance(rp_parsed, dict):
                    continue
                for _pn, _props in rp_parsed.items():
                    if isinstance(_props, dict):
                        for _k in _diam_keys:
                            _v = _props.get(_k)
                            if _v is not None and str(_v).strip():
                                try:
                                    fv = float(_v)
                                    nb_parsed["diameter_mm"] = fv
                                    conn.execute(
                                        sa.text("UPDATE elements SET normalized_jsonb = :nb WHERE id = :id"),
                                        {"nb": _json.dumps(nb_parsed, ensure_ascii=False), "id": eid}
                                    )
                                except (ValueError, TypeError):
                                    pass
                                break
                    if nb_parsed.get("diameter_mm") is not None:
                        break
            _storey_keys = ["ADSK_Этаж", "Этаж", "Storey", "Level"]
            _system_keys = ["BRU_Система", "Bru_Система", "Система", "System"]
            rows = conn.execute(
                sa.text("SELECT id, raw_psets_jsonb, storey_name, system_name FROM elements WHERE raw_psets_jsonb IS NOT NULL")
            ).fetchall()
            for eid, rp, cur_storey, cur_system in rows:
                if rp is None:
                    continue
                try:
                    parsed = _json.loads(rp) if isinstance(rp, str) else rp
                except Exception:
                    continue
                if not isinstance(parsed, dict):
                    continue
                new_storey = cur_storey
                if not new_storey:
                    for _pn, _props in parsed.items():
                        if isinstance(_props, dict):
                            for _k in _storey_keys:
                                _v = _props.get(_k)
                                if _v and str(_v).strip():
                                    new_storey = str(_v).strip()
                                    break
                        if new_storey:
                            break
                new_system = cur_system
                if not new_system:
                    for _pn, _props in parsed.items():
                        if isinstance(_props, dict):
                            for _k in _system_keys:
                                _v = _props.get(_k)
                                if _v and str(_v).strip():
                                    new_system = str(_v).strip()
                                    break
                        if new_system:
                            break
                if new_storey != cur_storey or new_system != cur_system:
                    conn.execute(
                        sa.text("UPDATE elements SET storey_name = :s, system_name = :sys WHERE id = :id"),
                        {"s": new_storey, "sys": new_system, "id": eid}
                    )
            # Migration: export raw_psets_jsonb / normalized_jsonb from DB to files
            rows2 = conn.execute(
                sa.text("SELECT id, raw_psets_jsonb, normalized_jsonb FROM elements WHERE raw_psets_jsonb IS NOT NULL")
            ).fetchall()
            exported = 0
            if rows2:
                from .element_storage import save_raw as _save_raw, save_norm as _save_norm, has_storage
                for eid, rp, nb in rows2:
                    if has_storage(eid):
                        continue
                    if rp:
                        try:
                            _save_raw(eid, _json.loads(rp) if isinstance(rp, str) else rp)
                        except Exception:
                            pass
                    if nb:
                        try:
                            _save_norm(eid, _json.loads(nb) if isinstance(nb, str) else nb)
                        except Exception:
                            pass
                    exported += 1
            if exported:
                import logging
                logging.getLogger(__name__).info(f"Exported {exported} element JSON blobs to disk")
            # Migration: clear JSON columns from DB after successful export
            conn.execute(
                sa.text("UPDATE elements SET raw_psets_jsonb = NULL, normalized_jsonb = NULL WHERE raw_psets_jsonb IS NOT NULL")
            )
            if exported:
                logging.getLogger(__name__).info(f"Cleared JSON columns from {exported} elements — DB size will shrink after VACUUM")
        await conn.run_sync(_migrate)
