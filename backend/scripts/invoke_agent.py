"""
Test agent by actually calling LLM and generating commands.

Usage:
    python backend/scripts/invoke_agent.py "Add ICS-43432 microphone. Connect VDD to 3V3 and GND to GND."
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ecop_schematic_copilot.catalog import load_catalog, index_parts, find_relevant_parts
from src.ecop_schematic_copilot.primitives import load_primitives, find_relevant_primitives
from src.ecop_schematic_copilot.agent import (
    build_allowed_parts_packet,
    build_system_instructions,
    build_user_message,
)
from src.ecop_schematic_copilot.domain import CommandsDoc
from src.ecop_schematic_copilot.compile import compile_to_actions, format_validation
from src.ecop_schematic_copilot.io import write_json
from src.rag.retriever import RAGRetriever

# Load environment
load_dotenv(override=True)


def invoke_agent_gemini(system_instructions: str, user_message: str) -> str:
    """Invoke Google Gemini API to generate commands."""
    import google.generativeai as genai
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment")
    
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_instructions,
    )
    
    response = model.generate_content(
        user_message,
        generation_config=genai.GenerationConfig(
            temperature=0.0,  # Deterministic for schema compliance
        ),
    )
    
    return response.text


def test_full_pipeline(user_request: str, catalog_path: str, primitives_path: str = None):
    """
    Full pipeline test: prompt → LLM → parse → validate → compile.
    
    Args:
        user_request: User's natural language request
        catalog_path: Path to catalog.json
        primitives_path: Optional path to primitives JSON
    """
    print("=" * 80)
    print("FULL AGENT PIPELINE TEST")
    print("=" * 80)
    print(f"\nUser request: {user_request}")
    
    # ========================================================================
    # STEP 1: Load catalog
    # ========================================================================
    print(f"\n[1/7] Loading catalog from {catalog_path}...")
    catalog = load_catalog(catalog_path)
    parts_by_id, warnings = index_parts(catalog)
    print(f"✓ Loaded {len(parts_by_id)} parts")
    
    # ========================================================================
    # STEP 2: Filter relevant parts (pre-search)
    # ========================================================================
    print("\n[2/7] Finding relevant parts from catalog...")
    relevant_part_ids = find_relevant_parts(parts_by_id, user_request, max_items=100)
    print(f"✓ Filtered to {len(relevant_part_ids)} relevant parts (from {len(parts_by_id)} total)")
    
    # ========================================================================
    # STEP 3: Build allowed parts packet
    # ========================================================================
    print("\n[3/7] Building allowed parts packet...")
    allowed_parts_packet = build_allowed_parts_packet(parts_by_id, relevant_part_ids)
    print(f"✓ Built packet with {len(allowed_parts_packet)} parts")
    
    # ========================================================================
    # STEP 4: Load primitives (optional)
    # ========================================================================
    primitives_excerpt = []
    if primitives_path and Path(primitives_path).exists():
        print(f"\n[4/7] Loading primitives from {primitives_path}...")
        primitives = load_primitives(primitives_path)
        primitives_excerpt = find_relevant_primitives(primitives, user_request, max_items=3)
        print(f"✓ Found {len(primitives_excerpt)} relevant primitives")
    else:
        print("\n[4/7] Skipping primitives (no path provided)")
    
    # ========================================================================
    # STEP 5: RAG Retrieval
    # ========================================================================
    print("\n[5/8] Retrieving design knowledge from RAG...")
    rag_context = ""
    try:
        print("  Initializing RAG retriever...")
        retriever = RAGRetriever()
        if retriever.enabled:
            print("  Querying vector database...")
            evidences = retriever.retrieve(user_request, top_k=5, use_topic_hint=True)
            print(f"✓ Retrieved {len(evidences)} relevant chunks")
            if evidences:
                rag_context = retriever.render_for_prompt(evidences, max_chars=8000)
                print(f"  RAG context: {len(rag_context)} chars")
        else:
            print("  RAG disabled or unavailable")
    except KeyboardInterrupt:
        print("\n⚠ RAG retrieval interrupted by user")
        rag_context = ""
    except Exception as e:
        print(f"⚠ RAG retrieval failed (continuing without): {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================================================
    # STEP 6: Build prompts
    # ========================================================================
    print("\n[6/8] Building agent prompts...")
    snapshot = {"components": [], "nets": []}  # Empty for CREATE mode
    system_instructions = build_system_instructions(snapshot=snapshot)
    user_message = build_user_message(
        user_request=user_request,
        snapshot=snapshot,
        allowed_parts_packet=allowed_parts_packet,
        primitives_excerpt=primitives_excerpt,
        rag_context=rag_context,
    )
    print(f"✓ System instructions: {len(system_instructions)} chars")
    print(f"✓ User message: {len(user_message)} chars")
    
    # ========================================================================
    # STEP 7: Invoke LLM
    # ========================================================================
    print("\n[7/8] Invoking Google Gemini API...")
    try:
        llm_response = invoke_agent_gemini(system_instructions, user_message)
        print(f"✓ Received response: {len(llm_response)} chars")
        
        # Save raw response
        output_dir = Path("agent_test_output")
        output_dir.mkdir(exist_ok=True)
        with open(output_dir / "llm_raw_response.txt", "w", encoding="utf-8") as f:
            f.write(llm_response)
        print(f"  Saved raw response to {output_dir / 'llm_raw_response.txt'}")
        
    except Exception as e:
        print(f"✗ LLM invocation failed: {e}")
        return
    
    # ========================================================================
    # STEP 8: Parse and validate commands
    # ========================================================================
    print("\n[8/8] Parsing and validating commands...")
    try:
        # Try to parse JSON (strip markdown if present)
        cleaned_response = llm_response.strip()
        if cleaned_response.startswith("```"):
            # Remove markdown code blocks
            lines = cleaned_response.split("\n")
            cleaned_response = "\n".join([l for l in lines if not l.startswith("```")])
        
        commands_data = json.loads(cleaned_response)
        commands_doc = CommandsDoc.model_validate(commands_data)
        
        print(f"✓ Parsed {len(commands_doc.commands)} commands")
        
        # Save commands
        write_json(str(output_dir / "commands_generated.json"), commands_data)
        print(f"  Saved to {output_dir / 'commands_generated.json'}")
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON parsing failed: {e}")
        print(f"  Response preview: {llm_response[:200]}...")
        return
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return
    
    # ========================================================================
    # STEP 8: Compile to actions
    # ========================================================================
    print("\n[8/8] Compiling to actions...")
    try:
        actions_doc, compile_warnings = compile_to_actions(
            commands=commands_doc,
            catalog_parts=parts_by_id,
            snapshot=None,
        )
        
        print(f"✓ Generated {len(actions_doc.actions)} actions")
        
        if compile_warnings:
            print(f"\nCompilation warnings ({len(compile_warnings)}):")
            for warn in compile_warnings[:5]:
                print(f"  - {warn}")
            if len(compile_warnings) > 5:
                print(f"  ... and {len(compile_warnings) - 5} more")
        
        # Save actions
        actions_data = actions_doc.model_dump(mode='json', by_alias=True)
        write_json(str(output_dir / "actions_generated.json"), actions_data)
        print(f"  Saved to {output_dir / 'actions_generated.json'}")
        
        # Show action types
        action_types = [a.type for a in actions_doc.actions]
        print(f"\nAction sequence: {' → '.join(action_types)}")
        
    except ValueError as e:
        print(f"✗ Compilation failed:\n{e}")
        return
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========================================================================
    # SUCCESS
    # ========================================================================
    print("\n" + "=" * 80)
    print("✓ PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"\nGenerated files in {output_dir}:")
    print(f"  - llm_raw_response.txt")
    print(f"  - commands_generated.json")
    print(f"  - actions_generated.json")
    print("\nYou can now execute actions_generated.json with the Fusion adapter.")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/invoke_agent.py <user_request>")
        print('Example: python backend/scripts/invoke_agent.py "Add ICS-43432 microphone"')
        sys.exit(1)
    
    user_request = sys.argv[1]
    catalog_path = "backend/assets/catalog.json"
    primitives_path = "backend/assets/primitives/circuit_primitives_robust_v0_2.json"
    
    test_full_pipeline(user_request, catalog_path, primitives_path)
