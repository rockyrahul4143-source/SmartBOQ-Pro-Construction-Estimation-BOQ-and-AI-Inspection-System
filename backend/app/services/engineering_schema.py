"""
Structured Engineering Data Schema
==================================

Normalized JSON schema for structural engineering data extraction with complete
source traceability, conflict resolution, and validation status tracking.

This schema supports:
- Multi-document cross-referencing
- Format-independent data normalization  
- Engineering terminology standardization
- Complete audit trail for every extracted value
- Conflict detection and resolution
- Validation status tracking
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import json
import uuid
from datetime import datetime

class MemberType(Enum):
    """Standard structural member types."""
    BEAM = "beam"
    COLUMN = "column" 
    SLAB = "slab"
    FOOTING = "footing"
    SHEAR_WALL = "shear_wall"
    STAIR = "stair"
    RETAINING_WALL = "retaining_wall"
    PILE = "pile"
    OTHER = "other"

class MaterialGrade(Enum):
    """Standard concrete and steel grades."""
    # Concrete grades (IS 456)
    M15 = "M15"
    M20 = "M20" 
    M25 = "M25"
    M30 = "M30"
    M35 = "M35"
    M40 = "M40"
    M45 = "M45"
    M50 = "M50"
    
    # Steel grades (IS 1786)
    FE415 = "Fe415"
    FE500 = "Fe500"
    FE550 = "Fe550"

class UnitType(Enum):
    """Engineering units for dimensions and measurements."""
    MM = "mm"
    CM = "cm"
    M = "m"
    INCHES = "inches"
    FEET = "feet"

class ExtractionMethod(Enum):
    """Methods used for data extraction."""
    AI_VISION = "ai_vision"
    AI_TEXT = "ai_text"
    OCR = "ocr"
    PDF_TEXT = "pdf_text"
    TABLE_EXTRACTION = "table_extraction"
    CAD_GEOMETRY = "cad_geometry"
    MANUAL_INPUT = "manual_input"
    CALCULATED = "calculated"

class ValidationStatus(Enum):
    """Validation status for extracted data."""
    VALIDATED = "validated"              # Confirmed accurate
    ACCEPTABLE = "acceptable"            # Reasonable but not perfect
    VERIFICATION_REQUIRED = "verification_required"  # Needs review
    NOT_FOUND = "not_found"             # Information missing
    CONFLICT = "conflict"               # Multiple conflicting values
    CALCULATED = "calculated"           # Derived from other values

@dataclass
class SourceReference:
    """
    Complete source traceability for extracted values.
    
    Every extracted engineering value must have source information
    to enable verification and audit trail.
    """
    # Document identification
    document_id: str
    document_name: str
    document_type: str  # pdf, dxf, dwg, image, excel
    
    # Location within document
    page_number: Optional[int] = None
    region: Optional[str] = None  # "Table 1, Row 3, Col 2" or bounding box
    layer: Optional[str] = None   # CAD layer name
    
    # Extraction details
    extraction_method: ExtractionMethod = ExtractionMethod.AI_VISION
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Quality indicators
    confidence: float = 0.0  # 0.0 to 1.0
    raw_text: Optional[str] = None  # Original text before normalization
    
    # AI provider details (if applicable)
    ai_provider: Optional[str] = None  # gemini, openai, anthropic
    ai_model: Optional[str] = None
    ai_processing_time_ms: Optional[int] = None

@dataclass  
class EngineeringValue:
    """
    A single engineering value with complete traceability.
    
    Stores both original and normalized values to preserve evidence
    while enabling standardized processing.
    """
    # Value content
    raw_value: str                      # Original text as extracted
    source_reference: SourceReference   # Source tracking (required)
    normalized_value: Optional[str] = None    # Standardized format
    numeric_value: Optional[float] = None     # Numeric conversion if applicable
    unit: Optional[UnitType] = None           # Engineering unit
    
    # Validation
    validation_status: ValidationStatus = ValidationStatus.VERIFICATION_REQUIRED
    
    # Alternative values (for conflicts)
    alternative_values: List['EngineeringValue'] = field(default_factory=list)
    
    # Metadata
    field_name: str = ""  # e.g., "top_reinforcement", "concrete_grade"
    notes: Optional[str] = None

@dataclass
class ReinforcementDetail:
    """Detailed reinforcement specification with normalization."""
    # Bar configuration
    bar_count: Optional[int] = None
    bar_diameter_mm: Optional[int] = None
    bar_grade: Optional[MaterialGrade] = None
    
    # Spacing (for stirrups/ties)
    spacing_mm: Optional[float] = None
    
    # Position/type
    position: Optional[str] = None  # top, bottom, extra, stirrup, tie
    
    # Source and validation
    raw_notation: str = ""  # Original text (e.g., "3-16T", "8@150")
    normalized_notation: Optional[str] = None  # Standardized (e.g., "3-16")
    source_reference: Optional[SourceReference] = None
    validation_status: ValidationStatus = ValidationStatus.VERIFICATION_REQUIRED
    
    # Additional specifications
    hook_type: Optional[str] = None
    development_length_mm: Optional[float] = None
    lap_length_mm: Optional[float] = None

@dataclass
class DimensionValue:
    """Physical dimensions with unit handling and source traceability."""
    value_mm: Optional[float] = None
    original_value: Optional[str] = None
    original_unit: Optional[UnitType] = None
    
    # For cross-sections (e.g., "300x450")
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    
    # Source tracking
    source_reference: Optional[SourceReference] = None
    validation_status: ValidationStatus = ValidationStatus.VERIFICATION_REQUIRED
    measurement_method: Optional[str] = None  # "schedule", "drawing", "calculated"

@dataclass
class StructuralMemberData:
    """
    Complete structural member data with normalized schema.
    
    Supports all member types with flexible field structure while
    maintaining engineering accuracy and source traceability.
    """
    # Core identification
    member_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mark: str = ""
    member_type: MemberType = MemberType.OTHER
    
    # Physical properties
    dimensions: Optional[DimensionValue] = None
    
    # Reinforcement (comprehensive)
    main_reinforcement: List[ReinforcementDetail] = field(default_factory=list)
    secondary_reinforcement: List[ReinforcementDetail] = field(default_factory=list)
    lateral_reinforcement: List[ReinforcementDetail] = field(default_factory=list)
    
    # Materials
    concrete_grade: Optional[EngineeringValue] = None
    steel_grade: Optional[EngineeringValue] = None
    cover_mm: Optional[EngineeringValue] = None
    
    # Geometry (from CAD or drawings)
    clear_span_mm: Optional[EngineeringValue] = None
    storey_height_mm: Optional[EngineeringValue] = None
    
    # Location context
    floor_level: Optional[EngineeringValue] = None
    grid_location: Optional[EngineeringValue] = None
    
    # Source documents
    source_documents: List[str] = field(default_factory=list)
    
    # Data quality
    completeness_score: float = 0.0  # 0.0 to 1.0
    validation_summary: Dict[str, ValidationStatus] = field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Flexible additional data
    additional_properties: Dict[str, EngineeringValue] = field(default_factory=dict)
    
    # Processing metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ProjectDataset:
    """
    Project-level engineering dataset with cross-document relationships.
    
    Manages multiple documents and their extracted data with conflict
    resolution and cross-referencing capabilities.
    """
    # Project identification
    project_id: str
    project_name: str = ""
    
    # Document registry
    documents: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Member registry (normalized across all documents)
    members: Dict[str, StructuralMemberData] = field(default_factory=dict)
    
    # Cross-document relationships
    member_instances: Dict[str, List[str]] = field(default_factory=dict)  # mark -> [member_ids]
    
    # Project-level information
    general_specifications: List[EngineeringValue] = field(default_factory=list)
    material_standards: List[EngineeringValue] = field(default_factory=list)
    design_parameters: Dict[str, EngineeringValue] = field(default_factory=dict)
    
    # Quality metrics
    extraction_summary: Dict[str, Any] = field(default_factory=dict)
    validation_summary: Dict[ValidationStatus, int] = field(default_factory=dict)
    
    # Processing history
    processing_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

class EngineeringDataNormalizer:
    """
    Utilities for normalizing engineering terminology and values.
    
    Handles variations in notation across different drawings and standards.
    """
    
    # Bar notation patterns
    BAR_PATTERNS = {
        r'(\d+)[-#T]\s*(\d+)': r'\1-\2',  # 3T16 -> 3-16
        r'(\d+)\s*nos?\s+(\d+)mm': r'\1-\2',  # 3 nos 16mm -> 3-16
        r'(\d+)Y(\d+)': r'\1-\2',  # 3Y16 -> 3-16
    }
    
    # Size format patterns
    SIZE_PATTERNS = {
        r'(\d+)\s*[xX×*]\s*(\d+)': r'\1x\2',  # 300 X 450 -> 300x450
        r'(\d+)\s*/\s*(\d+)': r'\1x\2',       # 300/450 -> 300x450
    }
    
    # Concrete grade synonyms
    CONCRETE_GRADES = {
        'M-20': 'M20', 'M 20': 'M20', 'M20.0': 'M20',
        'M-25': 'M25', 'M 25': 'M25', 'M25.0': 'M25',
        'M-30': 'M30', 'M 30': 'M30', 'M30.0': 'M30',
    }
    
    # Steel grade synonyms
    STEEL_GRADES = {
        'FE 415': 'Fe415', 'FE-415': 'Fe415', 'fe415': 'Fe415',
        'FE 500': 'Fe500', 'FE-500': 'Fe500', 'fe500': 'Fe500',
        'HYSD': 'Fe500',  # High Yield Strength Deformed bars
    }
    
    @classmethod
    def normalize_bar_notation(cls, raw_value: str) -> Optional[str]:
        """
        Normalize reinforcement bar notation to standard format.
        
        Examples:
            "3T16" -> "3-16"
            "3 nos 16mm dia" -> "3-16"
            "3Y16" -> "3-16"
        """
        import re
        
        if not raw_value or not isinstance(raw_value, str):
            return None
        
        cleaned = raw_value.strip().upper()
        
        for pattern, replacement in cls.BAR_PATTERNS.items():
            match = re.search(pattern, cleaned)
            if match:
                count, dia = match.groups()
                try:
                    count_int = int(count)
                    dia_int = int(dia)
                    # Validate reasonable ranges
                    if 1 <= count_int <= 50 and 6 <= dia_int <= 40:
                        return f"{count_int}-{dia_int}"
                except ValueError:
                    continue
        
        return None
    
    @classmethod
    def normalize_size_notation(cls, raw_value: str) -> Optional[str]:
        """
        Normalize size notation to standard format.
        
        Examples:
            "300 X 450" -> "300x450"
            "300/450" -> "300x450"
        """
        import re
        
        if not raw_value or not isinstance(raw_value, str):
            return None
        
        cleaned = raw_value.strip()
        
        for pattern, replacement in cls.SIZE_PATTERNS.items():
            match = re.search(pattern, cleaned)
            if match:
                w, d = match.groups()
                try:
                    w_int = int(w)
                    d_int = int(d)
                    # Validate reasonable ranges for structural members
                    if 50 <= w_int <= 5000 and 50 <= d_int <= 5000:
                        return f"{w_int}x{d_int}"
                except ValueError:
                    continue
        
        return None
    
    @classmethod
    def normalize_concrete_grade(cls, raw_value: str) -> Optional[str]:
        """Normalize concrete grade notation."""
        if not raw_value:
            return None
        
        cleaned = raw_value.strip()
        
        # Direct lookup
        normalized = cls.CONCRETE_GRADES.get(cleaned)
        if normalized:
            return normalized
        
        # Pattern matching for M-grades
        import re
        match = re.search(r'M[-\s]*(\d+)', cleaned, re.IGNORECASE)
        if match:
            grade_num = match.group(1)
            return f"M{grade_num}"
        
        return None
    
    @classmethod
    def normalize_steel_grade(cls, raw_value: str) -> Optional[str]:
        """Normalize steel grade notation."""
        if not raw_value:
            return None
        
        cleaned = raw_value.strip()
        
        # Direct lookup
        normalized = cls.STEEL_GRADES.get(cleaned)
        if normalized:
            return normalized
        
        # Pattern matching for Fe grades
        import re
        match = re.search(r'Fe[-\s]*(\d+)', cleaned, re.IGNORECASE)
        if match:
            grade_num = match.group(1)
            return f"Fe{grade_num}"
        
        return None
    
    @classmethod
    def parse_reinforcement(cls, raw_notation: str) -> Optional[ReinforcementDetail]:
        """
        Parse reinforcement notation into structured data.
        
        Args:
            raw_notation: Original reinforcement text
            
        Returns:
            ReinforcementDetail object or None if parsing fails
        """
        normalized = cls.normalize_bar_notation(raw_notation)
        if not normalized:
            return None
        
        try:
            parts = normalized.split('-')
            if len(parts) != 2:
                return None
            
            count = int(parts[0])
            diameter = int(parts[1])
            
            return ReinforcementDetail(
                bar_count=count,
                bar_diameter_mm=diameter,
                raw_notation=raw_notation,
                normalized_notation=normalized,
                validation_status=ValidationStatus.ACCEPTABLE
            )
            
        except (ValueError, IndexError):
            return None