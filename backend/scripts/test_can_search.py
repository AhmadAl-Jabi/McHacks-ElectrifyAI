#!/usr/bin/env python3
"""Test CAN search to debug why ISO1050 isn't being found."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.catalog.loader import load_catalog
from src.ecop_schematic_copilot.catalog.index import index_parts
from src.ecop_schematic_copilot.catalog.query import find_relevant_parts
import re


def _normalize_token(token: str) -> str:
    """Same as in query.py"""
    if token.endswith('s') and len(token) > 3:
        if token.endswith('ies') and len(token) > 4:
            return token[:-3] + 'y'
        elif token.endswith('es') and len(token) > 3:
            return token[:-1]
        elif token.endswith('ses') and len(token) > 4:
            return token[:-2]
        else:
            return token[:-1]
    return token


user_request = "Build me a CAN bus interface circuit with level shifters"
print(f"User request: {user_request}\n")

# Tokenize
raw_tokens = re.findall(r'\b\w+\b', user_request.lower())
query_tokens = set(_normalize_token(t) for t in raw_tokens)
print(f"Query tokens (normalized): {query_tokens}\n")

# Load catalog
catalog_path = Path(__file__).parent.parent / 'assets' / 'catalog.json'
catalog = load_catalog(str(catalog_path))
parts_by_id, _ = index_parts(catalog)

# Get ISO1050 part
iso_part = parts_by_id.get('ISO1050DUB*@ECOP_IC_Interface')
if not iso_part:
    print("ERROR: ISO1050 not found in catalog!")
    sys.exit(1)

print(f"ISO1050 part:")
print(f"  catalog_id: {iso_part.get('catalog_id')}")
print(f"  deviceset: {iso_part.get('deviceset')}")
print(f"  description: {iso_part.get('description', '')[:80]}...")
print(f"  keywords: {iso_part.get('keywords')}")
print()

# Manual scoring
deviceset = iso_part.get("deviceset", "").lower()
description = (iso_part.get("short_description", "") or iso_part.get("description", "")).lower()
keywords = [k.lower() for k in iso_part.get("keywords", [])]
mpn = iso_part.get("mpn", "").lower()
kind = iso_part.get("kind", "").lower()
library = iso_part.get("library", "").lower()

score = 0
matches = []

for token in query_tokens:
    if token in deviceset:
        score += 3
        matches.append(f"{token} in deviceset (+3)")
    if token in description:
        score += 2
        matches.append(f"{token} in description (+2)")
    if any(token in kw for kw in keywords):
        score += 2
        matches.append(f"{token} in keywords (+2)")
    if token in mpn:
        score += 2
        matches.append(f"{token} in mpn (+2)")
    if token in kind:
        score += 1
        matches.append(f"{token} in kind (+1)")
    if token in library:
        score += 1
        matches.append(f"{token} in library (+1)")

print(f"Manual scoring:")
print(f"  Total score: {score}")
print(f"  Matches:")
for m in matches:
    print(f"    - {m}")
print()

# Now run the actual function
relevant = find_relevant_parts(parts_by_id, user_request, max_items=200)
iso_in_results = 'ISO1050DUB*@ECOP_IC_Interface' in relevant

print(f"find_relevant_parts results:")
print(f"  Total relevant parts: {len(relevant)}")
print(f"  ISO1050 in results: {iso_in_results}")
if iso_in_results:
    idx = relevant.index('ISO1050DUB*@ECOP_IC_Interface')
    print(f"  ISO1050 rank: #{idx + 1}")
else:
    print(f"  Top 10 results:")
    for i, part_id in enumerate(relevant[:10], 1):
        print(f"    {i}. {part_id}")
