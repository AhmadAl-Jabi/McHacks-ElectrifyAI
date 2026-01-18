"""
JSON file writer with error handling.
"""
import json
from pathlib import Path
from typing import Any


def write_json(path: str, data: Any, indent: int = 2) -> None:
    """
    Write JSON data to file.
    
    Creates parent directories if they don't exist.
    
    Args:
        path: Path to output JSON file
        data: Data to serialize (must be JSON-serializable)
        indent: Indentation level for pretty printing
        
    Raises:
        ValueError: If data cannot be serialized to JSON
        OSError: If file cannot be written
    """
    output_path = Path(path)
    
    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cannot serialize data to JSON: {e}")
    except Exception as e:
        raise OSError(f"Error writing to file '{path}': {e}")
