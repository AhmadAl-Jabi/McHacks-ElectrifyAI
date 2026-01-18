"""
Deterministic schematic auto-placer.

Computes component placements for schematic layout using a grid-based approach.
Ensures no overlaps and provides deterministic results.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Rect:
    """Rectangle representing occupied space on schematic."""
    x: float
    y: float
    w: float
    h: float
    
    def intersects(self, other: 'Rect') -> bool:
        """Check if this rectangle intersects with another."""
        return not (
            self.x + self.w <= other.x or
            other.x + other.w <= self.x or
            self.y + self.h <= other.y or
            other.y + other.h <= self.y
        )


@dataclass
class Placement:
    """Computed placement for a component."""
    x: float
    y: float
    rotation: float
    layer: str = "Top"


@dataclass
class PartToPlace:
    """Part that needs placement."""
    refdes: str
    part_id: str
    kind: str
    anchor_refdes: Optional[str] = None
    dx: float = 0.0
    dy: float = 0.0
    rotation: float = 0.0
    width: Optional[float] = None
    height: Optional[float] = None


class GridPlacer:
    """
    Grid-based deterministic component placer.
    
    Places components on a grid, avoiding overlaps with existing components.
    Supports anchored placement (place_near semantics).
    """
    
    def __init__(
        self,
        grid_step: float = 10.0,
        margin: float = 5.0,
        sheet_max_x: float = 500.0,
        wrap_y_step: float = 50.0
    ):
        """
        Initialize placer.
        
        Args:
            grid_step: Grid cell size (distance units)
            margin: Minimum margin around components
            sheet_max_x: Maximum X coordinate before wrapping to next row
            wrap_y_step: Y increment when wrapping to next row
        """
        self.grid_step = grid_step
        self.margin = margin
        self.sheet_max_x = sheet_max_x
        self.wrap_y_step = wrap_y_step
    
    def estimate_size_cells(self, part_id: str, kind: str) -> tuple[int, int]:
        """
        Estimate component size in grid cells.
        
        Args:
            part_id: Catalog part ID
            kind: Component kind (resistor, ic, connector, etc.)
            
        Returns:
            (width_cells, height_cells)
        """
        # Normalize kind
        kind_lower = kind.lower()
        
        # Size rules based on component type
        if kind_lower in ('resistor', 'capacitor'):
            return (3, 1)
        elif kind_lower in ('ic', 'microcontroller', 'mcu'):
            return (6, 4)
        elif kind_lower == 'connector':
            return (6, 2)
        elif kind_lower in ('diode', 'transistor', 'mosfet', 'bjt'):
            return (3, 2)
        else:
            # Default for unknown types
            return (3, 2)
    
    def build_occupied(self, snapshot: Optional[dict]) -> list[Rect]:
        """
        Build list of occupied rectangles from snapshot.
        
        Args:
            snapshot: Snapshot dict with components array
            
        Returns:
            List of occupied rectangles
        """
        occupied = []
        
        if not snapshot or 'components' not in snapshot:
            return occupied
        
        for comp in snapshot.get('components', []):
            x = comp.get('x')
            y = comp.get('y')
            
            if x is None or y is None:
                continue
            
            # Get size from snapshot if available, otherwise estimate
            width = comp.get('width')
            height = comp.get('height')
            
            if width is None or height is None:
                # Estimate based on kind and part_id
                part_id = comp.get('part_id', '')
                kind = comp.get('kind', 'unknown')
                w_cells, h_cells = self.estimate_size_cells(part_id, kind)
                width = w_cells * self.grid_step
                height = h_cells * self.grid_step
            
            # Add margin
            occupied.append(Rect(
                x=x - self.margin,
                y=y - self.margin,
                w=width + 2 * self.margin,
                h=height + 2 * self.margin
            ))
        
        return occupied
    
    def snap_to_grid(self, x: float, y: float) -> tuple[float, float]:
        """Snap coordinates to grid."""
        return (
            round(x / self.grid_step) * self.grid_step,
            round(y / self.grid_step) * self.grid_step
        )
    
    def find_free_slot(
        self,
        occupied: list[Rect],
        preferred_origin: tuple[float, float],
        size: tuple[int, int]
    ) -> tuple[float, float]:
        """
        Find a free slot for a component of given size.
        
        Args:
            occupied: List of occupied rectangles
            preferred_origin: Preferred (x, y) starting position
            size: (width_cells, height_cells)
            
        Returns:
            (x, y) coordinates for placement
        """
        w_cells, h_cells = size
        width = w_cells * self.grid_step
        height = h_cells * self.grid_step
        
        # Snap preferred origin to grid
        start_x, start_y = self.snap_to_grid(*preferred_origin)
        
        # Search for free slot
        x = start_x
        y = start_y
        
        # Deterministic scan: try positions row by row
        max_attempts = 1000  # Safety limit
        attempts = 0
        
        while attempts < max_attempts:
            # Create test rectangle at current position
            test_rect = Rect(x=x, y=y, w=width, h=height)
            
            # Check collision with all occupied rectangles
            collides = any(test_rect.intersects(occ) for occ in occupied)
            
            if not collides:
                # Found a free slot!
                return (x, y)
            
            # Advance to next grid position
            x += self.grid_step
            
            # If exceeded sheet width, wrap to next row
            if x + width > self.sheet_max_x:
                x = start_x
                y += self.wrap_y_step
            
            attempts += 1
        
        # Fallback: return preferred origin even if collision
        # (better than crashing)
        return (start_x, start_y)
    
    def clamp_rotation(self, rotation: float) -> float:
        """Clamp rotation to nearest 0/90/180/270."""
        # Normalize to 0-360
        rotation = rotation % 360
        
        # Round to nearest 90 degrees
        quarters = round(rotation / 90.0)
        return (quarters * 90) % 360
    
    def place_all(
        self,
        new_parts: list[PartToPlace],
        snapshot: Optional[dict]
    ) -> dict[str, Placement]:
        """
        Place all new components deterministically.
        
        Args:
            new_parts: List of parts to place
            snapshot: Current schematic snapshot
            
        Returns:
            Dict mapping refdes to Placement
        """
        # Build occupied rectangles from existing components
        occupied = self.build_occupied(snapshot)
        
        # Build map of existing component positions (for anchors)
        existing_positions = {}
        if snapshot and 'components' in snapshot:
            for comp in snapshot.get('components', []):
                refdes = comp.get('refdes')
                x = comp.get('x')
                y = comp.get('y')
                if refdes and x is not None and y is not None:
                    existing_positions[refdes] = (x, y)
        
        # Find rightmost edge of occupied space
        max_x = 0.0
        if occupied:
            max_x = max(rect.x + rect.w for rect in occupied)
        
        # Column gap between existing and new components
        column_gap = 6 * self.grid_step
        base_x = max_x + column_gap
        base_y = 0.0
        
        # Place each part
        placements = {}
        
        for part in new_parts:
            # Determine size
            if part.width and part.height:
                # Use provided size
                w_cells = int(part.width / self.grid_step)
                h_cells = int(part.height / self.grid_step)
            else:
                # Estimate from kind
                w_cells, h_cells = self.estimate_size_cells(part.part_id, part.kind)
            
            # Determine preferred origin
            if part.anchor_refdes and part.anchor_refdes in existing_positions:
                # Anchored placement
                anchor_x, anchor_y = existing_positions[part.anchor_refdes]
                preferred_x = anchor_x + (part.dx * self.grid_step)
                preferred_y = anchor_y + (part.dy * self.grid_step)
            else:
                # Default placement: to the right of existing
                preferred_x = base_x
                preferred_y = base_y
            
            # Find free slot
            x, y = self.find_free_slot(occupied, (preferred_x, preferred_y), (w_cells, h_cells))
            
            # Clamp rotation
            rotation = self.clamp_rotation(part.rotation)
            
            # Create placement
            placements[part.refdes] = Placement(
                x=x,
                y=y,
                rotation=rotation,
                layer="Top"
            )
            
            # Add to occupied for next iteration
            width = w_cells * self.grid_step
            height = h_cells * self.grid_step
            occupied.append(Rect(
                x=x - self.margin,
                y=y - self.margin,
                w=width + 2 * self.margin,
                h=height + 2 * self.margin
            ))
            
            # Update existing positions so subsequent anchors can reference this
            existing_positions[part.refdes] = (x, y)
        
        return placements
