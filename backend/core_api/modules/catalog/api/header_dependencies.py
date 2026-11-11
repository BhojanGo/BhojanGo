from typing import Annotated
from fastapi import Depends, HTTPException, Request, status

async def require_admin(request: Request) -> None:
    """Verify the request comes from an admin user.
    In production, this validates the JWT claims forwarded by Kong.
    """
    # Kong forwards decoded JWT claims as headers
    role = request.headers.get("X-User-Role", "")
    if role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

async def require_restaurant_owner(request: Request) -> None:
    """Verify the request comes from a restaurant owner or admin."""
    role = request.headers.get("X-User-Role", "")
    if role not in ("restaurant_owner", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant owner access required",
        )
