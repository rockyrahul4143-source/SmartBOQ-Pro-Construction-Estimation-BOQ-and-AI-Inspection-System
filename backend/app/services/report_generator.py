"""
Report Generator Service
========================
Generates PDF, Excel, and CSV reports for projects, quantities, BOQs, and costs.
Uses ReportLab for PDF, openpyxl for Excel.
"""
from __future__ import annotations
import io
import csv
from datetime import datetime
from typing import Optional

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Excel
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Colours ───────────────────────────────────────────
PRIMARY   = colors.HexColor("#1E3A5F")   # dark navy
SECONDARY = colors.HexColor("#2E86AB")   # blue
ACCENT    = colors.HexColor("#F0A500")   # amber
LIGHT     = colors.HexColor("#EFF6FF")   # pale blue
WHITE     = colors.white
GREY      = colors.HexColor("#6B7280")


def _header_footer(canvas, doc, title: str, project_name: str):
    canvas.saveState()
    w, h = A4
    # Header bar
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, h - 2.5*cm, w, 2.5*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(1.5*cm, h - 1.5*cm, "SmartBOQ Pro")
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(w - 1.5*cm, h - 1.5*cm, title)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5*cm, h - 2.2*cm, f"Project: {project_name}")
    canvas.drawRightString(w - 1.5*cm, h - 2.2*cm,
                           f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC")
    # Footer
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5*cm, 0.8*cm, "SmartBOQ Pro — Confidential")
    canvas.drawRightString(w - 1.5*cm, 0.8*cm, f"Page {doc.page}")
    canvas.restoreState()


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("SectionHead", parent=s["Heading2"],
                         textColor=PRIMARY, spaceBefore=12, spaceAfter=4))
    s.add(ParagraphStyle("TableHead", parent=s["Normal"],
                         textColor=WHITE, alignment=TA_CENTER, fontSize=9))
    s.add(ParagraphStyle("CellRight", parent=s["Normal"],
                         alignment=TA_RIGHT, fontSize=8))
    return s


# ─────────────────────────────────────────────────────
# BOQ Report — PDF
# ─────────────────────────────────────────────────────
def generate_boq_pdf(boq, project) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=3*cm, bottomMargin=2*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
    )
    styles = _styles()
    story = []

    # Project info block
    info = [
        ["Project:", project.project_name, "BOQ No:", boq.boq_number],
        ["Client:",  project.client_name,  "Revision:", str(boq.revision)],
        ["Location:", project.location,    "Status:", boq.status.value.upper()],
        ["Date:", datetime.utcnow().strftime("%d %b %Y"), "Currency:", boq.currency],
    ]
    info_table = Table(info, colWidths=[3*cm, 7*cm, 3*cm, 5*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0,0), (0,-1), PRIMARY),
        ("TEXTCOLOR", (2,0), (2,-1), PRIMARY),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY))
    story.append(Spacer(1, 0.3*cm))

    # BOQ table header
    col_widths = [1.5*cm, 7*cm, 1.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    headers = ["Item\nNo", "Description", "Unit", "Quantity", "Rate\n(INR)", "Amount\n(INR)"]
    data = [headers]

    for item in boq.items:
        if item.is_heading:
            data.append([item.item_no, item.description.upper(), "", "", "", ""])
        else:
            data.append([
                item.item_no,
                item.description,
                item.unit,
                f"{item.quantity:,.3f}",
                f"{item.rate:,.2f}",
                f"{item.amount:,.2f}",
            ])

    # Totals
    data.append(["", "", "", "", "Sub-Total:", f"{boq.subtotal or 0:,.2f}"])
    data.append(["", "", "", "", f"Overhead ({boq.overhead_pct}%):", f"{boq.overhead_amount or 0:,.2f}"])
    data.append(["", "", "", "", f"Profit ({boq.profit_pct}%):", f"{boq.profit_amount or 0:,.2f}"])
    data.append(["", "", "", "", f"Contingency ({boq.contingency_pct}%):", f"{boq.contingency_amount or 0:,.2f}"])
    data.append(["", "", "", "", "GRAND TOTAL:", f"{boq.grand_total or 0:,.2f}"])

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    # Build style commands
    style_cmds = [
        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("BACKGROUND",  (0,0), (-1,0),  PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0),  WHITE),
        ("ALIGN",       (3,0), (-1,-1), "RIGHT"),
        ("ALIGN",       (0,0), (1,-1),  "LEFT"),
        ("GRID",        (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-5), [WHITE, LIGHT]),
        ("TOPPADDING",  (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]
    # Colour heading rows
    for i, item in enumerate(boq.items, 1):
        if item.is_heading:
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), SECONDARY))
            style_cmds.append(("TEXTCOLOR",  (0,i), (-1,i), WHITE))
            style_cmds.append(("FONTNAME",   (0,i), (-1,i), "Helvetica-Bold"))
            style_cmds.append(("SPAN",       (1,i), (-1,i)))

    # Grand total row styling
    gt_row = len(data) - 1
    style_cmds += [
        ("BACKGROUND", (0, gt_row), (-1, gt_row), ACCENT),
        ("FONTNAME",   (0, gt_row), (-1, gt_row), "Helvetica-Bold"),
        ("TEXTCOLOR",  (0, gt_row), (-1, gt_row), PRIMARY),
    ]
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, f"BILL OF QUANTITIES — {boq.boq_number}", project.project_name),
        onLaterPages=lambda c, d: _header_footer(c, d, f"BILL OF QUANTITIES — {boq.boq_number}", project.project_name),
    )
    return buf.getvalue()


