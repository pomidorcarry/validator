from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Lynx Backend"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    
    host: str = "0.0.0.0"
    port: int = 8000
    
    storage_path: str = "./storage"
    database_url: str = "sqlite+aiosqlite:///./lynx.db"
    
    max_file_size_mb: int = 100
    
    class Config:
        env_file = ".env"


settings = Settings()