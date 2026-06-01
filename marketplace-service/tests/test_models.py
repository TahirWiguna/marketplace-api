import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, Order, OrderStatus


@pytest.mark.asyncio
async def test_create_product(db_session: AsyncSession):
    """Test that a Product can be created and has expected fields."""
    product = Product(
        name="Test Widget",
        description="A test widget for testing",
        price=29.99,
        stock=100,
        seller_id=uuid.uuid4(),
        is_active=True,
    )
    db_session.add(product)
    await db_session.flush()

    # Refresh to get defaults populated
    await db_session.refresh(product)

    assert product.id is not None
    assert isinstance(product.id, uuid.UUID)
    assert product.name == "Test Widget"
    assert product.description == "A test widget for testing"
    assert float(product.price) == 29.99
    assert product.stock == 100
    assert product.is_active is True
    assert product.created_at is not None
    assert product.updated_at is not None


@pytest.mark.asyncio
async def test_create_order_with_status_enum(db_session: AsyncSession):
    """Test that an Order can be created with an OrderStatus enum value."""
    # Create a product first
    product = Product(
        name="Order Test Product",
        price=49.99,
        stock=50,
        seller_id=uuid.uuid4(),
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)

    # Create an order referencing the product
    order = Order(
        buyer_id=uuid.uuid4(),
        product_id=product.id,
        quantity=2,
        total_price=99.98,
        status=OrderStatus.pending,
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)

    assert order.id is not None
    assert isinstance(order.id, uuid.UUID)
    assert order.buyer_id is not None
    assert order.product_id == product.id
    assert order.quantity == 2
    assert float(order.total_price) == 99.98
    assert order.status == OrderStatus.pending
    assert order.created_at is not None

    # Test enum string values
    assert OrderStatus.pending.value == "pending"
    assert OrderStatus.confirmed.value == "confirmed"
    assert OrderStatus.cancelled.value == "cancelled"


@pytest.mark.asyncio
async def test_product_order_relationship(db_session: AsyncSession):
    """Test that Orders correctly reference a Product via foreign key."""
    product = Product(
        name="Relationship Test Product",
        price=19.99,
        stock=200,
        seller_id=uuid.uuid4(),
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)

    # Create multiple orders for the same product
    order1 = Order(
        buyer_id=uuid.uuid4(),
        product_id=product.id,
        quantity=1,
        total_price=19.99,
        status=OrderStatus.confirmed,
    )
    order2 = Order(
        buyer_id=uuid.uuid4(),
        product_id=product.id,
        quantity=3,
        total_price=59.97,
        status=OrderStatus.pending,
    )
    db_session.add_all([order1, order2])
    await db_session.flush()

    # Query orders for the product
    result = await db_session.execute(
        select(Order).where(Order.product_id == product.id)
    )
    orders = result.scalars().all()

    assert len(orders) == 2
    order_product_ids = {o.product_id for o in orders}
    assert product.id in order_product_ids
    assert all(o.product_id == product.id for o in orders)

    # Verify statuses
    statuses = {o.status for o in orders}
    assert OrderStatus.confirmed in statuses
    assert OrderStatus.pending in statuses
