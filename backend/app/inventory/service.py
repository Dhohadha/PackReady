import uuid
from typing import Optional, List
from sqlalchemy.orm import Session

from app.inventory.models import Inventory, InventoryTransaction, TransactionType, TransactionSource
from app.inventory.repository import InventoryRepository
from app.inventory.exceptions import InventoryNotFoundError, InsufficientStockError
from app.stores.models import StoreProduct
from app.stores.exceptions import StoreProductNotFoundError

class InventoryService:
    @staticmethod
    def _validate_enums(source_str: str) -> TransactionSource:
        try:
            return TransactionSource(source_str.upper())
        except ValueError:
            raise ValueError(f"Invalid transaction source '{source_str}'.")

    @staticmethod
    def stock_in(
        db: Session,
        store_product_id: uuid.UUID,
        quantity: int,
        source_str: str,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
    ) -> Inventory:
        source = InventoryService._validate_enums(source_str)
        if quantity <= 0:
            raise ValueError("Stock-in quantity must be greater than zero.")

        # Verify StoreProduct exists
        sp = db.query(StoreProduct).filter(StoreProduct.id == store_product_id).first()
        if not sp:
            raise StoreProductNotFoundError(f"StoreProduct with ID {store_product_id} not found.")

        # Lock row for update to ensure safe concurrent changes
        db_inv = InventoryRepository.get_inventory_for_update(db, store_product_id)
        
        if db_inv:
            prev_qty = db_inv.quantity
            new_qty = prev_qty + quantity
            InventoryRepository.update_inventory_quantity(db, db_inv, new_qty)
        else:
            prev_qty = 0
            new_qty = quantity
            db_inv = InventoryRepository.create_inventory(db, store_product_id, new_qty)

        try:
            # Create transaction ledger record
            InventoryRepository.create_transaction(
                db=db,
                inventory_id=db_inv.id,
                tx_type=TransactionType.STOCK_IN,
                quantity=quantity,
                prev_quantity=prev_qty,
                new_quantity=new_qty,
                source=source,
                ref_type=ref_type,
                ref_id=ref_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(db_inv)
        return db_inv

    @staticmethod
    def stock_out(
        db: Session,
        store_product_id: uuid.UUID,
        quantity: int,
        source_str: str,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
    ) -> Inventory:
        source = InventoryService._validate_enums(source_str)
        if quantity <= 0:
            raise ValueError("Stock-out quantity must be greater than zero.")

        # Lock row for update
        db_inv = InventoryRepository.get_inventory_for_update(db, store_product_id)
        
        if not db_inv:
            # Verify StoreProduct exists if no inventory record
            sp = db.query(StoreProduct).filter(StoreProduct.id == store_product_id).first()
            if not sp:
                raise StoreProductNotFoundError(f"StoreProduct with ID {store_product_id} not found.")
            raise InventoryNotFoundError(f"No inventory record found for StoreProduct {store_product_id}.")

        prev_qty = db_inv.quantity
        new_qty = prev_qty - quantity
        if new_qty < 0:
            raise InsufficientStockError(f"Insufficient stock. Cannot subtract {quantity} from {prev_qty}.")

        try:
            InventoryRepository.update_inventory_quantity(db, db_inv, new_qty)
            # Create transaction ledger record
            InventoryRepository.create_transaction(
                db=db,
                inventory_id=db_inv.id,
                tx_type=TransactionType.STOCK_OUT,
                quantity=quantity,
                prev_quantity=prev_qty,
                new_quantity=new_qty,
                source=source,
                ref_type=ref_type,
                ref_id=ref_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(db_inv)
        return db_inv

    @staticmethod
    def adjust(
        db: Session,
        store_product_id: uuid.UUID,
        new_quantity: int,
        source_str: str,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
    ) -> Inventory:
        source = InventoryService._validate_enums(source_str)
        if new_quantity < 0:
            raise ValueError("Adjustment target quantity cannot be negative.")

        # Lock row for update
        db_inv = InventoryRepository.get_inventory_for_update(db, store_product_id)

        if not db_inv:
            # Verify StoreProduct exists if no inventory record
            sp = db.query(StoreProduct).filter(StoreProduct.id == store_product_id).first()
            if not sp:
                raise StoreProductNotFoundError(f"StoreProduct with ID {store_product_id} not found.")
            prev_qty = 0
        else:
            prev_qty = db_inv.quantity

        net_change = new_quantity - prev_qty

        try:
            if not db_inv:
                db_inv = InventoryRepository.create_inventory(db, store_product_id, new_quantity)
            else:
                InventoryRepository.update_inventory_quantity(db, db_inv, new_quantity)

            # Create transaction ledger record
            InventoryRepository.create_transaction(
                db=db,
                inventory_id=db_inv.id,
                tx_type=TransactionType.ADJUSTMENT,
                quantity=net_change,  # stores net difference (signed)
                prev_quantity=prev_qty,
                new_quantity=new_quantity,
                source=source,
                ref_type=ref_type,
                ref_id=ref_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(db_inv)
        return db_inv

    @staticmethod
    def get_inventory(db: Session, store_product_id: uuid.UUID) -> Inventory:
        # Verify StoreProduct exists
        sp = db.query(StoreProduct).filter(StoreProduct.id == store_product_id).first()
        if not sp:
            raise StoreProductNotFoundError(f"StoreProduct with ID {store_product_id} not found.")

        db_inv = InventoryRepository.get_inventory(db, store_product_id)
        if not db_inv:
            raise InventoryNotFoundError(f"No inventory record found for StoreProduct {store_product_id}.")
        return db_inv

    @staticmethod
    def get_transaction_history(db: Session, store_product_id: uuid.UUID) -> List[InventoryTransaction]:
        # Verify StoreProduct exists
        sp = db.query(StoreProduct).filter(StoreProduct.id == store_product_id).first()
        if not sp:
            raise StoreProductNotFoundError(f"StoreProduct with ID {store_product_id} not found.")

        db_inv = InventoryRepository.get_inventory(db, store_product_id)
        if not db_inv:
            raise InventoryNotFoundError(f"No inventory record found for StoreProduct {store_product_id}.")

        return InventoryRepository.get_transactions_newest_first(db, db_inv.id)
