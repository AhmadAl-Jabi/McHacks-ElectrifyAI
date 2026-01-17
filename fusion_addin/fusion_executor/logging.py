"""
Structured logging for action execution.

Provides consistent logging with levels and timestamps.
"""
import datetime
from typing import List, Dict, Any


class ExecutionLog:
    """Simple structured logger for action execution."""
    
    def __init__(self, app=None):
        """
        Initialize logger.
        
        Args:
            app: Optional Fusion Application instance for log output
        """
        self.app = app
        self.entries: List[Dict[str, Any]] = []
    
    def _log(self, level: str, message: str):
        """
        Internal logging method.
        
        Args:
            level: Log level (INFO, WARN, ERROR)
            message: Log message
        """
        timestamp = datetime.datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.entries.append(entry)
        
        # Also output to Fusion log if app provided
        if self.app:
            self.app.log(f"[Executor:{level}] {message}")
    
    def info(self, message: str):
        """Log info message."""
        self._log("INFO", message)
    
    def warn(self, message: str):
        """Log warning message."""
        self._log("WARN", message)
    
    def error(self, message: str):
        """Log error message."""
        self._log("ERROR", message)
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """Get all log entries."""
        return self.entries
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get log summary.
        
        Returns:
            Dict with counts of each log level
        """
        info_count = sum(1 for e in self.entries if e["level"] == "INFO")
        warn_count = sum(1 for e in self.entries if e["level"] == "WARN")
        error_count = sum(1 for e in self.entries if e["level"] == "ERROR")
        
        return {
            "total": len(self.entries),
            "info": info_count,
            "warnings": warn_count,
            "errors": error_count
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export log as dictionary."""
        return {
            "entries": self.entries,
            "summary": self.get_summary()
        }
