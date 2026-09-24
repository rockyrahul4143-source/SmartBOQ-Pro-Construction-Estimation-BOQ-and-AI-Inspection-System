"""
BBS Cross-File Query Engine
============================
Searches across ALL uploaded project files to find data for a given member.

Priority order:
  1. Explicit schedule value
  2. DXF geometry measurement
  3. Section/detail
  4. General notes
  5. Derived / calculated
  6. NOT_FOUND — never guesses

Usage:
    dataset = query_member("EB5", project_files, member_type="beam")
    # Returns a MemberDataset with all found values + sources + conflicts
"""
from __future__ import annotations
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)

PRIORITY = {
    "drawing_schedule": 1,
    "dxf_geometry":     2,
    "drawing_section":  3,
    "general_note":     4,
    "derived":          5,
    "user_input":       6,
}
NOT_FOUND = "NOT_FOUND / VERIFICATION REQUIRED"
CONFLICT  = "CONFLICT_DETECTED — VERIFY DRAWING"


@dataclass
class FieldValue:
    """A single value found for one field from one source."""
    value:    Any
    source:   str          # source priority label
    file_name: str         # which file it came from
    raw:      str = ""     # raw text snippet

    def priority(self) -> int:
        return PRIORITY.get(self.source, 99)


@dataclass
class MemberDataset:
    """All collected data for one structural member from all files."""
    mark:        str
    member_type: str    # beam|column|slab|footing

    # Collected field values (list because same field may appear in multiple files)
    _fields: dict[str, list[FieldValue]] = field(default_factory=dict)

    def add(self, field_name: str, value: Any, source: str, file_name: str, raw: str = ""):
        if value is None:
            return
        fv = FieldValue(value=value, source=source, file_name=file_name, raw=raw)
        self._fields.setdefault(field_name, []).append(fv)

    def get(self, field_name: str) -> dict:
        """
        Return the best value for a field.
        If multiple sources agree → return value.
        If sources conflict → return CONFLICT with all values.
        If not found → return NOT_FOUND.
        """
        values = self._fields.get(field_name, [])
        if not values:
            return {"value": None, "status": NOT_FOUND, "sources": []}

        # Sort by priority
        values = sorted(values, key=lambda v: v.priority())

        # Check for conflicts: if top 2 sources disagree significantly
        if len(values) >= 2:
            v1, v2 = values[0].value, values[1].value
            if _values_conflict(v1, v2):
                return {
                    "value":   None,
                    "status":  CONFLICT,
                    "sources": [
                        {"value": v.value, "source": v.source, "file": v.file_name}
                        for v in values
                    ],
                }

        best = values[0]
        return {
            "value":   best.value,
            "status":  "found",
            "source":  best.source,
            "file":    best.file_name,
            "all_sources": [
                {"value": v.value, "source": v.source, "file": v.file_name}
                for v in values
            ],
        }

    def to_review_dict(self) -> dict:
        """Return full extracted dataset for engineer review."""
        review = {"mark": self.mark, "member_type": self.member_type, "fields": {}}
        for fn in self._fields:
            review["fields"][fn] = self.get(fn)
        return review

    def to_bbs_inputs(self) -> dict:
        """
        Convert to BBS engine input dict.
        Fields marked NOT_FOUND or CONFLICT are flagged for user input.
        """
        out = {}
        flags = []
        for fn in self._fields:
            r = self.get(fn)
            if r["status"] == "found":
                out[fn] = r["value"]
            elif r["status"].startswith("CONFLICT"):
                out[fn] = None
                flags.append({"field": fn, "status": CONFLICT, "sources": r.get("sources", [])})
            else:
                out[fn] = None
                flags.append({"field": fn, "status": NOT_FOUND})
        out["_flags"] = flags
        return out


def _values_conflict(v1: Any, v2: Any) -> bool:
    """Determine if two values conflict (differ by more than tolerance)."""
    if v1 is None or v2 is None:
        return False
    if type(v1) != type(v2):
        return False
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        # Numeric: conflict if differ by more than 5%
        if max(abs(v1), abs(v2)) == 0:
            return False
        return abs(v1 - v2) / max(abs(v1), abs(v2)) > 0.05
    if isinstance(v1, str):
        return v1.upper().strip() != v2.upper().strip()
    if isinstance(v1, dict):
        # For size dicts {b, d}
        b_diff = abs(v1.get("b",0) - v2.get("b",0))
        d_diff = abs(v1.get("d",0) - v2.get("d",0))
        return b_diff > 5 or d_diff > 5
    return False


# ── Member fuzzy match ────────────────────────────────

def _match_mark(query: str, available: list[str]) -> list[str]:
    """
    Find marks in available that match query.
    Supports: exact, prefix, comma-separated, "all beams", wildcards.
    """
    q = query.strip().upper()

    if q in ("ALL", "ALL BEAMS", "ALL COLUMNS", "ALL SLABS"):
        return available

    # Exact match
    if q in available:
        return [q]

    # Partial match
    matched = [m for m in available if q in m or m.startswith(q)]
    if matched:
        return matched

    # Comma-separated
    parts = [p.strip().upper() for p in re.split(r'[,\s]+', q) if p.strip()]
    matched = [m for m in available if m in parts]
    return matched


