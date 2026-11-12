"""One Settings class for every backend deployable (core_api, realtime, worker).

Common settings live at the top level; settings that only one area uses live in
a section (``settings.payments.STRIPE_SECRET_KEY``). Every field keeps the
environment variable name it had when each service had its own config.py, so
existing .env files and deploy configs keep working unchanged.
"""
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class IdentitySettings(BaseSettings):
    """Was services/user-svc."""

    model_config = _ENV

    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_PHONE_NUMBER_IN: str = ""

    # Sign in with Google / Apple: the OAuth client ids whose ID tokens we
    # accept (web, iOS and Android each have one). Verifying needs no account.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_IDS: list[str] = []
    GOOGLE_CLIENT_SECRET: str = ""

    # Apple: the app bundle ids (native) and the Services ID (web).
    APPLE_CLIENT_IDS: list[str] = ["com.bhojango.app", "com.bhojango.rider", "com.bhojango.partner"]
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""

    SNS_TOPIC_ARN_USER: str = ""

    @property
    def google_audiences(self) -> list[str]:
        return [c for c in [*self.GOOGLE_CLIENT_IDS, self.GOOGLE_CLIENT_ID] if c]

    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_OTP: str = "3/minute"


class CatalogSettings(BaseSettings):
    """Was services/restaurant-svc."""

    model_config = _ENV

    CACHE_TTL_RESTAURANTS: int = 300  # 5 minutes

    AWS_S3_BUCKET: str = "bhojango-assets-dev"
    AWS_CLOUDFRONT_URL: str = ""

    OPENSEARCH_URL: str = "http://localhost:9200"
    OPENSEARCH_INDEX_RESTAURANTS: str = "bhojango-restaurants"
    OPENSEARCH_INDEX_MENU_ITEMS: str = "bhojango-menu-items"


class OrdersSettings(BaseSettings):
    """Was services/order-svc."""

    model_config = _ENV

    SNS_TOPIC_ARN_ORDER: str = ""

    # Catalog and payments now run in the same process (core_api); these URLs
    # are kept because orders still calls them over HTTP until a later prompt
    # replaces the calls with in-process service calls.
    RESTAURANT_SVC_URL: str = "http://localhost:8001"
    PAYMENT_SVC_URL: str = "http://localhost:8001"

    # Delivery time estimation (minutes)
    BASE_DELIVERY_MINUTES: int = 30
    PREP_TIME_BUFFER_MINUTES: int = 5


class PaymentsSettings(BaseSettings):
    """Was services/payment-svc."""

    model_config = _ENV

    # Stripe (USA)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Razorpay (India)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    SNS_TOPIC_ARN_PAYMENT: str = ""

    ORDER_SVC_URL: str = "http://localhost:8001"


class RealtimeSettings(BaseSettings):
    """Was services/delivery-svc."""

    model_config = _ENV

    DRIVER_LOCATION_TTL: int = 30  # seconds
    # Dispatch (P14): offer to riders within this distance of the restaurant,
    # and only those whose last GPS fix is fresh (DRIVER_LOCATION_TTL).
    DISPATCH_RADIUS_KM: float = 6.0
    DISPATCH_RETRY_SECONDS: int = 15  # no rider free: try again after this
    SQS_QUEUE_URL_ORDERS: str = ""  # order events (order topic -> this queue)

    SNS_TOPIC_ARN_DELIVERY: str = ""
    SQS_QUEUE_URL_DELIVERY: str = ""
    DYNAMODB_TABLE_DELIVERY_HISTORY: str = "bhojango-delivery-history"
    DYNAMODB_ENDPOINT_URL: str = ""

    AWS_LOCATION_ROUTE_CALCULATOR: str = "bhojango-route-calculator"

    ORDER_SVC_URL: str = "http://localhost:8001"


class WorkerSettings(BaseSettings):
    """Was services/notification-svc."""

    model_config = _ENV

    SQS_QUEUE_URL_NOTIFICATION: str = ""

    # Firebase FCM
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""

    # Twilio SMS (same env vars as identity's OTP sender)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_PHONE_NUMBER_IN: str = ""

    # SendGrid email
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@bhojango.com"
    SENDGRID_FROM_NAME: str = "BhojanGo"

    # SQS polling
    SQS_MAX_MESSAGES: int = 10
    SQS_WAIT_TIME_SECONDS: int = 20
    SQS_VISIBILITY_TIMEOUT: int = 60


