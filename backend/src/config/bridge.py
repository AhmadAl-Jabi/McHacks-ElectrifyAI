"""
Shared bridge configuration: Single source of truth for file paths.

This module defines the shared folder path and all file paths used for
communication between the backend and Fusion 360 add-in.

Environment Variables:
    ELECTRIFY_BRIDGE_DIR: Override default bridge folder location
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# -----------------------------------------------------------------------------
# Project Root and Bridge Directory
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/src/config -> project root

BRIDGE_DIR = Path(
    os.getenv(
        "ELECTRIFY_BRIDGE_DIR",
        str(PROJECT_ROOT / "bridge")
    )
)

# -----------------------------------------------------------------------------
# Shared File Paths
# -----------------------------------------------------------------------------
# Schematic state snapshot (from Fusion → Backend)
SNAPSHOT_PATH = BRIDGE_DIR / "snapshot.json"

# Snapshot metadata (timestamp, version, etc.)
SNAPSHOT_META_PATH = BRIDGE_DIR / "snapshot.meta.json"

# Actions to execute (from Backend → Fusion)
ACTIONS_PATH = BRIDGE_DIR / "actions.json"

# Execution report (from Fusion → Backend after executing actions)
EXEC_REPORT_PATH = BRIDGE_DIR / "executor_report.json"

# Request flag to trigger snapshot capture (Backend → Fusion)
SNAPSHOT_REQUEST_PATH = BRIDGE_DIR / "snapshot_request.json"

# -----------------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------------
def ensure_bridge_dir():
    """
    Create bridge directory if it doesn't exist.
    
    This should be called on module import or at app startup.
    """
    try:
        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Warning: Failed to create bridge directory: {e}")
        return False


# Auto-create on import
ensure_bridge_dir()


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_bridge_status() -> dict:
    """
    Get status of all bridge files.
    
    Returns:
        dict with file existence and modification times
    """
    files = {
        "snapshot": SNAPSHOT_PATH,
        "snapshot_meta": SNAPSHOT_META_PATH,
        "actions": ACTIONS_PATH,
        "exec_report": EXEC_REPORT_PATH,
        "snapshot_request": SNAPSHOT_REQUEST_PATH,
    }
    
    status = {
        "bridge_dir": str(BRIDGE_DIR),
        "bridge_exists": BRIDGE_DIR.exists(),
        "files": {}
    }
    
    for name, path in files.items():
        if path.exists():
            stat = path.stat()
            status["files"][name] = {
                "exists": True,
                "path": str(path),
                "size": stat.st_size,
                "modified": stat.st_mtime
            }
        else:
            status["files"][name] = {
                "exists": False,
                "path": str(path)
            }
    
    return status


def clear_bridge_files():
    """
    Clear all bridge files (useful for testing/reset).
    
    Does not delete the bridge directory itself.
    """
    files = [
        SNAPSHOT_PATH,
        SNAPSHOT_META_PATH,
        ACTIONS_PATH,
        EXEC_REPORT_PATH,
        SNAPSHOT_REQUEST_PATH,
    ]
    
    removed = []
    errors = []
    
    for path in files:
        if path.exists():
            try:
                path.unlink()
                removed.append(str(path))
            except Exception as e:
                errors.append(f"{path.name}: {e}")
    
    return {
        "removed": removed,
        "errors": errors
    }


# -----------------------------------------------------------------------------
# Export for convenience
# -----------------------------------------------------------------------------
__all__ = [
    "BRIDGE_DIR",
    "SNAPSHOT_PATH",
    "SNAPSHOT_META_PATH",
    "ACTIONS_PATH",
    "EXEC_REPORT_PATH",
    "SNAPSHOT_REQUEST_PATH",
    "ensure_bridge_dir",
    "get_bridge_status",
    "clear_bridge_files",
]
