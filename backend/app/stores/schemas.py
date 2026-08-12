import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1)
    status: Optional[str] = "ACTIVE"


class StoreResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoreProductCreate(BaseModel):
    product_id: uuid.UUID
    selling_price: float = Field(..., ge=0.0)
    is_available: bool = True
    marketplace_enabled: bool = False


class StoreProductResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    selling_price: float
    is_available: bool
    marketplace_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
