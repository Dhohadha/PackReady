import io
import logging
import uuid
from typing import Optional
import httpx
from fastapi import UploadFile
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.storage import storage_service
from app.products.models import Category, Product, ProductIdentifier, ProductImage, ProductSource, IdentifierType, ImageType, SourceType
from app.products.repository import ProductRepository
from app.products.exceptions import ProductNotFoundError, CategoryNotFoundError, ImageNotFoundError, StorageFileNotFoundError
from app.products.resolver import normalize_identifier_value

logger = logging.getLogger(__name__)


class ProductService:
    @staticmethod
    def create_category(db: Session, name: str, parent_id: Optional[uuid.UUID] = None) -> Category:
        if parent_id is not None:
            parent = ProductRepository.get_category(db, parent_id)
            if not parent:
                raise CategoryNotFoundError(f"Parent category with ID {parent_id} does not exist.")
        return ProductRepository.create_category(db, name, parent_id)

    @staticmethod
    def create_product(
        db: Session,
        name: str,
        brand: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        unit_value: Optional[float] = None,
        unit_type: Optional[str] = None,
        manufacturer: Optional[str] = None,
        status = None,
    ) -> Product:
        if category_id is not None:
            category = ProductRepository.get_category(db, category_id)
            if not category:
                raise CategoryNotFoundError(f"Category with ID {category_id} does not exist.")
        return ProductRepository.create_product(
            db, name, brand, description, category_id, unit_value, unit_type, manufacturer, status
        )

    @staticmethod
    def update_product(db: Session, product_id: uuid.UUID, update_data: dict) -> Product:
        db_product = ProductRepository.get_product(db, product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # Business validation: validate category_id if present
        if "category_id" in update_data and update_data["category_id"] is not None:
            category = ProductRepository.get_category(db, update_data["category_id"])
            if not category:
                raise CategoryNotFoundError(f"Category with ID {update_data['category_id']} does not exist.")

        return ProductRepository.update_product(db, db_product, update_data)

    @staticmethod
    def create_identifier(
        db: Session,
        product_id: uuid.UUID,
        identifier_type: str,
        value: str,
    ) -> ProductIdentifier:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Validate identifier_type
        try:
            id_type = IdentifierType(identifier_type.upper())
        except ValueError:
            raise ValueError(
                f"Invalid identifier type '{identifier_type}'. Must be one of EAN, UPC, GTIN."
            )

        # 3. Normalize value
        norm_value = normalize_identifier_value(value)

        # 4. Check for duplicate identifier
        existing = ProductRepository.get_identifier(db, id_type, norm_value)
        if existing:
            raise ValueError("Duplicate identifier: this type and value combination already exists.")

        # 5. Create identifier
        return ProductRepository.create_identifier(db, product_id, id_type, norm_value)

    @staticmethod
    def create_image_metadata(
        db: Session,
        product_id: uuid.UUID,
        storage_key: str,
        image_type: str,
        source_type: str,
        original_filename: Optional[str] = None,
        mime_type: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        file_size_bytes: Optional[int] = None,
        is_primary: bool = False,
        is_verified: bool = False,
    ) -> ProductImage:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Validate ImageType enum
        try:
            img_type = ImageType(image_type.upper())
        except ValueError:
            raise ValueError(f"Invalid image type '{image_type}'.")

        # 3. Validate SourceType enum
        try:
            src_type = SourceType(source_type.upper())
        except ValueError:
            raise ValueError(f"Invalid source type '{source_type}'.")

        return ProductRepository.create_image(
            db=db,
            product_id=product_id,
            storage_key=storage_key,
            image_type=img_type,
            source_type=src_type,
            original_filename=original_filename,
            mime_type=mime_type,
            width=width,
            height=height,
            file_size_bytes=file_size_bytes,
            is_primary=is_primary,
            is_verified=is_verified,
        )

    @staticmethod
    def upload_image(
        db: Session,
        product_id: uuid.UUID,
        file: UploadFile,
        image_type: str,
        source_type: str,
    ) -> ProductImage:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Validate ImageType enum
        try:
            img_type = ImageType(image_type.upper())
        except ValueError:
            raise ValueError(f"Invalid image type '{image_type}'.")

        # 3. Validate SourceType enum
        try:
            src_type = SourceType(source_type.upper())
        except ValueError:
            raise ValueError(f"Invalid source type '{source_type}'.")

        # 4. Validate MIME Type
        mime_type = file.content_type
        if mime_type not in ("image/jpeg", "image/png", "image/webp"):
            raise ValueError(
                f"Unsupported MIME type '{mime_type}'. Supported types: image/jpeg, image/png, image/webp."
            )

        # 5. Read file contents and validate file size
        contents = file.file.read()
        file_size = len(contents)
        if file_size > settings.MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"File size exceeds the limit of {settings.MAX_IMAGE_SIZE_BYTES} bytes.")
        if file_size == 0:
            raise ValueError("File cannot be empty.")

        # 6. Verify image content using Pillow
        try:
            img = Image.open(io.BytesIO(contents))
            img.verify()  # Verifies image is not corrupt
            
            # Re-open because verify() closes the file pointer in PIL
            img = Image.open(io.BytesIO(contents))
            width, height = img.size
            img_format = img.format
        except UnidentifiedImageError:
            raise ValueError("Uploaded file is not a valid image.")
        except Exception:
            raise ValueError("Error processing image.")

        # 7. Map formats to confirm alignment
        MIME_MAP = {
            "image/jpeg": ("JPEG", ".jpg"),
            "image/png": ("PNG", ".png"),
            "image/webp": ("WEBP", ".webp"),
        }
        expected_format, ext = MIME_MAP[mime_type]
        # Check if PIL format matches
        if img_format not in (expected_format, "MPO"):
            if not (expected_format == "JPEG" and img_format == "MPO"):
                raise ValueError(
                    f"File content format ({img_format}) does not match MIME type ({mime_type})."
                )

        # 8. Save image to local storage
        file_like = io.BytesIO(contents)
        storage_key = storage_service.save(file_like, ext)

        # 9. Create ProductImage DB record
        return ProductRepository.create_image(
            db=db,
            product_id=product_id,
            storage_key=storage_key,
            image_type=img_type,
            source_type=src_type,
            original_filename=file.filename,
            mime_type=mime_type,
            width=width,
            height=height,
            file_size_bytes=file_size,
            is_primary=False,
            is_verified=False,
        )

    @staticmethod
    def get_image_file_path(
        db: Session,
        product_id: uuid.UUID,
        image_id: uuid.UUID,
    ) -> tuple[str, str]:
        """
        Returns (absolute_file_path, mime_type).
        """
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Verify image exists and belongs to the product
        image = ProductRepository.get_image(db, product_id, image_id)
        if not image:
            raise ImageNotFoundError(
                f"Image with ID {image_id} belonging to product {product_id} not found."
            )

        # 3. Retrieve file path and check existence
        try:
            file_path = storage_service.get_path(image.storage_key)
        except ValueError as e:
            raise ValueError(str(e))

        if not file_path.exists() or not file_path.is_file():
            raise StorageFileNotFoundError("Image file not found in storage.")

        return str(file_path), image.mime_type

    @staticmethod
    def delete_image(db: Session, product_id: uuid.UUID, image_id: uuid.UUID) -> None:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Verify image exists and belongs to product
        image = ProductRepository.get_image(db, product_id, image_id)
        if not image:
            raise ImageNotFoundError(
                f"Image with ID {image_id} belonging to product {product_id} not found."
            )

        # 3. Delete physical file
        try:
            storage_service.delete(image.storage_key)
        except Exception:
            pass

        # 4. Delete DB record
        ProductRepository.delete_image(db, image)

    @staticmethod
    def set_primary_image(db: Session, product_id: uuid.UUID, image_id: uuid.UUID) -> ProductImage:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Verify image exists and belongs to product
        image = ProductRepository.get_image(db, product_id, image_id)
        if not image:
            raise ImageNotFoundError(
                f"Image with ID {image_id} belonging to product {product_id} not found."
            )

        # 3. Unset existing primary image
        ProductRepository.unset_primary_images(db, product_id)

        # 4. Set this image as primary
        image.is_primary = True
        db.commit()
        db.refresh(image)
        return image

    @staticmethod
    def create_source(
        db: Session,
        product_id: uuid.UUID,
        source_in,
    ) -> ProductSource:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Validate SourceType enum
        try:
            src_type = SourceType(source_in.source_type.upper())
        except ValueError:
            raise ValueError(f"Invalid source type '{source_in.source_type}'.")

        return ProductRepository.create_source(
            db=db,
            product_id=product_id,
            source_type=src_type,
            source_name=source_in.source_name,
            external_id=source_in.external_id,
            source_url=source_in.source_url,
            retrieved_at=source_in.retrieved_at,
        )

    @staticmethod
    async def import_reference_image(
        db: Session,
        product_id: uuid.UUID,
        image_url: str,
        provider_name: str = "External Database",
    ) -> ProductImage:
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        if not (image_url.startswith("http://") or image_url.startswith("https://")):
            raise ValueError("Invalid image URL scheme. Only HTTP and HTTPS URLs are permitted.")

        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(image_url)

            if resp.status_code != 200:
                raise ValueError(f"Failed to download image from provider. HTTP status: {resp.status_code}")

            contents = resp.content
            file_size = len(contents)
            if file_size > MAX_FILE_SIZE:
                raise ValueError("Downloaded image file size exceeds the limit.")
            if file_size == 0:
                raise ValueError("Downloaded image is empty.")

            img = Image.open(io.BytesIO(contents))
            img.verify()
            img = Image.open(io.BytesIO(contents))
            width, height = img.size
            img_format = img.format

            FORMAT_MAP = {
                "JPEG": ("image/jpeg", ".jpg"),
                "PNG": ("image/png", ".png"),
                "WEBP": ("image/webp", ".webp"),
                "MPO": ("image/jpeg", ".jpg"),
            }
            if img_format not in FORMAT_MAP:
                raise ValueError(f"Unsupported image format '{img_format}'.")

            mime_type, ext = FORMAT_MAP[img_format]
            file_like = io.BytesIO(contents)
            storage_key = storage_service.save(file_like, ext)

            has_primary = any(i.is_primary for i in product.images)
            is_primary = not has_primary

            safe_provider = provider_name.lower().replace(" ", "_")
            original_filename = f"reference_{safe_provider}{ext}"

            return ProductRepository.create_image(
                db=db,
                product_id=product_id,
                storage_key=storage_key,
                image_type=ImageType.REFERENCE,
                source_type=SourceType.EXTERNAL_DATABASE,
                original_filename=original_filename,
                mime_type=mime_type,
                width=width,
                height=height,
                file_size_bytes=file_size,
                is_primary=is_primary,
                is_verified=False,
            )
        except Exception as e:
            logger.warning(f"Reference image import failed for product {product_id}: {e}")
            raise ValueError(f"Reference image import failed: {e}")
