import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.stores.models import Store, StoreProduct, StoreStatus

class StoreRepository:
    @staticmethod
    def get_store(db: Session, store_id: uuid.UUID) -> Optional[Store]:
        return db.query(Store).filter(Store.id == store_id).first()

    @staticmethod
    def get_or_create_store(db: Session, store_id: uuid.UUID, name: str = "PackReady Store") -> Store:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            store = Store(id=store_id, name=name, status=StoreStatus.ACTIVE)
            db.add(store)
            db.commit()
            db.refresh(store)
        return store

    @staticmethod
    def create_store(db: Session, name: str, status: StoreStatus = StoreStatus.ACTIVE) -> Store:
        db_store = Store(name=name, status=status)
        db.add(db_store)
        db.commit()
        db.refresh(db_store)
        return db_store

    @staticmethod
    def get_store_product(db: Session, store_id: uuid.UUID, product_id: uuid.UUID) -> Optional[StoreProduct]:
        return (
            db.query(StoreProduct)
            .filter(StoreProduct.store_id == store_id, StoreProduct.product_id == product_id)
            .first()
        )

    @staticmethod
    def get_store_products(db: Session, store_id: uuid.UUID) -> List[StoreProduct]:
        return db.query(StoreProduct).filter(StoreProduct.store_id == store_id).all()

    @staticmethod
    def create_store_product(
        db: Session,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        selling_price: float,
        is_available: bool = True,
        marketplace_enabled: bool = False,
    ) -> StoreProduct:
        db_sp = StoreProduct(
            store_id=store_id,
            product_id=product_id,
            selling_price=selling_price,
            is_available=is_available,
            marketplace_enabled=marketplace_enabled,
        )
        db.add(db_sp)
        db.commit()
        db.refresh(db_sp)
        return db_sp
