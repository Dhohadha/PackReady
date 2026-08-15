from typing import Optional, List
from sqlalchemy.orm import Session

from app.product_knowledge.orchestrator import ProviderOrchestrator
from app.product_knowledge.providers.base import ProductKnowledgeProvider
from app.product_knowledge.schemas import ProductKnowledgeLookupResponse


class ProductKnowledgeService:
    def __init__(self, orchestrator: Optional[ProviderOrchestrator] = None):
        self.orchestrator = orchestrator or ProviderOrchestrator()

    async def lookup_product(
        self, db: Session, identifier_type: str, value: str
    ) -> ProductKnowledgeLookupResponse:
        return await self.orchestrator.lookup(db, identifier_type, value)
