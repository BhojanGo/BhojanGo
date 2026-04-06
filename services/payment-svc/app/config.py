from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    SERVICE_NAME: str = "payment-svc"
    VERSION: str = "0.1.0"
    PORT: int = 8005
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/4"
    REDIS_PASSWORD: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Stripe (USA)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Razorpay (India)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""
    SNS_TOPIC_ARN_PAYMENT: str = ""

    ORDER_SVC_URL: str = "http://localhost:8003"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
