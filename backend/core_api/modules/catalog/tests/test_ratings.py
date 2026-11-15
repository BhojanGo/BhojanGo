"""Public stars and the cuisine strip's photos (web v3)."""
from core_api.modules.catalog.api.v1.discover import pick_cuisine_photos
from core_api.modules.catalog.service.ratings import rating_display


def test_new_until_five_ratings() -> None:
    assert rating_display(4.9, 0).model_dump(exclude_none=True) == {"new": True}
    assert rating_display(4.9, 4).model_dump(exclude_none=True) == {"new": True}
    assert rating_display(4.6333, 23).model_dump() == {"new": False, "stars": 4.6, "count": 23}
    assert rating_display(None, None).new is True


def test_each_cuisine_gets_its_own_photo() -> None:
    got = pick_cuisine_photos(["Indian", "Biryani", "Chinese"], {
        "Indian": ["a.jpg", "b.jpg"],
        "Biryani": ["a.jpg"],  # only one fitting photo: it picks first and keeps it
        "Chinese": ["c.jpg"],
    })
    assert got == {"Biryani": "a.jpg", "Indian": "b.jpg", "Chinese": "c.jpg"}
    assert len(set(got.values())) == len(got)


def test_no_photo_left_means_none() -> None:
    got = pick_cuisine_photos(["Indian", "Biryani"], {"Indian": ["a.jpg"], "Biryani": ["a.jpg"]})
    assert list(got.values()) == ["a.jpg"] and len(got) == 1
    assert pick_cuisine_photos(["Thai"], {}) == {}


def test_preference_order_is_kept() -> None:
    # candidates come best first (other kitchens' covers, dish photos, then covers already on a card)
    assert pick_cuisine_photos(["Indian"], {"Indian": ["other-cover.jpg", "dish.jpg", "card-cover.jpg"]}) == {
        "Indian": "other-cover.jpg"}


def test_star_distribution_for_the_kitchen() -> None:
    from core_api.modules.catalog.service.ratings import distribution

    assert distribution([]) == [0, 0, 0, 0, 0]
    assert distribution([(5.0, 7), (4.0, 2), (1.0, 1)]) == [1, 0, 0, 2, 7]
    assert distribution([(4.6, 1), (0.0, 1), (9.0, 1)]) == [1, 0, 0, 0, 2]  # rounded, kept in 1..5


def test_kitchen_summary_says_new_like_customers_see_it() -> None:
    from datetime import UTC, datetime

    from core_api.modules.catalog.service.ratings import RecentComment, summarize

    new = summarize(4.8, 3, [0, 0, 0, 1, 2], [])
    assert new.rating_display.new is True and new.average == 4.8 and new.count == 3
    none = summarize(0, 0, [0, 0, 0, 0, 0], [])
    assert none.average is None and none.count == 0 and none.rating_display.new is True
    c = RecentComment(stars=5, comment="Lovely dal", created_at=datetime(2026, 11, 14, tzinfo=UTC))
    shown = summarize(4.6333, 23, [1, 0, 2, 5, 15], [c])
    assert shown.rating_display.model_dump() == {"new": False, "stars": 4.6, "count": 23}
    assert shown.average == 4.6 and shown.recent == [c] and "customer" not in RecentComment.model_fields
