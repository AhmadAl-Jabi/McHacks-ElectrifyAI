"""
Script builder: converts actions to Fusion Electronics command-line statements.

Takes validated actions and generates .scr file content.
"""
from typing import List, Dict, Any, Tuple
from .action_types import (
    parse_action,
    AddAction,
    SetValueAction,
    PlaceAction,
    ConnectAction,
    DisconnectAction,
    RenameNetAction,
    RemoveAction
)


# Configuration
DEFAULT_GRID_UNIT = "MM"  # MM or MIL
DEFAULT_GRID_SIZE = 1.0   # Grid spacing


DEFAULT_GRID_SIZE = 1.0   # Grid spacing


def _escape_name(name: str) -> str:
    """
    Escape name/value string for Electronics script (quote if contains spaces or special chars).
    
    Args:
        name: String to escape
        
    Returns:
        Escaped string (quoted if necessary)
    """
    if " " in name or ";" in name or "(" in name or ")" in name:
        # Quote and escape internal quotes
        escaped = name.replace('"', '\\"')
        return f'"{escaped}"'
    return name


def build_add(action: AddAction) -> Tuple[List[str], List[str]]:
    """
    Build ADD command.
    
    Syntax: ADD part_name@library (x y)
    
    Args:
        action: AddAction instance
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    # ADD command - place at default position (10, 10) for now
    # Backend can override with explicit PLACE action if needed
    commands.append(f"{action.cmd} (10 10);")
    
    return commands, warnings


def build_set_value(action: SetValueAction) -> Tuple[List[str], List[str]]:
    """
    Build VALUE command to set component value.
    
    Syntax: VALUE refdes value
    
    Args:
        action: SetValueAction instance
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    value_escaped = _escape_name(action.value)
    commands.append(f"VALUE {action.refdes} {value_escaped};")
    
    return commands, warnings


def build_place(action: PlaceAction) -> Tuple[List[str], List[str]]:
    """
    Build MOVE and ROTATE commands to place component at specific coordinates.
    
    Emulates PLACE using:
    1. MOVE refdes (x y) - position component
    2. ROTATE R<angle> refdes - rotate component (if needed)
    
    The order is important: MOVE first establishes position,
    then ROTATE applies rotation around that position.
    
    Rotation is normalized to standard angles: 0/90/180/270 degrees.
    Layer checking: only "Top" is supported for schematics.
    
    Args:
        action: PlaceAction instance
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    # Check layer - only Top is supported for schematics
    layer = getattr(action, 'layer', 'Top')
    if layer and layer.lower() != 'top':
        warnings.append(
            f"PLACE {action.refdes}: Layer '{layer}' not supported "
            f"(only 'Top' for schematics), ignoring layer specification"
        )
    
    # Normalize rotation to standard angles (0, 90, 180, 270)
    rotation = action.rotation % 360  # Normalize to 0-359
    
    # Round to nearest 90 degrees
    standard_angles = [0, 90, 180, 270]
    rotation_normalized = min(standard_angles, key=lambda x: abs(x - rotation))
    
    if abs(rotation - rotation_normalized) > 1.0:
        warnings.append(
            f"PLACE {action.refdes}: Rotation {rotation}° normalized to "
            f"{rotation_normalized}° (only 0/90/180/270 supported)"
        )
    
    # MOVE command with coordinates - always execute first
    commands.append(f"MOVE {action.refdes} ({action.x} {action.y});")
    
    # Add ROTATE command if rotation is non-zero
    if rotation_normalized != 0:
        commands.append(f"ROTATE R{rotation_normalized} {action.refdes};")
    
    return commands, warnings


def build_connect(action: ConnectAction) -> Tuple[List[str], List[str]]:
    """
    Build NET command to connect pin to net.
    
    Syntax: NET net_name refdes.pin
    
    Args:
        action: ConnectAction instance
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    net_escaped = _escape_name(action.net_name)
    pin_escaped = _escape_name(action.pin)
    commands.append(f"NET {net_escaped} {action.refdes}.{pin_escaped};")
    
    return commands, warnings