# ── Main query function ───────────────────────────────

def query_member(
    member_query: str,
    project_files: list[dict],   # list of {"filename": ..., "extracted_data": json_str, ...}
    member_type: str = "beam",
) -> list[MemberDataset]:
    """
    Search ALL project files for data on the requested member(s).
    Returns a list of MemberDataset objects (one per matched member).
    """
    # Build index of all known members across all files
    all_marks: dict[str, list] = {}   # mark → list of (file_data, source_file_name)

    file_data_list = []
    for pf in project_files:
        raw = pf.get("extracted_data") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {}
        fname = pf.get("original_name") or pf.get("filename") or "unknown"
        file_data_list.append((data, fname))

        # Index beam marks
        for mark in data.get("beams", {}):
            all_marks.setdefault(mark.upper(), []).append(("beam", data, fname))
        # Index column marks
        for mark in data.get("columns", {}):
            all_marks.setdefault(mark.upper(), []).append(("column", data, fname))

    available = list(all_marks.keys())
    matched_marks = _match_mark(member_query, available)

    if not matched_marks:
        # Return empty dataset with NOT_FOUND
        ds = MemberDataset(mark=member_query.upper(), member_type=member_type)
        return [ds]

    datasets = []
    for mark in matched_marks:
        entries = all_marks.get(mark, [])
        mtype   = entries[0][0] if entries else member_type
        ds      = MemberDataset(mark=mark, member_type=mtype)

        for (etype, fdata, fname) in entries:
            members_dict = fdata.get("beams" if etype == "beam" else "columns", {})
            mdata = members_dict.get(mark, {})

            src = mdata.get("source", "drawing_schedule")

            # Size
            sz = mdata.get("size")
            if sz:
                ds.add("size",    sz,         src, fname, str(sz))
                ds.add("section_b_mm", sz.get("b"), src, fname)
                ds.add("section_d_mm", sz.get("d"), src, fname)

            # Reinforcement
            rebars = mdata.get("all_rebars", [])
            tops   = mdata.get("top_steel", [])
            bots   = mdata.get("bottom_steel", [])

            if tops:
                ds.add("top_steel",    tops,       src, fname, str(tops))
                ds.add("top_dia_mm",   tops[0]["dia"], src, fname)
                ds.add("top_num_bars", tops[0]["num"], src, fname)
            if bots:
                ds.add("bottom_steel",    bots,       src, fname, str(bots))
                ds.add("bottom_dia_mm",   bots[0]["dia"], src, fname)
                ds.add("bottom_num_bars", bots[0]["num"], src, fname)
            if rebars and not tops and not bots:
                ds.add("steel",    rebars,           src, fname)
                ds.add("dia_mm",   rebars[0]["dia"], src, fname)
                ds.add("num_bars", rebars[0]["num"], src, fname)

            # Stirrups
            st = mdata.get("stirrups")
            if st:
                ds.add("stirrup_dia_mm",    st["dia"],     src, fname, st.get("raw",""))
                ds.add("stirrup_spacing_mm", st["spacing"], src, fname)

            # Cover / design params
            if mdata.get("cover"):
                ds.add("cover_mm", mdata["cover"], src, fname)
            if mdata.get("fck"):
                ds.add("fck", mdata["fck"], src, fname)
            if mdata.get("fy"):
                ds.add("fy",  mdata["fy"],  src, fname)

        # Also scan global_params from all files
        for (data, fname) in file_data_list:
            gp = data.get("global_params", {})
            src = "general_note"
            if gp.get("fck"):
                ds.add("fck",      gp["fck"],   src, fname)
            if gp.get("fy"):
                ds.add("fy",       gp["fy"],    src, fname)
            if gp.get("cover"):
                ds.add("cover_mm", gp["cover"], src, fname)

        # DXF geometry — add building-level geometry
        for (data, fname) in file_data_list:
            if data.get("geometry", {}).get("type") == "dxf_geometry":
                geo = data["geometry"]
                # Use drawing extents as a possible span reference
                ext = geo.get("drawing_extents", {})
                if ext.get("width_m", 0) > 0:
                    ds.add("drawing_width_m",  ext["width_m"],  "dxf_geometry", fname)
                    ds.add("drawing_height_m", ext["height_m"], "dxf_geometry", fname)

        datasets.append(ds)

    return datasets


def query_to_review(
    member_query: str,
    project_files: list[dict],
    member_type: str = "beam",
) -> dict:
    """
    High-level: query member → return engineer review dict.
    """
    datasets = query_member(member_query, project_files, member_type)
    return {
        "query":   member_query,
        "results": [ds.to_review_dict() for ds in datasets],
        "count":   len(datasets),
        "all_available_members": _index_all_marks(project_files),
    }


def _index_all_marks(project_files: list[dict]) -> dict:
    beams, columns = [], []
    for pf in project_files:
        raw = pf.get("extracted_data") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {}
        beams.extend(list(data.get("beams", {}).keys()))
        columns.extend(list(data.get("columns", {}).keys()))
    return {"beams": sorted(set(beams)), "columns": sorted(set(columns))}
