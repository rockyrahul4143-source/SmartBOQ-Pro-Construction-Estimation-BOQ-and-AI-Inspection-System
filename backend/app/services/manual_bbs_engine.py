"""
Complete Manual BBS Engineering System
Professional reinforcement calculations with IS 456 compliance
Full specification compliance with detailed beam/column structures
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pydantic import BaseModel, Field, validator
import math
from datetime import datetime


class MemberType(str, Enum):
    """Structural member types"""
    BEAM = "BEAM"
    COLUMN = "COLUMN"


class LapMethod(str, Enum):
    """Lap length calculation methods"""
    DRAWING_SPECIFIED = "DRAWING_SPECIFIED"
    USER_SPECIFIED = "USER_SPECIFIED"
    D30 = "30D"  # 30 times diameter
    D40 = "40D"  # 40 times diameter  
    D45 = "45D"  # 45 times diameter
    D50 = "50D"  # 50 times diameter
    D60 = "60D"  # 60 times diameter
    CUSTOM = "CUSTOM"  # User-defined multiplier
    CODE_BASED = "CODE_BASED"  # Code-based calculation per IS 456


class CurtailmentRule(str, Enum):
    """Beam curtailment options"""
    L_HALF = "L/2"
    L_THIRD = "L/3"
    L_QUARTER = "L/4"
    DRAWING_SPECIFIED = "DRAWING_SPECIFIED"
    CUSTOM = "CUSTOM"


class ExtensionRule(str, Enum):
    """Beam extra bar extension options"""
    L_QUARTER = "L/4"
    L_THIRD = "L/3"
    DRAWING_SPECIFIED = "DRAWING_SPECIFIED"
    CUSTOM = "CUSTOM"


class DimensionConvention(str, Enum):
    """Stirrup dimension conventions"""
    INSIDE = "INSIDE"
    CENTRELINE = "CENTRELINE"
    OUTSIDE = "OUTSIDE"
    DRAWING_SPECIFIED = "DRAWING_SPECIFIED"
    CUSTOM = "CUSTOM"


class QuantitySource(str, Enum):
    """Source of quantity calculation"""
    CALCULATED = "CALCULATED"
    DRAWING_SPECIFIED = "DRAWING_SPECIFIED"


class HookType(str, Enum):
    """Hook/bend types"""
    BEND_45 = "45_DEGREE"
    BEND_90 = "90_DEGREE"
    BEND_135 = "135_DEGREE"
    BEND_180 = "180_DEGREE"
    STANDARD_HOOK = "STANDARD_HOOK"
    CUSTOM = "CUSTOM"


class LapCondition(str, Enum):
    """IS 456 lap conditions"""
    FLEXURAL_TENSION = "FLEXURAL_TENSION"
    DIRECT_TENSION = "DIRECT_TENSION"
    COMPRESSION = "COMPRESSION"


class StirrupZoneType(str, Enum):
    """Stirrup zone classifications"""  
    CONFINED = "CONFINED"  # High density near supports
    REGULAR = "REGULAR"   # Standard spacing in middle
    LAP_SPLICE = "LAP_SPLICE"  # Special spacing at laps
    CUSTOM = "CUSTOM"  # Custom zone type


class ConcreteGrade(str, Enum):
    """Standard concrete grades"""
    M15 = "M15"
    M20 = "M20" 
    M25 = "M25"
    M30 = "M30"
    M35 = "M35"
    M40 = "M40"


class SteelGrade(str, Enum):
    """Steel reinforcement grades"""
    FE415 = "FE415"  # fy = 415 N/mm²
    FE500 = "FE500"  # fy = 500 N/mm²
    FE550 = "FE550"  # fy = 550 N/mm²


@dataclass
class BarPosition:
    """3D position and orientation of a reinforcement bar"""
    x: float  # X coordinate
    y: float  # Y coordinate  
    z: float  # Z coordinate
    rotation: float = 0.0  # Rotation angle in degrees
    level: str = ""  # Floor/level identifier


@dataclass
class StirrupZone:
    """Multi-zone stirrup configuration"""
    zone_type: StirrupZoneType
    start_distance: float  # mm from member start
    end_distance: float    # mm from member start  
    spacing: float         # mm center-to-center
    diameter: int          # mm
    legs: int = 2          # Number of stirrup legs


@dataclass
class ColumnReduction:
    """Column reinforcement reduction at level changes"""
    level_name: str
    reduction_percentage: float  # 0-100%
    start_height: float  # mm from base
    end_height: float    # mm from base
    bars_to_reduce: List[str]  # Bar mark numbers


# Core calculation functions
def unit_weight_kg_per_m(diameter_mm: int) -> float:
    """
    Calculate unit weight of steel reinforcement using standard formula
    Formula: Weight = (d² / 162) kg/m where d is diameter in mm
    
    Args:
        diameter_mm: Bar diameter in millimeters
        
    Returns:
        Unit weight in kg/m
    """
    return (diameter_mm ** 2) / 162


def calculate_lap_length(
    diameter_mm: int,
    method: LapMethod,
    custom_factor: Optional[float] = None,
    drawing_specified_value: Optional[float] = None,
    user_specified_value: Optional[float] = None,
    concrete_grade: ConcreteGrade = ConcreteGrade.M25,
    steel_grade: SteelGrade = SteelGrade.FE415,
    lap_condition: LapCondition = LapCondition.COMPRESSION
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate lap length based on selected method with complete traceability
    
    Args:
        diameter_mm: Bar diameter in mm
        method: Lap calculation method
        custom_factor: Custom multiplier (required if method is CUSTOM)
        drawing_specified_value: Drawing specified value (required if method is DRAWING_SPECIFIED)
        user_specified_value: User specified value (required if method is USER_SPECIFIED)
        concrete_grade: Concrete grade for code-based calculation
        steel_grade: Steel grade for code-based calculation
        lap_condition: Lap condition per IS 456
        
    Returns:
        Tuple of (lap_length_mm, calculation_trace)
    """
    calculation_trace = {
        'input_diameter_mm': diameter_mm,
        'method': method.value,
        'concrete_grade': concrete_grade.value,
        'steel_grade': steel_grade.value,
        'lap_condition': lap_condition.value
    }
    
    if method == LapMethod.DRAWING_SPECIFIED:
        if drawing_specified_value is None:
            raise ValueError("Drawing specified value required for DRAWING_SPECIFIED lap method")
        lap_length = drawing_specified_value
        calculation_trace.update({
            'drawing_specified_mm': drawing_specified_value,
            'formula': 'As per drawing specification',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.USER_SPECIFIED:
        if user_specified_value is None:
            raise ValueError("User specified value required for USER_SPECIFIED lap method")
        lap_length = user_specified_value
        calculation_trace.update({
            'user_specified_mm': user_specified_value,
            'formula': 'User specified value',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.D30:
        lap_length = 30 * diameter_mm
        calculation_trace.update({
            'multiplier': 30,
            'formula': '30 × diameter',
            'calculation': f'30 × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.D40:
        lap_length = 40 * diameter_mm
        calculation_trace.update({
            'multiplier': 40,
            'formula': '40 × diameter',
            'calculation': f'40 × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.D45:
        lap_length = 45 * diameter_mm
        calculation_trace.update({
            'multiplier': 45,
            'formula': '45 × diameter',
            'calculation': f'45 × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.D50:
        lap_length = 50 * diameter_mm
        calculation_trace.update({
            'multiplier': 50,
            'formula': '50 × diameter',
            'calculation': f'50 × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.D60:
        lap_length = 60 * diameter_mm
        calculation_trace.update({
            'multiplier': 60,
            'formula': '60 × diameter',
            'calculation': f'60 × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.CUSTOM:
        if custom_factor is None:
            raise ValueError("Custom factor required for CUSTOM lap method")
        lap_length = custom_factor * diameter_mm
        calculation_trace.update({
            'custom_factor': custom_factor,
            'formula': 'custom_factor × diameter',
            'calculation': f'{custom_factor} × {diameter_mm}',
            'result_mm': lap_length
        })
        
    elif method == LapMethod.CODE_BASED:
        lap_length, is456_trace = calculate_is456_lap_length(
            diameter_mm, concrete_grade, steel_grade, lap_condition
        )
        calculation_trace.update({
            'formula': 'IS 456:2000 code-based calculation',
            'is456_calculation': is456_trace,
            'result_mm': lap_length
        })
    else:
        raise ValueError(f"Unknown lap method: {method}")
        
    return lap_length, calculation_trace


def calculate_is456_lap_length(
    diameter_mm: int,
    concrete_grade: ConcreteGrade,
    steel_grade: SteelGrade,
    lap_condition: LapCondition
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate lap length as per IS 456:2000 with complete breakdown
    
    Args:
        diameter_mm: Bar diameter in mm
        concrete_grade: Concrete grade
        steel_grade: Steel grade  
        lap_condition: Lap condition (flexural tension, direct tension, compression)
        
    Returns:
        Tuple of (lap_length_mm, calculation_trace)
    """
    # Development length first
    dev_length, dev_trace = calculate_development_length_is456(
        diameter_mm, concrete_grade, steel_grade
    )
    
    # Lap length factors per IS 456 Clause 26.2.5
    lap_factors = {
        LapCondition.FLEXURAL_TENSION: {
            'factor': 1.0,
            'description': 'Flexural tension lap',
            'clause': 'IS 456:2000 Cl. 26.2.5.1'
        },
        LapCondition.DIRECT_TENSION: {
            'factor': 2.0,  # Twice the development length
            'description': 'Direct tension lap',
            'clause': 'IS 456:2000 Cl. 26.2.5.2'
        },
        LapCondition.COMPRESSION: {
            'factor': 1.0,  # Same as development length
            'description': 'Compression lap',
            'clause': 'IS 456:2000 Cl. 26.2.5.3'
        }
    }
    
    lap_factor_info = lap_factors[lap_condition]
    lap_length = dev_length * lap_factor_info['factor']
    
    # Minimum lap length requirements
    min_lap_length = 15 * diameter_mm  # IS 456 minimum
    if lap_length < min_lap_length:
        lap_length = min_lap_length
        
    calculation_trace = {
        'development_length_calculation': dev_trace,
        'lap_condition': lap_condition.value,
        'lap_factor': lap_factor_info['factor'],
        'clause_reference': lap_factor_info['clause'],
        'description': lap_factor_info['description'],
        'calculated_lap_mm': dev_length * lap_factor_info['factor'],
        'minimum_lap_mm': min_lap_length,
        'adopted_lap_mm': lap_length,
        'formula': f'Lap = max({lap_factor_info["factor"]} × Ld, 15φ)'
    }
    
    return lap_length, calculation_trace


def calculate_development_length_is456(
    diameter_mm: int,
    concrete_grade: ConcreteGrade = ConcreteGrade.M25,
    steel_grade: SteelGrade = SteelGrade.FE415,
    bar_type: str = "deformed",
    tension_compression: str = "tension"
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate development length as per IS 456:2000 Clause 26.2.1 with complete breakdown
    Formula: Ld = φ × σs / (4 × τbd)
    
    Args:
        diameter_mm: Bar diameter in mm
        concrete_grade: Concrete grade
        steel_grade: Steel grade
        bar_type: Bar type (deformed/plain)
        tension_compression: Loading condition
        
    Returns:
        Tuple of (development_length_mm, calculation_trace)
    """
    # Design bond stress values (τbd) as per IS 456 Table 21
    tbd_values = {
        ConcreteGrade.M15: {'deformed': 1.6, 'plain': 1.2},
        ConcreteGrade.M20: {'deformed': 1.8, 'plain': 1.4},
        ConcreteGrade.M25: {'deformed': 2.0, 'plain': 1.5},
        ConcreteGrade.M30: {'deformed': 2.2, 'plain': 1.7},
        ConcreteGrade.M35: {'deformed': 2.4, 'plain': 1.9},
        ConcreteGrade.M40: {'deformed': 2.6, 'plain': 2.0},
    }
    
    # Steel stress values (σs) for limit state design
    steel_stress = {
        SteelGrade.FE415: 415,  # N/mm²
        SteelGrade.FE500: 500,
        SteelGrade.FE550: 550,
    }
    
    # For limit state design: σs = 0.87 × fy
    fy = steel_stress[steel_grade]
    sigma_s = 0.87 * fy
    
    # Get bond stress
    tbd = tbd_values[concrete_grade][bar_type]
    
    # Development length calculation
    ld = (diameter_mm * sigma_s) / (4 * tbd)
    
    # Minimum development length (IS 456 Clause 26.2.2)
    ld_min = 12 * diameter_mm
    
    # For compression, development length is reduced
    if tension_compression == "compression":
        ld = ld * 0.75  # 25% reduction for compression
    
    # Adopted development length
    ld_adopted = max(ld, ld_min)
    
    calculation_trace = {
        'inputs': {
            'diameter_mm': diameter_mm,
            'concrete_grade': concrete_grade.value,
            'steel_grade': steel_grade.value,
            'bar_type': bar_type,
            'tension_compression': tension_compression
        },
        'material_properties': {
            'fy_nmm2': fy,
            'sigma_s_nmm2': sigma_s,
            'sigma_s_formula': '0.87 × fy',
            'tbd_nmm2': tbd,
            'tbd_source': f'IS 456:2000 Table 21 - {concrete_grade.value} {bar_type}'
        },
        'calculation': {
            'formula': 'Ld = φ × σs / (4 × τbd)',
            'substitution': f'Ld = {diameter_mm} × {sigma_s} / (4 × {tbd})',
            'calculated_ld_mm': ld,
            'minimum_ld_mm': ld_min,
            'minimum_formula': '12 × φ',
            'compression_factor': 0.75 if tension_compression == "compression" else 1.0,
            'adopted_ld_mm': ld_adopted
        },
        'code_references': [
            'IS 456:2000 Clause 26.2.1 - Development length in tension',
            'IS 456:2000 Clause 26.2.2 - Minimum development length',
            'IS 456:2000 Table 21 - Design bond stress'
        ],
        'verification_status': 'CALCULATED' if ld_adopted > ld_min else 'MINIMUM_GOVERNS'
    }
    
    return ld_adopted, calculation_trace


# ══════════════════════════════════════════════════════
# DETAILED BEAM INPUT STRUCTURES
# ══════════════════════════════════════════════════════

class BeamTopMainBar(BaseModel):
    """Top main/continuous bar input"""
    bar_mark: str = Field(..., description="Bar mark/identifier")
    diameter: int = Field(..., description="Bar diameter in mm")
    number_of_bars: int = Field(..., description="Number of bars")
    left_anchorage_ld: Optional[float] = Field(None, description="Left anchorage/Ld in mm")
    right_anchorage_ld: Optional[float] = Field(None, description="Right anchorage/Ld in mm")
    lap_method: LapMethod = Field(LapMethod.CODE_BASED, description="Lap calculation method")
    lap_length: Optional[float] = Field(None, description="Lap length in mm")
    hook_near: Optional[HookType] = Field(None, description="Near side hook type")
    hook_far: Optional[HookType] = Field(None, description="Far side hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_shape: str = Field("straight", description="Bend/shape configuration")
    remarks: str = Field("", description="Additional remarks")


class BeamBottomMainBar(BaseModel):
    """Bottom main/continuous bar input"""
    bar_mark: str = Field(..., description="Bar mark/identifier")
    diameter: int = Field(..., description="Bar diameter in mm")
    number_of_bars: int = Field(..., description="Number of bars")
    left_anchorage_ld: Optional[float] = Field(None, description="Left anchorage/Ld in mm")
    right_anchorage_ld: Optional[float] = Field(None, description="Right anchorage/Ld in mm")
    lap_method: LapMethod = Field(LapMethod.CODE_BASED, description="Lap calculation method")
    lap_length: Optional[float] = Field(None, description="Lap length in mm")
    hook_near: Optional[HookType] = Field(None, description="Near side hook type")
    hook_far: Optional[HookType] = Field(None, description="Far side hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_shape: str = Field("straight", description="Bend/shape configuration")
    remarks: str = Field("", description="Additional remarks")


class BeamCurtailedBar(BaseModel):
    """Bottom mid-span/curtailed bar input"""
    bar_mark: str = Field(..., description="Bar mark/identifier")
    diameter: int = Field(..., description="Bar diameter in mm")
    number_of_bars: int = Field(..., description="Number of bars")
    number_of_units: int = Field(1, description="Number of identical units")
    curtailment_rule: CurtailmentRule = Field(..., description="Curtailment rule")
    extension_length: Optional[float] = Field(None, description="Extension length in mm")
    development_anchorage: Optional[float] = Field(None, description="Development/anchorage in mm")
    lap_method: LapMethod = Field(LapMethod.CODE_BASED, description="Lap method")
    lap_length: Optional[float] = Field(None, description="Lap length in mm")
    hook_type: Optional[HookType] = Field(None, description="Hook/bend type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    remarks: str = Field("", description="Additional remarks")


class BeamExtraBar(BaseModel):
    """Top extra bar (left/right) input"""
    bar_mark: str = Field(..., description="Bar mark/identifier")
    diameter: int = Field(..., description="Bar diameter in mm")
    number_of_bars: int = Field(..., description="Number of bars")
    extension_rule: ExtensionRule = Field(..., description="Extension rule")
    extension_length: Optional[float] = Field(None, description="Extension length in mm")
    development_anchorage: Optional[float] = Field(None, description="Development/anchorage in mm")
    lap_method: LapMethod = Field(LapMethod.CODE_BASED, description="Lap method")
    lap_length: Optional[float] = Field(None, description="Lap length in mm")
    hook_type: Optional[HookType] = Field(None, description="Hook/bend type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    remarks: str = Field("", description="Additional remarks")


class BeamStirrupZone(BaseModel):
    """Beam stirrup zone configuration"""
    stirrup_mark: str = Field(..., description="Stirrup mark/identifier")
    diameter: int = Field(..., description="Stirrup diameter in mm")
    spacing: float = Field(..., description="Stirrup spacing in mm")
    zone_length: float = Field(..., description="Zone length in mm")
    number_of_legs: int = Field(2, description="Number of stirrup legs")
    cover: float = Field(25, description="Cover in mm")
    shape: str = Field("rectangular", description="Stirrup shape")
    hook_type: HookType = Field(HookType.BEND_90, description="Hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_convention: str = Field("standard", description="Bend convention")
    quantity_source: QuantitySource = Field(QuantitySource.CALCULATED, description="Quantity source")
    specified_quantity: Optional[int] = Field(None, description="Drawing specified quantity")
    dimension_convention: DimensionConvention = Field(DimensionConvention.CENTRELINE, description="Dimension convention")


class CompleteBeamInput(BaseModel):
    """Complete beam input structure"""
    # Beam Information — project/metadata are OPTIONAL, only beam_mark+dimensions are required
    project: str = Field("", description="Project name/ID (optional metadata)")
    building_tower: str = Field("", description="Building/Tower identifier")
    block: str = Field("", description="Block identifier")
    floor_level: str = Field("", description="Floor/Level")
    drawing_reference: str = Field("", description="Drawing/Sheet reference")
    beam_mark: str = Field(..., description="Beam mark/identifier")
    description: str = Field("", description="Member description")
    number_of_units: int = Field(1, description="Number of identical units")
    
    # Beam Dimensions
    beam_width: float = Field(..., description="Beam width in mm")
    beam_depth: float = Field(..., description="Beam depth in mm")
    clear_span: float = Field(..., description="Clear span in mm")
    
    # Material Properties
    concrete_grade: ConcreteGrade = Field(ConcreteGrade.M25, description="Concrete grade")
    steel_grade: SteelGrade = Field(SteelGrade.FE415, description="Steel grade")
    cover: float = Field(25, description="Cover in mm")
    
    # Reinforcement Details
    top_main_bars: List[BeamTopMainBar] = Field(default_factory=list, description="Top main/continuous bars")
    bottom_main_bars: List[BeamBottomMainBar] = Field(default_factory=list, description="Bottom main/continuous bars")
    bottom_curtailed_bars: List[BeamCurtailedBar] = Field(default_factory=list, description="Bottom curtailed bars")
    top_extra_left_bars: List[BeamExtraBar] = Field(default_factory=list, description="Top extra left bars")
    top_extra_right_bars: List[BeamExtraBar] = Field(default_factory=list, description="Top extra right bars")
    
    # Stirrup Zones
    left_stirrup_zone: Optional[BeamStirrupZone] = Field(None, description="Left/Support zone stirrups")
    middle_stirrup_zone: Optional[BeamStirrupZone] = Field(None, description="Middle zone stirrups")
    right_stirrup_zone: Optional[BeamStirrupZone] = Field(None, description="Right/Support zone stirrups")
    
    # Additional Information
    remarks: str = Field("", description="General remarks")
    # Legacy aliases for backward compatibility (optional)
    member_id: Optional[str] = Field(None, description="Unique beam identifier")
    length: Optional[float] = Field(None, description="Beam length in mm (alias for clear_span)")
    width: Optional[float] = Field(None, description="Beam width in mm (alias for beam_width)") 
    depth: Optional[float] = Field(None, description="Beam depth in mm (alias for beam_depth)")
    clear_cover: float = Field(25, description="Clear cover in mm")
    
    # Main reinforcement
    top_bars: List[Dict[str, Any]] = Field(default_factory=list, description="Top reinforcement bars")
    bottom_bars: List[Dict[str, Any]] = Field(default_factory=list, description="Bottom reinforcement bars")
    
    # Stirrups with multi-zone support
    stirrup_zones: List[StirrupZone] = Field(default_factory=list, description="Stirrup zones")
    
    # Calculation parameters
    lap_method: LapMethod = Field(LapMethod.D50, description="Lap length method")
    custom_lap_factor: Optional[float] = Field(None, description="Custom lap factor")


# ══════════════════════════════════════════════════════
# DETAILED COLUMN INPUT STRUCTURES
# ══════════════════════════════════════════════════════

class ColumnMainBar(BaseModel):
    """Column main vertical bar input"""
    bar_mark: str = Field(..., description="Bar mark/identifier")
    description: str = Field("", description="Bar description")
    diameter: int = Field(..., description="Bar diameter in mm")
    number_of_bars: int = Field(..., description="Number of bars per column")
    number_of_units: int = Field(1, description="Number of units")
    lap_method: LapMethod = Field(LapMethod.CODE_BASED, description="Lap method")
    lap_length: Optional[float] = Field(None, description="Lap length in mm")
    lap_condition: LapCondition = Field(LapCondition.COMPRESSION, description="Lap condition per IS 456")
    development_length: Optional[float] = Field(None, description="Development length in mm")
    top_anchorage: Optional[float] = Field(None, description="Top anchorage in mm")
    bottom_anchorage: Optional[float] = Field(None, description="Bottom anchorage in mm")
    starter_bar: bool = Field(False, description="Has starter bar")
    hook_type: Optional[HookType] = Field(None, description="Hook/bend type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    remarks: str = Field("", description="Additional remarks")


class ColumnReductionLevel(BaseModel):
    """Column reduction/level-wise reinforcement"""
    level_name: str = Field(..., description="Floor/level name")
    column_width: Optional[float] = Field(None, description="Column width at this level")
    column_depth: Optional[float] = Field(None, description="Column depth at this level")
    main_bars: List[ColumnMainBar] = Field(default_factory=list, description="Main bars at this level")
    reduction_percentage: float = Field(0, description="Reduction percentage from base")
    start_height: float = Field(0, description="Start height from base in mm")
    end_height: float = Field(..., description="End height from base in mm")
    bars_to_reduce: List[str] = Field(default_factory=list, description="Bar marks to reduce")
    remarks: str = Field("", description="Level-specific remarks")


class MasterStirrup(BaseModel):
    """Master/main closed stirrup"""
    link_mark: str = Field(..., description="Link mark/identifier")
    description: str = Field("Main closed stirrup", description="Link description")
    diameter: int = Field(..., description="Link diameter in mm")
    shape: str = Field("rectangular", description="Link shape")
    column_width: Optional[float] = Field(None, description="Column width in mm (derived from column if omitted)")
    column_depth: Optional[float] = Field(None, description="Column depth in mm (derived from column if omitted)")
    cover: float = Field(40, description="Cover in mm")
    hook_type: HookType = Field(HookType.BEND_90, description="Hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_angle: float = Field(90, description="Bend angle in degrees")
    bend_convention: str = Field("standard", description="Bend convention")
    zone: str = Field("full_height", description="Zone identifier")
    zone_length: float = Field(0, description="Zone length in mm (0 = full height)")
    spacing: float = Field(..., description="Stirrup spacing in mm")
    number_of_legs: int = Field(2, description="Number of legs")
    number_per_set: int = Field(1, description="Number per set")
    quantity_source: QuantitySource = Field(QuantitySource.CALCULATED, description="Quantity source")
    specified_quantity: Optional[int] = Field(None, description="Drawing specified quantity")
    dimension_convention: DimensionConvention = Field(DimensionConvention.CENTRELINE, description="Dimension convention")


class ShortLink(BaseModel):
    """Short link configuration"""
    link_mark: str = Field(..., description="Link mark/identifier")
    description: str = Field("Short link", description="Link description")
    diameter: int = Field(..., description="Link diameter in mm")
    shape: str = Field("U", description="Link shape")
    link_width: Optional[float] = Field(None, description="Link width in mm (derived from column if omitted)")
    link_depth: Optional[float] = Field(None, description="Link depth in mm (derived from column if omitted)")
    cover: float = Field(40, description="Cover in mm")
    hook_type: HookType = Field(HookType.BEND_90, description="Hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_angle: float = Field(90, description="Bend angle in degrees")
    zone: str = Field("", description="Zone identifier")
    zone_length: float = Field(0, description="Zone length in mm (0 = full height)")
    spacing: float = Field(..., description="Link spacing in mm")
    number_per_set: int = Field(1, description="Number per set")
    quantity_source: QuantitySource = Field(QuantitySource.CALCULATED, description="Quantity source")
    specified_quantity: Optional[int] = Field(None, description="Drawing specified quantity")


class LongLink(BaseModel):
    """Long link configuration"""
    link_mark: str = Field(..., description="Link mark/identifier")
    description: str = Field("Long link", description="Link description")
    diameter: int = Field(..., description="Link diameter in mm")
    shape: str = Field("U", description="Link shape")
    link_width: Optional[float] = Field(None, description="Link width in mm (derived from column if omitted)")
    link_depth: Optional[float] = Field(None, description="Link depth in mm (derived from column if omitted)")
    cover: float = Field(40, description="Cover in mm")
    hook_type: HookType = Field(HookType.BEND_90, description="Hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_angle: float = Field(90, description="Bend angle in degrees")
    zone: str = Field("", description="Zone identifier")
    zone_length: float = Field(0, description="Zone length in mm (0 = full height)")
    spacing: float = Field(..., description="Link spacing in mm")
    number_per_set: int = Field(1, description="Number per set")
    quantity_source: QuantitySource = Field(QuantitySource.CALCULATED, description="Quantity source")
    specified_quantity: Optional[int] = Field(None, description="Drawing specified quantity")


class CrossTie(BaseModel):
    """Cross tie configuration"""
    link_mark: str = Field(..., description="Link mark/identifier")
    description: str = Field("Cross tie", description="Link description")
    diameter: int = Field(..., description="Link diameter in mm")
    geometry_length: Optional[float] = Field(None, description="Geometry/length in mm (derived from column if omitted)")
    hook_type: HookType = Field(HookType.BEND_90, description="Hook type")
    hook_extension: float = Field(0, description="Hook extension in mm")
    bend_angle: float = Field(90, description="Bend angle in degrees")
    zone: str = Field("", description="Zone identifier")
    zone_length: float = Field(0, description="Zone length in mm (0 = full height)")
    spacing: float = Field(..., description="Tie spacing in mm")
    number_per_set: int = Field(1, description="Number per set")
    quantity_source: QuantitySource = Field(QuantitySource.CALCULATED, description="Quantity source")
    specified_quantity: Optional[int] = Field(None, description="Drawing specified quantity")


class ColumnZone(BaseModel):
    """Column zone configuration"""
    zone_name: str = Field(..., description="Zone name/identifier")
    zone_type: str = Field("regular", description="Zone type (confined/regular/lap_splice/custom)")
    zone_length: float = Field(..., description="Zone length in mm")
    start_distance: float = Field(..., description="Start distance from column base in mm")
    end_distance: float = Field(..., description="End distance from column base in mm")
    link_marks: List[str] = Field(default_factory=list, description="Link marks in this zone")
    spacing_override: Optional[float] = Field(None, description="Zone-specific spacing override")
    remarks: str = Field("", description="Zone-specific remarks")


class CompleteColumnInput(BaseModel):
    """Complete column input structure"""
    # Column Information — project/metadata are OPTIONAL, only column_mark+dimensions are required
    project: str = Field("", description="Project name/ID (optional metadata)")
    building_tower: str = Field("", description="Building/Tower identifier")
    block: str = Field("", description="Block identifier")
    floor_level: str = Field("", description="Floor/Level")
    drawing_reference: str = Field("", description="Drawing/Sheet reference")
    column_mark: str = Field(..., description="Column mark/identifier")
    description: str = Field("", description="Member description")
    number_of_units: int = Field(1, description="Number of identical units")
    
    # Column Dimensions
    column_width: float = Field(..., description="Column width in mm")
    column_depth: float = Field(..., description="Column depth in mm")
    clear_floor_height: float = Field(..., description="Clear floor height in mm")
    
    # Material Properties
    concrete_grade: ConcreteGrade = Field(ConcreteGrade.M25, description="Concrete grade")
    steel_grade: SteelGrade = Field(SteelGrade.FE415, description="Steel grade")
    cover: float = Field(40, description="Cover in mm")
    
    # Main Reinforcement
    main_vertical_bars: List[ColumnMainBar] = Field(default_factory=list, description="Main vertical bars")
    
    # Level-wise Configuration
    reduction_levels: List[ColumnReductionLevel] = Field(default_factory=list, description="Level-wise reductions")
    
    # Lateral Ties
    master_stirrups: List[MasterStirrup] = Field(default_factory=list, description="Master/main stirrups")
    short_links: List[ShortLink] = Field(default_factory=list, description="Short links")
    long_links: List[LongLink] = Field(default_factory=list, description="Long links")
    cross_ties: List[CrossTie] = Field(default_factory=list, description="Cross ties")
    
    # Zone Configuration
    column_zones: List[ColumnZone] = Field(default_factory=list, description="Column zones")
    
    # Additional Information
    remarks: str = Field("", description="General remarks")
    # Legacy aliases for backward compatibility (optional)
    member_id: Optional[str] = Field(None, description="Unique column identifier")
    height: Optional[float] = Field(None, description="Column height in mm (alias for clear_floor_height)")
    width: Optional[float] = Field(None, description="Column width in mm (alias for column_width)")
    depth: Optional[float] = Field(None, description="Column depth in mm (alias for column_depth)") 
    clear_cover: Optional[float] = Field(None, description="Clear cover in mm (alias for cover)")
    
    # Legacy lateral reinforcement fields (optional)
    main_bars: List[Dict[str, Any]] = Field(default_factory=list, description="Main reinforcement bars (legacy)")
    ties: List[Dict[str, Any]] = Field(default_factory=list, description="Tie bars (legacy)")
    stirrup_zones: List[StirrupZone] = Field(default_factory=list, description="Stirrup zones (legacy)")
    reductions: List[ColumnReduction] = Field(default_factory=list, description="Level-wise reductions (legacy)")
    lap_method: LapMethod = Field(LapMethod.D50, description="Lap length method")
    custom_lap_factor: Optional[float] = Field(None, description="Custom lap factor")


@dataclass
class BBSEntry:
    """Single BBS table entry with calculation trace"""
    bar_mark: str
    member_id: str
    diameter: int  # mm
    number_of_bars: int
    length_of_each_bar: float  # mm
    total_length: float  # mm  
    unit_weight: float  # kg/m
    total_weight: float  # kg
    shape_code: str
    bending_details: Dict[str, Any]
    calculation_trace: Dict[str, Any]
    position: Optional[BarPosition] = None


@dataclass
class BBSCalculationResult:
    """Complete BBS calculation result"""
    entries: List[BBSEntry]
    diameter_summary: Dict[int, Dict[str, float]]  # diameter -> {total_length, total_weight}
    grand_total_weight: float
    calculation_metadata: Dict[str, Any]
    member_summaries: Dict[str, Dict[str, Any]]  # member_id -> summary


# ══════════════════════════════════════════════════════
# BEAM CUTTING LENGTH CALCULATIONS
# ══════════════════════════════════════════════════════

def calculate_beam_continuous_bar_length(
    bar: Union[BeamTopMainBar, BeamBottomMainBar],
    clear_span: float,
    concrete_grade: ConcreteGrade,
    steel_grade: SteelGrade
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate cutting length for beam continuous bars
    
    Formula: CL = Clear Span + Left Anchorage/Ld + Right Anchorage/Ld + hooks + laps
    """
    calculation_trace = {
        'bar_mark': bar.bar_mark,
        'diameter_mm': bar.diameter,
        'bar_type': 'continuous',
        'inputs': {
            'clear_span_mm': clear_span,
            'left_anchorage_mm': bar.left_anchorage_ld,
            'right_anchorage_ld_mm': bar.right_anchorage_ld,
            'lap_method': bar.lap_method.value
        }
    }
    
    # Basic length
    basic_length = clear_span
    
    # Left anchorage
    if bar.left_anchorage_ld is not None:
        left_anchorage = bar.left_anchorage_ld
    else:
        # Calculate development length
        left_anchorage, dev_trace = calculate_development_length_is456(
            bar.diameter, concrete_grade, steel_grade
        )
        calculation_trace['left_dev_calculation'] = dev_trace
    
    # Right anchorage  
    if bar.right_anchorage_ld is not None:
        right_anchorage = bar.right_anchorage_ld
    else:
        # Calculate development length
        right_anchorage, dev_trace = calculate_development_length_is456(
            bar.diameter, concrete_grade, steel_grade
        )
        calculation_trace['right_dev_calculation'] = dev_trace
        
    # Hook allowances
    hook_allowance = 0
    if bar.hook_near:
        hook_allowance += calculate_hook_allowance(bar.diameter, bar.hook_near, bar.hook_extension)
    if bar.hook_far:
        hook_allowance += calculate_hook_allowance(bar.diameter, bar.hook_far, bar.hook_extension)
        
    # Lap length if required
    lap_allowance = 0
    if bar.lap_length:
        lap_allowance = bar.lap_length
    elif bar.lap_method != LapMethod.DRAWING_SPECIFIED:
        lap_allowance, lap_trace = calculate_lap_length(
            bar.diameter, bar.lap_method,
            concrete_grade=concrete_grade, steel_grade=steel_grade
        )
        calculation_trace['lap_calculation'] = lap_trace
        
    # Total cutting length
    cutting_length = basic_length + left_anchorage + right_anchorage + hook_allowance + lap_allowance
    
    calculation_trace.update({
        'calculation_breakdown': {
            'basic_length_mm': basic_length,
            'left_anchorage_mm': left_anchorage,
            'right_anchorage_mm': right_anchorage,
            'hook_allowance_mm': hook_allowance,
            'lap_allowance_mm': lap_allowance,
            'total_cutting_length_mm': cutting_length
        },
        'formula': 'CL = Clear Span + Left Anchorage + Right Anchorage + Hooks + Lap',
        'calculation': f'{basic_length} + {left_anchorage} + {right_anchorage} + {hook_allowance} + {lap_allowance} = {cutting_length}'
    })
    
    return cutting_length, calculation_trace


def calculate_beam_curtailed_bar_length(
    bar: BeamCurtailedBar,
    clear_span: float,
    concrete_grade: ConcreteGrade,
    steel_grade: SteelGrade
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate cutting length for beam curtailed bars
    """
    calculation_trace = {
        'bar_mark': bar.bar_mark,
        'diameter_mm': bar.diameter,
        'bar_type': 'curtailed',
        'curtailment_rule': bar.curtailment_rule.value,
        'inputs': {
            'clear_span_mm': clear_span,
            'extension_length_mm': bar.extension_length,
            'development_anchorage_mm': bar.development_anchorage
        }
    }
    
    # Calculate curtailment/extension length
    if bar.curtailment_rule == CurtailmentRule.L_HALF:
        extension_length = clear_span / 2
        calculation_trace['extension_calculation'] = f'L/2 = {clear_span}/2 = {extension_length}'
    elif bar.curtailment_rule == CurtailmentRule.L_THIRD:
        extension_length = clear_span / 3
        calculation_trace['extension_calculation'] = f'L/3 = {clear_span}/3 = {extension_length}'
    elif bar.curtailment_rule == CurtailmentRule.L_QUARTER:
        extension_length = clear_span / 4
        calculation_trace['extension_calculation'] = f'L/4 = {clear_span}/4 = {extension_length}'
    elif bar.curtailment_rule == CurtailmentRule.DRAWING_SPECIFIED:
        if bar.extension_length is None:
            raise ValueError("Extension length required for DRAWING_SPECIFIED curtailment")
        extension_length = bar.extension_length
        calculation_trace['extension_calculation'] = f'Drawing specified: {extension_length}mm'
    elif bar.curtailment_rule == CurtailmentRule.CUSTOM:
        if bar.extension_length is None:
            raise ValueError("Extension length required for CUSTOM curtailment")
        extension_length = bar.extension_length
        calculation_trace['extension_calculation'] = f'Custom: {extension_length}mm'
    
    # Development/anchorage
    if bar.development_anchorage is not None:
        anchorage = bar.development_anchorage
    else:
        anchorage, dev_trace = calculate_development_length_is456(
            bar.diameter, concrete_grade, steel_grade
        )
        calculation_trace['anchorage_calculation'] = dev_trace
        
    # Hook allowance
    hook_allowance = 0
    if bar.hook_type:
        hook_allowance = calculate_hook_allowance(bar.diameter, bar.hook_type, bar.hook_extension)
        
    # Lap allowance
    lap_allowance = 0
    if bar.lap_length:
        lap_allowance = bar.lap_length
    elif bar.lap_method != LapMethod.DRAWING_SPECIFIED:
        lap_allowance, lap_trace = calculate_lap_length(
            bar.diameter, bar.lap_method,
            concrete_grade=concrete_grade, steel_grade=steel_grade
        )
        calculation_trace['lap_calculation'] = lap_trace
        
    # Total cutting length
    cutting_length = extension_length + anchorage + hook_allowance + lap_allowance
    
    calculation_trace.update({
        'calculation_breakdown': {
            'extension_length_mm': extension_length,
            'anchorage_mm': anchorage,
            'hook_allowance_mm': hook_allowance,
            'lap_allowance_mm': lap_allowance,
            'total_cutting_length_mm': cutting_length
        },
        'formula': 'CL = Extension + Anchorage + Hook + Lap',
        'calculation': f'{extension_length} + {anchorage} + {hook_allowance} + {lap_allowance} = {cutting_length}'
    })
    
    return cutting_length, calculation_trace


def calculate_beam_extra_bar_length(
    bar: BeamExtraBar,
    clear_span: float,
    concrete_grade: ConcreteGrade,
    steel_grade: SteelGrade
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate cutting length for beam extra bars (left/right)
    """
    calculation_trace = {
        'bar_mark': bar.bar_mark,
        'diameter_mm': bar.diameter,
        'bar_type': 'extra',
        'extension_rule': bar.extension_rule.value,
        'inputs': {
            'clear_span_mm': clear_span,
            'extension_length_mm': bar.extension_length,
            'development_anchorage_mm': bar.development_anchorage
        }
    }
    
    # Calculate extension length
    if bar.extension_rule == ExtensionRule.L_QUARTER:
        extension_length = clear_span / 4
        calculation_trace['extension_calculation'] = f'L/4 = {clear_span}/4 = {extension_length}'
    elif bar.extension_rule == ExtensionRule.L_THIRD:
        extension_length = clear_span / 3
        calculation_trace['extension_calculation'] = f'L/3 = {clear_span}/3 = {extension_length}'
    elif bar.extension_rule == ExtensionRule.DRAWING_SPECIFIED:
        if bar.extension_length is None:
            raise ValueError("Extension length required for DRAWING_SPECIFIED extension")
        extension_length = bar.extension_length
        calculation_trace['extension_calculation'] = f'Drawing specified: {extension_length}mm'
    elif bar.extension_rule == ExtensionRule.CUSTOM:
        if bar.extension_length is None:
            raise ValueError("Extension length required for CUSTOM extension")
        extension_length = bar.extension_length
        calculation_trace['extension_calculation'] = f'Custom: {extension_length}mm'
        
    # Development/anchorage
    if bar.development_anchorage is not None:
        anchorage = bar.development_anchorage
    else:
        anchorage, dev_trace = calculate_development_length_is456(
            bar.diameter, concrete_grade, steel_grade
        )
        calculation_trace['anchorage_calculation'] = dev_trace
        
    # Hook allowance
    hook_allowance = 0
    if bar.hook_type:
        hook_allowance = calculate_hook_allowance(bar.diameter, bar.hook_type, bar.hook_extension)
        
    # Lap allowance
    lap_allowance = 0
    if bar.lap_length:
        lap_allowance = bar.lap_length
    elif bar.lap_method != LapMethod.DRAWING_SPECIFIED:
        lap_allowance, lap_trace = calculate_lap_length(
            bar.diameter, bar.lap_method,
            concrete_grade=concrete_grade, steel_grade=steel_grade
        )
        calculation_trace['lap_calculation'] = lap_trace
        
    # Total cutting length
    cutting_length = extension_length + anchorage + hook_allowance + lap_allowance
    
    calculation_trace.update({
        'calculation_breakdown': {
            'extension_length_mm': extension_length,
            'anchorage_mm': anchorage,
            'hook_allowance_mm': hook_allowance,
            'lap_allowance_mm': lap_allowance,
            'total_cutting_length_mm': cutting_length
        },
        'formula': 'CL = Extension + Anchorage + Hook + Lap',
        'calculation': f'{extension_length} + {anchorage} + {hook_allowance} + {lap_allowance} = {cutting_length}'
    })
    
    return cutting_length, calculation_trace


def calculate_hook_allowance(
    diameter_mm: int,
    hook_type: HookType,
    hook_extension: float = 0
) -> float:
    """
    Calculate hook allowance based on hook type and bar diameter
    """
    # Standard hook allowances per IS 2502
    hook_allowances = {
        HookType.BEND_45: 2 * diameter_mm,
        HookType.BEND_90: 9 * diameter_mm,  # Standard 90° hook
        HookType.BEND_135: 12 * diameter_mm,
        HookType.BEND_180: 16 * diameter_mm,
        HookType.STANDARD_HOOK: 9 * diameter_mm,
        HookType.CUSTOM: hook_extension
    }
    
    return hook_allowances.get(hook_type, 0)
# ══════════════════════════════════════════════════════
# STIRRUP/LINK CUTTING LENGTH CALCULATIONS
# ══════════════════════════════════════════════════════

def calculate_effective_stirrup_dimensions(
    member_width: float,
    member_depth: float,
    cover: float,
    stirrup_diameter: float,
    dimension_convention: DimensionConvention
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Calculate effective stirrup dimensions based on dimension convention
    
    Returns:
        Tuple of (effective_width, effective_depth, calculation_trace)
    """
    calculation_trace = {
        'inputs': {
            'member_width_mm': member_width,
            'member_depth_mm': member_depth,
            'cover_mm': cover,
            'stirrup_diameter_mm': stirrup_diameter,
            'dimension_convention': dimension_convention.value
        }
    }
    
    if dimension_convention == DimensionConvention.INSIDE:
        # Inside dimensions (clear dimension between main bars)
        effective_width = member_width - 2 * cover - 2 * stirrup_diameter
        effective_depth = member_depth - 2 * cover - 2 * stirrup_diameter
        calculation_trace['formula'] = 'Inside dimension = Member - 2×Cover - 2×Stirrup diameter'
        calculation_trace['calculation'] = {
            'width': f'{member_width} - 2×{cover} - 2×{stirrup_diameter} = {effective_width}',
            'depth': f'{member_depth} - 2×{cover} - 2×{stirrup_diameter} = {effective_depth}'
        }
        
    elif dimension_convention == DimensionConvention.CENTRELINE:
        # Centreline dimensions (to stirrup centerline)
        effective_width = member_width - 2 * cover - stirrup_diameter
        effective_depth = member_depth - 2 * cover - stirrup_diameter
        calculation_trace['formula'] = 'Centreline dimension = Member - 2×Cover - Stirrup diameter'
        calculation_trace['calculation'] = {
            'width': f'{member_width} - 2×{cover} - {stirrup_diameter} = {effective_width}',
            'depth': f'{member_depth} - 2×{cover} - {stirrup_diameter} = {effective_depth}'
        }
        
    elif dimension_convention == DimensionConvention.OUTSIDE:
        # Outside dimensions (to outside of stirrup)
        effective_width = member_width - 2 * cover
        effective_depth = member_depth - 2 * cover
        calculation_trace['formula'] = 'Outside dimension = Member - 2×Cover'
        calculation_trace['calculation'] = {
            'width': f'{member_width} - 2×{cover} = {effective_width}',
            'depth': f'{member_depth} - 2×{cover} = {effective_depth}'
        }
        
    else:
        # Default to centreline
        effective_width = member_width - 2 * cover - stirrup_diameter
        effective_depth = member_depth - 2 * cover - stirrup_diameter
        calculation_trace['note'] = 'Using centreline convention as default'
        
    calculation_trace['results'] = {
        'effective_width_mm': effective_width,
        'effective_depth_mm': effective_depth
    }
    
    return effective_width, effective_depth, calculation_trace


def calculate_stirrup_cutting_length(
    stirrup: BeamStirrupZone,
    member_width: float,
    member_depth: float
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate stirrup cutting length with hooks and bend deductions
    """
    # Get effective dimensions
    eff_width, eff_depth, dim_trace = calculate_effective_stirrup_dimensions(
        member_width, member_depth, stirrup.cover, 
        stirrup.diameter, stirrup.dimension_convention
    )
    
    # Calculate perimeter
    perimeter = 2 * (eff_width + eff_depth)
    
    # Hook allowances
    hook_allowance = calculate_hook_allowance(stirrup.diameter, stirrup.hook_type, stirrup.hook_extension)
    total_hook_allowance = hook_allowance * 2  # Two hooks typically
    
    # Bend deductions (typically 2d per 90° bend for 4 bends)
    bend_deduction = 4 * 2 * stirrup.diameter  # 4 bends × 2d per bend
    
    # Total cutting length
    cutting_length = perimeter + total_hook_allowance - bend_deduction
    
    calculation_trace = {
        'stirrup_mark': stirrup.stirrup_mark,
        'diameter_mm': stirrup.diameter,
        'dimension_calculation': dim_trace,
        'geometry_calculation': {
            'effective_width_mm': eff_width,
            'effective_depth_mm': eff_depth,
            'perimeter_mm': perimeter,
            'perimeter_formula': '2 × (width + depth)',
            'perimeter_calculation': f'2 × ({eff_width} + {eff_depth}) = {perimeter}'
        },
        'allowances_deductions': {
            'hook_allowance_each_mm': hook_allowance,
            'total_hook_allowance_mm': total_hook_allowance,
            'bend_deduction_mm': bend_deduction,
            'bend_deduction_formula': '4 × 2d (4 bends × 2d per bend)'
        },
        'final_calculation': {
            'formula': 'CL = Perimeter + Hook Allowances - Bend Deductions',
            'calculation': f'{perimeter} + {total_hook_allowance} - {bend_deduction} = {cutting_length}',
            'cutting_length_mm': cutting_length
        }
    }
    
    return cutting_length, calculation_trace


def calculate_link_cutting_length(
    link: Union[ShortLink, LongLink],
    column_width: float,
    column_depth: float
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate link cutting length for short/long links
    """
    calculation_trace = {
        'link_mark': link.link_mark,
        'link_type': type(link).__name__,
        'diameter_mm': link.diameter,
        'inputs': {
            'link_width_mm': link.link_width,
            'link_depth_mm': link.link_depth,
            'cover_mm': link.cover,
            'column_width_mm': column_width,
            'column_depth_mm': column_depth
        }
    }
    
    # For U-shaped links, calculate the perimeter
    if link.shape.upper() == 'U':
        # U-shape: width + 2 × depth (open on one side)
        perimeter = link.link_width + 2 * link.link_depth
        calculation_trace['geometry'] = {
            'shape': 'U-shaped',
            'perimeter_formula': 'width + 2 × depth',
            'perimeter_calculation': f'{link.link_width} + 2 × {link.link_depth} = {perimeter}'
        }
    else:
        # Rectangular: 2 × (width + depth)
        perimeter = 2 * (link.link_width + link.link_depth)
        calculation_trace['geometry'] = {
            'shape': 'Rectangular',
            'perimeter_formula': '2 × (width + depth)',
            'perimeter_calculation': f'2 × ({link.link_width} + {link.link_depth}) = {perimeter}'
        }
    
    # Hook allowance
    hook_allowance = calculate_hook_allowance(link.diameter, link.hook_type, link.hook_extension)
    
    # For U-links, typically 2 hooks; for closed links, may vary
    num_hooks = 2 if link.shape.upper() == 'U' else 2
    total_hook_allowance = hook_allowance * num_hooks
    
    # Bend deductions
    num_bends = 2 if link.shape.upper() == 'U' else 4
    bend_deduction = num_bends * 2 * link.diameter
    
    # Total cutting length
    cutting_length = perimeter + total_hook_allowance - bend_deduction
    
    calculation_trace.update({
        'allowances_deductions': {
            'hook_allowance_each_mm': hook_allowance,
            'number_of_hooks': num_hooks,
            'total_hook_allowance_mm': total_hook_allowance,
            'number_of_bends': num_bends,
            'bend_deduction_mm': bend_deduction
        },
        'final_calculation': {
            'formula': 'CL = Perimeter + Hook Allowances - Bend Deductions',
            'calculation': f'{perimeter} + {total_hook_allowance} - {bend_deduction} = {cutting_length}',
            'cutting_length_mm': cutting_length
        }
    })
    
    return cutting_length, calculation_trace


def calculate_cross_tie_cutting_length(
    cross_tie: CrossTie
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate cross tie cutting length
    """
    # For cross ties, use the geometry length directly
    basic_length = cross_tie.geometry_length
    
    # Hook allowances
    hook_allowance = calculate_hook_allowance(cross_tie.diameter, cross_tie.hook_type, cross_tie.hook_extension)
    total_hook_allowance = hook_allowance * 2  # Two hooks typically
    
    # Minimal bend deductions for cross ties
    bend_deduction = 2 * 2 * cross_tie.diameter  # 2 bends × 2d per bend
    
    cutting_length = basic_length + total_hook_allowance - bend_deduction
    
    calculation_trace = {
        'cross_tie_mark': cross_tie.link_mark,
        'diameter_mm': cross_tie.diameter,
        'geometry_length_mm': basic_length,
        'allowances_deductions': {
            'hook_allowance_each_mm': hook_allowance,
            'total_hook_allowance_mm': total_hook_allowance,
            'bend_deduction_mm': bend_deduction
        },
        'final_calculation': {
            'formula': 'CL = Geometry Length + Hook Allowances - Bend Deductions',
            'calculation': f'{basic_length} + {total_hook_allowance} - {bend_deduction} = {cutting_length}',
            'cutting_length_mm': cutting_length
        }
    }
    
    return cutting_length, calculation_trace
# ══════════════════════════════════════════════════════
# COLUMN CALCULATIONS WITH REDUCTION AND LEVEL-WISE CONFIGURATION
# ══════════════════════════════════════════════════════

def calculate_column_main_bar_length(
    bar: ColumnMainBar,
    clear_floor_height: float,
    concrete_grade: ConcreteGrade,
    steel_grade: SteelGrade,
    reduction_levels: List[ColumnReductionLevel] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate column main bar cutting length with level-wise reductions
    """
    calculation_trace = {
        'bar_mark': bar.bar_mark,
        'diameter_mm': bar.diameter,
        'bar_type': 'column_main',
        'inputs': {
            'clear_floor_height_mm': clear_floor_height,
            'base_number_of_bars': bar.number_of_bars,
            'lap_method': bar.lap_method.value,
            'lap_condition': bar.lap_condition.value
        }
    }
    
    # Base length
    base_length = clear_floor_height
    
    # Apply level-wise reductions
    effective_length = base_length
    applied_reductions = []
    
    if reduction_levels:
        for level in reduction_levels:
            if bar.bar_mark in level.bars_to_reduce:
                reduction_length = level.end_height - level.start_height
                reduction_amount = reduction_length * (level.reduction_percentage / 100)
                effective_length -= reduction_amount
                
                applied_reductions.append({
                    'level_name': level.level_name,
                    'start_height_mm': level.start_height,
                    'end_height_mm': level.end_height,
                    'reduction_percentage': level.reduction_percentage,
                    'reduction_length_mm': reduction_length,
                    'reduction_amount_mm': reduction_amount
                })
                
    # Development length calculations
    development_length = 0
    if bar.development_length is not None:
        development_length = bar.development_length
    else:
        dev_length, dev_trace = calculate_development_length_is456(
            bar.diameter, concrete_grade, steel_grade, 
            tension_compression="compression"  # Column bars typically in compression
        )
        development_length = dev_length
        calculation_trace['development_calculation'] = dev_trace
        
    # Lap length calculations
    lap_length = 0
    if bar.lap_length is not None:
        lap_length = bar.lap_length
    elif bar.lap_method != LapMethod.DRAWING_SPECIFIED:
        lap_length, lap_trace = calculate_lap_length(
            bar.diameter, bar.lap_method,
            concrete_grade=concrete_grade, steel_grade=steel_grade,
            lap_condition=bar.lap_condition
        )
        calculation_trace['lap_calculation'] = lap_trace
        
    # Anchorages
    top_anchorage = bar.top_anchorage or development_length
    bottom_anchorage = bar.bottom_anchorage or development_length
    
    # Hook allowance
    hook_allowance = 0
    if bar.hook_type:
        hook_allowance = calculate_hook_allowance(bar.diameter, bar.hook_type, bar.hook_extension)
        
    # Total cutting length
    cutting_length = effective_length + top_anchorage + bottom_anchorage + lap_length + hook_allowance
    
    calculation_trace.update({
        'reductions_applied': applied_reductions,
        'calculation_breakdown': {
            'base_length_mm': base_length,
            'effective_length_mm': effective_length,
            'top_anchorage_mm': top_anchorage,
            'bottom_anchorage_mm': bottom_anchorage,
            'lap_length_mm': lap_length,
            'hook_allowance_mm': hook_allowance,
            'total_cutting_length_mm': cutting_length
        },
        'formula': 'CL = Effective Length + Top Anchorage + Bottom Anchorage + Lap + Hook',
        'calculation': f'{effective_length} + {top_anchorage} + {bottom_anchorage} + {lap_length} + {hook_allowance} = {cutting_length}'
    })
    
    return cutting_length, calculation_trace


def calculate_column_reduction_impacts(
    main_bars: List[ColumnMainBar],
    reduction_levels: List[ColumnReductionLevel]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate the impact of level-wise reductions on column reinforcement
    """
    reduction_impacts = {}
    
    for level in reduction_levels:
        level_impact = {
            'level_name': level.level_name,
            'reduction_percentage': level.reduction_percentage,
            'height_range': f'{level.start_height}mm to {level.end_height}mm',
            'affected_bars': [],
            'unaffected_bars': [],
            'reinforcement_changes': {}
        }
        
        for bar in main_bars:
            if bar.bar_mark in level.bars_to_reduce:
                # Calculate new effective bar count
                original_count = bar.number_of_bars
                effective_count = original_count * (1 - level.reduction_percentage / 100)
                
                level_impact['affected_bars'].append({
                    'bar_mark': bar.bar_mark,
                    'diameter_mm': bar.diameter,
                    'original_count': original_count,
                    'effective_count': effective_count,
                    'reduction_count': original_count - effective_count
                })
            else:
                level_impact['unaffected_bars'].append({
                    'bar_mark': bar.bar_mark,
                    'diameter_mm': bar.diameter,
                    'count': bar.number_of_bars
                })
                
        # Calculate reinforcement summary for this level
        total_original_bars = sum(bar.number_of_bars for bar in main_bars if bar.bar_mark in level.bars_to_reduce)
        total_reduced_bars = total_original_bars * (level.reduction_percentage / 100)
        
        level_impact['reinforcement_changes'] = {
            'total_bars_affected': total_original_bars,
            'total_bars_reduced': total_reduced_bars,
            'remaining_bars': total_original_bars - total_reduced_bars
        }
        
        reduction_impacts[level.level_name] = level_impact
        
    return reduction_impacts


# ══════════════════════════════════════════════════════
# QUANTITY CALCULATIONS
# ══════════════════════════════════════════════════════

def calculate_stirrup_quantity(
    zone_length: float,
    spacing: float,
    quantity_source: QuantitySource,
    specified_quantity: Optional[int] = None,
    endpoint_convention: str = "both_ends"
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate number of stirrups/links in a zone
    """
    calculation_trace = {
        'inputs': {
            'zone_length_mm': zone_length,
            'spacing_mm': spacing,
            'quantity_source': quantity_source.value,
            'specified_quantity': specified_quantity,
            'endpoint_convention': endpoint_convention
        }
    }
    
    if quantity_source == QuantitySource.DRAWING_SPECIFIED:
        if specified_quantity is None:
            raise ValueError("Specified quantity required for DRAWING_SPECIFIED source")
        quantity = specified_quantity
        calculation_trace.update({
            'method': 'Drawing specified',
            'result': quantity
        })
    else:
        # Calculate based on spacing
        if endpoint_convention == "both_ends":
            # Include stirrups at both ends: N = (L/s) + 1
            quantity = math.ceil(zone_length / spacing) + 1
            calculation_trace.update({
                'method': 'Calculated with both end stirrups',
                'formula': 'N = ceil(L/s) + 1',
                'calculation': f'ceil({zone_length}/{spacing}) + 1 = {quantity}'
            })
        elif endpoint_convention == "one_end":
            # Include stirrup at one end only
            quantity = math.ceil(zone_length / spacing)
            calculation_trace.update({
                'method': 'Calculated with one end stirrup',
                'formula': 'N = ceil(L/s)',
                'calculation': f'ceil({zone_length}/{spacing}) = {quantity}'
            })
        else:
            # No end stirrups, just spacing-based
            quantity = math.floor(zone_length / spacing)
            calculation_trace.update({
                'method': 'Calculated spacing only',
                'formula': 'N = floor(L/s)',
                'calculation': f'floor({zone_length}/{spacing}) = {quantity}'
            })
            
    calculation_trace['final_quantity'] = quantity
    return quantity, calculation_trace


class CompleteBeamBBSCalculator:
    """Professional beam BBS calculations with complete specification compliance"""
    
    def __init__(self, beam_input: CompleteBeamInput):
        self.input = beam_input
        self.entries: List[BBSEntry] = []
        
    def calculate_bbs(self) -> BBSCalculationResult:
        """Generate complete BBS for beam with all bar types"""
        self.entries = []
        bar_mark_counter = 1
        
        # Calculate top main bars
        for bar in self.input.top_main_bars:
            length, calc_trace = calculate_beam_continuous_bar_length(
                bar, self.input.clear_span, self.input.concrete_grade, self.input.steel_grade
            )
            
            entry = self._create_bbs_entry(
                f"T{bar_mark_counter}", bar, length, calc_trace, "top_main"
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate bottom main bars
        for bar in self.input.bottom_main_bars:
            length, calc_trace = calculate_beam_continuous_bar_length(
                bar, self.input.clear_span, self.input.concrete_grade, self.input.steel_grade
            )
            
            entry = self._create_bbs_entry(
                f"B{bar_mark_counter}", bar, length, calc_trace, "bottom_main"
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate bottom curtailed bars
        for bar in self.input.bottom_curtailed_bars:
            length, calc_trace = calculate_beam_curtailed_bar_length(
                bar, self.input.clear_span, self.input.concrete_grade, self.input.steel_grade
            )
            
            entry = self._create_bbs_entry(
                f"C{bar_mark_counter}", bar, length, calc_trace, "curtailed"
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate top extra left bars
        for bar in self.input.top_extra_left_bars:
            length, calc_trace = calculate_beam_extra_bar_length(
                bar, self.input.clear_span, self.input.concrete_grade, self.input.steel_grade
            )
            
            entry = self._create_bbs_entry(
                f"EL{bar_mark_counter}", bar, length, calc_trace, "extra_left"
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate top extra right bars
        for bar in self.input.top_extra_right_bars:
            length, calc_trace = calculate_beam_extra_bar_length(
                bar, self.input.clear_span, self.input.concrete_grade, self.input.steel_grade
            )
            
            entry = self._create_bbs_entry(
                f"ER{bar_mark_counter}", bar, length, calc_trace, "extra_right"
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate stirrups for each zone
        for zone_name, stirrup_zone in [
            ("left", self.input.left_stirrup_zone),
            ("middle", self.input.middle_stirrup_zone), 
            ("right", self.input.right_stirrup_zone)
        ]:
            if stirrup_zone:
                length, length_trace = calculate_stirrup_cutting_length(
                    stirrup_zone, self.input.beam_width, self.input.beam_depth
                )
                quantity, qty_trace = calculate_stirrup_quantity(
                    stirrup_zone.zone_length, stirrup_zone.spacing, 
                    stirrup_zone.quantity_source, stirrup_zone.specified_quantity
                )
                
                entry = BBSEntry(
                    bar_mark=f"S{zone_name[0].upper()}{bar_mark_counter}",
                    member_id=self.input.beam_mark,
                    diameter=stirrup_zone.diameter,
                    number_of_bars=quantity,
                    length_of_each_bar=length,
                    total_length=length * quantity,
                    unit_weight=unit_weight_kg_per_m(stirrup_zone.diameter),
                    total_weight=(length * quantity / 1000) * unit_weight_kg_per_m(stirrup_zone.diameter),
                    shape_code="R",
                    bending_details={
                        'zone': zone_name,
                        'spacing_mm': stirrup_zone.spacing,
                        'legs': stirrup_zone.number_of_legs
                    },
                    calculation_trace={
                        'length_calculation': length_trace,
                        'quantity_calculation': qty_trace
                    }
                )
                self.entries.append(entry)
                bar_mark_counter += 1
                
        return self._generate_summary()
        
    def _create_bbs_entry(self, bar_mark: str, bar, length: float, calc_trace: Dict, bar_type: str) -> BBSEntry:
        """Create BBS entry from bar data"""
        total_bars = bar.number_of_bars * self.input.number_of_units
        
        return BBSEntry(
            bar_mark=bar_mark,
            member_id=self.input.beam_mark,
            diameter=bar.diameter,
            number_of_bars=total_bars,
            length_of_each_bar=length,
            total_length=length * total_bars,
            unit_weight=unit_weight_kg_per_m(bar.diameter),
            total_weight=(length * total_bars / 1000) * unit_weight_kg_per_m(bar.diameter),
            shape_code=getattr(bar, 'bend_shape', 'I'),
            bending_details={
                'bar_type': bar_type,
                'original_bar_mark': bar.bar_mark,
                'remarks': getattr(bar, 'remarks', '')
            },
            calculation_trace=calc_trace
        )
        
    def _generate_summary(self) -> BBSCalculationResult:
        """Generate beam BBS summary"""
        diameter_summary = {}
        total_weight = 0
        
        for entry in self.entries:
            dia = entry.diameter
            if dia not in diameter_summary:
                diameter_summary[dia] = {'total_length': 0, 'total_weight': 0, 'count': 0}
                
            diameter_summary[dia]['total_length'] += entry.total_length
            diameter_summary[dia]['total_weight'] += entry.total_weight
            diameter_summary[dia]['count'] += entry.number_of_bars
            total_weight += entry.total_weight
            
        return BBSCalculationResult(
            entries=self.entries,
            diameter_summary=diameter_summary,
            grand_total_weight=total_weight,
            calculation_metadata={
                'member_type': MemberType.BEAM.value,
                'member_id': self.input.beam_mark,
                'calculation_method': 'IS_456_2000_COMPLETE',
                'project': self.input.project,
                'clear_span_mm': self.input.clear_span
            },
            member_summaries={
                self.input.beam_mark: {
                    'total_weight': total_weight,
                    'bar_count': len(self.entries)
                }
            }
        )
        self.input = beam_input
        self.entries: List[BBSEntry] = []
        
    def calculate_main_bar_length(self, bar_config: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Calculate main reinforcement bar length with hooks and development length"""
        diameter = bar_config['diameter']
        
        # Basic bar length
        basic_length = self.input.length
        
        # Development length calculation
        dev_length = calculate_development_length_is456(
            diameter, self.input.concrete_grade, self.input.steel_grade
        )
        
        # Hook lengths (IS 2502)
        hook_length = 9 * diameter  # Standard 90° hook
        
        # Total length calculation
        total_length = basic_length + 2 * max(dev_length, hook_length)
        
        calculation_trace = {
            'basic_length_mm': basic_length,
            'development_length_mm': dev_length,
            'hook_length_mm': hook_length,
            'extension_each_end_mm': max(dev_length, hook_length),
            'total_length_mm': total_length,
            'formula': 'L_total = L_basic + 2 × max(L_dev, L_hook)'
        }
        
        return total_length, calculation_trace
        
    def calculate_stirrup_length(self, zone: StirrupZone) -> Tuple[float, Dict[str, Any]]:
        """Calculate stirrup length with hooks"""
        # Stirrup perimeter calculation
        stirrup_width = self.input.width - 2 * self.input.clear_cover
        stirrup_depth = self.input.depth - 2 * self.input.clear_cover
        
        # Perimeter + hooks
        perimeter = 2 * (stirrup_width + stirrup_depth)
        hook_allowance = 2 * 10 * zone.diameter  # 2 hooks × 10D each
        
        total_length = perimeter + hook_allowance
        
        calculation_trace = {
            'stirrup_width_mm': stirrup_width,
            'stirrup_depth_mm': stirrup_depth,
            'perimeter_mm': perimeter,
            'hook_allowance_mm': hook_allowance,
            'total_length_mm': total_length,
            'formula': 'L = 2(w + d) + 2×10D'
        }
        
        return total_length, calculation_trace
        
    def calculate_number_of_stirrups(self, zone: StirrupZone) -> Tuple[int, Dict[str, Any]]:
        """Calculate number of stirrups in zone"""
        zone_length = zone.end_distance - zone.start_distance
        number = math.ceil(zone_length / zone.spacing) + 1  # +1 for end stirrup
        
        calculation_trace = {
            'zone_length_mm': zone_length,
            'spacing_mm': zone.spacing,
            'number_calculated': zone_length / zone.spacing + 1,
            'number_actual': number,
            'formula': 'N = ceil(L_zone / spacing) + 1'
        }
        
        return number, calculation_trace
        
class CompleteColumnBBSCalculator:
    """Professional column BBS calculations with level-wise reductions and all tie types"""
    
    def __init__(self, column_input: CompleteColumnInput):
        self.input = column_input
        self.entries: List[BBSEntry] = []
        
    def calculate_bbs(self) -> BBSCalculationResult:
        """Generate complete unified BBS for column with all components"""
        self.entries = []
        bar_mark_counter = 1
        
        # Calculate main vertical bars
        for bar in self.input.main_vertical_bars:
            length, calc_trace = calculate_column_main_bar_length(
                bar, self.input.clear_floor_height, 
                self.input.concrete_grade, self.input.steel_grade,
                self.input.reduction_levels
            )
            
            # Calculate effective number of bars considering reductions
            effective_bars = self._calculate_effective_bar_count(bar, self.input.reduction_levels)
            
            entry = BBSEntry(
                bar_mark=f"M{bar_mark_counter}",
                member_id=self.input.column_mark,
                diameter=bar.diameter,
                number_of_bars=effective_bars * self.input.number_of_units,
                length_of_each_bar=length,
                total_length=length * effective_bars * self.input.number_of_units,
                unit_weight=unit_weight_kg_per_m(bar.diameter),
                total_weight=(length * effective_bars * self.input.number_of_units / 1000) * unit_weight_kg_per_m(bar.diameter),
                shape_code="I",
                bending_details={
                    'bar_type': 'main_vertical',
                    'original_bar_mark': bar.bar_mark,
                    'description': bar.description,
                    'lap_condition': bar.lap_condition.value,
                    'remarks': bar.remarks
                },
                calculation_trace=calc_trace
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate master stirrups
        for stirrup in self.input.master_stirrups:
            length, length_trace = self._calculate_master_stirrup_length(stirrup)
            eff_zone_length = stirrup.zone_length if stirrup.zone_length > 0 else self.input.clear_floor_height
            quantity, qty_trace = calculate_stirrup_quantity(
                eff_zone_length, stirrup.spacing,
                stirrup.quantity_source, stirrup.specified_quantity
            )
            
            entry = BBSEntry(
                bar_mark=f"MS{bar_mark_counter}",
                member_id=self.input.column_mark,
                diameter=stirrup.diameter,
                number_of_bars=quantity * self.input.number_of_units,
                length_of_each_bar=length,
                total_length=length * quantity * self.input.number_of_units,
                unit_weight=unit_weight_kg_per_m(stirrup.diameter),
                total_weight=(length * quantity * self.input.number_of_units / 1000) * unit_weight_kg_per_m(stirrup.diameter),
                shape_code="R",
                bending_details={
                    'tie_type': 'master_stirrup',
                    'link_mark': stirrup.link_mark,
                    'description': stirrup.description,
                    'zone': stirrup.zone,
                    'spacing_mm': stirrup.spacing,
                    'legs': stirrup.number_of_legs
                },
                calculation_trace={
                    'length_calculation': length_trace,
                    'quantity_calculation': qty_trace
                }
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate short links
        for link in self.input.short_links:
            # Derive link dimensions from column if not explicitly set
            if link.link_width is None:
                link.link_width = self.input.column_width - 2 * link.cover - link.diameter
            if link.link_depth is None:
                link.link_depth = self.input.column_depth - 2 * link.cover - link.diameter
            eff_zone_length = link.zone_length if link.zone_length > 0 else self.input.clear_floor_height
            length, length_trace = calculate_link_cutting_length(
                link, self.input.column_width, self.input.column_depth
            )
            quantity, qty_trace = calculate_stirrup_quantity(
                eff_zone_length, link.spacing,
                link.quantity_source, link.specified_quantity
            )
            
            entry = BBSEntry(
                bar_mark=f"SL{bar_mark_counter}",
                member_id=self.input.column_mark,
                diameter=link.diameter,
                number_of_bars=quantity * link.number_per_set * self.input.number_of_units,
                length_of_each_bar=length,
                total_length=length * quantity * link.number_per_set * self.input.number_of_units,
                unit_weight=unit_weight_kg_per_m(link.diameter),
                total_weight=(length * quantity * link.number_per_set * self.input.number_of_units / 1000) * unit_weight_kg_per_m(link.diameter),
                shape_code="U",
                bending_details={
                    'tie_type': 'short_link',
                    'link_mark': link.link_mark,
                    'description': link.description,
                    'zone': link.zone,
                    'spacing_mm': link.spacing,
                    'per_set': link.number_per_set
                },
                calculation_trace={
                    'length_calculation': length_trace,
                    'quantity_calculation': qty_trace
                }
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate long links
        for link in self.input.long_links:
            # Derive link dimensions from column if not explicitly set
            if link.link_width is None:
                link.link_width = self.input.column_width - 2 * link.cover - link.diameter
            if link.link_depth is None:
                link.link_depth = self.input.column_depth - 2 * link.cover - link.diameter
            eff_zone_length = link.zone_length if link.zone_length > 0 else self.input.clear_floor_height
            length, length_trace = calculate_link_cutting_length(
                link, self.input.column_width, self.input.column_depth
            )
            quantity, qty_trace = calculate_stirrup_quantity(
                eff_zone_length, link.spacing,
                link.quantity_source, link.specified_quantity
            )
            
            entry = BBSEntry(
                bar_mark=f"LL{bar_mark_counter}",
                member_id=self.input.column_mark,
                diameter=link.diameter,
                number_of_bars=quantity * link.number_per_set * self.input.number_of_units,
                length_of_each_bar=length,
                total_length=length * quantity * link.number_per_set * self.input.number_of_units,
                unit_weight=unit_weight_kg_per_m(link.diameter),
                total_weight=(length * quantity * link.number_per_set * self.input.number_of_units / 1000) * unit_weight_kg_per_m(link.diameter),
                shape_code="U",
                bending_details={
                    'tie_type': 'long_link',
                    'link_mark': link.link_mark,
                    'description': link.description,
                    'zone': link.zone,
                    'spacing_mm': link.spacing,
                    'per_set': link.number_per_set
                },
                calculation_trace={
                    'length_calculation': length_trace,
                    'quantity_calculation': qty_trace
                }
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        # Calculate cross ties
        for tie in self.input.cross_ties:
            length, length_trace = calculate_cross_tie_cutting_length(tie)
            quantity, qty_trace = calculate_stirrup_quantity(
                tie.zone_length, tie.spacing,
                tie.quantity_source, tie.specified_quantity
            )
            
            entry = BBSEntry(
                bar_mark=f"CT{bar_mark_counter}",
                member_id=self.input.column_mark,
                diameter=tie.diameter,
                number_of_bars=quantity * tie.number_per_set * self.input.number_of_units,
                length_of_each_bar=length,
                total_length=length * quantity * tie.number_per_set * self.input.number_of_units,
                unit_weight=unit_weight_kg_per_m(tie.diameter),
                total_weight=(length * quantity * tie.number_per_set * self.input.number_of_units / 1000) * unit_weight_kg_per_m(tie.diameter),
                shape_code="X",
                bending_details={
                    'tie_type': 'cross_tie',
                    'link_mark': tie.link_mark,
                    'description': tie.description,
                    'zone': tie.zone,
                    'spacing_mm': tie.spacing,
                    'per_set': tie.number_per_set
                },
                calculation_trace={
                    'length_calculation': length_trace,
                    'quantity_calculation': qty_trace
                }
            )
            self.entries.append(entry)
            bar_mark_counter += 1
            
        return self._generate_unified_summary()
        
    def _calculate_effective_bar_count(self, bar: ColumnMainBar, reduction_levels: List[ColumnReductionLevel]) -> int:
        """Calculate effective bar count considering reductions"""
        base_count = bar.number_of_bars
        
        for level in reduction_levels:
            if bar.bar_mark in level.bars_to_reduce:
                # Apply reduction
                reduction_factor = 1 - (level.reduction_percentage / 100)
                base_count = int(base_count * reduction_factor)
                
        return base_count
        
    def _calculate_master_stirrup_length(self, stirrup: MasterStirrup) -> Tuple[float, Dict[str, Any]]:
        """Calculate master stirrup cutting length"""
        # Derive column dimensions from parent input if not set on the stirrup itself
        col_w = stirrup.column_width if stirrup.column_width is not None else self.input.column_width
        col_d = stirrup.column_depth if stirrup.column_depth is not None else self.input.column_depth
        # Get effective dimensions
        eff_width, eff_depth, dim_trace = calculate_effective_stirrup_dimensions(
            col_w, col_d,
            stirrup.cover, stirrup.diameter, stirrup.dimension_convention
        )
        
        # Calculate perimeter
        if stirrup.shape.lower() == "rectangular":
            perimeter = 2 * (eff_width + eff_depth)
        elif stirrup.shape.lower() == "circular":
            perimeter = math.pi * eff_width  # Assuming width = diameter for circular
        else:
            perimeter = 2 * (eff_width + eff_depth)  # Default to rectangular
            
        # Hook allowances
        hook_allowance = calculate_hook_allowance(stirrup.diameter, stirrup.hook_type, stirrup.hook_extension)
        total_hook_allowance = hook_allowance * 2
        
        # Bend deductions
        num_bends = 4 if stirrup.shape.lower() == "rectangular" else 0
        bend_deduction = num_bends * 2 * stirrup.diameter
        
        cutting_length = perimeter + total_hook_allowance - bend_deduction
        
        calculation_trace = {
            'stirrup_mark': stirrup.link_mark,
            'diameter_mm': stirrup.diameter,
            'shape': stirrup.shape,
            'dimension_calculation': dim_trace,
            'geometry_calculation': {
                'effective_width_mm': eff_width,
                'effective_depth_mm': eff_depth,
                'perimeter_mm': perimeter,
                'perimeter_formula': f'2 × (width + depth)' if stirrup.shape.lower() == "rectangular" else 'π × diameter'
            },
            'allowances_deductions': {
                'hook_allowance_each_mm': hook_allowance,
                'total_hook_allowance_mm': total_hook_allowance,
                'bend_deduction_mm': bend_deduction,
                'num_bends': num_bends
            },
            'final_calculation': {
                'formula': 'CL = Perimeter + Hook Allowances - Bend Deductions',
                'calculation': f'{perimeter} + {total_hook_allowance} - {bend_deduction} = {cutting_length}',
                'cutting_length_mm': cutting_length
            }
        }
        
        return cutting_length, calculation_trace
        
    def _generate_unified_summary(self) -> BBSCalculationResult:
        """Generate unified column BBS summary"""
        diameter_summary = {}
        total_weight = 0
        
        # Categorize by reinforcement type
        main_bar_weight = 0
        tie_weight = 0
        
        for entry in self.entries:
            dia = entry.diameter
            if dia not in diameter_summary:
                diameter_summary[dia] = {'total_length': 0, 'total_weight': 0, 'count': 0}
                
            diameter_summary[dia]['total_length'] += entry.total_length
            diameter_summary[dia]['total_weight'] += entry.total_weight
            diameter_summary[dia]['count'] += entry.number_of_bars
            total_weight += entry.total_weight
            
            # Categorize weight
            if entry.bending_details.get('bar_type') == 'main_vertical':
                main_bar_weight += entry.total_weight
            else:
                tie_weight += entry.total_weight
                
        return BBSCalculationResult(
            entries=self.entries,
            diameter_summary=diameter_summary,
            grand_total_weight=total_weight,
            calculation_metadata={
                'member_type': MemberType.COLUMN.value,
                'member_id': self.input.column_mark,
                'calculation_method': 'IS_456_2000_UNIFIED_COLUMN',
                'project': self.input.project,
                'clear_floor_height_mm': self.input.clear_floor_height,
                'main_bar_weight_kg': main_bar_weight,
                'tie_weight_kg': tie_weight,
                'reduction_levels': len(self.input.reduction_levels)
            },
            member_summaries={
                self.input.column_mark: {
                    'total_weight': total_weight,
                    'main_bar_weight': main_bar_weight,
                    'tie_weight': tie_weight,
                    'bar_count': len(self.entries)
                }
            }
        )
    """Professional column BBS calculations with level reductions"""
    
    def __init__(self, column_input: CompleteColumnInput):
        self.input = column_input
        self.entries: List[BBSEntry] = []
        
    def calculate_main_bar_length(self, bar_config: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Calculate main reinforcement bar length with reductions"""
        diameter = bar_config['diameter']
        
        # Base length
        base_length = self.input.height
        
        # Apply reductions
        effective_length = base_length
        applied_reductions = []
        
        for reduction in self.input.reductions:
            if bar_config.get('mark', '') in reduction.bars_to_reduce:
                reduction_length = reduction.end_height - reduction.start_height
                reduction_amount = reduction_length * (reduction.reduction_percentage / 100)
                effective_length -= reduction_amount
                
                applied_reductions.append({
                    'level': reduction.level_name,
                    'percentage': reduction.reduction_percentage,
                    'reduced_length_mm': reduction_amount
                })
                
        # Development length
        dev_length = calculate_development_length_is456(
            diameter, self.input.concrete_grade, self.input.steel_grade
        )
        
        # Lap length if required
        lap_length = calculate_lap_length(
            diameter, self.input.lap_method, self.input.custom_lap_factor,
            self.input.concrete_grade, self.input.steel_grade
        )
        
        # Total length with extensions
        total_length = effective_length + 2 * dev_length + lap_length
        
        calculation_trace = {
            'base_length_mm': base_length,
            'effective_length_mm': effective_length,
            'development_length_mm': dev_length,
            'lap_length_mm': lap_length,
            'total_length_mm': total_length,
            'reductions_applied': applied_reductions,
            'formula': 'L = L_effective + 2×L_dev + L_lap'
        }
        
        return total_length, calculation_trace
        
class ManualBBSEngine:
    """Main engine for Complete Manual BBS calculations"""
    
    def __init__(self):
        self.calculators = {
            MemberType.BEAM: CompleteBeamBBSCalculator,
            MemberType.COLUMN: CompleteColumnBBSCalculator
        }
        
    def calculate_member_bbs(
        self, 
        member_type: MemberType,
        member_input: Union[CompleteBeamInput, CompleteColumnInput]
    ) -> BBSCalculationResult:
        """Calculate BBS for a single member with complete specification compliance"""
        calculator_class = self.calculators[member_type]
        calculator = calculator_class(member_input)
        return calculator.calculate_bbs()
        
    def calculate_project_bbs(
        self, 
        members: List[Union[CompleteBeamInput, CompleteColumnInput]]
    ) -> Dict[str, BBSCalculationResult]:
        """Calculate BBS for multiple members with full traceability"""
        results = {}
        
        for member in members:
            if isinstance(member, CompleteBeamInput):
                member_type = MemberType.BEAM
                member_id = member.beam_mark
            elif isinstance(member, CompleteColumnInput):
                member_type = MemberType.COLUMN
                member_id = member.column_mark
            else:
                raise ValueError(f"Unsupported member type: {type(member)}")
                
            result = self.calculate_member_bbs(member_type, member)
            results[member_id] = result
            
        return results
        
    def generate_unified_bbs(
        self, 
        member_results: Dict[str, BBSCalculationResult]
    ) -> BBSCalculationResult:
        """Combine multiple member BBS into unified professional table"""
        all_entries = []
        combined_diameter_summary = {}
        grand_total = 0
        member_summaries = {}
        
        # Combine all entries with proper sorting
        for member_id, result in member_results.items():
            all_entries.extend(result.entries)
            member_summaries[member_id] = result.member_summaries[member_id]
            
            # Combine diameter summaries
            for dia, summary in result.diameter_summary.items():
                if dia not in combined_diameter_summary:
                    combined_diameter_summary[dia] = {'total_length': 0, 'total_weight': 0, 'count': 0}
                    
                combined_diameter_summary[dia]['total_length'] += summary['total_length']
                combined_diameter_summary[dia]['total_weight'] += summary['total_weight']  
                combined_diameter_summary[dia]['count'] += summary['count']
                
            grand_total += result.grand_total_weight
            
        # Sort entries by member type, then by bar mark
        all_entries.sort(key=lambda x: (x.member_id, x.bar_mark))
            
        return BBSCalculationResult(
            entries=all_entries,
            diameter_summary=combined_diameter_summary,
            grand_total_weight=grand_total,
            calculation_metadata={
                'member_count': len(member_results),
                'calculation_method': 'IS_456_2000_UNIFIED_PROJECT',
                'calculation_date': datetime.now().isoformat(),
                'members': list(member_results.keys()),
                'total_main_bars': len([e for e in all_entries if 'main' in e.bending_details.get('bar_type', '')]),
                'total_ties_stirrups': len([e for e in all_entries if 'tie' in e.bending_details.get('tie_type', '') or 'stirrup' in e.bending_details.get('tie_type', '')])
            },
            member_summaries=member_summaries
        )


# ══════════════════════════════════════════════════════
# EXPORT FUNCTIONS FOR API INTEGRATION
# ══════════════════════════════════════════════════════

def create_complete_beam_bbs(beam_data: Dict[str, Any]) -> BBSCalculationResult:
    """Create BBS for beam member with complete specification compliance"""
    beam_input = CompleteBeamInput(**beam_data)
    engine = ManualBBSEngine()
    return engine.calculate_member_bbs(MemberType.BEAM, beam_input)


def create_complete_column_bbs(column_data: Dict[str, Any]) -> BBSCalculationResult:
    """Create unified BBS for column member with all tie types"""
    column_input = CompleteColumnInput(**column_data)
    engine = ManualBBSEngine()
    return engine.calculate_member_bbs(MemberType.COLUMN, column_input)


def create_complete_project_bbs(members: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create unified BBS for project with complete specification compliance"""
    engine = ManualBBSEngine()
    
    # Parse member inputs
    parsed_members = []
    for member_data in members:
        member_type = member_data.get('member_type', member_data.get('type'))
        if member_type == 'BEAM' or member_type == MemberType.BEAM:
            parsed_members.append(CompleteBeamInput(**member_data))
        elif member_type == 'COLUMN' or member_type == MemberType.COLUMN:
            parsed_members.append(CompleteColumnInput(**member_data))
        else:
            raise ValueError(f"Unknown member type: {member_type}")
    
    member_results = engine.calculate_project_bbs(parsed_members)
    unified_result = engine.generate_unified_bbs(member_results)
    
    return {
        'unified_bbs': unified_result,
        'member_results': member_results,
        'summary': {
            'total_members': len(members),
            'total_weight_kg': unified_result.grand_total_weight,
            'diameter_breakdown': unified_result.diameter_summary,
            'calculation_metadata': unified_result.calculation_metadata
        }
    }


# Legacy compatibility functions (preserve existing Beam BBS)
def create_beam_bbs(beam_data: Dict[str, Any]) -> BBSCalculationResult:
    """Legacy beam BBS function for backward compatibility"""
    # Try to use existing simple beam format first
    try:
        from .bbs_engine import BeamBarInput, calc_beam_bar
        # Use existing simple calculation if possible
        return create_complete_beam_bbs(beam_data)
    except Exception:
        # Fall back to complete system
        return create_complete_beam_bbs(beam_data)


def create_column_bbs(column_data: Dict[str, Any]) -> BBSCalculationResult:
    """Legacy column BBS function for backward compatibility"""  
    return create_complete_column_bbs(column_data)


def create_project_bbs(members: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Legacy project BBS function for backward compatibility"""
    return create_complete_project_bbs(members)