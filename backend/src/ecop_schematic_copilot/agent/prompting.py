"""
Agent prompting builder: constructs grounded, strict prompts for schematic agents.

No LLM calls here - only prompt construction.
"""
import re
from typing import Any


def build_catalog_candidates(catalog_json: dict) -> list[dict]:
    """
    Build compact catalog candidates list for Gumloop and Gemini.
    
    Extracts only essential fields needed for:
    - Gumloop: selecting suggested_catalog_ids based on user request
    - Gemini: generating correct ADD actions using fusion_add
    
    Args:
        catalog_json: Full catalog dictionary with "parts" key
        
    Returns:
        List of compact part dictionaries with essential fields:
        - catalog_id: Unique identifier (key for lookup)
        - kind: Part type (resistor, capacitor, ic, generic, etc.)
        - description: Short description (HTML stripped, max 200 chars)
        - keywords: Search keywords (list of strings)
        - fusion_add: Fusion ADD command string (critical for Actions IR)
        - pins: List of pin names (if available)
    """
    parts_dict = catalog_json.get("parts", {})
    candidates = []
    
    for part_id, part_data in parts_dict.items():
        # Essential fields only - keep it compact
        candidate = {
            "catalog_id": part_id,  # Key identifier
            "kind": part_data.get("kind", "unknown"),
            "fusion_add": part_data.get("fusion_add", f"ADD {part_id}"),  # Critical for Actions IR
        }
        
        # Description (strip HTML, truncate if too long)
        if "description" in part_data:
            desc = part_data["description"]
            desc = re.sub(r'<[^>]+>', '', desc)  # Remove HTML tags
            desc = desc.strip()
            if len(desc) > 200:
                desc = desc[:200] + "..."
            candidate["description"] = desc
        elif "short_description" in part_data:
            desc = part_data["short_description"]
            desc = re.sub(r'<[^>]+>', '', desc)
            desc = desc.strip()
            if len(desc) > 200:
                desc = desc[:200] + "..."
            candidate["description"] = desc
        
        # Keywords for search/matching
        if "keywords" in part_data:
            candidate["keywords"] = part_data["keywords"]
        
        # Pins (needed for validation and connection generation)
        if "pins" in part_data:
            candidate["pins"] = part_data["pins"]
        
        # Optional: MPN for additional context (only if present)
        if "mpn" in part_data:
            candidate["mpn"] = part_data["mpn"]
        
        candidates.append(candidate)
    
    return candidates


def build_allowed_parts_packet(
    parts_by_id: dict[str, dict],
    allowed_ids: list[str]
) -> list[dict]:
    """
    Build allowed parts packet for agent context.
    
    Extracts essential fields for each allowed part to give the agent
    what it needs to make decisions without overwhelming it with full catalog.
    
    Args:
        parts_by_id: Full catalog parts index
        allowed_ids: List of part_ids to include in packet
        
    Returns:
        List of part dictionaries with essential fields only
    """
    packet = []
    
    for part_id in allowed_ids:
        if part_id not in parts_by_id:
            continue
        
        part = parts_by_id[part_id]
        
        # Extract essential fields
        # Use part_id as catalog_id (the key is the canonical identifier)
        part_info = {
            "catalog_id": part_id,
            "kind": part.get("kind", "unknown"),
            "library": part.get("library", ""),
            "deviceset": part.get("deviceset", ""),
            "pins": part.get("pins", []),
            "set_value": part.get("set_value", False),
        }
        
        # Optional fields
        if "keywords" in part:
            part_info["keywords"] = part["keywords"]
        
        if "short_description" in part:
            # Strip HTML tags if present
            desc = part["short_description"]
            desc = re.sub(r'<[^>]+>', '', desc)  # Remove HTML tags
            desc = desc.strip()
            part_info["short_description"] = desc
        
        if "mpn" in part:
            part_info["mpn"] = part["mpn"]
        
        packet.append(part_info)
    
    return packet


