import uuid
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from app.products.models import Product
from app.stores.models import StoreProduct
from app.inventory.models import Inventory
from app.stores.repository import StoreRepository
from app.stores.exceptions import StoreNotFoundError
from app.products.resolver import ProductResolver
from app.inventory.repository import InventoryRepository


class StoreProductResolver:
    @staticmethod
    def resolve_store_product(
        db: Session,
        store_id: uuid.UUID,
        identifier_type: str,
        value: str,
    ) -> Tuple[bool, bool, bool, Optional[Product], Optional[StoreProduct], Optional[Inventory]]:
        """
        Resolves a product at the store level by barcode identifier.
        Returns:
            (product_found, store_product_found, inventory_found, product, store_product, inventory)
        """
        # 1. Verify Store exists
        store = StoreRepository.get_store(db, store_id)
        if not store:
            raise StoreNotFoundError(f"Store with ID {store_id} not found.")

        # 2. Resolve global Product (raises ProductNotFoundError if missing)
        product = ProductResolver.resolve_by_identifier(db, identifier_type, value)

        # 3. Resolve StoreProduct
        sp = StoreRepository.get_store_product(db, store_id, product.id)
        if not sp:
            return True, False, False, product, None, None

        # 4. Resolve Inventory
        inv = InventoryRepository.get_inventory(db, sp.id)
        if not inv:
            return True, True, False, product, sp, None

        return True, True, True, product, sp, inv
