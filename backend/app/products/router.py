import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.storage import storage_service
from app.products.models import (
    Category,
    Product,
    ProductIdentifier,
    IdentifierType,
    ProductImage,
    ProductSource,
    ImageType,
    SourceType,
)
from app.products.schemas import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductIdentifierCreate,
    ProductIdentifierResponse,
    ProductImageCreate,
    ProductImageResponse,
    ProductSourceCreate,
    ProductSourceResponse,
)

router = APIRouter()


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    category_in: CategoryCreate, db: Session = Depends(get_db)
) -> Category:
    """
    Create a new product category.
    If parent_id is provided, validates that the parent category exists.
    """
    if category_in.parent_id is not None:
        parent = (
            db.query(Category)
            .filter(Category.id == category_in.parent_id)
            .first()
        )
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with ID {category_in.parent_id} does not exist.",
            )

    db_category = Category(
        name=category_in.name, parent_id=category_in.parent_id
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: uuid.UUID, db: Session = Depends(get_db)
) -> Category:
    """
    Retrieve a category by its UUID.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found.",
        )
    return category


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product_in: ProductCreate, db: Session = Depends(get_db)
) -> Product:
    """
    Create a new product.
    If category_id is provided, validates that the associated category exists.
    """
    if product_in.category_id is not None:
        category = (
            db.query(Category)
            .filter(Category.id == product_in.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with ID {product_in.category_id} does not exist.",
            )

    db_product = Product(
        name=product_in.name,
        brand=product_in.brand,
        description=product_in.description,
        category_id=product_in.category_id,
        unit_value=product_in.unit_value,
        unit_type=product_in.unit_type,
        manufacturer=product_in.manufacturer,
        status=product_in.status,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def normalize_identifier_value(v: str) -> str:
    if v is None:
        raise ValueError("Identifier value cannot be null")
    v_trimmed = v.strip()
    if not v_trimmed:
        raise ValueError("Identifier value cannot be empty")
    normalized = "".join(c for c in v_trimmed if c not in (' ', '-', '.', '_', '\t'))
    if not normalized:
        raise ValueError("Identifier value must contain valid characters")
    if not normalized.isdigit():
        raise ValueError("Identifier value must contain only numeric digits")
    return normalized


@router.get("/products/resolve", response_model=ProductResponse)
def resolve_product(
    identifier_type: str,
    value: str,
    db: Session = Depends(get_db),
) -> Product:
    """
    Resolve a product by its identifier type and value.
    """
    # 1. Validate identifier_type
    try:
        id_type = IdentifierType(identifier_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identifier type '{identifier_type}'. Must be one of EAN, UPC, GTIN.",
        )

    # 2. Normalize value
    try:
        norm_value = normalize_identifier_value(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 3. Query
    db_identifier = (
        db.query(ProductIdentifier)
        .filter(
            ProductIdentifier.identifier_type == id_type,
            ProductIdentifier.value == norm_value,
        )
        .first()
    )
    if not db_identifier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with identifier {id_type.value}:{norm_value} not found.",
        )

    return db_identifier.product


@router.post(
    "/products/{product_id}/identifiers",
    response_model=ProductIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_identifier(
    product_id: uuid.UUID,
    identifier_in: ProductIdentifierCreate,
    db: Session = Depends(get_db),
) -> ProductIdentifier:
    """
    Create a new identifier for a product.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Validate identifier_type
    try:
        id_type = IdentifierType(identifier_in.identifier_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identifier type '{identifier_in.identifier_type}'. Must be one of EAN, UPC, GTIN.",
        )

    # 3. Normalize value
    try:
        norm_value = normalize_identifier_value(identifier_in.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 4. Check for duplicate identifier
    existing = (
        db.query(ProductIdentifier)
        .filter(
            ProductIdentifier.identifier_type == id_type,
            ProductIdentifier.value == norm_value,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate identifier: this type and value combination already exists.",
        )

    # 5. Create identifier
    db_identifier = ProductIdentifier(
        product_id=product_id,
        identifier_type=id_type,
        value=norm_value,
    )
    db.add(db_identifier)
    db.commit()
    db.refresh(db_identifier)
    return db_identifier


@router.get(
    "/products/{product_id}/identifiers",
    response_model=List[ProductIdentifierResponse],
)
def get_product_identifiers(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[ProductIdentifier]:
    """
    Retrieve all identifiers for a product.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    return product.identifiers


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> Product:
    """
    Retrieve a product by its UUID.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_image(
    product_id: uuid.UUID,
    image_in: ProductImageCreate,
    db: Session = Depends(get_db),
) -> ProductImage:
    """
    Create metadata for a product image.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Validate ImageType enum
    try:
        img_type = ImageType(image_in.image_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type '{image_in.image_type}'.",
        )

    # 3. Validate SourceType enum
    try:
        src_type = SourceType(image_in.source_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type '{image_in.source_type}'.",
        )

    # 4. Create ProductImage
    db_image = ProductImage(
        product_id=product_id,
        storage_key=image_in.storage_key,
        image_type=img_type,
        source_type=src_type,
        original_filename=image_in.original_filename,
        mime_type=image_in.mime_type,
        width=image_in.width,
        height=image_in.height,
        file_size_bytes=image_in.file_size_bytes,
        is_primary=image_in.is_primary,
        is_verified=image_in.is_verified,
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


@router.get(
    "/products/{product_id}/images",
    response_model=List[ProductImageResponse],
)
def get_product_images(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[ProductImage]:
    """
    Retrieve all image metadata for a product.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    return product.images


@router.post(
    "/products/{product_id}/sources",
    response_model=ProductSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_source(
    product_id: uuid.UUID,
    source_in: ProductSourceCreate,
    db: Session = Depends(get_db),
) -> ProductSource:
    """
    Create metadata to record provenance of product information.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Validate SourceType enum
    try:
        src_type = SourceType(source_in.source_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type '{source_in.source_type}'.",
        )

    # 3. Create ProductSource
    db_source = ProductSource(
        product_id=product_id,
        source_type=src_type,
        source_name=source_in.source_name,
        external_id=source_in.external_id,
        source_url=source_in.source_url,
    )
    if source_in.retrieved_at is not None:
        db_source.retrieved_at = source_in.retrieved_at

    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@router.get(
    "/products/{product_id}/sources",
    response_model=List[ProductSourceResponse],
)
def get_product_sources(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[ProductSource]:
    """
    Retrieve all sources (provenance metadata) for a product.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    return product.sources


@router.post(
    "/products/{product_id}/images/upload",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    image_type: str = Form(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
) -> ProductImage:
    """
    Upload a product image, validate it, save it locally, and create metadata.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Validate ImageType enum
    try:
        img_type = ImageType(image_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type '{image_type}'.",
        )

    # 3. Validate SourceType enum
    try:
        src_type = SourceType(source_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type '{source_type}'.",
        )

    # 4. Validate MIME Type
    mime_type = file.content_type
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type '{mime_type}'. Supported types: image/jpeg, image/png, image/webp.",
        )

    # 5. Read file contents and validate file size
    contents = file.file.read()
    file_size = len(contents)
    if file_size > settings.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the limit of {settings.MAX_IMAGE_SIZE_BYTES} bytes.",
        )
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File cannot be empty.",
        )

    # 6. Verify image content using Pillow
    import io
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()  # Verifies image is not corrupt
        
        # Re-open because verify() closes the file pointer in PIL
        img = Image.open(io.BytesIO(contents))
        width, height = img.size
        img_format = img.format
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid image.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error processing image.",
        )

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content format ({img_format}) does not match MIME type ({mime_type}).",
            )

    # 8. Save image to local storage
    file_like = io.BytesIO(contents)
    storage_key = storage_service.save(file_like, ext)

    # 9. Create ProductImage DB record
    db_image = ProductImage(
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
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


@router.get(
    "/products/{product_id}/images/{image_id}/file",
)
def get_product_image_file(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Retrieve the actual image file from storage.
    """
    # 1. Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # 2. Verify image exists and belongs to the product
    image = (
        db.query(ProductImage)
        .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .first()
    )
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} belonging to product {product_id} not found.",
        )

    # 3. Retrieve file path and check existence
    try:
        file_path = storage_service.get_path(image.storage_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found in storage.",
        )

    return FileResponse(path=str(file_path), media_type=image.mime_type)
