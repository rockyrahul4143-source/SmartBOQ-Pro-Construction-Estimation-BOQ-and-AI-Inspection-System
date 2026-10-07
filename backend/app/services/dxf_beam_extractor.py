"""
DXF Beam Extractor
==================
Extracts all geometry and structural members from DXF bytes using ezdxf.
Uses recover.read(BytesIO) for maximum compatibility with real-world DXF files.
Generic — no hardcoded project data.
"""
from __future__ import annotations
import io
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ezdxf import recover

from .beam_geometry import (
    ExtractionResult,
    StructuralMember,
    _resolve_beam_geometry,
)

_GEOM_TYPES = {
    "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE",
    "DIMENSION", "TEXT", "MTEXT", "INSERT",
}


def _entity_to_record(entity) -> Dict[str, Any]:
    """Convert an ezdxf entity to a serialisable geometry record."""
    kind = entity.dxftype()
    rec: Dict[str, Any] = {
        "entity_type": kind,
        "handle": entity.dxf.handle if entity.dxf.hasattr("handle") else None,
        "layer": entity.dxf.layer if entity.dxf.hasattr("layer") else "0",
        "coordinates": [],
    }
    try:
        if kind == "LINE":
            s, e = entity.dxf.start, entity.dxf.end
            rec["coordinates"] = [[s.x, s.y, s.z], [e.x, e.y, e.z]]

        elif kind in {"LWPOLYLINE", "POLYLINE"}:
            rec["coordinates"] = [[p[0], p[1], 0.0] for p in entity.get_points("xy")]
            rec["closed"] = entity.closed

        elif kind == "ARC":
            c = entity.dxf.center
            rec["coordinates"] = [[c.x, c.y, c.z]]
            rec["radius"] = entity.dxf.radius
            rec["start_angle"] = entity.dxf.start_angle
            rec["end_angle"] = entity.dxf.end_angle

        elif kind == "CIRCLE":
            c = entity.dxf.center
            rec["coordinates"] = [[c.x, c.y, c.z]]
            rec["radius"] = entity.dxf.radius

        elif kind == "TEXT":
            ins = entity.dxf.insert
            rec["coordinates"] = [[ins.x, ins.y, ins.z]]
            rec["text"] = entity.dxf.text if entity.dxf.hasattr("text") else ""

        elif kind == "MTEXT":
            ins = entity.dxf.insert
            rec["coordinates"] = [[ins.x, ins.y, ins.z]]
            rec["text"] = entity.text if hasattr(entity, "text") else ""

        elif kind == "DIMENSION":
            dp = entity.dxf.defpoint
            rec["coordinates"] = [[dp.x, dp.y, dp.z]]
            rec["measurement"] = (
                entity.dxf.actual_measurement
                if entity.dxf.hasattr("actual_measurement") else None
            )
            rec["defpoint2"] = (
                list(entity.dxf.defpoint2)[:3]
                if entity.dxf.hasattr("defpoint2") else None
            )
            rec["defpoint3"] = (
                list(entity.dxf.defpoint3)[:3]
                if entity.dxf.hasattr("defpoint3") else None
            )

        elif kind == "INSERT":
            ins = entity.dxf.insert
            rec["coordinates"] = [[ins.x, ins.y, ins.z]]
            rec["block_name"] = entity.dxf.name if entity.dxf.hasattr("name") else ""
            rec["attributes"] = (
                [{"tag": a.dxf.tag, "text": a.dxf.text} for a in entity.attribs]
                if hasattr(entity, "attribs") else []
            )
    except Exception:
        pass  # partial record is fine; geometry fields stay empty
    return rec


def _units(doc, entities: List[Dict]) -> Dict[str, Any]:
    """Return drawing units, scale factor, and basic validation."""
    code = doc.header.get("$INSUNITS", 0)
    table = {0: ("unitless", None), 1: ("inches", 25.4), 2: ("feet", 304.8),
             4: ("mm", 1.0), 5: ("cm", 10.0), 6: ("m", 1000.0)}
    units, scale = table.get(code, ("unknown", None))

    # Heuristic: check coordinate range against declared units
    vals = [abs(c[i]) for e in entities for c in e.get("coordinates", []) for i in range(2)]
    rng  = max(vals) - min(vals) if vals else 0
    ok   = "valid"
    
    # Fix metadata mismatch: when INSUNITS claims inches but coordinates are in mm
    if units == "inches" and rng > 5000:
        # Coordinate range suggests mm, not inches
        units = "mm"
        scale = 1.0
        ok = "metadata_mismatch"
    elif units == "mm" and rng > 1_000_000:
        ok = "metadata_mismatch"
    elif units in {"m", "feet"} and rng < 10:
        ok = "metadata_mismatch"

    return {"drawing_units": units, "unit_scale_to_mm": scale,
            "insunits_code": code, "unit_validation": ok}


