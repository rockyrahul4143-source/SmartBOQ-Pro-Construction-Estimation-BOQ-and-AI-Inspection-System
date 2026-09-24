"""
BBS Extraction Engine
=====================
Parses uploaded files (PDF/DXF/DWG) and extracts structured BBS data.

Supports ANY layout — not tied to one specific schedule format.
Uses pattern matching on text content to find beam/column marks,
sizes, reinforcement, stirrups, cover, etc.

For DXF: uses geometry + text entities.
For PDF: uses text layer extraction.
For images: returns not_supported with guidance.

All extracted values carry a source field so the cross-file engine
can rank and conflict-check them.
"""
from __future__ import annotations
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Source priority labels ─────────────────────────────
SRC_SCHEDULE  = "drawing_schedule"
SRC_SECTION   = "drawing_section"
SRC_NOTE      = "general_note"
SRC_DXF       = "dxf_geometry"
SRC_DERIVED   = "derived"
SRC_USER      = "user_input"

VERIFY   = "VERIFY_REQUIRED"
CONFLICT = "CONFLICT_DETECTED"
MISSING  = "NOT_FOUND"


# ── Regex patterns for beam/column data ───────────────

# Beam mark: EB1, EB2X, TB1, HB1, EMB1, B1, GB1, etc.
_BEAM_MARK_RE = re.compile(
    r'\b(E?MB\d+|[A-Z]B\d+[A-Z0-9]*|EB\d+[A-Z0-9]*|TB\d+|HB\d+|B\d+[A-Z0-9]*)\b',
    re.IGNORECASE
)

# Column mark: EC1, C1, CC1, etc.
_COL_MARK_RE = re.compile(
    r'\b(E?C\s*\d+[\w,]*|CC?\d+[A-Z0-9]*)\b',
    re.IGNORECASE
)

# Size like 300X450, 300×450, 300x450
_SIZE_RE = re.compile(r'(\d{2,4})\s*[xX×]\s*(\d{2,4})')

# Reinforcement: 3-16#, 3-16Ø, 2T16, 3Y16, 3-16φ, 3 nos 16mm
_REBAR_RE = re.compile(
    r'(\d+)\s*[-–]?\s*(\d{1,2})\s*[#ØφTY@]?\s*(?:mm|dia|Ø|φ)?',
    re.IGNORECASE
)

# Stirrup / tie: 8Ø@150, T8@150, 8#@125
_STIRRUP_RE = re.compile(
    r'(\d{1,2})\s*[#ØφTY@]?\s*[@C/]\s*(\d{2,4})',
    re.IGNORECASE
)

# Cover: 25mm, cover=40, clear cover 25
_COVER_RE = re.compile(
    r'(?:clear\s+)?cover\s*[=:–-]?\s*(\d{1,3})\s*mm',
    re.IGNORECASE
)

# Floor / storey
_FLOOR_RE = re.compile(
    r'(ground|first|second|third|4th|5th|6th|7th|8th|9th|10th|GF|1F|2F|3F|FF|SF|TF|terrace|foundation)',
    re.IGNORECASE
)

# Lap / development length
_LAP_RE = re.compile(r'lap\s*[=:–]?\s*(\d+)\s*mm', re.IGNORECASE)
_DEV_RE = re.compile(r'development\s*length\s*[=:–]?\s*(\d+)\s*mm', re.IGNORECASE)

# fck / fy
_FCK_RE = re.compile(r'M\s*(\d{2})', re.IGNORECASE)
_FY_RE  = re.compile(r'Fe\s*(\d{3,4})', re.IGNORECASE)


def _extract_size(text: str) -> Optional[tuple]:
    m = _SIZE_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _extract_rebar(text: str) -> list[dict]:
    """Extract all rebar specs from a text string."""
    results = []
    for m in _REBAR_RE.finditer(text):
        num, dia = int(m.group(1)), int(m.group(2))
        if 4 <= dia <= 50 and 1 <= num <= 30:
            results.append({"num": num, "dia": dia, "raw": m.group(0).strip()})
    return results


def _extract_stirrup(text: str) -> Optional[dict]:
    m = _STIRRUP_RE.search(text)
    if m:
        dia, spacing = int(m.group(1)), int(m.group(2))
        if 4 <= dia <= 32 and 50 <= spacing <= 600:
            return {"dia": dia, "spacing": spacing, "raw": m.group(0).strip()}
    return None


# ── PDF text extraction ────────────────────────────────