class ProviderSettings(BaseSettings):
    """Which implementation each external provider uses (shared/providers and
    core_api payments).

    Locally and in tests everything runs with no account: payments are faked,
    SMS and push are logged, email goes to Mailpit (or the log), and routing is
    straight-line distance x ROAD_FACTOR. Production refuses the fakes.
    """

    model_config = _ENV

    # auto = the real provider when its keys are set, otherwise the fake
    PAYMENT_PROVIDER: str = "auto"  # auto | fake | live
    FAKE_PAYMENT_WEBHOOK_SECRET: str = "local-fake-webhook-secret"  # placeholder, local only
    # Fake payments complete on their own (like a customer finishing checkout)
    # after this many seconds; 0 = only via POST /payments/fake/{id}/complete.
    FAKE_PAYMENT_AUTO_COMPLETE_SECONDS: float = 0
    FAKE_PAYMENT_WEBHOOK_URL: str = "http://localhost:8001/api/v1/payments/fake/webhook"

    TAX_PROVIDER: str = "auto"  # auto | stripe_tax | local (US sales tax, P9)
    PAYOUT_PROVIDER: str = "auto"  # auto | live (Stripe Connect US, Razorpay Route IN) | fake (P13)
    SMS_PROVIDER: str = "log"  # log | live (Twilio for US, MSG91 for India)
    MSG91_AUTH_KEY: str = ""
    # DLT-registered template id per message key, e.g. {"otp": "6650..."}
    MSG91_TEMPLATE_IDS: dict[str, str] = {}
    EMAIL_PROVIDER: str = "log"  # log | smtp | sendgrid
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    PUSH_PROVIDER: str = "log"  # log | live (Expo, FCM or APNs by the device's token)
    EXPO_ACCESS_TOKEN: str = ""  # optional: Expo push security
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_PRIVATE_KEY: str = ""  # the .p8 key (PEM)
    APNS_BUNDLE_ID: str = "com.bhojango.app"
    APNS_SANDBOX: bool = False
    ROUTING_PROVIDER: str = "straight_line"
    # Uploaded files (P18: delivery photos, rider documents): local disk, or S3
    # (LocalStack in `make dev`).
    STORAGE_PROVIDER: str = "local"  # local | s3
    UPLOADS_BUCKET: str = "bhojango-uploads"
    LOCAL_STORAGE_DIR: str = Field(default_factory=lambda: str(Path(tempfile.gettempdir()) / "bhojango-uploads"))
    ROAD_FACTOR: float = 1.3
    AVG_SPEED_KMH: float = 25.0

    # Seed users (tools/seed) get this OTP outside production, so local sign-in
    # needs no SMS. Their phones start with these prefixes.
    OTP_FIXED_CODE: str = "123456"
    OTP_FIXED_CODE_PHONE_PREFIXES: list[str] = ["+9190000", "+12085550"]


class Settings(BaseSettings):
    model_config = _ENV

    # App — SERVICE_NAME and PORT are set per deployable (Dockerfile / compose).
    APP_ENV: str = "development"
    SERVICE_NAME: str = "core-api"
    VERSION: str = "0.1.0"
    PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = ""  # json | console; empty = json in production, console elsewhere

    # Observability (P23): traces to an OTLP collector (empty = off); the Sentry
    # adapter stays off unless a DSN is set (shared/observability.py).
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    SENTRY_DSN: str = ""
    # Alertmanager's webhook to core_api (P23): a shared token, empty = refused.
    ALERT_WEBHOOK_TOKEN: str = ""

    # Database (realtime does not use it, so it is not required at import time;
    # shared.db refuses to start without it)
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    REDIS_MAX_CONNECTIONS: int = 100  # per process; WebSockets share one pub/sub connection (realtime hub)

    # JWT: RS256 (shared/jwt_keys.py). Only core_api signs; everyone verifies.
    JWT_PRIVATE_KEY: str = ""  # PEM; required in production (core_api)
    JWT_PUBLIC_KEYS: list[str] = []  # extra PEMs to accept, e.g. the previous key while rotating
    JWKS_URL: str = ""  # realtime/worker: core_api's /.well-known/jwks.json
    JWT_DEV_KEY_PATH: str = Field(default_factory=lambda: str(Path(tempfile.gettempdir()) / "bhojango-jwt-dev.pem"))
    JWT_SECRET: str = ""  # unused since P5 (HS256 -> RS256); kept so old env files still load

    # realtime -> core_api internal calls (shared/internal_auth.py, P14)
    INTERNAL_SERVICE_SECRET: str = "local-internal-secret"  # placeholder; production sets its own
    CORE_API_URL: str = "http://localhost:8001"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""  # LocalStack URL in dev

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    orders: OrdersSettings = Field(default_factory=OrdersSettings)
    payments: PaymentsSettings = Field(default_factory=PaymentsSettings)
    realtime: RealtimeSettings = Field(default_factory=RealtimeSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v and not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