# ── Member extraction helpers ──────────────────────────────────────────────────

_BEAM_RE   = re.compile(r"(?:E)?(?:[BHTR]|HB|TB)\d+[A-Z0-9]*", re.IGNORECASE)
_COLUMN_RE = re.compile(r"(?:E)?C\d+[A-Z0-9]*", re.IGNORECASE)


def _member_type(label: str) -> Optional[str]:
    if _BEAM_RE.fullmatch(label):
        return "beam"
    if _COLUMN_RE.fullmatch(label):
        return "column"
    return None


def _register(members: List, mark: str, mtype: str,
               entity: Dict, insertion: List[float],
               filename: str, units: str, source: str) -> StructuralMember:
    """
    Register a NEW physical member instance for each label occurrence.
    
    CRITICAL FIX: Each beam label in the drawing represents a PHYSICAL INSTANCE.
    Multiple labels with the same mark (e.g., EB15, EB15, EB15) are separate
    physical beams that must be resolved independently.
    
    Previous logic used (mtype, mark) as key, which merged all EB15 labels into
    one StructuralMember object. This caused incorrect geometry association.
    
    New logic: Create a separate StructuralMember for each label occurrence,
    identified by its spatial location.
    """
    # Create NEW instance for this label occurrence
    m = StructuralMember(
        mark=mark.upper(),
        member_type=mtype,
        source=source,
        source_file=filename,
        drawing_units=units,
        layer=entity["layer"],
        location=(insertion[0], insertion[1]),
    )
    m.entity_refs.append(entity.get("handle") or "")
    m.geometry.append(entity)
    m.coordinates.append(insertion[:2])
    
    # Add to members list (not dict - allows multiple instances)
    members.append(m)
    return m


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_dxf_with_geometry(dxf_bytes: bytes, filename: str) -> ExtractionResult:
    """
    Full DXF extraction: entities, members, beam geometry, clear spans.
    Uses ezdxf recover.read for maximum compatibility.
    """
    try:
        doc, _ = recover.read(io.BytesIO(dxf_bytes))
    except Exception as exc:
        return ExtractionResult(
            members=[],
            metadata={
                "dxf_version": "unknown", "drawing_units": "unknown",
                "extraction_status": "failed", "error": str(exc),
                "member_geometry": {}, "entity_counts": {},
                "unsupported_entity_counts": {}, "layers": [],
                "blocks": [], "block_entities": [], "geometry_entities": [],
            },
        )

    dxf_version = doc.dxfversion
    msp = doc.modelspace()

    # ── Modelspace entities ────────────────────────────────────────────────────
    entity_counts: Counter = Counter()
    entities: List[Dict] = []
    for ent in msp:
        entity_counts[ent.dxftype()] += 1
        if ent.dxftype() in _GEOM_TYPES:
            entities.append(_entity_to_record(ent))

    # ── Layers ────────────────────────────────────────────────────────────────
    layers = [{"name": lyr.dxf.name} for lyr in doc.layers]

    # ── Blocks ────────────────────────────────────────────────────────────────
    block_entities: List[Dict] = []
    block_summary: List[Dict] = []
    for blk in doc.blocks:
        if blk.name.startswith("*"):
            continue
        recs = [
            {**_entity_to_record(e), "block_name": blk.name}
            for e in blk if e.dxftype() in _GEOM_TYPES
        ]
        block_entities.extend(recs)
        block_summary.append({"name": blk.name, "entity_count": len(blk), "entities": recs})

    # ── Units ─────────────────────────────────────────────────────────────────
    unit_info = _units(doc, entities)
    drawing_units = unit_info["drawing_units"]

    # ── Member discovery ──────────────────────────────────────────────────────
    # CRITICAL FIX: Use LIST not DICT to allow multiple instances of same mark
    members: List[StructuralMember] = []

    for ent in entities:
        if ent["entity_type"] not in {"TEXT", "MTEXT"}:
            continue
        label = ent.get("text", "").strip()
        # Handle compound marks like "EB20/EMB1" by splitting on /
        for part in label.split("/"):
            part = part.strip()
            mtype = _member_type(part)
            if mtype:
                ins = ent.get("coordinates", [[0.0, 0.0]])[0]
                _register(members, part, mtype, ent, ins, filename, drawing_units, "dxf_text")

    for ent in entities:
        if ent["entity_type"] != "INSERT":
            continue
        ins = ent.get("coordinates", [[0.0, 0.0]])[0]
        for attr in ent.get("attributes", []):
            label = attr.get("text", "").strip()
            mtype = _member_type(label)
            if mtype:
                m = _register(members, label, mtype, ent, ins,
                               filename, drawing_units, "dxf_block_attribute")
                if mtype == "beam":
                    m.geometry_status = "GEOMETRY_EXTRACTED"

    # ── Beam geometry resolution ───────────────────────────────────────────────
    scale = unit_info.get("unit_scale_to_mm")
    for m in members:
        if m.member_type == "beam":
            _resolve_beam_geometry(m, entities, scale)

    # ── Build member_geometry dict ────────────────────────────────────────────
    # Create unique keys for each physical instance using spatial location
    member_geometry = {}
    instance_counters: Dict[str, int] = {}
    
    for m in members:
        # Generate unique instance ID based on mark and occurrence order
        base_key = f"{m.member_type}_{m.mark}"
        instance_counters[base_key] = instance_counters.get(base_key, 0) + 1
        instance_id = instance_counters[base_key]
        
        # Unique key: type_mark_instance (e.g., beam_EB15_1, beam_EB15_2, etc.)
        unique_key = f"{base_key}_{instance_id}"
        
        member_geometry[unique_key] = {
            "mark": m.mark,
            "member_type": m.member_type,
            "instance_id": instance_id,
            "label_location": list(m.location) if m.location else None,
            "layer": m.layer,
            "entity_refs": m.entity_refs,
            "geometry": m.geometry,
            "bounding_box": m.bounding_box,
            "coordinates": m.coordinates,
            "source_file": m.source_file,
            "drawing_units": m.drawing_units,
            "geometry_status": m.geometry_status,
            "clear_span_mm": m.clear_span_mm,
            "clear_span_method": m.clear_span_method,
            "support_a": m.support_a,
            "support_b": m.support_b,
        }

    metadata = {
        "dxf_version": dxf_version,
        "entity_counts": dict(entity_counts),
        "supported_entity_counts": dict(
            Counter(e["entity_type"] for e in entities)
        ),
        "unsupported_entity_counts": {
            k: v for k, v in entity_counts.items() if k not in _GEOM_TYPES
        },
        "geometry_entity_count": len(entities),
        "geometry_entities": entities,
        "layers": layers,
        "blocks": block_summary,
        "block_entities": block_entities,
        "member_geometry": member_geometry,
        **unit_info,
    }

    return ExtractionResult(members=members, metadata=metadata)


