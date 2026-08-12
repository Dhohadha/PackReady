import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Category, Product, ProductImage, ProductSource, ImageType, SourceType

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the test tables
    before and after each test runs.
    """
    session = SessionLocal()
    # Clean up tables
    session.query(ProductSource).delete()
    session.query(ProductImage).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(ProductSource).delete()
        session.query(ProductImage).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_create_image_metadata(db_session: Session) -> None:
    # 1. Create product
    prod_id = client.post("/products", json={"name": "Sample Product"}).json()["id"]

    # 2. Add image metadata
    payload = {
        "storage_key": "products/images/juice_box.png",
        "image_type": "REFERENCE",
        "source_type": "PACKREADY",
        "original_filename": "juice_box.png",
        "mime_type": "image/png",
        "width": 800,
        "height": 600,
        "file_size_bytes": 102450
    }
    resp = client.post(f"/products/{prod_id}/images", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["storage_key"] == "products/images/juice_box.png"
    assert data["image_type"] == "REFERENCE"
    assert data["source_type"] == "PACKREADY"
    assert data["original_filename"] == "juice_box.png"
    assert data["mime_type"] == "image/png"
    assert data["width"] == 800
    assert data["height"] == 600
    assert data["file_size_bytes"] == 102450
    assert data["is_primary"] is False
    assert data["is_verified"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify db entry
    db_img = db_session.query(ProductImage).filter(ProductImage.id == data["id"]).first()
    assert db_img is not None
    assert db_img.storage_key == "products/images/juice_box.png"


def test_get_product_images(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Orange Soda"}).json()["id"]

    # Add images
    client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key1", "image_type": "REFERENCE", "source_type": "PACKREADY", "mime_type": "image/png"}
    )
    client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key2", "image_type": "MERCHANT", "source_type": "MERCHANT", "mime_type": "image/jpeg"}
    )

    resp = client.get(f"/products/{prod_id}/images")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    keys = {img["storage_key"] for img in data}
    assert "key1" in keys
    assert "key2" in keys


def test_multiple_images_for_one_product(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Chips"}).json()["id"]
    r1 = client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key1", "image_type": "TRAINING", "source_type": "MANUFACTURER", "mime_type": "image/png"}
    )
    assert r1.status_code == 201

    r2 = client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key2", "image_type": "MARKETPLACE", "source_type": "EXTERNAL_DATABASE", "mime_type": "image/png"}
    )
    assert r2.status_code == 201

    images = db_session.query(ProductImage).filter(ProductImage.product_id == prod_id).all()
    assert len(images) == 2


def test_required_field_validation_images(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Product X"}).json()["id"]
    
    # Missing storage_key
    resp = client.post(f"/products/{prod_id}/images", json={"image_type": "REFERENCE", "source_type": "PACKREADY", "mime_type": "image/png"})
    assert resp.status_code == 422

    # Missing image_type
    resp = client.post(f"/products/{prod_id}/images", json={"storage_key": "key", "source_type": "PACKREADY", "mime_type": "image/png"})
    assert resp.status_code == 422

    # Missing source_type
    resp = client.post(f"/products/{prod_id}/images", json={"storage_key": "key", "image_type": "REFERENCE", "mime_type": "image/png"})
    assert resp.status_code == 422

    # Missing mime_type
    resp = client.post(f"/products/{prod_id}/images", json={"storage_key": "key", "image_type": "REFERENCE", "source_type": "PACKREADY"})
    assert resp.status_code == 422


def test_negative_file_size_rejected(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Product"}).json()["id"]
    payload = {
        "storage_key": "key",
        "image_type": "REFERENCE",
        "source_type": "PACKREADY",
        "mime_type": "image/png",
        "file_size_bytes": -50
    }
    resp = client.post(f"/products/{prod_id}/images", json=payload)
    assert resp.status_code == 422


def test_negative_dimensions_rejected(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Product"}).json()["id"]
    
    # Negative width
    r1 = client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key", "image_type": "REFERENCE", "source_type": "PACKREADY", "mime_type": "image/png", "width": -10}
    )
    assert r1.status_code == 422

    # Negative height
    r2 = client.post(
        f"/products/{prod_id}/images",
        json={"storage_key": "key", "image_type": "REFERENCE", "source_type": "PACKREADY", "mime_type": "image/png", "height": -5}
    )
    assert r2.status_code == 422


def test_default_is_primary_and_is_verified(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Product"}).json()["id"]
    payload = {
        "storage_key": "key",
        "image_type": "REFERENCE",
        "source_type": "PACKREADY",
        "mime_type": "image/png"
    }
    resp = client.post(f"/products/{prod_id}/images", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_primary"] is False
    assert data["is_verified"] is False


def test_invalid_product_id_rejected_images(db_session: Session) -> None:
    fake_id = str(uuid.uuid4())
    payload = {
        "storage_key": "key",
        "image_type": "REFERENCE",
        "source_type": "PACKREADY",
        "mime_type": "image/png"
    }
    resp = client.post(f"/products/{fake_id}/images", json=payload)
    assert resp.status_code == 404


def test_create_source_metadata(db_session: Session) -> None:
    # 1. Create product
    prod_id = client.post("/products", json={"name": "Organic Honey"}).json()["id"]

    # 2. Create source
    payload = {
        "source_type": "EXTERNAL_DATABASE",
        "source_name": "OpenFoodFacts",
        "external_id": "off_12345",
        "source_url": "https://world.openfoodfacts.org/product/12345"
    }
    resp = client.post(f"/products/{prod_id}/sources", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "EXTERNAL_DATABASE"
    assert data["source_name"] == "OpenFoodFacts"
    assert data["external_id"] == "off_12345"
    assert data["source_url"] == "https://world.openfoodfacts.org/product/12345"
    assert "id" in data
    assert "retrieved_at" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify db
    db_src = db_session.query(ProductSource).filter(ProductSource.id == data["id"]).first()
    assert db_src is not None
    assert db_src.source_name == "OpenFoodFacts"


def test_get_product_sources(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Milk"}).json()["id"]
    client.post(f"/products/{prod_id}/sources", json={"source_type": "PACKREADY", "source_name": "Internal Import"})
    client.post(f"/products/{prod_id}/sources", json={"source_type": "MERCHANT", "source_name": "Vendor A"})

    resp = client.get(f"/products/{prod_id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {src["source_name"] for src in data}
    assert "Internal Import" in names
    assert "Vendor A" in names


def test_multiple_sources_for_one_product(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Water"}).json()["id"]
    r1 = client.post(f"/products/{prod_id}/sources", json={"source_type": "MANUFACTURER", "source_name": "Aqua Corp"})
    assert r1.status_code == 201
    r2 = client.post(f"/products/{prod_id}/sources", json={"source_type": "EXTERNAL_DATABASE", "source_name": "Barcodes DB"})
    assert r2.status_code == 201

    sources = db_session.query(ProductSource).filter(ProductSource.product_id == prod_id).all()
    assert len(sources) == 2


def test_invalid_product_id_rejected_sources(db_session: Session) -> None:
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/products/{fake_id}/sources", json={"source_type": "PACKREADY", "source_name": "Test Source"})
    assert resp.status_code == 404


def test_required_source_fields_validated(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Apple Juice"}).json()["id"]

    # Missing source_type
    resp = client.post(f"/products/{prod_id}/sources", json={"source_name": "Off-line Input"})
    assert resp.status_code == 422

    # Missing source_name
    resp = client.post(f"/products/{prod_id}/sources", json={"source_type": "PACKREADY"})
    assert resp.status_code == 422


def test_different_source_types_supported(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Towel"}).json()["id"]

    for st in ["PACKREADY", "MERCHANT", "MANUFACTURER", "EXTERNAL_DATABASE"]:
        resp = client.post(f"/products/{prod_id}/sources", json={"source_type": st, "source_name": f"Source for {st}"})
        assert resp.status_code == 201
