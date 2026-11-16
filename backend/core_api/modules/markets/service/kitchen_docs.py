"""The documents a kitchen needs to join, per country: Markets country setting
``kitchen_documents`` (admin: Markets -> country -> "Documents kitchens need").

    [{"key": "fssai", "title": {"en": "FSSAI licence", "hi": "..."},
      "why": {"en": "Every kitchen that sells food in India needs one.", "hi": "..."}}, ...]

Titles and reasons are per language (English required; the website falls back to
it). A country with none set shows a neutral "we'll tell you what's needed".
"""
import re
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "kitchen_documents"
MAX_DOCS = 12
KEY = re.compile(r"^[a-z0-9_]{2,30}$")
LANG = re.compile(r"^[a-z]{2}$")
LIMITS = {"title": 80, "why": 240}


def check_settings(settings: dict[str, Any] | None) -> None:
    """Refuse a malformed list (None clears it)."""
    value = (settings or {}).get(SETTING)
    if value is None:
        return
    if not isinstance(value, list) or len(value) > MAX_DOCS:
        raise MarketRuleError(f"{SETTING} is a list of at most {MAX_DOCS} documents")
    seen: set[str] = set()
    for doc in value:
        if not isinstance(doc, dict) or not isinstance(doc.get("key"), str) or not KEY.match(doc["key"]):
            raise MarketRuleError("Each document needs a key: lower-case letters, digits or _ (e.g. fssai)")
        if doc["key"] in seen:
            raise MarketRuleError(f"Document {doc['key']} is listed twice")
        seen.add(doc["key"])
        for part, limit in LIMITS.items():
            texts = doc.get(part)
            if not isinstance(texts, dict) or not str(texts.get("en") or "").strip():
                raise MarketRuleError(f"Document {doc['key']}: the {part} needs English text")
            for lang, text in texts.items():
                if not LANG.match(str(lang)) or not isinstance(text, str) or len(text) > limit:
                    raise MarketRuleError(f"Document {doc['key']}: each {part} is text of at most {limit} characters per language")


def localized(settings: dict[str, Any] | None, language: str) -> list[dict[str, str]]:
    """The country's documents in this language (English where a text isn't translated)."""
    out = []
    for doc in (settings or {}).get(SETTING) or []:
        if not isinstance(doc, dict):
            continue
        title, why = doc.get("title") or {}, doc.get("why") or {}
        out.append({"key": str(doc.get("key", "")), "title": str(title.get(language) or title.get("en") or ""),
                    "why": str(why.get(language) or why.get("en") or "")})
    return [d for d in out if d["title"]]
