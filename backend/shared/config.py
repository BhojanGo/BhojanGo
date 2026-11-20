"""One Settings class for every backend deployable (core_api, realtime, worker).

Common settings live at the top level; settings that only one area uses live in
a section (``settings.payments.STRIPE_SECRET_KEY``). Every field keeps the
environment variable name it had when each service had its own config.py, so
existing .env files and deploy configs keep working unchanged.
"""
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Environment names that mean real customers and real money. Checked against
# APP_ENV and the hosting platform's own name for the environment (Railway sets
# RAILWAY_ENVIRONMENT_NAME), so a mislabelled APP_ENV can't slip a fake through.
PRODUCTION_NAMES = frozenset({"production", "prod"})
# Environments tests never write to (tools/target_guard.py reads them from /health).
PROTECTED_TEST_TARGETS = PRODUCTION_NAMES | {"qa"}


class ProductionConfigError(RuntimeError):
    """A local-only fake is configured in an environment named production."""


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"})


def public_url_problem(name: str, url: str) -> str | None:
    """Why ``url`` can't be a public address in production (links in emails, Stripe return
    URLs), naming the variable; None when it's a usable https address."""
    from urllib.parse import urlsplit

    url = (url or "").strip()
    if not url:
        return f"{name} is not set (the public https address)"
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return f"{name} must be an https:// address"
    if host in _LOCAL_HOSTS or host.endswith(".localhost") or host.startswith("127."):
        return f"{name} points at {host} (it must be the public address)"
    if host.endswith(".railway.internal"):
        return f"{name} points at the private network (it must be the public address)"
    return None


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
    # Phone sign-in codes (service/otp.py): "local" = we make the code, keep it in Redis and the
    # worker texts it (SMS_PROVIDER); "twilio_verify" = Twilio Verify sends and checks the code
    # (no sender number or A2P 10DLC registration needed). Production uses twilio_verify.
    OTP_PROVIDER: str = "local"  # local | twilio_verify
    TWILIO_VERIFY_SERVICE_SID: str = ""  # VA..., Twilio console: Verify > Services

    # Sign in with Google / Apple: the OAuth client ids whose ID tokens we
    # accept (web, iOS and Android each have one). Verifying needs no account:
    # tokens are checked against Google's public keys (free). Unset = off.
    GOOGLE_CLIENT_ID: str = ""
    # The website's OAuth client id (Google Identity Services); also shown to the
    # website by GET /auth/providers. Falls back to GOOGLE_CLIENT_ID.
    GOOGLE_WEB_CLIENT_ID: str = ""
    GOOGLE_CLIENT_IDS: list[str] = []  # more accepted audiences (the apps' client ids)
    GOOGLE_CLIENT_SECRET: str = ""

    # Apple: the app bundle ids (native) and the Services ID (web). Off unless set.
    APPLE_CLIENT_IDS: list[str] = []
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""

    SNS_TOPIC_ARN_USER: str = ""

    @property
    def google_audiences(self) -> list[str]:
        """Every Google client id whose ID tokens we accept (web and apps)."""
        return list(dict.fromkeys(c for c in [self.GOOGLE_WEB_CLIENT_ID, self.GOOGLE_CLIENT_ID, *self.GOOGLE_CLIENT_IDS] if c))

    @property
    def google_web_client_id(self) -> str:
        return self.GOOGLE_WEB_CLIENT_ID or self.GOOGLE_CLIENT_ID

    @property
    def apple_audiences(self) -> list[str]:
        return list(dict.fromkeys(c for c in [self.APPLE_CLIENT_ID, *self.APPLE_CLIENT_IDS] if c))

    # Email sign-in and passwords (Round 8, D5; core_api/modules/identity/service).
    # The website's public address: password-reset links point at <it>/signin/reset.
    PUBLIC_WEB_URL: str = "http://localhost:3000"
    PASSWORD_RESET_MINUTES: int = 30
    # A wrong password (or two-step code) this many times locks the account's
    # password sign-in for LOCKOUT_MINUTES (email codes and reset still work).
    LOCKOUT_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    # Fernet keys for secrets stored encrypted (admins' two-step secrets). The first
    # encrypts, all decrypt (rotate by putting a new key first). Generate one with
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())".
    # Required in production; elsewhere a fixed development key is used when empty.
    IDENTITY_DATA_KEYS: list[str] = []
    # Pwned Passwords k-anonymity check for new passwords (fails open when unreachable).
    PASSWORD_BREACH_CHECK: bool = True

    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_OTP: str = "3/minute"


