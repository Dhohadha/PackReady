import hashlib
import io
import uuid
from typing import List, Dict, Any, Optional
from PIL import Image
from sqlalchemy.orm import Session

from app.core.storage import storage_service
from app.products.models import Product, ProductImage
from app.products.repository import ProductRepository
from app.products.exceptions import ProductNotFoundError


class ImageDeduplicationService:
    @staticmethod
    def compute_sha256(contents: bytes) -> str:
        return hashlib.sha256(contents).hexdigest()

    @staticmethod
    def compute_perceptual_hash(contents: bytes) -> Optional[str]:
        """
        Computes 64-bit average perceptual hash (ahash).
        Resizes to 8x8 grayscale, calculates mean pixel, and generates 64-bit binary string.
        """
        try:
            img = Image.open(io.BytesIO(contents)).convert("L").resize((8, 8), Image.Resampling.LANCZOS)
            pixels = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
            return bits
        except Exception:
            return None

    @staticmethod
    def find_duplicates_for_product(db: Session, product_id: uuid.UUID) -> List[Dict[str, Any]]:
        product = ProductRepository.get_product(db, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")

        images = product.images
        if len(images) < 2:
            return []

        image_hashes: List[Dict[str, Any]] = []
        for img in images:
            try:
                file_path = storage_service.get_path(img.storage_key)
                if not file_path.exists():
                    continue
                contents = file_path.read_bytes()
                sha256_val = ImageDeduplicationService.compute_sha256(contents)
                phash_val = ImageDeduplicationService.compute_perceptual_hash(contents)
                image_hashes.append({
                    "image_id": str(img.id),
                    "storage_key": img.storage_key,
                    "image_type": img.image_type.value,
                    "sha256": sha256_val,
                    "phash": phash_val,
                })
            except Exception:
                continue

        duplicates: List[Dict[str, Any]] = []
        n = len(image_hashes)
        for i in range(n):
            for j in range(i + 1, n):
                img_a = image_hashes[i]
                img_b = image_hashes[j]

                is_exact_duplicate = img_a["sha256"] == img_b["sha256"]
                is_perceptual_duplicate = (
                    img_a["phash"] is not None
                    and img_b["phash"] is not None
                    and img_a["phash"] == img_b["phash"]
                )

                if is_exact_duplicate or is_perceptual_duplicate:
                    match_type = "EXACT_BYTES" if is_exact_duplicate else "PERCEPTUAL_HASH"
                    duplicates.append({
                        "image_id_1": img_a["image_id"],
                        "image_id_2": img_b["image_id"],
                        "match_type": match_type,
                    })

        return duplicates
