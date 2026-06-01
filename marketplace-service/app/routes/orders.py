from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.order import Order
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderResponse, ProductSummary
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == data.product_id, Product.is_active == True)  # noqa: E712
        .with_for_update()
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.stock < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    product.stock -= data.quantity
    total_price = Decimal(str(product.price)) * data.quantity

    order = Order(
        buyer_id=UUID(current_user["id"]),
        product_id=data.product_id,
        quantity=data.quantity,
        total_price=total_price,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


@router.get("/", response_model=dict)
async def list_my_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    buyer_id = UUID(current_user["id"])

    total_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.buyer_id == buyer_id)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(Order, Product)
        .join(Product, Order.product_id == Product.id)
        .where(Order.buyer_id == buyer_id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()

    items = [
        OrderResponse(
            id=order.id,
            buyer_id=order.buyer_id,
            product_id=order.product_id,
            quantity=order.quantity,
            total_price=order.total_price,
            status=order.status,
            created_at=order.created_at,
            product=ProductSummary.model_validate(product),
        )
        for order, product in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if str(order.buyer_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    return order
