from decimal import Decimal
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    product_id: UUID
    quantity: Annotated[int, Field(gt=0)]


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    product_id: UUID
    quantity: int
    total_price: Decimal
    status: str
    created_at: datetime
