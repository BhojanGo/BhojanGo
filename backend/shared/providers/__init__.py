"""External providers behind small interfaces (SMS, email, push, routing).

Each ``get_*`` picks the implementation named in ``settings.providers``. The
local ones (log, SMTP to Mailpit, straight-line routing) need no account;
production refuses the ones that would silently drop messages.
"""
from shared.config import get_settings


class ProviderConfigError(RuntimeError):
    """A provider is misconfigured (e.g. a local fake selected in production)."""


def refuse_in_production(kind: str, name: str) -> None:
    if get_settings().is_production:
        raise ProviderConfigError(f"{kind} provider '{name}' is for local use only; configure a real one")
