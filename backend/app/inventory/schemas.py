import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class StockOperationRequest(BaseModel):
    store_product_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    source: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None


class AdjustOperationRequest(BaseModel):
    store_product_id: uuid.UUID
    new_quantity: int = Field(..., ge=0)
    source: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None


class InventoryResponse(BaseModel):
    id: uuid.UUID
    store_product_id: uuid.UUID
    quantity: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryTransactionResponse(BaseModel):
    id: uuid.UUID
    inventory_id: uuid.UUID
    transaction_type: str
    quantity: int
    previous_quantity: int
    new_quantity: int
    source: str
    reference_type: Optional[str]
    reference_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
