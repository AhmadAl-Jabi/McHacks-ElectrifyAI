"""
CLI script to compile Commands IR into Actions IR.

Usage:
    python backend/scripts/compile_to_actions.py \\
        --catalog catalog.json \\
        --commands commands.json \\
        --snapshot snapshot.json \\
        --out actions.json
"""
import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.catalog import load_catalog, index_parts
from src.ecop_schematic_copilot.domain import CommandsDoc, SnapshotDoc, ActionsDoc
from src.ecop_schematic_copilot.compile import compile_to_actions
from src.ecop_schematic_copilot.io import load_json, write_json


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compile Commands IR to Actions IR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--catalog",
        required=True,
        help="Path to catalog.json"
    )
    parser.add_argument(
        "--commands",
        required=True,
        help="Path to commands.json (agent output)"
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Path to snapshot.json (optional, for edit mode)"
    )
    parser.add_argument(
        "--out",
        default="actions.json",
        help="Output path for actions.json (default: actions.json)"
    )
    
    args = parser.parse_args()
    
    try:
        # ====================================================================
        # LOAD CATALOG
        # ====================================================================
        print(f"Loading catalog from {args.catalog}...")
        catalog = load_catalog(args.catalog)
        
        parts_by_id, catalog_warnings = index_parts(catalog)
        print(f"✓ Indexed {len(parts_by_id)} parts")
        
        if catalog_warnings:
            print(f"Catalog warnings ({len(catalog_warnings)}):")
            for warn in catalog_warnings:
                print(f"  - {warn}")
        
        # ====================================================================
        # LOAD SNAPSHOT (OPTIONAL)
        # ====================================================================
        snapshot = None
        if args.snapshot:
            print(f"Loading snapshot from {args.snapshot}...")
            snapshot_data = load_json(args.snapshot)
            snapshot = SnapshotDoc.model_validate(snapshot_data)
            print(f"✓ Loaded snapshot with {len(snapshot.components)} components, "
                  f"{len(snapshot.nets)} nets")
        else:
            print("No snapshot provided (create mode)")
            snapshot = None
        
        # ====================================================================
        # LOAD COMMANDS
        # ====================================================================
        print(f"Loading commands from {args.commands}...")
        commands_data = load_json(args.commands)
        commands = CommandsDoc.model_validate(commands_data)
        print(f"✓ Loaded {len(commands.commands)} commands")
        
        # ====================================================================
        # COMPILE TO ACTIONS
        # ====================================================================
        print("\nCompiling commands to actions...")
        actions_doc, warnings = compile_to_actions(
            commands=commands,
            catalog_parts=parts_by_id,
            snapshot=snapshot,
        )
        
        print(f"✓ Generated {len(actions_doc.actions)} actions")
        
        if warnings:
            print(f"\nCompilation warnings ({len(warnings)}):")
            for warn in warnings:
                print(f"  - {warn}")
        
        # ====================================================================
        # WRITE ACTIONS
        # ====================================================================
        print(f"\nWriting actions to {args.out}...")
        actions_dict = actions_doc.model_dump(mode='json', by_alias=True)
        write_json(args.out, actions_dict)
        print(f"✓ Actions written to {args.out}")
        
        print("\n✓ Compilation successful!")
        return 0
    
    except ValueError as e:
        # Validation errors or compilation errors
        print(f"\n✗ Compilation failed:\n{e}", file=sys.stderr)
        return 1
    
    except FileNotFoundError as e:
        print(f"\n✗ File not found: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
