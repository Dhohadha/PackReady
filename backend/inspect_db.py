from app.core.database import SessionLocal
from app.stores.models import Store, StoreProduct
from app.products.models import Product, ProductIdentifier
from app.inventory.models import Inventory

def inspect():
    db = SessionLocal()
    try:
        print("--- STORES ---")
        stores = db.query(Store).all()
        for s in stores:
            print(f"Store ID: {s.id}, Name: {s.name}, Status: {s.status}")
            
        print("\n--- PRODUCTS ---")
        products = db.query(Product).all()
        for p in products:
            print(f"Product ID: {p.id}, Name: {p.name}, Brand: {p.brand}")
            idents = db.query(ProductIdentifier).filter_by(product_id=p.id).all()
            for idt in idents:
                print(f"  Identifier: {idt.identifier_type} = {idt.value}")
                
        print("\n--- STORE PRODUCTS ---")
        sps = db.query(StoreProduct).all()
        for sp in sps:
            print(f"StoreProduct ID: {sp.id}, StoreID: {sp.store_id}, ProductID: {sp.product_id}, Price: {sp.selling_price}")
            
        print("\n--- INVENTORY ---")
        invs = db.query(Inventory).all()
        for inv in invs:
            print(f"Inventory ID: {inv.id}, StoreProduct: {inv.store_product_id}, Qty: {inv.quantity}")
            
    finally:
        db.close()

if __name__ == "__main__":
    inspect()
