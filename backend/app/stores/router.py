import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.stores.models import Store, StoreProduct
from app.stores.schemas import (
    StoreCreate,
    StoreResponse,
    StoreProductCreate,
    StoreProductResponse,
    StoreProductResolutionResponse,
)
from app.stores.repository import StoreRepository
from app.stores.service import StoreService
from app.stores.exceptions import StoreNotFoundError, StoreProductNotFoundError
from app.products.exceptions import ProductNotFoundError
from app.stores.resolver import StoreProductResolver

router = APIRouter()


@router.post(
    "/stores",
    response_model=StoreResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_store(store_in: StoreCreate, db: Session = Depends(get_db)) -> Store:
    """
    Create a new store.
    """
    try:
        return StoreService.create_store(db, name=store_in.name, status_str=store_in.status)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/stores/{store_id}",
    response_model=StoreResponse,
)
def get_store(
    store_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Store:
    """
    Retrieve a store by ID (auto-creating if not yet created).
    """
    return StoreRepository.get_or_create_store(db, store_id)


@router.post(
    "/stores/{store_id}/products",
    response_model=StoreProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_store_product(
    store_id: uuid.UUID,
    sp_in: StoreProductCreate,
    db: Session = Depends(get_db),
) -> StoreProduct:
    """
    Map a product to a store.
    """
    try:
        return StoreService.create_store_product(
            db=db,
            store_id=store_id,
            product_id=sp_in.product_id,
            selling_price=sp_in.selling_price,
            is_available=sp_in.is_available,
            marketplace_enabled=sp_in.marketplace_enabled,
        )
    except (StoreNotFoundError, ProductNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/stores/{store_id}/products",
    response_model=List[StoreProductResponse],
)
def get_store_products(
    store_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[StoreProduct]:
    """
    List all products mapped to a store (auto-creating store if not yet created).
    """
    StoreRepository.get_or_create_store(db, store_id)
    return StoreRepository.get_store_products(db, store_id)


@router.get(
    "/stores/{store_id}/products/resolve",
    response_model=StoreProductResolutionResponse,
)
def resolve_store_product(
    store_id: uuid.UUID,
    identifier_type: str,
    value: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Resolve store-level product and inventory by barcode identifier.
    """
    try:
        product_found, sp_found, inv_found, product, sp, inv = StoreProductResolver.resolve_store_product(
            db=db,
            store_id=store_id,
            identifier_type=identifier_type,
            value=value,
        )
        return {
            "product_found": product_found,
            "store_product_found": sp_found,
            "inventory_found": inv_found,
            "product": product,
            "store_product": sp,
            "inventory": inv,
        }
    except StoreNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/stores/{store_id}/products/{product_id}",
    response_model=StoreProductResponse,
)
def get_store_product(
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StoreProduct:
    """
    Retrieve details of a single product mapped to a store.
    """
    store = StoreRepository.get_store(db, store_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with ID {store_id} not found.",
        )
        
    sp = StoreRepository.get_store_product(db, store_id, product_id)
    if not sp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} is not mapped to Store {store_id}.",
        )
    return sp
