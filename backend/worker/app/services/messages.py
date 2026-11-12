"""What BhojanGo says, in English, Hindi and Telugu (P15).

Voice (brand board): plain, specific, warm. Numbers over adjectives: say the
time, the amount, the name. Never blame the customer, the rider or the kitchen.
No emoji.

Each message has a push title and a body; SMS sends "BhojanGo: <body>" and
email wraps the same words in the brand layout. India SMS must use a
DLT-registered template per message and language: the key is
"<message>_<language>" (e.g. "order_picked_up_hi") and its variables are the
placeholders below, in the order they appear (MSG91_TEMPLATE_IDS maps keys to
template ids).
"""
import html
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

LANGUAGES = ("en", "hi", "te")

# "Arriving around 8:24 PM." — omitted when there's no estimate.
ARRIVING = {
    "en": "Arriving around {eta}.",
    "hi": "लगभग {eta} तक पहुंचेगा।",
    "te": "సుమారు {eta}కి చేరుతుంది.",
}

# (title, body) per message per language.
CATALOGUE: dict[str, dict[str, tuple[str, str]]] = {
    "order_placed": {
        "en": ("Order placed", "{restaurant} has your order {code}. We'll tell you when they start cooking."),
        "hi": ("ऑर्डर मिल गया", "{restaurant} को आपका ऑर्डर {code} मिल गया है। खाना बनना शुरू होते ही हम बताएंगे।"),
        "te": ("ఆర్డర్ అందింది", "{restaurant}కి మీ ఆర్డర్ {code} అందింది. వంట మొదలవగానే మీకు తెలియజేస్తాం."),
    },
    "order_accepted": {
        "en": ("Order accepted", "{restaurant} accepted your order. {arriving}"),
        "hi": ("ऑर्डर स्वीकार हुआ", "{restaurant} ने आपका ऑर्डर स्वीकार कर लिया। {arriving}"),
        "te": ("ఆర్డర్ అంగీకరించారు", "{restaurant} మీ ఆర్డర్‌ను అంగీకరించింది. {arriving}"),
    },
    "order_preparing": {
        "en": ("Cooking now", "{restaurant} is cooking your order. {arriving}"),
        "hi": ("खाना बन रहा है", "{restaurant} आपका ऑर्डर बना रहा है। {arriving}"),
        "te": ("వంట జరుగుతోంది", "{restaurant} మీ ఆర్డర్‌ను వండుతోంది. {arriving}"),
    },
    "driver_assigned": {
        "en": ("Rider on the way to the kitchen", "{rider} will bring your order from {restaurant}. {arriving}"),
        "hi": ("राइडर तय हो गया", "{rider} {restaurant} से आपका ऑर्डर लाएंगे। {arriving}"),
        "te": ("రైడర్ ఖరారయ్యారు", "{rider} {restaurant} నుండి మీ ఆర్డర్ తెస్తారు. {arriving}"),
    },
    "order_picked_up": {
        "en": ("On the way", "{rider} picked up your order and is heading to you. {arriving}"),
        "hi": ("रास्ते में है", "{rider} ने आपका ऑर्डर ले लिया है और आपके पास आ रहे हैं। {arriving}"),
        "te": ("దారిలో ఉంది", "{rider} మీ ఆర్డర్ తీసుకుని మీ వద్దకు వస్తున్నారు. {arriving}"),
    },
    "order_delivered": {
        "en": ("Delivered", "Your order from {restaurant} is here. Enjoy your meal."),
        "hi": ("डिलीवर हो गया", "{restaurant} से आपका ऑर्डर पहुंच गया है। खाने का आनंद लें।"),
        "te": ("డెలివరీ అయింది", "{restaurant} నుండి మీ ఆర్డర్ చేరింది. హాయిగా ఆస్వాదించండి."),
    },
    "order_cancelled_refunded": {
        "en": ("Order cancelled", "Your order {code} from {restaurant} was cancelled. {refund} is on its way back to you; banks usually take 5–7 days."),
        "hi": ("ऑर्डर रद्द हुआ", "{restaurant} से आपका ऑर्डर {code} रद्द हो गया। {refund} आपको वापस भेजे जा रहे हैं; बैंक में आमतौर पर 5–7 दिन लगते हैं।"),
        "te": ("ఆర్డర్ రద్దయింది", "{restaurant} నుండి మీ ఆర్డర్ {code} రద్దయింది. {refund} మీకు తిరిగి పంపుతున్నాం; బ్యాంకుకు సాధారణంగా 5–7 రోజులు పడుతుంది."),
    },
    "order_cancelled_unpaid": {
        "en": ("Order cancelled", "Your order {code} from {restaurant} was cancelled. You have not been charged."),
        "hi": ("ऑर्डर रद्द हुआ", "{restaurant} से आपका ऑर्डर {code} रद्द हो गया। आपसे कोई पैसा नहीं लिया गया।"),
        "te": ("ఆర్డర్ రద్దయింది", "{restaurant} నుండి మీ ఆర్డర్ {code} రద్దయింది. మీ నుండి డబ్బు తీసుకోలేదు."),
    },
    "payment_failed": {
        "en": ("Payment didn't go through", "Payment didn't go through. You have not been charged. Your order {code} is held for a few minutes; try again in the app."),
        "hi": ("भुगतान नहीं हुआ", "भुगतान नहीं हो पाया। आपसे पैसा नहीं लिया गया। आपका ऑर्डर {code} कुछ मिनट के लिए रखा है; ऐप में फिर से कोशिश करें।"),
        "te": ("చెల్లింపు జరగలేదు", "చెల్లింపు జరగలేదు. మీ నుండి డబ్బు తీసుకోలేదు. మీ ఆర్డర్ {code} కొన్ని నిమిషాలు ఉంచాం; యాప్‌లో మళ్లీ ప్రయత్నించండి."),
    },
    "refund_items": {
        "en": ("Refund sent", "{amount} refunded for order {code}. Banks usually take 5–7 days."),
        "hi": ("रिफंड भेजा गया", "ऑर्डर {code} के लिए {amount} रिफंड किए गए। बैंक में आमतौर पर 5–7 दिन लगते हैं।"),
        "te": ("రిఫండ్ పంపాం", "ఆర్డర్ {code}కి {amount} రిఫండ్ చేశాం. బ్యాంకుకు సాధారణంగా 5–7 రోజులు పడుతుంది."),
    },
    "partner_new_order": {
        "en": ("New order {code}", "{items}, {total}. Accept by {accept_by}."),
        "hi": ("नया ऑर्डर {code}", "{items}, {total}। {accept_by} तक स्वीकार करें।"),
        "te": ("కొత్త ఆర్డర్ {code}", "{items}, {total}. {accept_by} లోపు అంగీకరించండి."),
    },
    "payout_paid": {
        "en": ("Payout sent", "{amount} sent to your bank account for {period}."),
        "hi": ("भुगतान भेजा गया", "{period} के लिए {amount} आपके बैंक खाते में भेजे गए।"),
        "te": ("చెల్లింపు పంపాం", "{period}కి {amount} మీ బ్యాంక్ ఖాతాకు పంపాం."),
    },
}

