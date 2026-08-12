import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image

from app.main import app
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.storage import storage_service
from app.products.models import Category, Product, ProductImage

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the test tables
    before and after each test runs.
    """
    session = SessionLocal()
    # Clean up tables
    session.query(ProductImage).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(ProductImage).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


@pytest.fixture(scope="function", autouse=True)
def override_media_root(tmp_path) -> None:
    """
    Automatically override media root path of storage service to a pytest temp directory
    so that tests do not write image files to the actual development media folder.
    """
    original_root = storage_service.media_root
    storage_service.media_root = tmp_path
    
    yield
    
    storage_service.media_root = original_root


def create_mock_image_bytes(fmt: str, size=(100, 100)) -> bytes:
    """
    Helper to generate valid image bytes in memory for tests.
    """
    img = Image.new("RGB", size, color="red")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_upload_valid_jpeg(db_session: Session) -> None:
    # 1. Create product
    prod_id = client.post("/products", json={"name": "Apple Juice"}).json()["id"]

    # 2. Generate JPEG image bytes
    img_bytes = create_mock_image_bytes("JPEG", size=(150, 120))

    # 3. Upload image
    files = {"file": ("juice.jpg", img_bytes, "image/jpeg")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert resp.status_code == 201

    resp_data = resp.json()
    assert resp_data["mime_type"] == "image/jpeg"
    assert resp_data["width"] == 150
    assert resp_data["height"] == 120
    assert resp_data["file_size_bytes"] == len(img_bytes)
    assert resp_data["image_type"] == "REFERENCE"
    assert resp_data["source_type"] == "PACKREADY"
    assert resp_data["original_filename"] == "juice.jpg"

    # Verify physical file existence in configured media directory
    file_path = storage_service.get_path(resp_data["storage_key"])
    assert file_path.exists()
    assert file_path.is_file()


def test_upload_valid_png(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Banana Milk"}).json()["id"]
    img_bytes = create_mock_image_bytes("PNG", size=(50, 50))
    files = {"file": ("banana.png", img_bytes, "image/png")}
    data = {"image_type": "MERCHANT", "source_type": "MERCHANT"}
    
    resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert resp.status_code == 201
    assert resp.json()["mime_type"] == "image/png"
    assert resp.json()["width"] == 50


def test_upload_valid_webp(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Cookies"}).json()["id"]
    img_bytes = create_mock_image_bytes("WEBP", size=(80, 60))
    files = {"file": ("cookies.webp", img_bytes, "image/webp")}
    data = {"image_type": "TRAINING", "source_type": "MANUFACTURER"}
    
    resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert resp.status_code == 201
    assert resp.json()["mime_type"] == "image/webp"
    assert resp.json()["width"] == 80


def test_unsupported_mime_type_rejected(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Bread"}).json()["id"]
    
    # Try uploading plain text
    files = {"file": ("info.txt", b"some plain text", "text/plain")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert resp.status_code == 400
    assert "Unsupported MIME type" in resp.json()["detail"]


def test_disguised_file_content_rejected(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Fake Image Product"}).json()["id"]
    
    # Try uploading non-image binary data but specifying image/jpeg MIME type
    files = {"file": ("exploit.jpg", b"MALICIOUS_EXEC_DATA_HERE", "image/jpeg")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert resp.status_code == 400
    assert "not a valid image" in resp.json()["detail"]


def test_oversized_image_rejected(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Bread"}).json()["id"]
    img_bytes = create_mock_image_bytes("JPEG")

    # Override max size setting temporarily
    original_max = settings.MAX_IMAGE_SIZE_BYTES
    settings.MAX_IMAGE_SIZE_BYTES = 10  # 10 bytes limit
    
    try:
        files = {"file": ("oversized.jpg", img_bytes, "image/jpeg")}
        data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
        resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
        assert resp.status_code == 400
        assert "exceeds the limit" in resp.json()["detail"]
    finally:
        settings.MAX_IMAGE_SIZE_BYTES = original_max


def test_invalid_product_id_rejected(db_session: Session) -> None:
    fake_id = str(uuid.uuid4())
    img_bytes = create_mock_image_bytes("JPEG")
    files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    
    resp = client.post(f"/products/{fake_id}/images/upload", files=files, data=data)
    assert resp.status_code == 404


def test_retrieve_uploaded_image_successfully(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Yogurt"}).json()["id"]
    img_bytes = create_mock_image_bytes("PNG")

    # 1. Upload
    files = {"file": ("yogurt.png", img_bytes, "image/png")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    upload_resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert upload_resp.status_code == 201
    image_id = upload_resp.json()["id"]

    # 2. Retrieve file
    retrieve_resp = client.get(f"/products/{prod_id}/images/{image_id}/file")
    assert retrieve_resp.status_code == 200
    assert retrieve_resp.headers["content-type"] == "image/png"
    assert retrieve_resp.content == img_bytes


def test_retrieve_image_via_wrong_product_id_fails(db_session: Session) -> None:
    p1 = client.post("/products", json={"name": "Yogurt"}).json()["id"]
    p2 = client.post("/products", json={"name": "Milk"}).json()["id"]
    img_bytes = create_mock_image_bytes("PNG")

    # Upload to product 1
    files = {"file": ("yogurt.png", img_bytes, "image/png")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    image_id = client.post(f"/products/{p1}/images/upload", files=files, data=data).json()["id"]

    # Try retrieving using product 2
    retrieve_resp = client.get(f"/products/{p2}/images/{image_id}/file")
    assert retrieve_resp.status_code == 404


def test_missing_storage_file_returns_404(db_session: Session) -> None:
    prod_id = client.post("/products", json={"name": "Cheese"}).json()["id"]
    img_bytes = create_mock_image_bytes("PNG")

    # 1. Upload
    files = {"file": ("cheese.png", img_bytes, "image/png")}
    data = {"image_type": "REFERENCE", "source_type": "PACKREADY"}
    upload_resp = client.post(f"/products/{prod_id}/images/upload", files=files, data=data)
    assert upload_resp.status_code == 201
    img_data = upload_resp.json()

    # 2. Physically delete the file in storage
    file_path = storage_service.get_path(img_data["storage_key"])
    assert file_path.exists()
    file_path.unlink()

    # 3. Retrieve
    retrieve_resp = client.get(f"/products/{prod_id}/images/{img_data['id']}/file")
    assert retrieve_resp.status_code == 404