def build_disconnect(action: DisconnectAction) -> Tuple[List[str], List[str]]:
    """
    Build RIPUP command to disconnect pin from net.
    
    EDIT-MODE operation: Removes connection between a component pin and net.
    
    Syntax: RIPUP refdes.pin
    
    The RIPUP command in EAGLE/Fusion Electronics removes net segments.
    When applied to a specific pin (refdes.pin), it disconnects that pin
    from its net without affecting other connections to the same net.
    
    Implementation strategy:
    - RIPUP refdes.pin: Removes net segment connected to that pin
    - The net itself persists if other components remain connected
    - Isolated architecture allows easy syntax updates
    
    Known limitations:
    - May require specific selection context in some EAGLE variants
    - Cannot partially disconnect multi-pin nets without RIPUP @ syntax
    - If reliability issues arise, can return error instead of command
    
    Architecture note:
    If RIPUP syntax proves unreliable, this function can be modified to:
    1. Return empty commands + error in warnings
    2. Use alternative DELETE/reconnect sequence
    3. Require manual intervention flag
    
    Args:
        action: DisconnectAction instance with refdes, pin, net_name
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    # Validate required fields
    if not action.refdes or not action.pin:
        warnings.append(
            f"DISCONNECT: Invalid action - refdes='{action.refdes}' pin='{action.pin}', skipping"
        )
        return commands, warnings
    
    # Escape pin name for special characters
    pin_escaped = _escape_name(action.pin)
    
    # Emit RIPUP command for specific pin
    # Format: RIPUP refdes.pin removes connection at that pin
    commands.append(f"RIPUP {action.refdes}.{pin_escaped};")
    
    # Note: If this proves unreliable in production, we can add:
    # warnings.append(
    #     f"DISCONNECT {action.refdes}.{action.pin}: RIPUP command may require "
    #     f"manual verification in complex net topologies"
    # )
    
    return commands, warnings


def build_rename_net(action: RenameNetAction) -> Tuple[List[str], List[str]]:
    """
    Build NAME command to rename net.
    
    EDIT-MODE operation: Renames an existing net in the schematic.
    
    Syntax: NAME old_name new_name
    
    The NAME command in EAGLE/Fusion Electronics renames a net.
    Both old and new names are escaped if they contain special characters.
    
    Known limitations:
    - Net must already exist in the schematic
    - New name must not conflict with existing nets
    - Some special characters may require escaping
    
    Architecture note:
    This function is isolated to make syntax changes easy.
    If NAME command syntax differs, only this function needs updating.
    
    Args:
        action: RenameNetAction instance with old_name and new_name
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    # Validate names are not empty
    if not action.old_name or not action.old_name.strip():
        warnings.append("RENAME_NET: old_name is empty, skipping")
        return commands, warnings
    
    if not action.new_name or not action.new_name.strip():
        warnings.append("RENAME_NET: new_name is empty, skipping")
        return commands, warnings
    
    # Escape special characters in net names
    old_escaped = _escape_name(action.old_name)
    new_escaped = _escape_name(action.new_name)
    
    # Emit NAME command
    commands.append(f"NAME {old_escaped} {new_escaped};")
    
    return commands, warnings


def build_remove(action: RemoveAction) -> Tuple[List[str], List[str]]:
    """
    Build DELETE command to remove component from schematic.
    
    EDIT-MODE operation: Completely removes a component and its connections.
    
    Syntax: DELETE refdes
    
    The DELETE command in EAGLE/Fusion Electronics removes the entire
    component (part instance) from the schematic, including:
    - The component symbol
    - All net connections to its pins
    - Associated attributes (value, etc.)
    
    Implementation notes:
    - DELETE operates on component reference designator (R1, C1, U1, etc.)
    - Nets are automatically cleaned up (removed if no other connections)
    - Undo is available in interactive mode but not in script mode
    
    Safety considerations:
    - Deletion is permanent in script execution
    - No confirmation prompt when SET CONFIRM YES is active
    - Consider generating backup/snapshot before destructive operations
    
    Architecture note:
    Isolated for easy modification if DELETE syntax needs adjustment
    or if safer two-step process is needed (disconnect, then delete).
    
    Args:
        action: RemoveAction instance with refdes to delete
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    # Validate refdes is not empty
    if not action.refdes or not action.refdes.strip():
        warnings.append("REMOVE: refdes is empty, skipping deletion")
        return commands, warnings
    
    # Emit DELETE command
    # Format: DELETE refdes removes entire component
    commands.append(f"DELETE {action.refdes};")
    
    # Optional: Add safety warning for destructive operation
    # Uncomment if production environment needs extra visibility:
    # warnings.append(
    #     f"REMOVE {action.refdes}: Component deletion is permanent in script mode"
    # )
    
    return commands, warnings


def build_comment(action_dict: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Build TEXT command for comment/note (if supported).
    
    Since TEXT command may not be universally supported, we'll emit a
    safe comment in script format and add a warning.
    
    Args:
        action_dict: Comment action dictionary
        
    Returns:
        (commands, warnings) tuple
    """
    commands = []
    warnings = []
    
    text = action_dict.get("text", "")
    
    # Emit as script comment (# prefix) - won't execute but visible in script
    commands.append(f"# COMMENT: {text}")
    
    warnings.append(f"COMMENT action emitted as script comment (not executable): {text[:50]}")
    
    return commands, warnings


