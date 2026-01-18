# Chat History Testing Guide

## Quick Start

### 1. Launch Fusion 360 with Copilot

1. **Start Fusion 360**
2. **Open the Electrify Copilot palette**
   - Look for the Electrify Copilot add-in in the Tools menu
   - The palette should appear with a chat interface

### 2. Verify Chat History is Working

#### Initial Load Check
- ✅ **Sidebar should be visible** on the left (if not, click the hamburger menu ☰)
- ✅ **"New Chat" button** should appear at the top
- ✅ **Search box** should be present
- ✅ **No banner** should show (unless backend is offline)

#### Create Your First Session
1. Type a message: "Hello, test message"
2. Send it
3. **Expected**: Session appears in sidebar with auto-generated title (~first 40 chars of message)

#### Test Basic Operations
1. **New Chat**: Click "New Chat" button → new session created
2. **Switch Sessions**: Click different sessions in sidebar → messages load
3. **Rename**: Hover over session → click pencil icon → enter new name → Save
4. **Pin**: Hover over session → click pin icon → session moves to top
5. **Delete**: Hover over session → click trash icon → confirm → session removed
6. **Search**: Type in search box → matching sessions appear

### 3. Test Persistence (Fusion Reload)

1. **Before closing**:
   - Note the sessions you have
   - Note which are pinned
   - Note any custom names

2. **Close Fusion 360 completely**

3. **Reopen Fusion 360**

4. **Open Copilot palette again**

5. **Verify**:
   - ✅ All sessions still present
   - ✅ Pinned sessions still at top
   - ✅ Custom names preserved
   - ✅ Messages load when clicking sessions

## Troubleshooting

### No Sidebar / History Not Loading

**Check Developer Console** (if available in Fusion palette webview):
- Look for errors mentioning "history"
- Check if backend is responding to history_list action

**Backend Check**:
- Ensure `history_handlers.py`, `history_service.py`, `chat_history.py` are in the same folder as `ElectrifyCopilotUI.py`
- Check Fusion's Python console for import errors

### "History Unavailable" Banner Appears

This means the backend connection failed. Possible causes:
- Python backend not running
- Import errors in history modules
- Database initialization failed

**To diagnose**:
1. Check Fusion's Python console for errors
2. Click the "Retry" button in the banner
3. If it persists, check database file location

### Database Location

Chat history is stored in SQLite database:
```
%APPDATA%\Electrify\copilot_history.db
```

On Windows, typically:
```
C:\Users\<YourUsername>\AppData\Roaming\Electrify\copilot_history.db
```

You can:
- Delete this file to reset history
- Use SQLite browser to inspect it
- Copy it to backup your history

### Session Not Saving Messages

**Check**:
- Are you seeing console errors about "history_append"?
- Is the session ID valid (not starting with "temp_")?

**Temp Sessions**: If backend is offline, you'll work in a temporary session (ID starts with `temp_`). When backend reconnects, you'll be prompted to save it.

## Feature Checklist

Use this to verify all features work:

### Core Features
- [ ] Sessions persist across Fusion restarts
- [ ] Create new session with "New Chat" button
- [ ] Auto-title from first message (~40 chars)
- [ ] Switch between sessions loads correct messages
- [ ] Messages appear in chronological order

### Session Management
- [ ] Rename session (pencil icon)
- [ ] Pin session (moves to top)
- [ ] Unpin session (returns to chronological order)
- [ ] Delete session (with confirmation)
- [ ] Most recently updated session loads on startup

### Search
- [ ] Search by session title
- [ ] Search by message content
- [ ] Clear search returns all sessions
- [ ] Search results update in real-time

### UI/UX
- [ ] Sidebar collapses/expands (hamburger button)
- [ ] Hover shows session actions (pin/rename/delete)
- [ ] Active session highlighted
- [ ] Pinned sessions show pin indicator
- [ ] Empty state shows when no sessions

### Resilience
- [ ] Works offline (temp session mode)
- [ ] "History unavailable" banner with retry
- [ ] Can migrate temp session when reconnected
- [ ] Large sessions (200+ messages) load without hanging
- [ ] Corrupted DB doesn't crash Fusion

## Manual Testing Checklist

See: [tests/test_chat_history.py](tests/test_chat_history.py) - search for `MANUAL_TEST_CHECKLIST`

Or run:
```bash
python tests/test_chat_history.py --manual
```

## Automated Tests

Run full test suite:
```bash
cd "c:\Users\choij\KiCad Plugin\electrify\fusion_addin\ElectrifyCopilotUI"
python tests/test_chat_history.py --auto
```

Expected output: All 14 tests pass ✓

## Known Limitations

1. **200 Message Limit**: Sessions with more than 200 messages only load the most recent 200
2. **No Cloud Sync**: History is local to your machine
3. **No Export**: Currently no way to export chat history (but you can access the SQLite DB directly)
4. **Search is Simple**: Basic text matching, no fuzzy search or regex

## Debug Mode

To enable verbose logging (if implemented):

1. Open browser dev tools (if available in Fusion webview)
2. Look for console logs with prefix `[History]`
3. Check for `HistoryClient` debug tracking messages

## Support

If you encounter issues:

1. **Check the database**:
   ```
   %APPDATA%\Electrify\copilot_history.db
   ```

2. **Reset history** (if corrupted):
   - Close Fusion 360
   - Delete the database file
   - Restart Fusion
   - Fresh database will be created

3. **Check Python errors**:
   - Look in Fusion 360's Python console
   - Check for import errors or exceptions

4. **Browser console** (if accessible):
   - Look for JavaScript errors
   - Check network tab for failed messages

---

**Enjoy your persistent chat history! 🎉**
