import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.inventory.models import Inventory, InventoryTransaction
from app.inventory.schemas import (
    StockOperationRequest,
    AdjustOperationRequest,
    InventoryResponse,
    InventoryTransactionResponse,
)
from app.inventory.service import InventoryService
from app.inventory.exceptions import InventoryNotFoundError, InsufficientStockError
from app.stores.exceptions import StoreProductNotFoundError

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post(
    "/stock-in",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
)
def stock_in(
    req: StockOperationRequest,
    db: Session = Depends(get_db),
) -> Inventory:
    """
    Perform a stock-in operation (increments stock count).
    """
    try:
        return InventoryService.stock_in(
            db=db,
            store_product_id=req.store_product_id,
            quantity=req.quantity,
            source_str=req.source,
            ref_type=req.reference_type,
            ref_id=req.reference_id,
        )
    except StoreProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/stock-out",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
)
def stock_out(
    req: StockOperationRequest,
    db: Session = Depends(get_db),
) -> Inventory:
    """
    Perform a stock-out operation (decrements stock count).
    """
    try:
        return InventoryService.stock_out(
            db=db,
            store_product_id=req.store_product_id,
            quantity=req.quantity,
            source_str=req.source,
            ref_type=req.reference_type,
            ref_id=req.reference_id,
        )
    except (StoreProductNotFoundError, InventoryNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except (ValueError, InsufficientStockError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/adjust",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
)
def adjust(
    req: AdjustOperationRequest,
    db: Session = Depends(get_db),
) -> Inventory:
    """
    Perform a stock adjustment operation (sets stock count directly).
    """
    try:
        return InventoryService.adjust(
            db=db,
            store_product_id=req.store_product_id,
            new_quantity=req.new_quantity,
            source_str=req.source,
            ref_type=req.reference_type,
            ref_id=req.reference_id,
        )
    except StoreProductNotFoundError as e:
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
    "/{store_product_id}",
    response_model=InventoryResponse,
)
def get_inventory(
    store_product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Inventory:
    """
    Retrieve current inventory details for a store product.
    """
    try:
        return InventoryService.get_inventory(db, store_product_id)
    except (StoreProductNotFoundError, InventoryNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{store_product_id}/transactions",
    response_model=List[InventoryTransactionResponse],
)
def get_transaction_history(
    store_product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[InventoryTransaction]:
    """
    Retrieve transaction ledger history for a store product.
    """
    try:
        return InventoryService.get_transaction_history(db, store_product_id)
    except (StoreProductNotFoundError, InventoryNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
