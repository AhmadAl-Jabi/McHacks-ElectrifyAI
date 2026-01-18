"""
Catalog query: keyword-based relevance search for parts.

Helps narrow down large catalogs to relevant parts before sending to LLM.
"""
import re


# Common stop words to ignore in search queries
# Note: Excludes technical acronyms like "CAN" (Controller Area Network)
STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 
    'to', 'was', 'will', 'with', 'me', 'my', 'we', 'you', 'i', 'this',
    'but', 'or', 'if', 'when', 'where', 'how', 'why', 'could',
    'would', 'should', 'do', 'does', 'did', 'have', 'had', 'been',
    'being', 'am', 'so', 'than', 'too', 'very', 'just', 'some', 'any',
    'all', 'both', 'each', 'few', 'more', 'most', 'other', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'build', 'make', 'create',
    'add', 'use', 'need', 'want', 'get', 'put', 'give', 'take', 'utilize'
}


def _normalize_token(token: str) -> str:
    """
    Normalize a token by removing common plural suffixes.
    
    Examples:
        resistors → resistor
        capacitors → capacitor
        switches → switch
        boxes → box
    """
    # Remove trailing 's' for simple plurals
    if token.endswith('s') and len(token) > 3:
        # Handle -ies → -y (e.g., batteries → battery)
        if token.endswith('ies') and len(token) > 4:
            return token[:-3] + 'y'
        # Handle -es → -e or nothing (e.g., switches → switch, boxes → box)
        elif token.endswith('es') and len(token) > 3:
            # Try removing just 's' first, keep the 'e'
            return token[:-1]
        # Handle -ses → -s (e.g., buses → bus)
        elif token.endswith('ses') and len(token) > 4:
            return token[:-2]
        # Simple -s removal (resistors → resistor)
        else:
            return token[:-1]
    return token


def _calculate_token_weight(token: str) -> float:
    """
    Calculate importance weight for a token.
    Longer technical terms are more specific and valuable.
    
    Returns:
        Weight multiplier (1.0 to 3.0)
    """
    length = len(token)
    if length >= 8:  # Technical terms like "transceiver", "microcontroller"
        return 3.0
    elif length >= 6:  # Medium terms like "resistor", "circuit"
        return 2.0
    elif length >= 4:  # Short terms like "chip", "gate"
        return 1.5
    else:  # Very short (probably filtered as stop words anyway)
        return 1.0


