import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.inventory.models import Inventory, InventoryTransaction, TransactionType, TransactionSource

class InventoryRepository:
    @staticmethod
    def get_inventory(db: Session, store_product_id: uuid.UUID) -> Optional[Inventory]:
        return db.query(Inventory).filter(Inventory.store_product_id == store_product_id).first()

    @staticmethod
    def get_inventory_for_update(db: Session, store_product_id: uuid.UUID) -> Optional[Inventory]:
        """
        Locks the inventory row using database row-level locking (SELECT ... FOR UPDATE).
        """
        return (
            db.query(Inventory)
            .filter(Inventory.store_product_id == store_product_id)
            .with_for_update()
            .first()
        )

    @staticmethod
    def create_inventory(db: Session, store_product_id: uuid.UUID, initial_quantity: int) -> Inventory:
        db_inv = Inventory(store_product_id=store_product_id, quantity=initial_quantity)
        db.add(db_inv)
        db.flush()
        return db_inv

    @staticmethod
    def update_inventory_quantity(db: Session, inventory: Inventory, new_quantity: int) -> None:
        inventory.quantity = new_quantity
        db.add(inventory)
        db.flush()

    @staticmethod
    def create_transaction(
        db: Session,
        inventory_id: uuid.UUID,
        tx_type: TransactionType,
        quantity: int,
        prev_quantity: int,
        new_quantity: int,
        source: TransactionSource,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
    ) -> InventoryTransaction:
        db_tx = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type=tx_type,
            quantity=quantity,
            previous_quantity=prev_quantity,
            new_quantity=new_quantity,
            source=source,
            reference_type=ref_type,
            reference_id=ref_id,
        )
        db.add(db_tx)
        db.flush()
        return db_tx

    @staticmethod
    def get_transactions_newest_first(db: Session, inventory_id: uuid.UUID) -> List[InventoryTransaction]:
        return (
            db.query(InventoryTransaction)
            .filter(InventoryTransaction.inventory_id == inventory_id)
            .order_by(InventoryTransaction.created_at.desc())
            .all()
        )
