import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Category, Product, ProductStatus

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the test tables
    before and after each test runs.
    """
    session = SessionLocal()
    # Clean up tables in case of dirty database from previous runs
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        # Clean up tables after the test runs
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_create_category(db_session: Session) -> None:
    """
    Test creating a basic category.
    """
    response = client.post("/categories", json={"name": "Grocery"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Grocery"
    assert data["parent_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify database entry exists
    db_cat = db_session.query(Category).filter(Category.name == "Grocery").first()
    assert db_cat is not None
    assert str(db_cat.id) == data["id"]


def test_create_nested_category(db_session: Session) -> None:
    """
    Test creating a category under a parent category.
    """
    # 1. Create parent category
    parent_resp = client.post("/categories", json={"name": "Grocery"})
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["id"]

    # 2. Create child category
    child_resp = client.post(
        "/categories", json={"name": "Biscuits", "parent_id": parent_id}
    )
    assert child_resp.status_code == 201
    child_data = child_resp.json()
    assert child_data["name"] == "Biscuits"
    assert child_data["parent_id"] == parent_id

    # 3. Verify in database
    db_child = db_session.query(Category).filter(Category.name == "Biscuits").first()
    assert db_child is not None
    assert str(db_child.parent_id) == parent_id


def test_create_category_with_invalid_parent(db_session: Session) -> None:
    """
    Test that creating a category with a non-existent parent_id fails.
    """
    fake_id = str(uuid.uuid4())
    response = client.post(
        "/categories", json={"name": "Invalid Child", "parent_id": fake_id}
    )
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_create_product_without_category(db_session: Session) -> None:
    """
    Test creating a product without assigning a category.
    """
    payload = {
        "name": "Organic Soap",
        "brand": "CleanLife",
        "description": "Natural body soap",
        "unit_value": 150.0,
        "unit_type": "g",
        "manufacturer": "Eco Corp",
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Organic Soap"
    assert data["category_id"] is None
    assert data["status"] == "ACTIVE"  # Safe default status

    # Verify in DB
    db_product = db_session.query(Product).filter(Product.name == "Organic Soap").first()
    assert db_product is not None
    assert db_product.status == ProductStatus.ACTIVE


def test_create_product_with_category(db_session: Session) -> None:
    """
    Test creating a product and linking it to a valid category.
    """
    # 1. Create a category
    cat_resp = client.post("/categories", json={"name": "Electronics"})
    assert cat_resp.status_code == 201
    category_id = cat_resp.json()["id"]

    # 2. Create product
    product_payload = {
        "name": "Smart Phone",
        "brand": "TechBrand",
        "category_id": category_id,
    }
    prod_resp = client.post("/products", json=product_payload)
    assert prod_resp.status_code == 201
    prod_data = prod_resp.json()
    assert prod_data["name"] == "Smart Phone"
    assert prod_data["category_id"] == category_id

    # 3. Verify relationships in DB
    db_product = db_session.query(Product).filter(Product.name == "Smart Phone").first()
    assert db_product is not None
    assert db_product.category is not None
    assert db_product.category.name == "Electronics"


def test_create_product_with_invalid_category(db_session: Session) -> None:
    """
    Test that creating a product with a non-existent category_id fails.
    """
    fake_id = str(uuid.uuid4())
    payload = {"name": "Laptop", "category_id": fake_id}
    response = client.post("/products", json=payload)
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_product_default_status(db_session: Session) -> None:
    """
    Test that product status defaults to ACTIVE if omitted.
    """
    response = client.post("/products", json={"name": "Simple Box"})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ACTIVE"


def test_get_category(db_session: Session) -> None:
    """
    Test retrieving a category by ID.
    """
    # Create category first
    cat = Category(name="Apparel")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)

    # Fetch via API
    response = client.get(f"/categories/{cat.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(cat.id)
    assert data["name"] == "Apparel"


def test_get_category_not_found() -> None:
    """
    Test retrieving a non-existent category returns 404.
    """
    fake_id = str(uuid.uuid4())
    response = client.get(f"/categories/{fake_id}")
    assert response.status_code == 404


def test_get_product(db_session: Session) -> None:
    """
    Test retrieving a product by ID.
    """
    # Create product first
    prod = Product(name="Jeans", status=ProductStatus.ACTIVE)
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)

    # Fetch via API
    response = client.get(f"/products/{prod.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(prod.id)
    assert data["name"] == "Jeans"
    assert data["status"] == "ACTIVE"


def test_get_product_not_found() -> None:
    """
    Test retrieving a non-existent product returns 404.
    """
    fake_id = str(uuid.uuid4())
    response = client.get(f"/products/{fake_id}")
    assert response.status_code == 404
