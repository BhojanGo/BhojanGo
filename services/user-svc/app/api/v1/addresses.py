import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.address import Address
from app.models.user import User

router = APIRouter(prefix="/me/addresses", tags=["Addresses"])


class AddressCreate(BaseModel):
    label: str = Field(default="Home", max_length=50)
    street: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="US", max_length=2)


class AddressResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    label: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str


@router.get("", response_model=list[AddressResponse])
async def list_addresses(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AddressResponse]:
    result = await db.execute(
        select(Address).where(Address.user_id == current_user.id).order_by(Address.created_at)
    )
    return [AddressResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    address = Address(
        user_id=current_user.id,
        label=data.label or "Home",
        street=data.street,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        country=data.country,
    )
    db.add(address)
    await db.flush()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    await db.delete(address)
