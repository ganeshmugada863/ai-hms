// chat.js - Coordinates ChatGPT-style interactions for MediCore AI Assistant

document.addEventListener('DOMContentLoaded', () => {
    const chatInputForm = document.getElementById('chatInputForm');
    const userInputField = document.getElementById('userInputField');
    const sendBtn = document.getElementById('sendBtn');
    const messagesContainer = document.getElementById('messagesContainer');
    const chatViewport = document.getElementById('chatViewport');
    const welcomeContainer = document.getElementById('welcomeContainer');
    const newChatBtn = document.getElementById('newChatBtn');
    const sessionsList = document.getElementById('sessionsList');
    const voiceInputBtn = document.getElementById('voiceInputBtn');
    const voiceStatusMsg = document.getElementById('voiceStatusMsg');
    const charCounter = document.getElementById('charCounter');
    const voiceSpeakToggle = document.getElementById('voiceSpeakToggle');
    const typingIndicator = document.getElementById('typingIndicator');
    const mobileSuggestionsStack = document.getElementById('mobileSuggestionsStack');
    const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
    const chatSidebar = document.querySelector('.chat-gpt-sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const botTitleDropdownBtn = document.getElementById('botTitleDropdownBtn');
    const quickPromptsDropdownMenu = document.getElementById('quickPromptsDropdownMenu');

    // Toggle mobile sidebar drawer
    if (mobileSidebarToggle && chatSidebar && sidebarBackdrop) {
        mobileSidebarToggle.addEventListener('click', () => {
            chatSidebar.classList.add('active');
            sidebarBackdrop.classList.add('active');
        });
        sidebarBackdrop.addEventListener('click', () => {
            chatSidebar.classList.remove('active');
            sidebarBackdrop.classList.remove('active');
        });
    }

    // Toggle header quick actions dropdown
    if (botTitleDropdownBtn && quickPromptsDropdownMenu) {
        botTitleDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const visible = quickPromptsDropdownMenu.style.display === 'block';
            quickPromptsDropdownMenu.style.display = visible ? 'none' : 'block';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!botTitleDropdownBtn.contains(e.target) && !quickPromptsDropdownMenu.contains(e.target)) {
                quickPromptsDropdownMenu.style.display = 'none';
            }
        });
    }

    // Click handler for quick action queries in the dropdown
    document.querySelectorAll('.dropdown-item-query').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const query = item.getAttribute('data-query');
            if (quickPromptsDropdownMenu) quickPromptsDropdownMenu.style.display = 'none';
            sendMessageText(query);
        });
    });

    // Click handler for mobile suggestion stack cards
    document.querySelectorAll('.mobile-suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            sendMessageText(query);
        });
    });

    const currentRole = (typeof userRole !== 'undefined') ? userRole : 'patient';
    const storageKey = 'medi_ai_session_id_' + currentRole;
    let activeSessionId = localStorage.getItem(storageKey) || '';
    let voiceSpeakEnabled = false;
    let recognition = null;
    let isListening = false;

    // Load initial sessions
    loadSessionsList();
    if (activeSessionId) {
        loadSessionHistory(activeSessionId);
    }

    // New Chat button click
    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            activeSessionId = '';
            localStorage.removeItem(storageKey);
            messagesContainer.innerHTML = '';
            welcomeContainer.style.display = 'flex';
            if (mobileSuggestionsStack) mobileSuggestionsStack.style.display = 'flex';
            document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
        });
    }

    // Option pills clicks
    document.querySelectorAll('.option-pill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.getAttribute('data-query');
            sendMessageText(query);
        });
    });

    // Form submission
    if (chatInputForm) {
        chatInputForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = userInputField.value.trim();
            if (text) {
                sendMessageText(text);
                userInputField.value = '';
                if (charCounter) charCounter.textContent = '0 / 250';
            }
        });
    }

    // Input character counter
    if (userInputField && charCounter) {
        userInputField.addEventListener('input', () => {
            const len = userInputField.value.length;
            charCounter.textContent = `${len} / 250`;
            charCounter.style.color = len > 250 ? '#ef4444' : '';
        });
    }

    // Load sessions list in sidebar
    function loadSessionsList() {
        if (!sessionsList) return;
        fetch(sessionsApiUrl)
            .then(res => res.json())
            .then(data => {
                if (data.sessions && data.sessions.length > 0) {
                    sessionsList.innerHTML = '';
                    data.sessions.forEach(s => {
                        const item = document.createElement('div');
                        item.className = `session-item ${s.session_id === activeSessionId ? 'active' : ''}`;
                        item.dataset.id = s.session_id;
                        item.innerHTML = `
                            <i class="fas fa-comment"></i>
                            <span class="session-text">${escapeHTML(s.snippet)}</span>
                        `;
                        item.addEventListener('click', () => {
                            loadSessionHistory(s.session_id);
                        });
                        sessionsList.appendChild(item);
                    });
                }
            })
            .catch(err => console.error("Error loading chat sessions:", err));
    }

    // Fetch conversation history
    function loadSessionHistory(sessionId) {
        activeSessionId = sessionId;
        localStorage.setItem(storageKey, sessionId);
        
        // Highlight in sidebar
        document.querySelectorAll('.session-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === sessionId);
        });

        welcomeContainer.style.display = 'none';
        if (mobileSuggestionsStack) mobileSuggestionsStack.style.display = 'none';
        messagesContainer.innerHTML = '<div style="text-align: center; color: var(--chat-text-muted); font-size: 13.5px; padding: 20px;">Retrieving secure logs...</div>';

        fetch(`${historyApiUrl}?session_id=${sessionId}`)
            .then(res => res.json())
            .then(data => {
                messagesContainer.innerHTML = '';
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        appendMessageBubble(msg.role, msg.content, msg.timestamp);
                    });
                }
                scrollToBottom();
            })
            .catch(err => {
                console.error("Error loading history:", err);
                messagesContainer.innerHTML = '<div style="text-align: center; color: #ef4444; font-size: 13.5px; padding: 20px;">Failed to load conversation history.</div>';
            });
    }

    // Main send message coordinator
    function sendMessageText(text) {
        welcomeContainer.style.display = 'none';
        if (mobileSuggestionsStack) mobileSuggestionsStack.style.display = 'none';
        
        // Disable UI
        userInputField.disabled = true;
        sendBtn.disabled = true;

        // Append user bubble
        appendMessageBubble('user', text);
        scrollToBottom();

        // Show typing indicator
        typingIndicator.style.display = 'block';
        scrollToBottom();

        const payload = {
            message: text,
            session_id: activeSessionId
        };

        fetch(sendApiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (!res.ok) throw new Error("Database query failed");
            return res.json();
        })
        .then(data => {
            typingIndicator.style.display = 'none';
            userInputField.disabled = false;
            sendBtn.disabled = false;
            userInputField.focus();

            appendMessageBubble('bot', data.response);

            if (data.session_id && data.session_id !== activeSessionId) {
                activeSessionId = data.session_id;
                localStorage.setItem(storageKey, activeSessionId);
                loadSessionsList();
            }

            speakBotResponse(data.response);
            scrollToBottom();
        })
        .catch(err => {
            console.error("Assistant Error:", err);
            typingIndicator.style.display = 'none';
            userInputField.disabled = false;
            sendBtn.disabled = false;

            appendMessageBubble('bot', "<p style='color:#ef4444;'>I encountered an issue querying the database. Please verify your authentication state and retry.</p>");
            scrollToBottom();
        });
    }

    // Helper: Append a message bubble to log
    function appendMessageBubble(role, content, timeStr = '') {
        const timestamp = timeStr || getCurrentTimeStr();
        const row = document.createElement('div');
        row.className = `message-row ${role}`;
        
        const avatarIcon = role === 'bot' ? 'fa-robot' : 'fa-user';
        
        row.innerHTML = `
            ${role === 'bot' ? `<div class="message-avatar"><i class="fas ${avatarIcon}"></i></div>` : ''}
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    ${content}
                </div>
                <span class="message-timestamp">${timestamp}</span>
            </div>
            ${role === 'user' ? `<div class="message-avatar"><i class="fas ${avatarIcon}"></i></div>` : ''}
        `;
        messagesContainer.appendChild(row);

        // Bind quick book clicks dynamically
        row.querySelectorAll('.chat-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const val = btn.getAttribute('data-value');
                sendMessageText(val);
            });
        });
    }

    // Scroll chat viewport to bottom
    function scrollToBottom() {
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }

    // Helper: Current Time formatted
    function getCurrentTimeStr() {
        const now = new Date();
        let hours = now.getHours();
        let minutes = now.getMinutes();
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        minutes = minutes < 10 ? '0' + minutes : minutes;
        return `${hours}:${minutes} ${ampm}`;
    }

    // Helper: Escape HTML
    function escapeHTML(str) {
        if (typeof str !== 'string') return str;
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Speech to text integration (Mic)
    if (voiceInputBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        try {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onstart = () => {
                isListening = true;
                voiceInputBtn.style.color = '#ef4444';
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Listening... Speak clearly";
            };

            recognition.onresult = (event) => {
                const resultText = event.results[0][0].transcript;
                userInputField.value = resultText;
                if (charCounter) charCounter.textContent = `${resultText.length} / 250`;
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice input captured!";
            };

            recognition.onerror = (e) => {
                console.error(e);
                stopListening();
            };

            recognition.onend = () => {
                stopListening();
            };

            voiceInputBtn.addEventListener('click', () => {
                if (isListening) {
                    stopListening();
                } else {
                    recognition.start();
                }
            });
        } catch (e) {
            console.warn(e);
        }
    }

    function stopListening() {
        isListening = false;
        if (voiceInputBtn) voiceInputBtn.style.color = '';
        if (voiceStatusMsg) voiceStatusMsg.textContent = "Standard encrypted medical sandbox";
        if (recognition) {
            try { recognition.stop(); } catch (e) {}
        }
    }

    // Text to Speech integration
    if (voiceSpeakToggle) {
        voiceSpeakToggle.addEventListener('click', () => {
            voiceSpeakEnabled = !voiceSpeakEnabled;
            if (voiceSpeakEnabled) {
                voiceSpeakToggle.innerHTML = '<i class="fas fa-volume-up" style="color: var(--chat-accent);"></i>';
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice output active";
            } else {
                voiceSpeakToggle.innerHTML = '<i class="fas fa-volume-mute"></i>';
                window.speechSynthesis.cancel();
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice output disabled";
            }
        });
    }

    function speakBotResponse(text) {
        if (!text || !voiceSpeakEnabled || !('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        
        // Strip HTML tags for clean speech synthesis
        const cleanText = text.replace(/<[^>]*>/g, '').trim();
        if (!cleanText) return;

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = 'en-US';
        window.speechSynthesis.speak(utterance);
    }
});