# ─────────────────────────────────────────────────────
# BOQ Report — Excel
# ─────────────────────────────────────────────────────
def generate_boq_excel(boq, project) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"

    hdr_font  = Font(bold=True, color="FFFFFF", size=10)
    hdr_fill  = PatternFill("solid", fgColor="1E3A5F")
    sec_fill  = PatternFill("solid", fgColor="2E86AB")
    tot_fill  = PatternFill("solid", fgColor="F0A500")
    alt_fill  = PatternFill("solid", fgColor="EFF6FF")
    bd = Side(style="thin", color="D1D5DB")
    border = Border(left=bd, right=bd, top=bd, bottom=bd)
    center = Alignment(horizontal="center", vertical="center")
    right  = Alignment(horizontal="right")

    # Title
    ws.merge_cells("A1:F1")
    ws["A1"] = f"BILL OF QUANTITIES — {boq.boq_number}"
    ws["A1"].font = Font(bold=True, size=14, color="1E3A5F")
    ws["A1"].alignment = center

    ws["A2"], ws["B2"] = "Project:", project.project_name
    ws["A3"], ws["B3"] = "Client:",  project.client_name
    ws["D2"], ws["E2"] = "Status:",  boq.status.value.upper()
    ws["D3"], ws["E3"] = "Currency:", boq.currency

    # Header row
    row = 5
    headers = ["Item No", "Description", "Unit", "Quantity", "Rate (INR)", "Amount (INR)"]
    col_widths = [10, 45, 10, 14, 18, 18]
    for c, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = center
        cell.border = border
        ws.column_dimensions[get_column_letter(c)].width = w

    row += 1
    alt = False
    for item in boq.items:
        if item.is_heading:
            for c in range(1, 7):
                cell = ws.cell(row=row, column=c)
                cell.fill = sec_fill
                cell.font = Font(bold=True, color="FFFFFF", size=9)
                cell.border = border
            ws.cell(row=row, column=1, value=item.item_no)
            ws.cell(row=row, column=2, value=item.description.upper())
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
        else:
            fill = alt_fill if alt else PatternFill()
            alt = not alt
            vals = [item.item_no, item.description, item.unit,
                    item.quantity, item.rate, item.amount]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=row, column=c, value=v)
                cell.fill = fill
                cell.border = border
                cell.font = Font(size=9)
                if c >= 4:
                    cell.number_format = "#,##0.00"
                    cell.alignment = right
        row += 1

    # Totals
    totals = [
        ("", "", "", "", "Sub-Total", boq.subtotal or 0),
        ("", "", "", "", f"Overhead ({boq.overhead_pct}%)", boq.overhead_amount or 0),
        ("", "", "", "", f"Profit ({boq.profit_pct}%)", boq.profit_amount or 0),
        ("", "", "", "", f"Contingency ({boq.contingency_pct}%)", boq.contingency_amount or 0),
        ("", "", "", "", "GRAND TOTAL", boq.grand_total or 0),
    ]
    for t_row in totals:
        is_grand = t_row[4] == "GRAND TOTAL"
        for c, v in enumerate(t_row, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.border = border
            if is_grand:
                cell.fill = tot_fill
                cell.font = Font(bold=True, size=10, color="1E3A5F")
            if c >= 5:
                cell.number_format = "#,##0.00"
                cell.alignment = right
        row += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────
# BOQ Report — CSV
# ─────────────────────────────────────────────────────
def generate_boq_csv(boq, project) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["SmartBOQ Pro — Bill of Quantities"])
    writer.writerow(["Project", project.project_name, "BOQ No", boq.boq_number])
    writer.writerow(["Client", project.client_name, "Status", boq.status.value])
    writer.writerow([])
    writer.writerow(["Item No", "Description", "Unit", "Quantity", "Rate", "Amount"])
    for item in boq.items:
        writer.writerow([
            item.item_no, item.description, item.unit,
            item.quantity if not item.is_heading else "",
            item.rate if not item.is_heading else "",
            item.amount if not item.is_heading else "",
        ])
    writer.writerow([])
    writer.writerow(["", "", "", "", "Sub-Total", boq.subtotal or 0])
    writer.writerow(["", "", "", "", f"Overhead ({boq.overhead_pct}%)", boq.overhead_amount or 0])
    writer.writerow(["", "", "", "", f"Profit ({boq.profit_pct}%)", boq.profit_amount or 0])
    writer.writerow(["", "", "", "", f"Contingency ({boq.contingency_pct}%)", boq.contingency_amount or 0])
    writer.writerow(["", "", "", "", "GRAND TOTAL", boq.grand_total or 0])
    return output.getvalue()


# ─────────────────────────────────────────────────────
# Quantity Report — PDF
# ─────────────────────────────────────────────────────
def generate_quantity_pdf(estimates, project) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=3*cm, bottomMargin=2*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []
    col_widths = [3*cm, 6*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    headers = ["Work Type", "Description", "Unit", "Quantity",
               "Cement\n(Bags)", "Sand\n(CFT)", "Steel\n(kg)"]
    data = [headers]
    for e in estimates:
        data.append([
            e.work_type.value.replace("_", " ").title(),
            f"Qty: {e.quantity:,.3f} {e.unit}",
            e.unit,
            f"{e.quantity:,.3f}",
            f"{e.cement_bags or 0:,.1f}",
            f"{e.sand_cft or 0:,.1f}",
            f"{e.steel_kg or 0:,.1f}",
        ])
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("GRID",       (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
        ("ALIGN",      (3,0), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(tbl)
    doc.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, "QUANTITY REPORT", project.project_name),
        onLaterPages=lambda c, d: _header_footer(c, d, "QUANTITY REPORT", project.project_name),
    )
    return buf.getvalue()
