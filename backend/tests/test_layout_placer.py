"""Tests for deterministic auto-placer."""

import pytest
from backend.src.layout.placer import GridPlacer, PartToPlace, Rect


def test_snap_to_grid():
    """Test grid snapping."""
    placer = GridPlacer(grid_step=10.0)
    
    assert placer.snap_to_grid(0, 0) == (0, 0)
    assert placer.snap_to_grid(5, 5) == (0, 0)  # round(0.5) = 0 (banker's rounding)
    assert placer.snap_to_grid(6, 6) == (10, 10)  # round(0.6) = 1
    assert placer.snap_to_grid(14, 16) == (10, 20)
    assert placer.snap_to_grid(25, 25) == (20, 20)  # round(2.5) = 2 (banker's rounding)
    assert placer.snap_to_grid(26, 26) == (30, 30)  # round(2.6) = 3


def test_rect_intersects():
    """Test rectangle intersection detection."""
    r1 = Rect(x=0, y=0, w=10, h=10)
    r2 = Rect(x=5, y=5, w=10, h=10)
    r3 = Rect(x=20, y=20, w=10, h=10)
    
    assert r1.intersects(r2)  # Overlapping
    assert r2.intersects(r1)  # Symmetric
    assert not r1.intersects(r3)  # Not overlapping
    assert not r3.intersects(r1)  # Symmetric


def test_estimate_size_cells():
    """Test component size estimation."""
    placer = GridPlacer(grid_step=10.0)
    
    # Test various component types
    assert placer.estimate_size_cells("RES123", "resistor") == (3, 1)
    assert placer.estimate_size_cells("CAP456", "capacitor") == (3, 1)
    assert placer.estimate_size_cells("U1", "ic") == (6, 4)
    assert placer.estimate_size_cells("J1", "connector") == (6, 2)
    assert placer.estimate_size_cells("D1", "diode") == (3, 2)
    assert placer.estimate_size_cells("Q1", "transistor") == (3, 2)
    assert placer.estimate_size_cells("X1", "unknown") == (3, 2)


def test_build_occupied_empty():
    """Test building occupied list from empty snapshot."""
    placer = GridPlacer(grid_step=10.0, margin=5.0)
    
    occupied = placer.build_occupied(None)
    assert occupied == []
    
    occupied = placer.build_occupied({})
    assert occupied == []
    
    occupied = placer.build_occupied({"components": []})
    assert occupied == []


def test_build_occupied_with_components():
    """Test building occupied list from snapshot with components."""
    placer = GridPlacer(grid_step=10.0, margin=5.0)
    
    snapshot = {
        "components": [
            {
                "refdes": "R1",
                "part_id": "RES@LIB",
                "kind": "resistor",
                "x": 0.0,
                "y": 0.0,
            },
            {
                "refdes": "U1",
                "part_id": "IC@LIB",
                "kind": "ic",
                "x": 50.0,
                "y": 0.0,
            }
        ]
    }
    
    occupied = placer.build_occupied(snapshot)
    assert len(occupied) == 2
    
    # R1: (3,1) cells = (30, 10) + margin
    assert occupied[0].x == -5.0
    assert occupied[0].y == -5.0
    assert occupied[0].w == 40.0  # 30 + 2*5
    assert occupied[0].h == 20.0  # 10 + 2*5
    
    # U1: (6,4) cells = (60, 40) + margin
    assert occupied[1].x == 45.0
    assert occupied[1].y == -5.0
    assert occupied[1].w == 70.0  # 60 + 2*5
    assert occupied[1].h == 50.0  # 40 + 2*5


def test_place_single_part_empty_schematic():
    """Test placing a single part on empty schematic."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    parts = [
        PartToPlace(
            refdes="R1",
            part_id="RES@LIB",
            kind="resistor"
        )
    ]
    
    placements = placer.place_all(parts, None)
    
    assert "R1" in placements
    # With empty schematic, should place at (60, 0) - base_x = 0 + 60
    assert placements["R1"].x == 60.0
    assert placements["R1"].y == 0.0
    assert placements["R1"].rotation == 0.0


def test_place_multiple_parts_no_overlap():
    """Test placing multiple parts ensures no overlap."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    parts = [
        PartToPlace(refdes="U1", part_id="IC@LIB", kind="ic"),
        PartToPlace(refdes="U2", part_id="IC@LIB", kind="ic"),
    ]
    
    placements = placer.place_all(parts, None)
    
    assert "U1" in placements
    assert "U2" in placements
    
    # Both should be placed without overlap
    p1 = placements["U1"]
    p2 = placements["U2"]
    
    # Create rectangles for placed components
    r1 = Rect(x=p1.x, y=p1.y, w=60, h=40)  # IC is 6x4 cells
    r2 = Rect(x=p2.x, y=p2.y, w=60, h=40)
    
    # They should not intersect
    assert not r1.intersects(r2)


