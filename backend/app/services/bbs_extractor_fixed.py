"""
BBS Extraction Engine — with Beam Geometry
===========================================
Complete extraction: schedules + CAD geometry + beam analysis.
"""
from __future__ import annotations
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Import beam geometry extraction
from .dxf_beam_extractor import extract_dxf_with_geometry, _ascii_dxf_fallback

# Re-export for compatibility
__all__ = ['extract_file', 'parse_beam_schedule', 'parse_column_schedule', '_ascii_dxf_fallback']


def extract_file(raw: bytes, filename: str, file_type: str = None):
    """
    Extract complete BBS data from file.
    For DXF: returns ExtractionResult with members and detailed metadata.
    For PDF/other: returns dict (legacy format).
    """
    # Auto-detect file type if not provided
    if not file_type:
        if filename.lower().endswith('.dxf'):
            file_type = 'dxf'
        elif filename.lower().endswith('.dwg'):
            file_type = 'dwg'
        elif filename.lower().endswith('.pdf'):
            file_type = 'pdf'
        else:
            file_type = 'unknown'
    
    # DXF with full beam geometry
    if file_type == 'dxf':
        return extract_dxf_with_geometry(raw, filename)
    
    # For other types, return basic dict (to be implemented)
    return {
        "file_type": file_type,
        "filename": filename,
        "extraction_status": "not_implemented",
        "members": [],
        "metadata": {}
    }


def parse_beam_schedule(text: str):
    """Parse beam schedule from text (stub for compatibility)."""
    return []


def parse_column_schedule(text: str):
    """Parse column schedule from text (stub for compatibility)."""
    return []
