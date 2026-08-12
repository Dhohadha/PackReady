import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.products.models import Category, Product, ProductIdentifier, ProductImage, ProductSource, IdentifierType, ImageType, SourceType

class ProductRepository:
    @staticmethod
    def get_category(db: Session, category_id: uuid.UUID) -> Optional[Category]:
        return db.query(Category).filter(Category.id == category_id).first()

    @staticmethod
    def create_category(db: Session, name: str, parent_id: Optional[uuid.UUID] = None) -> Category:
        db_category = Category(name=name, parent_id=parent_id)
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category

    @staticmethod
    def get_product(db: Session, product_id: uuid.UUID) -> Optional[Product]:
        return db.query(Product).filter(Product.id == product_id).first()

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
        db_product = Product(
            name=name,
            brand=brand,
            description=description,
            category_id=category_id,
            unit_value=unit_value,
            unit_type=unit_type,
            manufacturer=manufacturer,
            status=status,
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product

    @staticmethod
    def get_identifier(db: Session, identifier_type: IdentifierType, value: str) -> Optional[ProductIdentifier]:
        return (
            db.query(ProductIdentifier)
            .filter(
                ProductIdentifier.identifier_type == identifier_type,
                ProductIdentifier.value == value,
            )
            .first()
        )

    @staticmethod
    def create_identifier(
        db: Session,
        product_id: uuid.UUID,
        identifier_type: IdentifierType,
        value: str,
    ) -> ProductIdentifier:
        db_identifier = ProductIdentifier(
            product_id=product_id,
            identifier_type=identifier_type,
            value=value,
        )
        db.add(db_identifier)
        db.commit()
        db.refresh(db_identifier)
        return db_identifier

    @staticmethod
    def create_image(
        db: Session,
        product_id: uuid.UUID,
        storage_key: str,
        image_type: ImageType,
        source_type: SourceType,
        original_filename: Optional[str] = None,
        mime_type: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        file_size_bytes: Optional[int] = None,
        is_primary: bool = False,
        is_verified: bool = False,
    ) -> ProductImage:
        db_image = ProductImage(
            product_id=product_id,
            storage_key=storage_key,
            image_type=image_type,
            source_type=source_type,
            original_filename=original_filename,
            mime_type=mime_type,
            width=width,
            height=height,
            file_size_bytes=file_size_bytes,
            is_primary=is_primary,
            is_verified=is_verified,
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        return db_image

    @staticmethod
    def get_image(db: Session, product_id: uuid.UUID, image_id: uuid.UUID) -> Optional[ProductImage]:
        return (
            db.query(ProductImage)
            .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
            .first()
        )

    @staticmethod
    def create_source(
        db: Session,
        product_id: uuid.UUID,
        source_type: SourceType,
        source_name: str,
        external_id: Optional[str] = None,
        source_url: Optional[str] = None,
        retrieved_at = None,
    ) -> ProductSource:
        db_source = ProductSource(
            product_id=product_id,
            source_type=source_type,
            source_name=source_name,
            external_id=external_id,
            source_url=source_url,
        )
        if retrieved_at is not None:
            db_source.retrieved_at = retrieved_at
            
        db.add(db_source)
        db.commit()
        db.refresh(db_source)
        return db_source
