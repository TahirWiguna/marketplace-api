import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.utils.deps import get_current_user


def make_product_payload(name="Test Product", price="10.00", stock=100):
    return {"name": name, "description": "A test product", "price": price, "stock": stock}


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


@pytest_asyncio.fixture
async def seller_ctx(db_session):
    """Returns (client, seller_user) with auth overrides applied."""
    user = make_user("seller")
    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, user
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def public_ctx(db_session):
    """Returns unauthenticated client."""
    app.dependency_overrides[get_db] = override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_product(seller_ctx):
    ac, seller = seller_ctx
    payload = make_product_payload()
    resp = await ac.post("/api/v1/products/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert float(data["price"]) == float(payload["price"])
    assert data["stock"] == payload["stock"]
    assert data["seller_id"] == seller["id"]
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_product_invalid_price(seller_ctx):
    ac, _ = seller_ctx
    resp = await ac.post("/api/v1/products/", json=make_product_payload(price="0"))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_invalid_stock(seller_ctx):
    ac, _ = seller_ctx
    resp = await ac.post("/api/v1/products/", json=make_product_payload(stock=-1))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_requires_auth(public_ctx):
    resp = await public_ctx.post("/api/v1/products/", json=make_product_payload())
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_products_public(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    prefix = f"ListTest-{uuid.uuid4().hex[:8]}"
    await ac.post("/api/v1/products/", json=make_product_payload(name=f"{prefix}-A"))
    await ac.post("/api/v1/products/", json=make_product_payload(name=f"{prefix}-B"))

    resp = await public_ctx.get(f"/api/v1/products/?search={prefix}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 20


@pytest.mark.asyncio
async def test_list_products_pagination(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    prefix = f"PagTest-{uuid.uuid4().hex[:8]}"
    for i in range(5):
        await ac.post("/api/v1/products/", json=make_product_payload(name=f"{prefix}-{i}"))

    resp = await public_ctx.get(f"/api/v1/products/?search={prefix}&page=1&per_page=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["per_page"] == 3

    resp2 = await public_ctx.get(f"/api/v1/products/?search={prefix}&page=2&per_page=3")
    data2 = resp2.json()
    assert data2["total"] == 5
    assert len(data2["items"]) == 2
    assert data2["page"] == 2


@pytest.mark.asyncio
async def test_list_products_search(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    unique = uuid.uuid4().hex[:8]
    await ac.post("/api/v1/products/", json=make_product_payload(name=f"UniqueSearch-{unique}"))
    await ac.post("/api/v1/products/", json=make_product_payload(name=f"OtherProduct-{uuid.uuid4().hex[:8]}"))

    resp = await public_ctx.get(f"/api/v1/products/?search=UniqueSearch-{unique}")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == f"UniqueSearch-{unique}"


@pytest.mark.asyncio
async def test_get_product(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
    product_id = create_resp.json()["id"]

    resp = await public_ctx.get(f"/api/v1/products/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == product_id


@pytest.mark.asyncio
async def test_get_product_not_found(public_ctx):
    resp = await public_ctx.get(f"/api/v1/products/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_inactive_product_returns_404(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
    product_id = create_resp.json()["id"]
    await ac.delete(f"/api/v1/products/{product_id}")

    resp = await public_ctx.get(f"/api/v1/products/{product_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_product(seller_ctx):
    ac, _ = seller_ctx
    create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
    product_id = create_resp.json()["id"]

    resp = await ac.put(f"/api/v1/products/{product_id}", json={"name": "Updated Name", "price": "25.99"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert float(data["price"]) == 25.99


@pytest.mark.asyncio
async def test_update_product_owner_only(db_session):
    seller = make_user("seller")
    buyer = make_user("buyer")

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(seller)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
        product_id = create_resp.json()["id"]

    app.dependency_overrides[get_current_user] = override_user(buyer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.put(f"/api/v1/products/{product_id}", json={"name": "Hacked"})
        assert resp.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_product(seller_ctx, public_ctx):
    ac, _ = seller_ctx
    create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
    product_id = create_resp.json()["id"]

    resp = await ac.delete(f"/api/v1/products/{product_id}")
    assert resp.status_code == 204

    get_resp = await public_ctx.get(f"/api/v1/products/{product_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_owner_only(db_session):
    seller = make_user("seller")
    buyer = make_user("buyer")

    app.dependency_overrides[get_db] = override_db(db_session)
    app.dependency_overrides[get_current_user] = override_user(seller)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post("/api/v1/products/", json=make_product_payload())
        product_id = create_resp.json()["id"]

    app.dependency_overrides[get_current_user] = override_user(buyer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(f"/api/v1/products/{product_id}")
        assert resp.status_code == 403

    app.dependency_overrides.clear()
