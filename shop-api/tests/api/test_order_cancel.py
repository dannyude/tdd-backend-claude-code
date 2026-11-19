from unittest.mock import AsyncMock, patch

from app.models import Order

AUTH = {"X-User-Id": "1"}


# Helper: create an order for testing
async def make_order(session, owner_id=1, status="pending"):
    order = Order(owner_id=owner_id, status=status)
    session.add(order)
    await session.flush()  # assigns order.id without committing
    return order


# An authenticated owner can cancel a pending order
async def test_owner_cancels_pending_order(client, session):
    order = await make_order(session)
    r = await client.post(f"/orders/{order.id}/cancel", headers=AUTH)

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    await session.refresh(order)
    assert order.status == "cancelled"


# Cancelling a shipped order returns a conflict
async def test_cancel_shipped_order_conflicts(client, session):
    order = await make_order(session, status="shipped")
    r = await client.post(f"/orders/{order.id}/cancel", headers=AUTH)

    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "ORDER_NOT_CANCELLABLE"


# A user cannot cancel another user's order.
# Return 404 to avoid revealing that the order exists.
async def test_cancel_other_users_order_not_found(client, session):
    order = await make_order(session, owner_id=2)
    r = await client.post(f"/orders/{order.id}/cancel", headers=AUTH)

    assert r.status_code == 404
    assert r.json()["detail"] == "Order not found"


# Cancelling a nonexistent order returns 404
async def test_cancel_missing_order_not_found(client):
    r = await client.post("/orders/999999/cancel", headers=AUTH)

    assert r.status_code == 404
    assert r.json()["detail"] == "Order not found"


# Cancelling an order requires authentication
async def test_cancel_requires_auth(client, session):
    order = await make_order(session)
    r = await client.post(f"/orders/{order.id}/cancel")

    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


# Cancelling an already-cancelled order is idempotent
async def test_cancel_twice_is_idempotent(client, session):
    order = await make_order(session)

    with patch.object(
        session,
        "commit",
        new_callable=AsyncMock,
        wraps=session.commit,
    ) as commit:
        first = await client.post(
            f"/orders/{order.id}/cancel",
            headers=AUTH,
        )
        second = await client.post(
            f"/orders/{order.id}/cancel",
            headers=AUTH,
        )

    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "cancelled"
    assert commit.await_count == 1


# Delivered orders cannot be cancelled either
async def test_cancel_delivered_order_conflicts(client, session):
    order = await make_order(session, status="delivered")
    r = await client.post(f"/orders/{order.id}/cancel", headers=AUTH)

    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "ORDER_NOT_CANCELLABLE"


# Found by Schemathesis: 2**63 is a valid Python int,
# but not a valid order id
async def test_cancel_order_with_oversized_id_returns_422(client):
    response = await client.post(
        "/orders/9223372036854775808/cancel",
        headers=AUTH,
    )

    assert response.status_code == 422
