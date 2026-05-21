"""应用配置"""
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./plant_safety.db"
    SECRET_KEY: str = "plant-safety-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    APP_NAME: str = "发电厂安全生产管理系统"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: Optional[List[str]] = None

    # v1.1：集成密钥（与 equipment-inspection 共享，CRITICAL 缺陷自动落隐患单）
    INTEGRATION_SECRET: str = "coal-integration-shared-secret"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
