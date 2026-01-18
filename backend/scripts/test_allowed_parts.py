#!/usr/bin/env python3
"""Check if ISO1050 is in the allowed parts packet."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.catalog.loader import load_catalog
from src.ecop_schematic_copilot.catalog.index import index_parts
from src.ecop_schematic_copilot.catalog.query import find_relevant_parts
from src.ecop_schematic_copilot.agent.prompting import build_allowed_parts_packet

user_request = "Build me a CAN bus interface circuit"
catalog_path = Path(__file__).parent.parent / 'assets' / 'catalog.json'
catalog = load_catalog(str(catalog_path))
parts_by_id, _ = index_parts(catalog)

relevant_part_ids = find_relevant_parts(parts_by_id, user_request, max_items=100)
print(f"Relevant part IDs ({len(relevant_part_ids)} total):")
iso_in_relevant = [p for p in relevant_part_ids if 'ISO1050' in p]
print(f"ISO1050 in relevant_part_ids: {bool(iso_in_relevant)}")
if iso_in_relevant:
    print(f"  {iso_in_relevant}")

allowed_parts_packet = build_allowed_parts_packet(parts_by_id, relevant_part_ids)
print(f"\nAllowed parts packet ({len(allowed_parts_packet)} total):")
iso_in_packet = [p for p in allowed_parts_packet if 'ISO1050' in p.get('catalog_id', '')]
print(f"ISO1050 in allowed_parts_packet: {bool(iso_in_packet)}")
if iso_in_packet:
    for p in iso_in_packet:
        print(f"  catalog_id: {p.get('catalog_id')}")
        print(f"  kind: {p.get('kind')}")
        print(f"  description: {p.get('short_description', '')[:60]}...")
