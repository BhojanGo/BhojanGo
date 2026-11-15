import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user
from core_api.modules.identity.service.addresses import make_default, promote_newest
from shared.db import get_db
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.user import User

router = APIRouter(prefix="/me/addresses", tags=["Addresses"])


class AddressCreate(BaseModel):
    label: str = Field(default="Home", max_length=50)
    street: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="US", max_length=2)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    delivery_notes: str | None = Field(default=None, max_length=500)
    # The first address is always the default; later ones only when asked.
    is_default: bool = False


class AddressUpdate(BaseModel):
    """Any field; only the ones sent change. lat/lng/delivery_notes may be null."""

    label: str | None = Field(default=None, max_length=50)
    street: str | None = Field(default=None, min_length=1, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=2)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    delivery_notes: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None

    @model_validator(mode="after")
    def _required_stay_set(self) -> "AddressUpdate":
        for name in ("label", "street", "city", "state", "postal_code", "country", "is_default"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self


class AddressResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    label: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    lat: float | None = None
    lng: float | None = None
    delivery_notes: str | None = None
    is_default: bool = False


async def _own(db: AsyncSession, user: User, address_id: uuid.UUID) -> Address:
    result = await db.execute(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    return address


@router.get("", response_model=list[AddressResponse])
async def list_addresses(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[AddressResponse]:
    result = await db.execute(
        select(Address).where(Address.user_id == current_user.id).order_by(Address.created_at)
    )
    return [AddressResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AddressResponse:
    has_any = (await db.execute(select(Address.id).where(Address.user_id == current_user.id).limit(1))).first()
    address = Address(
        user_id=current_user.id,
        label=data.label or "Home",
        street=data.street,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        country=data.country,
        lat=data.lat,
        lng=data.lng,
        delivery_notes=data.delivery_notes,
        is_default=False,
    )
    db.add(address)
    await db.flush()
    if data.is_default or not has_any:
        await make_default(db, address)
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.patch("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: uuid.UUID,
    data: AddressUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AddressResponse:
    """Change any field of one of your addresses."""
    address = await _own(db, current_user, address_id)
    changes = data.model_dump(exclude_unset=True)
    want_default = changes.pop("is_default", None)
    if want_default is False and address.is_default:
        # Exactly one default: move it by making another address the default.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "DEFAULT_REQUIRED", "message": "Make another address the default instead"})
    for k, v in changes.items():
        setattr(address, k, v)
    await db.flush()
    if want_default:
        await make_default(db, address)
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.post("/{address_id}/default", response_model=AddressResponse)
async def set_default_address(
    address_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AddressResponse:
    """Make this your default address (the one checkout picks first)."""
    address = await _own(db, current_user, address_id)
    await make_default(db, address)
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    address = await _own(db, current_user, address_id)
    was_default = address.is_default
    await db.delete(address)
    await db.flush()
    if was_default:
        await promote_newest(db, current_user.id)
