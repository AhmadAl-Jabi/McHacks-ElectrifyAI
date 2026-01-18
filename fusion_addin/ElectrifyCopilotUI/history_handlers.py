# ============================================
# Electrify Copilot - History Handlers Module
# Routes history actions to HistoryService
# Protocol v1.1.0 compliant
# ============================================

"""
History Handlers: Routes incoming history_* actions to HistoryService
and sends responses back via sendInfoToHTML.

Action Routing:
    history_list    -> HistoryService.list_sessions()   -> history_list_result
    history_create  -> HistoryService.create_session()  -> history_create_result
    history_load    -> HistoryService.load_session()    -> history_load_result
    history_rename  -> HistoryService.rename_session()  -> history_ok
    history_delete  -> HistoryService.delete_session()  -> history_ok
    history_pin     -> HistoryService.pin_session()     -> history_ok
    history_append  -> HistoryService.append_messages() -> history_ok
    history_search  -> HistoryService.list_sessions()   -> history_list_result
"""

import json
import time
from typing import Dict, Any, Callable, Optional
from datetime import datetime

# Import service layer
try:
    from . import history_service
    from .history_service import HistoryService, get_service
except ImportError:
    # Fallback for direct execution
    import history_service
    from history_service import HistoryService, get_service


# ============================================
# Protocol Constants
# ============================================

PROTOCOL_VERSION = '1.1.0'

# Action to response action mapping
ACTION_RESPONSE_MAP = {
    'history_list': 'history_list_result',
    'history_create': 'history_create_result',
    'history_load': 'history_load_result',
    'history_rename': 'history_ok',
    'history_delete': 'history_ok',
    'history_pin': 'history_ok',
    'history_append': 'history_ok',
    'history_search': 'history_list_result',
}


# ============================================
# Response Helpers
# ============================================

def _ts_now_iso() -> str:
    """Get current timestamp in ISO 8601 format."""
    return datetime.utcnow().isoformat() + 'Z'


