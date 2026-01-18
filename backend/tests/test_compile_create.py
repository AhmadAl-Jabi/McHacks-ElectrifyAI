"""
Test compilation in CREATE mode (no snapshot).

Tests that commands are compiled into actions with proper ordering:
ADD -> SET_VALUE -> PLACE -> CONNECT
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.domain import (
    CommandsDoc,
    AddComponentCmd,
    AddComponentArgs,
    ConnectCmd,
    ConnectArgs,
    SetValueCmd,
    SetValueArgs,
    SnapshotDoc,
)
from src.ecop_schematic_copilot.compile import compile_to_actions


def test_compile_create_basic():
    """Test basic create mode: add components, set values, connect."""
    # ========================================================================
    # SETUP: Minimal catalog
    # ========================================================================
    catalog_parts = {
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "library": "ECOP_Resistor",
            "deviceset": "R_0603",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603@ECOP_Resistor' R",
        },
        "tvs_diode": {
            "catalog_id": "tvs_diode",
            "kind": "diode",
            "library": "ECOP_Diode",
            "deviceset": "TVS",
            "pins": ["A", "K"],
            "set_value": False,
            "fusion_add": "ADD 'tvs_diode@ECOP_Diode' D",
        },
        "can_transceiver": {
            "catalog_id": "can_transceiver",
            "kind": "ic",
            "library": "ECOP_IC_Interface",
            "deviceset": "MCP2551",
            "pins": ["TXD", "RXD", "CANH", "CANL", "VDD", "VSS"],
            "set_value": False,
            "fusion_add": "ADD 'can_transceiver@ECOP_IC_Interface' U",
        },
    }
    
    # ========================================================================
    # COMMANDS: Add components, set values, connect
    # ========================================================================
    commands = CommandsDoc(
        commands=[
            # Add components
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R1")),
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R2")),
            AddComponentCmd(args=AddComponentArgs(part_id="can_transceiver", refdes="U1")),
            
            # Set values
            SetValueCmd(args=SetValueArgs(refdes="R1", value="120")),
            SetValueCmd(args=SetValueArgs(refdes="R2", value="120")),
            
            # Connect
            ConnectCmd(args=ConnectArgs(refdes="U1", pin="CANH", net_name="CANH")),
            ConnectCmd(args=ConnectArgs(refdes="U1", pin="CANL", net_name="CANL")),
            ConnectCmd(args=ConnectArgs(refdes="R1", pin="1", net_name="CANH")),
            ConnectCmd(args=ConnectArgs(refdes="R1", pin="2", net_name="CANL")),
            ConnectCmd(args=ConnectArgs(refdes="U1", pin="VDD", net_name="VDD")),
            ConnectCmd(args=ConnectArgs(refdes="U1", pin="VSS", net_name="GND")),
        ]
    )
    
    # ========================================================================
    # COMPILE
    # ========================================================================
    actions_doc, warnings = compile_to_actions(
        commands=commands,
        catalog_parts=catalog_parts,
        snapshot=None,  # CREATE mode
    )
    
    # ========================================================================
    # ASSERTIONS
    # ========================================================================
    actions = actions_doc.actions
    
    # Should have: 3 ADD + 2 SET_VALUE + 3 PLACE + 6 CONNECT = 14 actions
    assert len(actions) >= 11, f"Expected at least 11 actions, got {len(actions)}"
    
    # Find action type indices
    action_types = [action.type for action in actions]
    
    # Check ordering: ADD before SET_VALUE before PLACE before CONNECT
    first_add = action_types.index("ADD")
    last_add = len(action_types) - 1 - action_types[::-1].index("ADD")
    
    first_set_value = action_types.index("SET_VALUE") if "SET_VALUE" in action_types else -1
    last_set_value = (len(action_types) - 1 - action_types[::-1].index("SET_VALUE")) if "SET_VALUE" in action_types else -1
    
    first_place = action_types.index("PLACE") if "PLACE" in action_types else -1
    last_place = (len(action_types) - 1 - action_types[::-1].index("PLACE")) if "PLACE" in action_types else -1
    
    first_connect = action_types.index("CONNECT") if "CONNECT" in action_types else -1
    
    # ADD must come before SET_VALUE
    if first_set_value >= 0:
        assert last_add < first_set_value, "ADD must come before SET_VALUE"
    
    # SET_VALUE must come before PLACE
    if last_set_value >= 0 and first_place >= 0:
        assert last_set_value < first_place, "SET_VALUE must come before PLACE"
    
    # PLACE must come before CONNECT
    if last_place >= 0 and first_connect >= 0:
        assert last_place < first_connect, "PLACE must come before CONNECT"
    
    # Check that auto-placement was applied
    place_actions = [a for a in actions if a.type == "PLACE"]
    assert len(place_actions) == 3, f"Expected 3 PLACE actions for new components, got {len(place_actions)}"
    
    # Verify placement coordinates are reasonable
    for place in place_actions:
        assert place.x >= 0, "Placement x should be non-negative"
        assert place.y is not None, "Placement y should exist"
    
    # Verify all ADDs have correct fusion commands
    add_actions = [a for a in actions if a.type == "ADD"]
    assert len(add_actions) == 3, f"Expected 3 ADD actions, got {len(add_actions)}"
    
    for add in add_actions:
        assert "ADD" in add.cmd, f"Fusion command should contain 'ADD', got: {add.cmd}"
        assert add.refdes in ["R1", "R2", "U1"], f"Unexpected refdes: {add.refdes}"
    
    # Verify SET_VALUE actions
    set_value_actions = [a for a in actions if a.type == "SET_VALUE"]
    assert len(set_value_actions) == 2, f"Expected 2 SET_VALUE actions, got {len(set_value_actions)}"
    
    for sv in set_value_actions:
        assert sv.value == "120", f"Expected value '120', got '{sv.value}'"
    
    # Verify CONNECT actions
    connect_actions = [a for a in actions if a.type == "CONNECT"]
    assert len(connect_actions) == 6, f"Expected 6 CONNECT actions, got {len(connect_actions)}"
    
    print("✓ test_compile_create_basic PASSED")


def test_compile_create_no_placement():
    """Test that components without explicit placement get auto-placed."""
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
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R2")),
            AddComponentCmd(args=AddComponentArgs(part_id="resistor_0603", refdes="R3")),
        ]
    )
    
    actions_doc, warnings = compile_to_actions(
        commands=commands,
        catalog_parts=catalog_parts,
        snapshot=None,
    )
    
    actions = actions_doc.actions
    place_actions = [a for a in actions if a.type == "PLACE"]
    
    # All 3 components should be auto-placed
    assert len(place_actions) == 3, f"Expected 3 auto-placed components, got {len(place_actions)}"
    
    # Verify placement coordinates differ (grid layout)
    x_coords = [p.x for p in place_actions]
    assert len(set(x_coords)) > 1 or len(place_actions) == 1, "Components should have different x coordinates"
    
    print("✓ test_compile_create_no_placement PASSED")


if __name__ == "__main__":
    test_compile_create_basic()
    test_compile_create_no_placement()
    print("\n✓ All CREATE mode tests passed!")
