import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.stores.models import Store, StoreProduct
from app.products.models import Product, Category

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the tables
    before and after each test runs.
    """
    session = SessionLocal()
    # Clean up tables in correct dependency order
    session.query(StoreProduct).delete()
    session.query(Store).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(StoreProduct).delete()
        session.query(Store).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_create_store(db_session: Session) -> None:
    # 1. Create a store with defaults
    resp = client.post("/stores", json={"name": "Downtown Market"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Downtown Market"
    assert data["status"] == "ACTIVE"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_retrieve_store(db_session: Session) -> None:
    # 1. Create a store
    store_id = client.post("/stores", json={"name": "Subway Station Store"}).json()["id"]

    # 2. Retrieve the store
    resp = client.get(f"/stores/{store_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Subway Station Store"


def test_create_store_with_status_inactive(db_session: Session) -> None:
    # 1. Create INACTIVE store
    resp = client.post("/stores", json={"name": "Closed Store", "status": "INACTIVE"})
    assert resp.status_code == 201
    assert resp.json()["status"] == "INACTIVE"


def test_create_store_invalid_status(db_session: Session) -> None:
    resp = client.post("/stores", json={"name": "Test Store", "status": "SUSPENDED"})
    assert resp.status_code == 400


def test_create_store_product_success(db_session: Session) -> None:
    # 1. Create store and product
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Drink"}).json()["id"]

    # 2. Map product to store
    resp = client.post(
        f"/stores/{store_id}/products",
        json={
            "product_id": prod_id,
            "selling_price": 2.99,
            "is_available": True,
            "marketplace_enabled": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["store_id"] == store_id
    assert data["product_id"] == prod_id
    assert data["selling_price"] == 2.99
    assert data["is_available"] is True
    assert data["marketplace_enabled"] is True


def test_create_store_product_defaults(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Drink"}).json()["id"]

    resp = client.post(
        f"/stores/{store_id}/products",
        json={
            "product_id": prod_id,
            "selling_price": 1.50,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_available"] is True
    assert data["marketplace_enabled"] is False


def test_retrieve_store_products(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    p1 = client.post("/products", json={"name": "Milk"}).json()["id"]
    p2 = client.post("/products", json={"name": "Bread"}).json()["id"]

    client.post(f"/stores/{store_id}/products", json={"product_id": p1, "selling_price": 3.00})
    client.post(f"/stores/{store_id}/products", json={"product_id": p2, "selling_price": 2.00})

    resp = client.get(f"/stores/{store_id}/products")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert {item["product_id"] for item in items} == {p1, p2}


def test_retrieve_single_store_product(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Milk"}).json()["id"]

    client.post(f"/stores/{store_id}/products", json={"product_id": prod_id, "selling_price": 3.49})

    resp = client.get(f"/stores/{store_id}/products/{prod_id}")
    assert resp.status_code == 200
    assert resp.json()["selling_price"] == 3.49


def test_negative_selling_price_rejected(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Drink"}).json()["id"]

    resp = client.post(
        f"/stores/{store_id}/products",
        json={
            "product_id": prod_id,
            "selling_price": -0.99,
        },
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_duplicate_store_product_rejected(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Energy Drink"}).json()["id"]

    # First mapping
    resp1 = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.99},
    )
    assert resp1.status_code == 201

    # Duplicate mapping
    resp2 = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": prod_id, "selling_price": 3.49},
    )
    assert resp2.status_code == 400
    assert "already mapped" in resp2.json()["detail"]


def test_invalid_store_id_rejected(db_session: Session) -> None:
    fake_store_id = str(uuid.uuid4())
    prod_id = client.post("/products", json={"name": "Energy Drink"}).json()["id"]

    resp = client.post(
        f"/stores/{fake_store_id}/products",
        json={"product_id": prod_id, "selling_price": 2.99},
    )
    assert resp.status_code == 404
    assert "Store" in resp.json()["detail"]


def test_invalid_product_id_rejected(db_session: Session) -> None:
    store_id = client.post("/stores", json={"name": "Main Branch"}).json()["id"]
    fake_prod_id = str(uuid.uuid4())

    resp = client.post(
        f"/stores/{store_id}/products",
        json={"product_id": fake_prod_id, "selling_price": 2.99},
    )
    assert resp.status_code == 404
    assert "Product" in resp.json()["detail"]


def test_multiple_stores_can_sell_same_product(db_session: Session) -> None:
    s1 = client.post("/stores", json={"name": "Store A"}).json()["id"]
    s2 = client.post("/stores", json={"name": "Store B"}).json()["id"]
    prod_id = client.post("/products", json={"name": "Soda Can"}).json()["id"]

    resp1 = client.post(f"/stores/{s1}/products", json={"product_id": prod_id, "selling_price": 1.20})
    resp2 = client.post(f"/stores/{s2}/products", json={"product_id": prod_id, "selling_price": 1.40})

    assert resp1.status_code == 201
    assert resp2.status_code == 201
