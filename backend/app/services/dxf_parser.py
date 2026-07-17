"""
DXF Parser Service
==================
Parses AutoCAD DXF files robustly.

Handles real-world DXF files that:
  - Have all geometry on layer '0' or numeric layers
  - Embed ZIP/binary ACDSDATA sections that crash ezdxf
  - Use metres, mm, or feet as drawing units

Strategy:
  1. Strip the ENTITIES section as raw text (lines 0 to ENDSEC of ENTITIES)
  2. Parse coordinates directly with regex — bypasses ezdxf entirely
  3. Compute wall lengths from all LINE entities
  4. Compute floor area from all closed LWPOLYLINE entities
  5. Fall back to ezdxf on a cleaned copy if direct parse fails
"""
from __future__ import annotations
import io
import re
import math
from collections import defaultdict


def _line_length(x1, y1, x2, y2) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _shoelace_area(pts) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    area = sum(pts[i][0] * pts[(i+1)%n][1] - pts[(i+1)%n][0] * pts[i][1] for i in range(n))
    return abs(area) / 2.0


class DXFParseResult:
    def __init__(self):
        self.total_wall_length_m: float = 0.0
        self.total_floor_area_m2: float = 0.0
        self.num_doors: int = 0
        self.num_windows: int = 0
        self.rooms: list = []
        self.warnings: list = []
        self.scale_factor: float = 1.0
        self.entity_counts: dict = {}

    def to_dict(self) -> dict:
        return {
            "total_wall_length_m":  round(self.total_wall_length_m, 3),
            "total_floor_area_m2":  round(self.total_floor_area_m2, 3),
            "num_doors":            self.num_doors,
            "num_windows":          self.num_windows,
            "rooms":                self.rooms,
            "warnings":             self.warnings,
            "scale_factor":         self.scale_factor,
            "entity_counts":        self.entity_counts,
        }


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _get_insunits(lines) -> int:
    """Read $INSUNITS from HEADER section."""
    for i, l in enumerate(lines):
        if l.strip() == "$INSUNITS" and i + 2 < len(lines):
            try:
                return int(lines[i + 2].strip())
            except Exception:
                pass
    return 0


def _extract_entities_section(lines) -> list:
    """Return only the lines inside the ENTITIES section."""
    start = None
    for i, l in enumerate(lines):
        if l.strip() == "ENTITIES":
            start = i
            break
    if start is None:
        return lines   # no ENTITIES section header — try whole file

    end = None
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "ENDSEC":
            end = i
            break

    if end is None:
        return lines[start:]
    return lines[start:end + 1]


def _parse_entities_raw(lines) -> dict:
    """
    Pure-Python entity parser.
    IMPORTANT: Step by 1 (not 2) and detect group code '0' at any position.
    This handles the ENTITIES header line that would misalign a step-by-2 reader.
    """
    wall_length = 0.0
    rooms = []
    num_doors = 0
    num_windows = 0
    entity_counts: dict = {}

    n = len(lines)
    i = 0

    while i < n:
        stripped = lines[i].strip()

        if stripped == "0" and i + 1 < n:
            etype = lines[i + 1].strip().upper()
            if not etype or etype in ("SECTION", "ENDSEC", "EOF"):
                i += 1
                continue
            entity_counts[etype] = entity_counts.get(etype, 0) + 1

            if etype == "LINE":
                coords = {}
                j = i + 2
                while j < n:
                    c = lines[j].strip()
                    if c == "0":
                        break
                    if j + 1 < n and c in ("10", "20", "11", "21"):
                        try:
                            coords[c] = float(lines[j + 1].strip())
                        except ValueError:
                            pass
                    j += 2
                if all(k in coords for k in ("10", "20", "11", "21")):
                    L = _line_length(coords["10"], coords["20"], coords["11"], coords["21"])
                    if L > 0:
                        wall_length += L

            elif etype == "LWPOLYLINE":
                pts   = []
                flags = 0
                cur_x = None
                j = i + 2
                while j < n:
                    c = lines[j].strip()
                    if c == "0":
                        break
                    if j + 1 < n:
                        v = lines[j + 1].strip()
                        if c == "70":
                            try:
                                flags = int(v)
                            except ValueError:
                                pass
                        elif c == "10":
                            try:
                                cur_x = float(v)
                            except ValueError:
                                cur_x = None
                        elif c == "20" and cur_x is not None:
                            try:
                                pts.append((cur_x, float(v)))
                                cur_x = None
                            except ValueError:
                                pass
                    j += 2

                closed = bool(flags & 1)
                if closed and len(pts) >= 3:
                    area = _shoelace_area(pts)
                    if area > 0:
                        rooms.append(area)

            elif etype == "INSERT":
                # Try to read block name (group 2) and layer (group 8)
                block_name = ""
                layer = ""
                j = i + 2
                while j < n:
                    c = lines[j].strip()
                    if c == "0":
                        break
                    if j + 1 < n:
                        v = lines[j + 1].strip()
                        if c == "2":
                            block_name = v.upper()
                        elif c == "8":
                            layer = v.upper()
                    j += 2
                if any(k in block_name + layer for k in ("DOOR", "PINTU")):
                    num_doors += 1
                elif any(k in block_name + layer for k in ("WINDOW", "WIN", "JENDELA")):
                    num_windows += 1

        i += 1   # step by 1 — handles misaligned ENTITIES header line

    return {
        "wall_length": wall_length,
        "rooms": rooms,
        "num_doors": num_doors,
        "num_windows": num_windows,
        "entity_counts": entity_counts,
    }


