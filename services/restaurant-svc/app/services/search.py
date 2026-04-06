"""OpenSearch integration for restaurant and menu item search."""
from typing import Any

import structlog
from opensearchpy import AsyncOpenSearch

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_client: AsyncOpenSearch | None = None


def get_opensearch() -> AsyncOpenSearch:
    global _client
    if _client is None:
        _client = AsyncOpenSearch(
            hosts=[settings.OPENSEARCH_URL],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
        )
    return _client


async def ensure_indices() -> None:
    client = get_opensearch()
    restaurant_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text", "analyzer": "standard"},
                "description": {"type": "text"},
                "cuisine_types": {"type": "keyword"},
                "city": {"type": "keyword"},
                "country": {"type": "keyword"},
                "rating": {"type": "float"},
                "is_open": {"type": "boolean"},
                "delivery_fee": {"type": "float"},
                "location": {"type": "geo_point"},
                "tags": {"type": "keyword"},
            }
        }
    }
    if not await client.indices.exists(index=settings.OPENSEARCH_INDEX_RESTAURANTS):
        await client.indices.create(
            index=settings.OPENSEARCH_INDEX_RESTAURANTS, body=restaurant_mapping
        )


async def index_restaurant(restaurant_id: str, doc: dict[str, Any]) -> None:
    try:
        client = get_opensearch()
        await client.index(
            index=settings.OPENSEARCH_INDEX_RESTAURANTS,
            id=restaurant_id,
            body=doc,
        )
    except Exception as e:
        logger.error("opensearch_index_failed", restaurant_id=restaurant_id, error=str(e))


async def search_restaurants(
    q: str | None = None,
    city: str | None = None,
    cuisine: str | None = None,
    min_rating: float | None = None,
    is_open: bool | None = None,
    page: int = 1,
    limit: int = 20,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    client = get_opensearch()
    must: list[dict] = []
    filters: list[dict] = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "fields": ["name^3", "description", "cuisine_types^2", "tags"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })

    if city:
        filters.append({"term": {"city": city.lower()}})
    if cuisine:
        filters.append({"term": {"cuisine_types": cuisine}})
    if min_rating is not None:
        filters.append({"range": {"rating": {"gte": min_rating}}})
    if is_open is not None:
        filters.append({"term": {"is_open": is_open}})

    query: dict[str, Any] = {
        "bool": {
            "must": must if must else [{"match_all": {}}],
            "filter": filters,
        }
    }

    sort: list[Any] = [{"_score": "desc"}, {"rating": "desc"}]
    if lat and lng:
        sort.insert(0, {"_geo_distance": {"location": {"lat": lat, "lon": lng}, "order": "asc"}})

    body = {
        "query": query,
        "sort": sort,
        "from": (page - 1) * limit,
        "size": limit,
    }

    try:
        result = await client.search(index=settings.OPENSEARCH_INDEX_RESTAURANTS, body=body)
        hits = result["hits"]
        return {
            "total": hits["total"]["value"],
            "ids": [hit["_id"] for hit in hits["hits"]],
        }
    except Exception as e:
        logger.error("opensearch_search_failed", error=str(e))
        return {"total": 0, "ids": []}
