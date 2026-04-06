from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    SERVICE_NAME: str = "order-svc"
    VERSION: str = "0.1.0"
    PORT: int = 8003
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/2"
    REDIS_PASSWORD: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""
    SNS_TOPIC_ARN_ORDER: str = ""

    # Internal service URLs
    RESTAURANT_SVC_URL: str = "http://localhost:8002"
    PAYMENT_SVC_URL: str = "http://localhost:8005"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Delivery time estimation (minutes)
    BASE_DELIVERY_MINUTES: int = 30
    PREP_TIME_BUFFER_MINUTES: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
