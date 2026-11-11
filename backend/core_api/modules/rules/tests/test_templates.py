"""Every template accepts good parameters and refuses bad ones."""
import pytest
from pydantic import ValidationError

from core_api.modules.rules.service import templates as t

GOOD = {
    ("delivery_fee", "flat"): {"amount": 30},
    ("delivery_fee", "distance_slabs"): {"slabs": [{"up_to": 3, "fee": 25}, {"up_to": 6, "fee": 35}]},
    ("delivery_fee", "free_above"): {"min_subtotal": 499, "otherwise": 30},
    ("delivery_fee", "tier_base"): {"tiers": {"A": 25, "B": 30}, "default_tier": "B"},
    ("customer_fee", "service_fee"): {"percent": 2, "min": 5, "max": 15},
    ("customer_fee", "small_order_fee"): {"below": 99, "fee": 15},
    ("customer_fee", "packaging_levy"): {"amount": 10},
    ("customer_fee", "surge_levy"): {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 15},
    ("customer_fee", "late_night_fee"): {"window": {"start": "23:00", "end": "02:00"}, "amount": 20},
    ("tax", "rate_on_lines"): {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"]},
    ("tax", "external"): {"provider": "stripe_tax"},
    ("commission", "percent_by_tier"): {"tiers": {"A": 18, "B": 15}, "default_tier": "B"},
    ("commission", "flat_per_order"): {"amount": 5},
    ("commission", "payout_schedule"): {"frequency": "weekly", "day": "mon"},
    ("rider_pay", "base_distance_wait"): {"base": 25, "per_unit": 6},
    ("rider_pay", "hourly_floor"): {"per_active_hour": 120},
    ("rider_pay", "batch_bonus"): {"per_extra_order": 10},
    ("rider_pay", "peak_bonus"): {"windows": [{"start": "12:00", "end": "14:00", "days": ["sat", "sun"]}], "per_order": 10},
    ("business", "accept_timeout"): {"seconds": 180},
    ("business", "unpaid_auto_cancel"): {"minutes": 10},
    ("business", "cancel_window"): {"minutes": 2},
    ("business", "refund_window"): {"hours": 72},
    ("business", "cod_limit"): {"max_amount": 1000},
    ("business", "tip_presets"): {"amounts": [10, 20, 30]},
    ("business", "max_radius"): {"distance": 10},
    ("business", "dispatch_offer_timeout"): {"seconds": 30},
    ("promotion", "percent_off"): {"percent": 10, "max_discount": 50, "funded_by": "platform"},
    ("promotion", "flat_off"): {"amount": 75, "funded_by": "restaurant", "min_subtotal": 299, "code": "SAVE75"},
    ("promotion", "free_delivery"): {"funded_by": "restaurant", "budget_cap": 5000},
    ("promotion", "first_order"): {"percent": 50, "max_discount": 100, "funded_by": "platform"},
    ("promotion", "referral"): {"amount": 100, "funded_by": "platform"},
}


def test_every_template_has_a_good_example() -> None:
    assert set(GOOD) == {(f, n) for f, ts in t.TEMPLATES.items() for n in ts}


@pytest.mark.parametrize(("family", "template"), list(GOOD))
def test_good_params_validate(family, template) -> None:
    out = t.validate_params(family, template, GOOD[(family, template)])
    assert isinstance(out, dict)


BAD = [
    ("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 6, "fee": 35}, {"up_to": 3, "fee": 25}]}),  # not ascending
    ("delivery_fee", "distance_slabs", {"slabs": []}),
    ("delivery_fee", "flat", {"amount": -1}),
    ("delivery_fee", "tier_base", {"tiers": {"A": 25}, "default_tier": "Z"}),
    ("customer_fee", "service_fee", {"percent": 2, "min": 15, "max": 5}),  # max < min
    ("customer_fee", "service_fee", {"percent": 120, "min": 1, "max": 5}),
    ("customer_fee", "surge_levy", {"windows": [{"start": "7pm", "end": "21:30"}], "amount": 15}),
    ("tax", "rate_on_lines", {"label": "GST", "rate_percent": 5, "target_lines": ["tip"]}),  # tips aren't taxed lines
    ("commission", "percent_by_tier", {"tiers": {"A": 180}, "default_tier": "A"}),
    ("business", "accept_timeout", {"seconds": 5}),
    ("business", "tip_presets", {"amounts": []}),
    ("promotion", "percent_off", {"percent": 10, "funded_by": "someone"}),
    ("promotion", "flat_off", {"amount": 50, "funded_by": "platform", "code": "lower case"}),
    ("customer_fee", "packaging_levy", {"amount": 10, "surprise": 1}),  # unknown keys are refused
]


@pytest.mark.parametrize(("family", "template", "params"), BAD)
def test_bad_params_refused(family, template, params) -> None:
    with pytest.raises(ValidationError):
        t.validate_params(family, template, params)


def test_unknown_family_or_template() -> None:
    with pytest.raises(t.TemplateError):
        t.validate_params("cashback", "flat", {})
    with pytest.raises(t.TemplateError):
        t.validate_params("delivery_fee", "formula", {})


def test_slots() -> None:
    assert t.slot_for("delivery_fee", "flat", None) == t.slot_for("delivery_fee", "distance_slabs", None) == "delivery_fee"
    assert t.slot_for("tax", "rate_on_lines", "gst_food") != t.slot_for("tax", "rate_on_lines", "gst_fees")
    assert t.slot_for("customer_fee", "service_fee", None) == "customer_fee:service_fee"
    assert t.slot_for("promotion", "percent_off", "diwali") == "promotion:percent_off:diwali"
    with pytest.raises(t.TemplateError):
        t.check_key("Bad Key")


def test_money_families_and_levels() -> None:
    assert "business" not in t.MONEY_FAMILIES and {"tax", "commission", "rider_pay"} <= t.MONEY_FAMILIES
    assert t.ALLOWED_LEVELS["tax"] == {"country", "region", "city"}
    assert "platform" in t.ALLOWED_LEVELS["business"] and "zone" in t.ALLOWED_LEVELS["delivery_fee"]


def test_catalogue_lists_everything_with_schemas() -> None:
    cat = t.catalogue()
    assert len(cat) == len(GOOD)
    svc = next(c for c in cat if c["template"] == "service_fee")
    assert svc["money"] is True and svc["allowed_levels"] == ["city", "zone", "restaurant"]
    assert set(svc["params_schema"]["properties"]) >= {"percent", "min", "max"}
