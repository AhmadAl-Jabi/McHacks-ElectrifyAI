"""
Primitives loader: reads circuit_primitives_robust_v0_2.json (read-only).
"""
import json
from pathlib import Path


def load_primitives(path: str) -> dict:
    """
    Load primitives JSON from file.
    
    Args:
        path: Path to circuit_primitives_robust_v0_2.json file
        
    Returns:
        Parsed primitives dictionary with structure:
        {
            "library_name": str,
            "primitives": list[dict]
        }
        
    Raises:
        FileNotFoundError: If primitives file doesn't exist
        ValueError: If primitives JSON is invalid
    """
    primitives_path = Path(path)
    
    if not primitives_path.exists():
        raise FileNotFoundError(f"Primitives file not found: {path}")
    
    try:
        with open(primitives_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in primitives file: {e}")
    
    # Validate primitives structure
    if not isinstance(data, dict):
        raise ValueError("Primitives root must be a JSON object")
    
    if "library_name" not in data:
        raise ValueError("Primitives must contain 'library_name' key")
    
    if "primitives" not in data:
        raise ValueError("Primitives must contain 'primitives' key")
    
    if not isinstance(data["primitives"], list):
        raise ValueError("Primitives 'primitives' must be a list")
    
    return data
