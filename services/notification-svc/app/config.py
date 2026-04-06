from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    SERVICE_NAME: str = "notification-svc"
    VERSION: str = "0.1.0"
    PORT: int = 8006
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    DB_POOL_SIZE: int = 5

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""
    SQS_QUEUE_URL_NOTIFICATION: str = ""

    # Firebase FCM
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_PHONE_NUMBER_IN: str = ""

    # SendGrid email
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@bhojango.com"
    SENDGRID_FROM_NAME: str = "BhojanGo"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # SQS polling
    SQS_MAX_MESSAGES: int = 10
    SQS_WAIT_TIME_SECONDS: int = 20
    SQS_VISIBILITY_TIMEOUT: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
