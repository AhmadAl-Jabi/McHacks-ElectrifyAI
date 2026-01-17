"""
Example: Using bridge configuration for backend-Fusion communication.

This script demonstrates how to use the bridge configuration module
to write/read files between backend and Fusion add-in.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

from src.config.bridge import (
    BRIDGE_DIR,
    SNAPSHOT_PATH,
    SNAPSHOT_META_PATH,
    ACTIONS_PATH,
    EXEC_REPORT_PATH,
    SNAPSHOT_REQUEST_PATH,
    get_bridge_status,
    clear_bridge_files
)


def example_backend_write_actions():
    """Example: Backend writes actions for Fusion to execute."""
    print("\n" + "=" * 60)
    print("Example 1: Backend → Fusion (Write Actions)")
    print("=" * 60)
    
    actions = {
        "actions": [
            {
                "type": "ADD",
                "cmd": "ADD R_CHIP-0402(1005-METRIC)@ECOP_Resistor",
                "refdes": "R1"
            },
            {
                "type": "SET_VALUE",
                "refdes": "R1",
                "value": "10k"
            },
            {
                "type": "PLACE",
                "refdes": "R1",
                "x": 50.0,
                "y": 50.0,
                "rotation": 0.0
            }
        ]
    }
    
    # Write actions
    with open(ACTIONS_PATH, "w") as f:
        json.dump(actions, f, indent=2)
    
    print(f"✓ Wrote {len(actions['actions'])} actions to:")
    print(f"  {ACTIONS_PATH}")
    print(f"\nFusion add-in can now read from: ACTIONS_PATH")


def example_fusion_write_snapshot():
    """Example: Fusion writes snapshot for backend to read."""
    print("\n" + "=" * 60)
    print("Example 2: Fusion → Backend (Write Snapshot)")
    print("=" * 60)
    
    # Simulate snapshot from Fusion
    snapshot = {
        "components": [
            {
                "refdes": "R1",
                "part": "R_CHIP-0402(1005-METRIC)@ECOP_Resistor",
                "value": "10k",
                "x": 50.0,
                "y": 50.0,
                "rotation": 0.0
            },
            {
                "refdes": "C1",
                "part": "C_0402(1005-METRIC)@ECOP_Capacitor",
                "value": "100nF",
                "x": 70.0,
                "y": 50.0,
                "rotation": 90.0
            }
        ],
        "nets": [
            {
                "name": "VCC",
                "pins": ["R1.1"]
            },
            {
                "name": "NODE_1",
                "pins": ["R1.2", "C1.1"]
            },
            {
                "name": "GND",
                "pins": ["C1.2"]
            }
        ]
    }
    
    # Write snapshot
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    
    # Write metadata
    meta = {
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "component_count": len(snapshot["components"]),
        "net_count": len(snapshot["nets"])
    }
    
    with open(SNAPSHOT_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    
    print(f"✓ Wrote snapshot with {len(snapshot['components'])} components to:")
    print(f"  {SNAPSHOT_PATH}")
    print(f"✓ Wrote metadata to:")
    print(f"  {SNAPSHOT_META_PATH}")
    print(f"\nBackend can now read from: SNAPSHOT_PATH")


def example_fusion_write_execution_report():
    """Example: Fusion writes execution report after running actions."""
    print("\n" + "=" * 60)
    print("Example 3: Fusion → Backend (Execution Report)")
    print("=" * 60)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "success": True,
        "actions_executed": 3,
        "actions_failed": 0,
        "warnings": [
            "Rotation normalized to 0° (was 5°)"
        ],
        "errors": [],
        "script_path": "C:\\Temp\\electrify_exec_20260117_143052.scr",
        "execution_time_ms": 245
    }
    
    with open(EXEC_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Wrote execution report to:")
    print(f"  {EXEC_REPORT_PATH}")
    print(f"\nStatus: {report['success']}")
    print(f"Actions executed: {report['actions_executed']}")
    print(f"Warnings: {len(report['warnings'])}")


def example_backend_request_snapshot():
    """Example: Backend requests Fusion to capture snapshot."""
    print("\n" + "=" * 60)
    print("Example 4: Backend → Fusion (Request Snapshot)")
    print("=" * 60)
    
    request = {
        "timestamp": datetime.now().isoformat(),
        "request_id": "req_12345",
        "reason": "User asked for current state"
    }
    
    with open(SNAPSHOT_REQUEST_PATH, "w") as f:
        json.dump(request, f, indent=2)
    
    print(f"✓ Wrote snapshot request to:")
    print(f"  {SNAPSHOT_REQUEST_PATH}")
    print(f"\nFusion should detect this file and:")
    print(f"  1. Capture current schematic state")
    print(f"  2. Write to SNAPSHOT_PATH")
    print(f"  3. Delete SNAPSHOT_REQUEST_PATH")


def example_check_bridge_status():
    """Example: Check status of all bridge files."""
    print("\n" + "=" * 60)
    print("Example 5: Check Bridge Status")
    print("=" * 60)
    
    status = get_bridge_status()
    
    print(f"Bridge Directory: {status['bridge_dir']}")
    print(f"Exists: {status['bridge_exists']}")
    print(f"\nFiles:")
    
    for name, info in status['files'].items():
        if info['exists']:
            size_kb = info['size'] / 1024
            print(f"  ✓ {name}: {size_kb:.2f} KB")
        else:
            print(f"  ✗ {name}: Not found")


def example_cleanup():
    """Example: Clean up bridge files."""
    print("\n" + "=" * 60)
    print("Example 6: Cleanup Bridge Files")
    print("=" * 60)
    
    print("Current files:")
    status = get_bridge_status()
    existing = [name for name, info in status['files'].items() if info['exists']]
    print(f"  {len(existing)} files exist")
    
    # Clear all files
    result = clear_bridge_files()
    
    print(f"\nCleaned up:")
    print(f"  Removed: {len(result['removed'])} files")
    print(f"  Errors: {len(result['errors'])}")
    
    if result['removed']:
        print("\nRemoved files:")
        for path in result['removed']:
            print(f"  • {Path(path).name}")


if __name__ == "__main__":
    print("=" * 60)
    print("Bridge Configuration Examples")
    print("=" * 60)
    print(f"\nBridge Directory: {BRIDGE_DIR}")
    print(f"Exists: {BRIDGE_DIR.exists()}")
    
    # Run examples
    example_backend_write_actions()
    example_fusion_write_snapshot()
    example_fusion_write_execution_report()
    example_backend_request_snapshot()
    example_check_bridge_status()
    example_cleanup()
    
    print("\n" + "=" * 60)
    print("✓ All examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Import config_bridge in your Fusion add-in")
    print("  2. Import src.config.bridge in your backend")
    print("  3. Use constants instead of hardcoded paths")
    print("  4. Implement file watchers for real-time sync")
