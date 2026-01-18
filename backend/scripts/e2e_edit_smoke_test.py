"""
End-to-End Edit Mode Smoke Test

Tests that the agent can:
1. Read a live snapshot from bridge folder
2. Generate edit commands grounded in that snapshot
3. Compile to valid actions
4. Validate action ordering and refdes existence

Does NOT execute in Fusion - validation only.
"""
import json
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from src.snapshot import load_snapshot, get_snapshot_summary
from src.config.bridge import SNAPSHOT_PATH
from agent_runtime import run_agent
import asyncio


async def run_edit_test():
    """Run end-to-end edit mode smoke test."""
    print("=" * 70)
    print("E2E EDIT MODE SMOKE TEST")
    print("=" * 70)
    
    # ========================================================================
    # STEP 1: Load snapshot from bridge
    # ========================================================================
    print("\n[1/5] Loading snapshot from bridge...")
    
    if not SNAPSHOT_PATH.exists():
        print(f"❌ ERROR: Snapshot not found at {SNAPSHOT_PATH}")
        print("   Please export a snapshot from Fusion first.")
        return False
    
    snapshot_doc, warnings = load_snapshot(force_reload=True)
    summary = get_snapshot_summary()
    
    print(f"✓ Snapshot loaded: {summary['components']} components, {summary['nets']} nets")
    print(f"  Age: {summary.get('age_human', 'unknown')}")
    
    if warnings:
        print(f"  Warnings: {warnings}")
    
    if summary['components'] == 0:
        print("❌ ERROR: Snapshot is empty (CREATE mode)")
        print("   This test requires an existing schematic with components/nets.")
        return False
    
    snapshot_dict = snapshot_doc.model_dump(mode='json')
    
    # Show snapshot context
    print("\n  Existing components:")
    for comp in snapshot_dict.get("components", [])[:5]:
        print(f"    - {comp.get('refdes', '?')}: {comp.get('part_id', '?')}")
    if len(snapshot_dict.get("components", [])) > 5:
        print(f"    ... and {len(snapshot_dict['components']) - 5} more")
    
    print("\n  Existing nets:")
    for net in snapshot_dict.get("nets", [])[:5]:
        print(f"    - {net.get('net_name', '?')}")
    if len(snapshot_dict.get("nets", [])) > 5:
        print(f"    ... and {len(snapshot_dict['nets']) - 5} more")
    
    # ========================================================================
    # STEP 2: Build edit prompt
    # ========================================================================
    print("\n[2/5] Building edit prompt...")
    
    # Get first component and net for realistic edit
    first_comp = snapshot_dict["components"][0] if snapshot_dict.get("components") else None
    first_net = snapshot_dict["nets"][0] if snapshot_dict.get("nets") else None
    
    if not first_comp or not first_net:
        print("❌ ERROR: Need at least one component and one net for edit test")
        return False
    
    first_refdes = first_comp.get("refdes", "R1")
    first_net_name = first_net.get("net_name", "VDD")
    
    # Build edit prompt that references existing elements
    edit_prompt = f"Rename net {first_net_name} to POWER_3V3"
    
    # If component supports set_value, add that too
    if first_comp.get("part_id", "").startswith("R@") or "resistor" in first_comp.get("part_id", "").lower():
        edit_prompt += f" and set {first_refdes} to 10k"
    
    print(f"✓ Edit prompt: '{edit_prompt}'")
    print(f"  Targets: refdes={first_refdes}, net={first_net_name}")
    
    # ========================================================================
    # STEP 3: Invoke agent runtime
    # ========================================================================
    print("\n[3/5] Invoking agent runtime...")
    
    try:
        result = await run_agent(
            user_message=edit_prompt,
            snapshot=snapshot_dict,
            max_parts=50,
            max_primitives=0  # Skip primitives for speed
        )
        
        commands = result.get("commands", [])
        actions = result.get("actions", [])
        reply = result.get("reply", "")
        
        print(f"✓ Agent completed")
        print(f"  Reply: {reply}")
        print(f"  Generated {len(commands)} commands → {len(actions)} actions")
        
    except Exception as e:
        print(f"❌ ERROR: Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    if not actions:
        print("❌ ERROR: No actions generated")
        return False
    
    # ========================================================================
    # STEP 4: Display actions
    # ========================================================================
    print("\n[4/5] Generated actions:")
    for i, action in enumerate(actions, 1):
        action_type = action.get("type", "?")
        if action_type == "RENAME_NET":
            print(f"  {i}. RENAME_NET: {action.get('from_net')} → {action.get('to_net')}")
        elif action_type == "SET_VALUE":
            print(f"  {i}. SET_VALUE: {action.get('refdes')} = {action.get('value')}")
        elif action_type == "CONNECT":
            print(f"  {i}. CONNECT: {action.get('refdes')}.{action.get('pin')} → {action.get('net_name')}")
        elif action_type == "DISCONNECT":
            print(f"  {i}. DISCONNECT: {action.get('refdes')}.{action.get('pin')} ← {action.get('net_name')}")
        elif action_type == "ADD":
            print(f"  {i}. ADD: {action.get('refdes')} ({action.get('cmd', '?')})")
        else:
            print(f"  {i}. {action_type}: {action}")
    
    # ========================================================================
    # STEP 5: Validate actions
    # ========================================================================
    print("\n[5/5] Validating actions...")
    
    validation_passed = True
    
    # Check 1: RENAME_NET should appear before CONNECT/DISCONNECT
    rename_indices = [i for i, a in enumerate(actions) if a.get("type") == "RENAME_NET"]
    connect_indices = [i for i, a in enumerate(actions) if a.get("type") in ["CONNECT", "DISCONNECT"]]
    
    if rename_indices and connect_indices:
        max_rename_idx = max(rename_indices)
        min_connect_idx = min(connect_indices)
        
        if max_rename_idx > min_connect_idx:
            print("  ❌ FAIL: RENAME_NET appears after CONNECT/DISCONNECT")
            print(f"     Last rename at index {max_rename_idx}, first connect at {min_connect_idx}")
            validation_passed = False
        else:
            print("  ✓ PASS: RENAME_NET appears before CONNECT/DISCONNECT")
    elif rename_indices:
        print("  ✓ PASS: RENAME_NET present (no connects to check ordering)")
    else:
        print("  ⚠ SKIP: No RENAME_NET actions (not applicable)")
    
    # Check 2: SET_VALUE targets existing refdes
    existing_refdes = {c.get("refdes") for c in snapshot_dict.get("components", [])}
    set_value_actions = [a for a in actions if a.get("type") == "SET_VALUE"]
    
    for action in set_value_actions:
        target_refdes = action.get("refdes")
        if target_refdes in existing_refdes:
            print(f"  ✓ PASS: SET_VALUE targets existing refdes '{target_refdes}'")
        else:
            print(f"  ❌ FAIL: SET_VALUE targets unknown refdes '{target_refdes}'")
            print(f"     Existing refdes: {', '.join(sorted(existing_refdes))}")
            validation_passed = False
    
    if not set_value_actions:
        print("  ⚠ SKIP: No SET_VALUE actions (not applicable)")
    
    # Check 3: RENAME_NET targets existing net
    existing_nets = {n.get("net_name") for n in snapshot_dict.get("nets", [])}
    rename_actions = [a for a in actions if a.get("type") == "RENAME_NET"]
    
    for action in rename_actions:
        from_net = action.get("from_net")
        if from_net in existing_nets:
            print(f"  ✓ PASS: RENAME_NET targets existing net '{from_net}'")
        else:
            print(f"  ❌ FAIL: RENAME_NET targets unknown net '{from_net}'")
            print(f"     Existing nets: {', '.join(sorted(existing_nets))}")
            validation_passed = False
    
    # Check 4: No ADD commands for components already in snapshot (should use existing)
    add_actions = [a for a in actions if a.get("type") == "ADD"]
    for action in add_actions:
        added_refdes = action.get("refdes")
        if added_refdes in existing_refdes:
            print(f"  ⚠ WARNING: ADD action for existing refdes '{added_refdes}'")
            print(f"     Agent should reference existing components, not re-add them")
            # Don't fail, but warn
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    if validation_passed:
        print("✅ SMOKE TEST PASSED")
        print("   Edit mode is working correctly:")
        print("   - Snapshot loaded successfully")
        print("   - Agent generated grounded edit commands")
        print("   - Actions compiled successfully")
        print("   - Action ordering validated")
        print("   - Refdes/net references validated")
    else:
        print("❌ SMOKE TEST FAILED")
        print("   See validation errors above.")
    print("=" * 70)
    
    return validation_passed


if __name__ == "__main__":
    success = asyncio.run(run_edit_test())
    sys.exit(0 if success else 1)
