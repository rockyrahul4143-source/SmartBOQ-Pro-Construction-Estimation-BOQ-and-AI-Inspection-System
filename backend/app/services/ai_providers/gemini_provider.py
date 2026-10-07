"""
Google Gemini AI Provider
==========================

Gemini provider for structural document understanding and entity extraction.
Optimized for engineering drawings, schedules, and technical documents.
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .base_provider import (
    AIProvider,
    DocumentType, 
    ExtractionRequest,
    ExtractionResponse,
    StructuralMember,
    SourceReference,
    ValidationStatus,
    AIError
)

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    """
    Google Gemini provider for structural document understanding.
    
    Supports both vision and text-based extraction using Gemini Pro models.
    """
    
    def __init__(self, api_key: str, model: str = "", **kwargs):
        # Default model selection
        if not model:
            model = "gemini-1.5-flash"  # Good balance of speed/capability for document understanding
        
        super().__init__(api_key, model, **kwargs)
        
        # Gemini-specific configuration
        self.max_tokens = kwargs.get("max_tokens", 4000)
        self.temperature = kwargs.get("temperature", 0.1)
        self.safety_settings = kwargs.get("safety_settings", "default")
    
    def _validate_config(self) -> None:
        """Validate Gemini configuration."""
        if not self.api_key:
            raise AIError("Gemini API key is required", provider="gemini")
        
        # Validate model name
        valid_models = [
            "gemini-1.5-flash", "gemini-1.5-pro", 
            "gemini-pro", "gemini-pro-vision"
        ]
        
        if self.model not in valid_models:
            logger.warning(f"[Gemini] Unrecognized model: {self.model}. Using gemini-1.5-flash")
            self.model = "gemini-1.5-flash"
    
    def classify_document(self, request: ExtractionRequest) -> DocumentType:
        """
        Classify structural document type using Gemini.
        
        Uses a focused classification prompt to determine document type
        from content, filename, and visual layout.
        """
        try:
            prompt = self._get_classification_prompt(request.filename)
            
            response = self._call_gemini_api(
                prompt=prompt,
                image_data=request.image_bytes or self._pdf_to_image(request.pdf_bytes),
                text_context=request.text_content,
                max_tokens=500,  # Classification needs fewer tokens
                temperature=0.0  # Deterministic classification
            )
            
            # Parse classification response
            doc_type = self._parse_classification(response)
            logger.info(f"[Gemini] Classified document as: {doc_type.value}")
            
            return doc_type
            
        except Exception as e:
            logger.error(f"[Gemini] Classification failed: {e}")
            # Fallback to filename-based classification
            return self._classify_by_filename(request.filename)
    
    def extract_structural_data(self, request: ExtractionRequest) -> ExtractionResponse:
        """
        Extract structural members and data using Gemini vision/text capabilities.
        
        Uses specialized prompts based on document type to extract:
        - Member marks and properties
        - Reinforcement details  
        - Materials and specifications
        - Dimensional information
        """
        start_time = time.time()
        
        try:
            # Get document type for targeted extraction
            doc_type = request.document_type_hint or self.classify_document(request)
            
            # Build extraction prompt based on document type
            prompt = self._get_extraction_prompt(doc_type)
            
            # Call Gemini API
            response = self._call_gemini_api(
                prompt=prompt,
                image_data=request.image_bytes or self._pdf_to_image(request.pdf_bytes),
                text_context=request.text_content,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Parse structured response
            extraction_data = self._parse_extraction_response(response, request.filename)
            
            # Build response
            processing_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResponse(
                document_type=doc_type,
                confidence=extraction_data.get("confidence", 0.8),
                members=extraction_data.get("members", []),
                project_info=extraction_data.get("project_info", {}),
                general_notes=extraction_data.get("notes", []),
                dimensions=extraction_data.get("dimensions", []),
                materials=extraction_data.get("materials", []),
                provider="gemini",
                model=self.model,
                processing_time_ms=processing_time,
                extraction_quality=extraction_data.get("quality", "medium"),
                warnings=extraction_data.get("warnings", []),
                pages_processed=1,
                extraction_methods_used=["ai_vision", "ai_text"],
                raw_response=response[:2000] if isinstance(response, str) else None
            )
            
        except Exception as e:
            logger.error(f"[Gemini] Extraction failed: {e}")
            processing_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResponse(
                document_type=DocumentType.OTHER,
                confidence=0.0,
                provider="gemini",
                model=self.model,
                processing_time_ms=processing_time,
                extraction_quality="failed",
                errors=[str(e)]
            )
    
    def _call_gemini_api(
        self,
        prompt: str,
        image_data: Optional[bytes] = None,
        text_context: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        """
        Make API call to Gemini with proper error handling and retry logic.
        
        Args:
            prompt: The instruction prompt
            image_data: Optional image bytes (PDF page, diagram, etc.)
            text_context: Optional extracted text content
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Returns:
            API response text
            
        Raises:
            AIError: If API call fails after retries
        """
        try:
            import google.generativeai as genai
            
            # Configure API
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            
            # Build content parts
            parts = [prompt]
            
            # Add text context if provided
            if text_context and len(text_context.strip()) > 50:
                parts.append(f"\n\nExtracted Text Content:\n{text_context[:8000]}")
            
            # Add image if provided
            if image_data:
                # Convert bytes to PIL Image for Gemini
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(image_data))
                parts.append(image)
            
            # Generation config
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.8,
                "top_k": 40
            }
            
            # Safety settings (lenient for technical documents)
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
            
            # Make API call with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = model.generate_content(
                        parts,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    )
                    
                    if response.text:
                        return response.text
                    else:
                        # Handle blocked or empty responses
                        if response.candidates:
                            candidate = response.candidates[0]
                            if hasattr(candidate, 'finish_reason'):
                                raise AIError(
                                    f"Content generation blocked: {candidate.finish_reason}",
                                    provider="gemini"
                                )
                        raise AIError("Empty response from Gemini", provider="gemini")
                        
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise AIError(f"Gemini API call failed: {e}", provider="gemini")
                    
                    logger.warning(f"[Gemini] Attempt {attempt + 1} failed: {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
            
        except ImportError:
            raise AIError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai",
                provider="gemini"
            )
    
    def _get_classification_prompt(self, filename: str) -> str:
        """Generate document classification prompt."""
        return f"""You are an expert structural engineer analyzing engineering documents.

