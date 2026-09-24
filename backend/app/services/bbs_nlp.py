"""
BBS Natural Language Interpreter
==================================
Parses natural-language BBS requests from civil engineers.
Returns a structured CalcRequest that the BBS engine can act on.

This is NOT a generic AI chatbot — it is a domain-specific parser
for civil engineering BBS/reinforcement calculation requests.

Examples handled:
  "Calculate complete BBS of EB5"
  "Find clear span of all beams"
  "Calculate EB5 stirrup cutting length"
  "Calculate BBS for all columns"
  "Calculate total steel by diameter"
  "Give complete project BBS"
  "Calculate column C1 ties"
  "Find all beam spans not written in drawing"
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class CalcRequest:
    """Parsed natural-language BBS request."""
    original:        str
    intent:          str         # complete_bbs|cutting_length|stirrups|span|steel_summary|quantity
    member_type:     str         # beam|column|slab|footing|all|unknown
    members:         List[str]   # specific marks ["EB5"] or ["all"] for all
    bar_position:    str         # bottom|top|stirrup|tie|side_face|extra_top|extra_bot|main|all
    calculation:     str         # cutting_length|lap|development|weight|quantity|span|summary|complete
    scope:           str         # single|all|project
    require_cad:     bool        # true if span/geometry measurement needed
    notes:           str         = ""


# ── Regex helpers ──────────────────────────────────────
_BEAM_MARK_RE = re.compile(r'\b(E?MB\d+[A-Z0-9]*|EB\d+[A-Z0-9]*|[A-Z]B\d+[A-Z0-9]*|TB\d+|HB\d+|B\d+[A-Z0-9]*)\b', re.I)
_COL_MARK_RE  = re.compile(r'\b(E?C\s*\d+[\w,]*|C\d+[A-Z0-9]*)\b', re.I)
_SLAB_MARK_RE = re.compile(r'\b(S\d+[A-Z0-9]*|SL\d+[A-Z0-9]*)\b', re.I)


def parse_request(user_input: str) -> CalcRequest:
    """Parse a natural-language BBS/reinforcement request."""
    raw = user_input.strip()
    q   = raw.lower()

    # ── Detect member type ────────────────────────────
    member_type = "all"
    if any(w in q for w in ["beam","eb","tb","hb","emb"]):
        member_type = "beam"
    if any(w in q for w in ["column","col","ec "," c1"," c2","tie","column c"]):
        member_type = "column"
    if "slab" in q:
        member_type = "slab"
    if any(w in q for w in ["footing","foundation","footing","raft"]):
        member_type = "footing"
    if any(w in q for w in ["staircase","stair"]):
        member_type = "staircase"
    if "all" in q and member_type == "all":
        member_type = "all"

    # ── Extract specific member marks ─────────────────
    marks = (
        _BEAM_MARK_RE.findall(raw) +
        _COL_MARK_RE.findall(raw)  +
        _SLAB_MARK_RE.findall(raw)
    )
    marks = [m.upper().strip() for m in marks]
    if not marks:
        if "all" in q:
            marks = ["all"]
        elif member_type != "all":
            marks = ["all"]   # "calculate all columns"

    scope = "single" if (marks and marks[0] != "all") else "all"
    if any(w in q for w in ["complete project","project bbs","all member","all beam","all column","all slab"]):
        scope = "project"
        marks = ["all"]

    # ── Bar position ──────────────────────────────────
    bar_position = "all"
    if any(w in q for w in ["bottom bar","bottom steel","bottom rein"]):
        bar_position = "bottom"
    elif any(w in q for w in ["top bar","top steel","top rein","extra top"]):
        bar_position = "top"
    elif any(w in q for w in ["stirrup","stirrups"]):
        bar_position = "stirrup"
    elif any(w in q for w in [" tie "," ties ","column tie"]):
        bar_position = "tie"
    elif any(w in q for w in ["side face","side-face","side bar"]):
        bar_position = "side_face"
    elif any(w in q for w in ["main bar","main steel","main rein"]):
        bar_position = "main"

    # ── Intent / calculation type ─────────────────────
    intent = "complete_bbs"
    calculation = "complete"

    if any(w in q for w in ["clear span","span of","span not written","measure span","find span","derive span"]):
        intent = "span"
        calculation = "span"
        require_cad = True
    elif any(w in q for w in ["cutting length","cut length"]):
        intent = "cutting_length"
        calculation = "cutting_length"
    elif any(w in q for w in ["total steel","steel by dia","diameter wise","diameter-wise","steel quantity","quantity of steel"]):
        intent = "steel_summary"
        calculation = "summary"
    elif any(w in q for w in ["weight","unit weight"]):
        intent = "weight"
        calculation = "weight"
    elif any(w in q for w in ["lap length","lap "]):
        intent = "cutting_length"
        calculation = "lap"
    elif any(w in q for w in ["development length","ld "]):
        intent = "cutting_length"
        calculation = "development"
    elif any(w in q for w in ["number of","quantity of","how many"]):
        intent = "quantity"
        calculation = "quantity"
    elif any(w in q for w in ["complete bbs","full bbs","generate bbs","bbs of","bbs for"]):
        intent = "complete_bbs"
        calculation = "complete"

    require_cad = (
        calculation in ("span",) or
        "from dwg" in q or "from dxf" in q or "from cad" in q or
        "not written" in q or "measure" in q or "geometry" in q
    )

    # ── Build notes ───────────────────────────────────
    notes_parts = []
    if "floor" in q or "level" in q:
        # Try to extract floor reference
        fm = re.search(r'(ground|first|second|third|\d+(?:st|nd|rd|th)?\s*floor|GF|FF|SF|TF)', raw, re.I)
        if fm: notes_parts.append(f"floor: {fm.group(0)}")
    notes = "; ".join(notes_parts)

    return CalcRequest(
        original=raw, intent=intent, member_type=member_type,
        members=marks, bar_position=bar_position,
        calculation=calculation, scope=scope,
        require_cad=require_cad, notes=notes,
    )


def describe_request(req: CalcRequest) -> str:
    """Human-readable description of what the system understood."""
    members_str = ", ".join(req.members) if req.members != ["all"] else f"all {req.member_type}s"
    if req.member_type == "all" and req.scope == "project":
        members_str = "complete project (all members)"
    return (
        f"Request: {req.intent.replace('_',' ').title()} | "
        f"Member: {members_str} | "
        f"Calculation: {req.calculation} | "
        f"Bar position: {req.bar_position}"
        + (f" | CAD geometry required" if req.require_cad else "")
        + (f" | {req.notes}" if req.notes else "")
    )


def get_required_params(req: CalcRequest) -> List[str]:
    """
    Return the list of engineering parameters needed for this request.
    This drives the cross-file search — what data to look for.
    """
    common = ["cover_mm", "fck", "fy"]

    if req.member_type == "beam":
        base = ["size", "section_b_mm", "section_d_mm", "clear_span_mm",
                "support_near_mm", "support_far_mm"] + common
        if req.bar_position in ("bottom", "all", "main"):
            base += ["bottom_dia_mm", "bottom_num_bars", "bottom_steel"]
        if req.bar_position in ("top", "all"):
            base += ["top_dia_mm", "top_num_bars", "top_steel"]
        if req.bar_position in ("stirrup", "all"):
            base += ["stirrup_dia_mm", "stirrup_spacing_mm", "stirrup_zones"]
        if req.bar_position in ("side_face", "all"):
            base += ["side_face_dia_mm", "side_face_num", "side_face_spacing_mm"]
        if req.calculation == "complete":
            base += ["bottom_dia_mm","bottom_num_bars","top_dia_mm","top_num_bars",
                     "stirrup_dia_mm","stirrup_spacing_mm","lap_mm","dev_length_mm"]
        if req.calculation == "span" or req.require_cad:
            base += ["beam_layout_cad", "support_locations"]
        return list(dict.fromkeys(base))

    if req.member_type == "column":
        base = ["size","section_b_mm","section_d_mm","storey_height_mm",
                "num_main_bars","main_dia_mm","lap_mm","cover_mm"] + common
        if req.bar_position in ("tie","all"):
            base += ["tie_dia_mm","tie_spacing_mm","tie_zones",
                     "tie_top_spacing","tie_mid_spacing","tie_bot_spacing",
                     "tie_top_zone_mm","tie_bot_zone_mm"]
        return list(dict.fromkeys(base))

    if req.member_type == "slab":
        return ["span_mm","width_mm","slab_thickness","dia_mm","spacing_mm",
                "cover_mm","support_mm"] + common

    if req.member_type == "footing":
        return ["length_mm","width_mm","depth_mm","dia_mm","spacing_mm",
                "cover_mm","starter_dia","starter_num"] + common

    # all / project
    return ["size","section_b_mm","section_d_mm","clear_span_mm",
            "storey_height_mm","num_main_bars","main_dia_mm",
            "stirrup_dia_mm","stirrup_spacing_mm","cover_mm","fck","fy"]