def find_relevant_parts(
    parts_by_id: dict[str, dict],
    user_request: str,
    max_items: int = 30,
    min_score: float = 1.0
) -> list[str]:
    """
    Find relevant parts using weighted keyword overlap heuristic.
    
    Relevance scoring (with token weight multiplier):
    - Exact deviceset match: +10 points (e.g., "MCP2551" matches exactly)
    - Token in deviceset: +5 × weight
    - Exact MPN match: +8 points
    - Token in MPN: +4 × weight
    - Token in description: +3 × weight
    - Token in keywords: +3 × weight per match
    - Token in kind: +2 × weight
    - Multi-word phrase match in description: +5 bonus
    - Token in library: +1 × weight
    
    Token weights (longer = more specific):
    - 8+ chars: 3.0× (e.g., "transceiver", "microcontroller")
    - 6-7 chars: 2.0× (e.g., "resistor", "circuit")
    - 4-5 chars: 1.5× (e.g., "chip", "gate")
    - <4 chars: 1.0× (filtered if stop word)
    
    Args:
        parts_by_id: Catalog parts index (from index_parts)
        user_request: User's natural language request
        max_items: Maximum number of part_ids to return
        min_score: Minimum score to include a part (filters noise)
        
    Returns:
        List of part_ids sorted by relevance score (highest first)
        Returns ALL parts if no matches found (fallback to full catalog)
    """
    if not user_request or not user_request.strip():
        return list(parts_by_id.keys())
    
    # Tokenize user request (lowercase alphanumeric tokens)
    raw_tokens = re.findall(r'\b\w+\b', user_request.lower())
    
    # Filter stop words and normalize for plurals
    filtered_tokens = [t for t in raw_tokens if t not in STOP_WORDS]
    normalized_tokens = [_normalize_token(t) for t in filtered_tokens]
    
    # Keep both normalized and original for matching
    query_tokens = set(normalized_tokens)
    if not query_tokens:
        return list(parts_by_id.keys())
    
    # Build token weights map
    token_weights = {token: _calculate_token_weight(token) for token in query_tokens}
    
    # Extract multi-word technical phrases (2-3 words) from non-stop-word tokens
    technical_phrases = []
    for i in range(len(filtered_tokens) - 1):
        # Normalize both tokens for matching
        token1_norm = _normalize_token(filtered_tokens[i])
        token2_norm = _normalize_token(filtered_tokens[i + 1])
        phrase = token1_norm + ' ' + token2_norm
        if len(phrase) >= 6:  # Lower threshold to catch "can transceiver"
            technical_phrases.append(phrase)
        
        if i < len(filtered_tokens) - 2:
            token3_norm = _normalize_token(filtered_tokens[i + 2])
            phrase3 = phrase + ' ' + token3_norm
            if len(phrase3) >= 12:
                technical_phrases.append(phrase3)
    
    scored_results = []
    
    for part_id, part in parts_by_id.items():
        score = 0.0
        
        # Extract fields for scoring
        deviceset = part.get("deviceset", "").lower()
        # Try both "description" and "short_description" fields
        description = part.get("short_description", "") or part.get("description", "")
        description = description.lower()
        keywords = [k.lower() for k in part.get("keywords", [])]
        mpn = part.get("mpn", "").lower()
        kind = part.get("kind", "").lower()
        library = part.get("library", "").lower()
        
        # Multi-word phrase matching FIRST (highest priority for specific terms)
        phrase_bonus = 0.0
        for phrase in technical_phrases:
            if phrase in description:
                # Huge bonus for multi-word technical phrases in description
                phrase_bonus += 15.0
            if phrase in deviceset:
                # Even bigger bonus for phrase in deviceset
                phrase_bonus += 20.0
        score += phrase_bonus
        
        # Check for exact single-token matches (still important but lower than phrases)
        for token in query_tokens:
            # Exact deviceset match (full match)
            if token == deviceset or token in deviceset.split():
                score += 10.0
            
            # Exact MPN match
            if token == mpn or token in mpn.split():
                score += 8.0
        
        # Weighted token matching (still valuable for single keywords)
        for token in query_tokens:
            weight = token_weights.get(token, 1.0)
            
            # Deviceset match (highest priority - often contains part number/type)
            if token in deviceset:
                score += 5.0 * weight
            
            # MPN match
            if token in mpn:
                score += 4.0 * weight
            
            # Description match (good for functional matches like "CAN transceiver")
            if token in description:
                score += 3.0 * weight
            
            # Keywords match
            if any(token in kw for kw in keywords):
                score += 3.0 * weight
            
            # Kind match (resistor, capacitor, ic, etc.)
            if token in kind:
                score += 2.0 * weight
            
            # Library match (lower priority)
            if token in library:
                score += 1.0 * weight
        
        if score >= min_score:
            scored_results.append((part_id, score))
    
    # Sort by score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    # Extract top part_ids
    top_part_ids = [part_id for part_id, _ in scored_results[:max_items]]
    
    # Fallback: if no matches found, return all parts (agent can still search)
    if not top_part_ids:
        return list(parts_by_id.keys())
    
    return top_part_ids


def search_parts_by_keyword(
    parts_by_id: dict[str, dict],
    keyword: str,
    max_results: int = 10
) -> list[dict]:
    """
    Simple exact keyword search in part descriptions and devicesets.
    
    Args:
        parts_by_id: Catalog parts index
        keyword: Case-insensitive keyword to search for
        max_results: Maximum number of results
        
    Returns:
        List of part dictionaries with catalog_id, deviceset, description
    """
    keyword_lower = keyword.lower()
    results = []
    
    for part_id, part in parts_by_id.items():
        deviceset = part.get("deviceset", "").lower()
        description = part.get("short_description", "").lower()
        
        if keyword_lower in deviceset or keyword_lower in description:
            results.append({
                "catalog_id": part_id,
                "deviceset": part.get("deviceset", ""),
                "description": part.get("short_description", ""),
                "kind": part.get("kind", "")
            })
            
            if len(results) >= max_results:
                break
    
    return results
