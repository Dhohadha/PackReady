import io
import uuid
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.storage import storage_service
from app.products.models import Product, ProductIdentifier, ProductImage, ProductSource, ImageType, SourceType
from app.products.repository import ProductRepository
from app.products.quality_service import ImageQualityService, QualityStatus
from app.products.deduplication_service import ImageDeduplicationService
from app.products.dataset_service import ProductDatasetService

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


def _create_sample_png(width: int = 200, height: int = 200, color: str = "white") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# -------------------------------------------------------------------
# 1. IMAGE QUALITY TESTS (Cases 1 - 10)
# -------------------------------------------------------------------

def test_1_valid_high_quality_image():
    # Draw a checkered pattern to provide good sharpness/edges
    img = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 100, 100], fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    report = ImageQualityService.analyze_image_bytes(buf.getvalue())
    assert report["status"] == QualityStatus.GOOD
    assert report["width"] == 200
    assert report["height"] == 200


def test_2_very_small_image():
    # 50x50 is below 100x100 minimum threshold
    data = _create_sample_png(50, 50)
    report = ImageQualityService.analyze_image_bytes(data)
    assert report["status"] == QualityStatus.REJECTED
    assert any("smaller than minimum" in w for w in report["warnings"])


def test_3_extremely_dark_image():
    # Pitch black 200x200 image
    data = _create_sample_png(200, 200, color="black")
    report = ImageQualityService.analyze_image_bytes(data)
    assert report["status"] == QualityStatus.NEEDS_REVIEW
    assert any("dark" in w for w in report["warnings"])


def test_4_extremely_bright_image():
    # Pure white 200x200 image without edges
    data = _create_sample_png(200, 200, color="white")
    report = ImageQualityService.analyze_image_bytes(data)
    assert report["status"] == QualityStatus.NEEDS_REVIEW
    assert any("bright" in w or "blurry" in w for w in report["warnings"])


def test_5_invalid_image_bytes():
    report = ImageQualityService.analyze_image_bytes(b"NOT_AN_IMAGE_FILE_BYTES")
    assert report["status"] == QualityStatus.REJECTED
    assert any("Corrupt" in w for w in report["warnings"])


def test_6_unsupported_format():
    report = ImageQualityService.analyze_image_bytes(b"RIFF....WEBPVP8 ...")
    assert report["status"] == QualityStatus.REJECTED


def test_7_oversized_image():
    # Dummy bytes larger than 10MB limit
    dummy_huge = b"0" * (11 * 1024 * 1024)
    report = ImageQualityService.analyze_image_bytes(dummy_huge)
    assert report["status"] == QualityStatus.REJECTED
    assert any("exceeds" in w for w in report["warnings"])


def test_8_unusual_aspect_ratio():
    # 500x10 is 50:1 aspect ratio
    data = _create_sample_png(500, 10)
    report = ImageQualityService.analyze_image_bytes(data)
    assert report["status"] == QualityStatus.REJECTED
    assert any("Extreme aspect ratio" in w for w in report["warnings"])


def test_9_corrupted_image():
    data = _create_sample_png(200, 200)
    corrupted = data[:30] + b"\x00" * 50
    report = ImageQualityService.analyze_image_bytes(corrupted)
    assert report["status"] == QualityStatus.REJECTED


def test_10_valid_image_metadata_extraction():
    data = _create_sample_png(250, 150)
    report = ImageQualityService.analyze_image_bytes(data)
    assert report["width"] == 250
    assert report["height"] == 150
    assert report["aspect_ratio"] == 1.67
    assert report["format"] == "PNG"


# -------------------------------------------------------------------
# 2. TRAINING SAFETY TESTS (Cases 11 - 16)
# -------------------------------------------------------------------

