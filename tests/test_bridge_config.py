"""
Test bridge configuration module.

Verifies that:
1. Bridge directory is created automatically
2. All path constants are defined correctly
3. Helper functions work as expected
4. Both backend and Fusion configs match
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.config import bridge as backend_bridge

# Add fusion_addin to path
fusion_path = Path(__file__).parent.parent / "fusion_addin"
sys.path.insert(0, str(fusion_path))

import config_bridge as fusion_bridge


def test_backend_config():
    """Test backend bridge configuration."""
    print("=" * 60)
    print("Testing Backend Bridge Config")
    print("=" * 60)
    
    # Check bridge dir exists
    assert backend_bridge.BRIDGE_DIR.exists(), "Bridge directory should be created"
    print(f"✓ Bridge directory exists: {backend_bridge.BRIDGE_DIR}")
    
    # Check all paths are defined
    paths = [
        ("SNAPSHOT_PATH", backend_bridge.SNAPSHOT_PATH),
        ("SNAPSHOT_META_PATH", backend_bridge.SNAPSHOT_META_PATH),
        ("ACTIONS_PATH", backend_bridge.ACTIONS_PATH),
        ("EXEC_REPORT_PATH", backend_bridge.EXEC_REPORT_PATH),
        ("SNAPSHOT_REQUEST_PATH", backend_bridge.SNAPSHOT_REQUEST_PATH),
    ]
    
    for name, path in paths:
        assert isinstance(path, Path), f"{name} should be a Path object"
        assert path.parent == backend_bridge.BRIDGE_DIR, f"{name} should be in BRIDGE_DIR"
        print(f"✓ {name}: {path.name}")
    
    # Test helper functions
    status = backend_bridge.get_bridge_status()
    assert status["bridge_exists"] is True
    assert "files" in status
    print(f"✓ get_bridge_status() works: {len(status['files'])} files tracked")
    
    print("\n✓ Backend config: All tests passed!\n")


def test_fusion_config():
    """Test Fusion add-in bridge configuration."""
    print("=" * 60)
    print("Testing Fusion Bridge Config")
    print("=" * 60)
    
    # Check bridge dir exists
    assert fusion_bridge.BRIDGE_DIR.exists(), "Bridge directory should be created"
    print(f"✓ Bridge directory exists: {fusion_bridge.BRIDGE_DIR}")
    
    # Check all paths are defined
    paths = [
        ("SNAPSHOT_PATH", fusion_bridge.SNAPSHOT_PATH),
        ("SNAPSHOT_META_PATH", fusion_bridge.SNAPSHOT_META_PATH),
        ("ACTIONS_PATH", fusion_bridge.ACTIONS_PATH),
        ("EXEC_REPORT_PATH", fusion_bridge.EXEC_REPORT_PATH),
        ("SNAPSHOT_REQUEST_PATH", fusion_bridge.SNAPSHOT_REQUEST_PATH),
    ]
    
    for name, path in paths:
        assert isinstance(path, Path), f"{name} should be a Path object"
        assert path.parent == fusion_bridge.BRIDGE_DIR, f"{name} should be in BRIDGE_DIR"
        print(f"✓ {name}: {path.name}")
    
    # Test helper functions
    status = fusion_bridge.get_bridge_status()
    assert status["bridge_exists"] is True
    assert "files" in status
    print(f"✓ get_bridge_status() works: {len(status['files'])} files tracked")
    
    print("\n✓ Fusion config: All tests passed!\n")


def test_backend_fusion_match():
    """Verify backend and Fusion configs are identical."""
    print("=" * 60)
    print("Testing Backend ↔ Fusion Config Matching")
    print("=" * 60)
    
    # Check bridge dirs match
    backend_dir = str(backend_bridge.BRIDGE_DIR.resolve())
    fusion_dir = str(fusion_bridge.BRIDGE_DIR.resolve())
    
    assert backend_dir == fusion_dir, "Bridge directories must match"
    print(f"✓ Bridge directories match:\n  {backend_dir}")
    
    # Check all file paths match
    path_pairs = [
        ("SNAPSHOT_PATH", backend_bridge.SNAPSHOT_PATH, fusion_bridge.SNAPSHOT_PATH),
        ("SNAPSHOT_META_PATH", backend_bridge.SNAPSHOT_META_PATH, fusion_bridge.SNAPSHOT_META_PATH),
        ("ACTIONS_PATH", backend_bridge.ACTIONS_PATH, fusion_bridge.ACTIONS_PATH),
        ("EXEC_REPORT_PATH", backend_bridge.EXEC_REPORT_PATH, fusion_bridge.EXEC_REPORT_PATH),
        ("SNAPSHOT_REQUEST_PATH", backend_bridge.SNAPSHOT_REQUEST_PATH, fusion_bridge.SNAPSHOT_REQUEST_PATH),
    ]
    
    for name, backend_path, fusion_path in path_pairs:
        backend_str = str(backend_path.resolve())
        fusion_str = str(fusion_path.resolve())
        assert backend_str == fusion_str, f"{name} paths must match"
        print(f"✓ {name} matches: {backend_path.name}")
    
    print("\n✓ Backend ↔ Fusion: All paths match!\n")


def test_file_operations():
    """Test file write/read operations."""
    print("=" * 60)
    print("Testing File Operations")
    print("=" * 60)
    
    import json
    
    # Write test snapshot
    test_snapshot = {
        "components": [
            {"refdes": "R1", "value": "10k"},
            {"refdes": "C1", "value": "100nF"}
        ],
        "nets": ["VCC", "GND", "SIGNAL"]
    }
    
    with open(backend_bridge.SNAPSHOT_PATH, "w") as f:
        json.dump(test_snapshot, f, indent=2)
    
    print(f"✓ Wrote test snapshot to: {backend_bridge.SNAPSHOT_PATH.name}")
    
    # Read from Fusion side
    with open(fusion_bridge.SNAPSHOT_PATH, "r") as f:
        read_snapshot = json.load(f)
    
    assert read_snapshot == test_snapshot, "Snapshot should match"
    print(f"✓ Read snapshot from Fusion side successfully")
    
    # Clean up
    backend_bridge.SNAPSHOT_PATH.unlink()
    print(f"✓ Cleaned up test file")
    
    print("\n✓ File operations: All tests passed!\n")


def test_clear_bridge():
    """Test clearing bridge files."""
    print("=" * 60)
    print("Testing Bridge Cleanup")
    print("=" * 60)
    
    import json
    
    # Create some test files
    test_files = [
        backend_bridge.SNAPSHOT_PATH,
        backend_bridge.ACTIONS_PATH,
        backend_bridge.EXEC_REPORT_PATH,
    ]
    
    for path in test_files:
        with open(path, "w") as f:
            json.dump({"test": True}, f)
    
    print(f"✓ Created {len(test_files)} test files")
    
    # Clear files
    result = backend_bridge.clear_bridge_files()
    
    assert len(result["removed"]) == len(test_files)
    assert len(result["errors"]) == 0
    print(f"✓ Cleared {len(result['removed'])} files")
    
    # Verify all gone
    for path in test_files:
        assert not path.exists(), f"{path.name} should be deleted"
    
    print(f"✓ All test files removed")
    
    print("\n✓ Bridge cleanup: All tests passed!\n")


if __name__ == "__main__":
    try:
        test_backend_config()
        test_fusion_config()
        test_backend_fusion_match()
        test_file_operations()
        test_clear_bridge()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print(f"\nBridge directory: {backend_bridge.BRIDGE_DIR}")
        print("\nAvailable paths:")
        print(f"  • snapshot.json")
        print(f"  • snapshot.meta.json")
        print(f"  • actions.json")
        print(f"  • executor_report.json")
        print(f"  • snapshot_request.json")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
