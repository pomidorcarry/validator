from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .db.models import init_db

from .api.v1 import health, ai_status, projects_api, models_api, categories_api, tz_api, ai_check_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "Lynx Backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


api_prefix = settings.api_prefix
app.include_router(health.router, prefix=api_prefix)
app.include_router(ai_status.router, prefix=api_prefix)
app.include_router(projects_api.router, prefix=api_prefix)
app.include_router(models_api.router, prefix=api_prefix)
app.include_router(categories_api.router, prefix=api_prefix)
app.include_router(tz_api.router, prefix=api_prefix)
app.include_router(ai_check_api.router, prefix=api_prefix)
