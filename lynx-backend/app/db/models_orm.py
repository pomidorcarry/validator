from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    technical_specification = Column(Text, default="")
    auto_bind_keywords = Column(Text, default="")
    tz_file_name = Column(String, default=None)
    tz_file_path = Column(String, default=None)
    tz_file_uploaded_at = Column(DateTime, default=None)
    tz_general = Column(Text, default="")
    tz_water_supply = Column(Text, default="")
    tz_sewerage = Column(Text, default="")
    tz_fire_fighting = Column(Text, default="")
    tz_other = Column(Text, default="")
    project_address = Column(Text, default="")
    sections_count = Column(Text, default="")
    floors_count = Column(Text, default="")
    bim_requirements = Column(Text, default="")
    pipeline_data = Column(JSON, default=dict)
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


class ProjectCategory(Base):
    __tablename__ = "project_categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    display_order = Column(Integer, default=0)
    columns_config = Column(JSON, default=list)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    ruleset_id = Column(String)
    model_name = Column(String, nullable=False)
    version_number = Column(Integer, default=None)
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


class TzVersion(Base):
    __tablename__ = "tz_versions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    data_jsonb = Column(JSON, nullable=False)
    source = Column(String, default="manual")
    file_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
