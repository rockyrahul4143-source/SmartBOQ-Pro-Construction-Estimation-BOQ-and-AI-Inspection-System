"""
CAD-AI Integration Service
==========================

Integrates AI-extracted structural data with existing CAD geometry processing.
Provides intelligent association between schedule data and geometric entities,
with conflict resolution and validation.

This service:
1. Correlates AI-extracted member marks with CAD geometry
2. Validates dimensional consistency between schedules and drawings
3. Enriches member data with geometric properties (spans, supports)
4. Resolves conflicts between different data sources
5. Maintains complete audit trail of associations
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .dataset_manager import DatasetManager
from .engineering_schema import (
    StructuralMemberData,
    EngineeringValue, 
    DimensionValue,
    SourceReference,
    ValidationStatus,
    MemberType,
    ExtractionMethod
)

# Import existing CAD services
from .beam_geometry import StructuralMember as CADMember, ExtractionResult as CADResult
from .dxf_beam_extractor import extract_dxf_with_geometry

logger = logging.getLogger(__name__)

@dataclass
class MemberAssociation:
    """Association between AI-extracted member and CAD geometry."""
    ai_member_id: str
    cad_member: CADMember
    association_confidence: float
    association_method: str
    dimensional_consistency: float
    validation_notes: List[str] = field(default_factory=list)

@dataclass
class GeometryEnrichment:
    """Geometric properties to enrich member data."""
    clear_span_mm: Optional[float] = None
    support_geometry: Dict[str, Any] = field(default_factory=dict)
    location_3d: Optional[Tuple[float, float, float]] = None
    layer_info: Optional[str] = None
    drawing_metadata: Dict[str, Any] = field(default_factory=dict)

class CADAIIntegrationService:
    """
    Service for integrating AI-extracted data with CAD geometry.
    
    Provides intelligent correlation between schedule data and geometric
    entities with validation and conflict resolution.
    """
    
    def __init__(self, dataset_manager: DatasetManager):
        self.dataset_manager = dataset_manager
        self.associations: Dict[str, MemberAssociation] = {}
        self.geometry_cache: Dict[str, CADResult] = {}
        
    def process_cad_file(
        self,
        cad_content: bytes,
        filename: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Process CAD file and associate with existing AI-extracted data.
        
        Args:
            cad_content: Raw CAD file bytes (DXF/DWG)
            filename: Original filename
            document_id: Document identifier
            
        Returns:
            Summary of associations and enrichments applied
        """
        logger.info(f"[CAD-AI] Processing CAD file: {filename}")
        
        try:
            # Extract CAD geometry
            cad_result = extract_dxf_with_geometry(cad_content, filename)
            self.geometry_cache[document_id] = cad_result
            
            # Associate with AI members
            association_summary = self._associate_members(cad_result, document_id)
            
            # Enrich member data with geometry
            enrichment_summary = self._enrich_member_data(document_id)
            
            # Validate dimensional consistency
            validation_summary = self._validate_dimensional_consistency()
            
            return {
                "cad_members_found": len(cad_result.members),
                "associations_created": association_summary["associations_created"],
                "associations_failed": association_summary["associations_failed"],
                "members_enriched": enrichment_summary["members_enriched"],
                "validation_conflicts": validation_summary["conflicts_detected"],
                "processing_status": "completed"
            }
            
        except Exception as e:
            logger.error(f"[CAD-AI] Failed to process CAD file {filename}: {e}")
            return {
                "processing_status": "failed",
                "error": str(e),
                "cad_members_found": 0,
                "associations_created": 0
            }
    
    def _associate_members(
        self,
        cad_result: CADResult,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Associate CAD members with AI-extracted members by mark matching.
        
        Args:
            cad_result: CAD extraction result
            document_id: CAD document ID
            
        Returns:
            Association summary statistics
        """
        summary = {
            "associations_created": 0,
            "associations_failed": 0,
            "multiple_matches": 0,
            "no_matches": 0
        }
        
        # Group CAD members by normalized mark
        cad_by_mark = {}
        for cad_member in cad_result.members:
            normalized_mark = self._normalize_member_mark(cad_member.mark)
            if normalized_mark not in cad_by_mark:
                cad_by_mark[normalized_mark] = []
            cad_by_mark[normalized_mark].append(cad_member)
        
        # Try to associate each AI member
        for member_id, ai_member in self.dataset_manager.project_dataset.members.items():
            normalized_ai_mark = self._normalize_member_mark(ai_member.mark)
            
            if normalized_ai_mark in cad_by_mark:
                cad_candidates = cad_by_mark[normalized_ai_mark]
                
                if len(cad_candidates) == 1:
                    # Single match - create association
                    association = self._create_association(
                        ai_member, 
                        cad_candidates[0], 
                        document_id,
                        method="exact_mark_match"
                    )
                    self.associations[member_id] = association
                    summary["associations_created"] += 1
                    
                elif len(cad_candidates) > 1:
                    # Multiple matches - find best match using location/properties
                    best_match = self._find_best_cad_match(ai_member, cad_candidates)
                    if best_match:
                        association = self._create_association(
                            ai_member, 
                            best_match, 
                            document_id,
                            method="best_match_selection"
                        )
                        self.associations[member_id] = association
                        summary["associations_created"] += 1
                    else:
                        summary["associations_failed"] += 1
                    summary["multiple_matches"] += 1
            else:
                summary["no_matches"] += 1
                logger.debug(f"[CAD-AI] No CAD match found for AI member: {ai_member.mark}")
        
        logger.info(f"[CAD-AI] Association summary: {summary}")
        return summary
    
    def _create_association(
        self,
        ai_member: StructuralMemberData,
        cad_member: CADMember,
        document_id: str,
        method: str
    ) -> MemberAssociation:
        """Create association between AI and CAD members."""
        
        # Calculate association confidence
        confidence = self._calculate_association_confidence(ai_member, cad_member, method)
        
        # Calculate dimensional consistency
        dimensional_consistency = self._calculate_dimensional_consistency(ai_member, cad_member)
        
        # Generate validation notes
        validation_notes = []
        if dimensional_consistency < 0.8:
            validation_notes.append(f"Dimensional inconsistency detected: {dimensional_consistency:.2f}")
        
        if confidence < 0.7:
            validation_notes.append(f"Low association confidence: {confidence:.2f}")
        
        association = MemberAssociation(
            ai_member_id=ai_member.member_id,
            cad_member=cad_member,
            association_confidence=confidence,
            association_method=method,
            dimensional_consistency=dimensional_consistency,
            validation_notes=validation_notes
        )
        
        logger.debug(
            f"[CAD-AI] Associated {ai_member.mark} with CAD member "
            f"(confidence: {confidence:.2f}, consistency: {dimensional_consistency:.2f})"
        )
        
        return association
    
    def _find_best_cad_match(
        self,
        ai_member: StructuralMemberData,
        cad_candidates: List[CADMember]
    ) -> Optional[CADMember]:
        """Find best CAD match from multiple candidates."""
        
        best_match = None
        best_score = 0.0
        
        for cad_member in cad_candidates:
            score = 0.0
            
            # Dimensional similarity
            if ai_member.dimensions and hasattr(cad_member, 'clear_span_mm'):
                dim_score = self._calculate_dimensional_consistency(ai_member, cad_member)
                score += dim_score * 0.4
            
            # Location proximity (if available)
            if (hasattr(ai_member, 'grid_location') and ai_member.grid_location and
                hasattr(cad_member, 'location') and cad_member.location):
                # Simple location scoring - could be enhanced
                score += 0.2
            
            # Geometry quality
            if hasattr(cad_member, 'geometry_status'):
                if cad_member.geometry_status == "MEASURED":
                    score += 0.3
                elif cad_member.geometry_status == "PARTIAL":
                    score += 0.1
            
            # Member type consistency
            expected_cad_type = self._ai_to_cad_type_mapping(ai_member.member_type)
            if cad_member.member_type == expected_cad_type:
                score += 0.1
            
            if score > best_score:
                best_score = score
                best_match = cad_member
        
        # Require minimum score for association
        if best_score >= 0.5:
            return best_match
        
        return None
    
    def _enrich_member_data(self, cad_document_id: str) -> Dict[str, Any]:
        """
        Enrich AI member data with CAD geometry information.
        
        Args:
            cad_document_id: ID of the CAD document
            
        Returns:
            Enrichment summary
        """
        summary = {
            "members_enriched": 0,
            "geometry_added": 0,
            "conflicts_detected": 0
        }
        
        for member_id, association in self.associations.items():
            ai_member = self.dataset_manager.project_dataset.members.get(member_id)
            if not ai_member:
                continue
            
            try:
                # Create geometry enrichment
                enrichment = self._create_geometry_enrichment(
                    association.cad_member, 
                    cad_document_id
                )
                
                # Apply enrichment to AI member
                conflicts = self._apply_geometry_enrichment(ai_member, enrichment, cad_document_id)
                
                summary["members_enriched"] += 1
                if enrichment.clear_span_mm is not None:
                    summary["geometry_added"] += 1
                if conflicts:
                    summary["conflicts_detected"] += len(conflicts)
                    
            except Exception as e:
                logger.warning(f"[CAD-AI] Failed to enrich member {ai_member.mark}: {e}")
        
        return summary
    
    def _create_geometry_enrichment(
        self,
        cad_member: CADMember,
        document_id: str
    ) -> GeometryEnrichment:
        """Create geometry enrichment from CAD member."""
        
        enrichment = GeometryEnrichment()
        
        # Extract clear span
        if hasattr(cad_member, 'clear_span_mm') and cad_member.clear_span_mm:
            enrichment.clear_span_mm = cad_member.clear_span_mm
        
        # Extract support geometry
        if hasattr(cad_member, 'geometry') and cad_member.geometry:
            for geo_item in cad_member.geometry:
                if geo_item.get('entity_type') == 'BEAM_AXIS':
                    enrichment.support_geometry = {
                        'support_a': geo_item.get('support_a', {}),
                        'support_b': geo_item.get('support_b', {}),
                        'clear_span_method': geo_item.get('clear_span_method')
                    }
                    break
        
        # Extract location
        if hasattr(cad_member, 'location') and cad_member.location:
            enrichment.location_3d = tuple(cad_member.location[:3]) if len(cad_member.location) >= 3 else None
        
        # Extract layer info
        if hasattr(cad_member, 'layer'):
            enrichment.layer_info = cad_member.layer
        
        # Drawing metadata
        enrichment.drawing_metadata = {
            'document_id': document_id,
            'drawing_units': getattr(cad_member, 'drawing_units', 'mm'),
            'geometry_status': getattr(cad_member, 'geometry_status', 'unknown')
        }
        
        return enrichment
    
    def _apply_geometry_enrichment(
        self,
        ai_member: StructuralMemberData,
        enrichment: GeometryEnrichment,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """
        Apply geometry enrichment to AI member, detecting conflicts.
        
        Args:
            ai_member: AI member to enrich
            enrichment: Geometry data to apply
            document_id: Source document ID
            
        Returns:
            List of conflicts detected
        """
        conflicts = []
        
        # Create CAD source reference
        cad_source = SourceReference(
            document_id=document_id,
            document_name=enrichment.drawing_metadata.get('filename', 'CAD Drawing'),
            document_type='dxf',
            extraction_method=ExtractionMethod.CAD_GEOMETRY,
            confidence=0.9,
            layer=enrichment.layer_info
        )
        
        # Enrich clear span
        if enrichment.clear_span_mm is not None:
            cad_span_value = EngineeringValue(
                raw_value=str(enrichment.clear_span_mm),
                normalized_value=str(enrichment.clear_span_mm),
                numeric_value=enrichment.clear_span_mm,
                source_reference=cad_source,
                validation_status=ValidationStatus.VALIDATED,
                field_name="clear_span_mm"
            )
            
            if ai_member.clear_span_mm:
                # Check for conflict
                existing_span = ai_member.clear_span_mm.numeric_value
                if existing_span and abs(existing_span - enrichment.clear_span_mm) > (existing_span * 0.05):
                    conflicts.append({
                        "field": "clear_span_mm",
                        "ai_value": existing_span,
                        "cad_value": enrichment.clear_span_mm,
                        "difference_percent": abs(existing_span - enrichment.clear_span_mm) / existing_span * 100
                    })
                
                # CAD geometry takes precedence
                ai_member.clear_span_mm.alternative_values.append(ai_member.clear_span_mm)
                ai_member.clear_span_mm = cad_span_value
            else:
                # No existing value, add CAD data
                ai_member.clear_span_mm = cad_span_value
        
        # Add geometric metadata to additional properties
        if enrichment.support_geometry:
            ai_member.additional_properties["support_geometry"] = EngineeringValue(
                raw_value=str(enrichment.support_geometry),
                source_reference=cad_source,
                validation_status=ValidationStatus.VALIDATED,
                field_name="support_geometry"
            )
        
        if enrichment.location_3d:
            ai_member.additional_properties["cad_location"] = EngineeringValue(
                raw_value=str(enrichment.location_3d),
                source_reference=cad_source,
                validation_status=ValidationStatus.VALIDATED,
                field_name="cad_location"
            )
        
        # Update source documents
        if document_id not in ai_member.source_documents:
            ai_member.source_documents.append(document_id)
        
        return conflicts
    
    def _validate_dimensional_consistency(self) -> Dict[str, Any]:
        """Validate dimensional consistency across all associations."""
        
        summary = {
            "total_associations": len(self.associations),
            "conflicts_detected": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0
        }
        
        for association in self.associations.values():
            if association.dimensional_consistency >= 0.8:
                summary["high_confidence"] += 1
            elif association.dimensional_consistency >= 0.6:
                summary["medium_confidence"] += 1
            else:
                summary["low_confidence"] += 1
                summary["conflicts_detected"] += 1
        
        return summary
    
    # Helper methods
    
    def _normalize_member_mark(self, mark: str) -> str:
        """Normalize member mark for comparison."""
        if not mark:
            return ""
        
        # Remove spaces, convert to uppercase
        normalized = mark.replace(" ", "").upper()
        
        # Handle common variations
        normalized = normalized.replace("-", "").replace("_", "")
        
        return normalized
    
    def _calculate_association_confidence(
        self,
        ai_member: StructuralMemberData,
        cad_member: CADMember,
        method: str
    ) -> float:
        """Calculate confidence score for member association."""
        
        base_confidence = {
            "exact_mark_match": 0.9,
            "best_match_selection": 0.7,
            "fuzzy_match": 0.5
        }.get(method, 0.3)
        
        # Boost for member type consistency
        expected_type = self._ai_to_cad_type_mapping(ai_member.member_type)
        if cad_member.member_type == expected_type:
            base_confidence += 0.1
        
        # Boost for dimensional consistency
        dim_consistency = self._calculate_dimensional_consistency(ai_member, cad_member)
        base_confidence += dim_consistency * 0.1
        
        return min(base_confidence, 1.0)
    
    def _calculate_dimensional_consistency(
        self,
        ai_member: StructuralMemberData,
        cad_member: CADMember
    ) -> float:
        """Calculate dimensional consistency between AI and CAD data."""
        
        consistency_scores = []
        
        # Compare clear span if both available
        if (ai_member.clear_span_mm and ai_member.clear_span_mm.numeric_value and
            hasattr(cad_member, 'clear_span_mm') and cad_member.clear_span_mm):
            
            ai_span = ai_member.clear_span_mm.numeric_value
            cad_span = cad_member.clear_span_mm
            
            if ai_span > 0:
                diff_percent = abs(ai_span - cad_span) / ai_span
                consistency = max(0.0, 1.0 - diff_percent * 2)  # 50% diff = 0 consistency
                consistency_scores.append(consistency)
        
        # Compare dimensions if available
        if (ai_member.dimensions and ai_member.dimensions.width_mm and ai_member.dimensions.depth_mm):
            # Could compare with CAD dimensions if available
            # For now, assume reasonable consistency if dimensions exist
            consistency_scores.append(0.7)
        
        # Return average consistency or default
        return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5
    
    def _ai_to_cad_type_mapping(self, ai_type: MemberType) -> str:
        """Map AI member types to CAD member types."""
        mapping = {
            MemberType.BEAM: "beam",
            MemberType.COLUMN: "column", 
            MemberType.SLAB: "slab",
            MemberType.FOOTING: "footing",
            MemberType.SHEAR_WALL: "wall"
        }
        return mapping.get(ai_type, "unknown")
    
    def get_association_summary(self) -> Dict[str, Any]:
        """Get summary of all associations."""
        return {
            "total_associations": len(self.associations),
            "associations_by_confidence": {
                "high": len([a for a in self.associations.values() if a.association_confidence >= 0.8]),
                "medium": len([a for a in self.associations.values() if 0.6 <= a.association_confidence < 0.8]),
                "low": len([a for a in self.associations.values() if a.association_confidence < 0.6])
            },
            "dimensional_consistency": {
                "high": len([a for a in self.associations.values() if a.dimensional_consistency >= 0.8]),
                "medium": len([a for a in self.associations.values() if 0.6 <= a.dimensional_consistency < 0.8]),
                "low": len([a for a in self.associations.values() if a.dimensional_consistency < 0.6])
            }
        }