def build_system_instructions(snapshot: dict = None) -> str:
    """
    Build system instructions with hard rules for agent behavior.
    
    Args:
        snapshot: Current schematic snapshot (used to determine mode)
    
    Returns:
        System instruction string with strict requirements
    """
    # Determine mode based on snapshot
    has_components = snapshot and len(snapshot.get("components", [])) > 0
    mode = "EDIT" if has_components else "CREATE"
    
    mode_specific_rules = ""
    if mode == "EDIT":
        # Extract existing context for EDIT mode
        existing_refdes = [c.get("refdes", "") for c in snapshot.get("components", [])]
        existing_nets = [n.get("net_name", "") for n in snapshot.get("nets", [])]
        
        mode_specific_rules = f"""
=== MODE: EDIT ===
You are EDITING an existing schematic with {len(existing_refdes)} components.

CRITICAL RULES FOR EDIT MODE:
1. Existing component refdes: {', '.join(existing_refdes[:30])}{'...' if len(existing_refdes) > 30 else ''}
2. Existing net names: {', '.join(existing_nets[:20])}{'...' if len(existing_nets) > 20 else ''}
3. PREFER existing net names when connecting (reuse VCC, GND, SDA, SCL, etc. from above)
4. When referencing components, ONLY use refdes from the existing list above
5. DO NOT invent/assume components (e.g., MCU, microcontroller) unless visible in snapshot
6. If adding new components, use new refdes that don't collide with existing
7. If user asks to modify/connect to a component, verify it exists in snapshot first
"""
    else:
        mode_specific_rules = """
=== MODE: CREATE ===
You are CREATING a new schematic from scratch.

RULES FOR CREATE MODE:
1. Generate new refdes following convention: R1, R2, C1, C2, U1, U2, etc.
2. Use standard net names: VCC, GND, VDD, VSS, SDA, SCL, TX, RX, etc.
3. Ensure no duplicate refdes in your command list
4. All components must be added before they can be connected
"""
    
    return f"""You are an EDA (Electronic Design Automation) schematic design assistant.
You help users design circuits in a friendly, conversational way.

=== CONVERSATION STYLE ===
- Be natural and conversational - you're talking to a user, not writing a technical report
- For greetings or casual messages, respond warmly without mentioning technical details
- Only explain technical decisions when the user is making changes to the schematic
- Don't say things like "I understand the user provided..." - speak directly to the user
- Examples:
  * User: "Hello" → You: "Hi! I'm here to help you design your schematic. What would you like to work on?"
  * User: "Add a resistor" → You: "I've added a 10kΩ resistor R1 to your schematic."
  * User: "Why did you use that value?" → You: "I chose 10kΩ as a standard pull-up resistor value..."

{mode_specific_rules}

=== ALLOWED PARTS ===
You may ONLY use parts from the ALLOWED_PARTS section in the user message below.
- Use the EXACT catalog_id string (e.g., "ICS-43432@ECOP_Audio-Devices")
- DO NOT shorten, modify, or make up part_id values
- Only use pins that exist in the part's pins list
- If a required part is missing, output a comment command explaining what's needed

=== DESIGN PRIMITIVES (OPTIONAL GUIDANCE) ===
If DESIGN_PRIMITIVES section is provided, you may use these validated circuit patterns
as guidance, but you MUST implement them using parts from ALLOWED_PARTS.

=== REFDES RULES ===
For CREATE mode (no snapshot):
- Generate new refdes following convention: R1, R2, C1, C2, U1, U2, etc.
- Ensure no duplicates within your command list

For EDIT mode (snapshot provided):
- Only reference existing refdes from snapshot.components
- Generate new refdes that don't collide with existing
- Never reference refdes that doesn't exist

=== COMMANDS IR SCHEMA ===
Root structure: {{"commands": [...]}}

Each command: {{"op": "operation_name", "args": {{...}}}}

Available operations:

1. add_component
   {{"op": "add_component", "args": {{"part_id": "exact_catalog_id", "refdes": "R1"}}}}

2. remove_component
   {{"op": "remove_component", "args": {{"refdes": "R1"}}}}

3. create_net (optional - nets auto-created on connect)
   {{"op": "create_net", "args": {{"net_name": "VDD"}}}}

4. rename_net
   {{"op": "rename_net", "args": {{"from": "OLD_NET", "to": "NEW_NET"}}}}

5. connect
   {{"op": "connect", "args": {{"refdes": "U1", "pin": "VDD", "net_name": "3V3"}}}}
   
   IMPORTANT: DO NOT use connect with power symbols (GND, VCC, VDD, VBUS, etc. from ECOP_Power_Symbols)
   Power symbols have no pins and auto-connect by their net name. Just add them - no connect needed.

6. disconnect
   {{"op": "disconnect", "args": {{"refdes": "U1", "pin": "VDD", "net_name": "3V3"}}}}

7. set_value (only if part.set_value == true)
   {{"op": "set_value", "args": {{"refdes": "R1", "value": "10k"}}}}
   
   IMPORTANT: DO NOT use set_value on power symbols (GND, VCC, VDD, etc. from ECOP_Power_Symbols)
   Power symbols are not parameterized and don't have values. Only set values on resistors, capacitors, etc.

8. place_component (optional)
   {{"op": "place_component", "args": {{"refdes": "R1", "x": 50.0, "y": 50.0, "rotation": 0.0, "layer": "Top"}}}}

9. place_near (optional - place relative to anchor)
   {{"op": "place_near", "args": {{"refdes": "R1", "anchor_refdes": "U1", "dx": 20.0, "dy": -10.0, "rotation": 0.0, "layer": "Top"}}}}

10. comment (when request is impossible)
    {{"op": "comment", "args": {{"text": "Missing parts: [list needed parts]"}}}}

=== YOUR WORKFLOW ===
1. Interpret the user's request
2. Check if all required parts exist in ALLOWED_PARTS
3. If impossible: output single comment command explaining missing parts
4. If possible: generate complete command sequence:
   a) Add all required components (use EXACT catalog_id)
   b) Set values for components that allow it
   c) Create connections between components and nets
   d) Optionally place components
5. Validate before outputting:
   - All part_id values are EXACT matches from ALLOWED_PARTS
   - All pins exist for their respective parts
   - All refdes references are valid
   - set_value only used on parts with set_value==true
6. Output ONLY valid JSON (no markdown, no code blocks, no extra text)

=== VALIDATION RULES ===
- All add_component.part_id must be in ALLOWED_PARTS (exact string match)
- All pins must exist in the part's pins list
- set_value only allowed if part.set_value == true
- For EDIT mode: all refdes must exist in snapshot or be newly added
- No duplicate refdes in your command list

=== OUTPUT FORMAT ===
You MUST return a JSON object with TWO fields:

1. "explanation" - A conversational explanation of what you're doing and why
2. "commands" - The JSON commands array

Format:
{{
  "explanation": "I'm adding a microcontroller U1 and connecting it to power. I'm using the STM32F401 because...",
  "commands": [
    {{"op": "add_component", "args": {{"part_id": "EXACT_CATALOG_ID", "refdes": "U1"}}}},
    {{"op": "connect", "args": {{"refdes": "U1", "pin": "VDD", "net_name": "3V3"}}}},
    ...
  ]
}}

For casual conversation (no schematic changes):
{{
  "explanation": "Hi! I'm here to help you design your schematic. What would you like to work on?",
  "commands": []
}}

If request is impossible:
{{
  "explanation": "I cannot complete this request because the required ICS-43432 microphone is not available in the catalog.",
  "commands": [
    {{"op": "comment", "args": {{"text": "Missing parts: ICS-43432 microphone not in catalog"}}}}
  ]
}}

EXPLANATION GUIDELINES:
- Speak directly to the user in a natural, friendly way
- For casual messages (greetings, questions), just respond conversationally - no need to mention commands
- For design requests, briefly explain what you did and why
- Don't say "The user provided..." or "I understand that..." - you're having a conversation
- Examples:
  * Greeting: "Hi! I'm ready to help you design your circuit. What would you like to create?"
  * Simple request: "I've added a 10kΩ resistor R1 between the microcontroller and power supply to act as a pull-up."
  * Complex request: "I've set up a voltage divider using R1 (10kΩ) and R2 (10kΩ) to halve your input voltage. The output appears between the resistors at the 'VOUT' net."

Remember: You're a helpful assistant having a conversation, not writing technical documentation."""


