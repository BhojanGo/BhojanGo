"""Help centre (F9): fallback order, search words, the draft/publish cycle and
the seed articles (tools/seed/help) themselves."""
import re
import uuid
from pathlib import Path

import pytest

from core_api.modules.content.models import GLOBAL, LANGUAGES, TOPICS, HelpArticle
from core_api.modules.content.service import help as svc

SEED = Path(__file__).resolve().parents[5] / "tools" / "seed" / "help"


def art(slug: str, country: str = GLOBAL, language: str = "en", **kw) -> HelpArticle:  # type: ignore[no-untyped-def]
    a = HelpArticle(id=uuid.uuid4(), slug=slug, country=country, language=language, topic=kw.get("topic", "orders"),
                    title=kw.get("title", slug), summary="", body="", status=kw.get("status", "published"),
                    popular=kw.get("popular", 0), related=[], draft=None, version=1)
    return a


def test_fallback_order_country_first_then_english_then_global() -> None:
    assert svc.preference("IN", "hi") == [("IN", "hi"), ("IN", "en"), ("*", "hi"), ("*", "en")]
    assert svc.preference("US", "en") == [("US", "en"), ("*", "en")]
    assert svc.preference(None, "es") == [("*", "es"), ("*", "en")]


def test_pick_best_per_slug() -> None:
    rows = [art("pay", "*", "en"), art("pay", "*", "hi"), art("pay", "IN", "en"), art("pin", "*", "en"), art("pin", "*", "hi"),
            art("docs", "US", "en"), art("other-country", "US", "es")]
    best = svc.pick_best(rows, "IN", "hi")
    assert (best["pay"].country, best["pay"].language) == ("IN", "en")  # the country's facts beat a global translation
    assert (best["pin"].country, best["pin"].language) == ("*", "hi")
    assert "docs" not in best and "other-country" not in best
    # A Telugu reader gets English where there is no Telugu.
    assert svc.pick_best(rows, "IN", "te")["pin"].language == "en"


def test_normalising_country_and_language() -> None:
    assert svc.norm_country("in") == "IN" and svc.norm_country("") is None and svc.norm_country("IND") is None
    assert svc.norm_language("hi-IN") == "hi" and svc.norm_language("xx") == "en" and svc.norm_language(None) == "en"


def test_prefix_query_is_safe_for_tsquery() -> None:
    assert svc.prefix_query("Refund late!") == "refund:* & late:*"
    assert svc.prefix_query("'); drop table x; --") == "drop:* & table:* & x:*"
    assert svc.prefix_query("  ") is None and svc.prefix_query("&|!") is None
    assert svc.prefix_query("रिफंड कब") == "रिफंड:* & कब:*"


def test_popular_and_topic_counts() -> None:
    best = svc.pick_best([art("a", popular=2), art("b", popular=1), art("c"), art("d", topic="delivery")], None, "en")
    assert [a.slug for a in svc.popular(best)] == ["b", "a"]
    counts = {t["topic"]: t["count"] for t in svc.topic_counts(best)}
    assert counts["orders"] == 3 and counts["delivery"] == 1 and set(counts) == set(TOPICS)


def test_published_article_keeps_live_text_until_published() -> None:
    a = art("x", title="Live title")
    svc.save(a, {"title": "New title"}, None)
    assert a.title == "Live title" and a.draft and a.draft["title"] == "New title"
    assert svc.working_copy(a)["title"] == "New title"
    svc.save(a, {"title": "Live title"}, None)  # saved back to the live text: nothing pending
    assert a.draft is None
    svc.save(a, {"body": "Fresh body"}, None)
    svc.publish(a, None)
    assert a.body == "Fresh body" and a.draft is None and a.status == "published" and a.published_at
    v = a.version
    svc.unpublish(a, None)
    assert a.status == "draft" and a.version == v + 1


def test_draft_article_changes_in_place() -> None:
    a = art("x", status="draft")
    svc.save(a, {"title": "Better", "related": ["y"]}, None)
    assert a.title == "Better" and a.related == ["y"] and a.draft is None


def test_parse_seed_rejects_bad_front_matter() -> None:
    good = "---\nslug: a-b\ntopic: orders\ncountry: *\ntitle: T\nsummary: S\npopular: 2\nrelated: c, d\n---\nBody\n"
    a = svc.parse_seed(good, "en")
    assert (a.slug, a.country, a.popular, a.related, a.body) == ("a-b", "*", 2, ["c", "d"], "Body\n")
    with pytest.raises(ValueError):
        svc.parse_seed(good.replace("topic: orders", "topic: food"), "en")
    with pytest.raises(ValueError):
        svc.parse_seed("no front matter", "en")


# ── the seed articles themselves ─────────────────────────────────────────────

BANNED = re.compile(r"\b(riders?|drivers?|couriers?|GOVT|partner app)\b", re.I)


def test_seed_articles_are_valid_and_linked() -> None:
    articles = svc.load_seed_dir(SEED)
    english = {(a.slug, a.country) for a in articles if a.language == "en"}
    slugs = {s for s, _ in english}
    assert len(slugs) >= 25
    assert {a.topic for a in articles} == set(TOPICS)
    for a in articles:
        assert a.language in LANGUAGES
        # every translation has an English original for the same country
        assert (a.slug, a.country) in english, (a.language, a.slug, a.country)
        assert set(a.related) <= slugs, (a.slug, set(a.related) - slugs)
        for link in re.findall(r"\]\((/[^)]*)\)", a.body):
            if link.startswith("/help/a/"):
                assert link.removeprefix("/help/a/") in slugs, (a.slug, link)
    for a in articles:
        if a.language == "en":
            assert not BANNED.search(a.title + " " + a.summary + " " + a.body), a.slug
    # Popular ones: unique order per country view
    pops = sorted(a.popular for a in articles if a.language == "en" and a.country in (GLOBAL, "IN") and a.popular)
    assert len(pops) == len(set(pops)) >= 6


def test_hindi_and_spanish_cover_their_countries() -> None:
    articles = svc.load_seed_dir(SEED)
    have = {(a.slug, a.country, a.language) for a in articles}
    for slug, country, lang in have:
        if lang != "en":
            continue
        if country in (GLOBAL, "IN"):
            assert (slug, country, "hi") in have, slug
        if country in (GLOBAL, "US"):
            assert (slug, country, "es") in have, slug
