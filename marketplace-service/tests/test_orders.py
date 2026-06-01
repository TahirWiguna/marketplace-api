import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.utils.deps import get_current_user


def make_user(prefix="user"):
    return {"id": str(uuid.uuid4()), "email": f"{prefix}@test.com", "username": prefix}


def override_db(db_session):
    async def _override():
        yield db_session
    return _override


def override_user(user):
    async def _override():
        return user
    return _override


async def _create_product(db_session, seller, stock=10, price="20.00"):
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(seller)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/products/",
            json={"name": f"Product-{uuid.uuid4().hex[:6]}", "description": "desc", "price": price, "stock": stock},
        )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved_overrides)
    return resp.json()


@pytest_asyncio.fixture
async def order_ctx(db_session):
    """Sets up a seller+product+buyer context; returns (buyer_client, product_id, seller_user, buyer_user)."""
    seller = make_user("seller")
    buyer = make_user("buyer")

    product = await _create_product(db_session, seller, stock=10)

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(buyer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, product["id"], seller, buyer

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_place_order(order_ctx):
    ac, product_id, _, buyer = order_ctx
    resp = await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 3})
    assert resp.status_code == 201
    data = resp.json()
    assert data["product_id"] == product_id
    assert data["quantity"] == 3
    assert float(data["total_price"]) == 60.0
    assert data["buyer_id"] == buyer["id"]
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_place_order_decrements_stock(db_session):
    seller = make_user("seller")
    buyer = make_user("buyer")
    product = await _create_product(db_session, seller, stock=5)
    product_id = product["id"]

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(buyer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 3})

        resp = await ac.get(f"/api/v1/products/{product_id}")
    app.dependency_overrides.clear()

    assert resp.json()["stock"] == 2


@pytest.mark.asyncio
async def test_place_order_insufficient_stock(db_session):
    seller = make_user("seller")
    buyer = make_user("buyer")
    product = await _create_product(db_session, seller, stock=2)

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(buyer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/orders/", json={"product_id": product["id"], "quantity": 5})
    app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Insufficient stock" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_place_order_product_not_found(order_ctx):
    ac, _, _, _ = order_ctx
    resp = await ac.post("/api/v1/orders/", json={"product_id": str(uuid.uuid4()), "quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_place_order_invalid_quantity(order_ctx):
    ac, product_id, _, _ = order_ctx
    resp = await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_place_order_requires_auth(db_session):
    seller = make_user("seller")
    product = await _create_product(db_session, seller, stock=5)

    app.dependency_overrides[get_db] = override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/orders/", json={"product_id": product["id"], "quantity": 1})
    app.dependency_overrides.clear()

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_my_orders(order_ctx):
    ac, product_id, _, buyer = order_ctx
    await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 1})
    await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 1})

    resp = await ac.get("/api/v1/orders/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert all(o["buyer_id"] == buyer["id"] for o in data["items"])


@pytest.mark.asyncio
async def test_list_my_orders_pagination(db_session):
    seller = make_user("seller")
    buyer = make_user("buyer")
    product = await _create_product(db_session, seller, stock=20)

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(buyer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(5):
            await ac.post("/api/v1/orders/", json={"product_id": product["id"], "quantity": 1})

        resp = await ac.get("/api/v1/orders/?page=1&per_page=3")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["page"] == 1
        assert data["per_page"] == 3

        resp2 = await ac.get("/api/v1/orders/?page=2&per_page=3")
        data2 = resp2.json()
        assert data2["total"] == 5
        assert len(data2["items"]) == 2

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_order(order_ctx):
    ac, product_id, _, buyer = order_ctx
    create_resp = await ac.post("/api/v1/orders/", json={"product_id": product_id, "quantity": 2})
    order_id = create_resp.json()["id"]

    resp = await ac.get(f"/api/v1/orders/{order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == order_id
    assert data["buyer_id"] == buyer["id"]


@pytest.mark.asyncio
async def test_get_order_not_found(order_ctx):
    ac, _, _, _ = order_ctx
    resp = await ac.get(f"/api/v1/orders/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_order_owner_only(db_session):
    seller = make_user("seller")
    buyer1 = make_user("buyer1")
    buyer2 = make_user("buyer2")

    product = await _create_product(db_session, seller, stock=10)

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(buyer1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post("/api/v1/orders/", json={"product_id": product["id"], "quantity": 1})
        order_id = create_resp.json()["id"]

    app.dependency_overrides[get_current_user] = override_user(buyer2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 403

    app.dependency_overrides.clear()
