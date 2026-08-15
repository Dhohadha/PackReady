import uuid
from app.core.database import SessionLocal
from app.stores.models import Store, StoreProduct
from app.products.models import Product, ProductIdentifier
from app.inventory.models import Inventory

def seed():
    db = SessionLocal()
    try:
        # Clear existing data
        db.query(Inventory).delete()
        db.query(StoreProduct).delete()
        db.query(Store).delete()
        db.query(ProductIdentifier).delete()
        db.query(Product).delete()
        db.commit()

        # 1. Create Store
        store = Store(
            id=uuid.uuid4(),
            name="Sai Kirana Store",
            status="ACTIVE"
        )
        db.add(store)
        db.flush()

        # 2. Case 2: Product exists, but not mapped to Store
        prod_case2 = Product(
            id=uuid.uuid4(),
            name="Dettol Handwash",
            brand="Dettol"
        )
        db.add(prod_case2)
        db.flush()

        ident_case2 = ProductIdentifier(
            id=uuid.uuid4(),
            product_id=prod_case2.id,
            identifier_type="EAN",
            value="8901396328322"
        )
        db.add(ident_case2)

        # 3. Case 3: Product + StoreProduct mapped, no inventory
        prod_case3 = Product(
            id=uuid.uuid4(),
            name="Colgate Toothpaste",
            brand="Colgate"
        )
        db.add(prod_case3)
        db.flush()

        ident_case3 = ProductIdentifier(
            id=uuid.uuid4(),
            product_id=prod_case3.id,
            identifier_type="EAN",
            value="8901123000557"
        )
        db.add(ident_case3)

        sp_case3 = StoreProduct(
            id=uuid.uuid4(),
            store_id=store.id,
            product_id=prod_case3.id,
            selling_price=120.0,
            is_available=True,
            marketplace_enabled=False
        )
        db.add(sp_case3)

        # 4. Case 4: Product + StoreProduct + Inventory all exist
        prod_case4 = Product(
            id=uuid.uuid4(),
            name="Kinder Joy Chocolate",
            brand="Kinder"
        )
        db.add(prod_case4)
        db.flush()

        ident_case4 = ProductIdentifier(
            id=uuid.uuid4(),
            product_id=prod_case4.id,
            identifier_type="EAN",
            value="8000500224163"
        )
        db.add(ident_case4)

        sp_case4 = StoreProduct(
            id=uuid.uuid4(),
            store_id=store.id,
            product_id=prod_case4.id,
            selling_price=45.0,
            is_available=True,
            marketplace_enabled=True
        )
        db.add(sp_case4)
        db.flush()

        inv_case4 = Inventory(
            id=uuid.uuid4(),
            store_product_id=sp_case4.id,
            quantity=15
        )
        db.add(inv_case4)

        db.commit()
        print("SEED SUCCESS!")
        print(f"STORE UUID: {store.id}")
        
    except Exception as e:
        db.rollback()
        print(f"SEED FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
