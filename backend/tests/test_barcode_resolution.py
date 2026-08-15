import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.stores.models import Store, StoreProduct
from app.products.models import Product, Category, ProductIdentifier, IdentifierType
from app.inventory.models import Inventory

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up all tables.
    """
    session = SessionLocal()
    session.query(Inventory).delete()
    session.query(StoreProduct).delete()
    session.query(Store).delete()
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(Inventory).delete()
        session.query(StoreProduct).delete()
        session.query(Store).delete()
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_resolve_barcode_case_4_full_exist(db_session: Session) -> None:
    # 1. Setup store, product, mapping, stock
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Choco Bar", "brand": "SweetCo"}).json()["id"]
    
    # Associate identifier
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "EAN", "value": " 400-638.133-3931 "},
    )

    sp_id = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 1.99},
    ).json()["id"]

    client.post(
        "/inventory/stock-in",
        json={"store_product_id": sp_id, "quantity": 10, "source": "MANUAL"},
    )

    # 2. Call resolve
    resp = client.get(
        f"/stores/{store_id}/products/resolve",
        params={"identifier_type": "EAN", "value": "4006381333931"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_found"] is True
    assert data["store_product_found"] is True
    assert data["inventory_found"] is True
    assert data["product"]["name"] == "Choco Bar"
    assert data["product"]["brand"] == "SweetCo"
    assert data["store_product"]["selling_price"] == 1.99
    assert data["inventory"]["quantity"] == 10


def test_resolve_barcode_case_3_missing_inventory(db_session: Session) -> None:
    # 1. Setup store, product, mapping (no inventory operation)
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Choco Bar", "brand": "SweetCo"}).json()["id"]
    
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "UPC", "value": "012345678905"},
    )

    client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 1.99},
    )

    # 2. Call resolve
    resp = client.get(
        f"/stores/{store_id}/products/resolve",
        params={"identifier_type": "UPC", "value": "012345678905"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_found"] is True
    assert data["store_product_found"] is True
    assert data["inventory_found"] is False
    assert data["product"]["name"] == "Choco Bar"
    assert data["store_product"] is not None
    assert data["inventory"] is None


def test_resolve_barcode_case_2_missing_store_product(db_session: Session) -> None:
    # 1. Setup store, product (no mapping)
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Choco Bar"}).json()["id"]
    
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "GTIN", "value": "98765432101234"},
    )

    # 2. Call resolve
    resp = client.get(
        f"/stores/{store_id}/products/resolve",
        params={"identifier_type": "GTIN", "value": "98765432101234"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_found"] is True
    assert data["store_product_found"] is False
    assert data["inventory_found"] is False
    assert data["product"]["name"] == "Choco Bar"
    assert data["store_product"] is None
    assert data["inventory"] is None


def test_resolve_barcode_case_1_unknown_identifier(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]

    resp = client.get(
        f"/stores/{store_id}/products/resolve",
        params={"identifier_type": "EAN", "value": "9999999999999"}
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


def test_resolve_barcode_invalid_store_id(db_session: Session) -> None:
    fake_store_id = str(uuid.uuid4())
    resp = client.get(
        f"/stores/{fake_store_id}/products/resolve",
        params={"identifier_type": "EAN", "value": "12345"}
    )
    assert resp.status_code == 404
    assert "Store" in resp.json()["detail"]


def test_resolve_barcode_normalization_works(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Downtown Store"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Choco Bar"}).json()["id"]
    
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "EAN", "value": " 400-638.133-3931 "},
    )

    # Call resolve with messy spacing/characters in value (verifies normalization works)
    resp = client.get(
        f"/stores/{store_id}/products/resolve",
        params={"identifier_type": "EAN", "value": "  400_638-133.3931 \t "}
    )
    assert resp.status_code == 200
    assert resp.json()["product_found"] is True


def test_resolve_barcode_ignores_other_store_mappings(db_session: Session) -> None:
    s1 = client.post("/stores", json={"name": "Store A"}).json()["id"]
    s2 = client.post("/stores", json={"name": "Store B"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Choco Bar"}).json()["id"]
    
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "EAN", "value": "4006381333931"},
    )

    # Map to Store B only
    client.post(
        f"/stores/{s2}/products",
        json={"product_id": prod_id, "selling_price": 1.99},
    )

    # Resolve from Store A (should report store_product_found = False)
    resp = client.get(
        f"/stores/{s1}/products/resolve",
        params={"identifier_type": "EAN", "value": "4006381333931"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_found"] is True
    assert data["store_product_found"] is False
