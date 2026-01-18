# ============================================
# Electrify Copilot - History Service Module
# Safe CRUD operations with validation
# Protocol v1.1.0 compliant
# ============================================

"""
HistoryService: High-level service layer for chat history operations.

Provides:
- Type validation and size limits
- Cursor-based pagination
- Safe error handling (never crashes host)
- Protocol v1.1.0 compliant responses
"""

import re
import json
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

# Import data layer
from . import chat_history as db


# ============================================
# Configuration & Limits
# ============================================

MAX_TITLE_LENGTH = 100
MAX_CONTENT_LENGTH = 100_000  # 100KB per message
MAX_MESSAGES_PER_APPEND = 50
MAX_EVENTS_PER_APPEND = 20
MAX_SESSIONS_PER_PAGE = 100
DEFAULT_SESSIONS_PER_PAGE = 50
MAX_MESSAGES_PER_LOAD = 500
DEFAULT_MESSAGES_PER_LOAD = 200
DEFAULT_TITLE = "New chat"
MAX_SEARCH_QUERY_LENGTH = 200
MIN_SEARCH_QUERY_LENGTH = 1

# UUID regex pattern
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


# ============================================
# Result Types
# ============================================

@dataclass
class ServiceResult:
    """Result wrapper for service operations."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        if self.success:
            return {
                'success': True,
                'data': self.data
            }
        return {
            'success': False,
            'error': {
                'code': self.error_code or 'UNKNOWN',
                'message': self.error_message or 'Unknown error'
            }
        }


# ============================================
# Validation Helpers
# ============================================

def _validate_uuid(value: Any, field_name: str) -> Tuple[bool, Optional[str]]:
    """Validate a UUID string. Returns (is_valid, error_message)."""
    if value is None:
        return False, f"{field_name} is required"
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if not UUID_PATTERN.match(value):
        return False, f"{field_name} must be a valid UUID"
    return True, None


def _validate_string(value: Any, field_name: str, 
                     max_length: int, required: bool = True,
                     min_length: int = 0) -> Tuple[bool, Optional[str]]:
    """Validate a string field. Returns (is_valid, error_message)."""
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    if len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    return True, None


def _validate_int(value: Any, field_name: str,
                  min_val: int = 0, max_val: int = 2**31,
                  default: Optional[int] = None) -> Tuple[int, Optional[str]]:
    """Validate and coerce an integer. Returns (value, error_message)."""
    if value is None:
        if default is not None:
            return default, None
        return 0, f"{field_name} is required"
    try:
        int_val = int(value)
        if int_val < min_val:
            return min_val, None  # Clamp to min
        if int_val > max_val:
            return max_val, None  # Clamp to max
        return int_val, None
    except (TypeError, ValueError):
        if default is not None:
            return default, None
        return 0, f"{field_name} must be an integer"


def _validate_bool(value: Any, default: bool = False) -> bool:
    """Validate and coerce a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _validate_message(msg: Any, index: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate a message object. Returns (validated_msg, error_message).
    
    Single-writer rule: Frontend generates ID and timestamp.
    Backend validates format and stores. ID is required.
    """
    if not isinstance(msg, dict):
        return None, f"messages[{index}] must be an object"
    
    # Validate role
    role = msg.get('role')
    if role not in ('user', 'assistant', 'error'):
        return None, f"messages[{index}].role must be 'user', 'assistant', or 'error'"
    
    # Validate content
    content = msg.get('content')
    valid, err = _validate_string(content, f"messages[{index}].content", 
                                   MAX_CONTENT_LENGTH, required=True)
    if not valid:
        return None, err
    
    # Single-writer: ID is REQUIRED from sender
    msg_id = msg.get('id')
    if not msg_id:
        return None, f"messages[{index}].id is required (single-writer rule)"
    
    # Validate ID format (must be valid identifier, not necessarily UUID)
    if not isinstance(msg_id, str) or len(msg_id) < 5 or len(msg_id) > 100:
        return None, f"messages[{index}].id must be a string (5-100 chars)"
    
    # Build validated message
    validated = {
        'id': msg_id,
        'role': role,
        'content': content
    }
    
    # Single-writer: ts from sender, convert ISO to int if needed
    if 'ts' in msg and msg['ts']:
        ts = msg['ts']
        if isinstance(ts, int):
            validated['ts'] = ts
        elif isinstance(ts, str):
            # Convert ISO 8601 to Unix ms
            parsed_ts = _parse_iso_timestamp(ts)
            if parsed_ts:
                validated['ts'] = parsed_ts
            else:
                return None, f"messages[{index}].ts invalid ISO format"
    
    # Optional status
    if 'status' in msg:
        status = msg['status']
        if status in ('sending', 'streaming', 'complete', 'error'):
            validated['status'] = status
    
    # Optional meta
    if 'meta' in msg and isinstance(msg['meta'], dict):
        validated['meta'] = msg['meta']
    
    return validated, None


def _parse_iso_timestamp(ts_str: str) -> Optional[int]:
    """Parse ISO 8601 timestamp string to Unix milliseconds."""
    try:
        from datetime import datetime
        # Handle various ISO formats
        ts_str = ts_str.rstrip('Z')
        if '.' in ts_str:
            dt = datetime.fromisoformat(ts_str)
        else:
            dt = datetime.fromisoformat(ts_str)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def _generate_auto_title(content: str, max_length: int = 40) -> str:
    """
    Generate an auto-title from message content (ChatGPT-style).
    
    - Strips whitespace
    - Takes first line only
    - Truncates to max_length chars
    - Adds ellipsis if truncated
    """
    if not content:
        return DEFAULT_TITLE
    
    # Take first line only
    first_line = content.split('\n')[0].strip()
    
    if not first_line:
        return DEFAULT_TITLE
    
    # Truncate if needed
    if len(first_line) <= max_length:
        return first_line
    
    # Find word boundary for cleaner truncation
    truncated = first_line[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length // 2:
        # Cut at word boundary if reasonable
        truncated = truncated[:last_space]
    
    return truncated.rstrip('.,;:!?') + '...'


def _validate_event(evt: Any, index: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validate an event object. Returns (validated_event, error_message)."""
    if not isinstance(evt, dict):
        return None, f"events[{index}] must be an object"
    
    # Validate type
    event_type = evt.get('type')
    valid, err = _validate_string(event_type, f"events[{index}].type", 
                                   50, required=True, min_length=1)
    if not valid:
        return None, err
    
    # Build validated event
    validated = {
        'type': event_type
    }
    
    # Optional data
    if 'data' in evt and isinstance(evt['data'], dict):
        # Limit data size
        try:
            data_json = json.dumps(evt['data'])
            if len(data_json) <= 10_000:  # 10KB limit
                validated['data'] = evt['data']
        except (TypeError, ValueError):
            pass  # Skip invalid data
    
    return validated, None


# ============================================
# Cursor Utilities
# ============================================

def _encode_cursor(updated_at: int, session_id: str) -> str:
    """Encode pagination cursor from updatedAt + id."""
    return f"{updated_at}:{session_id}"


def _decode_cursor(cursor: str) -> Tuple[Optional[int], Optional[str]]:
    """Decode pagination cursor to (updatedAt, id). Returns (None, None) on invalid."""
    if not cursor or not isinstance(cursor, str):
        return None, None
    
    parts = cursor.split(':', 1)
    if len(parts) != 2:
        return None, None
    
    try:
        updated_at = int(parts[0])
        session_id = parts[1]
        if UUID_PATTERN.match(session_id):
            return updated_at, session_id
    except (ValueError, TypeError):
        pass
    
    return None, None


# ============================================
# HistoryService Class
# ============================================

class HistoryService:
    """
    High-level service for chat history operations.
    
    All methods are safe and will never crash the host.
    Returns ServiceResult with success/error information.
    """
    
    def __init__(self):
        """Initialize the service and ensure database is ready."""
        try:
            db.init_database()
        except Exception:
            pass  # Database init failure handled per-operation
    
    def list_sessions(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> ServiceResult:
        """
        List sessions with cursor-based pagination.
        
        Args:
            limit: Maximum sessions to return (default 50, max 100)
            cursor: Pagination cursor (format: "updatedAt:sessionId")
            
        Returns:
            ServiceResult with data:
            {
                "sessions": [...],
                "nextCursor": "..." | null
            }
        """
        try:
            # Validate limit
            limit_val, _ = _validate_int(limit, "limit", 
                                          min_val=1, 
                                          max_val=MAX_SESSIONS_PER_PAGE,
                                          default=DEFAULT_SESSIONS_PER_PAGE)
            
            # Decode cursor for pagination
            cursor_ts, cursor_id = _decode_cursor(cursor) if cursor else (None, None)
            
            # Get sessions from database
            conn = db.get_connection()
            try:
                cursor_db = conn.cursor()
                
                if cursor_ts is not None and cursor_id is not None:
                    # Cursor-based pagination: get sessions before cursor position
                    cursor_db.execute('''
                        SELECT * FROM sessions 
                        WHERE (updatedAt < ? OR (updatedAt = ? AND id < ?))
                        ORDER BY pinned DESC, updatedAt DESC, id DESC
                        LIMIT ?
                    ''', (cursor_ts, cursor_ts, cursor_id, limit_val + 1))
                else:
                    # First page
                    cursor_db.execute('''
                        SELECT * FROM sessions 
                        ORDER BY pinned DESC, updatedAt DESC, id DESC
                        LIMIT ?
                    ''', (limit_val + 1,))
                
                rows = cursor_db.fetchall()
                
                # Check if there's a next page
                has_more = len(rows) > limit_val
                if has_more:
                    rows = rows[:limit_val]
                
                # Convert rows to session dicts
                sessions = [db._row_to_session(row, cursor_db) for row in rows]
                
                # Generate next cursor
                next_cursor = None
                if has_more and sessions:
                    last = sessions[-1]
                    # Convert ISO timestamp back to int for cursor
                    last_ts = db._iso_to_ts(last['updatedAt'])
                    next_cursor = _encode_cursor(last_ts, last['id'])
                
                return ServiceResult(
                    success=True,
                    data={
                        'sessions': sessions,
                        'nextCursor': next_cursor
                    }
                )
            finally:
                conn.close()
                
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to list sessions: {str(e)}"
            )
    
    def create_session(self, title: Optional[str] = None) -> ServiceResult:
        """
        Create a new chat session.
        
        Args:
            title: Optional session title (default "New chat", max 100 chars)
            
        Returns:
            ServiceResult with data: { "session": {...} }
        """
        try:
            # Validate title
            if title is not None:
                valid, err = _validate_string(title, "title", MAX_TITLE_LENGTH, required=False)
                if not valid:
                    return ServiceResult(
                        success=False,
                        error_code='INVALID_PAYLOAD',
                        error_message=err
                    )
                title = title.strip() if title else DEFAULT_TITLE
            else:
                title = DEFAULT_TITLE
            
            # Empty title becomes default
            if not title:
                title = DEFAULT_TITLE
            
            # Create session
            session = db.create_session(title)
            
            return ServiceResult(
                success=True,
                data={'session': session}
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to create session: {str(e)}"
            )
    
    def load_session(
        self,
        session_id: str,
        limit_messages: Optional[int] = None
    ) -> ServiceResult:
        """
        Load a session with its messages.
        
        Args:
            session_id: UUID of session to load
            limit_messages: Max messages to return (default 200, max 500)
            
        Returns:
            ServiceResult with data: { "session": {...}, "messages": [...] }
        """
        try:
            # Validate session_id - accept any non-empty string (including legacy IDs)
            if not session_id or not isinstance(session_id, str):
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message="sessionId is required and must be a string"
                )
            
            # Validate limit
            limit_val, _ = _validate_int(limit_messages, "limitMessages",
                                          min_val=1,
                                          max_val=MAX_MESSAGES_PER_LOAD,
                                          default=DEFAULT_MESSAGES_PER_LOAD)
            
            # Get session (allow local sessions to pass through)
            is_local = session_id.startswith(('local_', 'mock_', 'temp_'))
            session = db.get_session(session_id) if not is_local else None
            if session is None and not is_local:
                return ServiceResult(
                    success=False,
                    error_code='NOT_FOUND',
                    error_message=f"Session not found: {session_id}"
                )
            
            # Get messages with limit
            conn = db.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE sessionId = ? 
                    ORDER BY ts DESC
                    LIMIT ?
                ''', (session_id, limit_val))
                rows = cursor.fetchall()
                
                # Reverse to get chronological order
                messages = [db._row_to_message(row) for row in reversed(rows)]
            finally:
                conn.close()
            
            # Log load event
            db.log_event(session_id, 'session_loaded', {'messageCount': len(messages)})
            
            return ServiceResult(
                success=True,
                data={
                    'session': session,
                    'messages': messages
                }
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to load session: {str(e)}"
            )
    
    def rename_session(self, session_id: str, title: str) -> ServiceResult:
        """
        Rename a chat session.
        
        Args:
            session_id: UUID of session to rename
            title: New title (1-100 chars, required)
            
        Returns:
            ServiceResult with data: { "session": {...} }
        """
        try:
            # Validate session_id (allow non-UUID formats for local sessions)
            if not session_id or not isinstance(session_id, str):
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message="sessionId must be a non-empty string"
                )
            
            # Validate title
            valid, err = _validate_string(title, "title", MAX_TITLE_LENGTH, 
                                           required=True, min_length=1)
            if not valid:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=err
                )
            
            # Check session exists (allow local sessions)
            is_local = session_id.startswith(('local_', 'mock_', 'temp_'))
            session = db.get_session(session_id) if not is_local else None
            if session is None and not is_local:
                return ServiceResult(
                    success=False,
                    error_code='NOT_FOUND',
                    error_message=f"Session not found: {session_id}"
                )
            
            # Update title and mark as user-set (prevents auto-title)
            if is_local:
                # For local sessions, just return success
                return ServiceResult(
                    success=True,
                    data={'session': {'id': session_id, 'title': title}}
                )
            
            session = db.update_session(session_id, title=title.strip(), title_set_by_user=True)
            
            # Log event
            db.log_event(session_id, 'session_renamed', {'newTitle': title.strip()})
            
            return ServiceResult(
                success=True,
                data={'session': session}
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to rename session: {str(e)}"
            )
    
    def delete_session(self, session_id: str) -> ServiceResult:
        """
        Delete a chat session and all its messages/events.
        
        Args:
            session_id: UUID of session to delete
            
        Returns:
            ServiceResult with data: { "deleted": true }
        """
        try:
            # Validate session_id
            valid, err = _validate_uuid(session_id, "sessionId")
            if not valid:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=err
                )
            
            # Check session exists (optional - delete is idempotent)
            session = db.get_session(session_id)
            if not session:
                # Return success even if not found (idempotent delete)
                return ServiceResult(
                    success=True,
                    data={'deleted': True}
                )
            
            # Delete session (cascades to messages and events)
            success = db.delete_session(session_id)
            
            return ServiceResult(
                success=True,
                data={'deleted': success}
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to delete session: {str(e)}"
            )
    
    def pin_session(self, session_id: str, pinned: bool) -> ServiceResult:
        """
        Pin or unpin a chat session.
        
        Args:
            session_id: UUID of session to pin/unpin
            pinned: True to pin, False to unpin
            
        Returns:
            ServiceResult with data: { "session": {...} }
        """
        try:
            # Validate session_id
            valid, err = _validate_uuid(session_id, "sessionId")
            if not valid:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=err
                )
            
            # Coerce pinned to bool
            pinned_val = _validate_bool(pinned, default=True)
            
            # Check session exists (allow local sessions)
            is_local = session_id.startswith(('local_', 'mock_', 'temp_'))
            session = db.get_session(session_id) if not is_local else None
            if session is None and not is_local:
                return ServiceResult(
                    success=False,
                    error_code='NOT_FOUND',
                    error_message=f"Session not found: {session_id}"
                )
            
            # For local sessions, return success without database update
            if is_local:
                return ServiceResult(
                    success=True,
                    data={'session': {'id': session_id, 'pinned': pinned_val}}
                )
            
            # Update pinned status
            session = db.update_session(session_id, pinned=pinned_val)
            
            # Log event
            event_type = 'session_pinned' if pinned_val else 'session_unpinned'
            db.log_event(session_id, event_type, {})
            
            return ServiceResult(
                success=True,
                data={'session': session}
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to pin session: {str(e)}"
            )
    
    def append_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        events: Optional[List[Dict[str, Any]]] = None
    ) -> ServiceResult:
        """
        Append messages (and optionally events) to a session.
        
        Args:
            session_id: UUID of session
            messages: List of message objects (max 50)
                Each message: { role, content, id?, ts?, status? }
            events: Optional list of event objects (max 20)
                Each event: { type, data? }
            
        Returns:
            ServiceResult with data: { "session": {...}, "messageCount": n }
        """
        try:
            # Validate session_id (allow non-UUID formats for local sessions)
            if not session_id or not isinstance(session_id, str):
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message="sessionId must be a non-empty string"
                )
            
            # Validate messages array
            if not isinstance(messages, list):
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message="messages must be an array"
                )
            
            if len(messages) > MAX_MESSAGES_PER_APPEND:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=f"messages array exceeds maximum of {MAX_MESSAGES_PER_APPEND}"
                )
            
            # Validate each message
            validated_messages = []
            for i, msg in enumerate(messages):
                validated, err = _validate_message(msg, i)
                if err:
                    return ServiceResult(
                        success=False,
                        error_code='INVALID_PAYLOAD',
                        error_message=err
                    )
                validated_messages.append(validated)
            
            # Validate events if provided
            validated_events = []
            if events is not None:
                if not isinstance(events, list):
                    return ServiceResult(
                        success=False,
                        error_code='INVALID_PAYLOAD',
                        error_message="events must be an array"
                    )
                
                if len(events) > MAX_EVENTS_PER_APPEND:
                    return ServiceResult(
                        success=False,
                        error_code='INVALID_PAYLOAD',
                        error_message=f"events array exceeds maximum of {MAX_EVENTS_PER_APPEND}"
                    )
                
                for i, evt in enumerate(events):
                    validated, err = _validate_event(evt, i)
                    if err:
                        return ServiceResult(
                            success=False,
                            error_code='INVALID_PAYLOAD',
                            error_message=err
                        )
                    validated_events.append(validated)
            
            # Check session exists (skip for local sessions which don't persist to backend)
            is_local_session = session_id.startswith(('local_', 'mock_', 'temp_'))
            session = db.get_session(session_id) if not is_local_session else None
            
            if session is None and not is_local_session:
                return ServiceResult(
                    success=False,
                    error_code='NOT_FOUND',
                    error_message=f"Session not found: {session_id}"
                )
            
            # Auto-title: On first user message, set title if not user-renamed (only for backend sessions)
            should_auto_title = (
                session is not None and
                not session.get('titleSetByUser', False) and
                session.get('title') in (DEFAULT_TITLE, 'New Chat', 'New chat') and
                any(m['role'] == 'user' for m in validated_messages)
            )
            
            if should_auto_title:
                # Check if session has no existing messages (first message)
                existing_msgs = db.get_messages(session_id)
                if not existing_msgs:
                    # Get first user message content for auto-title
                    first_user_msg = next(
                        (m for m in validated_messages if m['role'] == 'user'), 
                        None
                    )
                    if first_user_msg:
                        auto_title = _generate_auto_title(first_user_msg['content'])
                        db.update_session(session_id, title=auto_title)
            
            # For local sessions, skip database persistence (handled by frontend)
            if is_local_session:
                return ServiceResult(
                    success=True,
                    data={
                        'session': {'id': session_id, 'title': 'New Chat'},
                        'messageCount': len(validated_messages)
                    }
                )
            
            # Append messages to database
            for msg in validated_messages:
                meta = {'status': msg.get('status', 'complete')} if 'status' in msg else None
                db.add_message(
                    session_id=session_id,
                    role=msg['role'],
                    content=msg['content'],
                    message_id=msg.get('id'),
                    ts=msg.get('ts') if isinstance(msg.get('ts'), int) else None,
                    meta=meta
                )
            
            # Log events
            for evt in validated_events:
                db.log_event(session_id, evt['type'], evt.get('data'))
            
            # Get updated session
            session = db.get_session(session_id)
            
            return ServiceResult(
                success=True,
                data={
                    'session': session,
                    'messageCount': len(validated_messages)
                }
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to append messages: {str(e)}"
            )
    
    def search_sessions(
        self,
        query: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        search_content: bool = True,
        include_archived: bool = False
    ) -> ServiceResult:
        """
        Search sessions by title and optionally message content.
        
        Args:
            query: Search query string (1-200 chars, required)
            limit: Maximum sessions to return (default 50, max 100)
            cursor: Pagination cursor (format: "updatedAt:sessionId")
            search_content: If True, also search message content (default True)
            include_archived: If True, include archived sessions
            
        Returns:
            ServiceResult with data:
            {
                "sessions": [
                    {
                        ...session fields...,
                        "matchType": "title" | "content" | "both",
                        "snippet": "...matching text...",
                        "matchCount": 5
                    }
                ],
                "nextCursor": "..." | null,
                "totalMatches": 42
            }
        """
        try:
            # Validate query
            if not query or not isinstance(query, str):
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message="query is required"
                )
            
            query = query.strip()
            if len(query) < MIN_SEARCH_QUERY_LENGTH:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=f"query must be at least {MIN_SEARCH_QUERY_LENGTH} character(s)"
                )
            
            if len(query) > MAX_SEARCH_QUERY_LENGTH:
                return ServiceResult(
                    success=False,
                    error_code='INVALID_PAYLOAD',
                    error_message=f"query must be at most {MAX_SEARCH_QUERY_LENGTH} characters"
                )
            
            # Validate limit
            limit_val, _ = _validate_int(limit, "limit",
                                          min_val=1,
                                          max_val=MAX_SESSIONS_PER_PAGE,
                                          default=DEFAULT_SESSIONS_PER_PAGE)
            
            # Decode cursor
            cursor_ts, cursor_id = _decode_cursor(cursor) if cursor else (None, None)
            
            # Coerce booleans
            search_content_val = _validate_bool(search_content, default=True)
            include_archived_val = _validate_bool(include_archived, default=False)
            
            # Perform search
            result = db.search_sessions(
                query=query,
                limit=limit_val,
                cursor_ts=cursor_ts,
                cursor_id=cursor_id,
                search_content=search_content_val,
                include_archived=include_archived_val
            )
            
            return ServiceResult(
                success=True,
                data=result
            )
            
        except Exception as e:
            return ServiceResult(
                success=False,
                error_code='DB_ERROR',
                error_message=f"Failed to search sessions: {str(e)}"
            )


# ============================================
# Module Interface
# ============================================

# Global service instance
_service: Optional[HistoryService] = None


def get_service() -> HistoryService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = HistoryService()
    return _service
