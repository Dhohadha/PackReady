import enum
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.products.models import SourceType


class ProductKnowledgeConfidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class CandidateSource(BaseModel):
    provider_name: str
    source_type: SourceType
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class CandidateImage(BaseModel):
    url: str
    provider: str
    image_role: Optional[str] = "REFERENCE"

    model_config = ConfigDict(from_attributes=True)


class ProductCandidate(BaseModel):
    identifier_type: str
    identifier_value: str
    name: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    unit_value: Optional[float] = None
    unit_type: Optional[str] = None
    images: List[CandidateImage] = Field(default_factory=list)
    sources: List[CandidateSource] = Field(default_factory=list)
    raw_provider_name: str = ""

    model_config = ConfigDict(from_attributes=True)


class ProductKnowledgeLookupResponse(BaseModel):
    found: bool
    match: Optional[Dict[str, Any]] = None
    identifiers: List[Dict[str, str]] = Field(default_factory=list)
    images: List[CandidateImage] = Field(default_factory=list)
    sources: List[CandidateSource] = Field(default_factory=list)
    confidence: ProductKnowledgeConfidence = ProductKnowledgeConfidence.UNKNOWN
    provider_status: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
