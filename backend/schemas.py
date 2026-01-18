from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional

class ChatRequest(BaseModel):
    message: str
    project_path: str = ""
    selected_ref: Optional[str] = None


# =============================================================================
# Gumloop Webhook Contract
# =============================================================================

class GumloopRequest(BaseModel):
    """
    Input contract for Gumloop webhook.
    
    Sends compact context to Gumloop for pre-processing/filtering.
    Gumloop should NOT generate Commands IR - only provide context enrichment.
    """
    prompt: str = Field(..., description="User's natural language request")
    snapshot_summary: dict[str, Any] = Field(
        ...,
        description="Compact snapshot summary with mode, components, nets"
    )
    catalog_candidates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Full catalog or compact subset (catalog.json has ~258 parts)"
    )


class GumloopResponse(BaseModel):
    """
    Output contract from Gumloop webhook.
    
    CRITICAL: Gumloop must never return Commands IR or any command-like structures.
    This response is UNTRUSTED - all fields are validated and clamped.
    """
    context_pack: str = Field(
        default="",
        description="Additional context/reasoning from Gumloop (untrusted)"
    )
    suggested_catalog_ids: list[str] = Field(
        default_factory=list,
        description="Filtered catalog part IDs (max 50, untrusted)"
    )
    
    class Config:
        # Ignore any extra fields Gumloop might add
        extra = "ignore"
    
    @field_validator("suggested_catalog_ids", mode="before")
    @classmethod
    def clamp_catalog_ids(cls, v) -> list[str]:
        """Clamp array to max 50 items for safety. Handles untrusted input."""
        if not isinstance(v, list):
            return []
        
        # Ensure all items are strings, filter out None/empty, clamp to 50
        validated = []
        for item in v:
            if item is not None and item != "":
                try:
                    validated.append(str(item))
                except Exception:
                    continue  # Skip items that can't be converted
        
        return validated[:50]
    
    @field_validator("context_pack", mode="before")
    @classmethod
    def validate_context_pack(cls, v) -> str:
        """Ensure context_pack is a string and limit size. Handles untrusted input."""
        if v is None:
            return ""
        
        # Convert to string if not already
        try:
            v_str = str(v) if not isinstance(v, str) else v
        except Exception:
            return ""
        
        # Limit to 50KB to prevent abuse
        return v_str[:50000]

class Action(BaseModel):
    id: str
    type: str
    label: str
    payload: dict[str, Any] = {}

class Artifact(BaseModel):
    id: str
    type: str  # "PLOT_PNG", "NETLIST", "TEXT"
    label: str
    payload: dict[str, Any] = {}

class ChatResponse(BaseModel):
    reply: str
    actions: list[Action] = []
    artifacts: list[Artifact] = []
