import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Category, Product, ProductIdentifier, IdentifierType

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the test tables
    before and after each test runs.
    """
    session = SessionLocal()
    # Clean up tables in case of dirty database from previous runs
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        # Clean up tables after the test runs
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_create_ean_identifier(db_session: Session) -> None:
    """
    Test creating an EAN identifier for a product and verifying normalization.
    """
    # 1. Create product
    prod_resp = client.post("/products", json={"name": "Orange Juice"})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 2. Create EAN identifier with formatting characters
    ident_resp = client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "EAN", "value": " 400-638-133-3931 "}
    )
    assert ident_resp.status_code == 201
    data = ident_resp.json()
    assert data["identifier_type"] == "EAN"
    assert data["value"] == "4006381333931"  # Normalized
    assert data["product_id"] == prod_id
    assert "id" in data

    # 3. Verify in database
    db_ident = db_session.query(ProductIdentifier).filter(ProductIdentifier.id == data["id"]).first()
    assert db_ident is not None
    assert db_ident.value == "4006381333931"
    assert db_ident.identifier_type == IdentifierType.EAN


def test_get_product_identifiers(db_session: Session) -> None:
    """
    Test retrieving identifiers associated with a specific product.
    """
    # 1. Create product
    prod_resp = client.post("/products", json={"name": "Washing Powder"})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 2. Add two identifiers
    client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "EAN", "value": "1234567890128"})
    client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "UPC", "value": "987654321012"})

    # 3. Retrieve identifiers
    get_resp = client.get(f"/products/{prod_id}/identifiers")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data) == 2
    types = {item["identifier_type"] for item in data}
    values = {item["value"] for item in data}
    assert "EAN" in types
    assert "UPC" in types
    assert "1234567890128" in values
    assert "987654321012" in values


def test_create_multiple_identifiers_one_product(db_session: Session) -> None:
    """
    Test that a single product can support multiple distinct identifier types.
    """
    # 1. Create product
    prod_resp = client.post("/products", json={"name": "Soy Milk"})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 2. Add multiple identifiers
    resp_gtin = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "GTIN", "value": "11111111111111"})
    assert resp_gtin.status_code == 201

    resp_upc = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "UPC", "value": "222222222222"})
    assert resp_upc.status_code == 201

    # Verify both are stored
    idents = db_session.query(ProductIdentifier).filter(ProductIdentifier.product_id == prod_id).all()
    assert len(idents) == 2


def test_resolve_product_by_identifier(db_session: Session) -> None:
    """
    Test resolving a product by its identifier type and value.
    """
    # 1. Create product
    prod_resp = client.post("/products", json={"name": "Dark Chocolate"})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 2. Add identifier with formatting
    client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "EAN", "value": " 500-011-263-1006 "})

    # 3. Resolve using same value (with or without formatting)
    resolve_resp = client.get("/products/resolve", params={"identifier_type": "EAN", "value": "5000112631006"})
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["id"] == prod_id
    assert resolve_resp.json()["name"] == "Dark Chocolate"

    # 4. Resolve using formatted query
    resolve_resp_fmt = client.get("/products/resolve", params={"identifier_type": "EAN", "value": " 500 - 011263 - 1006 "})
    assert resolve_resp_fmt.status_code == 200
    assert resolve_resp_fmt.json()["id"] == prod_id


def test_resolve_unknown_identifier_returns_404(db_session: Session) -> None:
    """
    Test resolving a non-existent identifier returns a 404 status.
    """
    response = client.get("/products/resolve", params={"identifier_type": "EAN", "value": "123456789012"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_duplicate_identifier_rejected(db_session: Session) -> None:
    """
    Test that creating duplicate identifier value combinations is blocked.
    """
    # 1. Create two products
    p1 = client.post("/products", json={"name": "Product One"}).json()["id"]
    p2 = client.post("/products", json={"name": "Product Two"}).json()["id"]

    # 2. Add identifier to product one
    resp1 = client.post(f"/products/{p1}/identifiers", json={"identifier_type": "UPC", "value": "123456789012"})
    assert resp1.status_code == 201

    # 3. Add same identifier to product two
    resp2 = client.post(f"/products/{p2}/identifiers", json={"identifier_type": "UPC", "value": "123456789012"})
    assert resp2.status_code == 400
    assert "Duplicate identifier" in resp2.json()["detail"]

    # 4. Add duplicate with formatting difference
    resp3 = client.post(f"/products/{p2}/identifiers", json={"identifier_type": "UPC", "value": " 123-456-789-012 "})
    assert resp3.status_code == 400


def test_invalid_identifier_type_rejected(db_session: Session) -> None:
    """
    Test that an invalid identifier type (not EAN, UPC, GTIN) is rejected.
    """
    prod_id = client.post("/products", json={"name": "Coffee Bean"}).json()["id"]
    response = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "ISBN", "value": "9783161484100"})
    assert response.status_code == 400
    assert "Invalid identifier type" in response.json()["detail"]


def test_empty_identifier_rejected(db_session: Session) -> None:
    """
    Test that an empty identifier value is rejected.
    """
    prod_id = client.post("/products", json={"name": "Green Tea"}).json()["id"]
    
    # Empty string
    r1 = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "EAN", "value": ""})
    assert r1.status_code == 400

    # Whitespace only
    r2 = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "EAN", "value": "   "})
    assert r2.status_code == 400

    # Formatting characters only (normalizes to empty)
    r3 = client.post(f"/products/{prod_id}/identifiers", json={"identifier_type": "EAN", "value": "- - -"})
    assert r3.status_code == 400


def test_invalid_product_id_rejected(db_session: Session) -> None:
    """
    Test that adding an identifier to a non-existent product UUID returns 404.
    """
    fake_id = str(uuid.uuid4())
    response = client.post(f"/products/{fake_id}/identifiers", json={"identifier_type": "EAN", "value": "123456789012"})
    assert response.status_code == 404