def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract all text from PDF using pdfminer if available."""
    try:
        from pdfminer.high_level import extract_text
        import io
        text = extract_text(io.BytesIO(file_bytes))
        return text or ""
    except ImportError:
        pass
    # Fallback: try pypdf
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except ImportError:
        pass
    return ""


# ── Parse beam schedule from text ─────────────────────

def _parse_beam_schedule(text: str) -> dict:
    """
    Parse beam schedule from any text layout.
    Returns {beam_mark: {size, top_steel, bottom_steel, stirrups, ...}}
    """
    beams: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Global values
    fck = fy = cover = None
    for ln in lines:
        if not fck:
            m = _FCK_RE.search(ln)
            if m: fck = int(m.group(1))
        if not fy:
            m = _FY_RE.search(ln)
            if m: fy = int(m.group(1))
        if not cover:
            m = _COVER_RE.search(ln)
            if m: cover = int(m.group(1))

    # Find beam marks and associate data
    for i, line in enumerate(lines):
        marks = _BEAM_MARK_RE.findall(line)
        if not marks:
            continue

        # Collect context — current line + a few around it
        ctx_start = max(0, i - 1)
        ctx_end   = min(len(lines), i + 6)
        context   = " ".join(lines[ctx_start:ctx_end])

        for mark in marks:
            mark = mark.upper().strip()
            if mark in beams:
                continue  # already parsed

            size = _extract_size(context)
            rebars = _extract_rebar(context)
            stirrup = _extract_stirrup(context)

            # Try to split top/bottom by position in line
            top_bars    = []
            bottom_bars = []
            # Heuristic: first rebar group = top, second = bottom
            if len(rebars) >= 2:
                top_bars    = [rebars[0]]
                bottom_bars = [rebars[1]]
            elif len(rebars) == 1:
                bottom_bars = [rebars[0]]

            beams[mark] = {
                "mark":         mark,
                "size":         {"b": size[0], "d": size[1]} if size else None,
                "top_steel":    top_bars,
                "bottom_steel": bottom_bars,
                "all_rebars":   rebars,
                "stirrups":     stirrup,
                "cover":        cover,
                "fck":          fck,
                "fy":           fy,
                "source":       SRC_SCHEDULE,
                "raw_context":  context[:300],
            }

    return beams


# ── Parse column schedule from text ───────────────────

def _parse_column_schedule(text: str) -> dict:
    """
    Parse column schedule from any text layout.
    Returns {col_mark: {floors: [{floor, size, steel, ties, ...}]}}
    """
    columns: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    fck = fy = cover = None
    for ln in lines:
        if not fck:
            m = _FCK_RE.search(ln)
            if m: fck = int(m.group(1))
        if not fy:
            m = _FY_RE.search(ln)
            if m: fy = int(m.group(1))
        if not cover:
            m = _COVER_RE.search(ln)
            if m: cover = int(m.group(1))

    for i, line in enumerate(lines):
        marks = _COL_MARK_RE.findall(line)
        if not marks:
            continue

        ctx_start = max(0, i - 1)
        ctx_end   = min(len(lines), i + 8)
        context   = " ".join(lines[ctx_start:ctx_end])

        for mark_raw in marks:
            # Normalise — "EC 2,37" → try each
            for mark in re.split(r'[,\s]+', mark_raw.strip()):
                mark = mark.upper().strip()
                if not mark or len(mark) < 2:
                    continue
                if mark in columns:
                    continue

                size    = _extract_size(context)
                rebars  = _extract_rebar(context)
                stirrup = _extract_stirrup(context)
                floors  = _FLOOR_RE.findall(context)

                columns[mark] = {
                    "mark":    mark,
                    "size":    {"b": size[0], "d": size[1]} if size else None,
                    "steel":   rebars,
                    "ties":    stirrup,
                    "floors":  floors,
                    "cover":   cover,
                    "fck":     fck,
                    "fy":      fy,
                    "source":  SRC_SCHEDULE,
                    "raw_context": context[:300],
                }

    return columns


# ── DXF geometry extraction ───────────────────────────

def _parse_dxf(file_bytes: bytes) -> dict:
    """Extract geometry + text from DXF for BBS context."""
    from app.services.dxf_parser import parse_dxf_bytes
    result = parse_dxf_bytes(file_bytes)
    d = result.to_dict()

    diag = d.get("diagnostics", {})
    ext  = diag.get("drawing_extents", {})

    return {
        "type":              "dxf_geometry",
        "building_footprint_m2": d.get("building_footprint_area_m2", 0),
        "wall_length_m":     d.get("total_wall_length_m", 0),
        "drawing_extents":   ext,
        "boundary_candidates": d.get("boundary_candidates", [])[:5],
        "units_detected":    d.get("units_detected"),
        "scale_factor":      d.get("scale_factor"),
        "entity_counts":     d.get("entity_counts", {}),
        "warnings":          d.get("warnings", []),
        "source":            SRC_DXF,
    }


# ── Detect file category from filename + content ──────

def _detect_category(filename: str, text: str) -> str:
    fn = filename.lower()
    tx = text[:2000].lower()

    if any(k in fn or k in tx for k in ["beam schedule", "schedule of beam", "beam sch"]):
        return "beam_schedule"
    if any(k in fn or k in tx for k in ["column schedule", "schedule of column", "col sch", "col. sch"]):
        return "column_schedule"
    if any(k in fn or k in tx for k in ["slab schedule", "schedule of slab"]):
        return "slab_schedule"
    if any(k in fn or k in tx for k in ["footing", "foundation", "raft"]):
        return "foundation_schedule"
    if fn.endswith(".dxf") or fn.endswith(".dwg"):
        return "structural_plan_cad"
    if any(k in fn or k in tx for k in ["structural plan", "framing plan", "layout"]):
        return "structural_plan"
    if any(k in fn or k in tx for k in ["reinforcement", "rcc detail", "detail"]):
        return "reinforcement_detail"
    if any(k in fn or k in tx for k in ["section", "elevation"]):
        return "section_elevation"
    if any(k in fn or k in tx for k in ["general note", "specification"]):
        return "general_notes"
    return "other"


# ── MAIN ENTRY POINT ──────────────────────────────────

def extract_file(file_bytes: bytes, filename: str, file_type: str) -> dict:
    """
    Main extraction function. Processes any file type and returns
    a structured dict with all extractable BBS-relevant data.

    Returns:
        {
            "file_type": ...,
            "category": ...,
            "beams": {mark: {...}},
            "columns": {mark: {...}},
            "slabs": {},
            "geometry": {},
            "global_params": {fck, fy, cover, ...},
            "raw_text": "...",
            "member_list": [...],
            "warnings": [...],
            "extraction_status": "complete"|"partial"|"not_supported",
        }
    """
    result = {
        "file_type":   file_type,
        "category":    "other",
        "beams":       {},
        "columns":     {},
        "slabs":       {},
        "geometry":    {},
        "global_params": {},
        "raw_text":    "",
        "member_list": [],
        "warnings":    [],
        "extraction_status": "pending",
    }

    try:
        if file_type == "dxf":
            geo = _parse_dxf(file_bytes)
            result["geometry"] = geo
            result["category"] = "structural_plan_cad"
            result["extraction_status"] = "complete"

        elif file_type == "pdf":
            text = _extract_pdf_text(file_bytes)
            result["raw_text"] = text[:50000]   # cap to avoid huge JSON
            result["category"] = _detect_category(filename, text)

            if text:
                beams   = _parse_beam_schedule(text)
                columns = _parse_column_schedule(text)
                result["beams"]   = beams
                result["columns"] = columns

                # Global params from text
                fck_m = _FCK_RE.search(text)
                fy_m  = _FY_RE.search(text)
                cov_m = _COVER_RE.search(text)
                result["global_params"] = {
                    "fck":   int(fck_m.group(1)) if fck_m else None,
                    "fy":    int(fy_m.group(1))  if fy_m  else None,
                    "cover": int(cov_m.group(1)) if cov_m else None,
                }
                result["extraction_status"] = "complete" if (beams or columns) else "partial"
                if not text.strip():
                    result["warnings"].append(
                        "PDF text layer is empty — this may be a scanned image. "
                        "Text extraction requires a text-layer PDF. "
                        "For scanned drawings, please extract the schedule data manually."
                    )
            else:
                result["warnings"].append(
                    "No text could be extracted from this PDF. "
                    "It may be a scanned/image PDF. Use manual BBS entry to input schedule values."
                )
                result["extraction_status"] = "not_supported"

        else:
            result["warnings"].append(
                f"File type '{file_type}' is not directly supported for automatic extraction. "
                "For DWG files: open in AutoCAD → Save As → DXF 2010 ASCII → re-upload. "
                "For images: enter schedule values manually in the BBS form."
            )
            result["extraction_status"] = "not_supported"

        # Build member list
        all_marks = list(result["beams"].keys()) + list(result["columns"].keys())
        result["member_list"] = sorted(set(all_marks))
        result["category"]    = _detect_category(filename, result.get("raw_text","")[:500])

    except Exception as e:
        logger.error(f"Extraction error for {filename}: {e}")
        result["warnings"].append(f"Extraction error: {e}")
        result["extraction_status"] = "failed"

    return result
