import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.products.models import Category, Product, ProductIdentifier, IdentifierType
from app.products.schemas import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductIdentifierCreate,
    ProductIdentifierResponse,
)

router = APIRouter()


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    category_in: CategoryCreate, db: Session = Depends(get_db)
) -> Category:
    """
    Create a new product category.
    If parent_id is provided, validates that the parent category exists.
    """
    if category_in.parent_id is not None:
        parent = (
            db.query(Category)
            .filter(Category.id == category_in.parent_id)
            .first()
        )
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with ID {category_in.parent_id} does not exist.",
            )

    db_category = Category(
        name=category_in.name, parent_id=category_in.parent_id
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: uuid.UUID, db: Session = Depends(get_db)
) -> Category:
    """
    Retrieve a category by its UUID.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found.",
        )
    return category


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product_in: ProductCreate, db: Session = Depends(get_db)
) -> Product:
    """
    Create a new product.
    If category_id is provided, validates that the associated category exists.
    """
    if product_in.category_id is not None:
        category = (
            db.query(Category)
            .filter(Category.id == product_in.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with ID {product_in.category_id} does not exist.",
            )

    db_product = Product(
        name=product_in.name,
        brand=product_in.brand,
        description=product_in.description,
        category_id=product_in.category_id,
        unit_value=product_in.unit_value,
        unit_type=product_in.unit_type,
        manufacturer=product_in.manufacturer,
        status=product_in.status,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def normalize_identifier_value(v: str) -> str:
    if v is None:
        raise ValueError("Identifier value cannot be null")
    v_trimmed = v.strip()
    if not v_trimmed:
        raise ValueError("Identifier value cannot be empty")
    normalized = "".join(c for c in v_trimmed if c not in (' ', '-', '.', '_', '\t'))
    if not normalized:
        raise ValueError("Identifier value must contain valid characters")
    if not normalized.isdigit():
        raise ValueError("Identifier value must contain only numeric digits")
    return normalized


@router.get("/products/resolve", response_model=ProductResponse)
def resolve_product(
    identifier_type: str,
    value: str,
    db: Session = Depends(get_db),
) -> Product:
    """
    Resolve a product by its identifier type and value.
    """
    # 1. Validate identifier_type
    try:
        id_type = IdentifierType(identifier_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identifier type '{identifier_type}'. Must be one of EAN, UPC, GTIN.",
        )

    # 2. Normalize value
    try:
        norm_value = normalize_identifier_value(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 3. Query
    db_identifier = (
        db.query(ProductIdentifier)
        .filter(
            ProductIdentifier.identifier_type == id_type,
            ProductIdentifier.value == norm_value,
        )
        .first()
    )
    if not db_identifier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with identifier {id_type.value}:{norm_value} not found.",
        )

    return db_identifier.product


@router.post(
    "/products/{product_id}/identifiers",
    response_model=ProductIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_identifier(
    product_id: uuid.UUID,
    identifier_in: ProductIdentifierCreate,
    db: Session = Depends(get_db),
) -> ProductIdentifier:
    """
    Create a new identifier for a product.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Validate identifier_type
    try:
        id_type = IdentifierType(identifier_in.identifier_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identifier type '{identifier_in.identifier_type}'. Must be one of EAN, UPC, GTIN.",
        )

    # 3. Normalize value
    try:
        norm_value = normalize_identifier_value(identifier_in.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 4. Check for duplicate identifier
    existing = (
        db.query(ProductIdentifier)
        .filter(
            ProductIdentifier.identifier_type == id_type,
            ProductIdentifier.value == norm_value,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate identifier: this type and value combination already exists.",
        )

    # 5. Create identifier
    db_identifier = ProductIdentifier(
        product_id=product_id,
        identifier_type=id_type,
        value=norm_value,
    )
    db.add(db_identifier)
    db.commit()
    db.refresh(db_identifier)
    return db_identifier


@router.get(
    "/products/{product_id}/identifiers",
    response_model=List[ProductIdentifierResponse],
)
def get_product_identifiers(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[ProductIdentifier]:
    """
    Retrieve all identifiers for a product.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    return product.identifiers


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> Product:
    """
    Retrieve a product by its UUID.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product