class CatalogSettings(BaseSettings):
    """Was services/restaurant-svc."""

    model_config = _ENV

    CACHE_TTL_RESTAURANTS: int = 300  # 5 minutes
    # GET /discover: a city's kitchens, hours and rules apart from the address, kept this long in
    # each process (R21 load test; 0 = computed on every uncached address, as before).
    DISCOVER_FACTS_SECONDS: float = 20

    AWS_S3_BUCKET: str = "bhojango-assets-dev"
    AWS_CLOUDFRONT_URL: str = ""
    # R22 (S13): https hosts a dish, cover or logo photo may be on besides our own API
    # (PUBLIC_API_URL) and AWS_CLOUDFRONT_URL, e.g. ["photos.bhojango.com"]. Empty: none.
    PHOTO_HOSTS: list[str] = []

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
    # Payouts through Stripe Connect (R10, finance/service/connect.py). Each Stripe webhook
    # endpoint has its own signing secret; empty = STRIPE_WEBHOOK_SECRET (one `stripe listen`).
    STRIPE_CONNECT_WEBHOOK_SECRET: str = ""  # Connect endpoint: /api/v1/finance/stripe/connect/webhook
    STRIPE_PAYOUTS_WEBHOOK_SECRET: str = ""  # account endpoint: /api/v1/finance/stripe/webhook (transfer.*)
    # This API's public address: payout onboarding links point at
    # <it>/api/v1/finance/payout-onboarding (they make a fresh Stripe link each time).
    PUBLIC_API_URL: str = "http://localhost:8001"

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
    # Live batching (task 43): where a city has it on, a new order waits this long for
    # the batch engine to pair it before it's offered alone.
    BATCH_HOLD_SECONDS: int = 20
    # "Almost there": once per order, when the rider carrying it comes this close to the door.
    ALMOST_THERE_METERS: int = 400
    # R22 security review (S10): WebSockets open at once in one realtime process, per account and
    # per client address (carrier NAT puts many phones behind one address, hence the higher one).
    # 0 turns a cap off: load runs that share a few seed accounts from one machine set both to 0.
    WS_MAX_PER_USER: int = 5
    WS_MAX_PER_IP: int = 100
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

    # Batch engine (task 43, app/batching): how often it looks at the orders waiting
    # for a rider, and where realtime takes its suggestions and live batches.
    BATCH_CYCLE_SECONDS: float = 5
    # Data retention (R8 F10, app/services/retention.py): how often it deletes what the
    # Privacy notices say we delete (order messages after 90 days, resolved tickets after 3 years).
    RETENTION_CYCLE_SECONDS: float = 6 * 3600
    REALTIME_INTERNAL_URL: str = "http://localhost:8004"

    # The demo rider simulator (worker/app/demo_sim): make dev and QA only. Also needs
    # APP_ENV local/development/dev/qa; refused wherever anything says production.
    DEMO_RIDER_SIM: bool = False
    # R20: the review simulator (worker/app/demo_sim/review.py): plays the review kitchen and
    # delivery partner for app store review orders, and touches nothing else (only orders of a
    # review-only city's review accounts; core_api checks again). The one simulator production allows.
    REVIEW_SIM: bool = False

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
    # The sender for every email provider (an address on a verified domain); empty = SENDGRID_FROM_*.
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = ""

    # Amazon SES email (EMAIL_PROVIDER=ses, shared/providers/email.py): the SES v2 API through boto3,
    # with an IAM user allowed only ses:SendEmail. Own names, so they never mix with the bucket's AWS_* keys.
    SES_REGION: str = ""  # e.g. us-west-2: where the domain identity is verified
    SES_ACCESS_KEY_ID: str = ""
    SES_SECRET_ACCESS_KEY: str = ""
    SES_CONFIGURATION_SET: str = ""  # optional: bounce and complaint events

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
    # auto | live | fake (P13). Which provider a country pays with is its Markets field
    # countries.payout_provider; this only says whether real money may move (finance/service/providers.py).
    PAYOUT_PROVIDER: str = "auto"
    # log | live (Twilio for US, MSG91 for India) | off (no SMS at all: order updates go by push and
    # email, sign-in codes by Twilio Verify (OTP_PROVIDER); allowed in production because it's chosen)
    SMS_PROVIDER: str = "log"
    MSG91_AUTH_KEY: str = ""
    # DLT-registered template id per message key, e.g. {"otp": "6650..."}
    MSG91_TEMPLATE_IDS: dict[str, str] = {}
    EMAIL_PROVIDER: str = "log"  # log | smtp | sendgrid | ses
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
    S3_ADDRESSING_STYLE: str = "auto"  # auto | path | virtual (a Railway bucket's urlStyle; "virtual-host" = virtual)
    LOCAL_STORAGE_DIR: str = Field(default_factory=lambda: str(Path(tempfile.gettempdir()) / "bhojango-uploads"))

    @field_validator("S3_ADDRESSING_STYLE")
    @classmethod
    def normalize_addressing_style(cls, v: str) -> str:
        """Railway's bucket credentials say urlStyle "virtual-host"; boto3 calls it "virtual"."""
        v = v.strip().lower()
        return "virtual" if v in ("virtual-host", "virtual-hosted", "virtual_host") else v
    ROAD_FACTOR: float = 1.3
    AVG_SPEED_KMH: float = 25.0

    # Seed users (tools/seed) get this OTP outside production, so local sign-in
    # needs no SMS. Their phones start with these prefixes.
    OTP_FIXED_CODE: str = "123456"
    OTP_FIXED_CODE_PHONE_PREFIXES: list[str] = ["+9190000", "+12085550"]
    # ...and seed/test email addresses in these domains get the same fixed email code.
    OTP_FIXED_CODE_EMAIL_DOMAINS: list[str] = ["example.com"]
    # Orders by customers on the fictional seed numbers get this delivery PIN
    # (not a random one) outside production, so Maestro/e2e runs can hand it
    # over. Everyone else gets a random 4-digit PIN. Empty = always random.
    DELIVERY_PIN_FIXED: str = Field(default="1234", pattern=r"^(\d{4})?$")
    DELIVERY_PIN_FIXED_PHONE_PREFIXES: list[str] = ["+9190000", "+1208555"]


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
    AWS_ENDPOINT_URL: str = ""  # LocalStack URL in dev; a Railway bucket's endpoint on Railway

    # Event bus behind the outbox (shared/bus.py): "aws" = SNS topics -> SQS queues
    # (AWS, LocalStack); "redis" = one Redis stream with a consumer group per
    # consumer (Railway, anywhere without SNS/SQS).
    EVENT_BUS: str = "aws"
    EVENT_BUS_REDIS_URL: str = ""  # default: REDIS_URL. Must be the same for every service
    EVENT_BUS_STREAM: str = "bhojango:events"
    EVENT_BUS_MAXLEN: int = 100_000  # approximate cap; consumers are seconds behind
    EVENT_BUS_RETRY_IDLE_MS: int = 30_000  # unacknowledged this long -> delivered again
    EVENT_BUS_MAX_DELIVERIES: int = 3  # then the dead-letter stream (<stream>:dlq), like the SQS redrive
    EVENT_BUS_CONSUMER: str = ""  # consumer name in the group; default: the host name

    # The header a platform proxy puts the client's address in (Railway: X-Real-IP);
    # empty = the socket's peer. Rate limits and request logs use it (shared/client_ip.py).
    CLIENT_IP_HEADER: str = ""
    # Price checks (POST /pricing/quote) per signed-in person (R21 security review, S7).
    # 0 = no limit, outside production only (a load run sharing a few seed accounts sets 0).
    QUOTE_LIMIT_PER_MINUTE: int = 60
    QUOTE_LIMIT_PER_DAY: int = 2000
    # Optional IP-to-place database for the website's "near you" hint (shared/geoip.py).
    GEOIP_DB_PATH: str = ""

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

    @property
    def environment_name(self) -> str:
        """The environment's name for public /health (tools/target_guard.py: tests never
        write to QA or production): APP_ENV, or Railway's own name when that is qa or production."""
        platform = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").strip().lower()
        return platform if platform in PROTECTED_TEST_TARGETS else self.APP_ENV.strip().lower()

    @property
    def production_named(self) -> bool:
        names = (self.APP_ENV, os.environ.get("RAILWAY_ENVIRONMENT_NAME", ""))
        return any(n.strip().lower() in PRODUCTION_NAMES for n in names)

    @model_validator(mode="after")
    def refuse_fakes_in_production(self) -> "Settings":
        """No service starts in an environment named production with the fake
        payment or payout provider, or with the fixed OTP or delivery PIN for seed phones."""
        if not self.production_named:
            return self
        p = self.providers
        problems = []
        if p.PAYMENT_PROVIDER != "live":
            problems.append(f"PAYMENT_PROVIDER={p.PAYMENT_PROVIDER!r} (must be 'live': 'auto' falls back to the fake without keys)")
        if p.PAYOUT_PROVIDER == "fake":
            problems.append("PAYOUT_PROVIDER='fake'")
        if p.OTP_FIXED_CODE:
            problems.append("OTP_FIXED_CODE is set (set it to an empty string)")
        if p.DELIVERY_PIN_FIXED:
            problems.append("DELIVERY_PIN_FIXED is set (set it to an empty string)")
        if self.worker.DEMO_RIDER_SIM:
            problems.append("DEMO_RIDER_SIM is on (the demo rider is for make dev and QA only)")
        if problems:
            raise ProductionConfigError("refusing to start in production: " + "; ".join(problems))
        return self

    def core_api_production_problems(self) -> list[str]:
        """What core_api (only it builds links and signs people in) needs in production beyond
        refuse_fakes_in_production. Each problem names its variable. Empty outside production."""
        if not self.production_named:
            return []
        problems = [p for p in (public_url_problem("PUBLIC_WEB_URL", self.identity.PUBLIC_WEB_URL),
                                public_url_problem("PUBLIC_API_URL", self.payments.PUBLIC_API_URL)) if p]
        if not [k for k in self.identity.IDENTITY_DATA_KEYS if k]:
            problems.append("IDENTITY_DATA_KEYS is not set (generate it once: python tools/secrets/identity_data_keys.py)")
        i = self.identity
        if i.OTP_PROVIDER == "twilio_verify":
            missing = [n for n in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_VERIFY_SERVICE_SID") if not getattr(i, n)]
            if missing:
                problems.append("OTP_PROVIDER='twilio_verify' needs " + ", ".join(missing))
        elif self.providers.SMS_PROVIDER not in ("live", "twilio"):
            problems.append(f"OTP_PROVIDER={i.OTP_PROVIDER!r} with SMS_PROVIDER={self.providers.SMS_PROVIDER!r}: "
                            "phone sign-in codes would never be sent (use OTP_PROVIDER='twilio_verify')")
        return problems

    def check_core_api_production(self) -> None:
        problems = self.core_api_production_problems()
        if problems:
            raise ProductionConfigError("refusing to start in production: " + "; ".join(problems))

    @field_validator("EVENT_BUS")
    @classmethod
    def validate_event_bus(cls, v: str) -> str:
        if v not in ("aws", "redis"):
            raise ValueError("EVENT_BUS must be aws or redis")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v and not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