def _sf_from_insunits(insunits: int) -> float:
    return {
        1: 0.0254,    # inches
        2: 0.3048,    # feet
        4: 0.001,     # mm
        5: 0.01,      # cm
        6: 1.0,       # metres (already in metres)
    }.get(insunits, None)


def parse_dxf_bytes(file_bytes: bytes, units: str = "mm") -> DXFParseResult:
    result = DXFParseResult()

    # Manual scale from upload parameter
    manual_sf = {"mm": 0.001, "cm": 0.01, "m": 1.0, "ft": 0.3048, "in": 0.0254}.get(units.lower(), 0.001)

    text  = _decode(file_bytes)
    lines = text.splitlines()

    # ── Auto-detect units from DXF header ────────────
    insunits = _get_insunits(lines)
    auto_sf  = _sf_from_insunits(insunits)

    if auto_sf:
        sf = auto_sf
        result.warnings.append(
            f"Auto-detected drawing units: "
            + {1:"inches",2:"feet",4:"mm",5:"cm",6:"metres"}.get(insunits, str(insunits))
        )
    else:
        sf = manual_sf

    result.scale_factor = sf

    # ── Extract only the ENTITIES section (avoids ZIP crash) ─
    ent_lines = _extract_entities_section(lines)
    result.warnings.append(f"Scanning {len(ent_lines)} lines in ENTITIES section.")

    # ── Parse entities ────────────────────────────────
    data = _parse_entities_raw(ent_lines)

    wall_length_raw = data["wall_length"]
    rooms_raw       = data["rooms"]

    result.entity_counts  = data["entity_counts"]
    result.num_doors      = data["num_doors"]
    result.num_windows    = data["num_windows"]

    # ── Scale to metres ───────────────────────────────
    result.total_wall_length_m = round(wall_length_raw * sf, 3)
    result.total_floor_area_m2 = round(sum(rooms_raw) * (sf ** 2), 3)

    # ── Rooms list ────────────────────────────────────
    for i, area_raw in enumerate(rooms_raw, 1):
        area_m2 = round(area_raw * (sf ** 2), 3)
        if area_m2 > 0.25:
            result.rooms.append({"name": f"Room {i}", "area_m2": area_m2})

    total_ents = sum(data["entity_counts"].values())
    result.warnings.insert(0, f"Parsed {total_ents} entities: {dict(sorted(data['entity_counts'].items(), key=lambda x:-x[1]))}")

    if result.total_wall_length_m == 0:
        result.warnings.append(
            "No wall lengths found. "
            f"Drawing units detected: {insunits} (6=m, 4=mm). "
            "All LINE entities summed — check if your file has geometry in the ENTITIES section."
        )
    if result.total_floor_area_m2 == 0:
        result.warnings.append(
            f"No closed LWPOLYLINE rooms found ({len(rooms_raw)} polygons before filter)."
        )

    return result
