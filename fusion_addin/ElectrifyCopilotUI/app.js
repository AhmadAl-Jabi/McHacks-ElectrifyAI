// ============================================
// Electrify Copilot - Fusion 360 Palette App
// State Management + Rendering
// Version: 1.0.0 with Chat History
// ============================================

(function () {
    'use strict';
    
    console.log('[JS] Electrify Copilot initializing...');
    
    // Show errors in page for debugging in Fusion
    window.addEventListener('error', function(e) {
        console.error('[JS] Window error:', e);
    });
    
    // Guard against double initialization
    if (window.__electrifyCopilotInitialized) {
        console.warn('[History] Electrify Copilot already initialized, skipping');
        return;
    }
    window.__electrifyCopilotInitialized = true;
    
    // Safe localStorage wrapper for Fusion's embedded browser
    let safeLocalStorage = null;
    try {
        safeLocalStorage = window.localStorage;
        // Test if it's actually usable
        safeLocalStorage.setItem('__test__', '1');
        safeLocalStorage.removeItem('__test__');
    } catch (e) {
        console.warn('[History] localStorage not available, using memory fallback');
        // Fallback to in-memory storage
        safeLocalStorage = {
            _data: {},
            getItem: function(key) { return this._data[key] || null; },
            setItem: function(key, value) { this._data[key] = String(value); },
            removeItem: function(key) { delete this._data[key]; },
            clear: function() { this._data = {}; }
        };
    }
    const localStorage = safeLocalStorage;

    // ============================================
    // Constants
    // ============================================
    const STORAGE_KEY = 'copilot_chat_history';
    const SETTINGS_KEY = 'copilot_settings';
    const SIDEBAR_KEY = 'copilot_sidebar_state';
    const MAX_FILES = 10;
    const MAX_TOTAL_SIZE = 20 * 1024 * 1024; // 20MB

    // File type mappings
    const SCHEMATIC_EXTENSIONS = ['.sch', '.brd', '.zip', '.pdf', '.txt', '.json'];
    const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp'];
    const TEXT_EXTENSIONS = ['.txt', '.json'];

    // ============================================
    // DOM Elements
    // ============================================
    const elements = {
        statusDot: document.getElementById('statusDot'),
        statusText: document.getElementById('statusText'),
        messageList: document.getElementById('messageList'),
        emptyState: document.getElementById('emptyState'),
        examplePrompts: document.getElementById('examplePrompts'),
        suggestions: document.getElementById('suggestions'),
        messageInput: document.getElementById('messageInput'),
        sendBtn: document.getElementById('sendBtn'),
        clearChatBtn: document.getElementById('clearChatBtn'),
        contextBar: document.getElementById('contextBar'),
        contextChips: document.getElementById('contextChips'),
        toast: document.getElementById('toast'),
        toastMessage: document.getElementById('toastMessage'),
        toastClose: document.getElementById('toastClose'),
        // New elements for Prompt 11
        actionsBtn: document.getElementById('actionsBtn'),
        actionsMenu: document.getElementById('actionsMenu'),
        addSchematicBtn: document.getElementById('addSchematicBtn'),
        addImageBtn: document.getElementById('addImageBtn'),
        pasteClipboardBtn: document.getElementById('pasteClipboardBtn'),
        clearChatMenuBtn: document.getElementById('clearChatMenuBtn'),
        exportChatBtn: document.getElementById('exportChatBtn'),
        settingsBtn: document.getElementById('settingsBtn'),
        schematicFileInput: document.getElementById('schematicFileInput'),
        imageFileInput: document.getElementById('imageFileInput'),
        attachmentsBar: document.getElementById('attachmentsBar'),
        attachmentsList: document.getElementById('attachmentsList'),
        dropZoneOverlay: document.getElementById('dropZoneOverlay'),
        settingsModal: document.getElementById('settingsModal'),
        settingsCloseBtn: document.getElementById('settingsCloseBtn'),
        themeSelect: document.getElementById('themeSelect'),
        fontSizeSelect: document.getElementById('fontSizeSelect'),
        displayNameInput: document.getElementById('displayNameInput'),
        autoScrollToggle: document.getElementById('autoScrollToggle'),
        showCommandsBtn: document.getElementById('showCommandsBtn'),
        showCommandsMenuBtn: document.getElementById('showCommandsMenuBtn'),
        commandsModal: document.getElementById('commandsModal'),
        commandsList: document.getElementById('commandsList'),
        commandsCloseBtn: document.getElementById('commandsCloseBtn'),
        // Chat History elements
        historySidebar: document.getElementById('historySidebar'),
        sidebarToggle: document.getElementById('sidebarToggle'),
        sidebarOpenBtn: document.getElementById('sidebarOpenBtn'),
        newChatBtn: document.getElementById('newChatBtn'),
        historySearchInput: document.getElementById('historySearchInput'),
        searchClearBtn: document.getElementById('searchClearBtn'),
        sessionList: document.getElementById('sessionList'),
        sessionEmpty: document.getElementById('sessionEmpty'),
        showArchivedBtn: document.getElementById('showArchivedBtn'),
        historyUnavailableBanner: document.getElementById('historyUnavailableBanner'),   
        historyRetryBtn: document.getElementById('historyRetryBtn'),
        // Rename Modal
        renameModal: document.getElementById('renameModal'),
        renameInput: document.getElementById('renameInput'),
        renameCloseBtn: document.getElementById('renameCloseBtn'),
        renameCancelBtn: document.getElementById('renameCancelBtn'),
        renameSaveBtn: document.getElementById('renameSaveBtn'),
        // Delete Modal
        deleteModal: document.getElementById('deleteModal'),
        deleteCloseBtn: document.getElementById('deleteCloseBtn'),
        deleteCancelBtn: document.getElementById('deleteCancelBtn'),
        deleteConfirmBtn: document.getElementById('deleteConfirmBtn'),
        // Component Info
        componentInfoBtn: document.getElementById('componentInfoBtn'),
        componentInfoModal: document.getElementById('componentInfoModal'),
        componentInfoBody: document.getElementById('componentInfoBody'),
        componentInfoCloseBtn: document.getElementById('componentInfoCloseBtn')
    };

    // ============================================
    // State Store
    // Message schema: { id, role, content, ts, status }
    // - id: unique string identifier
    // - role: 'user' | 'assistant' | 'error'
    // - content: message text
    // - ts: ISO timestamp
    // - status: 'sending' | 'streaming' | 'complete' | 'error'
    // ============================================
    const state = {
        messages: [],
        isTyping: false,
        isConnected: true,
        currentStreamingId: null,
        userHasScrolled: false,
        contextHints: new Set(), // Selected context toggles
        attachments: [], // Current pending attachments: { id, file, name, size, mime, kind }
        settings: {
            theme: 'system',
            fontSize: 'medium',
            displayName: '',
            autoScroll: true
        },
        // Chat History State
        history: {
            sessions: [],              // Session metadata only (no messages)
            activeSessionId: null,     // Currently selected session
            lastActiveSessionId: null, // Last active before deletion
            messagesBySession: {},     // Cache: sessionId -> messages[]
            sidebarOpen: true,
            searchQuery: '',
            showArchived: false,
            pendingRequests: new Map(), // requestId -> { resolve, reject, rollback? }
            optimisticOps: new Map(),   // requestId -> { type, snapshot }
            pendingDeletes: new Set(),  // sessionIds pending deletion (authoritative filter)
            renameSessionId: null,
            deleteSessionId: null,
            available: true,           // Backend availability flag
            initialized: false         // Startup complete flag
        }
    };

    // Alias for backward compatibility
    Object.defineProperty(state.history, 'currentSessionId', {
        get() { return this.activeSessionId; },
        set(v) { this.activeSessionId = v; }
    });

    // ============================================
    // Debug Tracking
    // ============================================
    const debug = {
        enabled: false,
        lastOutbound: null,  // { ts, action, bytes, json }
        lastInbound: null,   // { ts, action, bytes, json }
    };

    function trackOutbound(action, payload) {
        const json = JSON.stringify(payload);
        debug.lastOutbound = {
            ts: new Date().toISOString(),
            action,
            bytes: new Blob([json]).size,
            json
        };
        if (debug.enabled) {
            console.log('[Debug OUT]', action, debug.lastOutbound.bytes, 'bytes');
        }
    }

    function trackInbound(action, data) {
        const json = typeof data === 'string' ? data : JSON.stringify(data);
        debug.lastInbound = {
            ts: new Date().toISOString(),
            action,
            bytes: new Blob([json]).size,
            json
        };
        if (debug.enabled) {
            console.log('[Debug IN]', action, debug.lastInbound.bytes, 'bytes');
        }
    }

    // ============================================
    // HistoryClient - API wrapper for history operations
    // ============================================
    const HistoryClient = {
        /**
         * List sessions with optional filters
         * @param {object} opts - { limit?, cursor?, pinnedOnly? }
         */
        list: function(opts = {}) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: {
                    limit: opts.limit || 50,
                    cursor: opts.cursor || null,
                    pinnedOnly: opts.pinnedOnly || false
                }
            };
            return sendHistoryRequest(requestId, 'history_list', envelope);
        },

        /**
         * Create a new session
         * @param {string} title - Session title
         */
        create: function(title = 'New Chat') {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { title }
            };
            return sendHistoryRequest(requestId, 'history_create', envelope);
        },

        /**
         * Load a session with its messages
         * @param {string} sessionId - Session ID to load
         */
        load: function(sessionId) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { sessionId }
            };
            return sendHistoryRequest(requestId, 'history_load', envelope);
        },

        /**
         * Rename a session
         * @param {string} sessionId - Session ID
         * @param {string} title - New title
         */
        rename: function(sessionId, title) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { sessionId, title }
            };
            return sendHistoryRequest(requestId, 'history_rename', envelope);
        },

        /**
         * Delete a session
         * @param {string} sessionId - Session ID
         */
        delete: function(sessionId) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { sessionId }
            };
            return sendHistoryRequest(requestId, 'history_delete', envelope);
        },

        /**
         * Pin or unpin a session
         * @param {string} sessionId - Session ID
         * @param {boolean} pinned - Pin state
         */
        pin: function(sessionId, pinned) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { sessionId, pinned }
            };
            return sendHistoryRequest(requestId, 'history_pin', envelope);
        },

        /**
         * Append messages to a session
         * @param {string} sessionId - Session ID
         * @param {array} messages - Messages to append
         * @param {array} events - Events to log (optional)
         */
        append: function(sessionId, messages, events = []) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: { sessionId, messages, events }
            };
            return sendHistoryRequest(requestId, 'history_append', envelope);
        },

        /**
         * Search sessions
         * @param {string} query - Search query
         * @param {object} opts - { searchContent?, limit?, cursor? }
         */
        search: function(query, opts = {}) {
            const requestId = generateRequestId();
            const envelope = {
                v: '1.1.0',
                requestId,
                ts: new Date().toISOString(),
                payload: {
                    query,
                    searchContent: opts.searchContent !== false,
                    limit: opts.limit || 20,
                    cursor: opts.cursor || null
                }
            };
            return sendHistoryRequest(requestId, 'history_search', envelope);
        }
    };

    /**
     * Send a history request via adsk.fusionSendData
     */
    function sendHistoryRequest(requestId, action, envelope) {
        return new Promise((resolve, reject) => {
            state.history.pendingRequests.set(requestId, { resolve, reject });

            // Timeout after 10s
            setTimeout(() => {
                if (state.history.pendingRequests.has(requestId)) {
                    state.history.pendingRequests.delete(requestId);
                    const optimistic = state.history.optimisticOps.get(requestId);
                    if (optimistic) {
                        rollbackOptimistic(optimistic);
                        state.history.optimisticOps.delete(requestId);
                    }
                    reject(new Error('Request timeout'));
                }
            }, 10000);

            // Send via adsk.fusionSendData or mock
            const jsonStr = JSON.stringify(envelope);
            trackOutbound(action, envelope);

            if (typeof adsk !== 'undefined' && adsk.fusionSendData) {
                adsk.fusionSendData(action, jsonStr);
            } else {
                // Mock mode
                mockFusionResponse(action, envelope);
            }
        });
    }

    // ============================================
    // Request ID Generation & Tracking
    // ============================================
    let requestCounter = 0;
    
    function generateRequestId() {
        return 'req_' + Date.now() + '_' + (++requestCounter);
    }

    /**
     * Generate unique message ID
     */
    function generateId() {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Get message by ID
     */
    function getMessageById(id) {
        return state.messages.find(m => m.id === id);
    }

    /**
     * Get message index by ID
     */
    function getMessageIndexById(id) {
        return state.messages.findIndex(m => m.id === id);
    }

    // ============================================
    // Message State Functions (Public API)
    // ============================================

    /**
     * Extract keywords from text to generate a chat title
     * Removes common words and returns first 3-5 significant words
     */
    function generateTitleFromText(text) {
        // Common words to skip (stop words)
        const stopWords = new Set([
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
            'the', 'to', 'was', 'will', 'with', 'what', 'how', 'when', 'where',
            'why', 'this', 'which', 'who', 'can', 'could', 'do', 'does', 'did',
            'should', 'would', 'may', 'might', 'must', 'shall', 'me', 'my', 'we'
        ]);
        
        // Split into words, filter stop words, take first 4 significant words
        const words = text
            .toLowerCase()
            .split(/\s+/)
            .filter(w => w.length > 2 && !stopWords.has(w))
            .slice(0, 4);
        
        if (words.length === 0) {
            return 'New Chat';
        }
        
        // Capitalize first letter of each word
        return words
            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ');
    }
    
    /**
     * Auto-rename chat on first user message if it's still named "New Chat"
     */
    function autoRenameSessionIfNeeded(sessionId, firstUserMessage) {
        const session = state.history.sessions.find(s => s.id === sessionId);
        if (!session) {
            console.warn('[AutoRename] Session not found:', sessionId);
            return;
        }
        
        // Only auto-rename if still has default name
        if (session.title === 'New Chat') {
            const newTitle = generateTitleFromText(firstUserMessage);
            // Only rename if we generated something meaningful (not just "New Chat")
            if (newTitle !== 'New Chat') {
                console.log('[AutoRename] Renaming session to:', newTitle);
                renameSession(sessionId, newTitle);
            } else {
                console.log('[AutoRename] No meaningful keywords found, keeping "New Chat"');
            }
        } else {
            console.log('[AutoRename] Session already renamed to:', session.title);
        }
    }

    /**
     * Add a user message to the chat
     * Single-writer: Frontend generates ID/ts, backend validates and stores
     * @param {string} text - The message content
     * @returns {string} - The message ID
     */
    function addUserMessage(text) {
        const message = {
            id: generateId(),
            role: 'user',
            content: text,
            ts: new Date().toISOString(),
            status: 'complete'
        };

        state.messages.push(message);
        
        // Cache message immediately for offline resilience
        if (state.history.activeSessionId) {
            if (!state.history.messagesBySession[state.history.activeSessionId]) {
                state.history.messagesBySession[state.history.activeSessionId] = [];
            }
            state.history.messagesBySession[state.history.activeSessionId].push(message);
            saveSessionsToLocalStorage();
            
            // Auto-rename chat on first user message
            if (state.messages.filter(m => m.role === 'user').length === 1) {
                autoRenameSessionIfNeeded(state.history.activeSessionId, text);
            }
        }
        
        renderMessage(message);
        hideSuggestions();
        updateEmptyState();
        scrollToBottom(true); // Force scroll on user message
        saveToLocalStorage();

        // Single-writer: persist to backend immediately
        persistMessageToBackend(message);

        return message.id;
    }

    /**
     * Add an assistant message to the chat
     * @param {string} text - The message content
     * @param {string} [status='complete'] - Message status
     * @returns {string} - The message ID
     */
    function addAssistantMessage(text, status = 'complete') {
        const message = {
            id: generateId(),
            role: 'assistant',
            content: text,
            ts: new Date().toISOString(),
            status: status
        };

        state.messages.push(message);
        
        // Cache message immediately for offline resilience
        if (state.history.activeSessionId) {
            if (!state.history.messagesBySession[state.history.activeSessionId]) {
                state.history.messagesBySession[state.history.activeSessionId] = [];
            }
            state.history.messagesBySession[state.history.activeSessionId].push(message);
            saveSessionsToLocalStorage();
        }
        
        if (status === 'streaming') {
            state.currentStreamingId = message.id;
        }

        renderMessage(message);
        setTyping(false);
        scrollToBottom();
        saveToLocalStorage();

        return message.id;
    }

    /**
     * Update an existing assistant message (for streaming)
     * @param {string} id - The message ID to update
     * @param {string} newText - The new/appended text content
     * @param {boolean} [append=false] - If true, append to existing content
     */
    function updateAssistantMessage(id, newText, append = false) {
        const message = getMessageById(id);
        if (!message) {
            console.warn('Message not found:', id);
            return;
        }

        if (append) {
            message.content += newText;
        } else {
            message.content = newText;
        }

        // Update DOM
        const messageEl = document.querySelector(`[data-message-id="${id}"]`);
        if (messageEl) {
            const textEl = messageEl.querySelector('.message-text');
            if (textEl) {
                textEl.innerHTML = formatMessage(message.content);
            }
        }

        scrollToBottom();
    }

    /**
     * Mark a message as complete
     * Single-writer: persists assistant message to backend on completion
     * @param {string} id - The message ID
     */
    function completeMessage(id) {
        const message = getMessageById(id);
        if (message) {
            message.status = 'complete';
            if (state.currentStreamingId === id) {
                state.currentStreamingId = null;
            }
            saveToLocalStorage();
            
            // Cache the message locally for ALL message types
            if (state.history.activeSessionId) {
                if (!state.history.messagesBySession[state.history.activeSessionId]) {
                    state.history.messagesBySession[state.history.activeSessionId] = [];
                }
                // Ensure message is in cache
                const cached = state.history.messagesBySession[state.history.activeSessionId];
                const exists = cached.find(m => m.id === message.id);
                if (!exists) {
                    cached.push(message);
                }
                // Save cache to localStorage immediately
                saveSessionsToLocalStorage();
            }

            // Single-writer: persist assistant message to backend
            if (message.role === 'assistant') {
                persistMessageToBackend(message);
            }
        }
    }

    /**
     * Persist a message to backend via history_append
     * Single-writer rule: frontend is the writer, backend validates/stores
     * @param {object} message - Message object with id, role, content, ts
     */
    function persistMessageToBackend(message) {
        const sessionId = state.history.activeSessionId;
        if (!sessionId) {
            console.warn('[SingleWriter] No active session, skipping persist');
            return;
        }

        // Format message for backend (matches protocol schema)
        const msgPayload = {
            id: message.id,
            role: message.role,
            content: message.content,
            ts: message.ts,
            meta: message.meta || null
        };

        // Fire-and-forget append (errors logged, no UI blocking)
        HistoryClient.append(sessionId, [msgPayload], [])
            .then(() => {
                console.log('[SingleWriter] Persisted:', message.role, message.id);
                // Update session metadata locally
                const session = state.history.sessions.find(s => s.id === sessionId);
                if (session) {
                    session.messageCount = (session.messageCount || 0) + 1;
                    session.updatedAt = new Date().toISOString();
                    session.preview = message.content.slice(0, 100);
                }
            })
            .catch(err => {
                console.error('[SingleWriter] Failed to persist:', err);
                // Message stays in local state, will retry on next save
            });
    }

    /**
     * Add an error message
     * @param {string} text - Error message content
     * @returns {string} - The message ID
     */
    function addErrorMessage(text) {
        const message = {
            id: generateId(),
            role: 'error',
            content: text,
            ts: new Date().toISOString(),
            status: 'complete'
        };

        state.messages.push(message);
        renderMessage(message);
        setTyping(false);
        scrollToBottom();

        return message.id;
    }

    /**
     * Show or hide the typing indicator
     * @param {boolean} isTyping - Whether to show typing indicator
     */
    function setTyping(isTyping) {
        state.isTyping = isTyping;

        // Remove existing indicator
        const existing = document.getElementById('typingIndicator');
        if (existing) existing.remove();

        if (isTyping) {
            const typingEl = document.createElement('div');
            typingEl.className = 'message';
            typingEl.id = 'typingIndicator';
            typingEl.innerHTML = `
                <div class="message-avatar assistant">⚡</div>
                <div class="message-content">
                    <div class="message-role">Electrify Copilot</div>
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
            elements.messageList.appendChild(typingEl);
            scrollToBottom();
        }
        // Ensure send/stop button reflects new typing state
        updateInputState();
    }

    /**
     * Show a toast notification
     * @param {string} text - Toast message
     * @param {string} [type='info'] - Toast type: 'info' | 'success' | 'warning' | 'error'
     * @param {number} [duration=5000] - Auto-hide duration in ms (0 = no auto-hide)
     */
    let toastTimeout = null;

    function showToast(text, type = 'info', duration = 5000) {
        elements.toast.className = 'toast ' + type;
        elements.toastMessage.textContent = text;
        elements.toast.classList.remove('hidden');

        if (toastTimeout) {
            clearTimeout(toastTimeout);
            toastTimeout = null;
        }

        if (duration > 0) {
            toastTimeout = setTimeout(hideToast, duration);
        }
    }

    /**
     * Hide the toast notification
     */
    function hideToast() {
        elements.toast.classList.add('hidden');
        if (toastTimeout) {
            clearTimeout(toastTimeout);
            toastTimeout = null;
        }
    }

    /**
     * Clear all messages
     */
    function clearChat() {
        state.messages = [];
        state.currentStreamingId = null;
        state.isTyping = false;
        state.userHasScrolled = false;
        elements.messageList.innerHTML = '';
        showSuggestions();
        updateEmptyState();
        updateInputState();
        saveToLocalStorage();
    }

    // ============================================
    // LocalStorage Persistence
    // ============================================

    /**
     * Save messages to localStorage
     */
    function saveToLocalStorage() {
        try {
            const data = {
                messages: state.messages,
                savedAt: new Date().toISOString()
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (error) {
            console.warn('[Storage] Failed to save:', error);
        }
    }

    /**
     * Load messages from localStorage
     */
    function loadFromLocalStorage() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const data = JSON.parse(stored);
                if (data.messages && Array.isArray(data.messages)) {
                    state.messages = data.messages;
                    return true;
                }
            }
        } catch (error) {
            console.warn('[Storage] Failed to load:', error);
        }
        return false;
    }

    /**
     * Get all messages (for export/debug)
     */
    function getMessages() {
        return [...state.messages];
    }

    // ============================================
    // Rendering Functions
    // ============================================

    /**
     * Render a single message to the DOM
     */
    function renderMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message';
        messageEl.dataset.messageId = message.id;

        // Add role-specific class
        if (message.role === 'user') {
            messageEl.classList.add('user-message');
        }

        // Determine avatar and label based on role
        let avatarClass, avatarEmoji, roleLabel;
        
        switch (message.role) {
            case 'user':
                avatarClass = 'user';
                avatarEmoji = '👤';
                roleLabel = state.settings.displayName && state.settings.displayName.trim() ? state.settings.displayName : 'You';
                break;
            case 'assistant':
                avatarClass = 'assistant';
                avatarEmoji = '⚡';
                roleLabel = 'Electrify Copilot';
                break;
            case 'error':
                avatarClass = 'error';
                avatarEmoji = '⚠️';
                roleLabel = 'Error';
                break;
            default:
                avatarClass = 'assistant';
                avatarEmoji = '⚡';
                roleLabel = 'System';
        }

        // Add status indicator for streaming messages
        const statusClass = message.status === 'streaming' ? ' streaming' : '';

        messageEl.innerHTML = `
            <div class="message-avatar ${avatarClass}">${avatarEmoji}</div>
            <div class="message-content">
                <div class="message-role">${roleLabel}</div>
                <div class="message-text${statusClass}">${formatMessage(message.content)}</div>
            </div>
        `;

        elements.messageList.appendChild(messageEl);
        
        // Add copy buttons to code blocks
        addCopyButtonsToCodeBlocks(messageEl);

        // Add right-click context menu for assistant messages
        if (message.role === 'assistant') {
            messageEl.addEventListener('contextmenu', (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                openMessageContextMenu(ev.clientX, ev.clientY, messageEl);
            });
        }
    }

    /**
     * Add copy buttons to all code blocks in a message element
     */
    function addCopyButtonsToCodeBlocks(messageEl) {
        const codeBlocks = messageEl.querySelectorAll('pre');
        codeBlocks.forEach(pre => {
            // Create wrapper for positioning
            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-wrapper';
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);
            
            // Create copy button
            const copyBtn = document.createElement('button');
            copyBtn.className = 'code-copy-btn';
            copyBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="14" height="14">
                    <path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                </svg>
                <span>Copy</span>
            `;
            copyBtn.title = 'Copy code';
            
            copyBtn.addEventListener('click', () => {
                const code = pre.querySelector('code');
                const text = code ? code.textContent : pre.textContent;
                copyToClipboard(text, copyBtn);
            });
            
            wrapper.appendChild(copyBtn);
        });
    }

    /**
     * Copy text to clipboard using execCommand fallback (works in embedded browsers)
     */
    function doCopy(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
        document.body.appendChild(textarea);
        textarea.select();
        textarea.setSelectionRange(0, text.length); // iOS support
        let success = false;
        try {
            success = document.execCommand('copy');
        } catch (e) {
            success = false;
        }
        document.body.removeChild(textarea);
        return success;
    }

    /**
     * Copy text to clipboard and show feedback on a button
     */
    function copyToClipboard(text, button) {
        const success = doCopy(text);
        if (success) {
            // Show success feedback
            const originalHTML = button.innerHTML;
            button.innerHTML = `
                <svg viewBox="0 0 24 24" width="14" height="14">
                    <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span>Copied!</span>
            `;
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove('copied');
            }, 2000);
        } else {
            console.error('Failed to copy');
            showToast('Failed to copy to clipboard', 'error');
        }
    }

    /**
     * Re-render all messages from state
     */
    function renderAllMessages() {
        elements.messageList.innerHTML = '';
        state.messages.forEach(msg => renderMessage(msg));
        
        if (state.isTyping) {
            setTyping(true);
        }
        
        scrollToBottom();
    }

    /**
     * Format message text with markdown-like syntax
     */
    function formatMessage(text) {
        if (!text) return '';

        // Escape HTML
        let formatted = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks (```code```)
        formatted = formatted.replace(
            /```(\w*)\n?([\s\S]*?)```/g,
            '<pre><code class="language-$1">$2</code></pre>'
        );

        // Inline code (`code`)
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold (**text**)
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic (*text*)
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Paragraphs (double newline)
        const paragraphs = formatted.split('\n\n');
        if (paragraphs.length > 1) {
            formatted = paragraphs
                .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
                .join('');
        } else {
            formatted = formatted.replace(/\n/g, '<br>');
        }

        return formatted;
    }

    // ============================================
    // UI Helper Functions
    // ============================================

    /**
     * Scroll to bottom - respects user scroll and auto-scroll setting
     * @param {boolean} force - Force scroll even if user has scrolled up
     */
    function scrollToBottom(force = false) {
        // Respect auto-scroll setting (unless forced)
        if (!force && !state.settings.autoScroll) {
            return;
        }
        
        if (!force && state.userHasScrolled) {
            return; // Don't fight the user
        }
        
        requestAnimationFrame(() => {
            elements.messageList.scrollTop = elements.messageList.scrollHeight;
        });
    }

    /**
     * Check if user is near the bottom of the message list
     */
    function isNearBottom() {
        const threshold = 100; // pixels from bottom
        const { scrollTop, scrollHeight, clientHeight } = elements.messageList;
        return scrollHeight - scrollTop - clientHeight < threshold;
    }

    /**
     * Handle scroll events to detect user scrolling
     */
    function handleScroll() {
        state.userHasScrolled = !isNearBottom();
    }

    function updateInputState() {
        const hasText = elements.messageInput.value.trim().length > 0;
        const hasAttachments = state.attachments.length > 0;
        const canSend = (hasText || hasAttachments) && !state.isTyping && !state.currentStreamingId;
        // If generation is in progress, the send button becomes a Stop button
        elements.sendBtn.disabled = !(canSend || state.isTyping || state.currentStreamingId);
        updateSendButtonState();
    }

    function autoResizeTextarea() {
        const input = elements.messageInput;
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 300) + 'px';
    }

    function hideSuggestions() {
        elements.suggestions.classList.add('hidden');
        elements.emptyState.classList.add('hidden');
    }

    function showSuggestions() {
        elements.suggestions.classList.remove('hidden');
        if (state.messages.length === 0) {
            elements.emptyState.classList.remove('hidden');
        }
    }

    /**
     * Update empty state visibility based on message count
     */
    function updateEmptyState() {
        if (state.messages.length === 0) {
            elements.emptyState.classList.remove('hidden');
            elements.messageList.classList.add('hidden');
        } else {
            elements.emptyState.classList.add('hidden');
            elements.messageList.classList.remove('hidden');
        }
    }

    /**
     * Send an example prompt (insert and send immediately)
     */
    function sendExamplePrompt(promptText) {
        elements.messageInput.value = promptText;
        autoResizeTextarea();
        updateInputState();
        handleSendMessage();
    }

    function updateConnectionStatus(connected, message) {
        state.isConnected = connected;
        elements.statusDot.className = 'status-dot' + (connected ? '' : ' disconnected');
        elements.statusText.textContent = message || (connected ? 'Ready' : 'Disconnected');
    }

    // ============================================
    // Fusion 360 Communication
    // ============================================

    /**
     * Send data to Fusion 360 Python add-in
     * Falls back to mock responses when running outside Fusion 360
     * @param {string} action - The action name to send
     * @param {object} payloadObj - The payload object (will be JSON stringified)
     */
    function sendToFusion(action, payloadObj) {
        try {
            const jsonStr = JSON.stringify(payloadObj);
            trackOutbound(action, payloadObj);
            
            // Check if running inside Fusion 360
            if (typeof adsk !== 'undefined' && adsk.fusionSendData) {
                // Production: Send to Fusion 360 host
                adsk.fusionSendData(action, jsonStr);
                console.log('[Fusion] Sent:', action, payloadObj);
            } else {
                // Development: Mock mode for browser testing
                console.log('[Mock] sendToFusion:', action, payloadObj);
                mockFusionResponse(action, payloadObj);
            }
        } catch (error) {
            console.error('[sendToFusion] Error:', error);
            showToast('Failed to communicate with Fusion 360', 'error');
        }
    }

    /**
     * Mock Fusion 360 responses for browser testing
     * Echoes back fake assistant responses after 300ms
     * Uses the new copilot_* action names
     */
    function mockFusionResponse(action, payload) {
        switch (action) {
            case 'discover_commands':
                // Return a sample list of commands (mock)
                setTimeout(() => {
                    const cmds = [
                        { name: 'ADD R', description: 'Place resistor at X,Y with value' },
                        { name: 'ADD C', description: 'Place capacitor at X,Y with value' },
                        { name: 'REPORT CONTEXT', description: 'Return active schematic/context info' },
                        { name: 'LIST SHEETS', description: 'List available schematic sheets' }
                    ];
                    window.fusionJavaScriptHandler.handle('commands_list', JSON.stringify({ commands: cmds }));
                }, 200);
                break;
            case 'sendMessage':
                // Simulate streaming response after 300ms
                setTimeout(() => {
                    let mockResponses = [
                        "I've analyzed your design. I found several opportunities for electrical integration.\n\nHere are my recommendations:\n\n1. **Mount points** - Add 4 M3 standoffs in the corners\n2. **Cable routing** - Use the internal channels\n3. **Ventilation** - Consider adding slots near heat sources",
                        "Based on the geometry, I recommend routing wiring along the internal channels.\n\n```python\n# Example wire path calculation\npath = calculate_wire_route(start, end)\nprint(f'Total length: {path.length}mm')\n```",
                        "Your enclosure dimensions are compatible with standard electrical components. The `85mm x 55mm` footprint fits common DC-DC converters.",
                        "I can help you select appropriate connectors and mounting hardware for this design.\n\n**Suggested connectors:**\n- JST-XH for internal connections\n- USB-C for external power\n- XT30 for high current paths"
                    ];
                    
                    let response = mockResponses[Math.floor(Math.random() * mockResponses.length)];
                    
                    // Mention attachments if present
                    if (payload.attachments && payload.attachments.length > 0) {
                        const fileCount = payload.attachments.length;
                        const imageCount = payload.attachments.filter(a => a.kind === 'image').length;
                        const docCount = fileCount - imageCount;
                        
                        let attachmentNote = `\n\n---\n📎 **Received ${fileCount} file(s):** `;
                        if (imageCount > 0) attachmentNote += `${imageCount} image(s)`;
                        if (imageCount > 0 && docCount > 0) attachmentNote += ', ';
                        if (docCount > 0) attachmentNote += `${docCount} document(s)`;
                        attachmentNote += '\n\n*Files: ' + payload.attachments.map(a => a.name).join(', ') + '*';
                        
                        response += attachmentNote;
                    }
                    
                    // Use copilot_reply (the new primary action)
                    window.fusionJavaScriptHandler.handle(
                        'copilot_reply',
                        JSON.stringify({ message: response })
                    );
                }, 300);
                break;

            case 'paletteReady':
                console.log('[Mock] Palette ready, version:', payload.version);
                // Simulate connection confirmation using copilot_status
                setTimeout(() => {
                    window.fusionJavaScriptHandler.handle(
                        'copilot_status',
                        JSON.stringify({ connected: true, message: 'Mock Mode' })
                    );
                }, 100);
                break;


            case 'newChat':
                console.log('[Mock] New chat requested');
                break;

            default:
                // Handle history actions in mock mode
                if (action.startsWith('history_')) {
                    console.log('[Mock] History action:', action, payload);
                    mockHistoryResponse(action, payload);
                } else {
                    console.log('[Mock] Unhandled action:', action);
                }
        }
    }

    /**
     * Mock history responses for browser testing (Protocol v1.1.0)
     */
    function mockHistoryResponse(action, payload) {
        const requestId = payload.requestId;
        let responseAction = 'history_ok';
        let responsePayload = {};
        
        switch (action) {
            case 'history_list':
                responseAction = 'history_list_result';
                responsePayload = { sessions: state.history.sessions, nextCursor: null };
                break;
                
            case 'history_create':
                responseAction = 'history_create_result';
                const newSession = {
                    id: 'mock_' + Date.now(),
                    title: payload.payload?.title || 'New Chat',
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString(),
                    pinned: false,
                    archived: false,
                    messageCount: 0,
                    preview: ''
                };
                state.history.sessions.unshift(newSession);
                responsePayload = { session: newSession };
                break;
                
            case 'history_load':
                responseAction = 'history_load_result';
                const session = state.history.sessions.find(s => s.id === payload.payload?.sessionId);
                responsePayload = {
                    session: session || null,
                    messages: [],
                    events: []
                };
                break;
                
            case 'history_save':
            case 'history_append':
                responseAction = 'history_ok';
                responsePayload = {};
                break;
                
            case 'history_delete':
                responseAction = 'history_ok';
                state.history.sessions = state.history.sessions.filter(
                    s => s.id !== payload.payload?.sessionId
                );
                responsePayload = {};
                break;
                
            case 'history_rename':
            case 'history_pin':
            case 'history_archive':
                responseAction = 'history_ok';
                const targetSession = state.history.sessions.find(s => s.id === payload.payload?.sessionId);
                if (targetSession) {
                    if (action === 'history_rename' && payload.payload?.title) {
                        targetSession.title = payload.payload.title;
                    }
                    if (action === 'history_pin' && typeof payload.payload?.pinned !== 'undefined') {
                        targetSession.pinned = payload.payload.pinned;
                    }
                    targetSession.updatedAt = new Date().toISOString();
                }
                responsePayload = {};
                break;
                
            case 'history_search':
                responseAction = 'history_list_result';
                const query = (payload.payload?.query || '').toLowerCase();
                const searchContent = payload.payload?.searchContent !== false;
                const filtered = state.history.sessions
                    .filter(s => s.title.toLowerCase().includes(query))
                    .map(s => ({
                        ...s,
                        matchType: 'title',
                        matchCount: 1,
                        snippet: s.preview ? `...${s.preview.slice(0, 60)}...` : null
                    }));
                responsePayload = { sessions: filtered, nextCursor: null };
                break;
                
            default:
                responseAction = 'history_error';
                responsePayload = {
                    code: 'UNKNOWN_ACTION',
                    message: 'Unknown action: ' + action
                };
        }
        
        // Build protocol v1.1.0 response envelope
        const response = {
            action: responseAction,
            v: '1.1.0',
            requestId: requestId,
            ts: new Date().toISOString(),
            payload: responsePayload
        };
        
        // Simulate async response
        setTimeout(() => {
            window.fusionJavaScriptHandler.handle(responseAction, JSON.stringify(response));
        }, 50);
    }

    /**
     * Incoming message handler for Fusion 360 Palette
     * Called by Fusion 360 host via palette.sendInfoToHTML()
     * MUST return a non-empty string (Autodesk requirement)
     * 
     * Supported actions:
     * - copilot_reply: Final assistant message
     * - copilot_stream: Partial text chunk for streaming
     * - copilot_status: Update header status
     * - copilot_error: Show error toast + bubble
     */
    window.fusionJavaScriptHandler = {
        handle: function (action, dataString) {
            try {
                trackInbound(action, dataString);
                const data = dataString ? JSON.parse(dataString) : {};
                console.log('[Handler] Received:', action, data);

                switch (action) {
                    case 'commands_list':
                        // Host (or mock) returns an array of commands to display
                        openCommandsModal(data.commands || []);
                        return 'OK';
                    
                    case 'show_component_info':
                        // Host returns component information to display in modal
                        // Expected data: { name, ref, value, footprint, datasheet, description }
                        openComponentInfoModal(data);
                        return 'OK';
                    
                    // ============================================
                    // Primary Copilot Actions (from Fusion host)
                    // ============================================
                    
                    case 'copilot_reply':
                        // Final complete assistant message
                        // Expected data: { message: string }
                        setTyping(false);
                        if (state.currentStreamingId) {
                            // If we were streaming, complete that message
                            updateAssistantMessage(state.currentStreamingId, data.message, false);
                            completeMessage(state.currentStreamingId);
                        } else {
                            // New complete message
                            addAssistantMessage(data.message || data.text, 'complete');
                        }
                        updateInputState();
                        return 'OK';

                    case 'copilot_stream':
                        // Partial text chunk for streaming response
                        // Expected data: { text: string, done?: boolean }
                        setTyping(false);
                        
                        if (!state.currentStreamingId) {
                            // Start new streaming message
                            addAssistantMessage(data.text || '', 'streaming');
                        } else {
                            // Append to existing streaming message
                            updateAssistantMessage(state.currentStreamingId, data.text, true);
                        }
                        
                        // Check if streaming is complete
                        if (data.done) {
                            completeMessage(state.currentStreamingId);
                            updateInputState();
                        }
                        return 'OK';

                    case 'copilot_status':
                        // Update header status indicator
                        // Expected data: { connected?: boolean, message?: string, status?: string }
                        if (typeof data.connected !== 'undefined') {
                            updateConnectionStatus(data.connected, data.message || data.status);
                        } else if (data.message || data.status) {
                            elements.statusText.textContent = data.message || data.status;
                        }
                        return 'OK';

                    case 'copilot_error':
                        // Show error toast and render error bubble
                        // Expected data: { message: string }
                        setTyping(false);
                        addErrorMessage(data.message || 'An error occurred');
                        showToast(data.message || 'An error occurred', 'error');
                        updateInputState();
                        return 'OK';

                    // ============================================
                    // Legacy/Alternative Actions (for flexibility)
                    // ============================================

                    case 'receiveMessage':
                        // Complete message from assistant (legacy)
                        setTyping(false);
                        addAssistantMessage(data.message || data.text, 'complete');
                        updateInputState();
                        return 'OK';

                    case 'startStreaming':
                        // Start a new streaming message
                        setTyping(false);
                        const streamId = addAssistantMessage(data.text || '', 'streaming');
                        return streamId || 'OK';

                    case 'appendToMessage':
                        // Append to streaming message
                        if (state.currentStreamingId) {
                            updateAssistantMessage(state.currentStreamingId, data.text, true);
                        } else if (data.id) {
                            updateAssistantMessage(data.id, data.text, true);
                        }
                        return 'OK';

                    case 'completeStreaming':
                        // Mark streaming as complete
                        if (state.currentStreamingId) {
                            completeMessage(state.currentStreamingId);
                        } else if (data.id) {
                            completeMessage(data.id);
                        }
                        updateInputState();
                        return 'OK';

                    case 'setTyping':
                        setTyping(data.isTyping);
                        return 'OK';

                    case 'updateStatus':
                        updateConnectionStatus(data.connected, data.message);
                        return 'OK';

                    case 'showError':
                        setTyping(false);
                        addErrorMessage(data.message);
                        showToast(data.message, 'error');
                        updateInputState();
                        return 'OK';

                    case 'showToast':
                        showToast(data.message, data.type || 'info', data.duration);
                        return 'OK';

                    case 'clearChat':
                        clearChat();
                        return 'OK';

                    // ============================================
                    // Chat History Response Actions (Protocol v1.1.0)
                    // ============================================
                    
                    case 'history_response':
                        // Legacy response format (for backward compatibility)
                        // Expected data: { requestId: string, success: boolean, data: any, error: string|null }
                        handleHistoryResponse(data);
                        return 'OK';
                    
                    case 'history_list_result':
                        // Response to history_list or history_search
                        // Expected data: { requestId, payload: { sessions, nextCursor? } }
                        handleHistoryListResult(data);
                        return 'OK';
                    
                    case 'history_create_result':
                        // Response to history_create
                        // Expected data: { requestId, payload: { session } }
                        handleHistoryCreateResult(data);
                        return 'OK';
                    
                    case 'history_load_result':
                        // Response to history_load
                        // Expected data: { requestId, payload: { session, messages, events } }
                        handleHistoryLoadResult(data);
                        return 'OK';
                    
                    case 'history_ok':
                        // Response to history_rename, history_delete, history_pin, history_append
                        // Expected data: { requestId, payload: {} }
                        handleHistoryOk(data);
                        return 'OK';
                    
                    case 'history_error':
                        // Error response from history backend
                        // Expected data: { requestId, payload: { code, message, details? } }
                        handleHistoryError(data);
                        return 'OK';

                    default:
                        console.warn('[Handler] Unknown action:', action);
                        return 'OK';
                }
            } catch (error) {
                console.error('[Handler] Error:', error);
                return 'ERROR: ' + error.message;
            }
        }
    };

    // ============================================
    // User Actions
    // ============================================

    function handleSendMessage() {
        const text = elements.messageInput.value.trim();
        const hasAttachments = state.attachments.length > 0;
        
        // Need either text or attachments to send
        if ((!text && !hasAttachments) || state.isTyping || state.currentStreamingId) return;

        // Build display text for user message (include attachment count)
        let displayText = text;
        if (hasAttachments) {
            const attachmentNames = state.attachments.map(a => a.name).join(', ');
            if (text) {
                displayText = text + `\n\n📎 *Attached: ${attachmentNames}*`;
            } else {
                displayText = `📎 *Attached: ${attachmentNames}*`;
            }
        }

        // Add user message
        addUserMessage(displayText);

        // Clear input
        elements.messageInput.value = '';
        autoResizeTextarea();
        updateInputState();

        // Show typing indicator
        setTyping(true);

        // Build payload with context hints and attachments
        const payload = {
            message: text,
            timestamp: new Date().toISOString(),
            contextHints: Array.from(state.contextHints),
            attachments: [] // Will be populated async
        };

        // Process attachments and send
        processAttachmentsAndSend(payload);
    }

    // Show available commands (prints to chat like help)
    function showAvailableCommands() {
        // Request available commands from the host/backend
        sendToFusion('get_available_commands', {});
    }

    function openCommandsModal(commands) {
        elements.commandsList.innerHTML = '';
        if (!commands || commands.length === 0) {
            elements.commandsList.innerHTML = '<p>No commands available.</p>';
        } else {
            const list = document.createElement('div');
            list.style.display = 'flex';
            list.style.flexDirection = 'column';
            list.style.gap = '8px';
            commands.forEach(cmd => {
                const item = document.createElement('div');
                item.style.padding = '8px';
                item.style.border = '1px solid var(--border-default)';
                item.style.borderRadius = '8px';
                item.innerHTML = `<strong>${cmd.name}</strong><div style="font-size:0.9rem;color:var(--text-muted);">${cmd.description || ''}</div>`;
                list.appendChild(item);
            });
            elements.commandsList.appendChild(list);
        }

        elements.commandsModal.classList.remove('hidden');
        elements.commandsCloseBtn.focus();
    }

    /**
     * Open the Component Info modal with the provided component data
     * @param {object} info - Component info object: { name, ref, value, footprint, datasheet, description }
     */
    function openComponentInfoModal(info) {
        elements.componentInfoBody.innerHTML = '';
        
        if (!info || Object.keys(info).length === 0) {
            elements.componentInfoBody.innerHTML = '<p>No component information available.</p>';
        } else {
            const html = `
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    ${info.name ? `<div><strong>Name:</strong> ${escapeHtml(info.name)}</div>` : ''}
                    ${info.ref ? `<div><strong>Designator:</strong> ${escapeHtml(info.ref)}</div>` : ''}
                    ${info.value ? `<div><strong>Value:</strong> ${escapeHtml(info.value)}</div>` : ''}
                    ${info.footprint ? `<div><strong>Footprint:</strong> ${escapeHtml(info.footprint)}</div>` : ''}
                    ${info.datasheet ? `<div><strong>Datasheet:</strong> <a href="${escapeHtml(info.datasheet)}" target="_blank">Link</a></div>` : ''}
                    ${info.description ? `<div><strong>Description:</strong> ${escapeHtml(info.description)}</div>` : ''}
                </div>
            `;
            elements.componentInfoBody.innerHTML = html;
        }

        elements.componentInfoModal.classList.remove('hidden');
        elements.componentInfoCloseBtn.focus();
    }

    /**
     * Close the Component Info modal
     */
    function closeComponentInfoModal() {
        elements.componentInfoModal.classList.add('hidden');
    }

    /**
     * Request component info from the host (Python add-in)
     */
    function requestComponentInfo() {
        sendToFusion('get_component_info', {});
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Process attachments (encode files) and send the message
     */
    async function processAttachmentsAndSend(payload) {
        try {
            if (state.attachments.length > 0) {
                const encodedAttachments = await Promise.all(
                    state.attachments.map(att => encodeAttachment(att))
                );
                payload.attachments = encodedAttachments;
                
                // Clear attachments after encoding
                clearAttachments();
            }
            
            // Send to Fusion
            sendToFusion('sendMessage', payload);
        } catch (error) {
            console.error('Error processing attachments:', error);
            showToast('Failed to process attachments', 'error');
            setTyping(false);
        }
    }

    /**
     * Encode a single attachment based on its type
     */
    async function encodeAttachment(att) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = () => {
                resolve({
                    name: att.name,
                    mime: att.mime,
                    size: att.size,
                    kind: att.kind,
                    data: reader.result
                });
            };
            
            reader.onerror = () => reject(reader.error);
            
            if (att.kind === 'image') {
                // Images: DataURL
                reader.readAsDataURL(att.file);
            } else if (TEXT_EXTENSIONS.some(ext => att.name.toLowerCase().endsWith(ext))) {
                // Text files: read as text
                reader.readAsText(att.file);
            } else {
                // Binary files: base64
                reader.readAsDataURL(att.file);
            }
        });
    }

    /**
     * Toggle a context chip on/off
     */
    function toggleContextChip(contextKey) {
        if (state.contextHints.has(contextKey)) {
            state.contextHints.delete(contextKey);
        } else {
            state.contextHints.add(contextKey);
        }
        updateContextChipUI();
    }

    /**
     * Update context chip visual state
     */
    function updateContextChipUI() {
        const chips = elements.contextChips.querySelectorAll('.context-chip');
        chips.forEach(chip => {
            const key = chip.dataset.context;
            if (state.contextHints.has(key)) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });
    }

    /**
     * Get selected context hints
     */
    function getContextHints() {
        return Array.from(state.contextHints);
    }

    // Update send button appearance and label depending on generation state
    function updateSendButtonState() {
        const isGenerating = state.isTyping || state.currentStreamingId;
        if (isGenerating) {
            // Stop icon (square)
            elements.sendBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="20" height="20">
                    <rect x="6" y="6" width="12" height="12" fill="currentColor"></rect>
                </svg>`;
            elements.sendBtn.title = 'Stop generation';
            elements.sendBtn.setAttribute('aria-label', 'Stop generation');
            elements.sendBtn.classList.add('stop-mode');
        } else {
            // Send icon (paper plane)
            elements.sendBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="20" height="20">
                    <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>`;
            elements.sendBtn.title = 'Send message';
            elements.sendBtn.setAttribute('aria-label', 'Send message');
            elements.sendBtn.classList.remove('stop-mode');
        }
    }

    // Called when user wants to cancel/stop the current generation
    function handleStopGeneration() {
        if (!state.isTyping && !state.currentStreamingId) return;

        // Notify host to cancel if possible
        try {
            sendToFusion('copilot_cancel', { id: state.currentStreamingId });
        } catch (e) {
            console.warn('Unable to send cancel to host', e);
        }

        // Update UI state locally
        state.currentStreamingId = null;
        setTyping(false);
        updateInputState();
        showToast('Generation stopped', 'warning', 3000);
    }

    // ============================================
    // Event Listeners
    // ============================================

    // Send / Stop button: acts as Stop while generation is running
    elements.sendBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (state.isTyping || state.currentStreamingId) {
            handleStopGeneration();
        } else {
            handleSendMessage();
        }
    });

    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (state.isTyping || state.currentStreamingId) {
                handleStopGeneration();
            } else {
                handleSendMessage();
            }
        }
    });

    elements.messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        updateInputState();
    });

    elements.suggestions.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip');
        if (chip) {
            const prompt = chip.dataset.prompt;
            elements.messageInput.value = prompt;
            autoResizeTextarea();
            updateInputState();
            elements.messageInput.focus();
        }
    });

    elements.toastClose.addEventListener('click', hideToast);

    // Show available commands button in settings (if exists)
    if (elements.showCommandsBtn) {
        elements.showCommandsBtn.addEventListener('click', () => {
            showAvailableCommands();
        });
    }

    // Show commands from actions menu
    if (elements.showCommandsMenuBtn) {
        elements.showCommandsMenuBtn.addEventListener('click', () => {
            closeActionsMenu();
            showAvailableCommands();
        });
    }

    // Example prompts click (empty state)
    elements.examplePrompts.addEventListener('click', (e) => {
        const promptBtn = e.target.closest('.example-prompt');
        if (promptBtn) {
            const promptText = promptBtn.dataset.prompt;
            sendExamplePrompt(promptText);
        }
    });

    // Context chips toggle
    elements.contextChips.addEventListener('click', (e) => {
        const chip = e.target.closest('.context-chip');
        if (chip) {
            const contextKey = chip.dataset.context;
            toggleContextChip(contextKey);
        }
    });

    // Clear chat button
    elements.clearChatBtn.addEventListener('click', () => {
        if (state.messages.length > 0) {
            clearChat();
            showToast('Chat cleared', 'info', 2000);
        }
    });

    // Smart scroll detection
    elements.messageList.addEventListener('scroll', handleScroll);

    // ============================================
    // Actions Menu Event Listeners
    // ============================================
    
    // Toggle actions menu
    elements.actionsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleActionsMenu();
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.actionsMenu.contains(e.target) && !elements.actionsBtn.contains(e.target)) {
            closeActionsMenu();
        }
    });

    // Menu keyboard navigation
    elements.actionsMenu.addEventListener('keydown', (e) => {
        const items = elements.actionsMenu.querySelectorAll('.actions-menu-item');
        const currentIndex = Array.from(items).indexOf(document.activeElement);
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                items[(currentIndex + 1) % items.length].focus();
                break;
            case 'ArrowUp':
                e.preventDefault();
                items[(currentIndex - 1 + items.length) % items.length].focus();
                break;
            case 'Escape':
                closeActionsMenu();
                elements.actionsBtn.focus();
                break;
            case 'Tab':
                closeActionsMenu();
                break;
        }
    });

    // Menu item actions
    elements.addSchematicBtn.addEventListener('click', () => {
        closeActionsMenu();
        elements.schematicFileInput.click();
    });

    elements.addImageBtn.addEventListener('click', () => {
        closeActionsMenu();
        elements.imageFileInput.click();
    });

    elements.pasteClipboardBtn.addEventListener('click', async () => {
        closeActionsMenu();
        await pasteFromClipboard();
    });

    elements.clearChatMenuBtn.addEventListener('click', () => {
        closeActionsMenu();
        if (state.messages.length > 0) {
            clearChat();
            showToast('Chat cleared', 'info', 2000);
        } else {
            showToast('No messages to clear', 'info', 1500);
        }
    });

    elements.exportChatBtn.addEventListener('click', () => {
        closeActionsMenu();
        exportChat();
    });

    elements.settingsBtn.addEventListener('click', () => {
        closeActionsMenu();
        openSettingsModal();
    });

    // File input handlers
    elements.schematicFileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files);
        e.target.value = ''; // Reset to allow same file selection
    });

    elements.imageFileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files);
        e.target.value = '';
    });

    // Drag and drop
    let dragCounter = 0;
    
    document.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) {
            elements.dropZoneOverlay.classList.remove('hidden');
        }
    });

    document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            elements.dropZoneOverlay.classList.add('hidden');
        }
    });

    document.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    document.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        elements.dropZoneOverlay.classList.add('hidden');
        
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files);
        }
    });

    // Attachment remove handlers (delegated)
    elements.attachmentsList.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.attachment-remove');
        if (removeBtn) {
            const id = removeBtn.dataset.attachmentId;
            removeAttachment(id);
        }
    });

    // Settings modal
    elements.settingsCloseBtn.addEventListener('click', closeSettingsModal);
    
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            closeSettingsModal();
        }
    });

    elements.settingsModal.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSettingsModal();
        }
    });

    // Commands modal close
    elements.commandsCloseBtn.addEventListener('click', () => {
        elements.commandsModal.classList.add('hidden');
    });

    elements.commandsModal.addEventListener('click', (e) => {
        if (e.target === elements.commandsModal) {
            elements.commandsModal.classList.add('hidden');
        }
    });

    // Component Info modal close
    if (elements.componentInfoCloseBtn) {
        elements.componentInfoCloseBtn.addEventListener('click', closeComponentInfoModal);
    }

    if (elements.componentInfoModal) {
        elements.componentInfoModal.addEventListener('click', (e) => {
            if (e.target === elements.componentInfoModal) {
                closeComponentInfoModal();
            }
        });
    }

    // Component Info button in actions menu
    if (elements.componentInfoBtn) {
        elements.componentInfoBtn.addEventListener('click', () => {
            requestComponentInfo();
        });
    }

    elements.themeSelect.addEventListener('change', (e) => {
        state.settings.theme = e.target.value;
        applyTheme();
        saveSettings();
    });

    elements.fontSizeSelect.addEventListener('change', (e) => {
        state.settings.fontSize = e.target.value;
        applyFontSize();
        saveSettings();
    });

    // Display name input
    elements.displayNameInput.addEventListener('input', (e) => {
        state.settings.displayName = e.target.value;
        saveSettings();
    });

    elements.autoScrollToggle.addEventListener('change', (e) => {
        state.settings.autoScroll = e.target.checked;
        saveSettings();
    });

    

    // ============================================
    // Actions Menu Functions
    // ============================================

    function toggleActionsMenu() {
        const isOpen = !elements.actionsMenu.classList.contains('hidden');
        if (isOpen) {
            closeActionsMenu();
        } else {
            openActionsMenu();
        }
    }

    function openActionsMenu() {
        elements.actionsMenu.classList.remove('hidden');
        elements.actionsBtn.setAttribute('aria-expanded', 'true');
        // Focus first menu item
        const firstItem = elements.actionsMenu.querySelector('.actions-menu-item');
        if (firstItem) firstItem.focus();
    }

    function closeActionsMenu() {
        elements.actionsMenu.classList.add('hidden');
        elements.actionsBtn.setAttribute('aria-expanded', 'false');
    }

    // ============================================
    // Attachment Functions
    // ============================================

    function handleFileSelect(files) {
        const fileArray = Array.from(files);
        
        // Check file count limit
        if (state.attachments.length + fileArray.length > MAX_FILES) {
            showToast(`Maximum ${MAX_FILES} files allowed`, 'warning');
            return;
        }
        
        // Check total size
        const currentSize = state.attachments.reduce((sum, att) => sum + att.size, 0);
        const newSize = fileArray.reduce((sum, file) => sum + file.size, 0);
        
        if (currentSize + newSize > MAX_TOTAL_SIZE) {
            showToast(`Maximum total size is ${formatFileSize(MAX_TOTAL_SIZE)}`, 'warning');
            return;
        }
        
        // Validate and add files
        fileArray.forEach(file => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            const isImage = IMAGE_EXTENSIONS.includes(ext) || file.type.startsWith('image/');
            const isSchematic = SCHEMATIC_EXTENSIONS.includes(ext);
            
            if (!isImage && !isSchematic) {
                showToast(`Unsupported file type: ${ext}`, 'warning');
                return;
            }
            
            const attachment = {
                id: 'att_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
                file: file,
                name: file.name,
                size: file.size,
                mime: file.type || 'application/octet-stream',
                kind: isImage ? 'image' : 'document'
            };
            
            state.attachments.push(attachment);
        });
        
        renderAttachments();
        updateInputState();
    }

    function removeAttachment(id) {
        state.attachments = state.attachments.filter(att => att.id !== id);
        renderAttachments();
        updateInputState();
    }

    function clearAttachments() {
        state.attachments = [];
        renderAttachments();
    }

    function renderAttachments() {
        if (state.attachments.length === 0) {
            elements.attachmentsBar.classList.add('hidden');
            elements.attachmentsList.innerHTML = '';
            return;
        }
        
        elements.attachmentsBar.classList.remove('hidden');
        elements.attachmentsList.innerHTML = state.attachments.map(att => `
            <div class="attachment-pill" data-attachment-id="${att.id}">
                <span class="attachment-icon">${att.kind === 'image' ? '🖼️' : '📄'}</span>
                <span class="attachment-name" title="${att.name}">${att.name}</span>
                <span class="attachment-size">${formatFileSize(att.size)}</span>
                <button class="attachment-remove" data-attachment-id="${att.id}" aria-label="Remove ${att.name}">&times;</button>
            </div>
        `).join('');
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // ============================================
    // Clipboard Functions
    // ============================================

    async function pasteFromClipboard() {
        try {
            if (!navigator.clipboard || !navigator.clipboard.read) {
                showToast('Clipboard access not supported in this browser', 'warning');
                return;
            }
            
            const items = await navigator.clipboard.read();
            
            for (const item of items) {
                // Check for images
                const imageType = item.types.find(t => t.startsWith('image/'));
                if (imageType) {
                    const blob = await item.getType(imageType);
                    const file = new File([blob], `pasted-image-${Date.now()}.png`, { type: imageType });
                    handleFileSelect([file]);
                    return;
                }
                
                // Check for text (could be file path or content)
                if (item.types.includes('text/plain')) {
                    const blob = await item.getType('text/plain');
                    const text = await blob.text();
                    // Insert into message input
                    elements.messageInput.value += text;
                    autoResizeTextarea();
                    updateInputState();
                    elements.messageInput.focus();
                    return;
                }
            }
            
            showToast('No supported content in clipboard', 'info');
        } catch (error) {
            console.error('Clipboard error:', error);
            showToast('Could not access clipboard', 'warning');
        }
    }

    // ============================================
    // Export Functions
    // ============================================

    function exportChat() {
        if (state.messages.length === 0) {
            showToast('No messages to export', 'info');
            return;
        }
        
        const exportData = {
            exported: new Date().toISOString(),
            messages: state.messages.map(m => ({
                role: m.role,
                content: m.content,
                timestamp: m.ts
            }))
        };
        
        const json = JSON.stringify(exportData, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `electrify-chat-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('Chat exported', 'success', 2000);
    }

    // ============================================
    // Settings Functions
    // ============================================

    function openSettingsModal() {
        elements.settingsModal.classList.remove('hidden');
        elements.settingsCloseBtn.focus();
        document.body.style.overflow = 'hidden';
    }

    function closeSettingsModal() {
        elements.settingsModal.classList.add('hidden');
        document.body.style.overflow = '';
        elements.settingsBtn.focus();
    }

    function applyTheme() {
        document.documentElement.classList.remove('dark', 'light');
        if (state.settings.theme !== 'system') {
            document.documentElement.classList.add(state.settings.theme);
        }
    }

    function applyFontSize() {
        document.documentElement.classList.remove('font-small', 'font-medium', 'font-large');
        document.documentElement.classList.add('font-' + state.settings.fontSize);
    }

    function saveSettings() {
        try {
            localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings));
        } catch (error) {
            console.warn('Failed to save settings:', error);
        }
    }

    function loadSettings() {
        try {
            const stored = localStorage.getItem(SETTINGS_KEY);
            if (stored) {
                const settings = JSON.parse(stored);
                state.settings = { ...state.settings, ...settings };
                
                // Apply to UI
                elements.themeSelect.value = state.settings.theme;
                elements.fontSizeSelect.value = state.settings.fontSize;
                elements.displayNameInput.value = state.settings.displayName || '';
                elements.autoScrollToggle.checked = state.settings.autoScroll;
                
                // Apply visual settings
                applyTheme();
                applyFontSize();
            }
        } catch (error) {
            console.warn('Failed to load settings:', error);
        }
    }

    // ============================================
    // Chat History Functions
    // ============================================

    /**
     * Send a history action to Fusion backend with requestId correlation
     * @param {string} action - The history action (history_list, history_create, etc.)
     * @param {object} payload - The action payload
     * @returns {Promise} - Resolves with response data
     */
    function sendHistoryAction(action, payload = {}) {
        const requestId = generateRequestId();
        return sendHistoryActionWithId(requestId, action, payload);
    }

    /**
     * Send a history action with a specific requestId (for optimistic ops)
     */
    function sendHistoryActionWithId(requestId, action, payload = {}) {
        return new Promise((resolve, reject) => {
            // Store pending request
            state.history.pendingRequests.set(requestId, { resolve, reject });
            
            // Auto-timeout after 10 seconds
            setTimeout(() => {
                if (state.history.pendingRequests.has(requestId)) {
                    state.history.pendingRequests.delete(requestId);
                    // Also trigger rollback on timeout
                    const optimistic = state.history.optimisticOps.get(requestId);
                    if (optimistic) {
                        rollbackOptimistic(optimistic);
                        state.history.optimisticOps.delete(requestId);
                    }
                    reject(new Error('Request timeout'));
                }
            }, 10000);
            
            // Send to Fusion
            sendToFusion(action, { requestId, payload });
        });
    }

    /**
     * Handle history response from Fusion backend (legacy format)
     */
    function handleHistoryResponse(data) {
        const { requestId, success, data: responseData, error } = data;
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            if (success) {
                pending.resolve(responseData);
            } else {
                pending.reject(new Error(error || 'Unknown error'));
            }
        }
    }

    /**
     * Handle history_list_result from backend (Protocol v1.1.0)
     * Response to history_list or history_search
     * Uses REPLACE strategy (not append) and filters out pending deletes
     */
    function handleHistoryListResult(data) {
        const { requestId, payload } = data;
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            // payload: { sessions: [...], nextCursor: string | null }
            
            // Filter out sessions that are pending deletion (authoritative)
            const filteredSessions = (payload.sessions || []).filter(s => 
                !state.history.pendingDeletes.has(s.id)
            );
            
            // REPLACE sessions array (never append/concat to prevent duplicates)
            state.history.sessions = filteredSessions;
            
            pending.resolve(payload);
        }
    }

    /**
     * Handle history_create_result from backend (Protocol v1.1.0)
     * Response to history_create
     */
    function handleHistoryCreateResult(data) {
        const { requestId, payload } = data;
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            // payload: { session }
            pending.resolve(payload);
        }
    }

    /**
     * Handle history_load_result from backend (Protocol v1.1.0)
     * Response to history_load
     */
    function handleHistoryLoadResult(data) {
        const { requestId, payload } = data;
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            // payload: { session, messages, events }
            pending.resolve(payload);
        }
    }

    /**
     * Handle history_ok from backend (Protocol v1.1.0)
     * Response to history_rename, history_delete, history_pin, history_append
     */
    function handleHistoryOk(data) {
        const { requestId, payload } = data;
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            // payload is typically empty {}
            pending.resolve(payload || {});
        }
    }

    /**
     * Handle history_error from backend (Protocol v1.1.0)
     * Performs rollback if optimistic update was applied
     */
    function handleHistoryError(data) {
        const { requestId, payload } = data;
        
        // Check for optimistic rollback
        const optimistic = state.history.optimisticOps.get(requestId);
        if (optimistic) {
            rollbackOptimistic(optimistic);
            state.history.optimisticOps.delete(requestId);
        }
        
        const pending = state.history.pendingRequests.get(requestId);
        if (pending) {
            state.history.pendingRequests.delete(requestId);
            // payload: { code, message, details? }
            const errorMsg = payload?.message || payload?.code || 'Unknown error';
            pending.reject(new Error(errorMsg));
        }
        
        // Also show toast for user visibility
        if (payload?.message) {
            showToast(payload.message, 'error');
        }
    }

    /**
     * Rollback an optimistic update
     */
    function rollbackOptimistic(op) {
        switch (op.type) {
            case 'delete':
                // Restore deleted session
                if (op.snapshot.session) {
                    state.history.sessions.push(op.snapshot.session);
                    sortSessions();
                }
                if (op.snapshot.messages) {
                    state.history.messagesBySession[op.snapshot.sessionId] = op.snapshot.messages;
                }
                renderSessionList();
                showToast('Delete failed, restored chat', 'error');
                break;
            case 'rename':
                // Restore original title
                const renameSession = state.history.sessions.find(s => s.id === op.snapshot.sessionId);
                if (renameSession) {
                    renameSession.title = op.snapshot.title;
                }
                renderSessionList();
                showToast('Rename failed', 'error');
                break;
            case 'pin':
                // Restore original pin state
                const pinSession = state.history.sessions.find(s => s.id === op.snapshot.sessionId);
                if (pinSession) {
                    pinSession.pinned = op.snapshot.pinned;
                    sortSessions();
                }
                renderSessionList();
                showToast('Pin failed', 'error');
                break;
            case 'create':
                // Remove optimistically added session
                state.history.sessions = state.history.sessions.filter(s => s.id !== op.snapshot.tempId);
                if (state.history.activeSessionId === op.snapshot.tempId) {
                    state.history.activeSessionId = state.history.sessions[0]?.id || null;
                }
                renderSessionList();
                showToast('Failed to create chat', 'error');
                break;
        }
    }

    /**
     * Sort sessions: pinned first, then by updatedAt desc
     */
    function sortSessions() {
        state.history.sessions.sort((a, b) => {
            if (a.pinned !== b.pinned) return b.pinned ? 1 : -1;
            return new Date(b.updatedAt) - new Date(a.updatedAt);
        });
    }

    /**
     * Clear optimistic op on success (call from ok handlers)
     */
    function clearOptimisticOp(requestId) {
        state.history.optimisticOps.delete(requestId);
    }

    /**
     * Load chat sessions from backend (startup entry point)
     * - Calls history_list
     * - Opens last session if available, otherwise creates new
     * - Falls back to in-memory mode if backend unavailable
     */
    async function loadSessions() {
        try {
            // Always load messages cache from localStorage for offline resilience
            try {
                const cachedMessages = localStorage.getItem('copilot_messages_cache');
                if (cachedMessages) {
                    state.history.messagesBySession = JSON.parse(cachedMessages);
                    console.log('[History] Loaded messages cache from localStorage');
                }
            } catch (e) {
                console.warn('Failed to load messages cache:', e);
            }
            
            const result = await HistoryClient.list({ limit: 50 });
            state.history.sessions = result.sessions || [];
            state.history.available = true;
            renderSessionList();
            
            // Startup: open last session or create new
            if (!state.history.initialized) {
                state.history.initialized = true;
                if (state.history.sessions.length > 0) {
                    // Open most recent session (first in list, sorted by updatedAt desc)
                    const lastSession = state.history.sessions[0];
                    await loadSession(lastSession.id);
                } else {
                    // No sessions exist, create a new one
                    await createNewSession();
                }
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            handleHistoryUnavailable();
        }
    }

    /**
     * Handle backend unavailability gracefully
     */
    function handleHistoryUnavailable() {
        state.history.available = false;
        
        // Try localStorage fallback first
        const localSessions = loadSessionsFromLocalStorage();
        
        if (!state.history.initialized) {
            state.history.initialized = true;
            
            if (localSessions && localSessions.length > 0) {
                // Use cached sessions
                state.history.sessions = localSessions;
                renderSessionList();
                showToast('History loaded from cache', 'info', 3000);
                
                // Try to load last session from cache
                const lastSession = localSessions[0];
                state.history.activeSessionId = lastSession.id;
                const cached = state.history.messagesBySession[lastSession.id];
                if (cached) {
                    state.messages = [...cached];
                    renderAllMessages();
                }
            } else {
                // No cache, create temporary in-memory session
                createInMemorySession();
                showToast('History unavailable - using temporary session', 'warning', 5000);
            }
            
            // Show degraded state in sidebar
            showHistoryUnavailableBanner();
        }
    }

    /**
     * Create a temporary in-memory session (no backend)
     */
    function createInMemorySession() {
        const tempSession = {
            id: 'temp_' + Date.now(),
            title: 'Temporary Chat',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            pinned: false,
            archived: false,
            messageCount: 0,
            preview: '',
            isTemporary: true
        };
        
        state.history.sessions = [tempSession];
        state.history.activeSessionId = tempSession.id;
        state.messages = [];
        
        elements.messageList.innerHTML = '';
        updateEmptyState();
        showSuggestions();
        renderSessionList();
    }

    /**
     * Show "History unavailable" banner in sidebar
     */
    function showHistoryUnavailableBanner() {
        if (elements.historyUnavailableBanner) {
            elements.historyUnavailableBanner.classList.add('visible');
        }
    }

    /**
     * Remove unavailable banner
     */
    function hideHistoryUnavailableBanner() {
        if (elements.historyUnavailableBanner) {
            elements.historyUnavailableBanner.classList.remove('visible');
        }
    }

    /**
     * Retry connecting to history backend
     */
    async function retryHistoryConnection() {
        // Disable retry button during attempt
        if (elements.historyRetryBtn) {
            elements.historyRetryBtn.classList.add('retrying');
            elements.historyRetryBtn.disabled = true;
        }
        
        showToast('Reconnecting to history...', 'info', 2000);
        try {
            const result = await HistoryClient.list({ limit: 50 });
            state.history.sessions = result.sessions || [];
            state.history.available = true;
            hideHistoryUnavailableBanner();
            renderSessionList();
            showToast('History reconnected', 'success', 2000);
            
            // If using temp session with messages, offer to save
            if (state.history.activeSessionId?.startsWith('temp_') && state.messages.length > 0) {
                await migrateTemporarySession();
            }
        } catch (error) {
            showToast('Still unavailable', 'error', 2000);
        } finally {
            // Re-enable retry button
            if (elements.historyRetryBtn) {
                elements.historyRetryBtn.classList.remove('retrying');
                elements.historyRetryBtn.disabled = false;
            }
        }
    }

    /**
     * Migrate temporary session to persistent storage
     */
    async function migrateTemporarySession() {
        try {
            const result = await HistoryClient.create('Recovered Chat');
            const newSession = result.session;
            
            // Append existing messages
            if (state.messages.length > 0) {
                const msgs = state.messages.map(m => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    ts: m.ts
                }));
                await HistoryClient.append(newSession.id, msgs);
            }
            
            // Switch to new session
            state.history.sessions.unshift(newSession);
            state.history.activeSessionId = newSession.id;
            state.history.messagesBySession[newSession.id] = [...state.messages];
            
            // Remove temp session
            state.history.sessions = state.history.sessions.filter(s => !s.isTemporary);
            
            renderSessionList();
            showToast('Session saved to history', 'success', 2000);
        } catch (error) {
            console.error('Failed to migrate temp session:', error);
        }
    }

    /**
     * Fallback: Load sessions from localStorage
     * @returns {Array|null} Sessions array or null
     */
    function loadSessionsFromLocalStorage() {
        try {
            const stored = localStorage.getItem('copilot_sessions');
            if (stored) {
                const sessions = JSON.parse(stored);
                // Also try to load cached messages
                const cachedMessages = localStorage.getItem('copilot_messages_cache');
                if (cachedMessages) {
                    state.history.messagesBySession = JSON.parse(cachedMessages);
                }
                return sessions;
            }
        } catch (e) {
            console.warn('Failed to load sessions from localStorage:', e);
        }
        return null;
    }

    /**
     * Save sessions to localStorage as fallback
     */
    function saveSessionsToLocalStorage() {
        try {
            localStorage.setItem('copilot_sessions', JSON.stringify(state.history.sessions));
            // Also cache messages for offline resilience
            if (Object.keys(state.history.messagesBySession).length > 0) {
                localStorage.setItem('copilot_messages_cache', JSON.stringify(state.history.messagesBySession));
            }
        } catch (e) {
            console.warn('Failed to save sessions to localStorage:', e);
        }
    }

    /**
     * Create a new chat session
     */
    async function createNewSession() {
        // Save current session in background (don't await)
        if (state.history.currentSessionId && state.messages.length > 0) {
            saveCurrentSession().catch(err => console.error('Failed to save session:', err));
        }
        
        try {
            const result = await sendHistoryAction('history_create', {
                title: 'New Chat'
            });
            
            const session = result.session;
            
            // De-dup: Check if session already exists (shouldn't happen, but defensive)
            const existingIndex = state.history.sessions.findIndex(s => s.id === session.id);
            if (existingIndex >= 0) {
                console.warn('[History] Session already exists, updating:', session.id);
                state.history.sessions[existingIndex] = session;
            } else {
                // Add new session at the top
                state.history.sessions.unshift(session);
            }
            
            state.history.currentSessionId = session.id;
            
            // Clear current messages
            state.messages = [];
            elements.messageList.innerHTML = '';
            updateEmptyState();
            showSuggestions();
            
            renderSessionList();
            saveSessionsToLocalStorage();
            
            return session;
        } catch (error) {
            console.error('Failed to create session:', error);
            // Fallback: create local session
            return createLocalSession();
        }
    }

    /**
     * Create a local session (fallback when backend unavailable)
     */
    function createLocalSession() {
        const session = {
            id: 'local_' + Date.now(),
            title: 'New Chat',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            pinned: false,
            archived: false,
            messageCount: 0,
            preview: ''
        };
        
        state.history.sessions.unshift(session);
        state.history.currentSessionId = session.id;
        state.messages = [];
        elements.messageList.innerHTML = '';
        updateEmptyState();
        showSuggestions();
        
        renderSessionList();
        saveSessionsToLocalStorage();
        
        return session;
    }

    /**
     * Load a specific session
     * Uses messagesBySession cache when available
     */
    async function loadSession(sessionId) {
        if (sessionId === state.history.activeSessionId) return;
        
        // Save current session messages to cache before switching (don't await)
        if (state.history.activeSessionId && state.messages.length > 0) {
            state.history.messagesBySession[state.history.activeSessionId] = [...state.messages];
            // Fire-and-forget save
            saveCurrentSession().catch(err => console.error('Failed to save session:', err));
        }
        
        // Check cache first
        const cached = state.history.messagesBySession[sessionId];
        if (cached) {
            state.history.activeSessionId = sessionId;
            state.messages = [...cached];
            renderAllMessages();
            updateEmptyState();
            cached.length > 0 ? hideSuggestions() : showSuggestions();
            renderSessionList();
            return;
        }
        
        // Load from backend
        try {
            const result = await sendHistoryAction('history_load', { sessionId });
            
            state.history.activeSessionId = sessionId;
            state.messages = (result.messages || []).map(m => ({
                id: m.id,
                role: m.role,
                content: m.content,
                ts: m.timestamp || m.ts,
                status: m.status || 'complete'
            }));
            
            // Cache loaded messages
            state.history.messagesBySession[sessionId] = [...state.messages];
            
            renderAllMessages();
            updateEmptyState();
            state.messages.length > 0 ? hideSuggestions() : showSuggestions();
            renderSessionList();
            saveSessionsToLocalStorage();
        } catch (error) {
            console.error('Failed to load session:', sessionId, error);
            
            // If session not found, check if we have cached messages locally
            if (error.message && error.message.includes('not found')) {
                const cached = state.history.messagesBySession[sessionId];
                
                if (cached && cached.length > 0) {
                    // Use cached messages
                    state.history.activeSessionId = sessionId;
                    state.messages = [...cached];
                    renderAllMessages();
                    updateEmptyState();
                    hideSuggestions();
                    renderSessionList();
                    saveSessionsToLocalStorage();
                    showToast('Loaded from local cache', 'info');
                } else {
                    // No cached messages - load as empty but DON'T write empty to cache
                    // This way if messages are added later, they'll be preserved
                    state.history.activeSessionId = sessionId;
                    state.messages = [];
                    
                    renderAllMessages();
                    updateEmptyState();
                    showSuggestions();
                    renderSessionList();
                    showToast('Chat is empty', 'info');
                }
            } else {
                showToast(`Failed to load chat: ${error.message || error}`, 'error');
            }
        }
    }

    /**
     * Save the current session
     */
    async function saveCurrentSession() {
        if (!state.history.currentSessionId || state.messages.length === 0) return;
        
        try {
            await sendHistoryAction('history_save', {
                sessionId: state.history.currentSessionId,
                messages: state.messages.map(m => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    timestamp: m.ts,
                    status: m.status
                }))
            });
            
            // Update local session metadata
            const session = state.history.sessions.find(s => s.id === state.history.currentSessionId);
            if (session) {
                session.messageCount = state.messages.length;
                session.updatedAt = new Date().toISOString();
                if (state.messages.length > 0) {
                    const lastMsg = state.messages[state.messages.length - 1];
                    session.preview = lastMsg.content.slice(0, 100);
                }
            }
            
            saveSessionsToLocalStorage();
        } catch (error) {
            console.error('Failed to save session:', error);
            // Save to localStorage as fallback
            saveToLocalStorage();
        }
    }

    /**
     * Delete a session - authoritative, non-reversible flow
     * Immediately removes from UI and localStorage (source of truth)
     * Backend sync is fire-and-forget (doesn't block or rollback)
     */
    async function deleteSession(sessionId) {
        console.log('[History] Deleting session:', sessionId);
        
        // Add to pendingDeletes FIRST (authoritative filter)
        state.history.pendingDeletes.add(sessionId);
        
        // Remove from in-memory sessions list immediately
        state.history.sessions = state.history.sessions.filter(s => s.id !== sessionId);
        delete state.history.messagesBySession[sessionId];
        
        // If deleted the active session, clear it and switch to another
        let needsNewSession = false;
        if (state.history.activeSessionId === sessionId) {
            state.history.lastActiveSessionId = state.history.activeSessionId;
            state.history.activeSessionId = null;
            needsNewSession = true;
        }
        
        // Select/create a different session BEFORE rendering
        if (needsNewSession) {
            if (state.history.sessions.length > 0) {
                // Load first available session
                await loadSession(state.history.sessions[0].id);
            } else {
                // Create new session
                await createNewSession();
            }
        }
        
        renderSessionList();
        saveSessionsToLocalStorage();
        
        // Clean up localStorage immediately (authoritative)
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const data = JSON.parse(stored);
                if (data.sessions) {
                    data.sessions = data.sessions.filter(s => s.id !== sessionId);
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
                }
            }
        } catch (e) {
            console.warn('[History] Failed to clean localStorage:', e);
        }
        
        // Remove from pendingDeletes after local deletion is complete
        state.history.pendingDeletes.delete(sessionId);
        
        showToast('Chat deleted', 'success', 2000);
        
        // Fire-and-forget backend sync (don't wait or rollback)
        const requestId = generateRequestId();
        sendHistoryActionWithId(requestId, 'history_delete', { sessionId })
            .then(() => {
                console.log('[History] Backend delete synced successfully');
            })
            .catch(error => {
                console.warn('[History] Backend delete sync failed (local delete still applied):', error);
                // Don't rollback - localStorage is source of truth
            });
    }

    /**
     * Rename a session with optimistic UI
     */
    async function renameSession(sessionId, newTitle) {
        const session = state.history.sessions.find(s => s.id === sessionId);
        if (!session) return;
        
        // Snapshot for rollback
        const snapshot = { sessionId, title: session.title };
        
        // Optimistic: update immediately
        session.title = newTitle;
        session.updatedAt = new Date().toISOString();
        renderSessionList();
        saveSessionsToLocalStorage();
        showToast('Chat renamed', 'success', 2000);
        
        // Send to backend with rollback on failure
        const requestId = generateRequestId();
        state.history.optimisticOps.set(requestId, { type: 'rename', snapshot });
        
        try {
            await sendHistoryActionWithId(requestId, 'history_rename', { sessionId, title: newTitle });
            clearOptimisticOp(requestId);
        } catch (error) {
            // Rollback handled by handleHistoryError
            console.error('Failed to rename session:', error);
        }
    }

    /**
     * Pin/unpin a session with optimistic UI
     */
    async function pinSession(sessionId, pinned) {
        const session = state.history.sessions.find(s => s.id === sessionId);
        if (!session) return;
        
        // Snapshot for rollback
        const snapshot = { sessionId, pinned: session.pinned };
        
        // Optimistic: update immediately
        session.pinned = pinned;
        sortSessions();
        renderSessionList();
        saveSessionsToLocalStorage();
        
        // Send to backend with rollback on failure
        const requestId = generateRequestId();
        state.history.optimisticOps.set(requestId, { type: 'pin', snapshot });
        
        try {
            await sendHistoryActionWithId(requestId, 'history_pin', { sessionId, pinned });
            clearOptimisticOp(requestId);
        } catch (error) {
            // Rollback handled by handleHistoryError
            console.error('Failed to pin session:', error);
        }
    }

    /**
     * Search sessions with enhanced result info
     * @param {string} query - Search query
     * @param {object} options - Search options
     */
    async function searchSessions(query, options = {}) {
        state.history.searchQuery = query;
        
        if (!query) {
            loadSessions();
            return;
        }
        
        try {
            const result = await sendHistoryAction('history_search', {
                query,
                searchContent: options.searchContent !== false, // Default true
                limit: options.limit || 20
            });
            
            // Result should include sessions with matchType, snippet, matchCount
            state.history.sessions = result.sessions || [];
            renderSessionList();
        } catch (error) {
            console.error('Search failed:', error);
            // Fallback: filter locally (basic search, no snippets)
            const queryLower = query.toLowerCase();
            const filtered = state.history.sessions
                .filter(s => 
                    s.title.toLowerCase().includes(queryLower) ||
                    (s.preview && s.preview.toLowerCase().includes(queryLower))
                )
                .map(s => ({
                    ...s,
                    matchType: s.title.toLowerCase().includes(queryLower) ? 'title' : 'content',
                    matchCount: 1
                }));
            renderSessionList(filtered);
        }
    }

    /**
     * Format date for display
     */
    function formatSessionDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (days === 0) return 'Today';
        if (days === 1) return 'Yesterday';
        if (days < 7) return `${days} days ago`;
        if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
        return date.toLocaleDateString();
    }

    /**
     * Group sessions by date
     */
    function groupSessionsByDate(sessions) {
        const groups = {};
        
        sessions.forEach(session => {
            const label = formatSessionDate(session.updatedAt);
            if (!groups[label]) {
                groups[label] = [];
            }
            groups[label].push(session);
        });
        
        return groups;
    }

    /**
     * Render the session list
     */
    function renderSessionList(sessionsToRender = null) {
        const sessions = sessionsToRender || state.history.sessions;
        const isSearching = Boolean(state.history.searchQuery);
        
        if (sessions.length === 0) {
            elements.sessionEmpty.classList.remove('hidden');
            elements.sessionList.innerHTML = '';
            
            // Customize empty message for search
            const emptyText = elements.sessionEmpty.querySelector('.session-empty-text');
            const emptyIcon = elements.sessionEmpty.querySelector('.session-empty-icon');
            
            if (isSearching) {
                if (emptyText) emptyText.textContent = `No chats found for "${state.history.searchQuery}"`;
                if (emptyIcon) emptyIcon.textContent = '🔍';
            } else {
                if (emptyText) emptyText.textContent = 'No chat history yet';
                if (emptyIcon) emptyIcon.textContent = '💬';
            }
            elements.sessionList.appendChild(elements.sessionEmpty);
            return;
        }
        
        elements.sessionEmpty.classList.add('hidden');
        
        // Group by date (skip grouping during search)
        let html = '';
        
        if (isSearching) {
            // Flat list for search results with match info
            html += '<div class="session-group"><div class="session-group-header">Search Results</div>';
            
            for (const session of sessions) {
                html += renderSessionItem(session, isSearching);
            }
            
            html += '</div>';
        } else {
            // Group by date
            const groups = groupSessionsByDate(sessions);
            
            for (const [label, groupSessions] of Object.entries(groups)) {
                html += `<div class="session-group">
                    <div class="session-group-header">${label}</div>`;
                
                for (const session of groupSessions) {
                    html += renderSessionItem(session, false);
                }
                
                html += '</div>';
            }
        }
        
        elements.sessionList.innerHTML = html;
    }

    /**
     * Render a single session item
     */
    function renderSessionItem(session, isSearchResult) {
        const isActive = session.id === state.history.currentSessionId;
        const pinnedIcon = session.pinned ? '📌' : '💬';
        
        // Build preview text (use snippet for search results)
        let previewText = '';
        if (isSearchResult && session.snippet) {
            previewText = session.snippet;
        } else if (session.preview) {
            previewText = session.preview;
        }
        
        // Build match indicator for search results
        let matchBadge = '';
        if (isSearchResult && session.matchType) {
            const matchLabel = session.matchType === 'title' ? 'Title' :
                              session.matchType === 'content' ? 'Content' : 'Both';
            const matchCount = session.matchCount || 1;
            matchBadge = `<span class="session-match-badge" title="${matchCount} match(es)">${matchLabel}</span>`;
        }
        
        return `
        <div class="session-item ${isActive ? 'active' : ''} ${isSearchResult ? 'search-result' : ''}" data-session-id="${session.id}">
            <span class="session-icon ${session.pinned ? 'pinned' : ''}">${pinnedIcon}</span>
            <div class="session-info">
                <div class="session-title">${escapeHtml(session.title)}${matchBadge}</div>
                <div class="session-preview">${escapeHtml(previewText)}</div>
            </div>
            <div class="session-actions">
                <button class="session-action-btn pin-btn" data-action="pin" data-session-id="${session.id}" title="${session.pinned ? 'Unpin' : 'Pin'}">
                    <svg viewBox="0 0 24 24" width="14" height="14">
                        <path fill="currentColor" d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>
                    </svg>
                </button>
                <button class="session-action-btn rename-btn" data-action="rename" data-session-id="${session.id}" title="Rename">
                    <svg viewBox="0 0 24 24" width="14" height="14">
                        <path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                    </svg>
                </button>
                <button class="session-action-btn delete-btn" data-action="delete" data-session-id="${session.id}" title="Delete">
                    <svg viewBox="0 0 24 24" width="14" height="14">
                        <path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                    </svg>
                </button>
            </div>
        </div>`;
    }

    /**
     * Escape HTML for safe rendering
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Toggle sidebar visibility
     */
    function toggleSidebar(open = null) {
        const shouldOpen = open !== null ? open : state.history.sidebarOpen;
        state.history.sidebarOpen = !shouldOpen;
        
        if (state.history.sidebarOpen) {
            elements.historySidebar.classList.remove('collapsed');
            elements.sidebarOpenBtn.classList.add('hidden');
        } else {
            elements.historySidebar.classList.add('collapsed');
            elements.sidebarOpenBtn.classList.remove('hidden');
        }
        
        // Save state
        try {
            localStorage.setItem(SIDEBAR_KEY, JSON.stringify({ open: state.history.sidebarOpen }));
        } catch (e) {}
    }

    /**
     * Load sidebar state
     */
    function loadSidebarState() {
        try {
            const stored = localStorage.getItem(SIDEBAR_KEY);
            if (stored) {
                const { open } = JSON.parse(stored);
                state.history.sidebarOpen = open;
                toggleSidebar(!open); // Toggle to apply
            }
        } catch (e) {}
    }

    /**
     * Open rename modal
     */
    function openRenameModal(sessionId) {
        const session = state.history.sessions.find(s => s.id === sessionId);
        if (!session) return;
        
        state.history.renameSessionId = sessionId;
        elements.renameInput.value = session.title;
        elements.renameModal.classList.remove('hidden');
        elements.renameInput.focus();
        elements.renameInput.select();
    }

    /**
     * Close rename modal
     */
    function closeRenameModal() {
        state.history.renameSessionId = null;
        elements.renameModal.classList.add('hidden');
    }

    /**
     * Open delete modal
     */
    function openDeleteModal(sessionId) {
        state.history.deleteSessionId = sessionId;
        elements.deleteModal.classList.remove('hidden');
    }

    /**
     * Close delete modal
     */
    function closeDeleteModal() {
        state.history.deleteSessionId = null;
        elements.deleteModal.classList.add('hidden');
    }

    // ============================================
    // Event Listener Setup (called once in DOMContentLoaded)
    // ============================================
    
    function setupEventListeners() {
        console.log('[History] Setting up event listeners');
        
        // Sidebar toggle
        elements.sidebarToggle?.addEventListener('click', () => toggleSidebar(true));
        elements.sidebarOpenBtn?.addEventListener('click', () => toggleSidebar(false));

        // New chat button
        elements.newChatBtn?.addEventListener('click', createNewSession);

        // History retry button
        elements.historyRetryBtn?.addEventListener('click', retryHistoryConnection);

        // Session list click (delegation)
        elements.sessionList?.addEventListener('click', (e) => {
            const actionBtn = e.target.closest('.session-action-btn');
            if (actionBtn) {
                e.stopPropagation();
                const action = actionBtn.dataset.action;
                const sessionId = actionBtn.dataset.sessionId;
                
                switch (action) {
                    case 'pin':
                        const session = state.history.sessions.find(s => s.id === sessionId);
                        if (session) pinSession(sessionId, !session.pinned);
                        break;
                    case 'rename':
                        openRenameModal(sessionId);
                        break;
                    case 'delete':
                        openDeleteModal(sessionId);
                        break;
                }
                return;
            }
            
            const sessionItem = e.target.closest('.session-item');
            if (sessionItem) {
                const sessionId = sessionItem.dataset.sessionId;
                loadSession(sessionId);
            }
        });

        // Search input
        let searchDebounce = null;
        elements.historySearchInput?.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        // Show/hide clear button
        if (query) {
            elements.searchClearBtn?.classList.remove('hidden');
        } else {
            elements.searchClearBtn?.classList.add('hidden');
        }
        
        // Debounce search
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => {
            searchSessions(query);
        }, 300);
    });

    elements.searchClearBtn?.addEventListener('click', () => {
        elements.historySearchInput.value = '';
        elements.searchClearBtn.classList.add('hidden');
        searchSessions('');
    });

    // Show archived button
    elements.showArchivedBtn?.addEventListener('click', () => {
        state.history.showArchived = !state.history.showArchived;
        elements.showArchivedBtn.classList.toggle('active', state.history.showArchived);
        loadSessions();
    });

    // Rename modal
    elements.renameCloseBtn?.addEventListener('click', closeRenameModal);
    elements.renameCancelBtn?.addEventListener('click', closeRenameModal);
    elements.renameSaveBtn?.addEventListener('click', () => {
        const newTitle = elements.renameInput.value.trim();
        if (newTitle && state.history.renameSessionId) {
            renameSession(state.history.renameSessionId, newTitle);
            closeRenameModal();
        }
    });
    elements.renameModal?.addEventListener('click', (e) => {
        if (e.target === elements.renameModal) closeRenameModal();
    });
    elements.renameInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            elements.renameSaveBtn.click();
        } else if (e.key === 'Escape') {
            closeRenameModal();
        }
    });

    // Delete modal
    elements.deleteCloseBtn?.addEventListener('click', closeDeleteModal);
    elements.deleteCancelBtn?.addEventListener('click', closeDeleteModal);
    elements.deleteConfirmBtn?.addEventListener('click', () => {
        if (state.history.deleteSessionId) {
            deleteSession(state.history.deleteSessionId);
            closeDeleteModal();
        }
    });
    elements.deleteModal?.addEventListener('click', (e) => {
        if (e.target === elements.deleteModal) closeDeleteModal();
    });

    // Auto-save on message add (hook into existing functions)
    const originalAddUserMessage = addUserMessage;
    addUserMessage = function(text) {
        // Create session if needed
        if (!state.history.currentSessionId && state.history.sessions.length === 0) {
            createLocalSession();
        }
        
        const result = originalAddUserMessage(text);
        
        // Debounced save
        clearTimeout(window._autoSaveTimeout);
        window._autoSaveTimeout = setTimeout(() => {
            saveCurrentSession();
        }, 2000);
        
        return result;
    };

    const originalAddAssistantMessage = addAssistantMessage;
    addAssistantMessage = function(text, status) {
        const result = originalAddAssistantMessage(text, status);
        
        // Save after assistant message
        if (status === 'complete') {
            clearTimeout(window._autoSaveTimeout);
            window._autoSaveTimeout = setTimeout(() => {
                saveCurrentSession();
            }, 1000);
        }
        
        return result;
    };

    } // End of setupEventListeners function

    // ============================================
    // Initialization
    // ============================================

    document.addEventListener('DOMContentLoaded', () => {
        console.log('[History] Electrify Copilot v1.0.0 Initializing');
        console.log('[History] Sidebar element:', elements.historySidebar);
        console.log('[History] Sidebar classList before init:', elements.historySidebar?.className);
        
        // FORCE sidebar visible (ignore any stored state for now)
        if (elements.historySidebar) {
            elements.historySidebar.classList.remove('collapsed');
            elements.historySidebar.style.display = 'flex';
            elements.historySidebar.style.width = '200px';
            elements.historySidebar.style.minWidth = '200px';
            console.log('[History] FORCED sidebar visible');
        }
        if (elements.sidebarOpenBtn) {
            elements.sidebarOpenBtn.classList.add('hidden');
        }
        
        // Set up event listeners ONCE
        setupEventListeners();
        
        // Load settings first
        loadSettings();
        
        // Skip loadSidebarState to prevent auto-collapse
        // loadSidebarState();
        
        console.log('[History] Sidebar classList after init:', elements.historySidebar?.className);
        console.log('[History] Sidebar style.display:', elements.historySidebar?.style.display);
        
        // Load chat sessions
        loadSessions();
        
        // Load persisted messages
        if (loadFromLocalStorage() && state.messages.length > 0) {
            renderAllMessages();
            hideSuggestions();
        }
        
        // Set initial empty state visibility
        updateEmptyState();
        
        sendToFusion('paletteReady', { version: '1.0.0' });

        // Enable vertical mouse wheel to scroll the context chips horizontally
        // This makes it easier to navigate the context area with a regular mouse wheel
        try {
            const chips = elements.contextChips;
            if (chips) {
                chips.addEventListener('wheel', (ev) => {
                    // If there's no vertical scroll delta, let default behavior happen
                    const deltaY = ev.deltaY || 0;
                    const deltaX = ev.deltaX || 0;

                    // If user is already scrolling horizontally (deltaX larger), don't interfere
                    if (Math.abs(deltaX) > Math.abs(deltaY)) return;

                    // Prevent vertical page scroll and translate to horizontal scroll
                    if (deltaY !== 0) {
                        ev.preventDefault();
                        // Slightly amplify for a comfortable feel
                        chips.scrollLeft += deltaY;
                    }
                }, { passive: false });
            }
        } catch (e) {
            console.warn('Failed to attach wheel-to-scroll handler for context chips', e);
        }

        // Initialize the message context menu (for copy response)
        initMessageContextMenu();
    });

    // ============================================
    // Message Context Menu (right-click to copy)
    // ============================================
    let _ctxMenu = null;
    let _ctxCurrentMessage = null;

    function initMessageContextMenu() {
        if (_ctxMenu) return; // already initialized
        _ctxMenu = document.createElement('div');
        _ctxMenu.className = 'context-menu hidden';
        _ctxMenu.innerHTML = '<button type="button" class="ctx-copy-btn">📋 Copy response</button>';
        document.body.appendChild(_ctxMenu);

        const copyBtn = _ctxMenu.querySelector('.ctx-copy-btn');
        copyBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            if (!_ctxCurrentMessage) { hideMessageContextMenu(); return; }
            const textEl = _ctxCurrentMessage.querySelector('.message-text');
            const text = textEl ? textEl.innerText : '';
            const success = doCopy(text);
            hideMessageContextMenu();
            if (success) {
                showToast('Response copied to clipboard');
            } else {
                showToast('Failed to copy', 'error');
            }
        });

        document.addEventListener('click', () => hideMessageContextMenu());
        document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') hideMessageContextMenu(); });
    }

    function openMessageContextMenu(x, y, messageEl) {
        if (!_ctxMenu) initMessageContextMenu();
        _ctxCurrentMessage = messageEl;
        // Show menu first (hidden) so offsetWidth/Height are available
        _ctxMenu.style.visibility = 'hidden';
        _ctxMenu.classList.remove('hidden');
        const pad = 8;
        const left = Math.max(pad, Math.min(x, window.innerWidth - _ctxMenu.offsetWidth - pad));
        const top = Math.max(pad, Math.min(y, window.innerHeight - _ctxMenu.offsetHeight - pad));
        _ctxMenu.style.left = left + 'px';
        _ctxMenu.style.top = top + 'px';
        _ctxMenu.style.visibility = 'visible';
    }

    function hideMessageContextMenu() {
        if (_ctxMenu) _ctxMenu.classList.add('hidden');
        _ctxCurrentMessage = null;
    }

    // ============================================
    // Expose Public API (for debugging/testing)
    // ============================================
    window.ElectrifyCopilot = {
        addUserMessage,
        addAssistantMessage,
        updateAssistantMessage,
        addErrorMessage,
        completeMessage,
        setTyping,
        showToast,
        hideToast,
        clearChat,
        getMessages,
        getState: () => ({ ...state }),
        // Prompt 11 additions
        clearAttachments,
        getAttachments: () => [...state.attachments],
        exportChat,
        getSettings: () => ({ ...state.settings }),
        // Chat History API (high-level)
        history: {
            createSession: createNewSession,
            loadSession,
            saveSession: saveCurrentSession,
            deleteSession,
            renameSession,
            pinSession,
            loadSessions,
            searchSessions,
            getSessions: () => [...state.history.sessions],
            getCurrentSessionId: () => state.history.currentSessionId,
            toggleSidebar,
            retry: retryHistoryConnection,
            isAvailable: () => state.history.available
        },
        // HistoryClient (low-level bridge API)
        HistoryClient,
        // Debug panel access
        debug: {
            enable: () => { debug.enabled = true; },
            disable: () => { debug.enabled = false; },
            getLastOutbound: () => debug.lastOutbound,
            getLastInbound: () => debug.lastInbound,
            getLogs: () => ({ outbound: debug.lastOutbound, inbound: debug.lastInbound })
        }
    };

})();
