"""
BBS Export Service - Excel & PDF Generation
Professional BBS table export with calculation trace
Unified backend calculations for both Excel and PDF formats
"""

import io
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side, Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm

from .manual_bbs_engine import BBSCalculationResult, BBSEntry


class BBSExcelExporter:
    """Professional Excel export for BBS calculations"""
    
    def __init__(self):
        self.workbook = None
        self.worksheet = None
        
    def create_excel_report(
        self, 
        bbs_result: BBSCalculationResult, 
        project_info: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """
        Create professional Excel BBS report
        
        Args:
            bbs_result: BBS calculation result
            project_info: Project metadata
            
        Returns:
            Excel file as BytesIO
        """
        self.workbook = Workbook()
        self.worksheet = self.workbook.active
        self.worksheet.title = "Bar Bending Schedule"
        
        # Set up styles
        self._setup_styles()
        
        # Add project header
        self._add_project_header(project_info or {})
        
        # Add BBS table
        self._add_bbs_table(bbs_result)
        
        # Add diameter summary
        self._add_diameter_summary(bbs_result)
        
        # Add calculation metadata
        self._add_calculation_metadata(bbs_result)
        
        # Save to BytesIO
        excel_buffer = io.BytesIO()
        self.workbook.save(excel_buffer)
        excel_buffer.seek(0)
        
        return excel_buffer
        
    def _setup_styles(self):
        """Setup Excel cell styles"""
        self.header_font = Font(name='Arial', size=12, bold=True)
        self.title_font = Font(name='Arial', size=14, bold=True)
        self.data_font = Font(name='Arial', size=10)
        
        self.thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'), 
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        self.header_fill = PatternFill(
            start_color='D9D9D9',
            end_color='D9D9D9',
            fill_type='solid'
        )
        
        self.center_alignment = Alignment(
            horizontal='center',
            vertical='center'
        )
        
    def _add_project_header(self, project_info: Dict[str, Any]):
        """Add project information header"""
        current_row = 1
        
        # Project title
        self.worksheet.merge_cells(f'A{current_row}:K{current_row}')
        title_cell = self.worksheet[f'A{current_row}']
        title_cell.value = f"BAR BENDING SCHEDULE - {project_info.get('project_name', 'PROJECT')}"
        title_cell.font = self.title_font
        title_cell.alignment = self.center_alignment
        
        current_row += 2
        
        # Project details
        details = [
            ("Project ID:", project_info.get('project_id', 'N/A')),
            ("Date:", datetime.now().strftime('%d/%m/%Y')),
            ("Engineer:", project_info.get('engineer', 'N/A')),
            ("Standards:", "IS 456:2000, IS 2502")
        ]
        
        for detail_name, detail_value in details:
            self.worksheet[f'A{current_row}'].value = detail_name
            self.worksheet[f'A{current_row}'].font = self.header_font
            self.worksheet[f'B{current_row}'].value = detail_value
            self.worksheet[f'B{current_row}'].font = self.data_font
            current_row += 1
            
        self.current_row = current_row + 1
        
    def _add_bbs_table(self, bbs_result: BBSCalculationResult):
        """Add professional BBS table with complete specification compliance"""
        # Table headers as per specification
        headers = [
            "Sr No.", "Member Mark", "Description", "Bar Mark", "Bar Type", 
            "Diameter\n(mm)", "No. of Bars\n/ Set", "No. of\nUnits", "Total No.\nof Bars",
            "Zone", "Spacing\n(mm)", "Cutting Length\n(mm)", "Total Length\n(mm)", 
            "Unit Weight\n(kg/m)", "Total Weight\n(kg)", "Calculation\nSource", 
            "Calculation\nStatus", "Remarks"
        ]
        
        # Add headers
        for col, header in enumerate(headers, 1):
            cell = self.worksheet.cell(row=self.current_row, column=col)
            cell.value = header
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.thin_border
            cell.alignment = self.center_alignment
            
        self.current_row += 1
        
        # Add data rows with complete information
        sr_no = 1
        for entry in bbs_result.entries:
            # Extract detailed information from bending_details and calculation_trace
            member_mark = entry.member_id
            description = self._get_bar_description(entry)
            bar_type = self._get_bar_type(entry)
            zone = self._get_zone_info(entry)
            spacing = self._get_spacing_info(entry)
            calculation_source = self._get_calculation_source(entry)
            calculation_status = self._get_calculation_status(entry)
            remarks = self._format_detailed_remarks(entry)
            
            # Determine units and bars per set
            no_of_sets = entry.number_of_bars
            no_of_units = 1  # Default, can be enhanced based on input data
            total_bars = no_of_sets * no_of_units
            
            row_data = [
                sr_no,
                member_mark,
                description,
                entry.bar_mark,
                bar_type,
                entry.diameter,
                no_of_sets,
                no_of_units,
                total_bars,
                zone,
                spacing,
                round(entry.length_of_each_bar, 1),
                round(entry.total_length, 1),
                round(entry.unit_weight, 3),
                round(entry.total_weight, 2),
                calculation_source,
                calculation_status,
                remarks
            ]
            
            for col, value in enumerate(row_data, 1):
                cell = self.worksheet.cell(row=self.current_row, column=col)
                cell.value = value
                cell.font = self.data_font
                cell.border = self.thin_border
                
                # Center alignment for numeric columns
                if col in [1, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]:
                    cell.alignment = self.center_alignment
                    
            self.current_row += 1
            sr_no += 1
            
        # Add total row
        total_cell = self.worksheet.cell(row=self.current_row, column=15)
        total_cell.value = f"TOTAL: {round(bbs_result.grand_total_weight, 2)} kg"
        total_cell.font = Font(name='Arial', size=11, bold=True)
        total_cell.border = self.thin_border
        
        self.current_row += 2

    def _get_bar_description(self, entry: BBSEntry) -> str:
        """Get bar description from bending details"""
        bending_details = entry.bending_details
        if 'description' in bending_details:
            return bending_details['description']
        elif 'bar_type' in bending_details:
            return bending_details['bar_type'].replace('_', ' ').title()
        elif 'tie_type' in bending_details:
            return bending_details['tie_type'].replace('_', ' ').title()
        return "Reinforcement Bar"
        
    def _get_bar_type(self, entry: BBSEntry) -> str:
        """Get bar type classification"""
        bending_details = entry.bending_details
        if 'bar_type' in bending_details:
            bar_type = bending_details['bar_type']
            if 'main' in bar_type:
                return "Main Bar"
            elif 'extra' in bar_type:
                return "Extra Bar"
            elif 'curtailed' in bar_type:
                return "Curtailed Bar"
        elif 'tie_type' in bending_details:
            return "Lateral Tie"
        return "Reinforcement"
        
    def _get_zone_info(self, entry: BBSEntry) -> str:
        """Get zone information"""
        bending_details = entry.bending_details
        if 'zone' in bending_details:
            return str(bending_details['zone'])
        elif 'zone_type' in bending_details:
            return bending_details['zone_type']
        return "-"
        
    def _get_spacing_info(self, entry: BBSEntry) -> str:
        """Get spacing information"""
        bending_details = entry.bending_details
        if 'spacing_mm' in bending_details:
            return f"{bending_details['spacing_mm']}"
        elif 'spacing' in bending_details:
            return f"{bending_details['spacing']}"
        return "-"
        
    def _get_calculation_source(self, entry: BBSEntry) -> str:
        """Get calculation source"""
        if hasattr(entry, 'calculation_trace') and entry.calculation_trace:
            trace = entry.calculation_trace
            if 'method' in trace:
                return trace['method']
            elif 'formula' in trace:
                return "Calculated"
        return "AUTO CALCULATED"
        
    def _get_calculation_status(self, entry: BBSEntry) -> str:
        """Get calculation status"""
        if hasattr(entry, 'calculation_trace') and entry.calculation_trace:
            trace = entry.calculation_trace
            if 'verification_status' in trace:
                return trace['verification_status']
        return "VERIFIED"
        
    def _format_detailed_remarks(self, entry: BBSEntry) -> str:
        """Format detailed remarks with calculation info"""
        remarks = []
        
        bending_details = entry.bending_details
        if 'remarks' in bending_details and bending_details['remarks']:
            remarks.append(bending_details['remarks'])
            
        # Add lap method if available
        if hasattr(entry, 'calculation_trace') and entry.calculation_trace:
            trace = entry.calculation_trace
            if 'lap_method' in trace:
                remarks.append(f"Lap: {trace['lap_method']}")
            if 'curtailment_rule' in trace:
                remarks.append(f"Curtailment: {trace['curtailment_rule']}")
                
        return "; ".join(remarks) if remarks else ""
        
    def _add_diameter_summary(self, bbs_result: BBSCalculationResult):
        """Add diameter-wise summary table"""
        # Summary header
        summary_header = self.worksheet.cell(row=self.current_row, column=1)
        summary_header.value = "DIAMETER-WISE SUMMARY"
        summary_header.font = self.header_font
        self.current_row += 1
        
        # Summary table headers
        summary_headers = ["Diameter (mm)", "Total Length (mm)", "Total Weight (kg)", "Number of Bars"]
        
        for col, header in enumerate(summary_headers, 1):
            cell = self.worksheet.cell(row=self.current_row, column=col)
            cell.value = header
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.thin_border
            cell.alignment = self.center_alignment
            
        self.current_row += 1
        
        # Summary data
        for diameter, summary in sorted(bbs_result.diameter_summary.items()):
            row_data = [
                diameter,
                round(summary['total_length'], 1),
                round(summary['total_weight'], 2),
                summary['count']
            ]
            
            for col, value in enumerate(row_data, 1):
                cell = self.worksheet.cell(row=self.current_row, column=col)
                cell.value = value
                cell.font = self.data_font
                cell.border = self.thin_border
                cell.alignment = self.center_alignment
                
            self.current_row += 1
            
        self.current_row += 1
        
    def _add_calculation_metadata(self, bbs_result: BBSCalculationResult):
        """Add calculation metadata and formulas"""
        metadata_header = self.worksheet.cell(row=self.current_row, column=1)
        metadata_header.value = "CALCULATION DETAILS"
        metadata_header.font = self.header_font
        self.current_row += 1
        
        metadata_items = [
            ("Calculation Method:", bbs_result.calculation_metadata.get('calculation_method', 'Standard')),
            ("Unit Weight Formula:", "Weight (kg/m) = (diameter²) / 162"),
            ("Development Length:", "As per IS 456:2000 Clause 26.2.1"),
            ("Hook Length:", "9D for 90° hooks (IS 2502)"),
            ("Lap Length Method:", bbs_result.calculation_metadata.get('lap_method', 'Standard'))
        ]
        
        for item_name, item_value in metadata_items:
            self.worksheet[f'A{self.current_row}'].value = item_name
            self.worksheet[f'A{self.current_row}'].font = self.data_font
            self.worksheet[f'B{self.current_row}'].value = item_value
            self.worksheet[f'B{self.current_row}'].font = self.data_font
            self.current_row += 1
            
    def _format_remarks(self, entry: BBSEntry) -> str:
        """Format remarks for BBS entry"""
        remarks = []
        
        if hasattr(entry, 'bending_details') and entry.bending_details:
            if 'bar_type' in entry.bending_details:
                remarks.append(entry.bending_details['bar_type'].replace('_', ' ').title())
            if 'zone_type' in entry.bending_details:
                remarks.append(f"Zone: {entry.bending_details['zone_type']}")
                
        return "; ".join(remarks) if remarks else ""


class BBSPDFExporter:
    """Professional PDF export for BBS calculations"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Setup custom PDF styles"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center
        )
        
        self.header_style = ParagraphStyle(
            'CustomHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=10
        )
        
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=9
        )
        
    def create_pdf_report(
        self,
        bbs_result: BBSCalculationResult,
        project_info: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """
        Create professional PDF BBS report
        
        Args:
            bbs_result: BBS calculation result
            project_info: Project metadata
            
        Returns:
            PDF file as BytesIO
        """
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        story = []
        
        # Add title
        title_text = f"BAR BENDING SCHEDULE - {project_info.get('project_name', 'PROJECT')}"
        story.append(Paragraph(title_text, self.title_style))
        story.append(Spacer(1, 10))
        
        # Add project details
        self._add_project_details(story, project_info or {})
        
        # Add BBS table
        self._add_bbs_table_pdf(story, bbs_result)
        
        # Add diameter summary
        self._add_diameter_summary_pdf(story, bbs_result)
        
        # Add calculation details
        self._add_calculation_details_pdf(story, bbs_result)
        
        doc.build(story)
        pdf_buffer.seek(0)
        
        return pdf_buffer
        
    def _add_project_details(self, story: List, project_info: Dict[str, Any]):
        """Add project details to PDF"""
        details = [
            ["Project ID:", project_info.get('project_id', 'N/A')],
            ["Date:", datetime.now().strftime('%d/%m/%Y')],
            ["Engineer:", project_info.get('engineer', 'N/A')],
            ["Standards:", "IS 456:2000, IS 2502"]
        ]
        
        details_table = Table(details, colWidths=[100, 300])
        details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ]))
        
        story.append(details_table)
        story.append(Spacer(1, 15))
        
    def _add_bbs_table_pdf(self, story: List, bbs_result: BBSCalculationResult):
        """Add main BBS table to PDF"""
        story.append(Paragraph("BAR BENDING SCHEDULE", self.header_style))
        
        # Table headers
        headers = [
            "Bar\nMark", "Member\nID", "Dia\n(mm)", "No. of\nBars", 
            "Length Each\n(mm)", "Total Length\n(mm)", 
            "Unit Wt\n(kg/m)", "Total Wt\n(kg)", "Shape"
        ]
        
        # Table data
        table_data = [headers]
        
        for entry in bbs_result.entries:
            row = [
                entry.bar_mark,
                entry.member_id,
                str(entry.diameter),
                str(entry.number_of_bars),
                f"{entry.length_of_each_bar:.1f}",
                f"{entry.total_length:.1f}",
                f"{entry.unit_weight:.3f}",
                f"{entry.total_weight:.2f}",
                entry.shape_code
            ]
            table_data.append(row)
            
        # Add total row
        total_row = ["", "", "", "", "", "", "TOTAL:", f"{bbs_result.grand_total_weight:.2f} kg", ""]
        table_data.append(total_row)
        
        # Create table
        col_widths = [40, 60, 35, 35, 60, 60, 45, 50, 35]
        bbs_table = Table(table_data, colWidths=col_widths)
        
        # Table styling
        bbs_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 7),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            
            # Total row
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('BACKGROUND', (6, -1), (-1, -1), colors.lightgrey),
        ]))
        
        story.append(bbs_table)
        story.append(Spacer(1, 15))
        
    def _add_diameter_summary_pdf(self, story: List, bbs_result: BBSCalculationResult):
        """Add diameter summary to PDF"""
        story.append(Paragraph("DIAMETER-WISE SUMMARY", self.header_style))
        
        summary_headers = ["Diameter (mm)", "Total Length (mm)", "Total Weight (kg)", "Number of Bars"]
        summary_data = [summary_headers]
        
        for diameter, summary in sorted(bbs_result.diameter_summary.items()):
            row = [
                str(diameter),
                f"{summary['total_length']:.1f}",
                f"{summary['total_weight']:.2f}",
                str(summary['count'])
            ]
            summary_data.append(row)
            
        summary_table = Table(summary_data, colWidths=[80, 100, 100, 80])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 15))
        
    def _add_calculation_details_pdf(self, story: List, bbs_result: BBSCalculationResult):
        """Add calculation details to PDF"""
        story.append(Paragraph("CALCULATION DETAILS", self.header_style))
        
        details_text = f"""
        <b>Calculation Method:</b> {bbs_result.calculation_metadata.get('calculation_method', 'Standard')}<br/>
        <b>Unit Weight Formula:</b> Weight (kg/m) = (diameter²) / 162<br/>
        <b>Development Length:</b> As per IS 456:2000 Clause 26.2.1<br/>
        <b>Hook Length:</b> 9D for 90° hooks (IS 2502)<br/>
        <b>Lap Length Method:</b> {bbs_result.calculation_metadata.get('lap_method', 'Standard')}<br/>
        """
        
        story.append(Paragraph(details_text, self.normal_style))


class BBSExportService:
    """Unified BBS export service for Excel and PDF"""
    
    def __init__(self):
        self.excel_exporter = BBSExcelExporter()
        self.pdf_exporter = BBSPDFExporter()
        
    def export_to_excel(
        self, 
        bbs_result: BBSCalculationResult,
        project_info: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """Export BBS to Excel format"""
        return self.excel_exporter.create_excel_report(bbs_result, project_info)
        
    def export_to_pdf(
        self,
        bbs_result: BBSCalculationResult, 
        project_info: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """Export BBS to PDF format"""
        return self.pdf_exporter.create_pdf_report(bbs_result, project_info)
        
    def export_both_formats(
        self,
        bbs_result: BBSCalculationResult,
        project_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, io.BytesIO]:
        """Export BBS to both Excel and PDF formats"""
        return {
            'excel': self.export_to_excel(bbs_result, project_info),
            'pdf': self.export_to_pdf(bbs_result, project_info)
        }