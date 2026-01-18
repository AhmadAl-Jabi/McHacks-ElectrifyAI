#!/usr/bin/env python
"""Test RAG threshold and debug logging."""

import asyncio
import logging
import os
import sys

# Add parent directories to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.agent_runtime import RAG

# Enable logging to see RAG debug output
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    # Test queries with different likelihood of having evidence
    test_queries = [
        "Design a robotics power board with LiPo protection",  # Should match power docs
        "CAN bus termination and biasing",  # Should match comms docs  
        "Completely unrelated topic xyz abc def",  # Should have low scores
    ]
    
    print("=" * 80)
    print("RAG RETRIEVAL TEST WITH THRESHOLD")
    print("=" * 80)
    print(f"Threshold: 0.30 (default)")
    print(f"RAG_DEBUG: {os.getenv('RAG_DEBUG', 'false')}")
    print()
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 80)
        results = RAG.retrieve(query, top_k=3)
        
        if results:
            print(f"Retrieved {len(results)} evidences:")
            for i, evidence in enumerate(results, 1):
                print(f"  [{i}] {evidence.metadata.get('doc_id')} | "
                      f"topic={evidence.metadata.get('topic')} | "
                      f"page={evidence.metadata.get('page_number')} | "
                      f"score={evidence.score:.3f}")
        else:
            print("No evidence retrieved (below threshold or no matches)")

if __name__ == "__main__":
    asyncio.run(main())
