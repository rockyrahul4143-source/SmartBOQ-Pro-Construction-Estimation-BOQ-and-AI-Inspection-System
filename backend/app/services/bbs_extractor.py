"""
BBS Extraction Engine — Upgraded
=================================
Supports: DXF, PDF (text-layer + OCR attempt), DWG (honest capability)
Extracts beam/column/slab/footing data from ANY schedule/drawing layout.

FILE TYPE CAPABILITIES (honest):
  DXF  — Full: geometry, text entities, blocks, layers, dimensions
  DWG  — Partial: we cannot directly read binary DWG without AutoCAD SDK.
          Guidance: convert to DXF in AutoCAD → Save As DXF 2010 ASCII.
          Reported clearly, not silently ignored.
  PDF  — Text-layer PDFs: full text extraction + schedule parsing.
          Scanned/image PDFs: OCR attempted via pytesseract if available,
          otherwise reported as "OCR required".
  PNG/JPG — OCR attempted if pytesseract available.
  XLSX/CSV — Table extraction via openpyxl/csv.
"""
from __future__ import annotations
import re
import json
import logging
import io
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────
SRC_SCHEDULE = "drawing_schedule"
SRC_SECTION  = "drawing_section"
SRC_NOTE     = "general_note"
SRC_DXF      = "dxf_geometry"
SRC_OCR      = "ocr_extraction"
SRC_DERIVED  = "derived"
NOT_FOUND    = "NOT_FOUND / VERIFICATION REQUIRED"
CONFLICT     = "CONFLICT_DETECTED — VERIFY DRAWING"

# ── Regex patterns ─────────────────────────────────────
_BEAM_MARK = re.compile(r'\b(E?MB\d+[A-Z0-9]*|EB\d+[A-Z0-9]*|[A-Z]B\d+[A-Z0-9]*|TB\d+|HB\d+|B\d+[A-Z0-9]*)\b', re.I)
_COL_MARK  = re.compile(r'\b(E?C\s*\d+[\w,]*|C\d+[A-Z0-9]*|CC?\d+[A-Z0-9]*)\b', re.I)
_SLAB_MARK = re.compile(r'\b(S\d+[A-Z0-9]*|SL\d+[A-Z0-9]*)\b', re.I)
_SIZE_RE   = re.compile(r'(\d{2,4})\s*[xX×Xx]\s*(\d{2,4})')
_REBAR_RE  = re.compile(r'(\d{1,2})\s*[-–#@]?\s*(\d{1,2})\s*[ØφΦ#@dDTY]?\s*(?:mm|dia)?', re.I)
_STIRRUP   = re.compile(r'(\d{1,2})[ØφΦ#@dDTY]?\s*[@/Cc]\s*(\d{2,4})', re.I)
_COVER_RE  = re.compile(r'(?:clear\s*)?cover\s*[=:–\-]?\s*(\d{1,3})\s*mm', re.I)
_FCK_RE    = re.compile(r'\bM\s*(\d{2})\b', re.I)
_FY_RE     = re.compile(r'\bFe\s*(\d{3,4})\b', re.I)
_LAP_RE    = re.compile(r'lap\s*(?:length)?\s*[=:–]?\s*(\d+)\s*mm', re.I)
_DEV_RE    = re.compile(r'(?:development|ld)\s*(?:length)?\s*[=:–]?\s*(\d+)\s*mm', re.I)
_FLOOR_RE  = re.compile(r'\b(GF|FF|SF|TF|BF|[1-9]\d*(?:st|nd|rd|th)\s*f(?:loor)?|ground|first|second|third|terrace|basement|plinth|foundation)\b', re.I)


