"""
Cross-Document Engineering Dataset Manager
==========================================

Manages project-level engineering datasets with multi-document cross-referencing,
conflict resolution, and data validation. Provides intelligent merging of structural
data from various sources (schedules, drawings, CAD files, specifications).

Key Features:
- Multi-document member correlation
- Intelligent conflict detection and resolution
- Data completeness scoring
- Source priority ranking
- Validation status tracking
- Audit trail for all changes
"""

import logging
import json
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import datetime
from dataclasses import asdict
from collections import defaultdict

from .engineering_schema import (
    ProjectDataset,
    StructuralMemberData,
    EngineeringValue,
    ReinforcementDetail,
    DimensionValue,
    SourceReference,
    ValidationStatus,
    MemberType,
    ExtractionMethod,
    EngineeringDataNormalizer
)

logger = logging.getLogger(__name__)

class ConflictResolutionStrategy:
    """Strategies for resolving conflicts between multiple data sources."""
    
    # Source priority ranking (higher = more reliable)
    SOURCE_PRIORITIES = {
        ExtractionMethod.MANUAL_INPUT: 10,
        ExtractionMethod.CAD_GEOMETRY: 9,
        ExtractionMethod.TABLE_EXTRACTION: 8,
        ExtractionMethod.AI_VISION: 7,
        ExtractionMethod.AI_TEXT: 6,
        ExtractionMethod.PDF_TEXT: 5,
        ExtractionMethod.OCR: 4,
        ExtractionMethod.CALCULATED: 3
    }
    
    # Document type priority (for schedule data)
    DOCUMENT_TYPE_PRIORITIES = {
        "beam_schedule": 10,
        "column_schedule": 10,
        "slab_schedule": 10,
        "reinforcement_detail": 9,
        "beam_detail": 8,
        "column_reduction": 8,
        "structural_plan": 7,
        "general_notes": 6,
        "other": 1
    }
    
    @classmethod
    def resolve_engineering_value_conflict(
        cls,
        values: List[EngineeringValue],
        field_name: str
    ) -> Tuple[EngineeringValue, List[EngineeringValue]]:
        """
        Resolve conflicts between multiple EngineeringValue instances.
        
        Args:
            values: List of conflicting values
            field_name: Name of the field (affects resolution strategy)
            
        Returns:
            Tuple of (primary_value, alternative_values)
        """
        if not values:
            raise ValueError("No values to resolve")
        
        if len(values) == 1:
            return values[0], []
        
        # Sort by priority (highest first)
        sorted_values = sorted(
            values,
            key=lambda v: cls._calculate_value_priority(v, field_name),
            reverse=True
        )
        
        primary = sorted_values[0]
        alternatives = sorted_values[1:]
        
        # Special handling for critical fields
        if field_name in ["concrete_grade", "steel_grade"]:
            primary, alternatives = cls._resolve_material_conflict(sorted_values)
        elif field_name in ["clear_span_mm", "storey_height_mm"]:
            primary, alternatives = cls._resolve_dimension_conflict(sorted_values)
        
        # Mark conflict in primary value
        primary.alternative_values = alternatives
        
        return primary, alternatives
    
    @classmethod
    def _calculate_value_priority(cls, value: EngineeringValue, field_name: str) -> float:
        """Calculate priority score for an engineering value."""
        score = 0.0
        
        # Base priority from extraction method
        if value.source_reference:
            method_priority = cls.SOURCE_PRIORITIES.get(
                value.source_reference.extraction_method, 5
            )
            score += method_priority * 10
        
        # Confidence boost
        if value.source_reference and value.source_reference.confidence:
            score += value.source_reference.confidence * 5
        
        # Validation status boost
        validation_boost = {
            ValidationStatus.VALIDATED: 20,
            ValidationStatus.ACCEPTABLE: 15,
            ValidationStatus.VERIFICATION_REQUIRED: 10,
            ValidationStatus.NOT_FOUND: 0,
            ValidationStatus.CONFLICT: 5
        }
        score += validation_boost.get(value.validation_status, 0)
        
        # Normalized value bonus
        if value.normalized_value:
            score += 5
        
        # Numeric value bonus (for dimensions)
        if value.numeric_value is not None:
            score += 3
        
        return score
    
    @classmethod
    def _resolve_material_conflict(
        cls,
        values: List[EngineeringValue]
    ) -> Tuple[EngineeringValue, List[EngineeringValue]]:
        """Special resolution for material grades (concrete/steel)."""
        # For materials, prefer validated over calculated
        validated = [v for v in values if v.validation_status == ValidationStatus.VALIDATED]
        if validated:
            return validated[0], [v for v in values if v != validated[0]]
        
        # Prefer values with normalized notation
        normalized = [v for v in values if v.normalized_value]
        if normalized:
            return normalized[0], [v for v in values if v != normalized[0]]
        
        # Default to first (highest priority)
        return values[0], values[1:]
    
    @classmethod
    def _resolve_dimension_conflict(
        cls,
        values: List[EngineeringValue]
    ) -> Tuple[EngineeringValue, List[EngineeringValue]]:
        """Special resolution for dimensional values."""
        # For dimensions, check if values are approximately equal
        numeric_values = [v for v in values if v.numeric_value is not None]
        
        if len(numeric_values) >= 2:
            # Check if values are within 5% of each other
            nums = [v.numeric_value for v in numeric_values]
            max_val, min_val = max(nums), min(nums)
            
            if max_val > 0 and (max_val - min_val) / max_val <= 0.05:
                # Values are close - prefer CAD/manual source
                cad_values = [v for v in numeric_values 
                             if v.source_reference and 
                             v.source_reference.extraction_method == ExtractionMethod.CAD_GEOMETRY]
                if cad_values:
                    return cad_values[0], [v for v in values if v != cad_values[0]]
        
        # Default resolution
        return values[0], values[1:]

