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


class UPCItemDbProvider(ProductKnowledgeProvider):
    TIMEOUT_SECONDS = 5.0

    @property
    def name(self) -> str:
        return "UPCitemdb"

    async def lookup_by_barcode(
        self, db: Session, identifier_type: str, normalized_value: str
    ) -> Optional[ProductCandidate]:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={normalized_value}"

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning(f"UPCitemdb returned status code {resp.status_code} for barcode {normalized_value}")
                return None

            data = resp.json()
            if not isinstance(data, dict) or data.get("code") != "OK":
                return None

            items = data.get("items", [])
            if not items or not isinstance(items, list):
                return None

            item = items[0]
            if not isinstance(item, dict):
                return None

            name = normalize_product_name(item.get("title"))
            brand = normalize_brand(item.get("brand"))
            description = normalize_text(item.get("description"))

            # Unit value & unit type extraction from size or title if present
            raw_size = item.get("size")
            unit_val, unit_t = extract_unit_quantity(raw_size)

            images = []
            img_list = item.get("images", [])
            if isinstance(img_list, list):
                for img_url in img_list[:3]:  # Take up to 3 image URLs
                    if isinstance(img_url, str) and img_url.strip():
                        images.append(
                            CandidateImage(
                                url=img_url.strip(),
                                provider=self.name,
                                image_role="REFERENCE",
                            )
                        )

            source_url = f"https://www.upcitemdb.com/upc/{normalized_value}"
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
            logger.warning(f"UPCitemdb lookup failed for {normalized_value}: {e}")
            return None