def build_user_message(
    user_request: str,
    snapshot: dict,
    allowed_parts_packet: list[dict],
    primitives_excerpt: list[dict],
    rag_context: str = "",
    context_pack: str = "",
    allowed_catalog_ids: list[str] = None
) -> str:
    """
    Build structured user message with all context embedded.
    
    Args:
        user_request: User's natural language request
        snapshot: Snapshot document as dict (may be empty for create mode)
        allowed_parts_packet: List of allowed parts from build_allowed_parts_packet()
        primitives_excerpt: List of relevant primitive excerpts from query
        rag_context: Optional RAG-retrieved design knowledge context
        context_pack: Optional Gumloop context string (added verbatim)
        allowed_catalog_ids: Optional Gumloop-suggested catalog ID list for restriction
        
    Returns:
        Formatted user message with embedded context
    """
    sections = []
    
    # ========================================================================
    # CONTEXT PACK (GUMLOOP PRE-PROCESSOR)
    # ========================================================================
    if context_pack:
        sections.append("=== CONTEXT PACK ===")
        sections.append("Additional context from pre-processor analysis:\n")
        sections.append(context_pack.strip())
        sections.append("")
    
    # ========================================================================
    # USER REQUEST
    # ========================================================================
    sections.append("=== USER REQUEST ===")
    sections.append(user_request.strip())
    sections.append("")
    
    # ========================================================================
    # RAG DESIGN KNOWLEDGE (OPTIONAL)
    # ========================================================================
    if rag_context:
        sections.append("=== DESIGN KNOWLEDGE ===")
        sections.append("Relevant design guidelines retrieved from technical documentation:\n")
        sections.append(rag_context)
        sections.append("")
    
    # ========================================================================
    # SNAPSHOT (CURRENT SCHEMATIC STATE)
    # ========================================================================
    has_components = snapshot and len(snapshot.get("components", [])) > 0
    mode = "EDIT" if has_components else "CREATE"
    
    sections.append("=== CURRENT SNAPSHOT ===")
    sections.append(f"MODE: {mode}")
    sections.append("")
    
    if has_components:
        # EDIT mode - show full context
        components = snapshot.get("components", [])
        nets = snapshot.get("nets", [])
        
        sections.append(f"Snapshot contains {len(components)} components and {len(nets)} nets.")
        sections.append("")
        
        # List ALL existing refdes (critical for validation)
        sections.append("EXISTING COMPONENT REFDES (use these when referencing existing parts):")
        all_refdes = [c.get("refdes", "?") for c in components]
        sections.append(f"  {', '.join(all_refdes)}")
        sections.append("")
        
        # List ALL existing net names (critical for reuse)
        sections.append("EXISTING NET NAMES (PREFER reusing these when making connections):")
        all_nets = [n.get("net_name", "?") for n in nets]
        sections.append(f"  {', '.join(all_nets)}")
        sections.append("")
        
        sections.append("Component Details:")
        for comp in components[:20]:  # Show first 20 components in detail
            refdes = comp.get("refdes", "?")
            part_id = comp.get("part_id", "?")
            value = comp.get("value", "")
            pins = comp.get("pins", [])
            sections.append(f"  - {refdes}: {part_id}")
            if value:
                sections.append(f"      value: {value}")
            if pins:
                pins_str = ", ".join(pins[:10])  # First 10 pins
                if len(pins) > 10:
                    pins_str += f" ... ({len(pins)} total)"
                sections.append(f"      pins: [{pins_str}]")
        
        if len(components) > 20:
            sections.append(f"  ... and {len(components) - 20} more components (see refdes list above)")
        
        sections.append("")
        sections.append("Net Connection Details:")
        for net in nets[:15]:  # Show first 15 nets in detail
            net_name = net.get("net_name", "?")
            connections = net.get("connections", [])
            sections.append(f"  - {net_name}: {len(connections)} connections")
            for conn in connections[:5]:  # First 5 connections
                sections.append(f"      {conn.get('refdes', '?')}.{conn.get('pin', '?')}")
            if len(connections) > 5:
                sections.append(f"      ... and {len(connections) - 5} more")
        
        if len(nets) > 15:
            sections.append(f"  ... and {len(nets) - 15} more nets (see net names list above)")
    else:
        # CREATE mode - empty schematic
        sections.append("Empty schematic - no existing components or nets.")
        sections.append("You are starting from scratch.")
    
    sections.append("")
    
    # ========================================================================
    # ALLOWED PARTS
    # ========================================================================
    sections.append("=== ALLOWED PARTS ===")
    
    # Show ALLOWED_CATALOG_IDS restriction if Gumloop provided suggestions
    if allowed_catalog_ids:
        sections.append("=== ALLOWED_CATALOG_IDS (RESTRICTION) ===")
        sections.append(f"Pre-processor has suggested {len(allowed_catalog_ids)} catalog IDs for this request:")
        sections.append(", ".join(allowed_catalog_ids))
        sections.append("")
        sections.append("CRITICAL INSTRUCTION: You MUST ONLY use parts with catalog_id values in the ALLOWED_CATALOG_IDS list above.")
        sections.append("Do not use any other parts from the full catalog, even if they appear below.")
        sections.append("")
    
    if allowed_parts_packet:
        sections.append(f"You may use ONLY these {len(allowed_parts_packet)} parts:\n")
        for part in allowed_parts_packet:  # Show ALL parts (no truncation)
            catalog_id = part.get("catalog_id", "?")
            kind = part.get("kind", "?")
            pins = part.get("pins", [])
            set_value = part.get("set_value", False)
            
            sections.append(f"- catalog_id: {catalog_id}")
            sections.append(f"  kind: {kind}")
            sections.append(f"  library: {part.get('library', '')}")
            sections.append(f"  deviceset: {part.get('deviceset', '')}")
            sections.append(f"  set_value: {set_value}")
            sections.append(f"  pins: [{', '.join(pins)}]")
            
            if "short_description" in part:
                sections.append(f"  description: {part['short_description'][:100]}")
            if "mpn" in part:
                sections.append(f"  mpn: {part['mpn']}")
            if "keywords" in part:
                kw_str = ", ".join(part["keywords"][:5])
                sections.append(f"  keywords: {kw_str}")
            sections.append("")
        
        if len(allowed_parts_packet) > 100:
            sections.append(f"... and {len(allowed_parts_packet) - 100} more parts")
    else:
        sections.append("WARNING: No parts available!")
        sections.append("You must output a comment command explaining missing parts.")
    sections.append("")
    
    # ========================================================================
    # PRIMITIVES GUIDANCE (OPTIONAL)
    # ========================================================================
    if primitives_excerpt:
        sections.append("=== DESIGN PRIMITIVES (GUIDANCE) ===")
        sections.append("These validated circuit patterns may help guide your design:\n")
        for prim in primitives_excerpt[:5]:  # Limit to first 5
            sections.append(f"- id: {prim.get('id', '?')}")
            sections.append(f"  name: {prim.get('name', '?')}")
            sections.append(f"  intent: {prim.get('intent', '')[:150]}")
            sections.append(f"  category: {prim.get('category', '')}")
            if "ports" in prim:
                sections.append(f"  ports: {', '.join(prim['ports'][:5])}")
            if "connection_count" in prim:
                sections.append(f"  connection_count: {prim['connection_count']}")
            sections.append("")
        sections.append("Note: These are reference patterns. Use ALLOWED_PARTS for actual implementation.")
        sections.append("")
    
    # ========================================================================
    # TASK
    # ========================================================================
    sections.append("=== YOUR TASK ===")
    sections.append("Generate Commands IR JSON that fulfills the user request using ONLY allowed parts.")
    sections.append("CRITICAL: Use the EXACT catalog_id values shown above (including @library suffix).")
    sections.append("Output format: {\"commands\": [...]}")
    sections.append("")
    
    return "\n".join(sections)
