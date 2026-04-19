from datetime import datetime
from typing import Optional
import uuid
import json
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Ruleset(Base):
    __tablename__ = "rulesets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    status = Column(String, default="draft")
    source_text = Column(Text)
    ids_xml = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    ruleset_id = Column(String)
    model_name = Column(String, nullable=False)
    discipline = Column(String, default="VIV")
    status = Column(String, default="uploaded")
    source_filename = Column(String)
    ifc_hash = Column(String)
    ifc_schema = Column(String)
    export_profile = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    error_message = Column(Text)


class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String, nullable=False)
    artifact_type = Column(String, nullable=False)
    path = Column(String, nullable=False)
    mime_type = Column(String)
    sha256 = Column(String)
    size_bytes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Element(Base):
    __tablename__ = "elements"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String, nullable=False)
    global_id = Column(String, nullable=False)
    ifc_id = Column(Integer)
    ifc_class = Column(String, nullable=False)
    name = Column(String)
    object_type = Column(String)
    predefined_type = Column(String)
    type_name = Column(String)
    storey_name = Column(String)
    system_name = Column(String)
    raw_psets_jsonb = Column(JSON)
    normalized_jsonb = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ElementMeasurement(Base):
    __tablename__ = "element_measurements"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    element_id = Column(String, nullable=False)
    measurement_key = Column(String, nullable=False)
    value_num = Column(Float)
    unit = Column(String)
    source_path = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class Issue(Base):
    __tablename__ = "issues"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String, nullable=False)
    element_id = Column(String)
    global_id = Column(String)
    issue_type = Column(String, default="validation")
    severity = Column(String, default="error")
    rule_key = Column(String, nullable=False)
    status = Column(String, default="open")
    message = Column(String, nullable=False)
    expected_jsonb = Column(JSON)
    actual_jsonb = Column(JSON)
    source_engine = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String, nullable=False)
    element_id = Column(String)
    suggestion_type = Column(String, nullable=False)
    candidate_jsonb = Column(JSON, nullable=False)
    score = Column(Float)
    state = Column(String, default="draft")
    approved_by = Column(String)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_type = Column(String)
    actor_id = Column(String)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    payload_jsonb = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String, nullable=False)
    report_type = Column(String, nullable=False)
    path = Column(String)
    summary_jsonb = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


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


async def create_model_version(
    model_version_id: str,
    project_id: str,
    model_name: str,
    ruleset_id: str,
    filename: str,
) -> ModelVersion:
    async with async_session() as session:
        mv = ModelVersion(
            id=model_version_id,
            project_id=project_id,
            model_name=model_name,
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
            "status": mv.status,
        }


async def get_model_version(model_version_id: str) -> Optional[dict]:
    async with async_session() as session:
        from sqlalchemy import select
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
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Issue).where(Issue.model_version_id == model_version_id)
        )
        issues = result.scalars().all()
        return [
            {
                "id": i.id,
                "global_id": i.global_id,
                "severity": i.severity,
                "rule_key": i.rule_key,
                "message": i.message,
                "status": i.status,
            }
            for i in issues
        ]


async def list_all_models() -> list:
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ModelVersion).order_by(ModelVersion.created_at.desc())
        )
        models = result.scalars().all()
        return [
            {
                "id": m.id,
                "model_name": m.model_name,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "processed_at": m.processed_at.isoformat() if m.processed_at else None,
            }
            for m in models
        ]


async def get_elements(model_version_id: str) -> list:
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Element).where(Element.model_version_id == model_version_id)
        )
        elements = result.scalars().all()
        return [
            {
                "id": e.id,
                "global_id": e.global_id,
                "ifc_class": e.ifc_class,
                "name": e.name,
                "object_type": e.object_type,
                "type_name": e.type_name,
                "storey_name": e.storey_name,
                "system_name": e.system_name,
                "normalized_jsonb": e.normalized_jsonb,
            }
            for e in elements
        ]