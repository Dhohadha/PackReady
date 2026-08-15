import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.product_knowledge.normalization import normalize_identifier_value
from app.product_knowledge.providers.base import ProductKnowledgeProvider
from app.product_knowledge.providers.packready_provider import PackReadyProvider
from app.product_knowledge.providers.openfoodfacts_provider import OpenFoodFactsProvider
from app.product_knowledge.providers.upcitemdb_provider import UPCItemDbProvider
from app.product_knowledge.aggregator import CandidateAggregator
from app.product_knowledge.schemas import ProductCandidate, ProductKnowledgeLookupResponse

logger = logging.getLogger(__name__)


class ProviderOrchestrator:
    def __init__(self, providers: Optional[List[ProductKnowledgeProvider]] = None):
        if providers is None:
            self.providers = [
                PackReadyProvider(),
                OpenFoodFactsProvider(),
                UPCItemDbProvider(),
            ]
        else:
            self.providers = providers

    async def lookup(
        self, db: Session, identifier_type: str, raw_value: str
    ) -> ProductKnowledgeLookupResponse:
        normalized_value = normalize_identifier_value(raw_value)
        provider_status: Dict[str, str] = {}
        collected_candidates: List[ProductCandidate] = []

        for provider in self.providers:
            # Short-circuit check: If local DB already found product, stop querying external providers
            if isinstance(provider, PackReadyProvider):
                try:
                    cand = await provider.lookup_by_barcode(db, identifier_type, normalized_value)
                    if cand:
                        provider_status[provider.name] = "FOUND"
                        return CandidateAggregator.aggregate(
                            candidates=[cand],
                            provider_status=provider_status,
                            identifier_type=identifier_type,
                            identifier_value=normalized_value,
                        )
                    else:
                        provider_status[provider.name] = "NOT_FOUND"
                except Exception as e:
                    logger.error(f"Error in PackReadyProvider: {e}")
                    provider_status[provider.name] = "UNAVAILABLE"
                continue

            # Query external provider
            try:
                cand = await provider.lookup_by_barcode(db, identifier_type, normalized_value)
                if cand:
                    provider_status[provider.name] = "FOUND"
                    collected_candidates.append(cand)
                else:
                    provider_status[provider.name] = "NOT_FOUND"
            except Exception as e:
                logger.error(f"Error in {provider.name}: {e}")
                provider_status[provider.name] = "UNAVAILABLE"

        return CandidateAggregator.aggregate(
            candidates=collected_candidates,
            provider_status=provider_status,
            identifier_type=identifier_type,
            identifier_value=normalized_value,
        )
