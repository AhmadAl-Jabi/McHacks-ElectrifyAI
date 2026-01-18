"""
Snapshot Store: Load and cache schematic snapshots from bridge folder.

Provides deterministic snapshot loading for agent context.
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from backend.src.config.bridge import SNAPSHOT_PATH, SNAPSHOT_META_PATH


class SnapshotDoc(BaseModel):
    """Schematic snapshot document matching ULP export format."""
    model_config = ConfigDict(extra='allow')
    
    components: List[Dict[str, Any]] = Field(default_factory=list)
    nets: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None
    source: Optional[str] = None


class SnapshotMeta(BaseModel):
    """Snapshot metadata."""
    timestamp: str
    timestamp_unix_ms: int
    success: bool
    errors: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    export_count: Optional[int] = None


class SnapshotStore:
    """
    Manages snapshot loading and caching.
    
    Features:
    - Reads snapshot.json and snapshot.meta.json from bridge folder
    - Caches snapshot in memory with timestamp
    - Returns empty snapshot if files missing or invalid
    - Provides age/staleness information
    """
    
    def __init__(self, cache_ttl_seconds: int = 300):
        """
        Initialize snapshot store.
        
        Args:
            cache_ttl_seconds: Cache time-to-live (default: 5 minutes)
        """
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cached_snapshot: Optional[SnapshotDoc] = None
        self._cached_meta: Optional[SnapshotMeta] = None
        self._cache_time: Optional[datetime] = None
        self._warnings: List[str] = []
    
    def load_snapshot(self, force_reload: bool = False) -> tuple[SnapshotDoc, List[str]]:
        """
        Load snapshot from bridge folder.
        
        Args:
            force_reload: Force reload from disk even if cached
        
        Returns:
            tuple of (SnapshotDoc, warnings list)
        """
        self._warnings = []
        
        # Check cache validity
        if not force_reload and self._is_cache_valid():
            return self._cached_snapshot, self._warnings
        
        # Load from disk
        snapshot = self._load_snapshot_file()
        meta = self._load_meta_file()
        
        # Cache the results
        self._cached_snapshot = snapshot
        self._cached_meta = meta
        self._cache_time = datetime.now()
        
        return snapshot, self._warnings
    
    def _is_cache_valid(self) -> bool:
        """Check if cached snapshot is still valid."""
        if self._cached_snapshot is None or self._cache_time is None:
            return False
        
        age = datetime.now() - self._cache_time
        return age < self.cache_ttl
    
    def _load_snapshot_file(self) -> SnapshotDoc:
        """Load snapshot.json file."""
        try:
            if not SNAPSHOT_PATH.exists():
                self._warnings.append("Snapshot file not found - using empty snapshot")
                return SnapshotDoc()
            
            with open(SNAPSHOT_PATH, 'r') as f:
                data = json.load(f)
            
            # Validate and parse
            snapshot = SnapshotDoc(**data)
            
            # Check if empty
            if len(snapshot.components) == 0 and len(snapshot.nets) == 0:
                self._warnings.append("Snapshot is empty (no components or nets)")
            
            return snapshot
            
        except json.JSONDecodeError as e:
            self._warnings.append(f"Invalid JSON in snapshot file: {e}")
            return SnapshotDoc()
        except Exception as e:
            self._warnings.append(f"Error reading snapshot: {e}")
            return SnapshotDoc()
    
    def _load_meta_file(self) -> Optional[SnapshotMeta]:
        """Load snapshot.meta.json file."""
        try:
            if not SNAPSHOT_META_PATH.exists():
                self._warnings.append("Snapshot metadata not found")
                return None
            
            with open(SNAPSHOT_META_PATH, 'r') as f:
                data = json.load(f)
            
            meta = SnapshotMeta(**data)
            
            # Check for export errors
            if not meta.success:
                self._warnings.append(f"Snapshot export had errors: {meta.errors}")
            
            return meta
            
        except Exception as e:
            self._warnings.append(f"Error reading metadata: {e}")
            return None
    
    def get_snapshot_age(self) -> Optional[timedelta]:
        """
        Get age of current snapshot.
        
        Returns:
            timedelta if metadata available, None otherwise
        """
        if not self._cached_meta:
            return None
        
        try:
            snapshot_time = datetime.fromisoformat(self._cached_meta.timestamp)
            return datetime.now() - snapshot_time
        except:
            return None
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current snapshot.
        
        Returns:
            dict with component count, net count, age, warnings
        """
        if not self._cached_snapshot:
            return {
                "loaded": False,
                "components": 0,
                "nets": 0,
                "age_seconds": None,
                "warnings": ["No snapshot loaded"]
            }
        
        age = self.get_snapshot_age()
        age_seconds = age.total_seconds() if age else None
        
        return {
            "loaded": True,
            "components": len(self._cached_snapshot.components),
            "nets": len(self._cached_snapshot.nets),
            "age_seconds": age_seconds,
            "age_human": self._format_age(age) if age else "unknown",
            "warnings": self._warnings,
            "cache_valid": self._is_cache_valid(),
            "export_count": self._cached_meta.export_count if self._cached_meta else None,
            "reason": self._cached_meta.reason if self._cached_meta else None
        }
    
    def _format_age(self, age: timedelta) -> str:
        """Format age as human-readable string."""
        seconds = int(age.total_seconds())
        
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"


# Global instance
_store = SnapshotStore()


def load_snapshot(force_reload: bool = False) -> tuple[SnapshotDoc, List[str]]:
    """
    Load snapshot from global store.
    
    Args:
        force_reload: Force reload from disk
    
    Returns:
        tuple of (SnapshotDoc, warnings list)
    """
    return _store.load_snapshot(force_reload=force_reload)


def get_snapshot_summary() -> Dict[str, Any]:
    """Get summary of current snapshot from global store."""
    return _store.get_summary()
