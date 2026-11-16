"""The photo a kitchen is shown with (R8): its cover, else its first dish photo,
else its cuisine's library photo, else none (the clients draw a branded tile)."""
import json
from pathlib import Path

from core_api.modules.catalog.service.photos import CUISINE_PHOTOS, cuisine_photo, display_photo, library_url

LIBRARY = set(json.loads((Path(__file__).resolve().parents[2] / "markets" / "photo_library.json").read_text("utf-8")))


def test_every_mapped_photo_is_in_the_library():
    assert {slug for _, slug in CUISINE_PHOTOS} <= LIBRARY


def test_own_cover_first_then_a_dish_then_the_cuisine():
    assert display_photo("/food/sushi-800.webp", "/food/ramen-800.webp", ["Mexican"]) == "/food/sushi-800.webp"
    assert display_photo(None, "/food/ramen-800.webp", ["Mexican"]) == "/food/ramen-800.webp"
    assert display_photo(None, None, ["Mexican", "Burritos", "Bowls"]) == library_url("tacos")
    assert display_photo("", "", ["Basque", "Spanish"]) is None  # nobody mapped it: no wrong photo


def test_cuisines_match_on_words_in_the_kitchens_order():
    assert cuisine_photo(["Hyderabadi", "Biryani"]) == library_url("hyderabadi-chicken-biryani")
    assert cuisine_photo(["South Indian", "Dosa"]) == library_url("masala-dosa")  # "South" is a dosa kitchen before it is "Indian"
    assert cuisine_photo(["Andhra", "Thali"]) == library_url("south-indian-thali")
    assert cuisine_photo(["American", "Comfort"]) == library_url("cheeseburger")
    assert cuisine_photo(["Pizza", "Italian"]) == library_url("margherita-pizza")
    assert cuisine_photo(["Irani Cafe", "Snacks"]) == library_url("irani-chai")
    assert cuisine_photo(["Indo-Chinese"]) == library_url("ramen")
    assert cuisine_photo(["Spanish", "Healthy"]) == library_url("poke-bowl")  # the first cuisine with a photo
    assert cuisine_photo([]) is None and cuisine_photo(None) is None


def test_a_cuisine_photo_is_one_photo_at_any_width():
    from core_api.modules.catalog.api.v1.discover import pick_cuisine_photos

    got = pick_cuisine_photos(["Mexican", "Tacos"], {
        "Mexican": ["/food/tacos-1600.webp"],
        "Tacos": ["/food/tacos-800.webp", "/food/bbq-ribs-800.webp"],
    })
    assert got == {"Mexican": "/food/tacos-1600.webp", "Tacos": "/food/bbq-ribs-800.webp"}
