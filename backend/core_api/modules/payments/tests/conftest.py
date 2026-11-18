import pytest


@pytest.fixture(autouse=True)
def _stripe_configuration(monkeypatch):  # type: ignore[no-untyped-def]
    """Unit tests never reach Stripe for the payment method configuration (R13): a fixed id."""
    from core_api.modules.payments.service import stripe_methods

    async def configuration_id(methods):  # type: ignore[no-untyped-def]
        return "pmc_unit_" + "+".join(methods)

    monkeypatch.setattr(stripe_methods, "configuration_id", configuration_id)
