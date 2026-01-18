#!/usr/bin/env python
"""Test agent and show what context was injected."""

import asyncio
import os
import sys

# Add parent directories to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.agent_runtime import RAG, PRIMITIVES, run_agent

async def main():
    query = """Design a robotics power board input stage for 6S LiPo (nom 22.2V, max 25.2V). 
I need reverse polarity protection, surge protection, and a protected 12V rail at 8A. 
Provide selected primitive IDs, parameters, and net connections."""
    
    print("=" * 80)
    print("STEP 1: PRIMITIVE SEARCH")
    print("=" * 80)
    matches = PRIMITIVES.search(query, top_k=5)
    print(f"Found {len(matches)} matching primitives:")
    for match in matches:
        print(f"  - {match.primitive['id']} (score: {match.score:.2f})")
    
    print("\n" + "=" * 80)
    print("STEP 2: RAG EVIDENCE SEARCH")
    print("=" * 80)
    rag_results = RAG.retrieve(query, top_k=3)
    print(f"Found {len(rag_results)} RAG chunks:")
    for i, result in enumerate(rag_results, 1):
        print(f"  [{i}] {result.metadata.get('doc_id')} (page {result.metadata.get('page_number')}, score: {result.score:.3f})")
        print(f"      Topic: {result.metadata.get('topic')}")
        print(f"      Preview: {result.text[:100]}...")
    
    print("\n" + "=" * 80)
    print("STEP 3: RUN AGENT")
    print("=" * 80)
    response = await run_agent(query)
    
    print(f"\nAgent response length: {len(response['reply'])} chars")
    print(f"First 300 chars of reply:")
    print(response['reply'][:300] + "...\n")

if __name__ == "__main__":
    asyncio.run(main())
