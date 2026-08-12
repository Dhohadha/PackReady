import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.products.models import ProductStatus, IdentifierType, ImageType, SourceType


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, description="Category name")
    parent_id: Optional[uuid.UUID] = Field(
        None, description="Parent category UUID, if nested"
    )


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, description="Product name")
    brand: Optional[str] = Field(None, description="Product brand name")
    description: Optional[str] = Field(None, description="Product description")
    category_id: Optional[uuid.UUID] = Field(
        None, description="Associated Category UUID"
    )
    unit_value: Optional[float] = Field(
        None, description="Value per unit (e.g. 500)"
    )
    unit_type: Optional[str] = Field(
        None, description="Type of unit (e.g. ml, g, pcs)"
    )
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    status: ProductStatus = Field(
        ProductStatus.ACTIVE, description="Product lifecycle status"
    )


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductIdentifierCreate(BaseModel):
    identifier_type: str = Field(..., description="Identifier type (EAN, UPC, GTIN)")
    value: str = Field(..., description="Barcode or GTIN identifier value")


class ProductIdentifierResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    identifier_type: IdentifierType
    value: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductResolveQuery(BaseModel):
    identifier_type: str = Field(..., description="Identifier type (EAN, UPC, GTIN)")
    value: str = Field(..., description="Barcode or GTIN identifier value")


class ProductImageCreate(BaseModel):
    storage_key: str = Field(..., min_length=1)
    image_type: str = Field(..., description="Image type (REFERENCE, MERCHANT, TRAINING, MARKETPLACE)")
    source_type: str = Field(..., description="Source type (PACKREADY, MERCHANT, MANUFACTURER, EXTERNAL_DATABASE)")
    original_filename: Optional[str] = None
    mime_type: str = Field(..., min_length=1)
    width: Optional[int] = Field(None, ge=0)
    height: Optional[int] = Field(None, ge=0)
    file_size_bytes: Optional[int] = Field(None, ge=0)
    is_primary: bool = False
    is_verified: bool = False


class ProductImageResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    storage_key: str
    image_type: ImageType
    source_type: SourceType
    original_filename: Optional[str]
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    file_size_bytes: Optional[int]
    is_primary: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductSourceCreate(BaseModel):
    source_type: str = Field(..., description="Source type (PACKREADY, MERCHANT, MANUFACTURER, EXTERNAL_DATABASE)")
    source_name: str = Field(..., min_length=1)
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class ProductSourceResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    source_type: SourceType
    source_name: str
    external_id: Optional[str]
    source_url: Optional[str]
    retrieved_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
