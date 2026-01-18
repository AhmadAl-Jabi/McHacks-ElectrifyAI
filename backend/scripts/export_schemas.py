"""
Export JSON schemas for Snapshot, Commands, and Actions IRs.

Usage:
    python backend/scripts/export_schemas.py
"""
import json
from pathlib import Path

# Import domain models
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.domain import (
    SnapshotDoc,
    CommandsDoc,
    ActionsDoc,
)


def export_schemas():
    """Export Pydantic models as JSON schemas."""
    # Define output directory
    schemas_dir = Path(__file__).parent.parent / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    
    # Export each schema
    schemas = {
        "snapshot_schema.json": SnapshotDoc,
        "commands_schema.json": CommandsDoc,
        "actions_schema.json": ActionsDoc,
    }
    
    for filename, model in schemas.items():
        output_path = schemas_dir / filename
        schema = model.model_json_schema()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Exported {filename} to {output_path}")
    
    print(f"\nAll schemas exported to {schemas_dir}")


if __name__ == "__main__":
    export_schemas()
