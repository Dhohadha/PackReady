import io
import uuid
import pytest
from PIL import Image
from unittest.mock import patch, AsyncMock
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Product, ProductIdentifier, ProductImage, ProductSource, ImageType, SourceType
from app.products.service import ProductService
from app.products.repository import ProductRepository

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    session = SessionLocal()
    session.query(ProductImage).delete()
    session.query(ProductSource).delete()
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.commit()

    try:
        yield session
    finally:
        session.query(ProductImage).delete()
        session.query(ProductSource).delete()
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.commit()
        session.close()


def test_create_product_source_provenance(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # 1. Create ProductSource record via endpoint
    resp = client.post(
        f"/products/{prod.id}/sources",
        json={
            "source_type": "EXTERNAL_DATABASE",
            "source_name": "Open Food Facts",
            "external_id": "8901058861921",
            "source_url": "https://world.openfoodfacts.org/product/8901058861921",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_name"] == "Open Food Facts"
    assert data["source_type"] == "EXTERNAL_DATABASE"
    assert data["external_id"] == "8901058861921"
    assert data["source_url"] == "https://world.openfoodfacts.org/product/8901058861921"

    # 2. Test deduplication: repeated request returns existing record without creating duplicate
    resp2 = client.post(
        f"/products/{prod.id}/sources",
        json={
            "source_type": "EXTERNAL_DATABASE",
            "source_name": "Open Food Facts",
            "external_id": "8901058861921",
            "source_url": "https://world.openfoodfacts.org/product/8901058861921",
        },
    )
    assert resp2.status_code == 201
    assert resp2.json()["id"] == data["id"]
    assert db_session.query(ProductSource).filter(ProductSource.product_id == prod.id).count() == 1


def test_multiple_provider_sources_preserved(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # Add source 1: Open Food Facts
    ProductService.create_source(
        db_session,
        prod.id,
        source_in=type("SourceIn", (), {
            "source_type": "EXTERNAL_DATABASE",
            "source_name": "Open Food Facts",
            "external_id": "8901058861921",
            "source_url": "https://world.openfoodfacts.org/product/8901058861921",
            "retrieved_at": None,
        })
    )

    # Add source 2: UPCitemdb
    ProductService.create_source(
        db_session,
        prod.id,
        source_in=type("SourceIn", (), {
            "source_type": "EXTERNAL_DATABASE",
            "source_name": "UPCitemdb",
            "external_id": "8901058861921",
            "source_url": "https://www.upcitemdb.com/upc/8901058861921",
            "retrieved_at": None,
        })
    )

    sources = db_session.query(ProductSource).filter(ProductSource.product_id == prod.id).all()
    assert len(sources) == 2
    names = {s.source_name for s in sources}
    assert names == {"Open Food Facts", "UPCitemdb"}


@pytest.mark.anyio
async def test_import_reference_image_success_and_safety(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # Generate a valid PNG image buffer using Pillow
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, content=valid_png_bytes)

        resp = client.post(
            f"/products/{prod.id}/images/import-reference",
            json={
                "image_url": "https://images.openfoodfacts.org/front.png",
                "provider_name": "Open Food Facts",
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # TRAINING DATA SAFETY ASSERTIONS
        assert data["image_type"] == "REFERENCE"
        assert data["source_type"] == "EXTERNAL_DATABASE"
        assert data["is_verified"] is False  # Must NEVER be automatically verified
        assert data["is_primary"] is True    # Set primary because product had 0 images


@pytest.mark.anyio
async def test_import_reference_image_security_and_error_handling(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # 1. Invalid URL scheme (e.g. ftp:// or file://)
    resp = client.post(
        f"/products/{prod.id}/images/import-reference",
        json={"image_url": "file:///etc/passwd", "provider_name": "Open Food Facts"},
    )
    assert resp.status_code == 400

    # 2. Network error / 404 from provider
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(404)

        resp = client.post(
            f"/products/{prod.id}/images/import-reference",
            json={"image_url": "https://images.openfoodfacts.org/missing.jpg", "provider_name": "Open Food Facts"},
        )
        assert resp.status_code == 400
