# Import all models so Alembic can detect them
from app.models.user import User, UserRole
from app.models.project import Project, BuildingType, ProjectStatus
from app.models.building import Building, Room
from app.models.material import Material, MaterialCategory, MaterialUnit, MaterialRateHistory
from app.models.estimate import Estimate, WorkType
from app.models.boq import BOQ, BOQItem, BOQStatus
from app.models.report import Report, ReportType, ReportFormat, AuditLog
from app.models.inspection import Inspection, InspectionType, SeverityLevel
from app.models.sor import SORItem, WorkCategory, RateSource
from app.models.measurement import MeasurementBook, MeasurementItem
from app.models.rate_analysis import RateAnalysis, RateComponent
from app.models.billing import RABill, RABillItem, BillStatus
from app.models.bbs import BBSSheet, BBSBar
from app.models.project_file import ProjectFile

__all__ = [
    "User", "UserRole",
    "Project", "BuildingType", "ProjectStatus",
    "Building", "Room",
    "Material", "MaterialCategory", "MaterialUnit", "MaterialRateHistory",
    "Estimate", "WorkType",
    "BOQ", "BOQItem", "BOQStatus",
    "Report", "ReportType", "ReportFormat", "AuditLog",
    "Inspection", "InspectionType", "SeverityLevel",
    "SORItem", "WorkCategory", "RateSource",
    "MeasurementBook", "MeasurementItem",
    "RateAnalysis", "RateComponent",
    "RABill", "RABillItem", "BillStatus",
    "BBSSheet", "BBSBar",
    "ProjectFile",
]
