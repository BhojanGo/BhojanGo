from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    SERVICE_NAME: str = "delivery-svc"
    VERSION: str = "0.1.0"
    PORT: int = 8004
    LOG_LEVEL: str = "INFO"

    REDIS_URL: str = "redis://localhost:6379/3"
    REDIS_PASSWORD: str = ""
    DRIVER_LOCATION_TTL: int = 30  # seconds

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""
    SNS_TOPIC_ARN_DELIVERY: str = ""
    SQS_QUEUE_URL_DELIVERY: str = ""
    DYNAMODB_TABLE_DELIVERY_HISTORY: str = "bhojango-delivery-history"
    DYNAMODB_ENDPOINT_URL: str = ""

    AWS_LOCATION_ROUTE_CALCULATOR: str = "bhojango-route-calculator"

    ORDER_SVC_URL: str = "http://localhost:8003"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
