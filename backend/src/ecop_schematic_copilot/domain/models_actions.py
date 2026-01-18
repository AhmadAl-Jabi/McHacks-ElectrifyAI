"""
Actions IR: flat list of executor-ready operations.

Compiled from Commands IR with proper ordering and validation.
Executor runs these 1:1 operations deterministically.
"""
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, Discriminator


class AddAction(BaseModel):
    """Add component to schematic."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["ADD"] = "ADD"
    cmd: str  # Fusion add command
    refdes: str


class SetValueAction(BaseModel):
    """Set component value."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["SET_VALUE"] = "SET_VALUE"
    refdes: str
    value: str


class PlaceAction(BaseModel):
    """Place component at coordinates."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["PLACE"] = "PLACE"
    refdes: str
    x: float
    y: float
    rotation: float
    layer: Literal["Top", "Bottom"]


class ConnectAction(BaseModel):
    """Connect pin to net."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["CONNECT"] = "CONNECT"
    refdes: str
    pin: str
    net_name: str


class DisconnectAction(BaseModel):
    """Disconnect pin from net."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["DISCONNECT"] = "DISCONNECT"
    refdes: str
    pin: str
    net_name: str


class RenameNetAction(BaseModel):
    """Rename net."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["RENAME_NET"] = "RENAME_NET"
    from_: str = Field(alias="from")
    to: str


class RemoveAction(BaseModel):
    """Remove component from schematic."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["REMOVE"] = "REMOVE"
    refdes: str


# Discriminated union of all action types
Action = Annotated[
    AddAction
    | SetValueAction
    | PlaceAction
    | ConnectAction
    | DisconnectAction
    | RenameNetAction
    | RemoveAction,
    Discriminator("type"),
]


class ActionsDoc(BaseModel):
    """Complete executor-ready action list."""
    model_config = ConfigDict(extra="forbid")
    
    actions: list[Action] = Field(default_factory=list)
