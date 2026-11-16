"""The photo a kitchen is shown with (R8): ``photo_url`` on every public kitchen
(discover cards, the kitchen's page, favourites, search).

A kitchen's own cover first; a kitchen without one is shown with its first dish
that has a photo (menu order), else a photo of its cuisine from the food photo
library (the website's /food/<slug>-<width>.webp), else nothing: the website and
the apps then draw a plain branded tile (never initials over text). ``cover_url``
stays the kitchen's own photo only (what the kitchen app edits).

The cuisine map is matched on words of the kitchen's cuisines, in the kitchen's
order ("Mexican, Burritos, Bowls" -> tacos), so it works for any city's names;
a cuisine nobody mapped gets no photo rather than a wrong one. Every slug must
be in the library (tests/test_photos.py checks it against photo_library.json).
"""
import re
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# (words in a cuisine's name, library slug): first match wins, so specific words come first.
CUISINE_PHOTOS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("biryani", "hyderabadi"), "hyderabadi-chicken-biryani"),
    (("haleem", "mughlai"), "haleem"),
    (("dosa", "south", "tiffin", "tiffins", "kerala", "udupi", "chettinad"), "masala-dosa"),
    (("idli",), "idli-sambar"),
    (("vada",), "vada"),
    (("thali", "meals", "andhra", "gujarati", "rajasthani"), "south-indian-thali"),
    (("tandoor", "tandoori", "kebab", "kebabs", "grill"), "tandoori-chicken"),
    (("punjabi", "butter"), "butter-chicken"),
    (("chaat", "street"), "pani-puri"),
    (("snacks", "samosa"), "samosa"),
    (("sweets", "desserts", "dessert", "mithai"), "gulab-jamun"),
    (("lassi", "juice", "juices", "shakes"), "mango-lassi"),
    (("irani", "chai", "tea"), "irani-chai"),
    (("coffee", "cafe", "café", "bakery"), "latte"),
    (("breakfast", "brunch", "pancakes", "diner"), "pancakes"),
    (("pizza", "italian"), "margherita-pizza"),
    (("burger", "burgers", "american", "comfort"), "cheeseburger"),
    (("fried", "fries"), "fries"),
    (("bbq", "barbecue", "smokehouse", "ribs"), "bbq-ribs"),
    (("mexican", "tacos", "taco", "burrito", "burritos", "tex-mex"), "tacos"),
    (("sushi", "japanese"), "sushi"),
    (("ramen", "noodles", "chinese", "indo-chinese", "thai", "asian", "momos", "nepalese", "korean", "vietnamese"), "ramen"),
    (("poke", "bowls", "bowl", "healthy", "hawaiian"), "poke-bowl"),
    (("salad", "salads", "mediterranean", "middle", "vegan"), "caesar-salad"),
    (("veg", "vegetarian", "north", "indian", "curry"), "paneer-butter-masala"),
)

LIBRARY_WIDTH = 800  # the website serves 400, 800 and 1600; the clients resize by the name


def library_url(slug: str, width: int = LIBRARY_WIDTH) -> str:
    return f"/food/{slug}-{width}.webp"


def _words(name: str) -> set[str]:
    return set(re.split(r"[^\w-]+", name.lower())) - {""}


def cuisine_photo(cuisines: Iterable[str] | None) -> str | None:
    """A library photo for the first of the kitchen's cuisines that has one."""
    for name in cuisines or ():
        words = _words(name)
        for keys, slug in CUISINE_PHOTOS:
            if words & set(keys):
                return library_url(slug)
    return None


def display_photo(cover_url: str | None, first_dish: str | None, cuisines: Sequence[str] | None) -> str | None:
    """The kitchen's own cover, else its first dish photo, else its cuisine's library photo."""
    return cover_url or first_dish or cuisine_photo(cuisines)


async def first_dish_photos(db: AsyncSession, ids: Iterable[uuid.UUID | str]) -> dict[str, str]:
    """Each kitchen's first available dish with a photo (menu order), by kitchen id."""
    from core_api.modules.catalog.models.menu import MenuItem

    keys = [i if isinstance(i, uuid.UUID) else uuid.UUID(str(i)) for i in ids]
    if not keys:
        return {}
    rows = (await db.execute(
        select(MenuItem.restaurant_id, MenuItem.image_url)
        .where(MenuItem.restaurant_id.in_(keys), MenuItem.image_url.is_not(None), MenuItem.image_url != "",
               MenuItem.deleted_at.is_(None), MenuItem.is_available.is_(True))
        .order_by(MenuItem.restaurant_id, MenuItem.sort_order, MenuItem.name))).all()
    out: dict[str, str] = {}
    for rid, url in rows:
        out.setdefault(str(rid), url)
    return out


async def photos_for(db: AsyncSession, kitchens: Sequence) -> dict[str, str | None]:  # type: ignore[type-arg]
    """``photo_url`` for each kitchen (anything with id, cover_url, cuisine_types), by id;
    the menu is read only for kitchens without a cover of their own."""
    bare = [k.id for k in kitchens if not k.cover_url]
    dishes = await first_dish_photos(db, bare) if bare else {}
    return {str(k.id): display_photo(k.cover_url, dishes.get(str(k.id)), list(k.cuisine_types or [])) for k in kitchens}
