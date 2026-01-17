import argparse
import json
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

def build_add_token(deviceset: str, device_name: str) -> str:
    device_name = (device_name or "").strip()
    if device_name:
        return f"{deviceset}_{device_name}"
    return deviceset

def pick_add_name(ds_name: str, default_device_name: str, tech_attrs: dict) -> str:
    # Prefer real manufacturer part number if provided
    mpn = (tech_attrs.get("MPN") or tech_attrs.get("MANUFACTURER_PART_NUMBER") or "").strip()
    if mpn:
        return mpn

    # Otherwise fall back to deviceset + variant if variant exists
    default_device_name = (default_device_name or "").strip()
    if default_device_name:
        return f"{ds_name}_{default_device_name}"

    # Last resort
    return ds_name



def find_library_node(root: ET.Element) -> ET.Element:
    lib = root.find(".//drawing/library")
    if lib is None:
        lib = root.find(".//library")
    if lib is None:
        raise ValueError("Could not find <library> node. Not an EAGLE .lbr XML.")
    return lib


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def infer_kind(prefix: str, deviceset_name: str, description: str) -> str:
    name = (deviceset_name or "").upper()
    desc = (description or "").upper()
    p = (prefix or "").upper()

    # quick pattern-based inference
    if p == "R" or name.startswith("R") or "RESIST" in name or "RESIST" in desc:
        return "resistor"
    if p == "C" or name.startswith("C") or "CAPAC" in name or "CAPAC" in desc:
        return "capacitor"
    if p == "L" or name.startswith("L") or "INDUCT" in name or "CHOKE" in name or "INDUCT" in desc:
        return "inductor"
    if p == "D" or name.startswith("D") or "DIODE" in name or "TVS" in name or "ESD" in desc:
        return "diode"
    if p in ("Q",) or "TRANSIST" in desc or "MOSFET" in desc or "BJT" in desc:
        return "transistor"
    if p in ("U", "IC") or "TRANSCEIVER" in desc or "REGULATOR" in desc or "OPAMP" in desc:
        return "ic"
    if p in ("J", "P", "X") or "CONN" in name or "CONNECT" in desc or "HEADER" in desc:
        return "connector"

    return "generic"


def set_value_allowed(kind: str) -> bool:
    return kind in {"resistor", "capacitor", "inductor"}  # keep it simple


def extract_gate_symbols(deviceset_node: ET.Element) -> List[str]:
    symbols: List[str] = []
    gates = deviceset_node.find("gates")
    if gates is None:
        return symbols
    for gate in gates.findall("gate"):
        sym = gate.get("symbol", "")
        if sym:
            symbols.append(sym)
    return symbols


