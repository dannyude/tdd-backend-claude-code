from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.deps import get_current_user_id
from app.models import Order
from app.schemas import OrderOut

router = APIRouter(tags=["orders"])

NOT_CANCELLABLE = {"shipped", "delivered"}


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Order:
    order = await session.get(Order, order_id)

    if order is None or order.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in NOT_CANCELLABLE:
        raise HTTPException(
            status_code=409,
            detail={"code": "ORDER_NOT_CANCELLABLE"},
        )

    if order.status != "cancelled":
        order.status = "cancelled"
        await session.commit()

    return order