class DatasetManager:
    """
    Project-level engineering dataset manager with cross-document capabilities.
    
    Manages the complete lifecycle of engineering data from extraction to
    validation, including conflict resolution and data merging.
    """
    
    def __init__(self, project_id: str, project_name: str = ""):
        self.project_dataset = ProjectDataset(
            project_id=project_id,
            project_name=project_name
        )
        self.normalizer = EngineeringDataNormalizer()
        self.conflict_resolver = ConflictResolutionStrategy()
        
    def add_document(
        self,
        document_id: str,
        document_name: str,
        document_type: str,
        extraction_metadata: Dict[str, Any],
        members: List[StructuralMemberData]
    ) -> Dict[str, Any]:
        """
        Add a processed document and its extracted members to the dataset.
        
        Args:
            document_id: Unique document identifier
            document_name: Original document filename
            document_type: Document classification
            extraction_metadata: Processing metadata from AI provider
            members: List of extracted structural members
            
        Returns:
            Summary of conflicts detected and resolutions applied
        """
        logger.info(f"[DatasetManager] Adding document {document_name} with {len(members)} members")
        
        # Register document
        self.project_dataset.documents[document_id] = {
            "name": document_name,
            "type": document_type,
            "added_at": datetime.utcnow().isoformat(),
            "member_count": len(members),
            "extraction_metadata": extraction_metadata
        }
        
        # Process and merge members
        conflicts_summary = {
            "new_members": 0,
            "updated_members": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "validation_issues": 0
        }
        
        for member in members:
            try:
                result = self._merge_member(member, document_id)
                
                # Update summary
                if result["action"] == "created":
                    conflicts_summary["new_members"] += 1
                elif result["action"] == "updated":
                    conflicts_summary["updated_members"] += 1
                
                conflicts_summary["conflicts_detected"] += len(result.get("conflicts", []))
                conflicts_summary["conflicts_resolved"] += len(result.get("resolutions", []))
                
                if result.get("validation_issues"):
                    conflicts_summary["validation_issues"] += len(result["validation_issues"])
                    
            except Exception as e:
                logger.error(f"[DatasetManager] Failed to merge member {member.mark}: {e}")
                conflicts_summary["validation_issues"] += 1
        
        # Update dataset metadata
        self.project_dataset.updated_at = datetime.utcnow()
        self._update_extraction_summary()
        self._update_validation_summary()
        
        # Log processing
        self.project_dataset.processing_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "document_added",
            "document_id": document_id,
            "document_name": document_name,
            "conflicts_summary": conflicts_summary
        })
        
        logger.info(f"[DatasetManager] Processed {document_name}: {conflicts_summary}")
        return conflicts_summary
    
    def _merge_member(
        self,
        new_member: StructuralMemberData,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Merge a new member with existing data, resolving conflicts.
        
        Args:
            new_member: Member data to merge
            document_id: Source document ID
            
        Returns:
            Dictionary with merge results and conflict information
        """
        result = {
            "action": "unknown",
            "conflicts": [],
            "resolutions": [],
            "validation_issues": []
        }
        
        # Find existing member by mark
        existing_member_id = None
        for member_id, member in self.project_dataset.members.items():
            if member.mark.upper() == new_member.mark.upper():
                existing_member_id = member_id
                break
        
        if existing_member_id:
            # Merge with existing member
            existing_member = self.project_dataset.members[existing_member_id]
            result["action"] = "updated"
            
            # Merge fields with conflict detection
            merge_result = self._merge_member_fields(existing_member, new_member, document_id)
            result["conflicts"].extend(merge_result["conflicts"])
            result["resolutions"].extend(merge_result["resolutions"])
            
            # Update member instance tracking
            if new_member.mark not in self.project_dataset.member_instances:
                self.project_dataset.member_instances[new_member.mark] = []
            
            if existing_member_id not in self.project_dataset.member_instances[new_member.mark]:
                self.project_dataset.member_instances[new_member.mark].append(existing_member_id)
                
        else:
            # Create new member
            new_member.source_documents.append(document_id)
            member_id = new_member.member_id
            self.project_dataset.members[member_id] = new_member
            
            # Update instance tracking
            if new_member.mark not in self.project_dataset.member_instances:
                self.project_dataset.member_instances[new_member.mark] = []
            self.project_dataset.member_instances[new_member.mark].append(member_id)
            
            result["action"] = "created"
        
        return result
    
    def _merge_member_fields(
        self,
        existing: StructuralMemberData,
        new_member: StructuralMemberData,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Merge fields between existing and new member data.
        
        Args:
            existing: Existing member in dataset
            new_member: New member data to merge
            document_id: Source document for new data
            
        Returns:
            Dictionary with conflicts and resolutions
        """
        result = {
            "conflicts": [],
            "resolutions": []
        }
        
        # Add document to source list
        if document_id not in existing.source_documents:
            existing.source_documents.append(document_id)
        
        # Merge EngineeringValue fields
        value_fields = [
            "concrete_grade", "steel_grade", "cover_mm",
            "clear_span_mm", "storey_height_mm", "floor_level"
        ]
        
        for field_name in value_fields:
            existing_value = getattr(existing, field_name)
            new_value = getattr(new_member, field_name)
            
            if new_value:
                if existing_value:
                    # Conflict resolution needed
                    try:
                        resolved, alternatives = self.conflict_resolver.resolve_engineering_value_conflict(
                            [existing_value, new_value],
                            field_name
                        )
                        setattr(existing, field_name, resolved)
                        
                        result["conflicts"].append({
                            "field": field_name,
                            "existing_value": existing_value.raw_value,
                            "new_value": new_value.raw_value,
                            "resolved_value": resolved.raw_value
                        })
                        
                        result["resolutions"].append({
                            "field": field_name,
                            "strategy": "priority_based",
                            "primary_source": resolved.source_reference.document_name if resolved.source_reference else "unknown",
                            "alternative_count": len(alternatives)
                        })
                        
                    except Exception as e:
                        logger.warning(f"[DatasetManager] Failed to resolve conflict for {field_name}: {e}")
                        # Keep existing value, add new as alternative
                        if not existing_value.alternative_values:
                            existing_value.alternative_values = []
                        existing_value.alternative_values.append(new_value)
                else:
                    # No existing value, use new one
                    setattr(existing, field_name, new_value)
        
        # Merge dimensions
        if new_member.dimensions and not existing.dimensions:
            existing.dimensions = new_member.dimensions
        elif new_member.dimensions and existing.dimensions:
            # Dimension conflict resolution
            existing.dimensions = self._merge_dimensions(existing.dimensions, new_member.dimensions)
        
        # Merge reinforcement details
        existing.main_reinforcement.extend(new_member.main_reinforcement)
        existing.secondary_reinforcement.extend(new_member.secondary_reinforcement)
        existing.lateral_reinforcement.extend(new_member.lateral_reinforcement)
        
        # Remove duplicates and resolve conflicts in reinforcement
        existing.main_reinforcement = self._deduplicate_reinforcement(existing.main_reinforcement)
        existing.secondary_reinforcement = self._deduplicate_reinforcement(existing.secondary_reinforcement)
        existing.lateral_reinforcement = self._deduplicate_reinforcement(existing.lateral_reinforcement)
        
        # Merge additional properties
        for key, value in new_member.additional_properties.items():
            if key not in existing.additional_properties:
                existing.additional_properties[key] = value
            else:
                # Resolve conflict in additional properties
                try:
                    resolved, _ = self.conflict_resolver.resolve_engineering_value_conflict(
                        [existing.additional_properties[key], value],
                        key
                    )
                    existing.additional_properties[key] = resolved
                except Exception:
                    # Keep existing
                    pass
        
        # Update completeness and validation
        existing.completeness_score = max(existing.completeness_score, new_member.completeness_score)
        existing.validation_summary.update(new_member.validation_summary)
        existing.updated_at = datetime.utcnow()
        
        return result
    
    def _merge_dimensions(
        self,
        existing: DimensionValue,
        new_dim: DimensionValue
    ) -> DimensionValue:
        """Merge dimension values, preferring more complete data."""
        # Prefer CAD geometry over schedule data
        if (new_dim.source_reference and 
            new_dim.source_reference.extraction_method == ExtractionMethod.CAD_GEOMETRY):
            return new_dim
        
        # Prefer more complete dimension data
        existing_completeness = sum([
            1 if existing.value_mm else 0,
            1 if existing.width_mm else 0,
            1 if existing.depth_mm else 0
        ])
        
        new_completeness = sum([
            1 if new_dim.value_mm else 0,
            1 if new_dim.width_mm else 0,
            1 if new_dim.depth_mm else 0
        ])
        
        return new_dim if new_completeness > existing_completeness else existing
    
    def _deduplicate_reinforcement(
        self,
        reinforcements: List[ReinforcementDetail]
    ) -> List[ReinforcementDetail]:
        """Remove duplicate reinforcement details."""
        if not reinforcements:
            return []
        
        # Group by normalized notation
        groups = defaultdict(list)
        for rebar in reinforcements:
            key = rebar.normalized_notation or rebar.raw_notation
            groups[key].append(rebar)
        
        # Keep the best from each group
        deduplicated = []
        for group in groups.values():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Prefer higher validation status and better source
                best = max(group, key=lambda r: (
                    r.validation_status == ValidationStatus.VALIDATED,
                    r.source_reference.confidence if r.source_reference else 0
                ))
                deduplicated.append(best)
        
        return deduplicated
    
    def get_member_by_mark(self, mark: str) -> Optional[StructuralMemberData]:
        """Get member data by mark (case-insensitive)."""
        for member in self.project_dataset.members.values():
            if member.mark.upper() == mark.upper():
                return member
        return None
    
    def get_members_by_type(self, member_type: MemberType) -> List[StructuralMemberData]:
        """Get all members of a specific type."""
        return [
            member for member in self.project_dataset.members.values()
            if member.member_type == member_type
        ]
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get comprehensive validation summary for the project."""
        summary = {
            "total_members": len(self.project_dataset.members),
            "by_type": defaultdict(int),
            "by_validation_status": defaultdict(int),
            "completeness_distribution": defaultdict(int),
            "source_distribution": defaultdict(int),
            "conflict_count": 0
        }
        
        for member in self.project_dataset.members.values():
            # Count by type
            summary["by_type"][member.member_type.value] += 1
            
            # Count by validation status (use worst status from validation_summary)
            worst_status = ValidationStatus.VALIDATED
            for status in member.validation_summary.values():
                if status == ValidationStatus.NOT_FOUND:
                    worst_status = ValidationStatus.NOT_FOUND
                    break
                elif status == ValidationStatus.VERIFICATION_REQUIRED:
                    worst_status = ValidationStatus.VERIFICATION_REQUIRED
                elif status == ValidationStatus.CONFLICT and worst_status == ValidationStatus.VALIDATED:
                    worst_status = ValidationStatus.CONFLICT
            
            summary["by_validation_status"][worst_status.value] += 1
            
            # Completeness distribution
            completeness_bucket = int(member.completeness_score * 10) / 10
            summary["completeness_distribution"][completeness_bucket] += 1
            
            # Source distribution
            summary["source_distribution"][len(member.source_documents)] += 1
            
            # Count conflicts
            if member.conflicts:
                summary["conflict_count"] += len(member.conflicts)
        
        return dict(summary)
    
    def _update_extraction_summary(self):
        """Update project-level extraction summary."""
        self.project_dataset.extraction_summary = {
            "total_documents": len(self.project_dataset.documents),
            "total_members": len(self.project_dataset.members),
            "member_types": list(set(m.member_type.value for m in self.project_dataset.members.values())),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _update_validation_summary(self):
        """Update project-level validation summary."""
        status_counts = defaultdict(int)
        for member in self.project_dataset.members.values():
            for status in member.validation_summary.values():
                status_counts[status] += 1
        
        self.project_dataset.validation_summary = dict(status_counts)
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export dataset to dictionary format."""
        return {
            "project_id": self.project_dataset.project_id,
            "project_name": self.project_dataset.project_name,
            "documents": self.project_dataset.documents,
            "members": {
                mid: asdict(member) for mid, member in self.project_dataset.members.items()
            },
            "member_instances": self.project_dataset.member_instances,
            "extraction_summary": self.project_dataset.extraction_summary,
            "validation_summary": self.project_dataset.validation_summary,
            "created_at": self.project_dataset.created_at.isoformat(),
            "updated_at": self.project_dataset.updated_at.isoformat()
        }
    
    def export_to_json(self) -> str:
        """Export dataset to JSON string."""
        return json.dumps(self.export_to_dict(), indent=2, default=str)

# Global dataset cache for active projects
_project_datasets: Dict[str, DatasetManager] = {}

def get_dataset_manager(project_id: str, project_name: str = "") -> DatasetManager:
    """Get or create a dataset manager for a project."""
    if project_id not in _project_datasets:
        _project_datasets[project_id] = DatasetManager(project_id, project_name)
    return _project_datasets[project_id]

def clear_dataset_cache():
    """Clear the dataset cache (for testing)."""
    global _project_datasets
    _project_datasets = {}