def extract_pins_from_connects(device_node: ET.Element) -> List[str]:
    pins: List[str] = []
    connects = device_node.find("connects")
    if connects is None:
        return pins
    for c in connects.findall("connect"):
        pin = c.get("pin", "")
        if pin:
            pins.append(pin)
    # de-dup preserving order
    seen = set()
    out = []
    for p in pins:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def parse_one_lbr(lbr_path: Path) -> Tuple[Dict[str, Any], int, int]:
    tree = ET.parse(str(lbr_path))
    root = tree.getroot()
    lib_node = find_library_node(root)

    lib_name = lib_node.get("name") or lbr_path.stem
    lib_desc = clean_text(lib_node.findtext("description") or "")

    devicesets_node = lib_node.find("devicesets")
    if devicesets_node is None:
        return {"library": {"name": lib_name, "description": lib_desc}, "parts": []}, 0, 0

    parts: List[Dict[str, Any]] = []
    total_devicesets = 0
    kept_devicesets = 0

    for ds in devicesets_node.findall("deviceset"):
        total_devicesets += 1

        ds_name = ds.get("name", "")
        ds_prefix = ds.get("prefix", "")
        ds_desc = clean_text(ds.findtext("description") or "")

        # require at least one device variant
        devices_node = ds.find("devices")
        if devices_node is None:
            continue

        device_variants = devices_node.findall("device")
        if not device_variants:
            continue

        # Choose the first device variant as the default
        default_device = device_variants[0]
        default_device_name = default_device.get("name", "")
        default_package = default_device.get("package", "")

        # Pin names from connects of the chosen device
        pins = extract_pins_from_connects(default_device)

        # Pick default technology attributes (first technology if present)
        tech_attrs = {}
        techs_node = default_device.find("technologies")
        if techs_node is not None:
            first_tech = techs_node.find("technology")
            if first_tech is not None:
                for a in first_tech.findall("attribute"):
                    key = a.get("name", "")
                    if key:
                        tech_attrs[key] = a.get("value", "")

        add_name = pick_add_name(ds_name, default_device_name, tech_attrs)


        # If no connects pins, still keep the part, but pins list will be empty
        # (you can later fill pins by probing a placed instance if needed)

        kind = infer_kind(ds_prefix, ds_name, ds_desc or lib_desc)
        #add_token = build_add_token(ds_name, default_device_name)
        entry = {
            # Using the @ style you want (this is also convenient for Fusion ADD syntax)
            "catalog_id": f"{ds_name}@{lib_name}",
            "library": lib_name,
            "deviceset": ds_name,
            "kind": kind,
            "description": ds_desc or lib_desc,
            # Deterministic placement string
            
            "fusion_add": f"ADD {add_name}@{lib_name}",
            "add_name": add_name,
            "mpn": tech_attrs.get("MPN", ""),

            # If you later need exact variant handling, you already have this recorded
            "default_variant": {
                "device_name": default_device_name,
                "package": default_package,
            },
            "set_value": set_value_allowed(kind),
            "pins": pins,
            # Cheap keywords for matching without an LLM
            "keywords": [ds_name, kind, ds_prefix, default_package, default_device_name]

        }

        # remove empty keyword strings
        entry["keywords"] = [k for k in entry["keywords"] if k]

        parts.append(entry)
        kept_devicesets += 1

    return {
        "library": {"name": lib_name, "description": lib_desc, "source_file": lbr_path.name},
        "parts": parts,
    }, total_devicesets, kept_devicesets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Paths to .lbr files or folders containing .lbr files")
    parser.add_argument("--out", default="catalog.json", help="Output catalog JSON path")
    args = parser.parse_args()

    lbr_files: List[Path] = []
    for item in args.inputs:
        p = Path(item)
        if p.is_dir():
            lbr_files.extend(sorted(p.glob("*.lbr")))
        else:
            lbr_files.append(p)

    if not lbr_files:
        raise SystemExit("No .lbr files found.")

    catalog_parts: Dict[str, Any] = {}
    libraries: List[Dict[str, Any]] = []
    stats = {"total_devicesets": 0, "kept_devicesets": 0, "duplicates_skipped": 0}

    for lbr_path in lbr_files:
        parsed, total_ds, kept_ds = parse_one_lbr(lbr_path)
        libraries.append(parsed["library"])
        stats["total_devicesets"] += total_ds
        stats["kept_devicesets"] += kept_ds

        for part in parsed["parts"]:
            cid = part["catalog_id"]
            if cid in catalog_parts:
                # same catalog_id from multiple files: keep first, skip the rest
                stats["duplicates_skipped"] += 1
                continue
            catalog_parts[cid] = part

    out_obj = {
        "schema_version": 1,
        "libraries": libraries,
        # Hashmap for O(1) lookup
        "parts": catalog_parts,
        "stats": stats,
    }

    Path(args.out).write_text(json.dumps(out_obj, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Parts: {len(catalog_parts)} | Devicesets kept: {stats['kept_devicesets']} | Duplicates skipped: {stats['duplicates_skipped']}")


if __name__ == "__main__":
    main()
