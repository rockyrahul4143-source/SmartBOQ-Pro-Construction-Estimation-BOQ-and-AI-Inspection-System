"""
BBS Input Resolution
=====================
Generic cross-file resolution layer that assembles a single verified
engineering input dataset for any structural member BBS request.

Architecture
------------

  Project files in DB (DXF, PDF schedules, structural details, general notes)
              ↓
  Per-file extracted_data (members[], beams{}, columns{}, …)
              ↓
  Member Index  (_index_all_marks in bbs_query.py)
              ↓
  ┌───────────────────────────────────────────────────────┐
  │              bbs_input_resolution.py                  │
  │                                                       │
  │  resolve_member(mark, project_files, member_type)     │
  │                                                       │
  │    1. gather_field_candidates()                       │
  │       – DXF members[]  → geometry fields              │
  │       – beam/column schedule dicts → reinf. fields   │
  │       – structural detail PDFs → detailing rules     │
  │       – general-note PDFs → project-wide defaults    │
  │                                                       │
  │    2. merge_fields()                                  │
  │       – single source  → RESOLVED                    │
  │       – multiple agree → RESOLVED (consolidated)     │
  │       – multiple disagree → CONFLICT (flagged)       │
  │       – no source → NOT_FOUND                        │
  │                                                       │
  │    3. return ResolvedMember (inputs + traceability)   │
  └───────────────────────────────────────────────────────┘
              ↓
  Existing deterministic BBS engine  (bbs_engine.py / bbs_query.py)
              ↓
  BBS result

Key design decisions
--------------------
• GENERIC — no hardcoded member IDs, file names, spans, or notation
• SOURCE TRACEABILITY — every value records filename, method, confidence
• CONFLICT DETECTION — disagreements between files are preserved, not silently overwritten
• PARTIAL RESOLUTION — missing fields are flagged NOT_FOUND, valid fields kept
• PRIORITY ORDER — CAD geometry > table extraction > OCR > vision > free text
• NORMALISATION — member marks normalised before comparison (spaces, dashes, case)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class FieldStatus(str, Enum):
    RESOLVED       = "resolved"           # single unambiguous source
    CONSOLIDATED   = "consolidated"       # multiple sources agree
    CONFLICT       = "conflict"           # sources disagree (value kept from best source)
    NOT_FOUND      = "not_found"          # no source contains this field
    VERIFY_REQUIRED = "verify_required"   # flagged for engineer review


class ExtractionMethod(str, Enum):
    CAD_GEOMETRY = "cad_geometry"   # measured directly from DXF/DWG entity
    TABLE        = "table"          # parsed from a PDF table cell
    OCR          = "ocr"            # read via optical character recognition
    VISION       = "vision"         # extracted by multimodal vision API
    TEXT         = "text"           # parsed from unstructured text


# Source priority (higher = more trusted)
_METHOD_PRIORITY: Dict[str, int] = {
    ExtractionMethod.CAD_GEOMETRY: 10,
    ExtractionMethod.TABLE:        7,
    ExtractionMethod.OCR:          5,
    ExtractionMethod.VISION:       4,
    ExtractionMethod.TEXT:         2,
}


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FieldSource:
    """Full traceability record for one extracted value."""
    filename:   str
    file_type:  str
    method:     str                  # ExtractionMethod value
    confidence: float = 1.0
    page:       Optional[int]   = None
    table:      Optional[int]   = None
    layer:      Optional[str]   = None
    entity:     Optional[str]   = None
    region:     Optional[str]   = None

    def priority(self) -> int:
        return _METHOD_PRIORITY.get(self.method, 0)

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class FieldCandidate:
    """One (value, source) pair gathered from a single file."""
    value:  Any
    source: FieldSource


@dataclass
class ResolvedField:
    """Final resolved value for one engineering input field."""
    field:     str
    value:     Any
    status:    FieldStatus
    sources:   List[FieldSource] = field(default_factory=list)
    conflicts: List[Dict]        = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "field":     self.field,
            "value":     self.value,
            "status":    self.status.value,
            "sources":   [s.to_dict() for s in self.sources],
            "conflicts": self.conflicts,
        }


@dataclass
class ResolvedMember:
    """
    Complete resolved input dataset for one structural member.

    resolved    – dict of field_name → ResolvedField (all statuses)
    inputs      – dict of field_name → value  (RESOLVED + CONFLICT fields only)
    missing     – list of required field names with NOT_FOUND status
    conflicts   – list of conflict dicts for engineer review
    sources     – dict of field_name → primary source dict
    status      – overall resolution status string
    """
    mark:        str
    member_type: str
    resolved:    Dict[str, ResolvedField] = field(default_factory=dict)

    # ── Convenience accessors ────────────────────────────────────────────────

    @property
    def inputs(self) -> Dict[str, Any]:
        """Values for all fields that have any resolved value (RESOLVED or CONFLICT)."""
        return {
            f: r.value
            for f, r in self.resolved.items()
            if r.value is not None and r.status not in (
                FieldStatus.NOT_FOUND, FieldStatus.VERIFY_REQUIRED
            )
        }

    @property
    def missing(self) -> List[str]:
        return [f for f, r in self.resolved.items() if r.status == FieldStatus.NOT_FOUND]

    @property
    def conflicts(self) -> List[Dict]:
        out = []
        for r in self.resolved.values():
            if r.status == FieldStatus.CONFLICT:
                out.extend(r.conflicts)
        return out

    @property
    def sources(self) -> Dict[str, Dict]:
        return {
            f: r.sources[0].to_dict()
            for f, r in self.resolved.items()
            if r.sources
        }

    @property
    def status(self) -> str:
        if any(r.status == FieldStatus.CONFLICT for r in self.resolved.values()):
            return "conflict"
        resolved_count = sum(
            1 for r in self.resolved.values()
            if r.status in (FieldStatus.RESOLVED, FieldStatus.CONSOLIDATED)
        )
        if resolved_count == 0:
            return "not_found"
        if self.missing:
            return "partial"
        return "complete"

    def get(self, field_name: str, default=None) -> Any:
        r = self.resolved.get(field_name)
        return r.value if (r and r.value is not None) else default

    def to_dict(self) -> Dict:
        return {
            "mark":        self.mark,
            "member_type": self.member_type,
            "status":      self.status,
            "inputs":      self.inputs,
            "sources":     self.sources,
            "missing":     self.missing,
            "conflicts":   self.conflicts,
            "resolved":    {f: r.to_dict() for f, r in self.resolved.items()},
        }

    def to_bbs_inputs(self) -> Dict[str, Any]:
        """
        Return the flat dict that bbs_query.MemberDataset.to_bbs_inputs() produces,
        so downstream BBS engine code receives a compatible payload.
        """
        inp = self.inputs
        out: Dict[str, Any] = {}

        # Geometry
        if inp.get("clear_span_mm") is not None:
            out["clear_span_mm"] = inp["clear_span_mm"]
        if inp.get("storey_height_mm") is not None:
            out["storey_height_mm"] = inp["storey_height_mm"]
        if inp.get("section_b_mm") is not None:
            out["section_b_mm"] = inp["section_b_mm"]
        if inp.get("section_d_mm") is not None:
            out["section_d_mm"] = inp["section_d_mm"]
        if inp.get("size"):
            out["size"] = inp["size"]

        # Beam reinforcement
        if inp.get("top_bars"):
            count, dia = _parse_bar_notation(inp["top_bars"])
            if count and dia:
                out["top_num_bars"] = count
                out["top_dia_mm"]   = dia
        if inp.get("bottom_bars"):
            count, dia = _parse_bar_notation(inp["bottom_bars"])
            if count and dia:
                out["bottom_num_bars"] = count
                out["bottom_dia_mm"]   = dia
        if inp.get("stirrup_dia_mm") is not None:
            out["stirrup_dia_mm"] = int(inp["stirrup_dia_mm"])
        if inp.get("stirrup_spacing_mm") is not None:
            out["stirrup_spacing_mm"] = int(inp["stirrup_spacing_mm"])

        # Column reinforcement
        if inp.get("main_bars"):
            count, dia = _parse_bar_notation(inp["main_bars"])
            if count and dia:
                out["num_main_bars"] = count
                out["main_dia_mm"]   = dia
        if inp.get("tie_dia_mm") is not None:
            out["tie_dia_mm"] = int(inp["tie_dia_mm"])
        if inp.get("tie_spacing_mm") is not None:
            out["tie_spacing_mm"] = int(inp["tie_spacing_mm"])

        # Cover & grade (optional, passed through if present)
        if inp.get("cover_mm") is not None:
            out["cover_mm"] = inp["cover_mm"]
        if inp.get("concrete_grade"):
            out["concrete_grade"] = inp["concrete_grade"]
        if inp.get("steel_grade"):
            out["steel_grade"] = inp["steel_grade"]

        # Traceability — ensure all values are JSON-serializable strings
        def _src_dict(src_info: Dict) -> Dict:
            return {
                k: (v.value if hasattr(v, "value") else v)
                for k, v in src_info.items()
            }

        out["_source_files"]    = list({s["filename"] for s in self.sources.values()})
        out["_field_sources"]   = {f: _src_dict(s) for f, s in self.sources.items()}
        out["_cad_source_file"] = self._cad_source()
        out["_cad_span_method"] = self.get("clear_span_method")

        # Flags for bbs_query compatibility
        flags = []
        for fname in _required_inputs(self.member_type):
            r = self.resolved.get(fname)
            if r is None or r.status == FieldStatus.NOT_FOUND:
                flags.append({"field": fname, "status": "NOT_FOUND"})
            elif r.status == FieldStatus.CONFLICT:
                flags.append({
                    "field":  fname,
                    "status": "CONFLICT",
                    "values": [c.get("value") for c in r.conflicts],
                })
        out["_flags"] = flags
        return out

    def _cad_source(self) -> Optional[str]:
        for fname in ("clear_span_mm", "storey_height_mm", "layer", "start_coords"):
            r = self.resolved.get(fname)
            if r and r.sources and r.sources[0].method == ExtractionMethod.CAD_GEOMETRY:
                return r.sources[0].filename
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _canonical(mark: str) -> str:
    """Normalise member mark: strip spaces/dashes/underscores, uppercase."""
    return re.sub(r"[\s\-_]+", "", str(mark).upper())


def _marks_match(a: str, b: str) -> bool:
    return _canonical(a) == _canonical(b)


def _parse_bar_notation(bar_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse 'N-dia' string → (count, dia_mm). Returns (None, None) on failure."""
    if not bar_str:
        return None, None
    m = re.match(r"(\d{1,3})\s*[-#]\s*(\d{1,2})", str(bar_str).strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_size(size_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse 'BxD' string → (b_mm, d_mm). Returns (None, None) on failure."""
    if not size_str:
        return None, None
    m = re.match(r"(\d{2,4})\s*[xX×]\s*(\d{2,4})", str(size_str).strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _coerce_int(value: Any) -> Optional[int]:
    """Coerce a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(str(value).split(".")[0])
    except (ValueError, TypeError):
        return None


def _normalise_value(value: Any) -> Any:
    """Normalise value for equality comparison."""
    if isinstance(value, str):
        return value.strip().upper().replace(" ", "")
    if isinstance(value, float):
        return round(value, 1)
    return value


def _values_agree(a: Any, b: Any, tolerance_mm: float = 5.0) -> bool:
    """
    True if two field values are considered the same.
    Numeric values have a ±tolerance_mm allowance (for geometry measurements).
    """
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= tolerance_mm
    except (TypeError, ValueError):
        pass
    return _normalise_value(a) == _normalise_value(b)


def _required_inputs(member_type: str) -> List[str]:
    """Return required field names for BBS calculation by member type."""
    if member_type == "beam":
        return [
            "clear_span_mm",
            "section_b_mm",
            "section_d_mm",
            "top_bars",
            "bottom_bars",
            "stirrup_dia_mm",
            "stirrup_spacing_mm",
        ]
    if member_type == "column":
        return [
            "storey_height_mm",
            "section_b_mm",
            "section_d_mm",
            "main_bars",
            "tie_dia_mm",
            "tie_spacing_mm",
        ]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Source gathering — per file-type extractors
# ─────────────────────────────────────────────────────────────────────────────

def _gather_from_dxf_members(
    mark: str,
    extracted: Dict,
    filename: str,
) -> Dict[str, FieldCandidate]:
    """
    Extract geometry fields from the DXF members list.
    Returns {field_name: FieldCandidate}.
    """
    members = extracted.get("members", [])
    if isinstance(members, dict):
        members = list(members.values())

    src = FieldSource(filename=filename, file_type="dxf", method=ExtractionMethod.CAD_GEOMETRY)
    found: Dict[str, FieldCandidate] = {}

    for m in members:
        if not isinstance(m, dict):
            continue
        if not _marks_match(m.get("mark", ""), mark):
            continue

        # Geometry
        if m.get("clear_span_mm") is not None:
            found["clear_span_mm"] = FieldCandidate(float(m["clear_span_mm"]), src)
        if m.get("clear_span_method"):
            found["clear_span_method"] = FieldCandidate(m["clear_span_method"], src)
        if m.get("length_mm") is not None:
            found["length_mm"] = FieldCandidate(float(m["length_mm"]), src)
        if m.get("layer"):
            found["layer"] = FieldCandidate(m["layer"], src)
        if m.get("floor_level"):
            found["floor_level"] = FieldCandidate(m["floor_level"], src)
        if m.get("location"):
            found["location"] = FieldCandidate(m["location"], src)
        if m.get("member_type"):
            found["_dxf_member_type"] = FieldCandidate(m["member_type"], src)

        # Section geometry may be stored on DXF member too
        if m.get("size"):
            b, d = _parse_size(m["size"])
            if b and d:
                found["section_b_mm"] = FieldCandidate(b, src)
                found["section_d_mm"] = FieldCandidate(d, src)
                found["size"]         = FieldCandidate(m["size"], src)

        # Some DXF extractors embed storey height for columns
        if m.get("storey_height_mm") is not None:
            found["storey_height_mm"] = FieldCandidate(float(m["storey_height_mm"]), src)

        break  # first match is sufficient

    # Also check member_geometry sub-dict if present
    meta = extracted.get("metadata", {})
    geom_map = meta.get("member_geometry", {})
    for key, geom in geom_map.items():
        if not isinstance(geom, dict):
            continue
        if not _marks_match(geom.get("mark", key.split("_", 1)[-1]), mark):
            continue
        gsrc = FieldSource(
            filename=filename, file_type="dxf",
            method=ExtractionMethod.CAD_GEOMETRY,
            layer=geom.get("layer"),
        )
        if geom.get("clear_span_mm") is not None and "clear_span_mm" not in found:
            found["clear_span_mm"] = FieldCandidate(float(geom["clear_span_mm"]), gsrc)
        if geom.get("clear_span_method") and "clear_span_method" not in found:
            found["clear_span_method"] = FieldCandidate(geom["clear_span_method"], gsrc)
        if geom.get("layer") and "layer" not in found:
            found["layer"] = FieldCandidate(geom["layer"], gsrc)
        break

    return found


def _gather_from_beam_schedule(
    mark: str,
    extracted: Dict,
    filename: str,
    file_type: str,
) -> Dict[str, FieldCandidate]:
    """
    Extract beam reinforcement fields from a beam schedule dict.
    Returns {field_name: FieldCandidate}.
    """
    beams = extracted.get("beams", {})
    if isinstance(beams, list):
        beams = {b.get("mark", ""): b for b in beams if isinstance(b, dict)}

    method = ExtractionMethod.OCR if extracted.get("used_ocr") else ExtractionMethod.TABLE
    found: Dict[str, FieldCandidate] = {}

    for bmark, bdata in beams.items():
        if not _marks_match(bmark, mark):
            continue
        if not isinstance(bdata, dict):
            continue

        src = FieldSource(filename=filename, file_type=file_type, method=method)

        # Section size
        if bdata.get("size"):
            found["size"] = FieldCandidate(bdata["size"], src)
            b, d = _parse_size(bdata["size"])
            if b:
                found["section_b_mm"] = FieldCandidate(b, src)
            if d:
                found["section_d_mm"] = FieldCandidate(d, src)

        # Reinforcement bars
        for field_name in ("top_bars", "bottom_bars", "extra_top", "extra_bottom",
                           "side_face", "hanger_bars"):
            if bdata.get(field_name):
                found[field_name] = FieldCandidate(bdata[field_name], src)

        # Stirrups
        stir_dia = _coerce_int(bdata.get("stirrup_dia"))
        stir_spc = _coerce_int(bdata.get("stirrup_spacing"))
        if stir_dia is not None:
            found["stirrup_dia_mm"] = FieldCandidate(stir_dia, src)
        if stir_spc is not None:
            found["stirrup_spacing_mm"] = FieldCandidate(stir_spc, src)

        # Materials
        if bdata.get("concrete_grade"):
            found["concrete_grade"] = FieldCandidate(bdata["concrete_grade"], src)
        if bdata.get("steel_grade"):
            found["steel_grade"] = FieldCandidate(bdata["steel_grade"], src)
        if bdata.get("cover_mm") is not None:
            found["cover_mm"] = FieldCandidate(_coerce_int(bdata["cover_mm"]), src)

        # Span (if schedule includes it)
        if bdata.get("clear_span_mm") is not None:
            found.setdefault("clear_span_mm",
                FieldCandidate(float(bdata["clear_span_mm"]),
                    FieldSource(filename=filename, file_type=file_type,
                                method=ExtractionMethod.TABLE)))

        if bdata.get("floor_level"):
            found.setdefault("floor_level", FieldCandidate(bdata["floor_level"], src))

        break  # first match

    return found


def _gather_from_column_schedule(
    mark: str,
    extracted: Dict,
    filename: str,
    file_type: str,
) -> Dict[str, FieldCandidate]:
    """
    Extract column reinforcement fields from a column schedule dict.
    Returns {field_name: FieldCandidate}.
    """
    columns = extracted.get("columns", {})
    if isinstance(columns, list):
        columns = {c.get("mark", ""): c for c in columns if isinstance(c, dict)}

    method = ExtractionMethod.OCR if extracted.get("used_ocr") else ExtractionMethod.TABLE
    found: Dict[str, FieldCandidate] = {}

    for cmark, cdata in columns.items():
        if not _marks_match(cmark, mark):
            continue
        if not isinstance(cdata, dict):
            continue

        src = FieldSource(filename=filename, file_type=file_type, method=method)

        if cdata.get("size"):
            found["size"] = FieldCandidate(cdata["size"], src)
            b, d = _parse_size(cdata["size"])
            if b:
                found["section_b_mm"] = FieldCandidate(b, src)
            if d:
                found["section_d_mm"] = FieldCandidate(d, src)

        if cdata.get("main_bars"):
            found["main_bars"] = FieldCandidate(cdata["main_bars"], src)
        if cdata.get("main_bar_dia"):
            found["main_bar_dia_mm"] = FieldCandidate(_coerce_int(cdata["main_bar_dia"]), src)

        tie_dia = _coerce_int(cdata.get("tie_dia"))
        tie_spc = _coerce_int(cdata.get("tie_spacing"))
        if tie_dia is not None:
            found["tie_dia_mm"] = FieldCandidate(tie_dia, src)
        if tie_spc is not None:
            found["tie_spacing_mm"] = FieldCandidate(tie_spc, src)

        if cdata.get("concrete_grade"):
            found["concrete_grade"] = FieldCandidate(cdata["concrete_grade"], src)
        if cdata.get("steel_grade"):
            found["steel_grade"] = FieldCandidate(cdata["steel_grade"], src)
        if cdata.get("cover_mm") is not None:
            found["cover_mm"] = FieldCandidate(_coerce_int(cdata["cover_mm"]), src)
        if cdata.get("storey_height_mm") is not None:
            found["storey_height_mm"] = FieldCandidate(float(cdata["storey_height_mm"]), src)

        break

    return found


# ─────────────────────────────────────────────────────────────────────────────
# Field merging
# ─────────────────────────────────────────────────────────────────────────────

def _merge_candidates(
    field_name: str,
    candidates: List[FieldCandidate],
) -> ResolvedField:
    """
    Merge all candidates for a single field into one ResolvedField.

    Rules:
      • Zero candidates  → NOT_FOUND
      • One candidate    → RESOLVED
      • All agree        → CONSOLIDATED (use highest-priority source)
      • Disagree         → CONFLICT  (use highest-priority source value; flag others)
    """
    # Drop None values
    valid = [c for c in candidates if c.value is not None]

    if not valid:
        return ResolvedField(field=field_name, value=None,
                             status=FieldStatus.NOT_FOUND)

    if len(valid) == 1:
        return ResolvedField(field=field_name, value=valid[0].value,
                             status=FieldStatus.RESOLVED,
                             sources=[valid[0].source])

    # Sort by source priority (highest first)
    valid.sort(key=lambda c: (c.source.priority(), c.source.confidence), reverse=True)
    best = valid[0]

    # Check if all agree
    all_agree = all(_values_agree(c.value, best.value) for c in valid[1:])
    if all_agree:
        return ResolvedField(
            field=field_name,
            value=best.value,
            status=FieldStatus.CONSOLIDATED,
            sources=[c.source for c in valid],
        )

    # Conflict — record disagreements
    conflict_records = [
        {
            "field":    field_name,
            "value":    c.value,
            "source":   c.source.filename,
            "method":   c.source.method,
        }
        for c in valid[1:]
        if not _values_agree(c.value, best.value)
    ]

    return ResolvedField(
        field=field_name,
        value=best.value,      # best-source value is kept
        status=FieldStatus.CONFLICT,
        sources=[best.source],
        conflicts=conflict_records,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Member type auto-detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_member_type(mark: str, project_files: List[Dict]) -> str:
    """
    Auto-detect member type by searching extracted data.
    Falls back to pattern-matching the mark string.
    """
    mk = _canonical(mark)

    # Search extracted data first (most reliable)
    for fd in project_files:
        extracted = _load_extracted(fd)

        beams = extracted.get("beams", {})
        if isinstance(beams, dict):
            if any(_canonical(k) == mk for k in beams):
                return "beam"
        elif isinstance(beams, list):
            if any(_canonical(b.get("mark", "")) == mk for b in beams if isinstance(b, dict)):
                return "beam"

        cols = extracted.get("columns", {})
        if isinstance(cols, dict):
            if any(_canonical(k) == mk for k in cols):
                return "column"
        elif isinstance(cols, list):
            if any(_canonical(c.get("mark", "")) == mk for c in cols if isinstance(c, dict)):
                return "column"

        members = extracted.get("members", [])
        if isinstance(members, dict):
            members = list(members.values())
        for m in members:
            if isinstance(m, dict) and _canonical(m.get("mark", "")) == mk:
                return m.get("member_type", "beam")

    # Pattern-based fallback (generic regex, not project-specific)
    m_upper = mark.upper()
    if re.search(r'\b(?:B(?:EAM)?|[EGT]B)\s*[-]?\d', m_upper):
        return "beam"
    if re.search(r'\b(?:C(?:OL)?|EC)\s*[-]?\d', m_upper):
        return "column"
    if re.search(r'\b(?:S(?:LAB)?|SS)\s*[-]?\d', m_upper):
        return "slab"
    if re.search(r'\b(?:F(?:TG)?|FOOT)\s*[-]?\d', m_upper):
        return "footing"

    return "beam"   # conservative default


def _load_extracted(file_data: Dict) -> Dict:
    """Load extracted_data from a project file dict, handling JSON string or dict."""
    raw = file_data.get("extracted_data", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw or {}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def resolve_member(
    mark: str,
    project_files: List[Dict],
    member_type: Optional[str] = None,
) -> ResolvedMember:
    """
    Resolve all engineering inputs for a structural member from all project files.

    Parameters
    ----------
    mark          : Member identifier (any notation: B1, EB5, COL-A, G-B12, …)
    project_files : List of dicts, each with keys:
                      'filename'      (str)
                      'file_type'     (str: 'dxf', 'pdf', 'image', …)
                      'extracted_data' (str JSON or dict)
    member_type   : Optional hint ("beam", "column", "slab", "footing").
                    Auto-detected from extracted data if not supplied.

    Returns
    -------
    ResolvedMember  — complete resolved input dataset with traceability.
    """
    if not member_type:
        member_type = _detect_member_type(mark, project_files)

    logger.info("[resolve_member] mark=%s type=%s files=%d", mark, member_type, len(project_files))

    # ── Step 1: Gather all field candidates from every file ──────────────────
    # candidates[field_name] = list of (value, source) pairs
    candidates: Dict[str, List[FieldCandidate]] = {}

    def _add(field_name: str, cand: FieldCandidate) -> None:
        candidates.setdefault(field_name, []).append(cand)

    for fd in project_files:
        fname    = fd.get("filename") or fd.get("original_name") or "unknown"
        ftype    = fd.get("file_type", "unknown")
        extracted = _load_extracted(fd)

        # DXF → geometry
        if ftype == "dxf":
            for fn, c in _gather_from_dxf_members(mark, extracted, fname).items():
                _add(fn, c)

        # Any file may carry beam schedule data (PDF, Excel, CSV, …)
        if member_type == "beam":
            for fn, c in _gather_from_beam_schedule(mark, extracted, fname, ftype).items():
                _add(fn, c)

        # Any file may carry column schedule data
        if member_type == "column":
            for fn, c in _gather_from_column_schedule(mark, extracted, fname, ftype).items():
                _add(fn, c)

        # Both beam and column schedules may live in the same multi-schedule PDF,
        # so always try both when type was auto-detected from mark pattern.
        if member_type not in ("beam", "column"):
            for fn, c in _gather_from_beam_schedule(mark, extracted, fname, ftype).items():
                _add(fn, c)
            for fn, c in _gather_from_column_schedule(mark, extracted, fname, ftype).items():
                _add(fn, c)

    # ── Step 2: Merge candidates field-by-field ──────────────────────────────
    resolved: Dict[str, ResolvedField] = {}

    all_fields = set(candidates.keys()) | set(_required_inputs(member_type))

    for field_name in all_fields:
        field_candidates = candidates.get(field_name, [])
        resolved[field_name] = _merge_candidates(field_name, field_candidates)

    # ── Step 3: Infer section dims from size string if not directly present ──
    if "size" in resolved and resolved["size"].value:
        b, d = _parse_size(resolved["size"].value)
        size_src = resolved["size"].sources[0] if resolved["size"].sources else None
        if b and resolved.get("section_b_mm", ResolvedField("", None, FieldStatus.NOT_FOUND)).value is None:
            resolved["section_b_mm"] = ResolvedField(
                field="section_b_mm", value=b,
                status=FieldStatus.RESOLVED,
                sources=[size_src] if size_src else [],
            )
        if d and resolved.get("section_d_mm", ResolvedField("", None, FieldStatus.NOT_FOUND)).value is None:
            resolved["section_d_mm"] = ResolvedField(
                field="section_d_mm", value=d,
                status=FieldStatus.RESOLVED,
                sources=[size_src] if size_src else [],
            )

    result = ResolvedMember(mark=mark, member_type=member_type, resolved=resolved)

    logger.info(
        "[resolve_member] mark=%s → status=%s resolved=%d missing=%s conflicts=%d",
        mark, result.status,
        sum(1 for r in resolved.values()
            if r.status in (FieldStatus.RESOLVED, FieldStatus.CONSOLIDATED)),
        result.missing,
        len(result.conflicts),
    )

    return result


def resolve_all_members(
    project_files: List[Dict],
    member_type: Optional[str] = None,
) -> Dict[str, ResolvedMember]:
    """
    Resolve inputs for every member found across all project files.

    Returns dict of canonical_mark → ResolvedMember.
    """
    from app.services.bbs_query import _index_all_marks  # lazy import

    file_dicts = [
        {"original_name": fd.get("filename") or fd.get("original_name", ""),
         "extracted_data": fd.get("extracted_data", {})}
        for fd in project_files
    ]
    index = _index_all_marks(file_dicts)

    all_marks: List[str] = []
    if not member_type or member_type == "beam":
        all_marks += index.get("beams", [])
    if not member_type or member_type == "column":
        all_marks += index.get("columns", [])

    results: Dict[str, ResolvedMember] = {}
    for mark in all_marks:
        mtype = member_type or _detect_member_type(mark, project_files)
        results[_canonical(mark)] = resolve_member(mark, project_files, mtype)

    logger.info("[resolve_all_members] Resolved %d members", len(results))
    return results


def summarise_resolution(resolved: ResolvedMember) -> Dict:
    """
    Return a concise human-readable summary of the resolution result.
    Suitable for API responses and logging.
    """
    inp = resolved.inputs
    return {
        "mark":        resolved.mark,
        "member_type": resolved.member_type,
        "status":      resolved.status,
        "resolved_fields": len([
            r for r in resolved.resolved.values()
            if r.status in (FieldStatus.RESOLVED, FieldStatus.CONSOLIDATED)
        ]),
        "missing_fields":   resolved.missing,
        "conflict_fields":  [
            f for f, r in resolved.resolved.items()
            if r.status == FieldStatus.CONFLICT
        ],
        "geometry": {
            "clear_span_mm":   inp.get("clear_span_mm"),
            "storey_height_mm": inp.get("storey_height_mm"),
            "section":         inp.get("size"),
            "layer":           inp.get("layer"),
        },
        "reinforcement": {
            k: inp.get(k)
            for k in ("top_bars", "bottom_bars", "main_bars",
                      "stirrup_dia_mm", "stirrup_spacing_mm",
                      "tie_dia_mm", "tie_spacing_mm",
                      "concrete_grade", "cover_mm")
            if inp.get(k) is not None
        },
        "sources": resolved.sources,
    }
