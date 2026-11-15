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
