from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm import Session
from app.product_knowledge.schemas import ProductCandidate


class ProductKnowledgeProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider for metadata & status logging."""
        pass

    @abstractmethod
    async def lookup_by_barcode(
        self, db: Session, identifier_type: str, normalized_value: str
    ) -> Optional[ProductCandidate]:
        """
        Look up a product candidate by normalized identifier value.
        Returns a ProductCandidate if resolved, or None if unknown/failed.
        Must NOT mutate database state or create inventory records.
        """
        pass
