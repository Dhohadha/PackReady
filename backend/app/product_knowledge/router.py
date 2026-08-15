from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.product_knowledge.service import ProductKnowledgeService
from app.product_knowledge.schemas import ProductKnowledgeLookupResponse

router = APIRouter(prefix="/product-knowledge", tags=["Product Knowledge"])


@router.get("/lookup", response_model=ProductKnowledgeLookupResponse)
async def lookup_product_knowledge(
    identifier_type: str,
    value: str,
    db: Session = Depends(get_db),
) -> ProductKnowledgeLookupResponse:
    """
    Perform read-only multi-provider discovery lookup for a barcode.
    Queries local PackReady database first; falls back to external sources if unknown.
    MUST NOT mutate database records or create store inventory.
    """
    try:
        service = ProductKnowledgeService()
        return await service.lookup_product(db, identifier_type, value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/dataset-stats")
def get_dataset_statistics(db: Session = Depends(get_db)):
    """
    Get read-only dataset statistics and coverage metrics across reference, merchant, and training images.
    """
    from app.products.dataset_service import ProductDatasetService
    return ProductDatasetService.get_dataset_stats(db)


@router.get("/dataset-manifest")
def get_dataset_manifest(db: Session = Depends(get_db)):
    """
    Get model-agnostic ML dataset manifest for approved training images.
    """
    from app.products.dataset_service import ProductDatasetService
    return ProductDatasetService.export_dataset_manifest(db)
