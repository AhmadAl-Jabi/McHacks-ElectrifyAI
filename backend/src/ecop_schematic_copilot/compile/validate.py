"""
Commands validation against catalog and snapshot.

Validates that commands reference valid parts, pins, nets, and refdes.
"""
from dataclasses import dataclass, field
from typing import Optional

from ..domain import (
    CommandsDoc,
    SnapshotDoc,
    AddComponentCmd,
    RemoveComponentCmd,
    CreateNetCmd,
    RenameNetCmd,
    ConnectCmd,
    DisconnectCmd,
    SetValueCmd,
    PlaceComponentCmd,
    PlaceNearCmd,
    CommentCmd,
    snapshot_component_map,
    snapshot_net_map,
)


@dataclass
class ValidationResult:
    """Result of commands validation."""
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_commands(
    doc: CommandsDoc,
    parts_by_id: dict[str, dict],
    snapshot: Optional[SnapshotDoc] = None,
) -> ValidationResult:
    """
    Validate commands against catalog and snapshot.
    
    Args:
        doc: Commands document to validate
        parts_by_id: Catalog parts indexed by part_id
        snapshot: Optional current schematic state (None for create mode)
        
    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []
    
    # Build snapshot lookup maps
    snapshot_components = {}
    snapshot_nets_set = set()
    if snapshot:
        snapshot_components = snapshot_component_map(snapshot)
        snapshot_nets_set = {net.net_name for net in snapshot.nets}
    
    # Track state as we process commands
    newly_added_refdes = set()  # Refdes added in this command list
    known_refdes = set(snapshot_components.keys())  # All known refdes
    created_nets = set()  # Nets created in this command list
    known_nets = snapshot_nets_set.copy()  # All known nets
    net_renames = {}  # Track from -> to renames
    
    # Part_id lookup for newly added components
    refdes_to_part_id = {}
    
    for i, cmd in enumerate(doc.commands):
        cmd_idx = f"Command[{i}]"
        
        # ===================================================================
        # ADD_COMPONENT
        # ===================================================================
        if isinstance(cmd, AddComponentCmd):
            # Check part_id exists in catalog
            if cmd.args.part_id not in parts_by_id:
                errors.append(
                    f"{cmd_idx}: add_component part_id '{cmd.args.part_id}' not found in catalog"
                )
            
            # Check refdes uniqueness
            if cmd.args.refdes in newly_added_refdes:
                errors.append(
                    f"{cmd_idx}: add_component refdes '{cmd.args.refdes}' duplicates earlier add"
                )
            elif cmd.args.refdes in snapshot_components:
                errors.append(
                    f"{cmd_idx}: add_component refdes '{cmd.args.refdes}' already exists in snapshot"
                )
            else:
                # Valid add
                newly_added_refdes.add(cmd.args.refdes)
                known_refdes.add(cmd.args.refdes)
                refdes_to_part_id[cmd.args.refdes] = cmd.args.part_id
        
        # ===================================================================
        # REMOVE_COMPONENT
        # ===================================================================
        elif isinstance(cmd, RemoveComponentCmd):
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: remove_component refdes '{cmd.args.refdes}' does not exist"
                )
        
        # ===================================================================
        # CREATE_NET
        # ===================================================================
        elif isinstance(cmd, CreateNetCmd):
            if cmd.args.net_name in known_nets:
                warnings.append(
                    f"{cmd_idx}: create_net '{cmd.args.net_name}' already exists"
                )
            else:
                created_nets.add(cmd.args.net_name)
                known_nets.add(cmd.args.net_name)
        
        # ===================================================================
        # RENAME_NET
        # ===================================================================
        elif isinstance(cmd, RenameNetCmd):
            # Check 'from' exists
            if cmd.args.from_ not in known_nets:
                errors.append(
                    f"{cmd_idx}: rename_net 'from' net '{cmd.args.from_}' does not exist"
                )
            
            # Check 'to' doesn't already exist (unless same name)
            if cmd.args.to in known_nets and cmd.args.to != cmd.args.from_:
                errors.append(
                    f"{cmd_idx}: rename_net 'to' net '{cmd.args.to}' already exists"
                )
            
            # Track rename
            if cmd.args.from_ in known_nets:
                known_nets.discard(cmd.args.from_)
                known_nets.add(cmd.args.to)
                net_renames[cmd.args.from_] = cmd.args.to
        
        # ===================================================================
        # CONNECT
        # ===================================================================
        elif isinstance(cmd, ConnectCmd):
            # Check refdes exists
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: connect refdes '{cmd.args.refdes}' does not exist"
                )
            else:
                # Validate pin
                if cmd.args.refdes in newly_added_refdes:
                    # New component - check catalog pins
                    part_id = refdes_to_part_id.get(cmd.args.refdes)
                    if part_id and part_id in parts_by_id:
                        catalog_pins = parts_by_id[part_id].get("pins", [])
                        if cmd.args.pin not in catalog_pins:
                            errors.append(
                                f"{cmd_idx}: connect pin '{cmd.args.pin}' not in catalog "
                                f"pins for part '{part_id}': {catalog_pins}"
                            )
                elif cmd.args.refdes in snapshot_components:
                    # Existing component - check snapshot pins
                    snapshot_comp = snapshot_components[cmd.args.refdes]
                    snapshot_pins = snapshot_comp.pins
                    if snapshot_pins:  # If snapshot has pin info
                        if cmd.args.pin not in snapshot_pins:
                            errors.append(
                                f"{cmd_idx}: connect pin '{cmd.args.pin}' not in snapshot "
                                f"pins for '{cmd.args.refdes}': {snapshot_pins}"
                            )
                    else:
                        # No pin info in snapshot
                        warnings.append(
                            f"{cmd_idx}: connect pin '{cmd.args.pin}' cannot be validated - "
                            f"snapshot has no pin info for '{cmd.args.refdes}'"
                        )
            
            # Check net exists (auto-create warning if not)
            if cmd.args.net_name not in known_nets:
                warnings.append(
                    f"{cmd_idx}: connect net '{cmd.args.net_name}' will be auto-created"
                )
                known_nets.add(cmd.args.net_name)
        
        # ===================================================================
        # DISCONNECT
        # ===================================================================
        elif isinstance(cmd, DisconnectCmd):
            # Check refdes exists
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: disconnect refdes '{cmd.args.refdes}' does not exist"
                )
            else:
                # Validate pin (same logic as connect)
                if cmd.args.refdes in newly_added_refdes:
                    part_id = refdes_to_part_id.get(cmd.args.refdes)
                    if part_id and part_id in parts_by_id:
                        catalog_pins = parts_by_id[part_id].get("pins", [])
                        if cmd.args.args.pin not in catalog_pins:
                            errors.append(
                                f"{cmd_idx}: disconnect pin '{cmd.args.pin}' not in catalog "
                                f"pins for part '{part_id}': {catalog_pins}"
                            )
                elif cmd.args.refdes in snapshot_components:
                    snapshot_comp = snapshot_components[cmd.args.refdes]
                    snapshot_pins = snapshot_comp.pins
                    if snapshot_pins:
                        if cmd.args.pin not in snapshot_pins:
                            errors.append(
                                f"{cmd_idx}: disconnect pin '{cmd.args.pin}' not in snapshot "
                                f"pins for '{cmd.args.refdes}': {snapshot_pins}"
                            )
                    else:
                        warnings.append(
                            f"{cmd_idx}: disconnect pin '{cmd.args.pin}' cannot be validated - "
                            f"snapshot has no pin info for '{cmd.args.refdes}'"
                        )
            
            # Warn if connection doesn't exist in snapshot (not an error)
            if snapshot and cmd.args.refdes in snapshot_components:
                connection_exists = False
                for net in snapshot.nets:
                    if net.net_name == cmd.args.net_name:
                        for conn in net.connections:
                            if conn.refdes == cmd.args.refdes and conn.pin == cmd.args.pin:
                                connection_exists = True
                                break
                
                if not connection_exists:
                    warnings.append(
                        f"{cmd_idx}: disconnect connection '{cmd.args.refdes}.{cmd.args.pin}' -> "
                        f"'{cmd.args.net_name}' does not exist in snapshot"
                    )
        
        # ===================================================================
        # SET_VALUE
        # ===================================================================
        elif isinstance(cmd, SetValueCmd):
            # Check refdes exists
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: set_value refdes '{cmd.args.refdes}' does not exist"
                )
            else:
                # Check if part allows set_value
                part_id = None
                if cmd.args.refdes in newly_added_refdes:
                    part_id = refdes_to_part_id.get(cmd.args.refdes)
                elif cmd.args.refdes in snapshot_components:
                    part_id = snapshot_components[cmd.args.refdes].part_id
                
                if part_id and part_id in parts_by_id:
                    catalog_entry = parts_by_id[part_id]
                    allows_set_value = catalog_entry.get("set_value", False)
                    if not allows_set_value:
                        errors.append(
                            f"{cmd_idx}: set_value not allowed for part '{part_id}' "
                            f"(catalog.set_value != true)"
                        )
        
        # ===================================================================
        # PLACE_COMPONENT
        # ===================================================================
        elif isinstance(cmd, PlaceComponentCmd):
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: place_component refdes '{cmd.args.refdes}' does not exist"
                )
        
        # ===================================================================
        # PLACE_NEAR
        # ===================================================================
        elif isinstance(cmd, PlaceNearCmd):
            if cmd.args.refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: place_near refdes '{cmd.args.refdes}' does not exist"
                )
            if cmd.args.anchor_refdes not in known_refdes:
                errors.append(
                    f"{cmd_idx}: place_near anchor_refdes '{cmd.args.anchor_refdes}' does not exist"
                )
        
        # ===================================================================
        # COMMENT
        # ===================================================================
        elif isinstance(cmd, CommentCmd):
            # Comments are always valid
            pass
    
    # Determine overall result
    ok = len(errors) == 0
    
    return ValidationResult(ok=ok, errors=errors, warnings=warnings)


def format_validation(result: ValidationResult) -> str:
    """
    Format validation result as human-readable multi-line summary.
    
    Args:
        result: ValidationResult to format
        
    Returns:
        Formatted string with errors and warnings
    """
    lines = []
    
    if result.ok:
        lines.append("✓ Validation PASSED")
    else:
        lines.append("✗ Validation FAILED")
    
    if result.errors:
        lines.append(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            lines.append(f"  - {err}")
    
    if result.warnings:
        lines.append(f"\nWarnings ({len(result.warnings)}):")
        for warn in result.warnings:
            lines.append(f"  - {warn}")
    
    if not result.errors and not result.warnings:
        lines.append("  No issues found")
    
    return "\n".join(lines)
