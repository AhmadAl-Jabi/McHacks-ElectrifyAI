"""
Agent runtime: orchestrates the full pipeline for production use.

This is called by app.py to handle chat requests from the Fusion UI.
"""
import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import google.generativeai as genai

# Import new architecture modules
from backend.src.ecop_schematic_copilot.catalog import load_catalog, index_parts, find_relevant_parts
from backend.src.ecop_schematic_copilot.primitives import load_primitives, find_relevant_primitives
from backend.src.ecop_schematic_copilot.agent import (
    build_catalog_candidates,
    build_allowed_parts_packet,
    build_system_instructions,
    build_user_message,
)
from backend.src.ecop_schematic_copilot.domain import CommandsDoc
from backend.src.ecop_schematic_copilot.compile import compile_to_actions
from backend.src.rag.retriever import RAGRetriever
from backend.gumloop_client import call_gumloop

load_dotenv(override=True)

# Configure logging
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRIMITIVES_PATH = os.getenv(
    "PRIMITIVES_PATH",
    str(PROJECT_ROOT / "backend" / "assets" / "primitives" / "circuit_primitives_robust_v0_2.json"),
)

DEFAULT_CATALOG_PATH = os.getenv(
    "CATALOG_PATH",
    str(PROJECT_ROOT / "backend" / "assets" / "catalog.json"),
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment")

genai.configure(api_key=GOOGLE_API_KEY)

# Gumloop configuration
GUMLOOP_WEBHOOK_URL = os.getenv("GUMLOOP_WEBHOOK_URL")
GUMLOOP_ENABLED = os.getenv("GUMLOOP_ENABLED", "true" if GUMLOOP_WEBHOOK_URL else "false").lower() == "true"
GUMLOOP_SEND_CATALOG = os.getenv("GUMLOOP_SEND_CATALOG", "false").lower() == "true"  # Default: don't send catalog
GUMLOOP_TIMEOUT = float(os.getenv("GUMLOOP_TIMEOUT", "75.0"))  

# Gumloop only enabled if both URL exists and ENABLED flag is true
GUMLOOP_ENABLED = GUMLOOP_ENABLED and bool(GUMLOOP_WEBHOOK_URL)


# -----------------------------------------------------------------------------
# Helper: Invoke Gemini
# -----------------------------------------------------------------------------
def _invoke_gemini(system_instructions: str, user_message: str) -> str:
    """Call Google Gemini API and return raw response text."""
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


# -----------------------------------------------------------------------------
# Main Agent Pipeline
# -----------------------------------------------------------------------------
async def run_agent(
    user_message: str,
    snapshot: Optional[Dict[str, Any]] = None,
    catalog_path: Optional[str] = None,
    primitives_path: Optional[str] = None,
    max_parts: int = 100,
    max_primitives: int = 3,
) -> Dict[str, Any]:
    """
    Full agent pipeline: filters catalog → builds prompts → calls LLM → validates → compiles.
    
    Args:
        user_message: User's natural language request
        snapshot: Current schematic snapshot (dict with components/nets)
                  REQUIRED - should be loaded by caller from SnapshotStore
        catalog_path: Path to catalog.json
        primitives_path: Path to primitives JSON
        max_parts: Maximum number of relevant parts to send to LLM (increased to 100 for better coverage)
        max_primitives: Maximum number of relevant primitives to send to LLM
        
    Returns:
        Dict with:
            - commands: List of command dicts (Commands IR)
            - actions: List of action dicts (Actions IR)
            - reply: Human-readable summary message
            - artifacts: List of artifact dicts (for future use)
    """
    # Snapshot should always be provided by caller (from SnapshotStore)
    # If missing, use empty snapshot but log warning
    if snapshot is None:
        logger.warning("[Agent] No snapshot provided - using empty snapshot (CREATE mode)")
        snapshot = {"components": [], "nets": []}
    else:
        num_components = len(snapshot.get("components", []))
        num_nets = len(snapshot.get("nets", []))
        logger.info(f"[Agent] Using snapshot context: {num_components} components, {num_nets} nets")
    
    catalog_path = catalog_path or DEFAULT_CATALOG_PATH
    primitives_path = primitives_path or DEFAULT_PRIMITIVES_PATH
    
    try:
        # ====================================================================
        # STEP 1: Load catalog (send entire catalog to LLM)
        # ====================================================================
        catalog = load_catalog(catalog_path)
        parts_by_id, catalog_warnings = index_parts(catalog)
        
        # Use ALL parts from catalog (no filtering)
        relevant_part_ids = list(parts_by_id.keys())
        logger.info(f"[Catalog] Loaded {len(relevant_part_ids)} parts (entire catalog)")
        
        # ====================================================================
        # STEP 2: Load primitives and find relevant patterns
        # ====================================================================
        # DISABLED: Testing performance without primitives
        primitives_excerpt = []
        # if Path(primitives_path).exists():
        #     primitives = load_primitives(primitives_path)
        #     primitives_excerpt = find_relevant_primitives(primitives, user_message, max_items=max_primitives)
        
        # ====================================================================
        # STEP 3: Retrieve RAG design knowledge
        # ====================================================================
        rag_context = ""
        try:
            rag_retriever = RAGRetriever()
            rag_results = rag_retriever.retrieve(user_message, top_k=5, use_topic_hint=True)
            if rag_results:
                rag_context = rag_retriever.render_for_prompt(rag_results, max_chars=8000)
        except Exception as e:
            # RAG failure shouldn't break the pipeline
            print(f"Warning: RAG retrieval failed: {e}")
        
        # ====================================================================
        # STEP 3.5: Gumloop webhook (BEFORE Gemini - context enrichment & filtering)
        # ====================================================================
        gumloop_context = ""
        gumloop_filtered_ids = None
        gumloop_enabled = GUMLOOP_ENABLED
        
        if gumloop_enabled:
            # Only build catalog if configured to send it
            catalog_candidates = build_catalog_candidates(catalog) if GUMLOOP_SEND_CATALOG else []
            
            if GUMLOOP_SEND_CATALOG:
                logger.info(f"[Gumloop] Calling webhook with {len(catalog_candidates)} catalog entries")
            else:
                logger.info(f"[Gumloop] Calling webhook (catalog NOT sent - stored in Gumloop)")
            
            # Call Gumloop with prompt, snapshot, and optional catalog
            gumloop_response = await call_gumloop(
                user_message=user_message,
                snapshot=snapshot,
                catalog_candidates=catalog_candidates
            )
            
            # Always returns GumloopResponse (empty on failure)
            gumloop_context = gumloop_response.context_pack
            
            # Log what Gumloop actually returned (DETAILED)
            logger.info(f"[Gumloop] === RESPONSE DETAILS ===")
            logger.info(f"[Gumloop] context_pack length: {len(gumloop_context)}")
            logger.info(f"[Gumloop] suggested_catalog_ids count: {len(gumloop_response.suggested_catalog_ids)}")
            if gumloop_response.suggested_catalog_ids:
                logger.info(f"[Gumloop] Suggested IDs: {gumloop_response.suggested_catalog_ids}")
            if gumloop_context:
                logger.info(f"[Gumloop] Context preview: {gumloop_context[:200]}...")
            
            # Use Gumloop's suggested catalog IDs if provided and valid
            if gumloop_response.suggested_catalog_ids:
                # Validate that suggested IDs exist in catalog
                valid_ids = [
                    pid for pid in gumloop_response.suggested_catalog_ids
                    if pid in parts_by_id
                ]
                if valid_ids:
                    gumloop_filtered_ids = valid_ids
                    logger.info(f"[Gumloop] Filtering catalog to {len(valid_ids)} suggested IDs for Gemini")
                else:
                    logger.warning("[Gumloop] No valid catalog IDs in response, using full catalog for Gemini")
        
        # Use Gumloop-filtered IDs if available, otherwise use all
        if gumloop_filtered_ids:
            relevant_part_ids = gumloop_filtered_ids
        
        # ====================================================================
        # STEP 4: Build prompts (with Gumloop-filtered catalog if available)
        # ====================================================================
        allowed_parts_packet = build_allowed_parts_packet(parts_by_id, relevant_part_ids)
        system_instructions = build_system_instructions(snapshot=snapshot)
        user_prompt = build_user_message(
            user_request=user_message,
            snapshot=snapshot,
            allowed_parts_packet=allowed_parts_packet,
            primitives_excerpt=primitives_excerpt,
            rag_context=rag_context,
            context_pack=gumloop_context,  # Pass Gumloop context pack
            allowed_catalog_ids=gumloop_filtered_ids  # Pass Gumloop catalog ID restrictions
        )
        
        # ====================================================================
        # STEP 5: Invoke Gemini (with Gumloop context embedded in prompt)
        # ====================================================================
        llm_response = _invoke_gemini(system_instructions, user_prompt)
        
        # ====================================================================
        # STEP 6: Parse and validate LLM output
        # ====================================================================
        # LLM must return: {"explanation": "text", "commands": [...]}
        cleaned_response = llm_response.strip()
        if cleaned_response.startswith("```"):
            lines = cleaned_response.split("\n")
            cleaned_response = "\n".join([l for l in lines if not l.startswith("```")])
        
        try:
            response_data = json.loads(cleaned_response)
            
            # Extract explanation and commands (always expect this format)
            if not isinstance(response_data, dict):
                raise ValueError(f"Expected dict with 'explanation' and 'commands', got {type(response_data)}")
            
            explanation = response_data.get("explanation", "")
            commands_list = response_data.get("commands", [])
            
            # Validate commands structure
            commands_doc = CommandsDoc.model_validate({"commands": commands_list})
                
        except json.JSONDecodeError as e:
            return {
                "commands": [],
                "actions": [],
                "reply": f"Error: Agent produced invalid JSON: {e}",
                "artifacts": [],
            }
        except Exception as e:
            return {
                "commands": [],
                "actions": [],
                "reply": f"Error: Failed to parse agent output: {e}",
                "artifacts": [],
            }
        
        # ====================================================================
        # STEP 7: Compile to actions
        # ====================================================================
        try:
            # Pass snapshot to compiler
            from backend.src.ecop_schematic_copilot.domain import SnapshotDoc
            
            snapshot_for_compile = None
            if snapshot and snapshot.get("components"):
                snapshot_for_compile = SnapshotDoc(**snapshot)
            
            logger.info(f"[Compile] Using snapshot: {len(snapshot.get('components', []))} components")
            
            actions_doc, compile_warnings = compile_to_actions(
                commands=commands_doc,
                catalog_parts=parts_by_id,
                snapshot=snapshot_for_compile,
            )
            
            # Convert to plain dicts for API response
            commands_list_out = commands_doc.model_dump(mode='json', by_alias=True).get("commands", [])
            actions_list = actions_doc.model_dump(mode='json', by_alias=True).get("actions", [])
            
            # Use LLM's explanation as the reply
            reply = explanation if explanation else "Done."
            
            if compile_warnings:
                reply += f"\n\n⚠️ Note: {len(compile_warnings)} warning(s) during compilation."
            
            return {
                "commands": commands_list_out,
                "actions": actions_list,
                "reply": reply,
                "artifacts": [],
                "_debug": {
                    "gumloop_enabled": gumloop_enabled,
                    "gumloop_suggested_ids_count": len(gumloop_filtered_ids) if gumloop_filtered_ids else 0,
                    "gumloop_context_len": len(gumloop_context)
                }
            }
            
        except Exception as e:
            return {
                "commands": commands_doc.model_dump(mode='json', by_alias=True).get("commands", []),
                "actions": [],
                "reply": f"{explanation}\n\n⚠️ Error during compilation: {e}" if explanation else f"Error: Compilation failed - {e}",
                "artifacts": [],
            }
    
    except Exception as e:
        # Catch-all for unexpected errors
        import traceback
        error_detail = traceback.format_exc()
        return {
            "commands": [{"op": "comment", "args": {"text": f"Internal error: {e}"}}],
            "actions": [],
            "reply": f"Error: {e}",
            "artifacts": [],
        }
