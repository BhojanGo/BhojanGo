"""R15: the legal entity per country is checked data; GST countries need more before launch."""
import pytest

from core_api.modules.markets.service.legal import check_settings, entity, missing
from core_api.modules.markets.service.rules import MarketRuleError


def test_fields_follow_the_tax_regime() -> None:
    us = {"legal": {"name": "Example LLC"}}
    assert missing(us, "us_sales_tax") == ["address", "support_email", "support_phone"]
    assert missing(us, "gst")[-5:] == ["cin", "gstin", "grievance_name", "grievance_email", "grievance_phone"]
    assert entity(us, "us_sales_tax") == {"name": "Example LLC"}
    assert entity({"legal": {"name": "X", "address": "", "support_email": None}}, "us_sales_tax") == {"name": "X"}


def test_values_are_checked_never_invented() -> None:
    check_settings({"legal": {"name": "X", "support_email": "help@example.com", "support_phone": "+1 208 555 0100"}}, "us_sales_tax")
    check_settings({"legal": {"cin": "U72900TG2020PTC123456", "gstin": "36ABCDE1234F1Z5", "grievance_name": None}}, "gst")
    for bad, regime in (({"cin": "U1"}, "gst"), ({"gstin": "ABC"}, "gst"), ({"support_email": "nope"}, "us_sales_tax"),
                        ({"gstin": "36ABCDE1234F1Z5"}, "us_sales_tax"), ({"name": 5}, "gst"), ("text", "gst")):
        with pytest.raises(MarketRuleError):
            check_settings({"legal": bad}, regime)
