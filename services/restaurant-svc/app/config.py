from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    SERVICE_NAME: str = "restaurant-svc"
    VERSION: str = "0.1.0"
    PORT: int = 8002
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/1"
    REDIS_PASSWORD: str = ""
    CACHE_TTL_RESTAURANTS: int = 300  # 5 minutes

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""
    AWS_S3_BUCKET: str = "bhojango-assets-dev"
    AWS_CLOUDFRONT_URL: str = ""

    OPENSEARCH_URL: str = "http://localhost:9200"
    OPENSEARCH_INDEX_RESTAURANTS: str = "bhojango-restaurants"
    OPENSEARCH_INDEX_MENU_ITEMS: str = "bhojango-menu-items"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