Classify this structural document into one of these categories:

**SCHEDULES:**
- beam_schedule: Schedule of beams with reinforcement details
- column_schedule: Schedule of columns with reinforcement details  
- slab_schedule: Schedule of slabs with reinforcement details
- footing_schedule: Foundation/footing schedules

**DRAWINGS:**
- structural_plan: Structural layout/framing plans
- foundation_drawing: Foundation plans and details
- beam_detail: Beam reinforcement details and sections
- slab_detail: Slab reinforcement details and sections
- reinforcement_detail: General reinforcement details

**SPECIALIZED:**
- column_reduction: Column reduction drawings showing reinforcement changes by floor
- general_notes: Structural specifications and general notes
- other: Other structural documents

**ANALYSIS:**
1. Examine the document title, headers, and overall layout
2. Look for schedules/tables with member marks (EB1, C1, etc.)
3. Identify reinforcement notation (3-16, 8mm@150, etc.)
4. Check for drawings, dimensions, and details

**FILENAME:** {filename}

Respond with ONLY the category name (e.g., "beam_schedule", "structural_plan").
No explanation needed - just the classification."""
    
    def _get_extraction_prompt(self, doc_type: DocumentType) -> str:
        """Generate extraction prompt based on document type."""
        
        base_prompt = """You are an expert structural engineer extracting data from engineering documents.

CRITICAL RULES:
1. Extract ONLY what you can clearly see - never guess or assume values
2. Preserve original notation exactly as written
3. Mark uncertain extractions clearly
4. Use "NOT_FOUND" for missing information
5. Flag conflicts between different sources

Return a JSON object with this structure:
{
    "confidence": 0.0-1.0,
    "quality": "high|medium|low", 
    "members": [...],
    "project_info": {"project_name": "", "drawing_number": "", "date": ""},
    "notes": [...],
    "warnings": [...],
    "materials": [...]
}"""

        if doc_type == DocumentType.BEAM_SCHEDULE:
            return base_prompt + """

**BEAM SCHEDULE EXTRACTION:**

For each beam in the schedule, extract:

```json
{
    "mark": "EB1",
    "member_type": "beam",
    "size": "300x450",
    "main_reinforcement": "3-16",
    "top_reinforcement": "2-12", 
    "bottom_reinforcement": "3-16",
    "extra_reinforcement": "2-12 (support)",
    "lateral_reinforcement": "8mm",
    "lateral_spacing": "150",
    "concrete_grade": "M25",
    "steel_grade": "Fe500",
    "cover_mm": 25,
    "floor_level": "Ground Floor",
    "raw_values": {
        "original_size": "300 x 450",
        "original_top_bars": "2T12", 
        "original_stirrups": "8Ø @ 150 c/c"
    },
    "validation_status": "validated|verification_required|not_found",
    "source_references": [{
        "document_name": "filename",
        "page_number": 1,
        "region": "Row 3, Column 2-5",
        "confidence": 0.9
    }]
}
```

