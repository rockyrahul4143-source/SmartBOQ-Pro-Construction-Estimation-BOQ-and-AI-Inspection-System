"""
Drawing Analysis Engine
=======================
PRINCIPLE: Drawing Vision reads and extracts. Formula engine calculates.
Engineer verifies and approves. Nothing is invented.

Workflow:
  DXF/PDF/Image
    → _read_drawing()        — extract raw text, entities, schedules
    → _detect_elements()     — identify C1/B1/S1/F1 etc. with dimensions
    → _validate()            — cross-check schedule vs plan counts
    → DrawingAnalysis        — structured result with confidence flags
    → Engineer verifies      — approve / edit / reject each element
    → send_to_measurement_book() — only verified items enter the system

NO QUANTITY IS CALCULATED HERE.
Quantities are computed by the existing formula engine from engineer-verified dims.
"""
from __future__ import annotations
import re
import math
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


# ── Confidence levels ─────────────────────────────────
class Confidence(str, Enum):
    HIGH   = "high"     # directly read from schedule/explicit annotation
    MEDIUM = "medium"   # inferred from geometry + context
    LOW    = "low"      # estimated / partial data


class DetectionStatus(str, Enum):
    DETECTED             = "detected"
    ENGINEER_INPUT_REQ   = "engineer_input_required"
    CONFLICT_DETECTED    = "conflict_detected"
    NOT_FOUND            = "not_found"


class ElementType(str, Enum):
    COLUMN   = "column"
    BEAM     = "beam"
    SLAB     = "slab"
    FOOTING  = "footing"
    WALL     = "wall"
    DOOR     = "door"
    WINDOW   = "window"
    STAIR    = "stair"
    ROOM     = "room"
    OTHER    = "other"


# ── Formula selector — maps element → civil formula ───
FORMULA_MAP = {
    ElementType.COLUMN:  "B × D × H × Nos",
    ElementType.BEAM:    "B × D × L × Nos",
    ElementType.SLAB:    "L × B × Thickness × Nos",
    ElementType.FOOTING: "L × B × D × Nos",
    ElementType.WALL:    "L × H × Thickness × Nos − openings",
    ElementType.DOOR:    "W × H × Nos",
    ElementType.WINDOW:  "W × H × Nos",
    ElementType.STAIR:   "L × B × Thickness × Nos",
    ElementType.ROOM:    "L × B",
}

UNIT_MAP = {
    ElementType.COLUMN:  "m3",
    ElementType.BEAM:    "m3",
    ElementType.SLAB:    "m3",
    ElementType.FOOTING: "m3",
    ElementType.WALL:    "m3",
    ElementType.DOOR:    "no",
    ElementType.WINDOW:  "no",
    ElementType.STAIR:   "m3",
    ElementType.ROOM:    "m2",
}


@dataclass
class Dimension:
    """A single detected dimension value with its source."""
    value: Optional[float]
    unit: str = "m"
    source: str = "drawing"        # "schedule" | "annotation" | "geometry" | "user_input"
    confidence: Confidence = Confidence.MEDIUM
    raw_text: str = ""


@dataclass
class DrawingElement:
    """
    One detected element (e.g. C1, B2, F1).
    All dims are Optional — missing = engineer must fill.
    Quantity is NOT computed here.
    """
    mark: str                          # C1, B1, S1, F1 …
    element_type: ElementType
    description: str

    # Raw dimensions — mm converted to m during detection
    length:    Optional[Dimension] = None
    width:     Optional[Dimension] = None
    height:    Optional[Dimension] = None   # column height / beam depth / slab thickness
    depth:     Optional[Dimension] = None   # footing depth
    nos:       Optional[Dimension] = None   # count from plan

    # Detection metadata
    confidence: Confidence = Confidence.MEDIUM
    status: DetectionStatus = DetectionStatus.DETECTED
    conflict_notes: str = ""
    source_info: str = ""              # where was this found in the drawing

    # Formula info (for display — calculation done by formula engine later)
    formula: str = ""
    unit: str = "m3"
    category: str = "rcc"              # SOR category hint

    def to_dict(self) -> dict:
        def _dim(d: Optional[Dimension]) -> Optional[dict]:
            if d is None:
                return None
            return {"value": d.value, "unit": d.unit, "source": d.source,
                    "confidence": d.confidence.value, "raw_text": d.raw_text}
        return {
            "mark": self.mark,
            "element_type": self.element_type.value,
            "description": self.description,
            "length":   _dim(self.length),
            "width":    _dim(self.width),
            "height":   _dim(self.height),
            "depth":    _dim(self.depth),
            "nos":      _dim(self.nos),
            "confidence": self.confidence.value,
            "status":   self.status.value,
            "conflict_notes": self.conflict_notes,
            "source_info": self.source_info,
            "formula":  self.formula,
            "unit":     self.unit,
            "category": self.category,
        }


