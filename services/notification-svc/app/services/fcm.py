"""Firebase Cloud Messaging for push notifications."""
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_firebase_app = None


def get_firebase_app():  # type: ignore[no-untyped-def]
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not settings.FIREBASE_PROJECT_ID or settings.APP_ENV in ("test", "development"):
        logger.debug("firebase_mock_mode")
        return None

    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
        "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


async def send_push(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> bool:
    """Send FCM push notification to a single device. Returns True on success."""
    app = get_firebase_app()
    if app is None:
        logger.info("fcm_mock_send", token=token[-8:], title=title)
        return True

    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=1)
                )
            ),
        )
        messaging.send(message, app=app)
        logger.info("fcm_sent", token=token[-8:])
        return True
    except Exception as e:
        logger.error("fcm_send_failed", token=token[-8:], error=str(e))
        return False


async def send_multicast(tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> int:
    """Send to multiple tokens. Returns count of successful sends."""
    if not tokens:
        return 0

    app = get_firebase_app()
    if app is None:
        logger.info("fcm_mock_multicast", count=len(tokens), title=title)
        return len(tokens)

    try:
        from firebase_admin import messaging
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message, app=app)
        logger.info("fcm_multicast_sent", success=response.success_count, failure=response.failure_count)
        return response.success_count
    except Exception as e:
        logger.error("fcm_multicast_failed", error=str(e))
        return 0
