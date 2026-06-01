from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductList, ProductResponse, ProductUpdate
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = Product(
        name=data.name,
        description=data.description,
        price=data.price,
        stock=data.stock,
        seller_id=UUID(current_user["id"]),
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


@router.get("/", response_model=ProductList)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    base_filter = Product.is_active == True  # noqa: E712
    if search:
        base_filter = base_filter & Product.name.ilike(f"%{search}%")

    total_result = await db.execute(
        select(func.count()).select_from(Product).where(base_filter)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(Product).where(base_filter).offset((page - 1) * per_page).limit(per_page)
    )
    products = result.scalars().all()

    return ProductList(items=products, total=total, page=page, per_page=per_page)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.is_active == True)  # noqa: E712
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    if str(product.seller_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this product")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    if str(product.seller_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this product")

    product.is_active = False
    await db.flush()
