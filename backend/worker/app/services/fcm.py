"""Firebase app for FCM push (shared/providers/push.py FcmPush sends)."""
import structlog

from shared.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_firebase_app = None


def get_firebase_app():  # type: ignore[no-untyped-def]
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not settings.worker.FIREBASE_PROJECT_ID or settings.APP_ENV in ("test", "development"):
        logger.debug("firebase_mock_mode")
        return None

    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": settings.worker.FIREBASE_PROJECT_ID,
        "private_key_id": settings.worker.FIREBASE_PRIVATE_KEY_ID,
        "private_key": settings.worker.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        "client_email": settings.worker.FIREBASE_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app
