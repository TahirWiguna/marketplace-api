from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str
    description: str
    price: Annotated[Decimal, Field(gt=0)]
    stock: Annotated[int, Field(ge=0)]


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Annotated[Decimal, Field(gt=0)]] = None
    stock: Optional[Annotated[int, Field(ge=0)]] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    price: Decimal
    stock: int
    seller_id: UUID
    is_active: bool
    created_at: datetime


class ProductList(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    per_page: int