def build_script_commands(
    actions: List[Dict[str, Any]],
    grid_unit: str = DEFAULT_GRID_UNIT,
    grid_size: float = DEFAULT_GRID_SIZE
) -> Tuple[List[str], List[str]]:
    """
    Convert actions to Fusion Electronics script commands.
    
    Args:
        actions: List of action dictionaries (already validated by backend)
        grid_unit: Grid unit - "MM" or "MIL" (default: MM)
        grid_size: Grid spacing size (default: 1.0)
        
    Returns:
        (commands, warnings) tuple where:
            - commands: List of command strings
            - warnings: List of warning messages
    """
    commands = []
    warnings = []
    
    # Setup: Enable confirmation for safer execution
    commands.append("SET CONFIRM YES;")
    
    # Setup: Configure grid for consistent placement
    grid_unit_upper = grid_unit.upper()
    if grid_unit_upper not in ["MM", "MIL"]:
        warnings.append(f"Invalid grid unit '{grid_unit}', defaulting to MM")
        grid_unit_upper = "MM"
    
    commands.append(f"GRID {grid_unit_upper} {grid_size};")
    
    # Process each action
    for action_dict in actions:
        action_type = action_dict.get("type")
        
        try:
            if action_type == "ADD":
                action = parse_action(action_dict)
                cmds, warns = build_add(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "SET_VALUE":
                action = parse_action(action_dict)
                cmds, warns = build_set_value(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "PLACE":
                action = parse_action(action_dict)
                cmds, warns = build_place(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "CONNECT":
                action = parse_action(action_dict)
                cmds, warns = build_connect(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "DISCONNECT":
                action = parse_action(action_dict)
                cmds, warns = build_disconnect(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "RENAME_NET":
                action = parse_action(action_dict)
                cmds, warns = build_rename_net(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "REMOVE":
                action = parse_action(action_dict)
                cmds, warns = build_remove(action)
                commands.extend(cmds)
                warnings.extend(warns)
            
            elif action_type == "COMMENT":
                cmds, warns = build_comment(action_dict)
                commands.extend(cmds)
                warnings.extend(warns)
            
            else:
                warnings.append(f"Unknown action type: {action_type}")
        
        except Exception as e:
            warnings.append(f"Error processing action {action_type}: {e}")
    
    # Cleanup: Turn off confirmation at end
    commands.append("SET CONFIRM OFF;")
    
    return commands, warnings


def build_script_file_content(
    actions: List[Dict[str, Any]],
    header_comment: str = None,
    grid_unit: str = DEFAULT_GRID_UNIT,
    grid_size: float = DEFAULT_GRID_SIZE
) -> Tuple[str, List[str]]:
    """
    Build complete .scr file content from actions.
    
    Args:
        actions: List of action dictionaries
        header_comment: Optional header comment for the script
        grid_unit: Grid unit - "MM" or "MIL"
        grid_size: Grid spacing size
        
    Returns:
        (script_content, warnings) tuple where:
            - script_content: Complete script file content as string
            - warnings: List of warning messages
    """
    lines = []
    
    # Add header comment if provided
    if header_comment:
        lines.append(f"# {header_comment}")
        lines.append("")
    
    # Generate commands
    commands, warnings = build_script_commands(actions, grid_unit, grid_size)
    
    # Each command on its own line
    lines.extend(commands)
    
    # Join with newlines
    script_content = "\n".join(lines)
    
    return script_content, warnings
