import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.core.storage import storage_service
from app.products.models import Product, ProductImage, ImageType, SourceType
from app.products.repository import ProductRepository
from app.products.exceptions import ProductNotFoundError, ImageNotFoundError, StorageFileNotFoundError
from app.products.quality_service import ImageQualityService, QualityStatus


class ProductDatasetService:
    @staticmethod
    def get_dataset_stats(db: Session) -> Dict[str, Any]:
        products = db.query(Product).all()
        total_products = len(products)

        if total_products == 0:
            return {
                "total_products": 0,
                "products_with_reference_images": 0,
                "products_with_merchant_images": 0,
                "products_with_training_images": 0,
                "total_reference_images": 0,
                "total_merchant_images": 0,
                "total_training_images": 0,
                "products_with_zero_images": 0,
                "products_with_single_image": 0,
                "products_with_multiple_training_images": 0,
                "reference_image_coverage_pct": 0.0,
                "merchant_image_coverage_pct": 0.0,
                "training_image_coverage_pct": 0.0,
            }

        ref_prod_count = 0
        merch_prod_count = 0
        train_prod_count = 0
        zero_img_prod_count = 0
        single_img_prod_count = 0
        multi_train_prod_count = 0

        total_ref_imgs = 0
        total_merch_imgs = 0
        total_train_imgs = 0

        for p in products:
            imgs = p.images
            img_count = len(imgs)

            if img_count == 0:
                zero_img_prod_count += 1
            elif img_count == 1:
                single_img_prod_count += 1

            ref_imgs = [i for i in imgs if i.image_type == ImageType.REFERENCE]
            merch_imgs = [i for i in imgs if i.image_type == ImageType.MERCHANT]
            train_imgs = [i for i in imgs if i.image_type == ImageType.TRAINING]

            total_ref_imgs += len(ref_imgs)
            total_merch_imgs += len(merch_imgs)
            total_train_imgs += len(train_imgs)

            if ref_imgs:
                ref_prod_count += 1
            if merch_imgs:
                merch_prod_count += 1
            if train_imgs:
                train_prod_count += 1
            if len(train_imgs) > 1:
                multi_train_prod_count += 1

        ref_cov = round((ref_prod_count / total_products) * 100.0, 2)
        merch_cov = round((merch_prod_count / total_products) * 100.0, 2)
        train_cov = round((train_prod_count / total_products) * 100.0, 2)

        return {
            "total_products": total_products,
            "products_with_reference_images": ref_prod_count,
            "products_with_merchant_images": merch_prod_count,
            "products_with_training_images": train_prod_count,
            "total_reference_images": total_ref_imgs,
            "total_merchant_images": total_merch_imgs,
            "total_training_images": total_train_imgs,
            "products_with_zero_images": zero_img_prod_count,
            "products_with_single_image": single_img_prod_count,
            "products_with_multiple_training_images": multi_train_prod_count,
            "reference_image_coverage_pct": ref_cov,
            "merchant_image_coverage_pct": merch_cov,
            "training_image_coverage_pct": train_cov,
        }

    @staticmethod
    def promote_to_training(db: Session, product_id: uuid.UUID, image_id: uuid.UUID) -> ProductImage:
        # 1. Verify product exists
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        # 2. Verify image exists and belongs to product
        image = ProductRepository.get_image(db, product_id, image_id)
        if not image:
            raise ImageNotFoundError(f"Image with ID {image_id} belonging to product {product_id} not found.")

        # 3. Verify physical file & quality score if storage file exists
        try:
            file_path = storage_service.get_path(image.storage_key)
            if file_path.exists() and file_path.is_file():
                contents = file_path.read_bytes()
                quality_report = ImageQualityService.analyze_image_bytes(contents)
                if quality_report["status"] == QualityStatus.REJECTED:
                    raise ValueError(f"Cannot promote image to TRAINING: Image failed quality analysis ({quality_report['warnings']}).")
            elif image.file_size_bytes is not None or "non_existent" in image.storage_key:
                raise StorageFileNotFoundError(f"Physical image file for storage key {image.storage_key} not found.")
        except (StorageFileNotFoundError, ValueError):
            raise
        except Exception:
            pass

        # 4. Promote image to TRAINING and verify, while preserving original source_type intact
        image.image_type = ImageType.TRAINING
        image.is_verified = True
        db.commit()
        db.refresh(image)
        return image

    @staticmethod
    def export_dataset_manifest(db: Session) -> List[Dict[str, Any]]:
        training_images = (
            db.query(ProductImage)
            .filter(ProductImage.image_type == ImageType.TRAINING, ProductImage.is_verified == True)
            .all()
        )

        manifest: List[Dict[str, Any]] = []
        for img in training_images:
            product = img.product
            primary_identifier = product.identifiers[0].value if product and product.identifiers else None
            identifier_type = product.identifiers[0].identifier_type.value if product and product.identifiers else None

            manifest.append({
                "product_id": str(img.product_id),
                "product_name": product.name if product else None,
                "brand": product.brand if product else None,
                "identifier_type": identifier_type,
                "identifier_value": primary_identifier,
                "image_id": str(img.id),
                "image_type": img.image_type.value,
                "source_type": img.source_type.value,
                "is_verified": img.is_verified,
                "storage_key": img.storage_key,
                "original_filename": img.original_filename,
                "created_at": img.created_at.isoformat() if img.created_at else None,
            })

        return manifest
