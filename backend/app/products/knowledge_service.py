import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.products.models import Product, ProductImage, ImageType
from app.products.repository import ProductRepository
from app.products.exceptions import ProductNotFoundError, ImageNotFoundError


class ProductKnowledgeService:
    @staticmethod
    def calculate_completeness(db: Session, product_id: uuid.UUID) -> Dict[str, Any]:
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        has_name = bool(product.name and product.name.strip())
        has_brand = bool(product.brand and product.brand.strip())
        has_category = product.category_id is not None
        has_identifiers = len(product.identifiers) > 0
        has_images = len(product.images) > 0
        has_primary_image = any(img.is_primary for img in product.images)
        has_unit_info = bool(product.unit_value is not None and product.unit_type)

        missing_fields: List[str] = []
        if not has_brand:
            missing_fields.append("brand")
        if not has_category:
            missing_fields.append("category")
        if not has_identifiers:
            missing_fields.append("identifiers")
        if not has_images:
            missing_fields.append("images")
        if not has_primary_image:
            missing_fields.append("primary_image")
        if not has_unit_info:
            missing_fields.append("unit_info")

        total_criteria = 6
        met_criteria = (
            int(has_brand)
            + int(has_category)
            + int(has_identifiers)
            + int(has_images)
            + int(has_primary_image)
            + int(has_unit_info)
        )

        score = int(40 + (met_criteria / total_criteria) * 60)
        is_complete = met_criteria == total_criteria

        return {
            "product_id": product.id,
            "completeness_score": score,
            "is_complete": is_complete,
            "has_name": has_name,
            "has_brand": has_brand,
            "has_category": has_category,
            "has_identifiers": has_identifiers,
            "has_images": has_images,
            "has_primary_image": has_primary_image,
            "has_unit_info": has_unit_info,
            "missing_fields": missing_fields,
        }

    @staticmethod
    def designate_training_image(
        db: Session, product_id: uuid.UUID, image_id: uuid.UUID
    ) -> ProductImage:
        from app.products.dataset_service import ProductDatasetService
        return ProductDatasetService.promote_to_training(db, product_id, image_id)