def test_11_merchant_image_is_not_automatically_training(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    key = storage_service.save(io.BytesIO(_create_sample_png()), ".png")
    img = ProductRepository.create_image(
        db_session,
        prod.id,
        key,
        image_type=ImageType.MERCHANT,
        source_type=SourceType.MERCHANT,
        mime_type="image/png",
    )
    assert img.image_type == ImageType.MERCHANT
    assert img.is_verified is False


def test_12_reference_image_is_not_automatically_training(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    key = storage_service.save(io.BytesIO(_create_sample_png()), ".png")
    img = ProductRepository.create_image(
        db_session,
        prod.id,
        key,
        image_type=ImageType.REFERENCE,
        source_type=SourceType.EXTERNAL_DATABASE,
        mime_type="image/png",
    )
    assert img.image_type == ImageType.REFERENCE
    assert img.is_verified is False


def test_13_explicit_promotion_creates_training_state(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # Valid checkered image for quality check
    img_data = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img_data)
    draw.rectangle([10, 10, 100, 100], fill="black")
    buf = io.BytesIO()
    img_data.save(buf, format="PNG")

    key = storage_service.save(io.BytesIO(buf.getvalue()), ".png")
    img = ProductRepository.create_image(
        db_session,
        prod.id,
        key,
        image_type=ImageType.MERCHANT,
        source_type=SourceType.MERCHANT,
        original_filename="shelf_photo.png",
        mime_type="image/png",
    )

    promoted = ProductDatasetService.promote_to_training(db_session, prod.id, img.id)
    assert promoted.image_type == ImageType.TRAINING
    assert promoted.is_verified is True
    assert promoted.source_type == SourceType.MERCHANT  # Provenance intact!
    assert promoted.original_filename == "shelf_photo.png"


def test_14_invalid_image_cannot_be_promoted(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # 10x10 image is REJECTED by quality rules
    key = storage_service.save(io.BytesIO(_create_sample_png(10, 10)), ".png")
    img = ProductRepository.create_image(
        db_session,
        prod.id,
        key,
        image_type=ImageType.MERCHANT,
        source_type=SourceType.MERCHANT,
        mime_type="image/png",
    )

    with pytest.raises(ValueError, match="Cannot promote image to TRAINING"):
        ProductDatasetService.promote_to_training(db_session, prod.id, img.id)


def test_15_missing_physical_file_cannot_be_promoted(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    img = ProductRepository.create_image(
        db_session,
        prod.id,
        storage_key="non_existent_key.png",
        image_type=ImageType.MERCHANT,
        source_type=SourceType.MERCHANT,
        mime_type="image/png",
    )

    from app.products.exceptions import StorageFileNotFoundError
    with pytest.raises(StorageFileNotFoundError):
        ProductDatasetService.promote_to_training(db_session, prod.id, img.id)


def test_16_provenance_remains_unchanged_after_promotion(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # Valid image
    img_data = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img_data)
    draw.rectangle([10, 10, 100, 100], fill="black")
    buf = io.BytesIO()
    img_data.save(buf, format="PNG")

    key = storage_service.save(io.BytesIO(buf.getvalue()), ".png")
    img = ProductRepository.create_image(
        db_session,
        prod.id,
        key,
        image_type=ImageType.REFERENCE,
        source_type=SourceType.EXTERNAL_DATABASE,
        original_filename="off_ref.png",
        mime_type="image/png",
    )

    promoted = ProductDatasetService.promote_to_training(db_session, prod.id, img.id)
    assert promoted.source_type == SourceType.EXTERNAL_DATABASE
    assert promoted.original_filename == "off_ref.png"


# -------------------------------------------------------------------
# 3. DATASET STATISTICS TESTS (Cases 17 - 22)
# -------------------------------------------------------------------

def test_17_to_22_dataset_statistics_and_coverage(db_session: Session):
    p1 = Product(id=uuid.uuid4(), name="Product 1", brand="Brand A")
    p2 = Product(id=uuid.uuid4(), name="Product 2", brand="Brand B")
    p3 = Product(id=uuid.uuid4(), name="Product 3", brand="Brand C")
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    # Valid image helper
    def _save_valid_img():
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 100, 100], fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return storage_service.save(io.BytesIO(buf.getvalue()), ".png")

    # p1 has 1 REFERENCE image
    ProductRepository.create_image(
        db_session, p1.id, _save_valid_img(), image_type=ImageType.REFERENCE, source_type=SourceType.EXTERNAL_DATABASE, mime_type="image/png"
    )

    # p2 has 1 MERCHANT image and 1 TRAINING image
    ProductRepository.create_image(
        db_session, p2.id, _save_valid_img(), image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png"
    )
    t_img = ProductRepository.create_image(
        db_session, p2.id, _save_valid_img(), image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png"
    )
    ProductDatasetService.promote_to_training(db_session, p2.id, t_img.id)

    # p3 has zero images

    stats = ProductDatasetService.get_dataset_stats(db_session)

    assert stats["total_products"] == 3
    assert stats["products_with_reference_images"] == 1
    assert stats["products_with_merchant_images"] == 1
    assert stats["products_with_training_images"] == 1
    assert stats["total_reference_images"] == 1
    assert stats["total_merchant_images"] == 1
    assert stats["total_training_images"] == 1
    assert stats["products_with_zero_images"] == 1
    assert stats["products_with_single_image"] == 1  # p1 has single image
    assert round(stats["reference_image_coverage_pct"], 1) == 33.3
    assert round(stats["merchant_image_coverage_pct"], 1) == 33.3
    assert round(stats["training_image_coverage_pct"], 1) == 33.3


# -------------------------------------------------------------------
# 4. DEDUPLICATION TESTS (Cases 23 - 24)
# -------------------------------------------------------------------

def test_23_identical_image_detected(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    sample_bytes = _create_sample_png(200, 200, color="blue")
    key1 = storage_service.save(io.BytesIO(sample_bytes), ".png")
    key2 = storage_service.save(io.BytesIO(sample_bytes), ".png")

    img1 = ProductRepository.create_image(db_session, prod.id, key1, image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png")
    img2 = ProductRepository.create_image(db_session, prod.id, key2, image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png")

    dups = ImageDeduplicationService.find_duplicates_for_product(db_session, prod.id)
    assert len(dups) == 1
    assert dups[0]["match_type"] == "EXACT_BYTES"


def test_24_different_images_are_not_duplicates(db_session: Session):
    prod = Product(id=uuid.uuid4(), name="Milkybar", brand="Nestle")
    db_session.add(prod)
    db_session.commit()

    # Image 1: top-left black block
    img1_data = Image.new("RGB", (200, 200), color="white")
    draw1 = ImageDraw.Draw(img1_data)
    draw1.rectangle([0, 0, 100, 100], fill="black")
    buf1 = io.BytesIO()
    img1_data.save(buf1, format="PNG")

    # Image 2: bottom-right black block
    img2_data = Image.new("RGB", (200, 200), color="white")
    draw2 = ImageDraw.Draw(img2_data)
    draw2.rectangle([100, 100, 200, 200], fill="black")
    buf2 = io.BytesIO()
    img2_data.save(buf2, format="PNG")

    key1 = storage_service.save(io.BytesIO(buf1.getvalue()), ".png")
    key2 = storage_service.save(io.BytesIO(buf2.getvalue()), ".png")

    ProductRepository.create_image(db_session, prod.id, key1, image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png")
    ProductRepository.create_image(db_session, prod.id, key2, image_type=ImageType.MERCHANT, source_type=SourceType.MERCHANT, mime_type="image/png")

    dups = ImageDeduplicationService.find_duplicates_for_product(db_session, prod.id)
    assert len(dups) == 0
