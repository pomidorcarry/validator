import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["LYNX_TESTING"] = "1"

import app.core.config as config_mod

TEST_DIR = Path(tempfile.mkdtemp(prefix="lynx_test_"))
TEST_DB = TEST_DIR / "test.db"
TEST_STORAGE = TEST_DIR / "storage"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB}"

TEST_STORAGE.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def override_settings():
    old_storage = config_mod.settings.storage_path
    old_db = config_mod.settings.database_url
    config_mod.settings.storage_path = str(TEST_STORAGE)
    config_mod.settings.database_url = TEST_DB_URL
    yield
    config_mod.settings.storage_path = old_storage
    config_mod.settings.database_url = old_db


@pytest.fixture(scope="session")
def test_storage() -> Path:
    return TEST_STORAGE


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    from app.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_project(session: AsyncSession) -> dict:
    from app.db.models import create_project
    proj = await create_project(
        code="TEST001",
        name="Test Project",
        technical_specification="Test spec",
        auto_bind_keywords="test,check",
    )
    return proj


@pytest_asyncio.fixture
async def sample_model_version(session: AsyncSession, sample_project: dict) -> dict:
    from app.db.models import create_model_version
    mv = await create_model_version(
        model_version_id=str(uuid.uuid4()),
        project_id=sample_project["id"],
        model_name="TestModel",
        ruleset_id="default",
        filename="test.ifc",
    )
    return mv
