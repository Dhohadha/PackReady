import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from sqlalchemy.orm import Session

from app.products.models import SourceType
from app.product_knowledge.providers.base import ProductKnowledgeProvider
from app.product_knowledge.schemas import ProductCandidate, CandidateSource, CandidateImage
from app.product_knowledge.normalization import (
    normalize_text,
    normalize_brand,
    normalize_product_name,
    extract_unit_quantity,
)

logger = logging.getLogger(__name__)


class OpenFoodFactsProvider(ProductKnowledgeProvider):
    USER_AGENT = "PackReady/1.0 (contact@packready.app - Android/iOS Inventory App)"
    TIMEOUT_SECONDS = 5.0

    @property
    def name(self) -> str:
        return "Open Food Facts"

    async def lookup_by_barcode(
        self, db: Session, identifier_type: str, normalized_value: str
    ) -> Optional[ProductCandidate]:
        url = f"https://world.openfoodfacts.org/api/v2/product/{normalized_value}.json"
        headers = {"User-Agent": self.USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                logger.warning(f"OpenFoodFacts returned status code {resp.status_code} for barcode {normalized_value}")
                return None

            data = resp.json()
            if not isinstance(data, dict) or data.get("status") != 1:
                return None

            product_data = data.get("product", {})
            if not isinstance(product_data, dict):
                return None

            # Extract fields safely
            raw_name = (
                product_data.get("product_name")
                or product_data.get("product_name_en")
                or product_data.get("abbreviated_product_name")
            )
            name = normalize_product_name(raw_name)

            raw_brands = product_data.get("brands")
            first_brand = raw_brands.split(",")[0] if raw_brands else None
            brand = normalize_brand(first_brand)

            raw_desc = product_data.get("generic_name") or product_data.get("categories")
            description = normalize_text(raw_desc)

            raw_qty = product_data.get("quantity") or product_data.get("product_quantity")
            unit_val, unit_t = extract_unit_quantity(raw_qty)

            images = []
            img_url = (
                product_data.get("image_url")
                or product_data.get("image_front_url")
                or product_data.get("image_small_url")
            )
            if img_url:
                images.append(
                    CandidateImage(
                        url=img_url,
                        provider=self.name,
                        image_role="REFERENCE",
                    )
                )

            source_url = f"https://world.openfoodfacts.org/product/{normalized_value}"
            source = CandidateSource(
                provider_name=self.name,
                source_type=SourceType.EXTERNAL_DATABASE,
                external_id=normalized_value,
                source_url=source_url,
                retrieved_at=datetime.now(timezone.utc),
            )

            return ProductCandidate(
                identifier_type=identifier_type,
                identifier_value=normalized_value,
                name=name,
                brand=brand,
                description=description,
                unit_value=unit_val,
                unit_type=unit_t,
                images=images,
                sources=[source],
                raw_provider_name=self.name,
            )

        except (httpx.TimeoutException, httpx.HTTPError, ValueError, Exception) as e:
            logger.warning(f"OpenFoodFacts lookup failed for {normalized_value}: {e}")
            return None
