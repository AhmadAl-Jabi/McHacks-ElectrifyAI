# Electrify ULP Library

User Language Programs (ULPs) for Fusion Electronics automation and data exchange.

## Available ULPs

### `export_snapshot_json.ulp`

Exports the current schematic snapshot to JSON format for backend processing.

**Purpose:** Capture schematic state (components, nets, placement) for AI agent context.

**Usage:**

#### From Fusion Electronics Command Line:
```
RUN "C:/electrify/fusion_addin/ulp/export_snapshot_json.ulp" "C:/electrify/bridge/snapshot.json"
```

#### From Python (Fusion Add-in):
```python
from config_bridge import SNAPSHOT_PATH
from fusion_executor import test_ulp_execution

result = test_ulp_execution(
    "C:/electrify/fusion_addin/ulp/export_snapshot_json.ulp",
    args=str(SNAPSHOT_PATH)
)

if result['success']:
    print("✓ Snapshot exported to bridge")
else:
    print(f"✗ Export failed: {result['errors']}")
```

#### From Python (Backend):
```python
from src.config.bridge import SNAPSHOT_PATH
from pathlib import Path

# Trigger snapshot export (add-in watches for this file)
with open(SNAPSHOT_REQUEST_PATH, "w") as f:
    json.dump({"requested_at": datetime.now().isoformat()}, f)

# Wait for snapshot to be written...
if SNAPSHOT_PATH.exists():
    with open(SNAPSHOT_PATH) as f:
        snapshot = json.load(f)
```

**Output Format:**
```json
{
  "components": [
    {
      "refdes": "R1",
      "value": "10k",
      "device": "R_CHIP-0402(1005-METRIC)",
      "pins": ["1", "2"],
      "placement": {
        "x": 50.0,
        "y": 50.0,
        "rotation": 0,
        "layer": "Top"
      }
    }
  ],
  "nets": [
    {
      "net_name": "VCC",
      "connections": [
        {"refdes": "R1", "pin": "1"}
      ]
    }
  ],
  "generated_at": "2026-01-17T14:30:00",
  "source": "fusion_ulp",
  "component_count": 10,
  "net_count": 5
}
```

**Schema Contract:**

Matches backend `SnapshotDoc` schema:
- `components[]`: Array of component objects
  - `refdes`: Component reference designator (R1, C1, U1, etc.)
  - `value`: Component value ("10k", "100nF", etc.) or empty string
  - `device`: Device/package name
  - `pins[]`: Array of pin names
  - `placement`: Position and orientation
    - `x`, `y`: Coordinates in millimeters
    - `rotation`: 0, 90, 180, or 270 degrees
    - `layer`: "Top" or "Bottom" (always "Top" for schematics)
- `nets[]`: Array of net objects
  - `net_name`: Net name (VCC, GND, SIGNAL_1, etc.)
  - `connections[]`: Array of {refdes, pin} pairs
- `generated_at`: ISO8601 timestamp
- `source`: Always "fusion_ulp"
- Metadata: `component_count`, `net_count`

**Error Handling:**
- No schematic open → Shows error dialog, no file written
- No output path argument → Uses default bridge path with warning
- Invalid path → ULP execution fails with error

## Testing

### Test export_snapshot_json.ulp

```bash
# Run validation (Python side)
python tests/test_ulp_execution.py
```

### Manual Test in Fusion

1. Open Fusion 360 Electronics
2. Open a schematic (or create simple test circuit)
3. Open TEXT COMMANDS window (Alt+T)
4. Run ULP:
   ```
   RUN "C:/electrify/fusion_addin/ulp/export_snapshot_json.ulp" "C:/test_output.json"
   ```
5. Check output file for valid JSON
6. Verify components and nets are present

### Validate JSON Output

```python
import json
from pathlib import Path

# Load snapshot
with open("C:/test_output.json") as f:
    snapshot = json.load(f)

# Validate structure
assert "components" in snapshot
assert "nets" in snapshot
assert "generated_at" in snapshot
assert snapshot["source"] == "fusion_ulp"

print(f"✓ Valid snapshot with {snapshot['component_count']} components")
```

## Integration with Bridge

The ULP output should be written to the bridge folder for backend consumption:

```python
# Bridge paths (single source of truth)
from config_bridge import SNAPSHOT_PATH

# Export to bridge
result = test_ulp_execution(
    "ulp/export_snapshot_json.ulp",
    args=str(SNAPSHOT_PATH)
)

# Backend reads from same path
from src.config.bridge import SNAPSHOT_PATH
with open(SNAPSHOT_PATH) as f:
    snapshot = json.load(f)
```

## Development

### Creating New ULPs

1. Create `.ulp` file in this directory
2. Add usage header comment
3. Document in this README
4. Add test function if needed
5. Update bridge integration docs

### ULP Best Practices

1. **Arguments:** Use `argv[1]` for output path
2. **Defaults:** Provide sensible default path with warning
3. **Error handling:** Check context (schematic/board)
4. **JSON escaping:** Use helper function for quotes/backslashes
5. **Validation:** Show success/error dialog
6. **Timestamps:** Include ISO8601 timestamp
7. **Metadata:** Add source identifier and counts

### ULP Syntax Resources

- EAGLE ULP Reference: [Autodesk Documentation]
- Context objects: `schematic()`, `board()`, `library()`
- Iteration: `parts()`, `nets()`, `segments()`, `pinrefs()`
- Output: `output(filename, "wt") { printf(...) }`
- Units: `u2mm()`, `u2mil()`, `mm2u()`, `mil2u()`

## Troubleshooting

### ULP doesn't execute
- Check absolute path is correct
- Verify `.ulp` extension
- Ensure schematic is open
- Check Fusion TEXT COMMANDS window for errors

### JSON output invalid
- Check `escapeJson()` function
- Verify all `printf()` statements
- Test with JSON validator
- Check for trailing commas

### Missing components/nets
- Verify schematic has parts placed
- Check net names are assigned
- Ensure connections exist (not just wires)

### Python execution fails
```python
# Check ULP path
from pathlib import Path
ulp_path = Path("fusion_addin/ulp/export_snapshot_json.ulp")
assert ulp_path.exists(), f"ULP not found: {ulp_path}"

# Check bridge path
from config_bridge import SNAPSHOT_PATH
assert SNAPSHOT_PATH.parent.exists(), f"Bridge dir missing: {SNAPSHOT_PATH.parent}"
```

## Future ULPs

Planned additions:
- [ ] `import_netlist.ulp` - Import netlist from backend
- [ ] `validate_design.ulp` - DRC validation export
- [ ] `export_bom.ulp` - Bill of materials
- [ ] `auto_annotate.ulp` - Reference designator assignment
- [ ] `export_placement.ulp` - Component placement only (no nets)

## License

Part of Electrify Copilot project.