@dataclass
class DrawingInfo:
    drawing_type: str = "unknown"      # "structural_plan" | "architectural_plan" | "section" | "elevation"
    floor_level: str = ""
    scale: str = ""
    units: str = ""
    grid_lines: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class DrawingAnalysis:
    drawing_info: DrawingInfo
    elements: list[DrawingElement]
    schedule_data: dict               # raw schedule tables read from drawing
    validation_checks: list[dict]     # cross-checks
    warnings: list[str]
    missing_info: list[str]
    total_elements: int = 0

    def to_dict(self) -> dict:
        return {
            "drawing_info": {
                "drawing_type": self.drawing_info.drawing_type,
                "floor_level":  self.drawing_info.floor_level,
                "scale":        self.drawing_info.scale,
                "units":        self.drawing_info.units,
                "notes":        self.drawing_info.notes,
                "warnings":     self.drawing_info.warnings,
            },
            "total_elements": len(self.elements),
            "elements": [e.to_dict() for e in self.elements],
            "schedule_data": self.schedule_data,
            "validation_checks": self.validation_checks,
            "warnings": self.warnings,
            "missing_info": self.missing_info,
            "element_summary": self._element_summary(),
        }

    def _element_summary(self) -> dict:
        summary: dict = {}
        for el in self.elements:
            t = el.element_type.value
            if t not in summary:
                summary[t] = {"count": 0, "marks": []}
            summary[t]["count"] += 1
            summary[t]["marks"].append(el.mark)
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# DXF Text Analyzer
# Reads TEXT/MTEXT entities to find element schedules and labels
# ─────────────────────────────────────────────────────────────────────────────

# Regex patterns for common structural schedule formats
_COL_SCHEDULE_PATTERNS = [
    # "C1 - 300X300" or "C1: 300x300" or "C1 300 x 300"
    re.compile(r'\b(C\d+[A-Z]?)\s*[-:=]?\s*(\d+)\s*[xX×]\s*(\d+)', re.IGNORECASE),
    # "C1 300X300X3200" (with height)
    re.compile(r'\b(C\d+[A-Z]?)\s*[-:=]?\s*(\d+)\s*[xX×]\s*(\d+)\s*[xX×]\s*(\d+)', re.IGNORECASE),
]
_BEAM_SCHEDULE_PATTERNS = [
    re.compile(r'\b(B\d+[A-Z]?)\s*[-:=]?\s*(\d+)\s*[xX×]\s*(\d+)', re.IGNORECASE),
]
_FOOTING_SCHEDULE_PATTERNS = [
    re.compile(r'\b(F\d+[A-Z]?)\s*[-:=]?\s*(\d+)\s*[xX×]\s*(\d+)\s*[xX×]?\s*(\d*)', re.IGNORECASE),
]
_SLAB_THICKNESS_PATTERNS = [
    re.compile(r'\b(S\d+[A-Z]?|SLAB)\s*[-:=T]?\s*(\d+)\s*(?:MM|mm|MM THICK|mm thick)?', re.IGNORECASE),
    re.compile(r'(?:SLAB|ROOF|FLOOR)\s+(?:THICK(?:NESS)?|T)\s*[=:]?\s*(\d+)\s*(?:MM|mm)?', re.IGNORECASE),
]
_STOREY_HEIGHT_PATTERNS = [
    re.compile(r'(?:STOREY|FLOOR|FLOOR TO FLOOR|FFL|HTG|HT|HEIGHT)\s*[=:]?\s*(\d+[\.,]\d*|\d+)\s*(?:M|MM|m|mm)?', re.IGNORECASE),
]
_SCALE_PATTERNS = [
    re.compile(r'SCALE\s*[=:]?\s*1\s*[:/]\s*(\d+)', re.IGNORECASE),
    re.compile(r'1\s*:\s*(\d+)', re.IGNORECASE),
]
_COUNT_PATTERNS = [
    # "12 NOS", "12 NO.", "NOS = 12"
    re.compile(r'(\d+)\s*(?:NOS?|NO\.?)\b', re.IGNORECASE),
    re.compile(r'NOS?\s*[=:]\s*(\d+)', re.IGNORECASE),
]


