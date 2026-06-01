from decimal import Decimal
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    product_id: UUID
    quantity: Annotated[int, Field(gt=0)]


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    product_id: UUID
    quantity: int
    total_price: Decimal
    status: str
    created_at: datetime
    product: Optional[ProductSummary] = None
