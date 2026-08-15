import uuid
import pytest
import threading
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.database import SessionLocal
from app.stores.models import Store, StoreProduct
from app.products.models import Product, Category
from app.inventory.models import Inventory, InventoryTransaction
from app.inventory.exceptions import InventoryNotFoundError, InsufficientStockError
from app.inventory.service import InventoryService
from app.stores.exceptions import StoreProductNotFoundError

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up all tables.
    """
    session = SessionLocal()
    session.query(InventoryTransaction).delete()
    session.query(Inventory).delete()
    session.query(StoreProduct).delete()
    session.query(Store).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(InventoryTransaction).delete()
        session.query(Inventory).delete()
        session.query(StoreProduct).delete()
        session.query(Store).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_stock_in_creates_initial_inventory(db_session: Session) -> None:
    # 1. Setup store product
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # 2. Stock-in 10 items (lazy initialization)
    resp = client.post(
        "/inventory/stock-in",
        json={
            "store_product_id": sp_id,
            "quantity": 10,
            "source": "MANUAL",
            "reference_type": "PO",
            "reference_id": "PO-1001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity"] == 10
    assert data["store_product_id"] == sp_id

    # 3. Verify exactly one transaction exists
    tx_resp = client.get(f"/inventory/{sp_id}/transactions")
    assert tx_resp.status_code == 200
    txs = tx_resp.json()
    assert len(txs) == 1
    tx = txs[0]
    assert tx["transaction_type"] == "STOCK_IN"
    assert tx["quantity"] == 10
    assert tx["previous_quantity"] == 0
    assert tx["new_quantity"] == 10
    assert tx["source"] == "MANUAL"
    assert tx["reference_type"] == "PO"
    assert tx["reference_id"] == "PO-1001"


def test_stock_in_increases_existing_inventory(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # First stock-in
    client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 10, "source": "MANUAL"})
    
    # Second stock-in
    resp = client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 5, "source": "BARCODE"})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 15

    # Verify transaction history
    txs = client.get(f"/inventory/{sp_id}/transactions").json()
    assert len(txs) == 2
    assert txs[0]["transaction_type"] == "STOCK_IN"
    assert txs[0]["quantity"] == 5
    assert txs[0]["previous_quantity"] == 10
    assert txs[0]["new_quantity"] == 15
    assert txs[0]["source"] == "BARCODE"


def test_stock_out_decreases_inventory(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # Stock-in 10
    client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 10, "source": "MANUAL"})

    # Stock-out 4
    resp = client.post("/inventory/stock-out", json={"store_product_id": sp_id, "quantity": 4, "source": "SALE"})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 6

    # Verify transaction history
    txs = client.get(f"/inventory/{sp_id}/transactions").json()
    assert len(txs) == 2
    assert txs[0]["transaction_type"] == "STOCK_OUT"
    assert txs[0]["quantity"] == 4
    assert txs[0]["previous_quantity"] == 10
    assert txs[0]["new_quantity"] == 6
    assert txs[0]["source"] == "SALE"


def test_stock_out_exceeding_inventory_rejected(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # Stock-in 5
    client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 5, "source": "MANUAL"})

    # Stock-out 6 (exceeds 5)
    resp = client.post("/inventory/stock-out", json={"store_product_id": sp_id, "quantity": 6, "source": "MANUAL"})
    assert resp.status_code == 400
    assert "Insufficient stock" in resp.json()["detail"]


def test_stock_out_no_inventory_fails(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # Try stock-out directly (fails because no inventory row exists)
    resp = client.post("/inventory/stock-out", json={"store_product_id": sp_id, "quantity": 5, "source": "MANUAL"})
    assert resp.status_code == 404
    assert "No inventory record" in resp.json()["detail"]


def test_negative_and_zero_quantities_rejected(db_session: Session) -> None:
    sp_id = str(uuid.uuid4())

    # Zero stock-in
    r1 = client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 0, "source": "MANUAL"})
    assert r1.status_code == 422

    # Negative stock-in
    r2 = client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": -5, "source": "MANUAL"})
    assert r2.status_code == 422

    # Zero stock-out
    r3 = client.post("/inventory/stock-out", json={"store_product_id": sp_id, "quantity": 0, "source": "MANUAL"})
    assert r3.status_code == 422


def test_adjustment_changes_inventory(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # Adjust initial empty stock to 15 (creates row lazily)
    resp1 = client.post("/inventory/adjust", json={"store_product_id": sp_id, "new_quantity": 15, "source": "MANUAL"})
    assert resp1.status_code == 200
    assert resp1.json()["quantity"] == 15

    # Adjust 15 to 8
    resp2 = client.post("/inventory/adjust", json={"store_product_id": sp_id, "new_quantity": 8, "source": "MANUAL"})
    assert resp2.status_code == 200
    assert resp2.json()["quantity"] == 8

    # Verify transaction ledger
    txs = client.get(f"/inventory/{sp_id}/transactions").json()
    assert len(txs) == 2
    
    # Check newest transaction (adjusting 15 to 8)
    assert txs[0]["transaction_type"] == "ADJUSTMENT"
    assert txs[0]["quantity"] == -7  # Net adjustment (8 - 15 = -7)
    assert txs[0]["previous_quantity"] == 15
    assert txs[0]["new_quantity"] == 8

    # Check oldest transaction (adjusting 0 to 15)
    assert txs[1]["transaction_type"] == "ADJUSTMENT"
    assert txs[1]["quantity"] == 15
    assert txs[1]["previous_quantity"] == 0
    assert txs[1]["new_quantity"] == 15


def test_adjustment_negative_quantity_rejected(db_session: Session) -> None:
    sp_id = str(uuid.uuid4())
    resp = client.post("/inventory/adjust", json={"store_product_id": sp_id, "new_quantity": -1, "source": "MANUAL"})
    assert resp.status_code == 422


def test_get_inventory(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 12, "source": "MANUAL"})

    resp = client.get(f"/inventory/{sp_id}")
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 12


def test_nonexistent_store_product_rejected(db_session: Session) -> None:
    fake_sp_id = str(uuid.uuid4())
    resp = client.post("/inventory/stock-in", json={"store_product_id": fake_sp_id, "quantity": 10, "source": "MANUAL"})
    assert resp.status_code == 404
    assert "StoreProduct" in resp.json()["detail"]


def test_transaction_rollback_on_failure(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # Initial stock-in
    client.post("/inventory/stock-in", json={"store_product_id": sp_id, "quantity": 10, "source": "MANUAL"})

    # Attempt to run a database-level constraint breach.
    # We will trigger a constraint error by calling Service logic directly with negative new_quantity transaction parameters
    # which violates `chk_tx_new_quantity_nonnegative` CHECK constraint!
    # Because of transactional atomicity, the database row update to inventory quantity should roll back!
    db = SessionLocal()
    db_inv = db.query(Inventory).filter(Inventory.store_product_id == uuid.UUID(sp_id)).first()
    assert db_inv is not None
    assert db_inv.quantity == 10

    # Mutate db_inv locally inside transaction
    db_inv.quantity = 15
    db.add(db_inv)
    db.flush()

    # Now attempt to append an invalid transaction with new_quantity = -5
    from app.inventory.models import InventoryTransaction, TransactionType, TransactionSource
    bad_tx = InventoryTransaction(
        inventory_id=db_inv.id,
        transaction_type=TransactionType.STOCK_OUT,
        quantity=5,
        previous_quantity=10,
        new_quantity=-5,  # Violates chk_tx_new_quantity_nonnegative constraint!
        source=TransactionSource.MANUAL,
    )
    db.add(bad_tx)

    with pytest.raises(IntegrityError):
        db.commit()  # Triggers constraint check and raises error, rolling back changes
    db.close()

    # Confirm inventory quantity remains 10 in the database
    inv_check = client.get(f"/inventory/{sp_id}").json()
    assert inv_check["quantity"] == 10


def test_concurrent_stock_out_handled_safely(db_session: Session) -> None:
    # 1. Setup store, product, mapping
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Soda"}).json()["id"]
    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.50},
    ).json()["id"]

    # 2. Stock-in 10 items
    client.post(
        "/inventory/stock-in",
        json={"store_product_id": sp_id, "quantity": 10, "source": "MANUAL"},
    )

    # We will run two threads attempting to stock-out 6 items concurrently
    errors = []
    successes = []

    def perform_stock_out():
        db = SessionLocal()
        try:
            InventoryService.stock_out(
                db=db,
                store_product_id=uuid.UUID(sp_id),
                quantity=6,
                source_str="MANUAL",
            )
            successes.append(True)
        except Exception as e:
            errors.append(e)
        finally:
            db.close()

    t1 = threading.Thread(target=perform_stock_out)
    t2 = threading.Thread(target=perform_stock_out)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Whichever thread obtains row lock first updates count to 4.
    # The second thread reads 4 and fails with InsufficientStockError!
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InsufficientStockError)

    # Check final stock is 4
    inv = client.get(f"/inventory/{sp_id}").json()
    assert inv["quantity"] == 4