def _ascii_dxf_fallback(dxf_bytes: bytes) -> Tuple[List[StructuralMember], Dict]:
    """
    Minimal regex-based fallback for DXF files that ezdxf cannot parse.
    Returns (members, metadata).  Members list will typically be empty;
    metadata contains basic entity counts for diagnostics.
    """
    try:
        text = dxf_bytes.decode("utf-8", errors="replace")
    except Exception:
        return [], {"error": "Cannot decode DXF bytes"}

    lines = text.splitlines()
    entity_counts: Counter = Counter()
    entities: List[Dict] = []
    i = 0
    while i < len(lines):
        token = lines[i].strip()
        if token in _GEOM_TYPES:
            entity_counts[token] += 1
            if token == "TEXT" and i + 20 < len(lines):
                for j in range(i + 1, min(i + 20, len(lines))):
                    if lines[j].strip() == "1":
                        entities.append({
                            "entity_type": "TEXT",
                            "text": lines[j + 1].strip() if j + 1 < len(lines) else "",
                            "coordinates": [[0.0, 0.0, 0.0]],
                            "layer": "0",
                        })
                        break
        i += 1

    return [], {
        "extraction_method": "ascii_fallback",
        "entity_counts": dict(entity_counts),
        "geometry_entities": entities,
        "drawing_units": "mm",
    }
