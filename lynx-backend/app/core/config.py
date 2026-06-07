import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load proxy env vars from .env before Settings initialization,
# so httpx/openai clients can pick them up.
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if os.path.isfile(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip()
            if _k.upper() in ("HTTP_PROXY", "HTTPS_PROXY") and not os.environ.get(_k.upper()):
                os.environ[_k.upper()] = _v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    app_name: str = "Lynx Backend"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    
    host: str = "0.0.0.0"
    port: int = 8000
    
    storage_path: str = "./storage"
    database_url: str = "sqlite+aiosqlite:///./lynx.db"
    
    max_file_size_mb: int = 100
    
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    demo_mode: bool = False


settings = Settings()