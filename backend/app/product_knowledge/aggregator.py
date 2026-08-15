from typing import List, Dict, Optional, Any
from app.product_knowledge.schemas import (
    ProductCandidate,
    CandidateImage,
    CandidateSource,
    ProductKnowledgeConfidence,
    ProductKnowledgeLookupResponse,
)


class CandidateAggregator:
    @staticmethod
    def aggregate(
        candidates: List[ProductCandidate],
        provider_status: Dict[str, str],
        identifier_type: str,
        identifier_value: str,
    ) -> ProductKnowledgeLookupResponse:
        if not candidates:
            return ProductKnowledgeLookupResponse(
                found=False,
                match=None,
                identifiers=[{"type": identifier_type, "value": identifier_value}],
                images=[],
                sources=[],
                confidence=ProductKnowledgeConfidence.UNKNOWN,
                provider_status=provider_status,
            )

        # Priority 1: Check if any candidate came from PackReady Local DB
        local_cand = next((c for c in candidates if c.raw_provider_name == "PackReady Local DB"), None)
        if local_cand:
            return ProductKnowledgeLookupResponse(
                found=True,
                match={
                    "name": local_cand.name,
                    "brand": local_cand.brand,
                    "description": local_cand.description,
                    "unit_value": local_cand.unit_value,
                    "unit_type": local_cand.unit_type,
                },
                identifiers=[{"type": identifier_type, "value": identifier_value}],
                images=local_cand.images,
                sources=local_cand.sources,
                confidence=ProductKnowledgeConfidence.HIGH,
                provider_status=provider_status,
            )

        # External candidate aggregation
        best_candidate = candidates[0]

        # Determine confidence
        confidence = ProductKnowledgeConfidence.MEDIUM
        if len(candidates) > 1:
            # Check agreement between provider candidates
            brands = [c.brand.lower() for c in candidates if c.brand]
            names = [c.name.lower() for c in candidates if c.name]

            brand_agreement = len(set(brands)) == 1 if brands else False

            # Name agreement check: check if words overlap
            name_words_0 = set(names[0].split()) if names else set()
            name_words_1 = set(names[1].split()) if len(names) > 1 else set()
            name_agreement = bool(name_words_0.intersection(name_words_1))

            if brand_agreement or name_agreement:
                confidence = ProductKnowledgeConfidence.HIGH
            elif len(set(brands)) > 1:
                confidence = ProductKnowledgeConfidence.LOW

        # Consolidate non-null fields
        final_name = next((c.name for c in candidates if c.name), best_candidate.name)
        final_brand = next((c.brand for c in candidates if c.brand), best_candidate.brand)
        final_desc = next((c.description for c in candidates if c.description), best_candidate.description)
        final_uval = next((c.unit_value for c in candidates if c.unit_value is not None), best_candidate.unit_value)
        final_utype = next((c.unit_type for c in candidates if c.unit_type), best_candidate.unit_type)

        # Consolidate images & sources preserving provenance
        combined_images: List[CandidateImage] = []
        seen_img_urls = set()
        for c in candidates:
            for img in c.images:
                if img.url not in seen_img_urls:
                    seen_img_urls.add(img.url)
                    combined_images.append(img)

        combined_sources: List[CandidateSource] = []
        for c in candidates:
            combined_sources.extend(c.sources)

        return ProductKnowledgeLookupResponse(
            found=True,
            match={
                "name": final_name,
                "brand": final_brand,
                "description": final_desc,
                "unit_value": final_uval,
                "unit_type": final_utype,
            },
            identifiers=[{"type": identifier_type, "value": identifier_value}],
            images=combined_images,
            sources=combined_sources,
            confidence=confidence,
            provider_status=provider_status,
        )
