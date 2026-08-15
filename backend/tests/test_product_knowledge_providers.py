import uuid
import pytest
from unittest.mock import patch, AsyncMock
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.products.models import Product, ProductIdentifier, ProductImage, ProductSource
from app.stores.models import Store, StoreProduct
from app.inventory.models import Inventory
from app.product_knowledge.providers.packready_provider import PackReadyProvider
from app.product_knowledge.providers.openfoodfacts_provider import OpenFoodFactsProvider
from app.product_knowledge.providers.upcitemdb_provider import UPCItemDbProvider
from app.product_knowledge.aggregator import CandidateAggregator
from app.product_knowledge.orchestrator import ProviderOrchestrator
from app.product_knowledge.schemas import ProductCandidate, CandidateImage, ProductKnowledgeConfidence

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    session = SessionLocal()
    session.query(Inventory).delete()
    session.query(StoreProduct).delete()
    session.query(Store).delete()
    session.query(ProductImage).delete()
    session.query(ProductSource).delete()
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.commit()

    try:
        yield session
    finally:
        session.query(Inventory).delete()
        session.query(StoreProduct).delete()
        session.query(Store).delete()
        session.query(ProductImage).delete()
        session.query(ProductSource).delete()
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.commit()
        session.close()


# ── 1. PackReadyProvider Tests ──────────────────────────────────────────────
@pytest.mark.anyio
async def test_packready_provider_known_barcode(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle", unit_value=42.0, unit_type="g")
    db_session.add(prod)
    db_session.flush()
    ident = ProductIdentifier(id=uuid.uuid4(), product_id=prod.id, identifier_type="EAN", value="8901058861921")
    db_session.add(ident)
    db_session.commit()

    provider = PackReadyProvider()
    cand = await provider.lookup_by_barcode(db_session, "EAN", "8901058861921")
    assert cand is not None
    assert cand.name == "Milkybar"
    assert cand.brand == "Nestle"
    assert cand.unit_value == 42.0
    assert cand.sources[0].provider_name == "PackReady Local DB"


@pytest.mark.anyio
async def test_packready_provider_unknown_barcode(db_session: Session):
    provider = PackReadyProvider()
    cand = await provider.lookup_by_barcode(db_session, "EAN", "9999999999999")
    assert cand is None


# ── 2. OpenFoodFactsProvider Tests ─────────────────────────────────────────
@pytest.mark.anyio
async def test_openfoodfacts_provider_success(db_session: Session):
    mock_resp = {
        "status": 1,
        "product": {
            "product_name": "Milkybar Create",
            "brands": "Nestle, Nestle India",
            "generic_name": "White Chocolate",
            "quantity": "42g",
            "image_url": "https://images.openfoodfacts.org/1.jpg",
        },
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_resp)

        provider = OpenFoodFactsProvider()
        cand = await provider.lookup_by_barcode(db_session, "EAN", "8901058861921")

        assert cand is not None
        assert cand.name == "Milkybar Create"
        assert cand.brand == "Nestle"
        assert cand.unit_value == 42.0
        assert cand.unit_type == "g"
        assert len(cand.images) == 1
        assert cand.images[0].url == "https://images.openfoodfacts.org/1.jpg"


@pytest.mark.anyio
async def test_openfoodfacts_provider_not_found(db_session: Session):
    mock_resp = {"status": 0, "status_verbose": "product not found"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_resp)

        provider = OpenFoodFactsProvider()
        cand = await provider.lookup_by_barcode(db_session, "EAN", "0000000000000")
        assert cand is None


@pytest.mark.anyio
async def test_openfoodfacts_provider_error_and_timeout(db_session: Session):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Timeout")

        provider = OpenFoodFactsProvider()
        cand = await provider.lookup_by_barcode(db_session, "EAN", "8901058861921")
        assert cand is None


# ── 3. UPCItemDbProvider Tests ─────────────────────────────────────────────
@pytest.mark.anyio
async def test_upcitemdb_provider_success(db_session: Session):
    mock_resp = {
        "code": "OK",
        "items": [
            {
                "title": "Milky Bar Chocolate 42g",
                "brand": "Nestle",
                "description": "Delicious milk chocolate",
                "size": "42g",
                "images": ["https://images.upcitemdb.com/1.jpg"],
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_resp)

        provider = UPCItemDbProvider()
        cand = await provider.lookup_by_barcode(db_session, "EAN", "8901058861921")

        assert cand is not None
        assert cand.name == "Milky Bar Chocolate 42g"
        assert cand.brand == "Nestle"
        assert cand.unit_value == 42.0
        assert len(cand.images) == 1


@pytest.mark.anyio
async def test_upcitemdb_provider_rate_limit(db_session: Session):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(429, json={"code": "TOO_MANY_REQUESTS"})

        provider = UPCItemDbProvider()
        cand = await provider.lookup_by_barcode(db_session, "EAN", "8901058861921")
        assert cand is None


# ── 4. CandidateAggregator Tests ──────────────────────────────────────────
def test_aggregator_multi_provider_agreement():
    c1 = ProductCandidate(
        identifier_type="EAN",
        identifier_value="8901058861921",
        name="Milkybar Create",
        brand="Nestle",
        unit_value=42.0,
        unit_type="g",
        raw_provider_name="Open Food Facts",
    )
    c2 = ProductCandidate(
        identifier_type="EAN",
        identifier_value="8901058861921",
        name="Milkybar Chocolate",
        brand="Nestle",
        unit_value=42.0,
        unit_type="g",
        raw_provider_name="UPCitemdb",
    )

    res = CandidateAggregator.aggregate([c1, c2], {}, "EAN", "8901058861921")
    assert res.found is True
    assert res.confidence == ProductKnowledgeConfidence.HIGH
    assert res.match["brand"] == "Nestle"


def test_aggregator_conflict():
    c1 = ProductCandidate(
        identifier_type="EAN",
        identifier_value="8901058861921",
        name="Milkybar",
        brand="Nestle",
        raw_provider_name="Open Food Facts",
    )
    c2 = ProductCandidate(
        identifier_type="EAN",
        identifier_value="8901058861921",
        name="Dark Chocolate",
        brand="Cadbury",
        raw_provider_name="UPCitemdb",
    )

    res = CandidateAggregator.aggregate([c1, c2], {}, "EAN", "8901058861921")
    assert res.found is True
    assert res.confidence == ProductKnowledgeConfidence.LOW


# ── 5. ProviderOrchestrator Tests ──────────────────────────────────────────
@pytest.mark.anyio
async def test_orchestrator_short_circuits_local_hit(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Local Soap", brand="Dettol")
    db_session.add(prod)
    db_session.flush()
    ident = ProductIdentifier(id=uuid.uuid4(), product_id=prod.id, identifier_type="EAN", value="8901396328322")
    db_session.add(ident)
    db_session.commit()

    orchestrator = ProviderOrchestrator()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        res = await orchestrator.lookup(db_session, "EAN", "8901396328322")

        assert res.found is True
        assert res.match["name"] == "Local Soap"
        assert res.confidence == ProductKnowledgeConfidence.HIGH
        assert res.provider_status["PackReady Local DB"] == "FOUND"
        # Verify external HTTP call was NEVER made!
        mock_get.assert_not_called()


# ── 6. Read-Only Endpoint & Database Mutation Assertions ──────────────────
def test_lookup_endpoint_read_only_guarantee(db_session: Session):
    # Get initial table counts
    p_count = db_session.query(Product).count()
    pi_count = db_session.query(ProductIdentifier).count()
    img_count = db_session.query(ProductImage).count()
    sp_count = db_session.query(StoreProduct).count()

    mock_resp = {
        "status": 1,
        "product": {
            "product_name": "Test Snack",
            "brands": "Lays",
        },
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_resp)

        resp = client.get("/product-knowledge/lookup?identifier_type=EAN&value=8901234567890")
        assert resp.status_code == 200
        data = resp.json()

        assert data["found"] is True
        assert data["match"]["name"] == "Test Snack"

    # Assert that NO database records were created
    assert db_session.query(Product).count() == p_count
    assert db_session.query(ProductIdentifier).count() == pi_count
    assert db_session.query(ProductImage).count() == img_count
    assert db_session.query(StoreProduct).count() == sp_count
