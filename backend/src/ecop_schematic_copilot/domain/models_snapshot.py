"""
Snapshot IR: represents the current state of a schematic.

Exported from Fusion 360 Electronics or initialized empty for new schematics.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Placement(BaseModel):
    """Component placement information."""
    model_config = ConfigDict(extra="forbid")
    
    x: float
    y: float
    rotation: float = 0.0
    layer: Literal["Top", "Bottom"] = "Top"


class NetConnection(BaseModel):
    """Pin-to-net connection."""
    model_config = ConfigDict(extra="forbid")
    
    refdes: str
    pin: str


class SnapshotComponent(BaseModel):
    """Component in the schematic snapshot."""
    model_config = ConfigDict(extra="allow")  # Allow extra fields from ULP export (e.g., device)
    
    refdes: str
    part_id: str | None = None
    value: str | None = None
    pins: list[str] = Field(default_factory=list)
    placement: Placement | None = None


class SnapshotNet(BaseModel):
    """Net with connections."""
    model_config = ConfigDict(extra="allow")  # Allow extra fields from ULP export
    
    net_name: str
    connections: list[NetConnection] = Field(default_factory=list)


class SnapshotDoc(BaseModel):
    """Complete schematic snapshot."""
    model_config = ConfigDict(extra="allow")  # Allow extra fields from ULP export (e.g., generated_at, source, component_count)
    
    components: list[SnapshotComponent] = Field(default_factory=list)
    nets: list[SnapshotNet] = Field(default_factory=list)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def snapshot_component_map(snapshot: SnapshotDoc) -> dict[str, SnapshotComponent]:
    """Build refdes -> SnapshotComponent lookup map."""
    return {comp.refdes: comp for comp in snapshot.components}


def snapshot_net_map(snapshot: SnapshotDoc) -> dict[str, SnapshotNet]:
    """Build net_name -> SnapshotNet lookup map."""
    return {net.net_name: net for net in snapshot.nets}