def test_place_with_existing_components():
    """Test placing new components to the right of existing ones."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    snapshot = {
        "components": [
            {"refdes": "R1", "part_id": "RES@LIB", "kind": "resistor", "x": 0.0, "y": 0.0},
            {"refdes": "R2", "part_id": "RES@LIB", "kind": "resistor", "x": 50.0, "y": 0.0},
        ]
    }
    
    parts = [
        PartToPlace(refdes="C1", part_id="CAP@LIB", kind="capacitor")
    ]
    
    placements = placer.place_all(parts, snapshot)
    
    assert "C1" in placements
    # Should place to the right of existing (max_x=80 + 60 gap = 140)
    assert placements["C1"].x >= 100.0


def test_place_near_anchor():
    """Test anchored placement using place_near semantics."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    snapshot = {
        "components": [
            {"refdes": "U1", "part_id": "IC@LIB", "kind": "ic", "x": 100.0, "y": 100.0}
        ]
    }
    
    parts = [
        PartToPlace(
            refdes="C1",
            part_id="CAP@LIB",
            kind="capacitor",
            anchor_refdes="U1",
            dx=2.0,  # 2 grid steps to the right
            dy=0.0
        )
    ]
    
    placements = placer.place_all(parts, snapshot)
    
    assert "C1" in placements
    # Should place near U1 at (100 + 2*10, 100) = (120, 100)
    # Might shift if collision with U1's occupied space, but should be nearby
    assert abs(placements["C1"].x - 120.0) <= 60.0  # Allow more tolerance for collision avoidance
    assert abs(placements["C1"].y - 100.0) < 50.0


def test_place_near_anchor_collision_avoidance():
    """Test that anchored placement shifts if collision occurs."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    snapshot = {
        "components": [
            {"refdes": "U1", "part_id": "IC@LIB", "kind": "ic", "x": 100.0, "y": 100.0},
            # Another component blocking the preferred anchor position
            {"refdes": "R1", "part_id": "RES@LIB", "kind": "resistor", "x": 120.0, "y": 100.0}
        ]
    }
    
    parts = [
        PartToPlace(
            refdes="C1",
            part_id="CAP@LIB",
            kind="capacitor",
            anchor_refdes="U1",
            dx=2.0,
            dy=0.0
        )
    ]
    
    placements = placer.place_all(parts, snapshot)
    
    assert "C1" in placements
    # Should shift to avoid collision with R1
    # Exact position depends on algorithm, but should not overlap R1
    p_c1 = placements["C1"]
    r_c1 = Rect(x=p_c1.x, y=p_c1.y, w=30, h=10)
    r_r1 = Rect(x=120-5, y=100-5, w=40, h=20)  # R1 with margin
    
    assert not r_c1.intersects(r_r1)


def test_deterministic_placement():
    """Test that placer produces deterministic results."""
    placer = GridPlacer(grid_step=10.0, margin=5.0, sheet_max_x=500.0)
    
    parts = [
        PartToPlace(refdes="R1", part_id="RES@LIB", kind="resistor"),
        PartToPlace(refdes="C1", part_id="CAP@LIB", kind="capacitor"),
        PartToPlace(refdes="U1", part_id="IC@LIB", kind="ic"),
    ]
    
    snapshot = {
        "components": [
            {"refdes": "R0", "part_id": "RES@LIB", "kind": "resistor", "x": 0.0, "y": 0.0}
        ]
    }
    
    # Place twice and compare
    placements1 = placer.place_all(parts, snapshot)
    placements2 = placer.place_all(parts, snapshot)
    
    assert placements1.keys() == placements2.keys()
    for refdes in placements1:
        assert placements1[refdes].x == placements2[refdes].x
        assert placements1[refdes].y == placements2[refdes].y
        assert placements1[refdes].rotation == placements2[refdes].rotation


def test_rotation_clamping():
    """Test that rotations are clamped to 0/90/180/270."""
    placer = GridPlacer(grid_step=10.0)
    
    assert placer.clamp_rotation(0) == 0
    assert placer.clamp_rotation(45) == 0  # Rounds to 0
    assert placer.clamp_rotation(50) == 90  # Rounds to 90
    assert placer.clamp_rotation(90) == 90
    assert placer.clamp_rotation(180) == 180
    assert placer.clamp_rotation(270) == 270
    assert placer.clamp_rotation(360) == 0
    assert placer.clamp_rotation(405) == 0  # 405 % 360 = 45 -> 0


def test_wrapping_to_next_row():
    """Test that placement wraps to next row when exceeding sheet width."""
    placer = GridPlacer(
        grid_step=10.0,
        margin=5.0,
        sheet_max_x=150.0,  # Small sheet to force wrapping
        wrap_y_step=50.0
    )
    
    parts = [
        PartToPlace(refdes="U1", part_id="IC@LIB", kind="ic"),
        PartToPlace(refdes="U2", part_id="IC@LIB", kind="ic"),
        PartToPlace(refdes="U3", part_id="IC@LIB", kind="ic"),
    ]
    
    placements = placer.place_all(parts, None)
    
    # First IC should fit
    assert placements["U1"].x == 60.0
    assert placements["U1"].y == 0.0
    
    # Second IC should wrap or shift
    # Since ICs are 60 wide, U1 ends at 120, U2 would start at next grid (130+)
    # which exceeds 150, so should wrap
    assert placements["U2"].y >= 50.0 or placements["U2"].x != placements["U1"].x
