import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.products.models import Category, Product
from app.products.schemas import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
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
