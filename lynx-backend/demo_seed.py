"""
Demo seed script: pre-processes an IFC file and creates a demo project
with two model versions (V1 = all issues, V2 = fewer issues, "fixed").

Usage:
    python demo_seed.py /path/to/model.ifc

Requires:
    - .env with correct database_url (lynx.db will be used)
    - ifcopenshell installed
"""
import asyncio
import uuid
import sys
import logging
from pathlib import Path
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("demo_seed")

DEMO_PROJECT_ID = "demo-project-001"
DEMO_PROJECT_CODE = "DEMO-001"
DEMO_PROJECT_NAME = "Demo Project — ЖК Элемент"

SEED_V1_ID = "demo-seed-v1"
SEED_V2_ID = "demo-seed-v2"

DEMO_ERRORS_PATH = Path(__file__).parent / "demo_errors.json"


async def seed():
    if len(sys.argv) < 2:
        print("Usage: python demo_seed.py /path/to/model.ifc")
        sys.exit(1)

    ifc_path = Path(sys.argv[1])
    if not ifc_path.exists():
        print(f"IFC file not found: {ifc_path}")
        sys.exit(1)

    from app.core.config import settings
    from app.db.base import async_session, init_db
    from app.db.models import (
        Project, ModelVersion, Element, Issue,
        ProjectCategory,
    )
    from sqlalchemy import select, delete

    # Ensure DB exists
    await init_db()

    # Clean any existing demo data
    async with async_session() as session:
        await session.execute(
            delete(Issue).where(Issue.model_version_id.in_([SEED_V1_ID, SEED_V2_ID]))
        )
        await session.execute(
            delete(Element).where(Element.model_version_id.in_([SEED_V1_ID, SEED_V2_ID]))
        )
        await session.execute(
            delete(ModelVersion).where(ModelVersion.id.in_([SEED_V1_ID, SEED_V2_ID]))
        )
        await session.commit()

    # Create/update demo project
    async with async_session() as session:
        result = await session.execute(select(Project).where(Project.id == DEMO_PROJECT_ID))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Demo project already exists, reusing")
        else:
            p = Project(
                id=DEMO_PROJECT_ID,
                code=DEMO_PROJECT_CODE,
                name=DEMO_PROJECT_NAME,
                auto_bind_keywords="demo, test",
            )
            session.add(p)
            await session.commit()
            logger.info(f"Created demo project: {DEMO_PROJECT_NAME}")

            from app.db.crud import DEFAULT_CATEGORIES, DEFAULT_COLUMNS
            for i, name in enumerate(DEFAULT_CATEGORIES):
                session.add(ProjectCategory(
                    project_id=DEMO_PROJECT_ID,
                    name=name,
                    display_order=i,
                    columns_config=DEFAULT_COLUMNS.get(name, []),
                ))
            await session.commit()

    # Process the IFC with the real pipeline
    logger.info(f"Processing IFC: {ifc_path}")

    # Copy IFC to storage
    storage_raw = Path(settings.storage_path) / "raw"
    storage_raw.mkdir(parents=True, exist_ok=True)

    ifc_dst = storage_raw / f"{SEED_V1_ID}.ifc"
    import shutil
    shutil.copy2(str(ifc_path), str(ifc_dst))
    logger.info(f"Copied IFC to {ifc_dst}")

    # Run real processing for V1
    from app.services.ifc_normalizer import process_model_version

    # Create V1 model version
    async with async_session() as session:
        mv1 = ModelVersion(
            id=SEED_V1_ID,
            project_id=DEMO_PROJECT_ID,
            model_name="Demo Model V1",
            version_number=0,
            status="queued",
            source_filename=ifc_path.name,
        )
        session.add(mv1)
        await session.commit()

    await process_model_version(SEED_V1_ID)
    logger.info("V1 processed with real rules")

    # Load demo error templates
    with open(DEMO_ERRORS_PATH, encoding="utf-8") as f:
        demo_errors = json.load(f)

    # Inject V1 fake rule issues
    v1_rule_issues = demo_errors.get("v1", {}).get("rule_issues", [])
    async with async_session() as session:
        for issue_data in v1_rule_issues:
            session.add(Issue(
                id=str(uuid.uuid4()),
                model_version_id=SEED_V1_ID,
                global_id=issue_data["global_id"],
                severity=issue_data["severity"],
                rule_key=issue_data["rule_key"],
                message=issue_data["message"],
                status="open",
            ))
        await session.commit()
    logger.info(f"V1: injected {len(v1_rule_issues)} fake rule issues")

    # Create V2 — copy IFC and elements
    shutil.copy2(str(ifc_dst), str(storage_raw / f"{SEED_V2_ID}.ifc"))

    async with async_session() as session:
        mv2 = ModelVersion(
            id=SEED_V2_ID,
            project_id=DEMO_PROJECT_ID,
            model_name="Demo Model V2 (fixed)",
            version_number=1,
            status="queued",
            source_filename=ifc_path.name,
        )
        session.add(mv2)
        await session.commit()

    await process_model_version(SEED_V2_ID)
    logger.info("V2 processed with real rules")

    # Inject V2 fake rule issues (subset — some "fixed")
    v2_rule_issues = demo_errors.get("v2", {}).get("rule_issues", [])
    async with async_session() as session:
        for issue_data in v2_rule_issues:
            session.add(Issue(
                id=str(uuid.uuid4()),
                model_version_id=SEED_V2_ID,
                global_id=issue_data["global_id"],
                severity=issue_data["severity"],
                rule_key=issue_data["rule_key"],
                message=issue_data["message"],
                status="open",
            ))
        await session.commit()
    logger.info(f"V2: injected {len(v2_rule_issues)} fake rule issues")

    # Save AI check results for demo project
    v1_ai = demo_errors.get("v1", {}).get("ai_problems", [])
    ai_check_dir = Path(settings.storage_path) / "ai_check"
    ai_check_dir.mkdir(parents=True, exist_ok=True)
    (ai_check_dir / f"{DEMO_PROJECT_ID}.json").write_text(
        json.dumps({
            "project_id": DEMO_PROJECT_ID,
            "problems": v1_ai,
            "updated_at": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"Saved AI check result: {len(v1_ai)} problems")

    # Save fix suggestions for demo project
    v1_fixes = demo_errors.get("v1", {}).get("fix_suggestions", [])
    for fix in v1_fixes:
        idx = fix.get("issue_index")
        if idx is not None and 0 <= idx < len(v1_ai):
            fix["issue_message"] = v1_ai[idx].get("message", "")
            fix["issue_severity"] = v1_ai[idx].get("severity", "warning")
    fix_dir = Path(settings.storage_path) / "fix_suggestions"
    fix_dir.mkdir(parents=True, exist_ok=True)
    (fix_dir / f"{DEMO_PROJECT_ID}.json").write_text(
        json.dumps({
            "project_id": DEMO_PROJECT_ID,
            "fixes": v1_fixes,
            "updated_at": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"Saved fix suggestions: {len(v1_fixes)} fixes")

    # Final counts
    async with async_session() as session:
        v1_count = (await session.execute(
            select(Issue).where(Issue.model_version_id == SEED_V1_ID)
        )).scalars().all()
        v2_count = (await session.execute(
            select(Issue).where(Issue.model_version_id == SEED_V2_ID)
        )).scalars().all()
        logger.info(f"Final: V1={len(v1_count)} issues, V2={len(v2_count)} issues")
        logger.info(f"AI check: {len(v1_ai)} problems, Fixes: {len(v1_fixes)}")

    logger.info("Demo seed complete!")
    logger.info(f"Project ID: {DEMO_PROJECT_ID}")
    logger.info(f"Model V1: {SEED_V1_ID}")
    logger.info(f"Model V2: {SEED_V2_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
