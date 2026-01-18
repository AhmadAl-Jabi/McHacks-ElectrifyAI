# Deterministic Auto-Placer Implementation

## Summary

Implemented a deterministic grid-based auto-placer for schematic component layout. The placer ensures collision-free placement with consistent, reproducible results.

## Files Created

### 1. `backend/src/layout/placer.py`
Core placement logic with the following components:

**Classes:**
- `Rect`: Rectangle for occupied space tracking
- `Placement`: Component placement (x, y, rotation, layer)
- `PartToPlace`: Input data for parts needing placement
- `GridPlacer`: Main placer engine

**Key Features:**
- Grid-based placement (configurable grid_step, default 10.0)
- Collision detection with margins (default 5.0)
- Component size estimation based on kind (resistor, ic, connector, etc.)
- Anchored placement support (place_near semantics)
- Deterministic scanning algorithm (left-to-right, top-to-bottom)
- Sheet wrapping when exceeding max_x (default 500.0)
- Rotation clamping to 0/90/180/270 degrees

**Sizing Rules:**
- Resistor/Capacitor: 3x1 cells
- IC/Microcontroller: 6x4 cells  
- Connector: 6x2 cells
- Diode/Transistor/MOSFET: 3x2 cells
- Default: 3x2 cells

### 2. `backend/src/layout/__init__.py`
Package initialization with exports.

### 3. `backend/tests/test_layout_placer.py`
Comprehensive test suite (13 tests, all passing):
- Grid snapping
- Rectangle intersection
- Size estimation
- Occupied space building
- Single and multiple part placement
- Existing component avoidance
- Anchored placement
- Collision avoidance
- Deterministic behavior
- Rotation clamping
- Row wrapping

## Integration

### Modified Files

**`backend/src/ecop_schematic_copilot/compile/placement.py`:**
- Replaced simple grid placement with GridPlacer integration
- Updated `auto_place()` to use GridPlacer with catalog awareness
- Maintained `place_near()` for relative positioning

**`backend/src/ecop_schematic_copilot/compile/compiler.py`:**
- Updated `auto_place()` call to pass `catalog_parts` and `snapshot`
- Enables size-aware and collision-aware placement

## Algorithm

1. **Build Occupied Space:**
   - Extract existing component positions from snapshot
   - Estimate sizes based on kind (or use provided width/height)
   - Create rectangles with margins

2. **Place New Components:**
   - For each part to place:
     - Determine preferred origin (anchored or column-based)
     - Find free slot by grid scanning
     - Add placed rect to occupied (for next iteration)
   
3. **Grid Scanning:**
   - Start at preferred origin (snapped to grid)
   - Check collision with all occupied rectangles
   - If collision: advance by grid_step
   - If exceed sheet_max_x: wrap to next row
   - Deterministic: same input → same output

4. **Anchored Placement:**
   - If anchor_refdes provided: start near anchor + offset
   - Still performs collision avoidance
   - Falls back to free slot if preferred position occupied

## Usage Example

```python
from backend.src.layout.placer import GridPlacer, PartToPlace

placer = GridPlacer(
    grid_step=10.0,
    margin=5.0,
    sheet_max_x=500.0,
    wrap_y_step=50.0
)

parts = [
    PartToPlace(refdes="R1", part_id="RES@LIB", kind="resistor"),
    PartToPlace(refdes="U1", part_id="IC@LIB", kind="ic"),
    PartToPlace(
        refdes="C1", 
        part_id="CAP@LIB", 
        kind="capacitor",
        anchor_refdes="U1",  # Place near U1
        dx=2.0,  # 2 grid steps to the right
        dy=0.0
    ),
]

placements = placer.place_all(parts, snapshot=None)
# Returns: {
#   "R1": Placement(x=60.0, y=0.0, rotation=0, layer="Top"),
#   "U1": Placement(x=130.0, y=0.0, rotation=0, layer="Top"),
#   "C1": Placement(x=220.0, y=0.0, rotation=0, layer="Top"),
# }
```

## Test Results

All 13 tests passing:
```
✓ test_snap_to_grid
✓ test_rect_intersects
✓ test_estimate_size_cells
✓ test_build_occupied_empty
✓ test_build_occupied_with_components
✓ test_place_single_part_empty_schematic
✓ test_place_multiple_parts_no_overlap
✓ test_place_with_existing_components
✓ test_place_near_anchor
✓ test_place_near_anchor_collision_avoidance
✓ test_deterministic_placement
✓ test_rotation_clamping
✓ test_wrapping_to_next_row
```

## Benefits

1. **Deterministic:** Same input always produces same output
2. **Collision-Free:** Automatically avoids overlaps
3. **Size-Aware:** Uses component kind to estimate appropriate spacing
4. **Anchored Support:** Respects place_near semantics
5. **Sheet Management:** Wraps to next row when needed
6. **Extensible:** Easy to add custom size rules or placement strategies

## Future Enhancements

Potential improvements:
- Hierarchical placement (group related components)
- Net-aware routing hints (place connected components nearby)
- Custom placement constraints from catalog
- Interactive placement adjustment
- Multi-sheet support
