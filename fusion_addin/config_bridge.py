"""
Shared bridge configuration: Single source of truth for file paths (Fusion side).

This module mirrors backend/src/config/bridge.py to ensure both sides
use identical file paths for communication.

Environment Variables:
    ELECTRIFY_BRIDGE_DIR: Override default bridge folder location
    
Note: Fusion 360 add-ins may not have access to .env files, so the
default path (relative to add-in directory) is used if env var is not set.
"""
import os
from pathlib import Path

# -----------------------------------------------------------------------------
# Project Root and Bridge Directory
# -----------------------------------------------------------------------------
# Get add-in directory (fusion_addin/)
ADDON_DIR = Path(__file__).resolve().parent

# Navigate up one level to project
PROJECT_ROOT = ADDON_DIR.parent

# Get bridge directory from env var or use default
BRIDGE_DIR = Path(
    os.getenv(
        "ELECTRIFY_BRIDGE_DIR",
        str(PROJECT_ROOT / "bridge")
    )
)

# -----------------------------------------------------------------------------
# Shared File Paths (must match backend/src/config/bridge.py exactly)
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
    
    This should be called on module import or at add-in startup.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        # Can't use logging here as we might be in Fusion environment
        try:
            import adsk.core
            app = adsk.core.Application.get()
            app.log(f"Warning: Failed to create bridge directory: {e}")
        except:
            print(f"Warning: Failed to create bridge directory: {e}")
        return False


# Auto-create on import
ensure_bridge_dir()


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_bridge_status():
    """
    Get status of all bridge files.
    
    Returns:
        dict with file existence and sizes
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
    
    Returns:
        dict with removed files and errors
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


def log_bridge_config():
    """
    Log bridge configuration (useful for debugging in Fusion).
    
    Attempts to use Fusion logging if available, falls back to print.
    """
    msg = (
        f"Bridge Configuration:\n"
        f"  BRIDGE_DIR: {BRIDGE_DIR}\n"
        f"  SNAPSHOT_PATH: {SNAPSHOT_PATH}\n"
        f"  ACTIONS_PATH: {ACTIONS_PATH}\n"
        f"  EXEC_REPORT_PATH: {EXEC_REPORT_PATH}\n"
        f"  Bridge exists: {BRIDGE_DIR.exists()}"
    )
    
    try:
        import adsk.core
        app = adsk.core.Application.get()
        app.log(msg)
    except:
        print(msg)


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
    "log_bridge_config",
]
