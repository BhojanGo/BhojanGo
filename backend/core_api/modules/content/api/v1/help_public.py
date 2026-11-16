"""The Help centre on the website (round 8, F9). Public, read-mostly.

  GET  /help                    topics with counts and the popular articles
  GET  /help/topics/{topic}     a topic's articles
  GET  /help/search?q=          full-text search (as you type)
  GET  /help/articles/{slug}    one article, with related articles
  POST /help/votes              "Was this helpful?" (anonymous, rate-limited)
  POST /help/contact            the contact form for people not signed in (a support ticket)
  POST /help/messages           a signed-in customer writes to support (a support ticket)

Every read takes the visitor's ``country`` (IN, US; none = articles for every
country only) and ``language`` (en, hi, ...): see service/help.py for the fallback.
"""
import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.content.models import TOPICS, HelpArticle
from core_api.modules.content.service import help as svc
from shared.client_ip import client_ip
from shared.db import get_db

router = APIRouter(prefix="/help", tags=["Help"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
limiter = Limiter(key_func=client_ip)
Country = Annotated[str | None, Query(max_length=2, description="The visitor's country (IN, US)")]
Language = Annotated[str | None, Query(max_length=5, description="The visitor's language (en, hi, es, ...)")]
Topic = Literal["orders", "payments-refunds", "delivery", "account", "kitchen-partners", "delivery-partners"]


class ArticleCard(BaseModel):
    slug: str
    topic: str
    title: str
    summary: str
    language: str
    country: str


class TopicCount(BaseModel):
    topic: str
    count: int


class HelpHome(BaseModel):
    topics: list[TopicCount]
    popular: list[ArticleCard]


class TopicPage(BaseModel):
    topic: str
    articles: list[ArticleCard]


class SearchResults(BaseModel):
    query: str
    results: list[ArticleCard]


class Article(ArticleCard):
    id: uuid.UUID
    body: str
    updated_at: datetime
    related: list[ArticleCard]
    # True when it isn't in the language asked for (the page says "not yet in your language")
    fallback: bool


def card(a: HelpArticle) -> ArticleCard:
    return ArticleCard(slug=a.slug, topic=a.topic, title=a.title, summary=a.summary, language=a.language, country=a.country)


@router.get("", response_model=HelpHome)
async def help_home(db: DB, country: Country = None, language: Language = None) -> HelpHome:
    best = await svc.visible(db, svc.norm_country(country), svc.norm_language(language))
    return HelpHome(topics=[TopicCount(**t) for t in svc.topic_counts(best)], popular=[card(a) for a in svc.popular(best)])


@router.get("/topics/{topic}", response_model=TopicPage)
async def help_topic(topic: str, db: DB, country: Country = None, language: Language = None) -> TopicPage:
    if topic not in TOPICS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NO_TOPIC", "message": "No such help topic"})
    best = await svc.visible(db, svc.norm_country(country), svc.norm_language(language))
    return TopicPage(topic=topic, articles=[card(a) for a in svc.ordered([a for a in best.values() if a.topic == topic])])


@router.get("/search", response_model=SearchResults)
async def help_search(db: DB, q: str = Query("", max_length=200), country: Country = None, language: Language = None,
                      limit: int = Query(10, ge=1, le=25)) -> SearchResults:
    found = await svc.search(db, q, svc.norm_country(country), svc.norm_language(language), limit)
    return SearchResults(query=q, results=[card(a) for a in found])


@router.get("/articles/{slug}", response_model=Article)
async def help_article(slug: str, db: DB, country: Country = None, language: Language = None) -> Article:
    lang = svc.norm_language(language)
    best = await svc.visible(db, svc.norm_country(country), lang)
    a = best.get(slug)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NO_ARTICLE", "message": "No such help article"})
    related = [best[s] for s in (a.related or []) if s in best and s != slug]
    if len(related) < 3:  # top up from the same topic
        related += [b for b in svc.ordered([b for b in best.values() if b.topic == a.topic])
                    if b.slug != slug and b not in related][: 3 - len(related)]
    return Article(**card(a).model_dump(), id=a.id, body=a.body, updated_at=a.updated_at,
                   related=[card(r) for r in related[:5]], fallback=a.language != lang)


class VoteIn(BaseModel):
    article_id: uuid.UUID
    helpful: bool
    voter: str = Field("", max_length=64, description="A random id the browser keeps, so a second click changes the vote")


@router.post("/votes", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute;100/day")
async def help_vote(request: Request, data: VoteIn, db: DB) -> dict:
    """Anonymous: we keep a hash of the browser's random id, never who it is."""
    a = await db.get(HelpArticle, data.article_id)
    if a is None or a.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NO_ARTICLE", "message": "No such help article"})
    await svc.vote(db, a, svc.voter_key(data.voter, client_ip(request)), data.helpful)
    return {"ok": True}


URL = re.compile(r"https?://|www\.", re.I)


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    topic: Topic
    message: str = Field(min_length=10, max_length=2000)
    country: str | None = Field(default=None, max_length=2)
    city: str | None = Field(default=None, max_length=20, description="The visitor's city code, when the website knows it")
    language: str | None = Field(default=None, max_length=5)
    website: str = Field("", max_length=200, description="Leave empty (a field people never see; bots fill it in)")


class ContactOut(BaseModel):
    ok: bool


async def _city(db: AsyncSession, code: str | None, country: str | None) -> str | None:
    from core_api.modules.markets.models import City

    if not code or not country or not code.upper().startswith(country + "-"):
        return None
    return (await db.execute(select(City.code).where(City.code == code.upper()))).scalar_one_or_none()


@router.post("/contact", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute;10/day")
async def help_contact(request: Request, data: ContactIn, db: DB) -> ContactOut:
    """The Help contact form, for someone who isn't signed in: a support ticket
    for the country (or their city) that support answers by email. Bots that
    fill in the hidden field, or messages that are mostly links, are thanked
    and dropped."""
    from core_api.modules.support.models import SupportTicket

    if data.website.strip() or len(URL.findall(data.message)) > 2:
        return ContactOut(ok=True)
    country = svc.norm_country(data.country)
    if country is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "COUNTRY", "message": "Pick the country you're asking about"})
    db.add(SupportTicket(kind="contact", status="open", market_city=await _city(db, data.city, country), country=country,
                         requester_id=None, requester_role="visitor", topic=data.topic, note=data.message.strip()[:500],
                         details={"name": data.name.strip(), "email": str(data.email).lower(), "message": data.message.strip(),
                                  "language": svc.norm_language(data.language)}))
    await db.flush()
    return ContactOut(ok=True)


class MessageIn(BaseModel):
    topic: Topic
    message: str = Field(min_length=10, max_length=2000)
    order_id: uuid.UUID | None = None
    language: str | None = Field(default=None, max_length=5)


class MessageOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime


@router.post("/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute;30/day")
async def help_message(request: Request, data: MessageIn, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> MessageOut:
    """A signed-in customer writes to support from Help, about one of their
    orders or not. The ticket goes to the order's city (else their country)."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.support.models import SupportTicket

    order = None
    if data.order_id:
        order = await db.get(Order, data.order_id)
        if order is None or order.customer_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    city = order.market_city if order else None
    t = SupportTicket(kind="message", status="open", market_city=city, country=(city or user.country or "US")[:2],
                      requester_id=user.id, requester_role="customer", restaurant_id=order.restaurant_id if order else None,
                      order_id=order.id if order else None, topic=data.topic, note=data.message.strip()[:500],
                      details={"message": data.message.strip(), "language": svc.norm_language(data.language)})
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return MessageOut(id=t.id, status=t.status, created_at=t.created_at)
