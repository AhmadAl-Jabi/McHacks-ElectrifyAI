// ============================================
// Electrify Copilot - Fusion 360 Palette App
// State Management + Rendering
// ============================================

(function () {
    'use strict';

    // ============================================
    // Constants
    // ============================================
    const STORAGE_KEY = 'copilot_chat_history';
    const SETTINGS_KEY = 'copilot_settings';
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
        autoScrollToggle: document.getElementById('autoScrollToggle')
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
            autoScroll: true
        }
    };

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
     * Add a user message to the chat
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
        renderMessage(message);
        hideSuggestions();
        updateEmptyState();
        scrollToBottom(true); // Force scroll on user message
        saveToLocalStorage();

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
        }
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
                roleLabel = 'You';
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
     * Copy text to clipboard and show feedback
     */
    async function copyToClipboard(text, button) {
        try {
            await navigator.clipboard.writeText(text);
            
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
        } catch (error) {
            console.error('Failed to copy:', error);
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
        elements.sendBtn.disabled = !canSend;
    }

    function autoResizeTextarea() {
        const input = elements.messageInput;
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 140) + 'px';
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
            // Check if running inside Fusion 360
            if (typeof adsk !== 'undefined' && adsk.fusionSendData) {
                // Production: Send to Fusion 360 host
                adsk.fusionSendData(action, JSON.stringify(payloadObj));
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
                console.log('[Mock] Unhandled action:', action);
        }
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
                const data = dataString ? JSON.parse(dataString) : {};
                console.log('[Handler] Received:', action, data);

                switch (action) {
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

    // ============================================
    // Event Listeners
    // ============================================

    elements.sendBtn.addEventListener('click', handleSendMessage);

    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
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
    // Initialization
    // ============================================

    document.addEventListener('DOMContentLoaded', () => {
        // Load settings first
        loadSettings();
        
        // Load persisted messages
        if (loadFromLocalStorage() && state.messages.length > 0) {
            renderAllMessages();
            hideSuggestions();
        }
        
        // Set initial empty state visibility
        updateEmptyState();
        
        sendToFusion('paletteReady', { version: '1.0.0' });
    });

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
        getSettings: () => ({ ...state.settings })
    };

})();
