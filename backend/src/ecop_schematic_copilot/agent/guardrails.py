"""
Agent guardrails: post-check validation for model output grounding.

Enforces that agent output stays within allowed boundaries (parts, pins, refdes).
Runs after parsing model output, before compilation.
"""
from typing import Optional

from ..domain import (
    CommandsDoc,
    SnapshotDoc,
    AddComponentCmd,
    ConnectCmd,
    DisconnectCmd,
    snapshot_component_map,
)
from ..compile import ValidationResult


def enforce_grounding(
    commands: CommandsDoc,
    allowed_part_ids: set[str],
    parts_by_id: dict[str, dict],
    snapshot: Optional[SnapshotDoc] = None,
) -> ValidationResult:
    """
    Enforce grounding constraints on agent-generated commands.
    
    This is a post-check that runs after parsing model output to ensure
    the agent stayed within allowed boundaries.
    
    Checks:
    1. All add_component.part_id are in allowed_part_ids
    2. All pins are valid for their parts
    3. No refdes collisions between new adds and existing snapshot
    
    Args:
        commands: Commands document from agent
        allowed_part_ids: Set of part_ids the agent was allowed to use
        parts_by_id: Full catalog parts index
        snapshot: Optional current schematic state
        
    Returns:
        ValidationResult with errors and warnings (does not raise)
    """
    errors = []
    warnings = []
    
    # Build snapshot component map
    snapshot_components = {}
    if snapshot:
        snapshot_components = snapshot_component_map(snapshot)
    
    # Track newly added refdes
    newly_added_refdes = set()
    refdes_to_part_id = {}
    
    # Track all known refdes (existing + new)
    known_refdes = set(snapshot_components.keys())
    
    for i, cmd in enumerate(commands.commands):
        cmd_idx = f"Command[{i}]"
        
        # ===================================================================
        # CHECK ADD_COMPONENT
        # ===================================================================
        if isinstance(cmd, AddComponentCmd):
            # Check part_id is in allowed set
            if cmd.args.part_id not in allowed_part_ids:
                errors.append(
                    f"{cmd_idx}: add_component part_id '{cmd.args.part_id}' not in allowed parts "
                    f"(grounding violation)"
                )
            
            # Check refdes collision with existing
            if cmd.args.refdes in snapshot_components:
                errors.append(
                    f"{cmd_idx}: add_component refdes '{cmd.args.refdes}' already exists in snapshot "
                    f"(collision)"
                )
            
            # Check refdes collision with earlier adds
            if cmd.args.refdes in newly_added_refdes:
                errors.append(
                    f"{cmd_idx}: add_component refdes '{cmd.args.refdes}' duplicates earlier add "
                    f"(collision)"
                )
            
            # Track new component
            newly_added_refdes.add(cmd.args.refdes)
            known_refdes.add(cmd.args.refdes)
            refdes_to_part_id[cmd.args.refdes] = cmd.args.part_id
        
        # ===================================================================
        # CHECK CONNECT PIN VALIDITY
        # ===================================================================
        elif isinstance(cmd, ConnectCmd):
            if cmd.args.refdes not in known_refdes:
                # Refdes doesn't exist - this is caught by standard validation
                # We focus on grounding violations here
                continue
            
            # Check pin validity
            if cmd.args.refdes in newly_added_refdes:
                # New component - check against catalog
                part_id = refdes_to_part_id.get(cmd.args.refdes)
                if part_id and part_id in parts_by_id:
                    catalog_pins = parts_by_id[part_id].get("pins", [])
                    if cmd.args.pin not in catalog_pins:
                        errors.append(
                            f"{cmd_idx}: connect pin '{cmd.args.pin}' not valid for part '{part_id}' "
                            f"(valid pins: {catalog_pins}) - grounding violation"
                        )
            elif cmd.args.refdes in snapshot_components:
                # Existing component - check against snapshot pins if available
                snapshot_comp = snapshot_components[cmd.args.refdes]
                snapshot_pins = snapshot_comp.pins
                if snapshot_pins:  # Only check if snapshot has pin info
                    if cmd.args.pin not in snapshot_pins:
                        errors.append(
                            f"{cmd_idx}: connect pin '{cmd.args.pin}' not in snapshot pins for "
                            f"'{cmd.args.refdes}' (valid pins: {snapshot_pins}) - grounding violation"
                        )
                else:
                    # No pin info - can't validate, issue warning
                    warnings.append(
                        f"{cmd_idx}: connect pin '{cmd.args.pin}' cannot be validated - "
                        f"snapshot missing pin info for '{cmd.args.refdes}'"
                    )
        
        # ===================================================================
        # CHECK DISCONNECT PIN VALIDITY
        # ===================================================================
        elif isinstance(cmd, DisconnectCmd):
            if cmd.args.refdes not in known_refdes:
                continue
            
            # Check pin validity (same logic as connect)
            if cmd.args.refdes in newly_added_refdes:
                part_id = refdes_to_part_id.get(cmd.args.refdes)
                if part_id and part_id in parts_by_id:
                    catalog_pins = parts_by_id[part_id].get("pins", [])
                    if cmd.args.pin not in catalog_pins:
                        errors.append(
                            f"{cmd_idx}: disconnect pin '{cmd.args.pin}' not valid for part '{part_id}' "
                            f"(valid pins: {catalog_pins}) - grounding violation"
                        )
            elif cmd.args.refdes in snapshot_components:
                snapshot_comp = snapshot_components[cmd.args.refdes]
                snapshot_pins = snapshot_comp.pins
                if snapshot_pins:
                    if cmd.args.pin not in snapshot_pins:
                        errors.append(
                            f"{cmd_idx}: disconnect pin '{cmd.args.pin}' not in snapshot pins for "
                            f"'{cmd.args.refdes}' (valid pins: {snapshot_pins}) - grounding violation"
                        )
                else:
                    warnings.append(
                        f"{cmd_idx}: disconnect pin '{cmd.args.pin}' cannot be validated - "
                        f"snapshot missing pin info for '{cmd.args.refdes}'"
                    )
    
    # Determine overall result
    ok = len(errors) == 0
    
    return ValidationResult(ok=ok, errors=errors, warnings=warnings)
