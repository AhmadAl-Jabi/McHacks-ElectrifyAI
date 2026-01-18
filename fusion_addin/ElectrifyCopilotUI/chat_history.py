# ============================================
# Electrify Copilot - Chat History Module
# SQLite-backed session persistence
# Protocol v1.1.0 - Strict JSON message protocol
# ============================================

import os
import json
import sqlite3
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# Database configuration
DB_FILENAME = 'copilot_chat_history.db'
CURRENT_SCHEMA_VERSION = 1
PROTOCOL_VERSION = '1.1.0'


def get_db_path() -> str:
    """Get the database file path (in the add-in directory)."""
    add_in_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(add_in_dir, DB_FILENAME)


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory and foreign keys enabled."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


# ============================================
# Timestamp Utilities
# ============================================

def _ts_now() -> int:
    """Get current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def _ts_to_iso(ts: int) -> str:
    """Convert Unix timestamp (ms) to ISO 8601 string."""
    return datetime.utcfromtimestamp(ts / 1000).isoformat() + 'Z'


def _iso_to_ts(iso_str: str) -> int:
    """Convert ISO 8601 string to Unix timestamp (ms)."""
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1]
    dt = datetime.fromisoformat(iso_str)
    return int(dt.timestamp() * 1000)


# ============================================
# Database Initialization & Migrations
# ============================================

def init_database():
    """Initialize the database schema with migrations."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Schema version table (for migrations)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL,
                description TEXT
            )
        ''')
        
        # Check current schema version
        cursor.execute('SELECT MAX(version) as v FROM schema_version')
        row = cursor.fetchone()
        current_version = row['v'] if row['v'] is not None else 0
        
        # Run migrations
        if current_version < 1:
            _migrate_v1(cursor)
            cursor.execute('''
                INSERT INTO schema_version (version, applied_at, description)
                VALUES (1, ?, 'Initial schema: sessions, messages, events tables')
            ''', (_ts_now(),))
        
        conn.commit()
    finally:
        conn.close()


def _migrate_v1(cursor: sqlite3.Cursor):
    """
    Migration v1: Create initial schema.
    
    Tables:
      - sessions(id TEXT PK, title TEXT, createdAt INT, updatedAt INT, pinned INT, summary TEXT NULL)
      - messages(id TEXT PK, sessionId TEXT, role TEXT, content TEXT, ts INT, metaJson TEXT)
      - events(id TEXT PK, sessionId TEXT, type TEXT, ts INT, dataJson TEXT)
    
    Indexes:
      - sessions.updatedAt, sessions.pinned
      - messages.sessionId, messages.ts
    """
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            pinned INTEGER DEFAULT 0,
            titleSetByUser INTEGER DEFAULT 0,
            summary TEXT
        )
    ''')
    
    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sessionId TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ts INTEGER NOT NULL,
            metaJson TEXT,
            FOREIGN KEY (sessionId) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    
    # Events table (for analytics/debugging)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            sessionId TEXT NOT NULL,
            type TEXT NOT NULL,
            ts INTEGER NOT NULL,
            dataJson TEXT,
            FOREIGN KEY (sessionId) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    
    # Indexes for sessions
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_updatedAt 
        ON sessions(updatedAt DESC)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_pinned 
        ON sessions(pinned DESC)
    ''')
    
    # Indexes for messages
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_messages_sessionId 
        ON messages(sessionId)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_messages_ts 
        ON messages(ts)
    ''')
    
    # Index for events
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_events_sessionId 
        ON events(sessionId)
    ''')


def get_schema_version() -> int:
    """Get current schema version."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(version) as v FROM schema_version')
        row = cursor.fetchone()
        return row['v'] if row and row['v'] else 0
    except Exception:
        return 0
    finally:
        conn.close()


# ============================================
# Session CRUD Operations
# ============================================

def create_session(title: str = "New Chat") -> Dict[str, Any]:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    now = _ts_now()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (id, title, createdAt, updatedAt, pinned, titleSetByUser, summary)
            VALUES (?, ?, ?, ?, 0, 0, NULL)
        ''', (session_id, title, now, now))
        conn.commit()
        
        return _make_session_response(session_id, title, now, now, False, None, 0, '', False)
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a single session by ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        
        if row:
            return _row_to_session(row, cursor)
        return None
    finally:
        conn.close()


