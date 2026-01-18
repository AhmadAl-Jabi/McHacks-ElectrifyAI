"""
Actions dispatcher: routes actions to Fusion 360 adapter.

Iterates through ActionsDoc and dispatches each action to the appropriate
adapter method.
"""
from ..domain import (
    ActionsDoc,
    AddAction,
    SetValueAction,
    PlaceAction,
    ConnectAction,
    DisconnectAction,
    RenameNetAction,
    RemoveAction,
)
from .fusion_adapter import FusionAdapter


def dispatch_actions(actions: ActionsDoc, adapter: FusionAdapter) -> None:
    """
    Dispatch actions to Fusion 360 adapter.
    
    Iterates through actions in order and calls the appropriate adapter method
    for each action type.
    
    Args:
        actions: ActionsDoc containing ordered list of actions
        adapter: FusionAdapter instance to execute actions
        
    Raises:
        Any exceptions raised by adapter methods are propagated
    """
    for i, action in enumerate(actions.actions):
        print(f"[DISPATCH] Action {i+1}/{len(actions.actions)}: {action.type}")
        
        # ====================================================================
        # ADD
        # ====================================================================
        if isinstance(action, AddAction):
            adapter.add(
                cmd=action.cmd,
                refdes=action.refdes,
            )
        
        # ====================================================================
        # SET_VALUE
        # ====================================================================
        elif isinstance(action, SetValueAction):
            adapter.set_value(
                refdes=action.refdes,
                value=action.value,
            )
        
        # ====================================================================
        # PLACE
        # ====================================================================
        elif isinstance(action, PlaceAction):
            adapter.place(
                refdes=action.refdes,
                x=action.x,
                y=action.y,
                rotation=action.rotation,
                layer=action.layer,
            )
        
        # ====================================================================
        # CONNECT
        # ====================================================================
        elif isinstance(action, ConnectAction):
            adapter.connect(
                refdes=action.refdes,
                pin=action.pin,
                net=action.net,
            )
        
        # ====================================================================
        # DISCONNECT
        # ====================================================================
        elif isinstance(action, DisconnectAction):
            adapter.disconnect(
                refdes=action.refdes,
                pin=action.pin,
                net=action.net,
            )
        
        # ====================================================================
        # RENAME_NET
        # ====================================================================
        elif isinstance(action, RenameNetAction):
            adapter.rename_net(
                from_net=action.from_,
                to_net=action.to,
            )
        
        # ====================================================================
        # REMOVE
        # ====================================================================
        elif isinstance(action, RemoveAction):
            adapter.remove(
                refdes=action.refdes,
            )
        
        else:
            # Unknown action type (shouldn't happen with discriminated union)
            print(f"[WARNING] Unknown action type: {type(action)}")
    
    print(f"[DISPATCH] Completed {len(actions.actions)} actions")
