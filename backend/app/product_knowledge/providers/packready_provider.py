from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.products.models import SourceType
from app.products.resolver import ProductResolver
from app.products.exceptions import ProductNotFoundError
from app.product_knowledge.providers.base import ProductKnowledgeProvider
from app.product_knowledge.schemas import ProductCandidate, CandidateSource, CandidateImage


class PackReadyProvider(ProductKnowledgeProvider):
    @property
    def name(self) -> str:
        return "PackReady Local DB"

    async def lookup_by_barcode(
        self, db: Session, identifier_type: str, normalized_value: str
    ) -> Optional[ProductCandidate]:
        try:
            product = ProductResolver.resolve_by_identifier(
                db=db,
                identifier_type=identifier_type,
                value=normalized_value,
            )
        except (ProductNotFoundError, ValueError):
            return None

        # Build candidate images from product images if available
        images = []
        for img in product.images:
            images.append(
                CandidateImage(
                    url=f"/products/{product.id}/images/{img.id}/file",
                    provider=self.name,
                    image_role="PRIMARY" if img.is_primary else img.image_type.value,
                )
            )

        source = CandidateSource(
            provider_name=self.name,
            source_type=SourceType.PACKREADY,
            external_id=str(product.id),
            source_url=f"/products/{product.id}",
            retrieved_at=datetime.now(timezone.utc),
        )

        return ProductCandidate(
            identifier_type=identifier_type,
            identifier_value=normalized_value,
            name=product.name,
            brand=product.brand,
            description=product.description,
            unit_value=product.unit_value,
            unit_type=product.unit_type,
            images=images,
            sources=[source],
            raw_provider_name=self.name,
        )