# "1 item" / "3 items"
ITEMS = {"en": ("{n} item", "{n} items"), "hi": ("{n} आइटम", "{n} आइटम"), "te": ("{n} ఐటమ్", "{n} ఐటమ్స్")}

EMAIL_FOOTER = {
    "en": "BhojanGo · The honest table. These emails are about your BhojanGo orders.",
    "hi": "BhojanGo · असली खाना, सच्चा दाम। ये ईमेल आपके ऑर्डर के बारे में हैं।",
    "te": "BhojanGo · అసలైన రుచి, న్యాయమైన ధర. ఈ ఈమెయిల్స్ మీ ఆర్డర్‌ల గురించి.",
}
EMAIL_TOTAL = {"en": "Total", "hi": "कुल", "te": "మొత్తం"}
EMAIL_ORDER = {"en": "Order", "hi": "ऑर्डर", "te": "ఆర్డర్"}


@dataclass(frozen=True)
class Rendered:
    key: str
    language: str
    title: str
    body: str
    params: dict[str, str]  # the placeholder values (DLT variables)

    @property
    def sms(self) -> str:
        return f"BhojanGo: {self.body}"

    @property
    def dlt_template(self) -> str:
        return f"{self.key}_{self.language}"


def language_for(locale: str | None) -> str:
    """hi-IN → hi, te-IN → te, anything else → en."""
    lang = (locale or "en").split("-")[0].lower()
    return lang if lang in LANGUAGES else "en"