def _mm_to_m(val: float, raw_unit: str = "mm") -> float:
    """Convert raw drawing dimension to metres."""
    raw_unit = raw_unit.lower().strip()
    if raw_unit in ("mm", ""):
        return val / 1000.0
    elif raw_unit == "cm":
        return val / 100.0
    elif raw_unit == "m":
        return val
    elif raw_unit in ("ft", "feet"):
        return val * 0.3048
    elif raw_unit in ("in", "inch", "inches"):
        return val * 0.0254
    return val / 1000.0  # default: assume mm


def _extract_texts_from_dxf(lines: list[str]) -> list[str]:
    """
    Extract all TEXT and MTEXT string values from DXF entity lines.
    Returns list of text strings found.
    """
    texts = []
    n = len(lines)
    i = 0
    while i < n:
        stripped = lines[i].strip()
        if stripped == "0" and i + 1 < n:
            etype = lines[i + 1].strip().upper()
            if etype in ("TEXT", "MTEXT", "ATTDEF", "ATTRIB"):
                # Read group codes 1 (TEXT string) and 3 (MTEXT additional text)
                j = i + 2
                while j < n:
                    c = lines[j].strip()
                    if c == "0":
                        break
                    if j + 1 < n and c in ("1", "3"):
                        val = lines[j + 1].strip()
                        if val:
                            texts.append(val)
                    j += 2
        i += 1
    return texts


def _read_schedule_from_texts(texts: list[str]) -> dict:
    """
    Parse structural schedule data from extracted text strings.
    Returns dict: { "C1": {"width":0.3,"depth":0.3,"source":"schedule"}, ... }
    """
    schedule: dict = {}

    all_text = "\n".join(texts)

    # Column schedule
    for pattern in _COL_SCHEDULE_PATTERNS:
        for m in pattern.finditer(all_text):
            groups = m.groups()
            mark = groups[0].upper()
            try:
                w = _mm_to_m(float(groups[1]))
                d = _mm_to_m(float(groups[2]))
                h = _mm_to_m(float(groups[3])) if len(groups) > 3 and groups[3] else None
            except (ValueError, IndexError):
                continue
            if mark not in schedule:
                schedule[mark] = {"type": "column", "width": w, "depth": d, "source": "schedule", "raw": m.group(0)}
                if h:
                    schedule[mark]["height"] = h

    # Beam schedule
    for pattern in _BEAM_SCHEDULE_PATTERNS:
        for m in pattern.finditer(all_text):
            groups = m.groups()
            mark = groups[0].upper()
            try:
                w = _mm_to_m(float(groups[1]))
                d = _mm_to_m(float(groups[2]))
            except (ValueError, IndexError):
                continue
            if mark not in schedule:
                schedule[mark] = {"type": "beam", "width": w, "depth": d, "source": "schedule", "raw": m.group(0)}

    # Footing schedule
    for pattern in _FOOTING_SCHEDULE_PATTERNS:
        for m in pattern.finditer(all_text):
            groups = m.groups()
            mark = groups[0].upper()
            try:
                l = _mm_to_m(float(groups[1]))
                b = _mm_to_m(float(groups[2]))
                d = _mm_to_m(float(groups[3])) if len(groups) > 3 and groups[3] else None
            except (ValueError, IndexError):
                continue
            if mark not in schedule:
                entry = {"type": "footing", "length": l, "width": b, "source": "schedule", "raw": m.group(0)}
                if d:
                    entry["depth"] = d
                schedule[mark] = entry

    # Slab thickness
    for pattern in _SLAB_THICKNESS_PATTERNS:
        for m in pattern.finditer(all_text):
            groups = m.groups()
            mark = groups[0].upper() if groups[0] else "SLAB"
            try:
                t = _mm_to_m(float(groups[-1]))
            except (ValueError, IndexError):
                continue
            if mark not in schedule:
                schedule[mark] = {"type": "slab", "thickness": t, "source": "schedule", "raw": m.group(0)}

    return schedule


