"""
Catalog indexer: builds part_id lookup with validation.
"""


def index_parts(catalog: dict) -> tuple[dict[str, dict], list[str]]:
    """
    Index parts by canonical part_id with validation.
    
    Args:
        catalog: Loaded catalog dictionary with "parts" key
        
    Returns:
        Tuple of (parts_by_id, warnings)
        - parts_by_id: Dictionary mapping part_id -> part entry
        - warnings: List of warning messages
        
    Raises:
        ValueError: If a part is missing required fusion_add field
    """
    parts_by_id = {}
    warnings = []
    
    parts = catalog.get("parts", {})
    
    for part_id, part_entry in parts.items():
        # Validate part entry is a dictionary
        if not isinstance(part_entry, dict):
            warnings.append(f"Part '{part_id}' is not a dictionary, skipping")
            continue
        
        # Check catalog_id consistency
        if "catalog_id" in part_entry:
            catalog_id = part_entry["catalog_id"]
            if catalog_id != part_id:
                warnings.append(
                    f"Part key '{part_id}' does not match catalog_id '{catalog_id}'"
                )
        
        # Require fusion_add command
        if "fusion_add" not in part_entry:
            raise ValueError(
                f"Part '{part_id}' is missing required 'fusion_add' field"
            )
        
        if not isinstance(part_entry["fusion_add"], str):
            raise ValueError(
                f"Part '{part_id}' fusion_add must be a string"
            )
        
        # Ensure pins list exists (set empty if missing)
        if "pins" not in part_entry:
            part_entry["pins"] = []
            warnings.append(f"Part '{part_id}' missing pins, defaulting to []")
        elif not isinstance(part_entry["pins"], list):
            raise ValueError(
                f"Part '{part_id}' pins must be a list"
            )
        
        # Add to index
        parts_by_id[part_id] = part_entry
    
    return parts_by_id, warnings
