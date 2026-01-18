"""
Primitives query: simple keyword-based relevance search (no agent calls).

Returns small excerpts, not full primitive definitions.
"""
import re


def find_relevant_primitives(
    primitives: dict,
    user_request: str,
    max_items: int = 5
) -> list[dict]:
    """
    Find relevant primitives using simple keyword overlap heuristic.
    
    Relevance scoring:
    - Token appears in primitive name: +3 points
    - Token appears in primitive id: +2 points
    - Token appears in intent: +2 points
    - Token appears in tags/evidence_topics: +1 point per match
    - Token appears in category: +1 point
    
    Args:
        primitives: Loaded primitives dictionary with "primitives" list
        user_request: User's natural language request
        max_items: Maximum number of results to return
        
    Returns:
        List of primitive excerpts (small summaries), sorted by relevance
    """
    if not user_request or not user_request.strip():
        return []
    
    primitives_list = primitives.get("primitives", [])
    if not primitives_list:
        return []
    
    # Tokenize user request (lowercase alphanumeric tokens)
    query_tokens = set(re.findall(r'\b\w+\b', user_request.lower()))
    if not query_tokens:
        return []
    
    scored_results = []
    
    for prim in primitives_list:
        if not isinstance(prim, dict):
            continue
        
        score = 0
        
        # Extract fields for scoring
        prim_id = prim.get("id", "").lower()
        prim_name = prim.get("name", "").lower()
        prim_intent = prim.get("intent", "").lower()
        prim_category = prim.get("category", "").lower()
        prim_tags = [t.lower() for t in prim.get("tags", [])]
        prim_topics = [t.lower() for t in prim.get("evidence_topics", [])]
        
        # Score each query token
        for token in query_tokens:
            # Name match (highest priority)
            if token in prim_name:
                score += 3
            
            # ID match
            if token in prim_id:
                score += 2
            
            # Intent match
            if token in prim_intent:
                score += 2
            
            # Tags/topics match
            if any(token in tag for tag in prim_tags):
                score += 1
            if any(token in topic for topic in prim_topics):
                score += 1
            
            # Category match
            if token in prim_category:
                score += 1
        
        if score > 0:
            # Create excerpt (small summary)
            excerpt = {
                "id": prim.get("id"),
                "name": prim.get("name"),
                "intent": prim.get("intent", "")[:200],  # Truncate intent
                "category": prim.get("category"),
                "ports": [p.get("name") for p in prim.get("ports", [])[:5]],  # First 5 ports
                "score": score,
            }
            
            # Include parameters if present (keys only)
            if "parameters" in prim and prim["parameters"]:
                excerpt["parameters"] = list(prim["parameters"].keys())[:5]
            
            # Include connection count (not full list)
            connections = prim.get("connections", [])
            if connections:
                excerpt["connection_count"] = len(connections)
            
            scored_results.append(excerpt)
    
    # Sort by score descending
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    # Return top max_items (remove score from output)
    results = scored_results[:max_items]
    for r in results:
        r.pop("score", None)
    
    return results
