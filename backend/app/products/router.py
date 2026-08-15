import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.products.models import Category, Product, ProductIdentifier, ProductImage, ProductSource
from app.products.schemas import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductIdentifierCreate,
    ProductIdentifierResponse,
    ProductImageCreate,
    ProductImageResponse,
    ProductSourceCreate,
    ProductSourceResponse,
    ProductReferenceImageImport,
    ProductCompletenessResponse,
)
from app.products.repository import ProductRepository
from app.products.service import ProductService
from app.products.knowledge_service import ProductKnowledgeService
from app.products.exceptions import (
    CategoryNotFoundError,
    ProductNotFoundError,
    ImageNotFoundError,
    StorageFileNotFoundError,
)
from app.products.resolver import ProductResolver

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
    try:
        return ProductService.create_category(
            db=db,
            name=category_in.name,
            parent_id=category_in.parent_id,
        )
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: uuid.UUID, db: Session = Depends(get_db)
) -> Category:
    """
    Retrieve a category by its UUID.
    """
    category = ProductRepository.get_category(db, category_id)
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
    try:
        return ProductService.create_product(
            db=db,
            name=product_in.name,
            brand=product_in.brand,
            description=product_in.description,
            category_id=product_in.category_id,
            unit_value=product_in.unit_value,
            unit_type=product_in.unit_type,
            manufacturer=product_in.manufacturer,
            status=product_in.status,
        )
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/products/resolve", response_model=ProductResponse)
def resolve_product(
    identifier_type: str,
    value: str,
    db: Session = Depends(get_db),
) -> Product:
    """
    Resolve a product by its identifier type and value.
    """
    try:
        return ProductResolver.resolve_by_identifier(
            db=db,
            identifier_type=identifier_type,
            value=value,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


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
    try:
        return ProductService.create_identifier(
            db=db,
            product_id=product_id,
            identifier_type=identifier_in.identifier_type,
            value=identifier_in.value,
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    product = ProductRepository.get_product(db, product_id)
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
    product = ProductRepository.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
) -> Product:
    """
    Partially update an existing product.
    Only fields explicitly sent in the payload are modified.
    """
    try:
        update_data = product_in.model_dump(exclude_unset=True)
        return ProductService.update_product(db, product_id, update_data)
    except (ProductNotFoundError, CategoryNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, ProductNotFoundError) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    try:
        return ProductService.create_image_metadata(
            db=db,
            product_id=product_id,
            storage_key=image_in.storage_key,
            image_type=image_in.image_type,
            source_type=image_in.source_type,
            original_filename=image_in.original_filename,
            mime_type=image_in.mime_type,
            width=image_in.width,
            height=image_in.height,
            file_size_bytes=image_in.file_size_bytes,
            is_primary=image_in.is_primary,
            is_verified=image_in.is_verified,
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    product = ProductRepository.get_product(db, product_id)
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
    try:
        return ProductService.create_source(
            db=db,
            product_id=product_id,
            source_in=source_in,
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    product = ProductRepository.get_product(db, product_id)
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
    try:
        return ProductService.upload_image(
            db=db,
            product_id=product_id,
            file=file,
            image_type=image_type,
            source_type=source_type,
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    try:
        file_path, mime_type = ProductService.get_image_file_path(
            db=db,
            product_id=product_id,
            image_id=image_id,
        )
        return FileResponse(path=file_path, media_type=mime_type)
    except (ProductNotFoundError, ImageNotFoundError, StorageFileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/products/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a product image file and its metadata.
    """
    try:
        ProductService.delete_image(db, product_id, image_id)
    except (ProductNotFoundError, ImageNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/products/{product_id}/images/{image_id}/primary", response_model=ProductImageResponse)
def set_primary_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductImage:
    """
    Set an image as primary for a product, unsetting the previous primary image.
    """
    try:
        return ProductService.set_primary_image(db, product_id, image_id)
    except (ProductNotFoundError, ImageNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/products/{product_id}/completeness", response_model=ProductCompletenessResponse)
def get_product_completeness(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get completeness metrics for a product.
    """
    try:
        return ProductKnowledgeService.calculate_completeness(db, product_id)
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/products/{product_id}/images/{image_id}/training", response_model=ProductImageResponse)
def designate_training_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductImage:
    """
    Explicitly designate a product image as verified and training-eligible for ML dataset.
    """
    try:
        return ProductKnowledgeService.designate_training_image(db, product_id, image_id)
    except (ProductNotFoundError, ImageNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/products/{product_id}/images/import-reference",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_reference_product_image(
    product_id: uuid.UUID,
    import_in: ProductReferenceImageImport,
    db: Session = Depends(get_db),
) -> ProductImage:
    """
    Import an external reference image from a verified Product Knowledge lookup provider.
    """
    try:
        return await ProductService.import_reference_image(
            db=db,
            product_id=product_id,
            image_url=import_in.image_url,
            provider_name=import_in.provider_name,
        )
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/products/{product_id}/images/{image_id}/quality")
def get_image_quality_analysis(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get advisory objective image quality analysis (dimensions, brightness, blur score, quality status).
    """
    try:
        file_path, _ = ProductService.get_image_file_path(db, product_id, image_id)
        from app.products.quality_service import ImageQualityService
        with open(file_path, "rb") as f:
            contents = f.read()
        return ImageQualityService.analyze_image_bytes(contents)
    except (ProductNotFoundError, ImageNotFoundError, StorageFileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/products/{product_id}/images/duplicates")
def get_product_image_duplicates(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Detect duplicate images for a product using SHA-256 and perceptual hashing.
    """
    try:
        from app.products.deduplication_service import ImageDeduplicationService
        return ImageDeduplicationService.find_duplicates_for_product(db, product_id)
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