def _make_success_response(
    response_action: str,
    request_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a success response envelope."""
    return {
        'action': response_action,
        'v': PROTOCOL_VERSION,
        'requestId': request_id,
        'ts': _ts_now_iso(),
        'payload': payload
    }


def _make_error_response(
    request_id: str,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create an error response envelope."""
    payload = {
        'code': code,
        'message': message
    }
    if details:
        payload['details'] = details
    
    return {
        'action': 'history_error',
        'v': PROTOCOL_VERSION,
        'requestId': request_id,
        'ts': _ts_now_iso(),
        'payload': payload
    }


# ============================================
# Action Handlers
# ============================================

def _handle_list(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_list action."""
    result = service.list_sessions(
        limit=payload.get('limit'),
        cursor=payload.get('cursor')
    )
    
    if result.success:
        return result.data
    raise ValueError(result.error_message)


def _handle_create(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_create action."""
    result = service.create_session(
        title=payload.get('title')
    )
    
    if result.success:
        return result.data
    raise ValueError(result.error_message)


def _handle_load(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_load action."""
    result = service.load_session(
        session_id=payload.get('sessionId', ''),
        limit_messages=payload.get('limitMessages')
    )
    
    if result.success:
        return result.data
    
    # Convert error code to appropriate exception
    if result.error_code == 'NOT_FOUND':
        raise KeyError(result.error_message)
    raise ValueError(result.error_message)


def _handle_rename(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_rename action."""
    result = service.rename_session(
        session_id=payload.get('sessionId', ''),
        title=payload.get('title', '')
    )
    
    if result.success:
        return result.data
    
    if result.error_code == 'NOT_FOUND':
        raise KeyError(result.error_message)
    raise ValueError(result.error_message)


def _handle_delete(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_delete action."""
    result = service.delete_session(
        session_id=payload.get('sessionId', '')
    )
    
    if result.success:
        return result.data
    raise ValueError(result.error_message)


def _handle_pin(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_pin action."""
    result = service.pin_session(
        session_id=payload.get('sessionId', ''),
        pinned=payload.get('pinned', True)
    )
    
    if result.success:
        return result.data
    
    if result.error_code == 'NOT_FOUND':
        raise KeyError(result.error_message)
    raise ValueError(result.error_message)


def _handle_append(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle history_append action."""
    # Support single message (protocol spec) or messages array
    messages = payload.get('messages', [])
    
    # If 'message' singular is provided, wrap in array
    if 'message' in payload and not messages:
        messages = [payload['message']]
    
    session_id = payload.get('sessionId', '')
    
    # If no sessionId provided, silently return success (frontend handles locally)
    # This prevents errors when session hasn't been created yet
    if not session_id:
        return {
            "session": None,
            "messageCount": 0
        }
    
    result = service.append_messages(
        session_id=session_id,
        messages=messages,
        events=payload.get('events')
    )
    
    if result.success:
        return result.data
    
    if result.error_code == 'NOT_FOUND':
        raise KeyError(result.error_message)
    # For any validation errors, silently ignore to prevent UI popups
    # Messages are already stored locally in frontend
    if result.error_code == 'INVALID_PAYLOAD':
        return {
            "session": None,
            "messageCount": 0
        }
    raise ValueError(result.error_message)


def _handle_search(service: HistoryService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle history_search action.
    
    Searches session titles (LIKE) and optionally message content.
    Returns matching sessions with snippet preview and match counts.
    
    Payload:
        query: Search query string (required, 1-200 chars)
        limit: Max sessions to return (default 50, max 100)
        cursor: Pagination cursor for next page
        searchContent: If true, search message content too (default true)
        includeArchived: If true, include archived sessions (default false)
        
    Response:
        sessions: [...] with extra fields: matchType, snippet, matchCount
        nextCursor: pagination cursor or null
        totalMatches: total number of matching sessions
    """
    result = service.search_sessions(
        query=payload.get('query', ''),
        limit=payload.get('limit'),
        cursor=payload.get('cursor'),
        search_content=payload.get('searchContent', True),
        include_archived=payload.get('includeArchived', False)
    )
    
    if result.success:
        return result.data
    
    raise ValueError(result.error_message)


# Handler dispatch table
ACTION_HANDLERS: Dict[str, Callable[[HistoryService, Dict[str, Any]], Dict[str, Any]]] = {
    'history_list': _handle_list,
    'history_create': _handle_create,
    'history_load': _handle_load,
    'history_rename': _handle_rename,
    'history_delete': _handle_delete,
    'history_pin': _handle_pin,
    'history_append': _handle_append,
    'history_search': _handle_search,
}


# ============================================
# Main Handler
# ============================================

class HistoryHandlers:
    """
    Routes history_* actions to HistoryService methods.
    
    Usage in Fusion executor:
        handler = HistoryHandlers()
        response = handler.handle(action, data)
        send_to_palette(response['action'], response)
    """
    
    def __init__(self):
        """Initialize with HistoryService instance."""
        self._service = get_service()
    
    def can_handle(self, action: str) -> bool:
        """Check if this handler can process the given action."""
        return action in ACTION_HANDLERS
    
    def handle(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a history action and return response.
        
        Args:
            action: The action name (e.g., 'history_list')
            data: Request data with requestId and payload
            
        Returns:
            Response dict ready to send via sendInfoToHTML:
            {
                'action': 'history_*_result' | 'history_ok' | 'history_error',
                'v': '1.1.0',
                'requestId': '...',
                'ts': '...',
                'payload': { ... }
            }
        """
        # Extract request ID with fallback
        request_id = data.get('requestId', f'req_{int(time.time() * 1000)}_0')
        payload = data.get('payload', {})
        
        # Get handler for action
        handler = ACTION_HANDLERS.get(action)
        if not handler:
            return _make_error_response(
                request_id,
                'INVALID_ACTION',
                f"Unknown action: {action}"
            )
        
        # Get expected response action
        response_action = ACTION_RESPONSE_MAP.get(action, 'history_ok')
        
        try:
            # Execute handler
            result_payload = handler(self._service, payload)
            
            return _make_success_response(
                response_action,
                request_id,
                result_payload
            )
            
        except KeyError as e:
            # Not found errors
            return _make_error_response(
                request_id,
                'NOT_FOUND',
                str(e)
            )
            
        except ValueError as e:
            # Validation errors
            return _make_error_response(
                request_id,
                'INVALID_PAYLOAD',
                str(e)
            )
            
        except Exception as e:
            # Unexpected errors - never crash
            return _make_error_response(
                request_id,
                'UNKNOWN',
                f"Internal error: {str(e)}"
            )


# ============================================
# Module Interface
# ============================================

# Global handler instance
_handlers: Optional[HistoryHandlers] = None


def get_handlers() -> HistoryHandlers:
    """Get or create the singleton handler instance."""
    global _handlers
    if _handlers is None:
        _handlers = HistoryHandlers()
    return _handlers


def handle_history_action(action: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for handling history actions.
    
    Args:
        action: The history action (e.g., 'history_list')
        data: Request data including requestId and payload
        
    Returns:
        Response dict with action, v, requestId, ts, payload
        
    Example:
        response = handle_history_action('history_list', {
            'requestId': 'req_123_1',
            'payload': {'limit': 50}
        })
        # response['action'] == 'history_list_result'
        # response['payload'] == {'sessions': [...], 'nextCursor': ...}
    """
    return get_handlers().handle(action, data)


def is_history_action(action: str) -> bool:
    """Check if an action should be handled by history handlers."""
    return action.startswith('history_') and action in ACTION_HANDLERS