def render(key: str, language: str, **params: object) -> Rendered:
    """Fill a message. ``eta`` (a formatted time) becomes the "Arriving around"
    sentence; without it the sentence is left out."""
    language = language if language in LANGUAGES else "en"
    texts = CATALOGUE[key]
    title, body = texts.get(language, texts["en"])
    values = {k: str(v) for k, v in params.items() if v is not None}
    if isinstance(params.get("items"), int):
        one, many = ITEMS[language]
        values["items"] = (one if params["items"] == 1 else many).format(n=params["items"])
    values["arriving"] = ARRIVING[language].format(eta=values["eta"]) if values.get("eta") else ""
    used = {k: values.get(k, "") for k in _placeholders(title + body)}
    filled_title, filled_body = title.format(**used), body.format(**used)
    return Rendered(key, language, filled_title.strip(), " ".join(filled_body.split()), used)


def _placeholders(text: str) -> list[str]:
    import string

    return [f for _, f, _, _ in string.Formatter().parse(text) if f]


# ── formatting ────────────────────────────────────────────────────────────────

SYMBOL = {"INR": "₹", "USD": "$"}


def money(amount: Decimal | float | str, currency: str) -> str:
    """₹1,24,050.00 (Indian grouping) or $1,240.50."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if value < 0 else ""
    whole, cents = f"{abs(value):.2f}".split(".")
    if currency == "INR" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + groups + [tail])
    else:
        whole = f"{int(whole):,}"
    return f"{sign}{SYMBOL.get(currency, currency + ' ')}{whole}.{cents}"


def minor_to_money(minor: int | str, currency: str) -> str:
    return money(Decimal(int(minor)) / 100, currency)


def clock(at: datetime | str | None, timezone: str) -> str | None:
    """8:24 PM in the city's time."""
    if not at:
        return None
    when = datetime.fromisoformat(at) if isinstance(at, str) else at
    local = when.astimezone(ZoneInfo(timezone))
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def order_code(order_id: str) -> str:
    return "#" + order_id.replace("-", "")[:6].upper()


def period(start: date, end_exclusive: date) -> str:
    """3–9 Nov (the run's end date is exclusive)."""
    from datetime import timedelta

    last = end_exclusive - timedelta(days=1)
    if start.month == last.month:
        return f"{start.day}–{last.day} {last.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')} – {last.day} {last.strftime('%b')}"


def email_html(r: Rendered, *, total: str | None = None, code: str | None = None) -> str:
    """The brand email: Peacock heading, the message, an optional total line."""
    esc = html.escape
    rows = ""
    if total:
        rows = (f'<tr><td style="padding:12px 0 0;color:#4C5A5E">{esc(EMAIL_ORDER[r.language])} {esc(code or "")}</td>'
                f'<td style="padding:12px 0 0;text-align:right;font-weight:700">{esc(EMAIL_TOTAL[r.language])} {esc(total)}</td></tr>')
    return f"""<!doctype html><html lang="{r.language}"><body style="margin:0;background:#F4F6F6">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6F6;padding:24px 12px">
<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="max-width:520px;background:#FFFFFF;border-radius:16px;padding:28px;font-family:'Hanken Grotesk',
 'Noto Sans Devanagari','Noto Sans Telugu',Arial,sans-serif;color:#111418">
<tr><td colspan="2" style="font-size:20px;font-weight:700;color:#0B5D66;padding-bottom:16px">bhojango</td></tr>
<tr><td colspan="2" style="font-size:24px;font-weight:700;padding-bottom:8px">{esc(r.title)}</td></tr>
<tr><td colspan="2" style="font-size:16px;line-height:1.5">{esc(r.body)}</td></tr>
{rows}
<tr><td colspan="2" style="font-size:12px;color:#4C5A5E;padding-top:24px">{esc(EMAIL_FOOTER[r.language])}</td></tr>
</table></td></tr></table></body></html>"""