def list_sessions(
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    search_query: str = ''
) -> List[Dict[str, Any]]:
    """List sessions ordered by pinned status and update time."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        query = 'SELECT * FROM sessions WHERE 1=1'
        params: List[Any] = []
        
        if search_query:
            # Search in title and summary, also search message content
            query += ''' AND (
                title LIKE ? 
                OR summary LIKE ? 
                OR id IN (SELECT DISTINCT sessionId FROM messages WHERE content LIKE ?)
            )'''
            search_pattern = f'%{search_query}%'
            params.extend([search_pattern, search_pattern, search_pattern])
        
        query += ' ORDER BY pinned DESC, updatedAt DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [_row_to_session(row, cursor) for row in rows]
    finally:
        conn.close()


def search_sessions(
    query: str,
    limit: int = 50,
    cursor_ts: Optional[int] = None,
    cursor_id: Optional[str] = None,
    search_content: bool = True,
    include_archived: bool = False
) -> Dict[str, Any]:
    """
    Search sessions with snippet preview and match counts.
    
    Args:
        query: Search query string
        limit: Maximum sessions to return
        cursor_ts: Pagination cursor - updatedAt timestamp
        cursor_id: Pagination cursor - session ID
        search_content: If True, also search message content
        include_archived: If True, include archived sessions
        
    Returns:
        {
            'sessions': [...],  # Session dicts with extra search fields
            'nextCursor': '...' | None,
            'totalMatches': int
        }
        
        Each session includes:
        - matchType: 'title' | 'content' | 'both'
        - snippet: First matching content snippet
        - matchCount: Number of matching messages
    """
    if not query or not query.strip():
        return {'sessions': [], 'nextCursor': None, 'totalMatches': 0}
    
    search_pattern = f'%{query}%'
    conn = get_connection()
    
    try:
        db_cursor = conn.cursor()
        
        # Build the search query
        # First, find sessions matching title
        title_match_sql = '''
            SELECT id, 'title' as match_source
            FROM sessions 
            WHERE title LIKE ?
        '''
        
        # Find sessions with matching message content
        content_match_sql = '''
            SELECT DISTINCT sessionId as id, 'content' as match_source
            FROM messages 
            WHERE content LIKE ?
        '''
        
        # Combine results
        if search_content:
            combined_sql = f'''
                WITH matches AS (
                    {title_match_sql}
                    UNION ALL
                    {content_match_sql}
                ),
                session_matches AS (
                    SELECT 
                        id,
                        GROUP_CONCAT(DISTINCT match_source) as match_sources,
                        COUNT(*) as source_count
                    FROM matches
                    GROUP BY id
                )
                SELECT 
                    s.*,
                    sm.match_sources,
                    sm.source_count
                FROM sessions s
                INNER JOIN session_matches sm ON s.id = sm.id
            '''
            params = [search_pattern, search_pattern]
        else:
            combined_sql = f'''
                WITH session_matches AS (
                    SELECT id, 'title' as match_sources, 1 as source_count
                    FROM sessions 
                    WHERE title LIKE ?
                )
                SELECT 
                    s.*,
                    sm.match_sources,
                    sm.source_count
                FROM sessions s
                INNER JOIN session_matches sm ON s.id = sm.id
            '''
            params = [search_pattern]
        
        # Add cursor-based pagination
        if cursor_ts is not None and cursor_id is not None:
            combined_sql += '''
                WHERE (s.updatedAt < ? OR (s.updatedAt = ? AND s.id < ?))
            '''
            params.extend([cursor_ts, cursor_ts, cursor_id])
        
        # Order and limit
        combined_sql += '''
            ORDER BY s.pinned DESC, s.updatedAt DESC, s.id DESC
            LIMIT ?
        '''
        params.append(limit + 1)  # +1 to check for more
        
        db_cursor.execute(combined_sql, params)
        rows = db_cursor.fetchall()
        
        # Check if there's more
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        
        # Process results
        sessions = []
        for row in rows:
            # Base session data
            session = _row_to_session(row, db_cursor)
            
            # Determine match type
            match_sources = row['match_sources'] if row['match_sources'] else 'title'
            if 'title' in match_sources and 'content' in match_sources:
                session['matchType'] = 'both'
            elif 'content' in match_sources:
                session['matchType'] = 'content'
            else:
                session['matchType'] = 'title'
            
            # Get match count and snippet for content matches
            if search_content:
                match_info = _get_search_match_info(db_cursor, row['id'], query)
                session['matchCount'] = match_info['count']
                session['snippet'] = match_info['snippet']
            else:
                session['matchCount'] = 1 if query.lower() in session['title'].lower() else 0
                session['snippet'] = _highlight_match(session['title'], query)
            
            sessions.append(session)
        
        # Generate next cursor
        next_cursor = None
        if has_more and sessions:
            last = sessions[-1]
            last_ts = _iso_to_ts(last['updatedAt'])
            next_cursor = f"{last_ts}:{last['id']}"
        
        # Get total count (without pagination)
        total_matches = _count_search_matches(db_cursor, query, search_content)
        
        return {
            'sessions': sessions,
            'nextCursor': next_cursor,
            'totalMatches': total_matches
        }
        
    finally:
        conn.close()


def _get_search_match_info(cursor: sqlite3.Cursor, session_id: str, query: str) -> Dict[str, Any]:
    """Get match count and best snippet for a session."""
    search_pattern = f'%{query}%'
    
    # Count matching messages
    cursor.execute('''
        SELECT COUNT(*) as cnt FROM messages 
        WHERE sessionId = ? AND content LIKE ?
    ''', (session_id, search_pattern))
    count_row = cursor.fetchone()
    count = count_row['cnt'] if count_row else 0
    
    # Get first matching message for snippet
    cursor.execute('''
        SELECT content FROM messages 
        WHERE sessionId = ? AND content LIKE ?
        ORDER BY ts ASC
        LIMIT 1
    ''', (session_id, search_pattern))
    snippet_row = cursor.fetchone()
    
    snippet = ''
    if snippet_row and snippet_row['content']:
        snippet = _extract_snippet(snippet_row['content'], query, max_length=100)
    
    return {'count': count, 'snippet': snippet}


def _extract_snippet(content: str, query: str, max_length: int = 100) -> str:
    """Extract a snippet around the first match, with highlighting."""
    query_lower = query.lower()
    content_lower = content.lower()
    
    # Find first match position
    pos = content_lower.find(query_lower)
    if pos == -1:
        # No match found, return truncated content
        return content[:max_length] + ('...' if len(content) > max_length else '')
    
    # Calculate window around match
    query_len = len(query)
    context_size = (max_length - query_len) // 2
    
    start = max(0, pos - context_size)
    end = min(len(content), pos + query_len + context_size)
    
    # Extract snippet
    snippet = content[start:end]
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = '...' + snippet
    if end < len(content):
        snippet = snippet + '...'
    
    return snippet


def _highlight_match(text: str, query: str) -> str:
    """Return text with match location for highlighting (just returns text for now)."""
    # Could add HTML highlighting here if needed
    return text[:100] + ('...' if len(text) > 100 else '')


def _count_search_matches(cursor: sqlite3.Cursor, query: str, search_content: bool) -> int:
    """Count total matching sessions."""
    search_pattern = f'%{query}%'
    
    if search_content:
        cursor.execute('''
            SELECT COUNT(DISTINCT id) as cnt FROM (
                SELECT id FROM sessions WHERE title LIKE ?
                UNION
                SELECT DISTINCT sessionId as id FROM messages WHERE content LIKE ?
            )
        ''', (search_pattern, search_pattern))
    else:
        cursor.execute('''
            SELECT COUNT(*) as cnt FROM sessions WHERE title LIKE ?
        ''', (search_pattern,))
    
    row = cursor.fetchone()
    return row['cnt'] if row else 0


def update_session(
    session_id: str,
    title: Optional[str] = None,
    pinned: Optional[bool] = None,
    summary: Optional[str] = None,
    title_set_by_user: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """Update session metadata."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if title is not None:
            updates.append('title = ?')
            params.append(title)
        
        if pinned is not None:
            updates.append('pinned = ?')
            params.append(1 if pinned else 0)
        
        if summary is not None:
            updates.append('summary = ?')
            params.append(summary)
        
        if title_set_by_user is not None:
            updates.append('titleSetByUser = ?')
            params.append(1 if title_set_by_user else 0)
        
        if not updates:
            return get_session(session_id)
        
        updates.append('updatedAt = ?')
        params.append(_ts_now())
        params.append(session_id)
        
        cursor.execute(f'''
            UPDATE sessions SET {', '.join(updates)} WHERE id = ?
        ''', params)
        conn.commit()
        
        return get_session(session_id)
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages/events (cascade)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Log deletion event before deleting (will cascade delete with session)
        _log_event_internal(cursor, session_id, 'session_deleted', {'sessionId': session_id})
        
        # Delete session (messages and events cascade due to foreign keys)
        cursor.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================