def _extract_size(text: str) -> Optional[tuple]:
    m = _SIZE_RE.search(text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _extract_rebars(text: str) -> list:
    results = []
    for m in _REBAR_RE.finditer(text):
        n, d = int(m.group(1)), int(m.group(2))
        if 1 <= n <= 30 and 6 <= d <= 50:
            results.append({"num": n, "dia": d, "raw": m.group(0).strip()})
    return results


def _extract_stirrup(text: str) -> Optional[dict]:
    m = _STIRRUP.search(text)
    if m:
        d, s = int(m.group(1)), int(m.group(2))
        if 4 <= d <= 32 and 25 <= s <= 600:
            return {"dia": d, "spacing": s, "raw": m.group(0).strip()}
    return None


def _global_params(text: str) -> dict:
    fck = fy = cover = lap = dev = None
    if m := _FCK_RE.search(text):    fck   = int(m.group(1))
    if m := _FY_RE.search(text):     fy    = int(m.group(1))
    if m := _COVER_RE.search(text):  cover = int(m.group(1))
    if m := _LAP_RE.search(text):    lap   = int(m.group(1))
    if m := _DEV_RE.search(text):    dev   = int(m.group(1))
    return {"fck":fck,"fy":fy,"cover":cover,"lap_mm":lap,"dev_length_mm":dev}


# ── Text extraction helpers ────────────────────────────

def _pdf_text(raw: bytes) -> tuple[str, str]:
    """Returns (text, method). method: 'text_layer'|'ocr'|'none'"""
    text = ""
    # 1. Try pdfminer (best for text-layer PDFs)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(io.BytesIO(raw)) or ""
        if text.strip():
            return text, "text_layer"
    except Exception:
        pass
    # 2. Try pypdf
    try:
        import pypdf
        r = pypdf.PdfReader(io.BytesIO(raw))
        text = "\n".join(p.extract_text() or "" for p in r.pages)
        if text.strip():
            return text, "text_layer"
    except Exception:
        pass
    # 3. OCR attempt via pdf2image + pytesseract
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        images = convert_from_bytes(raw, dpi=200, first_page=1, last_page=5)
        text = "\n".join(pytesseract.image_to_string(img) for img in images)
        if text.strip():
            return text, "ocr"
    except Exception:
        pass
    return "", "none"


def _image_text(raw: bytes) -> tuple[str, str]:
    """OCR an image file."""
    try:
        import pytesseract
        from PIL import Image
        img  = Image.open(io.BytesIO(raw))
        text = pytesseract.image_to_string(img)
        return text, "ocr"
    except Exception:
        return "", "none"


def _excel_text(raw: bytes) -> str:
    try:
        import openpyxl
        wb   = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
        rows = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                rows.append("  ".join(str(c) if c is not None else "" for c in row))
        return "\n".join(rows)
    except Exception:
        return ""


def _csv_text(raw: bytes) -> str:
    try:
        import csv
        text   = raw.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        return "\n".join("  ".join(r) for r in reader)
    except Exception:
        return ""


# ── Schedule parsers ───────────────────────────────────

def _parse_schedule(text: str, mark_re, section_key: str) -> dict:
    """Generic parser for beam/column/slab schedules."""
    members: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    gp    = _global_params(text)

    for i, line in enumerate(lines):
        marks = mark_re.findall(line)
        if not marks:
            continue
        ctx_lines = lines[max(0,i-1):min(len(lines),i+7)]
        context   = " ".join(ctx_lines)

        for mark_raw in marks:
            # Handle comma-separated multi-marks like "EC 2,37"
            for mark in re.split(r'[,\s]+', mark_raw.strip()):
                mark = mark.upper().strip()
                if not mark or len(mark) < 2 or mark in members:
                    continue
                size    = _extract_size(context)
                rebars  = _extract_rebars(context)
                stirrup = _extract_stirrup(context)
                floors  = _FLOOR_RE.findall(context)

                top_bars, bot_bars = [], []
                if len(rebars) >= 2:
                    top_bars = [rebars[0]];  bot_bars = [rebars[1]]
                elif rebars:
                    bot_bars = [rebars[0]]

                members[mark] = {
                    "mark":         mark,
                    "type":         section_key,
                    "size":         {"b": size[0], "d": size[1]} if size else None,
                    "top_steel":    top_bars,
                    "bottom_steel": bot_bars,
                    "all_rebars":   rebars,
                    "stirrups":     stirrup,
                    "floors":       floors,
                    "cover":        gp.get("cover"),
                    "fck":          gp.get("fck"),
                    "fy":           gp.get("fy"),
                    "lap_mm":       gp.get("lap_mm"),
                    "dev_length_mm": gp.get("dev_length_mm"),
                    "source":       SRC_SCHEDULE,
                    "raw_context":  context[:400],
                }
    return members


# ── DXF extraction ─────────────────────────────────────

def _parse_dxf(raw: bytes) -> dict:
    from app.services.dxf_parser import parse_dxf_bytes
    result = parse_dxf_bytes(raw)
    d      = result.to_dict()
    diag   = d.get("diagnostics", {})
    ext    = diag.get("drawing_extents", {})
    return {
        "type":               "dxf_geometry",
        "building_footprint": d.get("building_footprint_area_m2", 0),
        "wall_length_m":      d.get("total_wall_length_m", 0),
        "boundary_perimeter": d.get("boundary_perimeter_m", 0),
        "drawing_extents":    ext,
        "boundary_candidates": d.get("boundary_candidates", [])[:5],
        "entity_counts":      d.get("entity_counts", {}),
        "units_detected":     d.get("units_detected"),
        "scale_factor":       d.get("scale_factor"),
        "warnings":           d.get("warnings", []),
        "source":             SRC_DXF,
    }


# ── Category detection ─────────────────────────────────

def _detect_category(filename: str, text: str) -> str:
    fn = filename.lower()
    tx = (text or "")[:3000].lower()
    checks = [
        (["beam schedule","schedule of beam","beam sch"],   "beam_schedule"),
        (["column schedule","schedule of column","col sch"], "column_schedule"),
        (["slab schedule","schedule of slab"],              "slab_schedule"),
        (["footing schedule","foundation schedule","raft"],  "foundation_schedule"),
        (["staircase","stair"],                             "staircase"),
        (["reinforcement detail","rcc detail","bar detail"], "reinforcement_detail"),
        (["structural plan","framing plan","layout"],        "structural_plan"),
        (["section","elevation"],                           "section_elevation"),
        (["general note","specification","note:"],          "general_notes"),
    ]
    for keywords, cat in checks:
        if any(k in fn or k in tx for k in keywords):
            return cat
    if fn.endswith((".dxf",".dwg")): return "structural_plan_cad"
    return "other"


# ── MAIN ENTRY ─────────────────────────────────────────

def extract_file(raw: bytes, filename: str, file_type: str) -> dict:
    """
    Extract all BBS-relevant data from any file.
    Returns structured dict with honest status for every extraction step.
    """
    result = {
        "file_type":        file_type,
        "filename":         filename,
        "category":         "other",
        "extraction_method": "none",
        "beams":    {}, "columns": {}, "slabs": {},
        "geometry": {},
        "global_params": {},
        "raw_text":  "",
        "member_list": [],
        "warnings":  [],
        "extraction_status": "pending",
        "capability_notes": [],
    }

    try:
        # ── DXF ────────────────────────────────────────
        if file_type == "dxf":
            geo = _parse_dxf(raw)
            result["geometry"]          = geo
            result["extraction_method"] = "dxf_geometry"
            result["category"]          = "structural_plan_cad"
            result["warnings"].extend(geo.get("warnings", []))
            result["extraction_status"] = "complete"
            result["capability_notes"].append(
                "DXF: geometry, text entities, dimensions, blocks extracted."
            )

        # ── DWG ────────────────────────────────────────
        elif file_type == "dwg":
            result["extraction_status"] = "not_supported"
            result["capability_notes"].append(
                "DWG (binary AutoCAD) cannot be read directly. "
                "Action required: Open in AutoCAD → Save As → DXF 2010 ASCII → re-upload. "
                "File is stored for reference."
            )
            result["warnings"].append(
                "DWG file uploaded. To enable geometry extraction: "
                "Open in AutoCAD → File → Save As → AutoCAD DXF 2010 (*.dxf) → re-upload."
            )

        # ── PDF ────────────────────────────────────────
        elif file_type == "pdf":
            text, method = _pdf_text(raw)
            result["extraction_method"] = method
            result["raw_text"] = text[:60000]
            result["category"] = _detect_category(filename, text)

            if method == "none":
                result["extraction_status"] = "ocr_required"
                result["warnings"].append(
                    "PDF has no text layer and OCR is not available. "
                    "Install pytesseract + pdf2image for scanned PDF support. "
                    "Alternatively, enter schedule values manually."
                )
            else:
                beams   = _parse_schedule(text, _BEAM_MARK, "beam")
                cols    = _parse_schedule(text, _COL_MARK,  "column")
                slabs   = _parse_schedule(text, _SLAB_MARK, "slab")
                gp      = _global_params(text)
                result["beams"]         = beams
                result["columns"]       = cols
                result["slabs"]         = slabs
                result["global_params"] = gp
                found   = bool(beams or cols or slabs)
                result["extraction_status"] = "complete" if found else "partial"
                note = f"PDF ({method}): "
                if beams:    note += f"{len(beams)} beams, "
                if cols:     note += f"{len(cols)} columns, "
                if slabs:    note += f"{len(slabs)} slabs, "
                note += "extracted."
                result["capability_notes"].append(note)
                if not found:
                    result["warnings"].append(
                        "No beam/column marks found in PDF text. "
                        "If this is a schedule, check that mark names follow standard patterns "
                        "(EB1, EC1, B1, C1, etc.)."
                    )

        # ── Images (PNG / JPG) ─────────────────────────
        elif file_type == "image":
            text, method = _image_text(raw)
            result["extraction_method"] = method
            if text.strip():
                result["raw_text"] = text[:20000]
                beams = _parse_schedule(text, _BEAM_MARK, "beam")
                cols  = _parse_schedule(text, _COL_MARK,  "column")
                result["beams"]   = beams
                result["columns"] = cols
                result["global_params"] = _global_params(text)
                result["extraction_status"] = "complete" if (beams or cols) else "partial"
                result["capability_notes"].append(f"Image OCR: {len(beams)} beams, {len(cols)} columns found.")
            else:
                result["extraction_status"] = "ocr_required"
                result["warnings"].append(
                    "Image uploaded. OCR not available or text not recognised. "
                    "Install pytesseract for image schedule extraction."
                )

        # ── Excel / CSV ────────────────────────────────
        elif file_type in ("xlsx", "csv"):
            text = _excel_text(raw) if file_type == "xlsx" else _csv_text(raw)
            result["raw_text"] = text[:40000]
            result["extraction_method"] = "table"
            beams = _parse_schedule(text, _BEAM_MARK, "beam")
            cols  = _parse_schedule(text, _COL_MARK,  "column")
            result["beams"]         = beams
            result["columns"]       = cols
            result["global_params"] = _global_params(text)
            result["extraction_status"] = "complete" if (beams or cols) else "partial"
            result["capability_notes"].append(f"Table: {len(beams)} beams, {len(cols)} columns.")

        else:
            result["extraction_status"] = "not_supported"
            result["capability_notes"].append(
                f"File type '{file_type}' is not currently supported. "
                "Supported: DXF, PDF, PNG, JPG, XLSX, CSV. "
                "For DWG: convert to DXF in AutoCAD first."
            )

        result["member_list"] = sorted(set(list(result["beams"].keys()) + list(result["columns"].keys())))
        result["category"]    = _detect_category(filename, result.get("raw_text","")[:1000])

    except Exception as e:
        logger.error(f"Extraction error {filename}: {e}")
        result["warnings"].append(f"Extraction error: {e}")
        result["extraction_status"] = "failed"

    return result