def _count_mark_occurrences(texts: list[str], mark: str) -> int:
    """
    Count how many times a given element mark appears in text labels.
    Handles: C1, (C1), C1-TYP, C1 (TYP), C1x12, 12C1 etc.
    """
    pattern = re.compile(r'\b' + re.escape(mark) + r'\b', re.IGNORECASE)
    count = sum(1 for t in texts if pattern.search(t))

    # Also look for explicit count next to the mark: "C1 - 12 NOS"
    all_text = "\n".join(texts)
    for cp in _COUNT_PATTERNS:
        for m in cp.finditer(all_text):
            before = all_text[max(0, m.start()-30):m.start()]
            if re.search(r'\b' + re.escape(mark) + r'\b', before, re.IGNORECASE):
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return max(count, 1)


def _detect_floor_level(texts: list[str]) -> str:
    for t in texts:
        m = re.search(r'\b(G\s*(?:FLOOR|F|LVL)|GROUND\s*FLOOR|GF|FF|FIRST\s*FLOOR|SECOND\s*FLOOR|PLINTH|TERRACE|ROOF)\b', t, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return "Not detected — Engineer input required"


def _detect_drawing_type(texts: list[str]) -> str:
    all_text = " ".join(texts).upper()
    if any(k in all_text for k in ("COLUMN SCHEDULE", "BEAM SCHEDULE", "STRUCTURAL")):
        return "structural_plan"
    if any(k in all_text for k in ("FLOOR PLAN", "ARCH", "ARCHITECTURAL")):
        return "architectural_plan"
    if any(k in all_text for k in ("SECTION", "CROSS SECTION")):
        return "section"
    if any(k in all_text for k in ("ELEVATION", "FRONT VIEW", "REAR VIEW")):
        return "elevation"
    if any(k in all_text for k in ("FOOTING", "FOUNDATION PLAN")):
        return "foundation_plan"
    return "plan"  # generic


def _detect_scale(texts: list[str]) -> str:
    for t in texts:
        for pattern in _SCALE_PATTERNS:
            m = pattern.search(t)
            if m:
                return f"1:{m.group(1)}"
    return "Not detected — Engineer input required"


def _detect_storey_height(texts: list[str], default_mm: int = 3000) -> Optional[float]:
    for t in texts:
        for pattern in _STOREY_HEIGHT_PATTERNS:
            m = pattern.search(t)
            if m:
                try:
                    val = float(m.group(1).replace(",", "."))
                    # Heuristic: if value > 100 assume mm, else assume m
                    if val > 100:
                        return val / 1000.0
                    return val
                except ValueError:
                    pass
    return None


def _build_elements_from_schedule(
    schedule: dict,
    texts: list[str],
    storey_height: Optional[float],
    drawing_units: str = "mm",
) -> list[DrawingElement]:
    """
    Create DrawingElement objects from schedule data + plan occurrence counts.
    """
    elements: list[DrawingElement] = []

    for mark, data in schedule.items():
        etype = data.get("type", "other")
        mark_upper = mark.upper()

        # Count occurrences in plan labels
        nos_count = _count_mark_occurrences(texts, mark_upper)
        nos_dim = Dimension(
            value=float(nos_count),
            unit="nos",
            source="plan_label_count",
            confidence=Confidence.MEDIUM if nos_count > 1 else Confidence.LOW,
            raw_text=f"Found mark {mark_upper} × {nos_count} in plan text",
        )

        if etype == "column":
            w = data.get("width")
            d = data.get("depth")
            h = data.get("height") or storey_height

            el = DrawingElement(
                mark=mark_upper,
                element_type=ElementType.COLUMN,
                description=f"RCC Column {mark_upper}",
                width=Dimension(w, "m", "schedule", Confidence.HIGH, data.get("raw","")) if w else None,
                height=Dimension(d, "m", "schedule", Confidence.HIGH, data.get("raw","")) if d else None,
                depth=Dimension(h, "m", "storey_height" if not data.get("height") else "schedule",
                                Confidence.HIGH if data.get("height") else Confidence.MEDIUM) if h else None,
                nos=nos_dim,
                formula=FORMULA_MAP[ElementType.COLUMN],
                unit="m3",
                category="rcc",
                status=DetectionStatus.DETECTED if (w and d) else DetectionStatus.ENGINEER_INPUT_REQ,
                confidence=Confidence.HIGH if (w and d) else Confidence.LOW,
                source_info=f"Schedule: {data.get('raw','')}",
            )
            if not h:
                el.status = DetectionStatus.ENGINEER_INPUT_REQ
                el.conflict_notes = "Column height not found in drawing. Engineer must input floor-to-floor height."
            elements.append(el)

        elif etype == "beam":
            w = data.get("width")
            d = data.get("depth")
            el = DrawingElement(
                mark=mark_upper,
                element_type=ElementType.BEAM,
                description=f"RCC Beam {mark_upper}",
                width=Dimension(w, "m", "schedule", Confidence.HIGH) if w else None,
                height=Dimension(d, "m", "schedule", Confidence.HIGH) if d else None,
                nos=nos_dim,
                formula=FORMULA_MAP[ElementType.BEAM],
                unit="m3",
                category="rcc",
                status=DetectionStatus.ENGINEER_INPUT_REQ,  # beam LENGTH always needs plan measurement
                confidence=Confidence.MEDIUM,
                source_info=f"Schedule: {data.get('raw','')}",
                conflict_notes="Beam length not extracted from drawing — Engineer must measure from plan.",
            )
            elements.append(el)

        elif etype == "footing":
            l = data.get("length")
            b = data.get("width")
            d = data.get("depth")
            el = DrawingElement(
                mark=mark_upper,
                element_type=ElementType.FOOTING,
                description=f"RCC Isolated Footing {mark_upper}",
                length=Dimension(l, "m", "schedule", Confidence.HIGH) if l else None,
                width=Dimension(b, "m", "schedule", Confidence.HIGH) if b else None,
                depth=Dimension(d, "m", "schedule", Confidence.HIGH) if d else None,
                nos=nos_dim,
                formula=FORMULA_MAP[ElementType.FOOTING],
                unit="m3",
                category="rcc",
                status=DetectionStatus.DETECTED if (l and b and d) else DetectionStatus.ENGINEER_INPUT_REQ,
                confidence=Confidence.HIGH if (l and b and d) else Confidence.MEDIUM,
                source_info=f"Schedule: {data.get('raw','')}",
            )
            if not d:
                el.conflict_notes = "Footing depth not found in schedule — Engineer input required."
            elements.append(el)

        elif etype == "slab":
            t = data.get("thickness")
            el = DrawingElement(
                mark=mark_upper,
                element_type=ElementType.SLAB,
                description=f"RCC Slab {mark_upper}",
                depth=Dimension(t, "m", "schedule", Confidence.HIGH) if t else None,
                nos=Dimension(1.0, "nos", "drawing", Confidence.MEDIUM),
                formula=FORMULA_MAP[ElementType.SLAB],
                unit="m3",
                category="rcc",
                status=DetectionStatus.ENGINEER_INPUT_REQ,
                confidence=Confidence.MEDIUM,
                source_info=f"Schedule: {data.get('raw','')}",
                conflict_notes="Slab dimensions (L × B) must be measured from plan by engineer.",
            )
            elements.append(el)

    return elements


def _add_wall_elements(texts: list[str], elements: list[DrawingElement]):
    """Look for wall thickness annotations and create wall elements."""
    all_text = "\n".join(texts)
    wall_patterns = [
        re.compile(r'(?:EXT(?:ERNAL)?|INT(?:ERNAL)?|PARTITION)?\s*WALL\s*[-:=T]?\s*(\d+)\s*(?:MM|mm)?', re.IGNORECASE),
        re.compile(r'(\d+)\s*(?:MM|mm)\s*(?:THICK(?:NESS)?)?\s*WALL', re.IGNORECASE),
    ]
    seen_thicknesses = set()
    for pattern in wall_patterns:
        for m in pattern.finditer(all_text):
            try:
                t_mm = float(m.group(1))
                if t_mm > 500 or t_mm < 50:
                    continue
                t_m = t_mm / 1000.0
                if t_m in seen_thicknesses:
                    continue
                seen_thicknesses.add(t_m)
                label = "External" if "EXT" in m.group(0).upper() else ("Internal" if "INT" in m.group(0).upper() else "")
                elements.append(DrawingElement(
                    mark=f"W{len(seen_thicknesses)}",
                    element_type=ElementType.WALL,
                    description=f"{label} Wall {int(t_mm)}mm thick",
                    depth=Dimension(t_m, "m", "annotation", Confidence.HIGH, m.group(0)),
                    formula=FORMULA_MAP[ElementType.WALL],
                    unit="m3",
                    category="masonry",
                    status=DetectionStatus.ENGINEER_INPUT_REQ,
                    confidence=Confidence.MEDIUM,
                    source_info=f"Annotation: {m.group(0)}",
                    conflict_notes="Wall length and height must be measured from plan by engineer.",
                ))
            except ValueError:
                pass


def _add_door_window_elements(texts: list[str], elements: list[DrawingElement]):
    """Detect door/window schedule entries."""
    all_text = "\n".join(texts)
    dw_patterns = [
        # "D1 - 900x2100" or "W1 - 1200x1200"
        re.compile(r'\b([DW]\d+[A-Z]?)\s*[-:=]?\s*(\d+)\s*[xX×]\s*(\d+)', re.IGNORECASE),
    ]
    for pattern in dw_patterns:
        for m in pattern.finditer(all_text):
            groups = m.groups()
            mark = groups[0].upper()
            is_door = mark.startswith("D")
            try:
                w = _mm_to_m(float(groups[1]))
                h = _mm_to_m(float(groups[2]))
            except (ValueError, IndexError):
                continue
            nos_count = _count_mark_occurrences(texts, mark)
            etype = ElementType.DOOR if is_door else ElementType.WINDOW
            elements.append(DrawingElement(
                mark=mark,
                element_type=etype,
                description=f"{'Door' if is_door else 'Window'} {mark} {int(float(groups[1]))}×{int(float(groups[2]))}mm",
                width=Dimension(w, "m", "schedule", Confidence.HIGH, m.group(0)),
                height=Dimension(h, "m", "schedule", Confidence.HIGH, m.group(0)),
                nos=Dimension(float(nos_count), "nos", "plan_count", Confidence.MEDIUM),
                formula=FORMULA_MAP[etype],
                unit="no",
                category="doors_windows",
                status=DetectionStatus.DETECTED,
                confidence=Confidence.HIGH,
                source_info=f"Schedule: {m.group(0)}",
            ))


def _validation_checks(
    elements: list[DrawingElement],
    schedule: dict,
    texts: list[str],
) -> list[dict]:
    """
    Engineering consistency checks between plan and schedule.
    Returns list of check results with status.
    """
    checks = []

    # Check: schedule has column C1 but plan shows C2 mark too
    schedule_marks = set(schedule.keys())
    plan_marks_found = set()
    for t in texts:
        for m in re.finditer(r'\b([BCF]\d+[A-Z]?)\b', t, re.IGNORECASE):
            plan_marks_found.add(m.group(1).upper())

    in_schedule_not_plan = schedule_marks - plan_marks_found
    in_plan_not_schedule = plan_marks_found - schedule_marks

    if in_plan_not_schedule:
        checks.append({
            "check": "Plan marks not in schedule",
            "marks": list(in_plan_not_schedule),
            "status": "WARNING",
            "message": f"Marks found in plan but not in schedule: {', '.join(in_plan_not_schedule)}. Engineer review required.",
        })

    if in_schedule_not_plan:
        checks.append({
            "check": "Schedule marks not in plan",
            "marks": list(in_schedule_not_plan),
            "status": "INFO",
            "message": f"Schedule marks not found in plan labels: {', '.join(in_schedule_not_plan)}. May be on another sheet.",
        })

    # Check: element count sanity
    for el in elements:
        if el.nos and el.nos.value:
            if el.element_type == ElementType.COLUMN and el.nos.value > 200:
                checks.append({
                    "check": f"Unusual column count for {el.mark}",
                    "status": "WARNING",
                    "message": f"{el.mark}: {el.nos.value} columns detected — unusually high. Engineer verification required.",
                })
            if el.element_type == ElementType.FOOTING and el.nos and el.nos.value:
                # Footing count should roughly match column count
                col_counts = {e.mark: (e.nos.value or 0) for e in elements if e.element_type == ElementType.COLUMN}
                # Basic: total footings should ≈ total columns
                total_cols = sum(col_counts.values())
                total_ftgs = sum(e.nos.value for e in elements if e.element_type == ElementType.FOOTING and e.nos)
                if total_cols > 0 and total_ftgs > 0 and abs(total_cols - total_ftgs) > total_cols * 0.2:
                    checks.append({
                        "check": "Column/Footing count mismatch",
                        "status": "WARNING",
                        "message": f"Total columns ≈ {total_cols:.0f} but footings ≈ {total_ftgs:.0f}. Check if combined footing schedule is used.",
                    })
                    break

    if not checks:
        checks.append({"check": "Basic validation", "status": "OK", "message": "No major conflicts detected."})

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API: analyze_dxf_drawing
# ─────────────────────────────────────────────────────────────────────────────

def analyze_dxf_drawing(dxf_bytes: bytes, drawing_units: str = "mm") -> DrawingAnalysis:
    """
    Main entry point. Analyze a DXF file for structural elements.

    Returns DrawingAnalysis with:
    - All detected elements (dimensions from schedules/annotations)
    - Confidence flags on each dimension
    - Validation checks
    - Missing information list
    - Engineer verification required flags

    DOES NOT calculate quantities — that is done by the formula engine.
    """
    from app.services.dxf_parser import _decode, _get_insunits, _extract_entities_section

    warnings = []
    missing_info = []

    try:
        text = _decode(dxf_bytes)
        lines = text.splitlines()
    except Exception as e:
        return DrawingAnalysis(
            drawing_info=DrawingInfo(warnings=[f"Failed to read DXF file: {e}"]),
            elements=[], schedule_data={}, validation_checks=[],
            warnings=[f"Cannot read file: {e}"],
            missing_info=["File could not be parsed"],
        )

    # Extract text entities
    ent_lines = _extract_entities_section(lines)
    texts = _extract_texts_from_dxf(ent_lines)

    # Also scan full file for schedule tables (often in TABLES or MODEL space)
    all_texts = _extract_texts_from_dxf(lines)
    combined_texts = list(set(texts + all_texts))

    # Drawing info
    drawing_info = DrawingInfo()
    drawing_info.drawing_type  = _detect_drawing_type(combined_texts)
    drawing_info.floor_level   = _detect_floor_level(combined_texts)
    drawing_info.scale         = _detect_scale(combined_texts)
    drawing_info.units         = drawing_units
    drawing_info.notes         = [t for t in combined_texts if len(t) > 20 and len(t) < 200][:5]

    if drawing_info.scale == "Not detected — Engineer input required":
        warnings.append("Drawing scale not found. Geometric measurements from pixel data are NOT computed. Element dimensions come from schedule text only.")
        missing_info.append("Drawing scale / units not detected. Engineer must verify all dimensions.")

    # Storey height
    storey_height = _detect_storey_height(combined_texts)
    if not storey_height:
        warnings.append("Floor-to-floor height not detected in drawing. Column heights will be marked as Engineer Input Required.")
        missing_info.append("Floor-to-floor height (storey height) not found. Required for column RCC calculation.")

    # Read schedule
    schedule = _read_schedule_from_texts(combined_texts)
    if not schedule:
        warnings.append("No element schedule detected (no C1 300×300 type annotations found). Only basic wall/door/window data may be available.")
        missing_info.append("Column/Beam/Footing schedule not detected. Engineer must manually enter all element dimensions.")

    # Build elements from schedule
    elements = _build_elements_from_schedule(schedule, combined_texts, storey_height, drawing_units)

    # Add walls
    _add_wall_elements(combined_texts, elements)

    # Add doors/windows
    _add_door_window_elements(combined_texts, elements)

    # Validation
    validation_checks = _validation_checks(elements, schedule, combined_texts)

    # Missing info summary
    for el in elements:
        if el.status == DetectionStatus.ENGINEER_INPUT_REQ:
            missing_info.append(f"{el.mark} ({el.element_type.value}): {el.conflict_notes or 'Engineer input required'}")
        if el.status == DetectionStatus.CONFLICT_DETECTED:
            warnings.append(f"Conflict in {el.mark}: {el.conflict_notes}")

    if not elements:
        missing_info.append("No structural elements detected. This may be an architectural plan without schedule annotations. Upload a structural drawing with element schedules.")

    return DrawingAnalysis(
        drawing_info=drawing_info,
        elements=elements,
        schedule_data=schedule,
        validation_checks=validation_checks,
        warnings=warnings,
        missing_info=missing_info,
        total_elements=len(elements),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Convert verified elements → Measurement Book items
# Called AFTER engineer verification — NEVER before
# ─────────────────────────────────────────────────────────────────────────────

def elements_to_mb_items(
    verified_elements: list[dict],
    storey_height_m: float = 3.0,
) -> list[dict]:
    """
    Convert engineer-verified drawing elements into MeasurementBook item dicts.

    Input: list of element dicts (from DrawingElement.to_dict()) with
           engineer-modified values.
    Output: list of dicts ready for POST /measurements/{book_id}/items

    Each item has L, W, H, Nos filled where applicable.
    Formula display is generated by the MeasurementBook API.
    """
    items = []
    sort = 0

    by_type: dict = {}
    for el in verified_elements:
        t = el.get("element_type", "other")
        by_type.setdefault(t, []).append(el)

    for etype, group in by_type.items():
        # Section heading
        items.append({
            "description": etype.replace("_", " ").upper(),
            "is_heading": True,
            "sort_order": sort,
            "unit": None,
        })
        sort += 1

        for el in group:
            mark = el.get("mark", "?")
            et = ElementType(etype) if etype in [e.value for e in ElementType] else ElementType.OTHER

            def _v(key: str) -> Optional[float]:
                d = el.get(key)
                if d and isinstance(d, dict):
                    return d.get("value")
                return None

            nos_v = _v("nos") or 1.0
            l_v   = _v("length")
            w_v   = _v("width")
            h_v   = _v("height") or _v("depth")

            # Map element dims to L, W, H fields
            if et == ElementType.COLUMN:
                item = {"description": el.get("description", f"RCC Column {mark}"), "unit": "m3",
                        "length": w_v, "width": h_v, "height": _v("depth") or storey_height_m,
                        "nos": nos_v}
            elif et == ElementType.BEAM:
                item = {"description": el.get("description", f"RCC Beam {mark}"), "unit": "m3",
                        "length": l_v, "width": w_v, "height": h_v,
                        "nos": nos_v}
            elif et == ElementType.FOOTING:
                item = {"description": el.get("description", f"RCC Footing {mark}"), "unit": "m3",
                        "length": l_v, "width": w_v, "height": h_v,
                        "nos": nos_v}
            elif et == ElementType.SLAB:
                item = {"description": el.get("description", f"RCC Slab {mark}"), "unit": "m3",
                        "length": l_v, "width": w_v, "height": h_v,
                        "nos": nos_v}
            elif et in (ElementType.DOOR, ElementType.WINDOW):
                item = {"description": el.get("description", mark), "unit": "no",
                        "nos": nos_v}
            else:
                item = {"description": el.get("description", mark), "unit": el.get("unit", "m3"),
                        "length": l_v, "width": w_v, "height": h_v, "nos": nos_v}

            item["sort_order"] = sort
            item["item_ref"] = mark
            item["is_heading"] = False
            item["is_manual_override"] = False
            items.append(item)
            sort += 1

    return items