# Message CRUD Operations
# ============================================

def add_message(
    session_id: str,
    role: str,
    content: str,
    message_id: Optional[str] = None,
    ts: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Add a message to a session."""
    msg_id = message_id or str(uuid.uuid4())
    msg_ts = ts or _ts_now()
    meta_json = json.dumps(meta) if meta else None
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Insert message
        cursor.execute('''
            INSERT INTO messages (id, sessionId, role, content, ts, metaJson)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (msg_id, session_id, role, content, msg_ts, meta_json))
        
        # Update session updatedAt
        cursor.execute('UPDATE sessions SET updatedAt = ? WHERE id = ?', (msg_ts, session_id))
        
        # Auto-generate title from first user message if title is "New Chat"
        cursor.execute('SELECT title FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        if row and row['title'] == 'New Chat' and role == 'user':
            auto_title = content[:50].strip()
            if len(content) > 50:
                auto_title += '...'
            cursor.execute('UPDATE sessions SET title = ? WHERE id = ?', (auto_title, session_id))
        
        conn.commit()
        
        return {
            'id': msg_id,
            'sessionId': session_id,
            'role': role,
            'content': content,
            'ts': _ts_to_iso(msg_ts),
            'status': meta.get('status', 'complete') if meta else 'complete'
        }
    finally:
        conn.close()


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a session."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE sessionId = ? 
            ORDER BY ts ASC
        ''', (session_id,))
        rows = cursor.fetchall()
        
        return [_row_to_message(row) for row in rows]
    finally:
        conn.close()


def clear_messages(session_id: str) -> bool:
    """Clear all messages from a session."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE sessionId = ?', (session_id,))
        cursor.execute('UPDATE sessions SET updatedAt = ?, summary = NULL WHERE id = ?',
                       (_ts_now(), session_id))
        conn.commit()
        return True
    finally:
        conn.close()


def save_session_messages(session_id: str, messages: List[Dict[str, Any]]) -> bool:
    """Save/replace all messages for a session (batch operation)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now = _ts_now()
        
        # Clear existing messages
        cursor.execute('DELETE FROM messages WHERE sessionId = ?', (session_id,))
        
        # Insert all new messages
        for msg in messages:
            msg_id = msg.get('id', str(uuid.uuid4()))
            msg_ts = msg.get('ts')
            if isinstance(msg_ts, str):
                msg_ts = _iso_to_ts(msg_ts)
            elif msg_ts is None:
                msg_ts = now
            
            meta = {}
            if 'status' in msg:
                meta['status'] = msg['status']
            meta_json = json.dumps(meta) if meta else None
            
            cursor.execute('''
                INSERT INTO messages (id, sessionId, role, content, ts, metaJson)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                msg_id,
                session_id,
                msg.get('role', 'user'),
                msg.get('content', ''),
                msg_ts,
                meta_json
            ))
        
        # Update session updatedAt
        cursor.execute('UPDATE sessions SET updatedAt = ? WHERE id = ?', (now, session_id))
        
        conn.commit()
        return True
    finally:
        conn.close()


# ============================================
# Events Operations
# ============================================

def _log_event_internal(cursor: sqlite3.Cursor, session_id: str, event_type: str, 
                        data: Optional[Dict[str, Any]] = None) -> str:
    """Internal: Log an event using existing cursor (no commit)."""
    event_id = str(uuid.uuid4())
    now = _ts_now()
    data_json = json.dumps(data) if data else None
    
    try:
        cursor.execute('''
            INSERT INTO events (id, sessionId, type, ts, dataJson)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_id, session_id, event_type, now, data_json))
        return event_id
    except Exception:
        return ''


def log_event(session_id: str, event_type: str, data: Optional[Dict[str, Any]] = None) -> str:
    """Log an event for a session."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        event_id = _log_event_internal(cursor, session_id, event_type, data)
        conn.commit()
        return event_id
    except Exception:
        # Events are non-critical, don't fail on errors
        return ''
    finally:
        conn.close()


def get_events(session_id: str, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get events for a session, optionally filtered by type."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        if event_type:
            cursor.execute('''
                SELECT * FROM events WHERE sessionId = ? AND type = ? ORDER BY ts ASC
            ''', (session_id, event_type))
        else:
            cursor.execute('''
                SELECT * FROM events WHERE sessionId = ? ORDER BY ts ASC
            ''', (session_id,))
        
        rows = cursor.fetchall()
        return [{
            'id': row['id'],
            'sessionId': row['sessionId'],
            'type': row['type'],
            'ts': _ts_to_iso(row['ts']),
            'data': json.loads(row['dataJson']) if row['dataJson'] else None
        } for row in rows]
    finally:
        conn.close()


# ============================================
# Helper Functions
# ============================================

def _get_message_count(cursor: sqlite3.Cursor, session_id: str) -> int:
    """Get message count for a session."""
    cursor.execute('SELECT COUNT(*) as cnt FROM messages WHERE sessionId = ?', (session_id,))
    row = cursor.fetchone()
    return row['cnt'] if row else 0


def _get_preview(cursor: sqlite3.Cursor, session_id: str) -> str:
    """Get preview text (last message content, truncated)."""
    cursor.execute('''
        SELECT content FROM messages WHERE sessionId = ? ORDER BY ts DESC LIMIT 1
    ''', (session_id,))
    row = cursor.fetchone()
    if row and row['content']:
        return row['content'][:100]
    return ''


def _make_session_response(
    session_id: str,
    title: str,
    created_at: int,
    updated_at: int,
    pinned: bool,
    summary: Optional[str],
    message_count: int,
    preview: str = '',
    title_set_by_user: bool = False
) -> Dict[str, Any]:
    """Create a session response dict matching protocol schema."""
    return {
        'id': session_id,
        'title': title,
        'createdAt': _ts_to_iso(created_at),
        'updatedAt': _ts_to_iso(updated_at),
        'pinned': pinned,
        'archived': False,  # Kept for protocol compatibility
        'messageCount': message_count,
        'preview': preview or (summary[:100] if summary else ''),
        'titleSetByUser': title_set_by_user
    }


def _row_to_session(row: sqlite3.Row, cursor: sqlite3.Cursor) -> Dict[str, Any]:
    """Convert a database row to a session dict."""
    session_id = row['id']
    # Handle titleSetByUser column (may not exist in old databases)
    try:
        title_set_by_user = bool(row['titleSetByUser'])
    except (KeyError, IndexError):
        title_set_by_user = False
    
    return _make_session_response(
        session_id=session_id,
        title=row['title'],
        created_at=row['createdAt'],
        updated_at=row['updatedAt'],
        pinned=bool(row['pinned']),
        summary=row['summary'],
        message_count=_get_message_count(cursor, session_id),
        preview=_get_preview(cursor, session_id),
        title_set_by_user=title_set_by_user
    )


def _row_to_message(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a database row to a message dict."""
    meta = json.loads(row['metaJson']) if row['metaJson'] else {}
    return {
        'id': row['id'],
        'sessionId': row['sessionId'],
        'role': row['role'],
        'content': row['content'],
        'ts': _ts_to_iso(row['ts']),
        'status': meta.get('status', 'complete')
    }


# ============================================
# JSON Protocol Handler (v1.1.0)
# Strict request/response format with requestId correlation
# ============================================

class ChatHistoryHandler:
    """
    Handles chat history JSON protocol messages (v1.1.0).
    
    Request format (from UI):
    {
        "v": "1.1.0",
        "requestId": "req_xxx",
        "ts": "2026-01-14T12:34:56.789Z",
        "payload": { ... }
    }
    
    Response format (to UI):
    - history_list_result: { sessions: [...] }
    - history_create_result: { session: {...} }
    - history_load_result: { session: {...}, messages: [...] }
    - history_ok: { session?: {...}, deleted?: true }
    - history_error: { code: "...", message: "...", details?: {...} }
    """
    
    # Error codes
    ERR_NOT_FOUND = 'NOT_FOUND'
    ERR_INVALID_PAYLOAD = 'INVALID_PAYLOAD'
    ERR_DB_ERROR = 'DB_ERROR'
    ERR_UNKNOWN = 'UNKNOWN'
    
    def __init__(self):
        init_database()
    
    def handle(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a chat history action.
        Returns a response dict with appropriate response action type.
        """
        request_id = data.get('requestId', f'req_{_ts_now()}_0')
        payload = data.get('payload', {})
        
        try:
            response_action, result = self._dispatch(action, payload)
            return self._make_response(response_action, request_id, result)
        except ValueError as e:
            return self._make_error_response(request_id, self.ERR_INVALID_PAYLOAD, str(e))
        except KeyError as e:
            return self._make_error_response(request_id, self.ERR_NOT_FOUND, str(e))
        except sqlite3.Error as e:
            return self._make_error_response(request_id, self.ERR_DB_ERROR, str(e))
        except Exception as e:
            return self._make_error_response(request_id, self.ERR_UNKNOWN, str(e))
    
    def _make_response(self, action: str, request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a success response."""
        return {
            'action': action,
            'v': PROTOCOL_VERSION,
            'requestId': request_id,
            'ts': _ts_to_iso(_ts_now()),
            'payload': payload
        }
    
    def _make_error_response(self, request_id: str, code: str, message: str, 
                              details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an error response."""
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
            'ts': _ts_to_iso(_ts_now()),
            'payload': payload
        }
    
    def _dispatch(self, action: str, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Dispatch action to appropriate handler. Returns (response_action, result)."""
        handlers = {
            'history_list': self._handle_list,
            'history_create': self._handle_create,
            'history_load': self._handle_load,
            'history_append': self._handle_append,
            'history_delete': self._handle_delete,
            'history_rename': self._handle_rename,
            'history_pin': self._handle_pin,
            'history_search': self._handle_search,
        }
        
        handler = handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        
        return handler(payload)
    
    def _handle_list(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """List all sessions -> history_list_result."""
        sessions = list_sessions(
            include_archived=payload.get('includeArchived', False),
            limit=payload.get('limit', 50),
            offset=payload.get('offset', 0)
        )
        return ('history_list_result', {'sessions': sessions})
    
    def _handle_create(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Create a new session -> history_create_result."""
        title = payload.get('title', 'New Chat')
        session = create_session(title)
        return ('history_create_result', {'session': session})
    
    def _handle_load(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Load a session with all its messages -> history_load_result."""
        session_id = payload.get('sessionId')
        if not session_id:
            raise ValueError("sessionId is required")
        
        session = get_session(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")
        
        messages = get_messages(session_id)
        
        # Log load event
        log_event(session_id, 'session_loaded', {'messageCount': len(messages)})
        
        return ('history_load_result', {
            'session': session,
            'messages': messages
        })
    
    def _handle_append(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Append a message to a session -> history_ok."""
        session_id = payload.get('sessionId')
        message = payload.get('message', {})
        
        if not session_id:
            raise ValueError("sessionId is required")
        if not message:
            raise ValueError("message is required")
        
        # Ensure session exists
        session = get_session(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")
        
        # Parse message timestamp
        msg_ts = message.get('ts')
        if isinstance(msg_ts, str):
            msg_ts = _iso_to_ts(msg_ts)
        
        # Build meta from status
        meta = None
        if 'status' in message:
            meta = {'status': message['status']}
        
        # Add the message
        add_message(
            session_id=session_id,
            role=message.get('role', 'user'),
            content=message.get('content', ''),
            message_id=message.get('id'),
            ts=msg_ts,
            meta=meta
        )
        
        # Return updated session
        session = get_session(session_id)
        return ('history_ok', {'session': session})
    
    def _handle_delete(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Delete a session -> history_ok."""
        session_id = payload.get('sessionId')
        if not session_id:
            raise ValueError("sessionId is required")
        
        success = delete_session(session_id)
        return ('history_ok', {'deleted': success})
    
    def _handle_rename(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Rename a session -> history_ok."""
        session_id = payload.get('sessionId')
        title = payload.get('title')
        
        if not session_id:
            raise ValueError("sessionId is required")
        if not title:
            raise ValueError("title is required")
        
        session = get_session(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")
        
        session = update_session(session_id, title=title)
        
        # Log rename event
        log_event(session_id, 'session_renamed', {'newTitle': title})
        
        return ('history_ok', {'session': session})
    
    def _handle_pin(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Pin/unpin a session -> history_ok."""
        session_id = payload.get('sessionId')
        pinned = payload.get('pinned', True)
        
        if not session_id:
            raise ValueError("sessionId is required")
        
        session = get_session(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")
        
        session = update_session(session_id, pinned=pinned)
        
        # Log pin event
        log_event(session_id, 'session_pinned' if pinned else 'session_unpinned', {})
        
        return ('history_ok', {'session': session})
    
    def _handle_search(self, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Search sessions by title/content -> history_list_result."""
        query = payload.get('query', '')
        if not query:
            raise ValueError("query is required")
        
        sessions = list_sessions(
            search_query=query,
            include_archived=payload.get('includeArchived', False),
            limit=payload.get('limit', 50)
        )
        return ('history_list_result', {'sessions': sessions})


# ============================================
# Module Interface
# ============================================

# Global handler instance
_handler: Optional[ChatHistoryHandler] = None


def get_handler() -> ChatHistoryHandler:
    """Get or create the singleton handler instance."""
    global _handler
    if _handler is None:
        _handler = ChatHistoryHandler()
    return _handler


def handle_history_action(action: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for handling chat history actions.
    Called from the main add-in HTMLEventHandler.
    
    Args:
        action: The history action (e.g., 'history_list', 'history_create')
        data: Request data including requestId and payload
        
    Returns:
        Response dict with action, v, requestId, ts, payload
    """
    handler = get_handler()
    return handler.handle(action, data)
