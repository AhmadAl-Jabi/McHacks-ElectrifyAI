"""Test deterministic mode detection in agent prompts."""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.ecop_schematic_copilot.agent.prompting import build_system_instructions, build_user_message


def test_create_mode():
    """Test CREATE mode with empty snapshot."""
    snapshot = {"components": [], "nets": []}
    
    system_instructions = build_system_instructions(snapshot=snapshot)
    
    assert "MODE: CREATE" in system_instructions
    assert "CREATING a new schematic" in system_instructions
    assert "MODE: EDIT" not in system_instructions
    
    user_message = build_user_message(
        user_request="Add a voltage divider",
        snapshot=snapshot,
        allowed_parts_packet=[],
        primitives_excerpt=[],
        rag_context=""
    )
    
    assert "MODE: CREATE" in user_message
    assert "Empty schematic" in user_message
    assert "EXISTING COMPONENT REFDES" not in user_message
    
    print("✓ CREATE mode test passed")


def test_edit_mode():
    """Test EDIT mode with existing components."""
    snapshot = {
        "components": [
            {"refdes": "R1", "part_id": "resistor", "pins": ["1", "2"]},
            {"refdes": "R2", "part_id": "resistor", "pins": ["1", "2"]},
            {"refdes": "U1", "part_id": "mcu", "pins": ["VDD", "GND", "PA0"]}
        ],
        "nets": [
            {"net_name": "VCC", "connections": [{"refdes": "R1", "pin": "1"}]},
            {"net_name": "GND", "connections": [{"refdes": "U1", "pin": "GND"}]}
        ]
    }
    
    system_instructions = build_system_instructions(snapshot=snapshot)
    
    assert "MODE: EDIT" in system_instructions
    assert "EDITING an existing schematic" in system_instructions
    assert "R1, R2, U1" in system_instructions
    assert "VCC, GND" in system_instructions
    assert "PREFER existing net names" in system_instructions
    assert "DO NOT invent/assume components" in system_instructions
    assert "MODE: CREATE" not in system_instructions
    
    user_message = build_user_message(
        user_request="Connect R2 to U1",
        snapshot=snapshot,
        allowed_parts_packet=[],
        primitives_excerpt=[],
        rag_context=""
    )
    
    assert "MODE: EDIT" in user_message
    assert "EXISTING COMPONENT REFDES" in user_message
    assert "R1, R2, U1" in user_message
    assert "EXISTING NET NAMES" in user_message
    assert "VCC, GND" in user_message
    assert "3 components and 2 nets" in user_message
    
    print("✓ EDIT mode test passed")


def test_mode_transition():
    """Test that mode correctly transitions based on snapshot."""
    # Start with empty
    empty_snapshot = {"components": [], "nets": []}
    instructions_create = build_system_instructions(snapshot=empty_snapshot)
    assert "MODE: CREATE" in instructions_create
    
    # Add a component
    with_component = {
        "components": [{"refdes": "R1", "part_id": "resistor"}],
        "nets": []
    }
    instructions_edit = build_system_instructions(snapshot=with_component)
    assert "MODE: EDIT" in instructions_edit
    assert "R1" in instructions_edit
    
    print("✓ Mode transition test passed")


if __name__ == "__main__":
    test_create_mode()
    test_edit_mode()
    test_mode_transition()
    print("\n✅ All deterministic mode tests passed!")
