import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Category, Product, ProductImage, ProductIdentifier, ImageType, SourceType

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    session = SessionLocal()
    session.query(ProductImage).delete()
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()

    try:
        yield session
    finally:
        session.query(ProductImage).delete()
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_completeness_incomplete_product(db_session: Session) -> None:
    # Product with only name
    prod_resp = client.post("/products", json={"name": "Basic Bread"})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    comp_resp = client.get(f"/products/{prod_id}/completeness")
    assert comp_resp.status_code == 200
    data = comp_resp.json()

    assert data["product_id"] == prod_id
    assert data["is_complete"] is False
    assert data["has_name"] is True
    assert data["has_brand"] is False
    assert data["has_images"] is False
    assert data["has_identifiers"] is False
    assert "brand" in data["missing_fields"]
    assert "images" in data["missing_fields"]
    assert data["completeness_score"] == 40


def test_completeness_fully_populated_product(db_session: Session) -> None:
    # 1. Create category
    cat_id = client.post("/categories", json={"name": "Beverages"}).json()["id"]

    # 2. Create product with full detail
    prod_resp = client.post(
        "/products",
        json={
            "name": "Orange Juice",
            "brand": "Tropicana",
            "category_id": cat_id,
            "unit_value": 1.0,
            "unit_type": "L",
        },
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 3. Add identifier
    client.post(
        f"/products/{prod_id}/identifiers",
        json={"identifier_type": "EAN", "value": "8901234567890"},
    )

    # 4. Add primary image metadata
    client.post(
        f"/products/{prod_id}/images",
        json={
            "storage_key": "images/oj.jpg",
            "image_type": "REFERENCE",
            "source_type": "PACKREADY",
            "mime_type": "image/jpeg",
            "is_primary": True,
        },
    )

    # 5. Fetch completeness
    comp_resp = client.get(f"/products/{prod_id}/completeness")
    assert comp_resp.status_code == 200
    data = comp_resp.json()

    assert data["is_complete"] is True
    assert data["completeness_score"] == 100
    assert len(data["missing_fields"]) == 0
    assert data["has_name"] is True
    assert data["has_brand"] is True
    assert data["has_category"] is True
    assert data["has_identifiers"] is True
    assert data["has_images"] is True
    assert data["has_primary_image"] is True
    assert data["has_unit_info"] is True


def test_merchant_image_is_not_automatically_training(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Test Product"}).json()["id"]

    img_resp = client.post(
        f"/products/{prod_id}/images",
        json={
            "storage_key": "images/merchant.jpg",
            "image_type": "MERCHANT",
            "source_type": "MERCHANT",
            "mime_type": "image/jpeg",
        },
    )
    assert img_resp.status_code == 201
    img_data = img_resp.json()

    assert img_data["image_type"] == "MERCHANT"
    assert img_data["is_verified"] is False


def test_explicit_training_designation(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Training Product"}).json()["id"]

    img_data = client.post(
        f"/products/{prod_id}/images",
        json={
            "storage_key": "images/merchant.jpg",
            "image_type": "MERCHANT",
            "source_type": "MERCHANT",
            "mime_type": "image/jpeg",
        },
    ).json()
    image_id = img_data["id"]

    # Explicitly designate as training eligible
    train_resp = client.patch(f"/products/{prod_id}/images/{image_id}/training")
    assert train_resp.status_code == 200
    res_data = train_resp.json()

    assert res_data["image_type"] == "TRAINING"
    assert res_data["is_verified"] is True
    # Provenance preserved
    assert res_data["source_type"] == "MERCHANT"


def test_training_designation_invalid_relationship_fails(db_session: Session) -> None:
    p1 = client.post("/products", json={"name": "P1"}).json()["id"]
    p2 = client.post("/products", json={"name": "P2"}).json()["id"]

    img_id = client.post(
        f"/products/{p1}/images",
        json={
            "storage_key": "images/p1.jpg",
            "image_type": "MERCHANT",
            "source_type": "MERCHANT",
            "mime_type": "image/jpeg",
        },
    ).json()["id"]

    # Try designating image of P1 under P2
    resp = client.patch(f"/products/{p2}/images/{img_id}/training")
    assert resp.status_code == 404