**MEMBER MARKS:** Look for beam identifiers like EB1, B1, TB1, GB1, HB1, etc.
**SIZE FORMAT:** Convert various formats (300x450, 300 X 450, 300*450) to standardized "300x450"
**REINFORCEMENT:** Preserve notation (3-16, 3T16, 3#16, 3Y16) but normalize to "count-diameter"
**SPACING:** Extract stirrup/tie spacing (150, @150, 150c/c, 150 C/C)"""

        elif doc_type == DocumentType.COLUMN_SCHEDULE:
            return base_prompt + """

**COLUMN SCHEDULE EXTRACTION:**

For each column in the schedule, extract:

```json
{
    "mark": "C1",
    "member_type": "column", 
    "size": "300x600",
    "main_reinforcement": "8-20",
    "lateral_reinforcement": "8mm",
    "lateral_spacing": "100",
    "concrete_grade": "M30",
    "steel_grade": "Fe500", 
    "cover_mm": 40,
    "floor_level": "All Floors",
    "storey_height_mm": 3000,
    "additional_data": {
        "foundation_level": "8-25",
        "ground_floor": "8-20", 
        "typical_floors": "6-16"
    }
}
```

**FLOOR VARIATIONS:** Many column schedules show different reinforcement by floor level
**MEMBER MARKS:** Look for C1, EC1, COL-1, P1, etc.
**TIES/STIRRUPS:** Extract tie diameter and spacing"""

        else:
            # Generic extraction for other document types
            return base_prompt + """

**GENERIC STRUCTURAL EXTRACTION:**

Extract any structural members visible:
- Member marks (any alphanumeric identifiers)
- Dimensions and sizes
- Reinforcement details
- Material specifications
- Notes and specifications

Use the member JSON format but adapt fields as needed for the document type."""
    
    def _parse_classification(self, response: str) -> DocumentType:
        """Parse classification response."""
        # Clean response
        classification = response.strip().lower()
        
        # Remove common prefixes/suffixes
        for prefix in ["classification:", "category:", "type:"]:
            if classification.startswith(prefix):
                classification = classification[len(prefix):].strip()
        
        # Map to DocumentType
        classification_map = {
            "beam_schedule": DocumentType.BEAM_SCHEDULE,
            "column_schedule": DocumentType.COLUMN_SCHEDULE,
            "slab_schedule": DocumentType.SLAB_SCHEDULE,
            "footing_schedule": DocumentType.FOOTING_SCHEDULE,
            "foundation_drawing": DocumentType.FOUNDATION_DRAWING,
            "structural_plan": DocumentType.STRUCTURAL_PLAN,
            "framing_plan": DocumentType.FRAMING_PLAN,
            "beam_detail": DocumentType.BEAM_DETAIL,
            "slab_detail": DocumentType.SLAB_DETAIL,
            "column_reduction": DocumentType.COLUMN_REDUCTION,
            "reinforcement_detail": DocumentType.REINFORCEMENT_DETAIL,
            "general_notes": DocumentType.GENERAL_NOTES,
            "other": DocumentType.OTHER
        }
        
        return classification_map.get(classification, DocumentType.OTHER)
    
    def _parse_extraction_response(self, response: str, filename: str) -> Dict[str, Any]:
        """Parse structured extraction response from Gemini."""
        try:
            # Clean JSON response (remove markdown code blocks if present)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            elif cleaned.startswith("```"):
                lines = cleaned.split("\n")  
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Convert members to StructuralMember objects
            members = []
            for member_dict in data.get("members", []):
                # Create source reference
                source_refs = []
                for ref_dict in member_dict.get("source_references", []):
                    source_refs.append(SourceReference(
                        document_name=ref_dict.get("document_name", filename),
                        page_number=ref_dict.get("page_number", 1),
                        region=ref_dict.get("region"),
                        extraction_method="ai_vision",
                        confidence=ref_dict.get("confidence", 0.8)
                    ))
                
                # Map validation status
                status_str = member_dict.get("validation_status", "verification_required")
                validation_status = {
                    "validated": ValidationStatus.VALIDATED,
                    "acceptable": ValidationStatus.ACCEPTABLE, 
                    "verification_required": ValidationStatus.VERIFICATION_REQUIRED,
                    "not_found": ValidationStatus.NOT_FOUND,
                    "conflict": ValidationStatus.CONFLICT
                }.get(status_str, ValidationStatus.VERIFICATION_REQUIRED)
                
                # Create StructuralMember
                member = StructuralMember(
                    mark=member_dict.get("mark", ""),
                    member_type=member_dict.get("member_type", "unknown"),
                    size=member_dict.get("size"),
                    main_reinforcement=member_dict.get("main_reinforcement"),
                    top_reinforcement=member_dict.get("top_reinforcement"),
                    bottom_reinforcement=member_dict.get("bottom_reinforcement"), 
                    extra_reinforcement=member_dict.get("extra_reinforcement"),
                    lateral_reinforcement=member_dict.get("lateral_reinforcement"),
                    lateral_spacing=member_dict.get("lateral_spacing"),
                    concrete_grade=member_dict.get("concrete_grade"),
                    steel_grade=member_dict.get("steel_grade"),
                    cover_mm=member_dict.get("cover_mm"),
                    floor_level=member_dict.get("floor_level"),
                    clear_span_mm=member_dict.get("clear_span_mm"),
                    storey_height_mm=member_dict.get("storey_height_mm"),
                    source_references=source_refs,
                    validation_status=validation_status,
                    raw_values=member_dict.get("raw_values", {}),
                    additional_data=member_dict.get("additional_data", {})
                )
                members.append(member)
            
            return {
                "confidence": data.get("confidence", 0.8),
                "quality": data.get("quality", "medium"),
                "members": members,
                "project_info": data.get("project_info", {}),
                "notes": data.get("notes", []),
                "warnings": data.get("warnings", []),
                "materials": data.get("materials", []),
                "dimensions": data.get("dimensions", [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"[Gemini] JSON parse error: {e}")
            logger.debug(f"[Gemini] Raw response: {response[:1000]}")
            
            # Fallback: try to extract member marks from text
            return self._fallback_text_extraction(response, filename)
        
        except Exception as e:
            logger.error(f"[Gemini] Response parsing error: {e}")
            return {
                "confidence": 0.1,
                "quality": "low", 
                "members": [],
                "warnings": [f"Response parsing failed: {e}"]
            }
    
    def _fallback_text_extraction(self, response: str, filename: str) -> Dict[str, Any]:
        """Fallback extraction when JSON parsing fails."""
        import re
        
        # Try to extract member marks from text response
        members = []
        
        # Look for common beam/column patterns
        beam_pattern = r'\b(EB|TB|GB|HB|B)[\-\s]*(\d+)\b'
        col_pattern = r'\b(EC|C|COL)[\-\s]*(\d+)\b'
        
        beam_matches = re.findall(beam_pattern, response, re.IGNORECASE)
        col_matches = re.findall(col_pattern, response, re.IGNORECASE)
        
        for prefix, num in beam_matches:
            mark = f"{prefix.upper()}{num}"
            member = StructuralMember(
                mark=mark,
                member_type="beam",
                validation_status=ValidationStatus.VERIFICATION_REQUIRED,
                source_references=[SourceReference(
                    document_name=filename,
                    page_number=1,
                    extraction_method="ai_text_fallback",
                    confidence=0.3
                )]
            )
            members.append(member)
        
        for prefix, num in col_matches:
            mark = f"{prefix.upper()}{num}"
            member = StructuralMember(
                mark=mark, 
                member_type="column",
                validation_status=ValidationStatus.VERIFICATION_REQUIRED,
                source_references=[SourceReference(
                    document_name=filename,
                    page_number=1,
                    extraction_method="ai_text_fallback", 
                    confidence=0.3
                )]
            )
            members.append(member)
        
        return {
            "confidence": 0.3,
            "quality": "low",
            "members": members,
            "warnings": ["JSON parsing failed, used fallback text extraction"]
        }
    
    def _classify_by_filename(self, filename: str) -> DocumentType:
        """Fallback classification based on filename."""
        fn = filename.lower()
        
        if any(word in fn for word in ["beam", "bm"]):
            return DocumentType.BEAM_SCHEDULE
        elif any(word in fn for word in ["column", "col"]):
            return DocumentType.COLUMN_SCHEDULE  
        elif "slab" in fn:
            return DocumentType.SLAB_SCHEDULE
        elif "foundation" in fn or "footing" in fn:
            return DocumentType.FOUNDATION_DRAWING
        else:
            return DocumentType.OTHER
    
    def _pdf_to_image(self, pdf_bytes: Optional[bytes]) -> Optional[bytes]:
        """Convert PDF first page to PNG bytes for vision processing."""
        if not pdf_bytes:
            return None
        
        try:
            import pymupdf  # PyMuPDF
            import io
            
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]  # First page only
            
            # Render at high DPI for better text recognition
            mat = pymupdf.Matrix(2.0, 2.0)  # 144 DPI
            pix = page.get_pixmap(matrix=mat)
            
            return pix.tobytes("png")
            
        except ImportError:
            logger.warning("[Gemini] PyMuPDF not available for PDF rendering")
            return None
        except Exception as e:
            logger.warning(f"[Gemini] PDF to image conversion failed: {e}")
            return None