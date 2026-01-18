"""
Test compilation in EDIT mode (with snapshot).

Tests that compiler correctly handles existing components and nets:
- Rename nets
- Disconnect existing connections
- Set values on existing components
- Add new components
- Place near existing components
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.domain import (
    CommandsDoc,
    SnapshotDoc,
    SnapshotComponent,
    SnapshotNet,
    NetConnection,
    Placement,
    AddComponentCmd,
    AddComponentArgs,
    RenameNetCmd,
    RenameNetArgs,
    DisconnectCmd,
    DisconnectArgs,
    SetValueCmd,
    SetValueArgs,
    PlaceNearCmd,
    PlaceNearArgs,
    ConnectCmd,
    ConnectArgs,
)
from src.ecop_schematic_copilot.compile import compile_to_actions


def test_compile_edit_basic():
    """Test edit mode: rename net, disconnect, set value, add component, place near."""
    # ========================================================================
    # SETUP: Catalog
    # ========================================================================
    catalog_parts = {
        "can_transceiver": {
            "catalog_id": "can_transceiver",
            "kind": "ic",
            "pins": ["TXD", "RXD", "CANH", "CANL", "VDD", "VSS"],
            "set_value": False,
            "fusion_add": "ADD 'can_transceiver' U",
        },
        "tvs_diode": {
            "catalog_id": "tvs_diode",
            "kind": "diode",
            "pins": ["A", "K"],
            "set_value": False,
            "fusion_add": "ADD 'tvs_diode' D",
        },
        "connector_rj45": {
            "catalog_id": "connector_rj45",
            "kind": "connector",
            "pins": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "set_value": False,
            "fusion_add": "ADD 'connector_rj45' J",
        },
        "resistor_0603": {
            "catalog_id": "resistor_0603",
            "kind": "resistor",
            "pins": ["1", "2"],
            "set_value": True,
            "fusion_add": "ADD 'resistor_0603' R",
        },
    }
    
    # ========================================================================
    # SNAPSHOT: Existing schematic
    # ========================================================================
    snapshot = SnapshotDoc(
        components=[
            SnapshotComponent(
                refdes="U1",
                part_id="can_transceiver",
                pins=["TXD", "RXD", "CANH", "CANL", "VDD", "VSS"],
                placement=Placement(x=50.0, y=50.0, rotation=0.0, layer="Top"),
            ),
            SnapshotComponent(
                refdes="J1",
                part_id="connector_rj45",
                pins=["1", "2", "3", "4", "5", "6", "7", "8"],
                placement=Placement(x=10.0, y=10.0, rotation=0.0, layer="Top"),
            ),
            SnapshotComponent(
                refdes="R1",
                part_id="resistor_0603",
                value="120",
                pins=["1", "2"],
                placement=Placement(x=30.0, y=30.0, rotation=0.0, layer="Top"),
            ),
        ],
        nets=[
            SnapshotNet(
                net_name="CANH",
                connections=[
                    NetConnection(refdes="U1", pin="CANH"),
                    NetConnection(refdes="R1", pin="1"),
                ],
            ),
            SnapshotNet(
                net_name="CANL",
                connections=[
                    NetConnection(refdes="U1", pin="CANL"),
                    NetConnection(refdes="R1", pin="2"),
                ],
            ),
            SnapshotNet(
                net_name="VDD",
                connections=[
                    NetConnection(refdes="U1", pin="VDD"),
                ],
            ),
        ],
    )
    
    # ========================================================================
    # COMMANDS: Edit operations
    # ========================================================================
    commands = CommandsDoc(
        commands=[
            # Rename net
            RenameNetCmd(args=RenameNetArgs(**{"from": "VDD", "to": "VCC"})),
            
            # Disconnect
            DisconnectCmd(args=DisconnectArgs(refdes="R1", pin="2", net_name="CANL")),
            
            # Set value on existing component
            SetValueCmd(args=SetValueArgs(refdes="R1", value="60")),
            
            # Add new TVS diode
            AddComponentCmd(args=AddComponentArgs(part_id="tvs_diode", refdes="D1")),
            
            # Place near J1
            PlaceNearCmd(args=PlaceNearArgs(
                refdes="D1",
                anchor_refdes="J1",
                dx=20.0,
                dy=-10.0,
                rotation=90.0,
            )),
            
            # Connect new component
            ConnectCmd(args=ConnectArgs(refdes="D1", pin="A", net_name="CANH")),
            ConnectCmd(args=ConnectArgs(refdes="D1", pin="K", net_name="GND")),
        ]
    )
    
    # ========================================================================
    # COMPILE
    # ========================================================================
    actions_doc, warnings = compile_to_actions(
        commands=commands,
        catalog_parts=catalog_parts,
        snapshot=snapshot,
    )
    
    # ========================================================================
    # ASSERTIONS
    # ========================================================================
    actions = actions_doc.actions
    action_types = [action.type for action in actions]
    
    print(f"Generated {len(actions)} actions: {action_types}")
    
    # Check RENAME_NET comes first
    assert action_types[0] == "RENAME_NET", f"Expected RENAME_NET first, got {action_types[0]}"
    rename_action = actions[0]
    assert rename_action.from_ == "VDD", f"Expected rename from 'VDD', got '{rename_action.from_}'"
    assert rename_action.to == "VCC", f"Expected rename to 'VCC', got '{rename_action.to}'"
    
    # Check action ordering
    first_add = action_types.index("ADD") if "ADD" in action_types else -1
    first_set_value = action_types.index("SET_VALUE") if "SET_VALUE" in action_types else -1
    first_place = action_types.index("PLACE") if "PLACE" in action_types else -1
    first_connect = action_types.index("CONNECT") if "CONNECT" in action_types else -1
    first_disconnect = action_types.index("DISCONNECT") if "DISCONNECT" in action_types else -1
    
    # ADD should come after RENAME_NET but before CONNECT
    if first_add >= 0 and first_connect >= 0:
        assert first_add < first_connect, "ADD must come before CONNECT"
    
    # SET_VALUE for existing component
    set_value_actions = [a for a in actions if a.type == "SET_VALUE"]
    assert len(set_value_actions) == 1, f"Expected 1 SET_VALUE action, got {len(set_value_actions)}"
    assert set_value_actions[0].refdes == "R1", "SET_VALUE should target R1"
    assert set_value_actions[0].value == "60", "SET_VALUE should set value to 60"
    
    # PLACE action for new component (placed near J1)
    place_actions = [a for a in actions if a.type == "PLACE"]
    assert len(place_actions) == 1, f"Expected 1 PLACE action, got {len(place_actions)}"
    place = place_actions[0]
    assert place.refdes == "D1", "PLACE should target D1"
    # Should be near J1 (10, 10) + offset (20, -10) = (30, 0)
    assert place.x == 30.0, f"Expected x=30.0, got x={place.x}"
    assert place.y == 0.0, f"Expected y=0.0, got y={place.y}"
    assert place.rotation == 90.0, f"Expected rotation=90.0, got {place.rotation}"
    
    # DISCONNECT action
    disconnect_actions = [a for a in actions if a.type == "DISCONNECT"]
    assert len(disconnect_actions) == 1, f"Expected 1 DISCONNECT action, got {len(disconnect_actions)}"
    disc = disconnect_actions[0]
    assert disc.refdes == "R1", "DISCONNECT should target R1"
    assert disc.pin == "2", "DISCONNECT should target pin 2"
    assert disc.net == "CANL", "DISCONNECT should target net CANL"
    
    # CONNECT actions for new component
    connect_actions = [a for a in actions if a.type == "CONNECT"]
    assert len(connect_actions) == 2, f"Expected 2 CONNECT actions, got {len(connect_actions)}"
    
    # Verify connections
    d1_connections = [c for c in connect_actions if c.refdes == "D1"]
    assert len(d1_connections) == 2, "D1 should have 2 connections"
    
    print("✓ test_compile_edit_basic PASSED")


def test_compile_edit_net_rename_propagation():
    """Test that net renames propagate to later connect/disconnect commands."""
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
        nets=[
            SnapshotNet(net_name="OLD_NET", connections=[]),
        ],
    )
    
    commands = CommandsDoc(
        commands=[
            # Rename net
            RenameNetCmd(args=RenameNetArgs(**{"from": "OLD_NET", "to": "NEW_NET"})),
            
            # Connect using old name (should be normalized)
            ConnectCmd(args=ConnectArgs(refdes="R1", pin="1", net_name="OLD_NET")),
        ]
    )
    
    actions_doc, warnings = compile_to_actions(
        commands=commands,
        catalog_parts=catalog_parts,
        snapshot=snapshot,
    )
    
    actions = actions_doc.actions
    
    # Find RENAME_NET and CONNECT actions
    rename_actions = [a for a in actions if a.type == "RENAME_NET"]
    connect_actions = [a for a in actions if a.type == "CONNECT"]
    
    assert len(rename_actions) == 1, "Should have 1 RENAME_NET action"
    assert len(connect_actions) == 1, "Should have 1 CONNECT action"
    
    # CONNECT should use normalized (new) net name
    assert connect_actions[0].net == "NEW_NET", \
        f"CONNECT should use renamed net 'NEW_NET', got '{connect_actions[0].net}'"
    
    print("✓ test_compile_edit_net_rename_propagation PASSED")


if __name__ == "__main__":
    test_compile_edit_basic()
    test_compile_edit_net_rename_propagation()
    print("\n✓ All EDIT mode tests passed!")
