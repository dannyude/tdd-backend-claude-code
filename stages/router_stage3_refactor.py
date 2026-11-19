from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.deps import get_current_user_id
from app.models import Order
from app.schemas import OrderOut
from app.services.orders import (
    OrderNotCancellable,
    OrderNotFound,
    cancel_order,
)

router = APIRouter(tags=["orders"])


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order_endpoint(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Order:
    try:
        return await cancel_order(session, order_id, user_id)

    except OrderNotFound:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        ) from None

    except OrderNotCancellable:
        raise HTTPException(
            status_code=409,
            detail={"code": "ORDER_NOT_CANCELLABLE"},
        ) from None
