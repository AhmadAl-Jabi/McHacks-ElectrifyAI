"""
Commands IR: agent-generated operations for schematic modification.

Schema-validated output that references catalog_id, valid pins, and existing refdes.
Supports both create and edit modes.
"""
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, Discriminator


# Args classes (nested under each command)
class AddComponentArgs(BaseModel):
    """Arguments for add_component command."""
    model_config = ConfigDict(extra="forbid")
    part_id: str
    refdes: str


class RemoveComponentArgs(BaseModel):
    """Arguments for remove_component command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str


class CreateNetArgs(BaseModel):
    """Arguments for create_net command."""
    model_config = ConfigDict(extra="forbid")
    net_name: str


class RenameNetArgs(BaseModel):
    """Arguments for rename_net command."""
    model_config = ConfigDict(extra="forbid")
    from_: str = Field(alias="from")
    to: str


class ConnectArgs(BaseModel):
    """Arguments for connect command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str
    pin: str
    net_name: str


class DisconnectArgs(BaseModel):
    """Arguments for disconnect command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str
    pin: str
    net_name: str


class SetValueArgs(BaseModel):
    """Arguments for set_value command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str
    value: str


class PlaceComponentArgs(BaseModel):
    """Arguments for place_component command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str
    x: float
    y: float
    rotation: float = 0.0
    layer: Literal["Top", "Bottom"] = "Top"


class PlaceNearArgs(BaseModel):
    """Arguments for place_near command."""
    model_config = ConfigDict(extra="forbid")
    refdes: str
    anchor_refdes: str
    dx: float
    dy: float
    rotation: float = 0.0
    layer: Literal["Top", "Bottom"] = "Top"


class CommentArgs(BaseModel):
    """Arguments for comment command."""
    model_config = ConfigDict(extra="forbid")
    text: str


# Command classes (op + args structure)
class AddComponentCmd(BaseModel):
    """Add a component to the schematic."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["add_component"] = "add_component"
    args: AddComponentArgs


class RemoveComponentCmd(BaseModel):
    """Remove a component from the schematic."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["remove_component"] = "remove_component"
    args: RemoveComponentArgs


class CreateNetCmd(BaseModel):
    """Create a new net (optional, compiler can auto-create)."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["create_net"] = "create_net"
    args: CreateNetArgs


class RenameNetCmd(BaseModel):
    """Rename an existing net."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["rename_net"] = "rename_net"
    args: RenameNetArgs


class ConnectCmd(BaseModel):
    """Connect a component pin to a net."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["connect"] = "connect"
    args: ConnectArgs


class DisconnectCmd(BaseModel):
    """Disconnect a component pin from a net."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["disconnect"] = "disconnect"
    args: DisconnectArgs


class SetValueCmd(BaseModel):
    """Set component value (e.g., resistance, capacitance)."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["set_value"] = "set_value"
    args: SetValueArgs


class PlaceComponentCmd(BaseModel):
    """Place component at absolute coordinates."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["place_component"] = "place_component"
    args: PlaceComponentArgs


class PlaceNearCmd(BaseModel):
    """Place component relative to anchor component."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["place_near"] = "place_near"
    args: PlaceNearArgs


class CommentCmd(BaseModel):
    """Comment for missing parts or impossible requests."""
    model_config = ConfigDict(extra="forbid")
    
    op: Literal["comment"] = "comment"
    args: CommentArgs


# Discriminated union of all command types
Command = Annotated[
    AddComponentCmd
    | RemoveComponentCmd
    | CreateNetCmd
    | RenameNetCmd
    | ConnectCmd
    | DisconnectCmd
    | SetValueCmd
    | PlaceComponentCmd
    | PlaceNearCmd
    | CommentCmd,
    Discriminator("op"),
]


class CommandsDoc(BaseModel):
    """Complete agent command output."""
    model_config = ConfigDict(extra="forbid")
    
    commands: list[Command] = Field(default_factory=list)
