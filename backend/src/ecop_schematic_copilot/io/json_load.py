"""
JSON file loader with error handling.
"""
import json
from pathlib import Path
from typing import Any


def load_json(path: str) -> Any:
    """
    Load JSON data from file.
    
    Args:
        path: Path to JSON file
        
    Returns:
        Parsed JSON data (dict, list, etc.)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid
    """
    json_path = Path(path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file '{path}': {e}")
    except Exception as e:
        raise ValueError(f"Error reading file '{path}': {e}")
