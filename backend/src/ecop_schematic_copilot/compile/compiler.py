"""
Compiler: transforms Commands IR + Snapshot + Catalog into Actions IR.

This is the core transformation layer that produces executor-ready actions
with proper ordering and placement.
"""
from typing import Optional

from ..domain import (
    CommandsDoc,
    SnapshotDoc,
    ActionsDoc,
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
    AddAction,
    SetValueAction,
    PlaceAction,
    ConnectAction,
    DisconnectAction,
    RenameNetAction,
    RemoveAction,
    Placement,
    snapshot_component_map,
)
from .validate import validate_commands, format_validation
from .placement import auto_place, place_near as place_near_util


def normalize_net_name(name: str, net_alias: dict[str, str]) -> str:
    """
    Normalize net name by following alias chain.
    
    Args:
        name: Original net name
        net_alias: Dictionary mapping old names to new names
        
    Returns:
        Final net name after following all renames
    """
    # Follow alias chain (handle transitive renames)
    visited = set()
    current = name
    
    while current in net_alias and current not in visited:
        visited.add(current)
        current = net_alias[current]
    
    return current


def compile_to_actions(
    commands: CommandsDoc,
    catalog_parts: dict[str, dict],
    snapshot: Optional[SnapshotDoc] = None,
) -> tuple[ActionsDoc, list[str]]:
    """
    Compile Commands IR into Actions IR.
    
    This is the only function that raises exceptions for validation errors.
    
    Args:
        commands: Commands document from agent
        catalog_parts: Catalog parts indexed by part_id
        snapshot: Optional current schematic state
        
    Returns:
        Tuple of (ActionsDoc, warnings list)
        
    Raises:
        ValueError: If validation fails (includes formatted error summary)
    """
    # ========================================================================
    # STEP 1: VALIDATION
    # ========================================================================
    validation_result = validate_commands(commands, catalog_parts, snapshot)
    
    if not validation_result.ok:
        formatted = format_validation(validation_result)
        raise ValueError(f"Commands validation failed:\n{formatted}")
    
    warnings = validation_result.warnings.copy()
    
    # ========================================================================
    # STEP 2: BUILD MAPS
    # ========================================================================
    existing_components = {}
    if snapshot:
        existing_components = snapshot_component_map(snapshot)
    
    # Track new components and their part_ids
    new_components = {}  # refdes -> part_id
    refdes_to_part_id = {}  # All refdes -> part_id (including existing)
    
    # Populate existing refdes -> part_id
    for refdes, comp in existing_components.items():
        if comp.part_id:
            refdes_to_part_id[refdes] = comp.part_id
    
    # Track explicit placements from commands
    explicit_placements = {}  # refdes -> Placement
    
    # Track existing placements from snapshot
    existing_placements = {}
    if snapshot:
        for comp in snapshot.components:
            if comp.placement:
                existing_placements[comp.refdes] = comp.placement
    
    # Net alias mapping (for rename tracking)
    net_alias = {}  # old_name -> new_name
    
    # Components to remove
    components_to_remove = []
    
    # ========================================================================
    # STEP 3: FIRST PASS - COLLECT STATE
    # ========================================================================
    for cmd in commands.commands:
        if isinstance(cmd, AddComponentCmd):
            new_components[cmd.args.refdes] = cmd.args.part_id
            refdes_to_part_id[cmd.args.refdes] = cmd.args.part_id
        
        elif isinstance(cmd, RenameNetCmd):
            net_alias[cmd.args.from_] = cmd.args.to
        
        elif isinstance(cmd, PlaceComponentCmd):
            explicit_placements[cmd.args.refdes] = Placement(
                x=cmd.args.x,
                y=cmd.args.y,
                rotation=cmd.args.rotation,
                layer=cmd.args.layer,
            )
        
        elif isinstance(cmd, PlaceNearCmd):
            # Resolve anchor placement
            anchor_placement = None
            if cmd.args.anchor_refdes in explicit_placements:
                anchor_placement = explicit_placements[cmd.args.anchor_refdes]
            elif cmd.args.anchor_refdes in existing_placements:
                anchor_placement = existing_placements[cmd.args.anchor_refdes]
            else:
                # Anchor not placed yet - skip for now, will be handled in auto-place
                warnings.append(
                    f"place_near: anchor '{cmd.args.anchor_refdes}' has no placement, "
                    f"skipping relative placement for '{cmd.args.refdes}'"
                )
                continue
            
            # Calculate relative placement
            new_placement = place_near_util(
                anchor=anchor_placement,
                dx=cmd.args.dx,
                dy=cmd.args.dy,
                rotation=cmd.args.rotation,
                layer=cmd.args.layer,
            )
            explicit_placements[cmd.args.refdes] = new_placement
        
        elif isinstance(cmd, RemoveComponentCmd):
            components_to_remove.append(cmd.args.refdes)
    
    # ========================================================================
    # STEP 4: BUILD ACTIONS IN DETERMINISTIC ORDER
    # ========================================================================
    actions = []
    
    # ----------------------------------------------------------------------
    # A) RENAME_NET ACTIONS FIRST
    # ----------------------------------------------------------------------
    for cmd in commands.commands:
        if isinstance(cmd, RenameNetCmd):
            actions.append(RenameNetAction(
                **{"from": cmd.args.from_, "to": cmd.args.to}
            ))
    
    # ----------------------------------------------------------------------
    # B) ADD ACTIONS
    # ----------------------------------------------------------------------
    for cmd in commands.commands:
        if isinstance(cmd, AddComponentCmd):
            # Get fusion_add command from catalog
            catalog_entry = catalog_parts.get(cmd.args.part_id)
            if not catalog_entry:
                warnings.append(f"Part '{cmd.args.part_id}' not found in catalog during compilation")
                continue
            
            fusion_cmd = catalog_entry.get("fusion_add")
            if not fusion_cmd:
                warnings.append(f"Part '{cmd.args.part_id}' missing fusion_add command")
                continue
            
            actions.append(AddAction(
                cmd=fusion_cmd,
                refdes=cmd.args.refdes,
            ))
    
    # ----------------------------------------------------------------------
    # C) SET_VALUE ACTIONS
    # ----------------------------------------------------------------------
    for cmd in commands.commands:
        if isinstance(cmd, SetValueCmd):
            actions.append(SetValueAction(
                refdes=cmd.args.refdes,
                value=cmd.args.value,
            ))
    
    # ----------------------------------------------------------------------
    # D) PLACEMENT ACTIONS
    # ----------------------------------------------------------------------
    # Auto-place any new components not explicitly placed
    all_placements = existing_placements.copy()
    all_placements.update(explicit_placements)
    
    new_refdes_list = list(new_components.keys())
    auto_placements = auto_place(
        refdes_list=new_refdes_list,
        catalog_parts=catalog_parts,
        existing_placements=all_placements,
        snapshot=snapshot.model_dump(mode='json') if snapshot else None,
    )
    
    # Merge auto placements
    all_placements.update(auto_placements)
    
    # Emit PLACE actions for all newly added components
    for refdes in new_refdes_list:
        if refdes in all_placements:
            placement = all_placements[refdes]
            actions.append(PlaceAction(
                refdes=refdes,
                x=placement.x,
                y=placement.y,
                rotation=placement.rotation,
                layer=placement.layer,
            ))
    
    # ----------------------------------------------------------------------
    # E) CONNECTIVITY ACTIONS (CONNECT/DISCONNECT)
    # ----------------------------------------------------------------------
    for cmd in commands.commands:
        if isinstance(cmd, ConnectCmd):
            # Normalize net name
            final_net = normalize_net_name(cmd.args.net_name, net_alias)
            actions.append(ConnectAction(
                refdes=cmd.args.refdes,
                pin=cmd.args.pin,
                net_name=final_net,
            ))
        
        elif isinstance(cmd, DisconnectCmd):
            # Normalize net name
            final_net = normalize_net_name(cmd.args.net_name, net_alias)
            actions.append(DisconnectAction(
                refdes=cmd.args.refdes,
                pin=cmd.args.pin,
                net_name=final_net,
            ))
    
    # ----------------------------------------------------------------------
    # F) REMOVE ACTIONS (LAST)
    # ----------------------------------------------------------------------
    for cmd in commands.commands:
        if isinstance(cmd, RemoveComponentCmd):
            actions.append(RemoveAction(
                refdes=cmd.args.refdes,
            ))
    
    # ========================================================================
    # RETURN ACTIONS DOCUMENT
    # ========================================================================
    actions_doc = ActionsDoc(actions=actions)
    
    return actions_doc, warnings
