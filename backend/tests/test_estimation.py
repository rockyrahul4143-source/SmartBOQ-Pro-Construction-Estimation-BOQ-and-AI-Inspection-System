"""Quantity Estimation Engine unit tests — no DB required."""
import pytest
from app.services.estimation_engine import (
    calc_excavation, calc_pcc, calc_rcc_footing,
    calc_rcc_column, calc_rcc_beam, calc_rcc_slab,
    calc_brickwork, calc_blockwork,
    calc_plaster_external, calc_plaster_internal,
    calc_flooring, calc_paint, calc_waterproofing,
    calc_total_steel, calc_openings,
)


class TestExcavation:
    def test_basic_volume(self):
        r = calc_excavation(10.0, 8.0, 1.5)
        # (10+0.6) × (8+0.6) × 1.5
        expected = round(10.6 * 8.6 * 1.5, 3)
        assert r.volume_m3 == expected

    def test_zero_slope(self):
        r = calc_excavation(10.0, 8.0, 1.5, slope_allowance=0)
        assert r.volume_m3 == round(10.0 * 8.0 * 1.5, 3)

    def test_positive_volume(self):
        r = calc_excavation(5.0, 4.0, 2.0)
        assert r.volume_m3 > 0


class TestPCC:
    def test_volume(self):
        r = calc_pcc(10.0, 8.0, 0.075)
        assert r.volume_m3 == round(10.0 * 8.0 * 0.075, 3)

    def test_materials_not_zero(self):
        r = calc_pcc(10.0, 8.0, 0.075)
        assert r.cement_bags > 0
        assert r.sand_cft > 0
        assert r.aggregate_cft > 0

    def test_m10_mix(self):
        r = calc_pcc(1.0, 1.0, 1.0, mix="M10")
        # DRY_VOLUME_FACTOR=1.54, M10=(1,3,6), total=10
        # cement_bags = (1.54 * 1/10 * 1440) / 50 ≈ 4.44
        assert abs(r.cement_bags - 4.44) < 0.1


class TestRCCSlab:
    def test_volume(self):
        r = calc_rcc_slab(10.0, 8.0, 0.125, num_floors=1)
        assert r.volume_m3 == round(10.0 * 8.0 * 0.125, 3)

    def test_multi_floor(self):
        r1 = calc_rcc_slab(10.0, 8.0, 0.125, num_floors=1)
        r3 = calc_rcc_slab(10.0, 8.0, 0.125, num_floors=3)
        assert abs(r3.volume_m3 - 3 * r1.volume_m3) < 0.001

    def test_steel_calculated(self):
        r = calc_rcc_slab(10.0, 8.0, 0.125, steel_pct=1.0)
        # steel_kg = volume * 7850 * 0.01
        expected = round(r.volume_m3 * 7850 * 1.0 / 100, 2)
        assert r.steel_kg == expected


class TestRCCColumn:
    def test_multi_floor_height(self):
        r = calc_rcc_column(0.3, 0.3, 3.0, num_columns=4, num_floors=2)
        vol = round(0.3 * 0.3 * 3.0 * 2 * 4, 3)
        assert r.volume_m3 == vol


class TestBrickwork:
    def test_gross_volume(self):
        r = calc_brickwork(20.0, 3.0, 0.23, num_floors=1)
        assert r.volume_m3 == round(20.0 * 3.0 * 0.23, 3)

    def test_deducts_openings(self):
        no_openings = calc_brickwork(20.0, 3.0, 0.23, num_doors=0, num_windows=0)
        with_openings = calc_brickwork(20.0, 3.0, 0.23, num_doors=2, door_width=0.9, door_height=2.1)
        assert with_openings.volume_m3 < no_openings.volume_m3

    def test_bricks_count_positive(self):
        r = calc_brickwork(10.0, 3.0, 0.23)
        assert r.bricks_nos > 0


class TestPlaster:
    def test_external_area(self):
        r = calc_plaster_external(20.0, 3.0, thickness=0.020)
        assert r.area_m2 == round(20.0 * 3.0, 3)

    def test_internal_cement_bags(self):
        r = calc_plaster_internal(20.0, 3.0, thickness=0.012)
        assert r.cement_bags > 0
        assert r.sand_cft > 0


class TestFlooring:
    def test_tile_count_with_wastage(self):
        r = calc_flooring(10.0, 8.0, tile_size=0.6, wastage_pct=10.0)
        area_with_waste = 10.0 * 8.0 * 1.10
        import math
        expected_tiles = math.ceil(area_with_waste / (0.6 * 0.6))
        assert r.tiles_nos == expected_tiles

    def test_net_area(self):
        r = calc_flooring(10.0, 5.0)
        assert r.area_m2 == 50.0


class TestPaint:
    def test_litres_calculated(self):
        r = calc_paint(100.0, 0.0, coats=2)
        # (100 * (2+1)) / 10 = 30
        assert r.paint_litres == 30.0

    def test_includes_ceiling(self):
        r = calc_paint(100.0, ceiling_area_m2=50.0, coats=2)
        assert r.area_m2 == 150.0


class TestWaterproofing:
    def test_compound_kg(self):
        r = calc_waterproofing(100.0)
        # 1.5 kg/m²
        assert r.compound_kg == 150.0


class TestSteelSummary:
    def test_total_across_elements(self):
        r = calc_total_steel(
            slab_vol_m3=10.0, slab_pct=1.0,
            column_vol_m3=2.0, column_pct=2.5,
            beam_vol_m3=1.5, beam_pct=2.0,
        )
        expected = (10.0 * 7850 * 0.01 + 2.0 * 7850 * 0.025 + 1.5 * 7850 * 0.02)
        assert abs(r.steel_kg - round(expected, 2)) < 0.01
        assert r.steel_tons == round(r.steel_kg / 1000, 3)


class TestOpenings:
    def test_door_area(self):
        r = calc_openings(3, 0.9, 2.1, 4, 1.2, 1.2)
        assert r["doors"].total_area_m2 == round(3 * 0.9 * 2.1, 3)
        assert r["windows"].total_area_m2 == round(4 * 1.2 * 1.2, 3)

    def test_zero_openings(self):
        r = calc_openings(0, 0.9, 2.1, 0, 1.2, 1.2)
        assert r["doors"].count == 0
        assert r["windows"].count == 0
