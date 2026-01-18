#!/usr/bin/env python
"""Test agent with a real design query."""

import asyncio
import json
import os
import sys

# Add parent directories to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.agent_runtime import run_agent

test_queries = ["""Design a robotics power board input stage for 6S LiPo (nom 22.2V, max 25.2V). 
I need reverse polarity protection, surge protection, and a protected 12V rail at 8A. 
Provide selected primitive IDs, parameters, and net connections.""",
"""Create a CAN bus transceiver interface circuit for a microcontroller.
Include termination resistors and ESD protection""",
"""Design an isolated RS-485 transceiver circuit with biasing resistors
suitable for industrial environments.""",
"""Create a UART interface circuit with level shifting from 3.3V to 5V
and ESD protection for a microcontroller.""",]


async def main():
    query = test_queries[1]
    
    print("=" * 80)
    print("QUERY:")
    print("=" * 80)
    print(query)
    print("\n" + "=" * 80)
    print("AGENT RESPONSE:")
    print("=" * 80 + "\n")
    
    response = await run_agent(query)
    
    print(f"REPLY:\n{response['reply']}\n")
    
    # Validate primitive instances if present
    print("\n" + "=" * 80)
    print("VALIDATION: PRIMITIVES")
    print("=" * 80)
    primitive_found = False
    for action in response.get('actions', []):
        payload = action.get('payload', {})
        if 'primitive_id' in payload:
            primitive_found = True
            instances = payload.get('primitive_instances', [])
            assert instances, "ERROR: primitive_id present but primitive_instances is empty"
            assert len(instances) > 0, "ERROR: primitive_instances must be non-empty"
            
            # Validate each instance
            for idx, instance in enumerate(instances):
                assert 'port_map' in instance, f"ERROR: instance {idx} missing port_map"
                assert isinstance(instance['port_map'], dict), f"ERROR: instance {idx} port_map not a dict"
                assert len(instance['port_map']) > 0, f"ERROR: instance {idx} port_map is empty"
                
                assert 'connections' in instance, f"ERROR: instance {idx} missing connections"
                assert isinstance(instance['connections'], list), f"ERROR: instance {idx} connections not a list"
                assert len(instance['connections']) > 0, f"ERROR: instance {idx} connections list is empty"
            
            # Print preview
            first_instance = instances[0]
            print(f"✓ Found primitive instances")
            print(f"  First instance ID: {first_instance.get('id', 'N/A')}")
            print(f"  Number of connections: {len(first_instance.get('connections', []))}")
            print(f"  First 5 connections:")
            for conn in first_instance.get('connections', [])[:5]:
                print(f"    - {conn}")
    
    if not primitive_found:
        print("⚠ No primitive_id found in actions (agent may not have selected primitives)")
    
    # Validate RAG evidence
    print("\n" + "=" * 80)
    print("VALIDATION: RAG EVIDENCE")
    print("=" * 80)
    reply = response.get('reply', '')
    citations_found = any(f"[{i}]" in reply for i in range(1, 10))
    no_evidence_msg = "No relevant RAG evidence retrieved" in reply
    
    if citations_found:
        print("✓ Citations found in reply (agent referenced RAG evidence)")
    elif no_evidence_msg:
        print("✓ Reply explicitly states no RAG evidence retrieved")
    else:
        print("⚠ No citations or explicit 'no evidence' message (RAG may have returned empty results)")
    
    if response['actions']:
        print(f"\nACTIONS ({len(response['actions'])}):")
        for i, action in enumerate(response['actions'], 1):
            print(f"  [{i}] {action.get('type', 'unknown')}: {action.get('label', 'no label')}")
    
    if response['artifacts']:
        print(f"\nARTIFACTS ({len(response['artifacts'])}):")
        for i, artifact in enumerate(response['artifacts'], 1):
            print(f"  [{i}] {artifact.get('type', 'unknown')}: {artifact.get('label', 'no label')}")

if __name__ == "__main__":
    asyncio.run(main())
