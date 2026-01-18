"""
Placement module for automatic component placement using GridPlacer.
"""
from typing import Optional

from backend.src.layout.placer import GridPlacer, PartToPlace, Placement as GridPlacement
from ..domain import Placement


def auto_place(
    refdes_list: list[str],
    catalog_parts: dict[str, dict],
    existing_placements: dict[str, Placement],
    snapshot: Optional[dict] = None,
    grid_step: float = 10.0,
    margin: float = 5.0,
    sheet_max_x: float = 500.0,
) -> dict[str, Placement]:
    """
    Automatically place components using GridPlacer.
    
    Uses deterministic grid-based placement that avoids overlaps with existing components.
    
    Args:
        refdes_list: List of refdes to place
        catalog_parts: Catalog parts index {part_id -> part_info}
        existing_placements: Dictionary of existing placements {refdes -> Placement}
        snapshot: Current snapshot with component positions
        grid_step: Grid cell size
        margin: Minimum margin around components
        sheet_max_x: Maximum x before wrapping
        
    Returns:
        Dictionary of new placements {refdes -> Placement}
    """
    # Initialize placer
    placer = GridPlacer(
        grid_step=grid_step,
        margin=margin,
        sheet_max_x=sheet_max_x,
        wrap_y_step=50.0
    )
    
    # Build list of parts to place
    parts_to_place = []
    
    for refdes in refdes_list:
        # Skip if already placed
        if refdes in existing_placements:
            continue
        
        # Get part info from snapshot if available
        part_id = None
        kind = "unknown"
        
        if snapshot and 'components' in snapshot:
            for comp in snapshot['components']:
                if comp.get('refdes') == refdes:
                    part_id = comp.get('part_id', '')
                    kind = comp.get('kind', 'unknown')
                    break
        
        # If not found in snapshot, try to infer from catalog
        # (In practice, we need to track added parts separately)
        parts_to_place.append(PartToPlace(
            refdes=refdes,
            part_id=part_id or refdes,
            kind=kind
        ))
    
    # Place all parts
    grid_placements = placer.place_all(parts_to_place, snapshot)
    
    # Convert GridPlacement to domain Placement
    new_placements = {}
    for refdes, gp in grid_placements.items():
        new_placements[refdes] = Placement(
            x=gp.x,
            y=gp.y,
            rotation=gp.rotation,
            layer=gp.layer
        )
    
    return new_placements


def place_near(
    anchor: Placement,
    dx: float,
    dy: float,
    rotation: float = 0.0,
    layer: str = "Top",
) -> Placement:
    """
    Place a component relative to an anchor component.
    
    Args:
        anchor: Anchor component placement
        dx: X offset from anchor
        dy: Y offset from anchor
        rotation: Rotation angle for new placement
        layer: PCB layer for new placement
        
    Returns:
        New Placement offset from anchor
    """
    return Placement(
        x=anchor.x + dx,
        y=anchor.y + dy,
        rotation=rotation,
        layer=layer,
    )
