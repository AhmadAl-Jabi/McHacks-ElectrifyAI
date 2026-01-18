"""
Catalog loader: reads and validates catalog.json.
"""
import json
from pathlib import Path


def load_catalog(path: str) -> dict:
    """
    Load catalog JSON from file.
    
    Args:
        path: Path to catalog.json file
        
    Returns:
        Parsed catalog dictionary
        
    Raises:
        FileNotFoundError: If catalog file doesn't exist
        ValueError: If catalog is invalid (missing "parts" key or invalid JSON)
    """
    catalog_path = Path(path)
    
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog file not found: {path}")
    
    try:
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in catalog file: {e}")
    
    # Validate catalog structure
    if not isinstance(catalog, dict):
        raise ValueError("Catalog root must be a JSON object")
    
    if "parts" not in catalog:
        raise ValueError("Catalog must contain a 'parts' key")
    
    if not isinstance(catalog["parts"], dict):
        raise ValueError("Catalog 'parts' must be a dictionary")
    
    return catalog
