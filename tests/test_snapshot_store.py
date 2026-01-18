"""Test snapshot store functionality."""
import json
import pytest
from pathlib import Path
import sys
import os

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from src.snapshot.snapshot_store import SnapshotStore, load_snapshot, get_snapshot_summary
from src.config.bridge import SNAPSHOT_PATH, SNAPSHOT_META_PATH, BRIDGE_DIR


def test_snapshot_store_empty():
    """Test snapshot store with no files."""
    # Ensure clean state
    if SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.unlink()
    if SNAPSHOT_META_PATH.exists():
        SNAPSHOT_META_PATH.unlink()
    
    store = SnapshotStore()
    snapshot, warnings = store.load_snapshot()
    
    assert snapshot.components == []
    assert snapshot.nets == []
    assert len(warnings) > 0
    assert "not found" in warnings[0].lower()


def test_snapshot_store_valid():
    """Test snapshot store with valid files."""
    # Create bridge directory
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write test snapshot
    test_snapshot = {
        "components": [
            {
                "refdes": "R1",
                "value": "10k",
                "device": "R-US_R0805",
                "pins": [{"name": "1"}, {"name": "2"}]
            }
        ],
        "nets": [
            {
                "net_name": "VCC",
                "connections": [{"refdes": "R1", "pin": "1"}]
            }
        ],
        "generated_at": "2026-01-17T10:00:00",
        "source": "test"
    }
    
    with open(SNAPSHOT_PATH, 'w') as f:
        json.dump(test_snapshot, f)
    
    # Write test metadata
    test_meta = {
        "timestamp": "2026-01-17T10:00:00.123456",
        "timestamp_unix_ms": 1737108000123,
        "success": True,
        "errors": [],
        "reason": "test",
        "export_count": 1
    }
    
    with open(SNAPSHOT_META_PATH, 'w') as f:
        json.dump(test_meta, f)
    
    # Load snapshot
    store = SnapshotStore()
    snapshot, warnings = store.load_snapshot()
    
    assert len(snapshot.components) == 1
    assert snapshot.components[0]["refdes"] == "R1"
    assert len(snapshot.nets) == 1
    assert snapshot.nets[0]["net_name"] == "VCC"
    assert len(warnings) == 0
    
    # Test summary
    summary = store.get_summary()
    assert summary["loaded"] is True
    assert summary["components"] == 1
    assert summary["nets"] == 1
    assert summary["age_seconds"] is not None
    
    # Clean up
    SNAPSHOT_PATH.unlink()
    SNAPSHOT_META_PATH.unlink()


def test_snapshot_store_global():
    """Test global load_snapshot function."""
    # Create bridge directory
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write empty snapshot
    with open(SNAPSHOT_PATH, 'w') as f:
        json.dump({"components": [], "nets": []}, f)
    
    # Load using global function
    snapshot, warnings = load_snapshot(force_reload=True)
    
    assert snapshot.components == []
    assert snapshot.nets == []
    assert "empty" in str(warnings).lower() or len(warnings) == 0
    
    # Test summary
    summary = get_snapshot_summary()
    assert summary["loaded"] is True
    assert summary["components"] == 0
    
    # Clean up
    SNAPSHOT_PATH.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
