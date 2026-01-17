"""
Action type definitions and validation.

Input actions are already validated by backend - this provides
simple type checking and field extraction for the executor.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AddAction:
    """ADD action: add component to schematic"""
    type: str  # "ADD"
    cmd: str   # Full EAGLE command: "ADD PART_NAME@LIBRARY"
    refdes: str
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AddAction":
        return cls(
            type=d["type"],
            cmd=d["cmd"],
            refdes=d["refdes"],
            id=d.get("id")
        )


@dataclass
class SetValueAction:
    """SET_VALUE action: set component value"""
    type: str  # "SET_VALUE"
    refdes: str
    value: str
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SetValueAction":
        return cls(
            type=d["type"],
            refdes=d["refdes"],
            value=d["value"],
            id=d.get("id")
        )


@dataclass
class PlaceAction:
    """PLACE action: place component at coordinates"""
    type: str  # "PLACE"
    refdes: str
    x: float
    y: float
    rotation: float = 0.0
    layer: str = "Top"
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlaceAction":
        return cls(
            type=d["type"],
            refdes=d["refdes"],
            x=d["x"],
            y=d["y"],
            rotation=d.get("rotation", 0.0),
            layer=d.get("layer", "Top"),
            id=d.get("id")
        )


@dataclass
class ConnectAction:
    """CONNECT action: connect pin to net"""
    type: str  # "CONNECT"
    refdes: str
    pin: str
    net_name: str
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConnectAction":
        return cls(
            type=d["type"],
            refdes=d["refdes"],
            pin=d["pin"],
            net_name=d["net_name"],
            id=d.get("id")
        )


@dataclass
class DisconnectAction:
    """DISCONNECT action: disconnect pin from net"""
    type: str  # "DISCONNECT"
    refdes: str
    pin: str
    net_name: str
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DisconnectAction":
        return cls(
            type=d["type"],
            refdes=d["refdes"],
            pin=d["pin"],
            net_name=d["net_name"],
            id=d.get("id")
        )


@dataclass
class RenameNetAction:
    """RENAME_NET action: rename a net"""
    type: str  # "RENAME_NET"
    old_name: str
    new_name: str
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RenameNetAction":
        return cls(
            type=d["type"],
            old_name=d["old_name"],
            new_name=d["new_name"]
        )


@dataclass
class RemoveAction:
    """REMOVE action: delete component"""
    type: str  # "REMOVE"
    refdes: str
    id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RemoveAction":
        return cls(
            type=d["type"],
            refdes=d["refdes"],
            id=d.get("id")
        )


def parse_action(action_dict: Dict[str, Any]) -> Any:
    """
    Parse action dict into typed dataclass.
    
    Args:
        action_dict: Action dictionary with "type" field
        
    Returns:
        Typed action dataclass instance
        
    Raises:
        ValueError: If action type is unknown
    """
    action_type = action_dict.get("type")
    
    if action_type == "ADD":
        return AddAction.from_dict(action_dict)
    elif action_type == "SET_VALUE":
        return SetValueAction.from_dict(action_dict)
    elif action_type == "PLACE":
        return PlaceAction.from_dict(action_dict)
    elif action_type == "CONNECT":
        return ConnectAction.from_dict(action_dict)
    elif action_type == "DISCONNECT":
        return DisconnectAction.from_dict(action_dict)
    elif action_type == "RENAME_NET":
        return RenameNetAction.from_dict(action_dict)
    elif action_type == "REMOVE":
        return RemoveAction.from_dict(action_dict)
    elif action_type == "COMMENT":
        # COMMENT actions are passed through as-is (handled specially in script_builder)
        return action_dict
    else:
        raise ValueError(f"Unknown action type: {action_type}")


def validate_actions_structure(actions: List[Dict[str, Any]]) -> None:
    """
    Basic structure validation (backend already validated, this is sanity check).
    
    Args:
        actions: List of action dictionaries
        
    Raises:
        ValueError: If structure is invalid
    """
    if not isinstance(actions, list):
        raise ValueError("Actions must be a list")
    
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"Action {i} must be a dict")
        
        if "type" not in action:
            raise ValueError(f"Action {i} missing 'type' field")
        
        # Try to parse (will raise if invalid)
        parse_action(action)
