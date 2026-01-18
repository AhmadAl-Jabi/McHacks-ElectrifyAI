"""
Negative validation tests.

Tests that validation correctly rejects invalid commands:
- Invalid pins
- Refdes collisions with snapshot
- set_value forbidden for parts that don't allow it
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.domain import (
    CommandsDoc,
    SnapshotDoc,
    SnapshotComponent,
    AddComponentCmd,
    AddComponentArgs,
    ConnectCmd,
    ConnectArgs,
    SetValueCmd,
    SetValueArgs,
)
from src.ecop_schematic_copilot.compile import validate_commands


def test_validate_invalid_pin():
    """Test that validation rejects invalid pin references."""
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],  # Only pins 1 and 2
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    commands = CommandsDoc(
        commands=[
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R1")),
            # Try to connect to invalid pin "3"
            ConnectCmd(args=ConnectArgs(refdes="R1", pin="3", net_name="NET1")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=None,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for invalid pin"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions invalid pin
    error_text = " ".join(result.errors).lower()
    assert "pin" in error_text, "Error should mention pin issue"
    assert "3" in error_text, "Error should mention pin '3'"
    
    print("✓ test_validate_invalid_pin PASSED")


def test_validate_refdes_collision_snapshot():
    """Test that validation rejects refdes that already exists in snapshot."""
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    snapshot = SnapshotDoc(
        components=[
            SnapshotComponent(refdes="R1", part_id="resistor_0603", pins=["1", "2"]),
        ],
        nets=[],
    )
    
    commands = CommandsDoc(
        commands=[
            # Try to add component with same refdes as existing
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R1")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=snapshot,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for refdes collision"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions collision
    error_text = " ".join(result.errors).lower()
    assert "r1" in error_text, "Error should mention refdes 'R1'"
    assert ("collision" in error_text or "already exists" in error_text or "duplicates" in error_text), \
        "Error should mention collision or duplication"
    
    print("✓ test_validate_refdes_collision_snapshot PASSED")


def test_validate_set_value_forbidden():
    """Test that validation rejects set_value for parts that don't allow it."""
    catalog_parts = {
        "tvs_diode": {
            "catalog_id": "tvs_diode",
            "kind": "diode",
            "pins": ["A", "K"],
            "set_value": False,  # Does NOT allow set_value
            "fusion_add": "ADD 'tvs_diode' D",
        },
    }
    
    commands = CommandsDoc(
        commands=[
            AddComponentCmd(args=AddComponentArgs(part_id="tvs_diode", refdes="D1")),
            # Try to set value on component that doesn't allow it
            SetValueCmd(args=SetValueArgs(refdes="D1", value="3.3V")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=None,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for forbidden set_value"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions set_value issue
    error_text = " ".join(result.errors).lower()
    assert "set_value" in error_text, "Error should mention set_value"
    assert ("not allowed" in error_text or "forbidden" in error_text), \
        "Error should indicate set_value is not allowed"
    
    print("✓ test_validate_set_value_forbidden PASSED")


def test_validate_refdes_duplicate_in_commands():
    """Test that validation rejects duplicate refdes within commands."""
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    commands = CommandsDoc(
        commands=[
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R1")),
            # Try to add another component with same refdes
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R1")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=None,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for duplicate refdes in commands"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions duplicate
    error_text = " ".join(result.errors).lower()
    assert "r1" in error_text, "Error should mention refdes 'R1'"
    assert "duplicate" in error_text, "Error should mention duplicate"
    
    print("✓ test_validate_refdes_duplicate_in_commands PASSED")


def test_validate_missing_part_id():
    """Test that validation rejects part_id not in catalog."""
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    commands = CommandsDoc(
        commands=[
            # Try to add component with part_id not in catalog
            AddComponentCmd(args=AddComponentArgs(part_id="nonexistent_part", refdes="U1")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=None,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for missing part_id"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions missing part
    error_text = " ".join(result.errors).lower()
    assert "nonexistent_part" in error_text, "Error should mention missing part_id"
    assert ("not found" in error_text or "does not exist" in error_text), \
        "Error should indicate part_id doesn't exist"
    
    print("✓ test_validate_missing_part_id PASSED")


def test_validate_connect_nonexistent_refdes():
    """Test that validation rejects connect to non-existent refdes."""
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    commands = CommandsDoc(
        commands=[
            # Try to connect to refdes that doesn't exist
            ConnectCmd(args=ConnectArgs(refdes="R99", pin="1", net_name="NET1")),
        ]
    )
    
    result = validate_commands(
        doc=commands,
        parts_by_id=catalog_parts,
        snapshot=None,
    )
    
    # Should fail validation
    assert not result.ok, "Validation should fail for non-existent refdes"
    assert len(result.errors) > 0, "Should have at least one error"
    
    # Check error message mentions missing refdes
    error_text = " ".join(result.errors).lower()
    assert "r99" in error_text, "Error should mention refdes 'R99'"
    assert "does not exist" in error_text, "Error should indicate refdes doesn't exist"
    
    print("✓ test_validate_connect_nonexistent_refdes PASSED")


if __name__ == "__main__":
    test_validate_invalid_pin()
    test_validate_refdes_collision_snapshot()
    test_validate_set_value_forbidden()
    test_validate_refdes_duplicate_in_commands()
    test_validate_missing_part_id()
    test_validate_connect_nonexistent_refdes()
    print("\n✓ All validation tests passed!")
