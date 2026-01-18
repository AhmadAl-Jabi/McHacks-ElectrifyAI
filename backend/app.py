from fastapi import FastAPI
import logging
from backend.schemas import ChatRequest, ChatResponse, Action, Artifact
from backend.agent_runtime import run_agent
from backend.src.snapshot import load_snapshot, get_snapshot_summary
from backend.hidden.router import detect_hidden_circuit
from backend.hidden.demo_pipeline import run_hidden_demo

app = FastAPI()

# Configure logging
logger = logging.getLogger(__name__)

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    # ====================================================================
    # HIDDEN MODE: Check if prompt triggers a prebuilt circuit demo
    # ====================================================================
    # If triggered, runs Gumloop + Gemini for explanation, then loads .sch file
    # NO Commands IR, NO validation, NO compilation, NO executor
    circuit_id = detect_hidden_circuit(req.message)
    
    if circuit_id:
        logger.info(f"[HiddenMode] Detected trigger for: {circuit_id}")
        
        try:
            # Load current snapshot BEFORE running demo
            snapshot_doc, warnings = load_snapshot(force_reload=True)
            if warnings:
                logger.warning(f"[Snapshot] Warnings: {warnings}")
            
            current_snapshot = snapshot_doc.model_dump(mode='json')
            
            # Run HIDDEN MODE pipeline:
            # 1. Get current snapshot_summary
            # 2. Call Gumloop (prompt + snapshot_summary, NO catalog)
            # 3. Call Gemini (explanation ONLY, NOT Commands IR)
            # 4. Load .sch file into workspace
            demo_result = await run_hidden_demo(
                prompt=req.message,
                circuit_id=circuit_id,
                current_snapshot=current_snapshot
            )
            
            reply = demo_result["reply"]
            actions = demo_result.get("actions", [])
            meta = demo_result.get("meta", {})
            
            # Log demo pipeline details
            logger.info(
                f"[HiddenMode] Pipeline complete: "
                f"circuit={meta.get('circuit_id')}, "
                f"actions={len(actions)}, "
                f"gemini_used={meta.get('gemini_used')}, "
                f"suggested_ids={len(meta.get('suggested_catalog_ids', []))}"
            )
            
            # Return explanation with actions to execute
            return ChatResponse(
                reply=reply,
                actions=actions,  # Actions for Fusion to place components
                artifacts=[]
            )
            
        except Exception as e:
            logger.error(f"[HiddenMode] Pipeline failed for {circuit_id}: {e}", exc_info=True)
            # Fall through to normal pipeline if demo fails
    
    # ====================================================================
    # NORMAL PIPELINE: Standard agent reasoning and execution
    # ====================================================================
    # If no hidden circuit triggered, proceed with normal flow
    
    # ====================================================================
    # CRITICAL: Load snapshot before agent reasoning
    # ====================================================================
    # This ensures the agent sees the current schematic state
    # Snapshot is exported by Fusion add-in on every user message
    snapshot_doc, warnings = load_snapshot(force_reload=True)
    summary = get_snapshot_summary()
    
    # Log snapshot details
    logger.info(f"[Snapshot] Loaded: {summary['components']} components, {summary['nets']} nets")
    logger.info(f"[Snapshot] Age: {summary.get('age_human', 'unknown')}")
    logger.info(f"[Snapshot] Reason: {summary.get('reason', 'unknown')}")
    
    if warnings:
        logger.warning(f"[Snapshot] Warnings: {warnings}")
    
    if summary['components'] == 0 and summary['nets'] == 0:
        logger.warning("[Snapshot] Empty snapshot - agent will operate in CREATE mode")
    
    # Convert snapshot to dict for agent
    snapshot_dict = snapshot_doc.model_dump(mode='json')
    
    # ====================================================================
    # Run agent with guaranteed snapshot context
    # ====================================================================
    data = await run_agent(req.message, snapshot=snapshot_dict)
    
    # Debug log for Gumloop integration
    debug_info = data.get("_debug", {})
    logger.info(
        f"[Gumloop] enabled={debug_info.get('gumloop_enabled', False)}, "
        f"suggested_ids={debug_info.get('gumloop_suggested_ids_count', 0)}, "
        f"context_len={debug_info.get('gumloop_context_len', 0)}"
    )

    reply = data.get("reply", "")
    actions_raw = data.get("actions", []) or []
    artifacts_raw = data.get("artifacts", []) or []
    
    # Wrap flat actions in API schema: {id, type, label, payload}
    # agent_runtime returns flat dicts like: {type: "ADD", cmd: "...", refdes: "..."}
    # API expects: {id: "...", type: "ADD", label: "...", payload: {...}}
    actions = []
    for i, action in enumerate(actions_raw):
        action_type = action.get("type", "UNKNOWN")
        
        # Generate label from action
        if action_type == "ADD":
            label = f"ADD {action.get('refdes', '?')}"
        elif action_type == "SET_VALUE":
            label = f"SET_VALUE {action.get('refdes', '?')} = {action.get('value', '?')}"
        elif action_type == "PLACE":
            label = f"PLACE {action.get('refdes', '?')} at ({action.get('x', 0)}, {action.get('y', 0)})"
        elif action_type == "CONNECT":
            label = f"CONNECT {action.get('refdes', '?')}.{action.get('pin', '?')} to {action.get('net_name', '?')}"
        elif action_type == "RENAME_NET":
            label = f"RENAME_NET {action.get('from', '?')} → {action.get('to', '?')}"
        elif action_type == "DISCONNECT":
            label = f"DISCONNECT {action.get('refdes', '?')}.{action.get('pin', '?')}"
        elif action_type == "REMOVE":
            label = f"REMOVE {action.get('refdes', '?')}"
        else:
            label = action_type
        
        actions.append(Action(
            id=f"{action_type.lower()}_{i+1}",
            type=action_type,
            label=label,
            payload=action  # Entire flat action becomes payload
        ))
    
    artifacts = [Artifact(**a) for a in artifacts_raw]

    return ChatResponse(reply=reply, actions=actions, artifacts=artifacts)
