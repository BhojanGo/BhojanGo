import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Level = Literal["platform", "country", "region", "city", "zone", "restaurant"]


class RuleCreate(BaseModel):
    family: str = Field(examples=["customer_fee"])
    template: str = Field(examples=["service_fee"])
    key: str | None = Field(default=None, description="Only when several rules of one template apply together, e.g. gst_food")
    name: str | None = Field(default=None, max_length=120)
    params: dict[str, Any]
    scope_level: Level
    scope_id: str = Field(description='"*" for platform; IN / IN-TG / IN-TG-HYD; a zone or restaurant id')
    priority: int = 0
    locked: bool = Field(default=False, description="Can't be overridden below this level")
    effective_from: datetime | None = Field(default=None, description="Start; defaults to when it is published")
    effective_to: datetime | None = Field(default=None, description="End (optional); after it, the inherited rule applies again")


class RuleUpdate(BaseModel):
    name: str | None = None
    params: dict[str, Any] | None = None
    priority: int | None = None
    locked: bool | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class NewVersion(BaseModel):
    params: dict[str, Any] | None = None
    name: str | None = None
    effective_from: datetime | None = None


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class Rejection(BaseModel):
    note: str = Field(min_length=3, max_length=500)


class EndRule(BaseModel):
    at: datetime | None = None


class RuleOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    rule_key: uuid.UUID
    version: int
    family: str
    template: str
    key: str | None
    slot: str
    name: str | None
    params: dict[str, Any]
    scope_level: str
    scope_id: str
    market_scope: str
    priority: int
    locked: bool
    status: str
    effective_from: datetime
    effective_to: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    money: bool = False
    paused_at: datetime | None = None
    paused_reason: str | None = None


class ApprovalOut(BaseModel):
    model_config = {"from_attributes": True}

    requested_by: uuid.UUID
    requested_at: datetime
    decision: str | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    note: str | None


class AuditOut(BaseModel):
    model_config = {"from_attributes": True}

    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str
    scope: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    at: datetime


class RuleHistory(BaseModel):
    versions: list[RuleOut]
    approvals: dict[str, list[ApprovalOut]]
    audit: list[AuditOut]


class ResolvedRule(BaseModel):
    slot: str
    rule_id: uuid.UUID
    rule_key: uuid.UUID
    version: int
    family: str
    template: str
    name: str | None
    params: dict[str, Any]
    scope_level: str
    scope_id: str
