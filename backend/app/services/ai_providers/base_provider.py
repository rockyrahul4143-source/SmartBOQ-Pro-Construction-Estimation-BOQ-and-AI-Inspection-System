"""
Base AI Provider Interface
==========================

Abstract base class and data models for structural document understanding.
All AI providers must implement this interface to ensure consistency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Union
import base64

class DocumentType(Enum):
    """Types of structural documents that can be processed."""
    BEAM_SCHEDULE = "beam_schedule"
    COLUMN_SCHEDULE = "column_schedule"
    SLAB_SCHEDULE = "slab_schedule"
    FOOTING_SCHEDULE = "footing_schedule"
    FOUNDATION_DRAWING = "foundation_drawing"
    COLUMN_REDUCTION = "column_reduction"
    BEAM_DETAIL = "beam_detail"
    SLAB_DETAIL = "slab_detail"
    STRUCTURAL_PLAN = "structural_plan"
    FRAMING_PLAN = "framing_plan"
    SHEAR_WALL_SCHEDULE = "shear_wall_schedule"
    GENERAL_NOTES = "general_notes"
    REINFORCEMENT_DETAIL = "reinforcement_detail"
    SECTION = "section"
    ELEVATION = "elevation"
    UNKNOWN_STRUCTURAL = "unknown_structural"
    OTHER = "other"

class ValidationStatus(Enum):
    """Status of extracted data validation."""
    VALIDATED = "validated"
    ACCEPTABLE = "acceptable"
    VERIFICATION_REQUIRED = "verification_required"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"

@dataclass
class SourceReference:
    """Tracks the source of extracted information for traceability."""
    document_name: str
    page_number: int
    region: Optional[str] = None  # Bounding box or region description
    extraction_method: str = "ai_vision"  # ai_vision, ai_text, ocr, manual
    confidence: float = 0.0
    raw_text: Optional[str] = None

@dataclass
class StructuralMember:
    """
    Normalized structural member data extracted from documents.
    Supports all member types with flexible field structure.
    """
    # Core identification
    mark: str
    member_type: str  # beam, column, slab, footing, shear_wall, stair, other
    
    # Physical properties (all optional, varies by member type)
    size: Optional[str] = None  # e.g., "300x450", "375x780"
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    
    # Reinforcement (flexible structure)
    main_reinforcement: Optional[str] = None  # Primary bars
    top_reinforcement: Optional[str] = None
    bottom_reinforcement: Optional[str] = None
    extra_reinforcement: Optional[str] = None
    lateral_reinforcement: Optional[str] = None  # Stirrups/ties
    lateral_spacing: Optional[str] = None
    
    # Materials
    concrete_grade: Optional[str] = None  # M25, M30, etc.
    steel_grade: Optional[str] = None     # Fe500, Fe415, etc.
    cover_mm: Optional[int] = None
    
    # Location context
    floor_level: Optional[str] = None
    grid_location: Optional[str] = None
    
    # Geometry (if available from drawings)
    clear_span_mm: Optional[float] = None
    storey_height_mm: Optional[float] = None
    
    # Source and validation
    source_references: List[SourceReference] = field(default_factory=list)
    field_sources: Dict[str, SourceReference] = field(default_factory=dict)
    validation_status: ValidationStatus = ValidationStatus.VERIFICATION_REQUIRED
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Raw values (preserve original text)
    raw_values: Dict[str, str] = field(default_factory=dict)
    
    # Additional flexible fields
    additional_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExtractionRequest:
    """Request for AI document understanding."""
    # Document content
    pdf_bytes: Optional[bytes] = None
    image_bytes: Optional[bytes] = None
    text_content: Optional[str] = None
    
    # Document metadata
    filename: str = "document"
    document_type_hint: Optional[DocumentType] = None
    
    # Extraction parameters
    extract_tables: bool = True
    extract_diagrams: bool = True
    extract_dimensions: bool = True
    extract_notes: bool = True
    
    # AI provider settings
    model_override: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

@dataclass
class ExtractionResponse:
    """Response from AI document understanding."""
    # Classification
    document_type: DocumentType
    confidence: float
    
    # Extracted members
    members: List[StructuralMember] = field(default_factory=list)
    
    # Additional extracted information
    project_info: Dict[str, Any] = field(default_factory=dict)
    general_notes: List[str] = field(default_factory=list)
    dimensions: List[Dict[str, Any]] = field(default_factory=list)
    materials: List[Dict[str, Any]] = field(default_factory=list)
    
    # Processing metadata
    provider: str = ""
    model: str = ""
    processing_time_ms: int = 0
    tokens_used: int = 0
    
    # Quality indicators
    extraction_quality: str = "unknown"  # high, medium, low, failed
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Source tracking
    pages_processed: int = 0
    extraction_methods_used: List[str] = field(default_factory=list)
    
    # Raw AI response (for debugging)
    raw_response: Optional[str] = None

class AIError(Exception):
    """Custom exception for AI provider errors."""
    def __init__(self, message: str, provider: str = "", error_code: str = ""):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code

class AIProvider(ABC):
    """
    Abstract base class for AI providers.
    
    All providers must implement document classification and entity extraction
    while maintaining consistent output format and error handling.
    """
    
    def __init__(self, api_key: str, model: str = "", **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider configuration and API key."""
        pass
    
    @abstractmethod
    def classify_document(
        self, 
        request: ExtractionRequest
    ) -> DocumentType:
        """
        Classify the type of structural document.
        
        Args:
            request: Document content and metadata
            
        Returns:
            DocumentType enum value
            
        Raises:
            AIError: If classification fails
        """
        pass
    
    @abstractmethod
    def extract_structural_data(
        self, 
        request: ExtractionRequest
    ) -> ExtractionResponse:
        """
        Extract structural members and related data from document.
        
        Args:
            request: Document content and extraction parameters
            
        Returns:
            ExtractionResponse with normalized structural data
            
        Raises:
            AIError: If extraction fails
        """
        pass
    
    def process_document(
        self, 
        request: ExtractionRequest
    ) -> ExtractionResponse:
        """
        High-level document processing: classify + extract.
        
        Default implementation calls classify_document then extract_structural_data.
        Providers can override for optimized single-pass processing.
        """
        try:
            # Classification
            doc_type = self.classify_document(request)
            
            # Update request with classification result
            if not request.document_type_hint:
                request.document_type_hint = doc_type
            
            # Extraction
            response = self.extract_structural_data(request)
            response.document_type = doc_type
            
            return response
            
        except Exception as e:
            # Return error response instead of raising
            return ExtractionResponse(
                document_type=DocumentType.OTHER,
                confidence=0.0,
                provider=self.__class__.__name__,
                extraction_quality="failed",
                errors=[str(e)]
            )
    
    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 string for API calls."""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def _create_source_reference(
        self,
        document_name: str,
        page_num: int = 1,
        confidence: float = 0.0,
        region: str = None
    ) -> SourceReference:
        """Helper to create consistent source references."""
        return SourceReference(
            document_name=document_name,
            page_number=page_num,
            region=region,
            extraction_method="ai_vision",
            confidence=confidence
        )