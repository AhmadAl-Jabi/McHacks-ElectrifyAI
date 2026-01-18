"""
Gumloop webhook client for context enrichment and catalog filtering.

Provides a simple, resilient client for calling Gumloop webhooks with:
- Configurable timeout
- Automatic retry on network errors
- Minimal logging (metrics only, no full data)
- Safe fallback on any failure
"""
import os
import json
import time
import logging
from typing import Optional, Dict, Any, List

import httpx
from dotenv import load_dotenv

from backend.schemas import GumloopRequest, GumloopResponse

load_dotenv(override=True)

logger = logging.getLogger(__name__)


def summarize_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create compact snapshot summary for Gumloop.
    
    Rules:
    - mode: "CREATE" if no components, "EDIT" otherwise
    - components: compact list with refdes, kind/part_id, value
    - nets: list of net names only
    - counts: num_components, num_nets
    
    Does NOT include full raw snapshot or geometry fields.
    
    Args:
        snapshot: Full snapshot dict from bridge
    
    Returns:
        Compact summary dict for Gumloop
    """
    components = snapshot.get("components", [])
    nets = snapshot.get("nets", [])
    
    # Determine mode deterministically
    mode = "CREATE" if len(components) == 0 else "EDIT"
    
    # Build compact components list
    compact_components = []
    for comp in components:
        compact_comp = {"refdes": comp.get("refdes")}
        
        # Add kind or part_id if available
        if "kind" in comp:
            compact_comp["kind"] = comp["kind"]
        elif "part_id" in comp:
            compact_comp["part_id"] = comp["part_id"]
        
        # Add value if present
        if "value" in comp and comp["value"]:
            compact_comp["value"] = comp["value"]
        
        compact_components.append(compact_comp)
    
    # Build compact nets list (names only)
    compact_nets = [net.get("name") for net in nets if net.get("name")]
    
    return {
        "mode": mode,
        "num_components": len(components),
        "num_nets": len(nets),
        "components": compact_components,
        "nets": compact_nets
    }


class GumloopClient:
    """
    Client for calling Gumloop webhook with resilience and logging.
    
    Features:
    - POST JSON request with Content-Type: application/json
    - Configurable timeout (default: 10 seconds)
    - 1 retry on network errors (not on 4xx client errors)
    - Returns empty response on any failure (non-blocking)
    - Minimal logging (metrics only, no sensitive data)
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 1
    ):
        """
        Initialize Gumloop client.
        
        Args:
            webhook_url: Gumloop webhook URL (defaults to env var)
            timeout: Request timeout in seconds (8-12 recommended)
            max_retries: Number of retries on network error (default: 1)
        """
        self.webhook_url = webhook_url or os.getenv("GUMLOOP_WEBHOOK_URL", "")
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.webhook_url:
            logger.warning("[GumloopClient] No webhook URL configured")
    
    async def call(
        self,
        user_message: str,
        snapshot: Dict[str, Any],
        catalog_candidates: List[Dict[str, Any]]
    ) -> GumloopResponse:
        """
        Call Gumloop webhook with request data.
        
        Args:
            user_message: User's natural language request
            snapshot: Current schematic snapshot
            catalog_candidates: Full catalog or compact subset
        
        Returns:
            GumloopResponse with context_pack and suggested_catalog_ids,
            or empty response on any failure
        """
        if not self.webhook_url:
            logger.debug("[GumloopClient] Skipping call - no webhook URL")
            return GumloopResponse()
        
        # Build compact snapshot summary
        snapshot_summary = summarize_snapshot(snapshot)
        
        # Build request (catalog_candidates sent as-is)
        request = GumloopRequest(
            prompt=user_message,
            snapshot_summary=snapshot_summary,
            catalog_candidates=catalog_candidates
        )
        
        # Serialize request
        request_json = request.model_dump()
        request_bytes = json.dumps(request_json).encode('utf-8')
        request_size = len(request_bytes)
        
        # LOG THE EXACT JSON BEING SENT
        logger.info(f"[GumloopClient] === REQUEST JSON ===")
        logger.info(f"[GumloopClient] Keys: {list(request_json.keys())}")
        logger.info(f"[GumloopClient] snapshot_summary type: {type(request_json.get('snapshot_summary'))}")
        logger.info(f"[GumloopClient] snapshot_summary keys: {list(request_json.get('snapshot_summary', {}).keys()) if isinstance(request_json.get('snapshot_summary'), dict) else 'NOT A DICT'}")
        logger.info(f"[GumloopClient] Full request preview: {json.dumps(request_json, indent=2)[:1000]}...")
        
        logger.info(
            f"[GumloopClient] Calling webhook: "
            f"mode={snapshot_summary['mode']}, "
            f"{snapshot_summary['num_components']} components, "
            f"{len(catalog_candidates)} catalog entries, "
            f"{request_size} bytes"
        )
        
        # Make HTTP request with retries
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                # Disable SSL verification for corporate networks
                async with httpx.AsyncClient(verify=False) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=request_json,
                        headers={"Content-Type": "application/json"},
                        timeout=self.timeout
                    )
                    
                    # Don't retry on 4xx client errors
                    if 400 <= response.status_code < 500:
                        logger.warning(
                            f"[GumloopClient] Client error {response.status_code}, "
                            "not retrying"
                        )
                        return GumloopResponse()
                    
                    response.raise_for_status()
                
                # Parse and validate response
                response_data = response.json()
                logger.info(f"[GumloopClient] Raw response: {json.dumps(response_data)[:500]}...")
                
                gumloop_response = GumloopResponse.model_validate(response_data)
                
                # Log success metrics
                elapsed = time.time() - start_time
                logger.info(
                    f"[GumloopClient] Success: "
                    f"{len(gumloop_response.suggested_catalog_ids)} suggested IDs, "
                    f"{len(gumloop_response.context_pack)} chars context, "
                    f"{elapsed:.2f}s"
                )
                
                # Log the actual IDs if present
                if gumloop_response.suggested_catalog_ids:
                    logger.info(f"[GumloopClient] IDs: {gumloop_response.suggested_catalog_ids[:10]}...")
                
                return gumloop_response
                
            except httpx.TimeoutException:
                elapsed = time.time() - start_time
                if attempt < self.max_retries:
                    logger.warning(
                        f"[GumloopClient] ⏱️ TIMEOUT after {elapsed:.2f}s, "
                        f"retrying ({attempt + 1}/{self.max_retries})..."
                    )
                    continue
                else:
                    logger.error(
                        f"[GumloopClient] ⏱️ TIMEOUT after {elapsed:.2f}s, "
                        f"no retries left. Gumloop flow may still be running. "
                        f"Consider increasing GUMLOOP_TIMEOUT (current: {self.timeout}s)"
                    )
                    return GumloopResponse()
            
            except httpx.NetworkError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"[GumloopClient] Network error: {e}, "
                        f"retrying ({attempt + 1}/{self.max_retries})..."
                    )
                    continue
                else:
                    logger.warning(
                        f"[GumloopClient] Network error: {e}, "
                        "no retries left"
                    )
                    return GumloopResponse()
            
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"[GumloopClient] HTTP error {e.response.status_code}: "
                    f"{e.response.text[:200]}"
                )
                return GumloopResponse()
            
            except Exception as e:
                logger.warning(f"[GumloopClient] Unexpected error: {e}")
                return GumloopResponse()
        
        # Should not reach here, but safety fallback
        return GumloopResponse()


# Global client instance
_client: Optional[GumloopClient] = None


def get_client() -> GumloopClient:
    """Get or create global GumloopClient instance."""
    global _client
    if _client is None:
        # Get timeout from environment (default: 30 seconds)
        timeout = float(os.getenv("GUMLOOP_TIMEOUT", "30.0"))
        _client = GumloopClient(timeout=timeout, max_retries=1)
        logger.info(f"[GumloopClient] Initialized with timeout={timeout}s")
    return _client


async def call_gumloop(
    user_message: str,
    snapshot: Dict[str, Any],
    catalog_candidates: List[Dict[str, Any]]
) -> GumloopResponse:
    """
    Convenience function to call Gumloop webhook.
    
    Args:
        user_message: User's natural language request
        snapshot: Current schematic snapshot
        catalog_candidates: Full catalog or compact subset
    
    Returns:
        GumloopResponse or empty response on failure
    """
    client = get_client()
    return await client.call(user_message, snapshot, catalog_candidates)

