from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order

NOT_CANCELLABLE = {"shipped", "delivered"}


class OrderNotFound(Exception):
    pass


class OrderNotCancellable(Exception):
    pass


async def cancel_order(
    session: AsyncSession,
    order_id: int,
    user_id: int,
) -> Order:
    order = await session.get(Order, order_id)

    if order is None or order.owner_id != user_id:
        raise OrderNotFound

    if order.status in NOT_CANCELLABLE:
        raise OrderNotCancellable

    if order.status != "cancelled":
        order.status = "cancelled"
        await session.commit()

    return order
