import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.stores.models import Store, StoreProduct, StoreStatus
from app.stores.repository import StoreRepository
from app.stores.exceptions import StoreNotFoundError, StoreProductNotFoundError
from app.products.repository import ProductRepository
from app.products.exceptions import ProductNotFoundError

class StoreService:
    @staticmethod
    def create_store(db: Session, name: str, status_str: Optional[str] = None) -> Store:
        status = StoreStatus.ACTIVE
        if status_str is not None:
            try:
                status = StoreStatus(status_str.upper())
            except ValueError:
                raise ValueError(f"Invalid store status '{status_str}'. Must be ACTIVE or INACTIVE.")
        return StoreRepository.create_store(db, name, status)

    @staticmethod
    def create_store_product(
        db: Session,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        selling_price: float,
        is_available: bool = True,
        marketplace_enabled: bool = False,
    ) -> StoreProduct:
        # 1. Verify Store exists
        store = StoreRepository.get_store(db, store_id)
        if not store:
            raise StoreNotFoundError(f"Store with ID {store_id} not found.")

        # 2. Verify Product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 3. Check duplicate
        existing = StoreRepository.get_store_product(db, store_id, product_id)
        if existing:
            raise ValueError(f"Product with ID {product_id} is already mapped to Store {store_id}.")

        # 4. Check negative selling price
        if selling_price < 0.0:
            raise ValueError("Selling price cannot be negative.")

        return StoreRepository.create_store_product(
            db=db,
            store_id=store_id,
            product_id=product_id,
            selling_price=selling_price,
            is_available=is_available,
            marketplace_enabled=marketplace_enabled,
        )
