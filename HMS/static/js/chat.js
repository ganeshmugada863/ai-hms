// chat.js - Handles patient interactions with the AI assistant

document.addEventListener('DOMContentLoaded', function () {
    // DOM Elements
    const chatInputForm = document.getElementById('chatInputForm');
    const userInputField = document.getElementById('userInputField');
    const sendBtn = document.getElementById('sendBtn');
    const messagesContainer = document.getElementById('messagesContainer');
    const chatViewport = document.getElementById('chatViewport');
    const langSelect = document.getElementById('langSelect');
    const newChatBtn = document.getElementById('newChatBtn');
    const sessionsList = document.getElementById('sessionsList');
    
    const activeSessionTitle = document.getElementById('activeSessionTitle');
    const activeSessionMeta = document.getElementById('activeSessionMeta');
    
    // Sidebar indicators
    const symptomChips = document.getElementById('symptomChips');
    const riskBar = document.getElementById('riskBar');
    const riskLabel = document.getElementById('riskLabel');
    const predictionResults = document.getElementById('predictionResults');
    const allergyAlerts = document.getElementById('allergyAlerts');
    const typingIndicator = document.getElementById('typingIndicator');

    // App state
    let activeSessionId = localStorage.getItem('ai_chat_session_id') || '';
    let languageCode = 'en'; // default English

    // Init
    loadSessionsList();
    if (activeSessionId) {
        loadSessionHistory(activeSessionId);
    } else {
        createNewChat();
    }

    // Event Listeners
    if (chatInputForm) {
        chatInputForm.addEventListener('submit', function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    if (userInputField) {
        userInputField.addEventListener('keypress', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    if (langSelect) {
        langSelect.addEventListener('change', function () {
            languageCode = this.value;
            updateUIPlaceholders();
        });
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', function () {
            createNewChat();
        });
    }

    // Start a new chat session
    function createNewChat() {
        activeSessionId = '';
        localStorage.removeItem('ai_chat_session_id');
        
        // Reset message container
        messagesContainer.innerHTML = '';
        appendBotMessage({
            content: "Hello! 👋 I am your **HMS AI Medical Appointment Assistant** 🏥\n\nI can help you:\n• Describe your symptoms\n• Find the right specialist doctor\n• Book appointments\n\nPlease describe your symptoms or health concern, and I will recommend the appropriate specialist for you."
        });

        if (activeSessionTitle) activeSessionTitle.textContent = "New Conversation";
        if (activeSessionMeta) activeSessionMeta.textContent = "Awaiting symptom entry...";
        
        // Reset panels
        resetAnalysisPanels();
        
        // Update active class in sidebar
        if (sessionsList) {
            document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
        }
    }

    // Update form placeholders depending on language
    function updateUIPlaceholders() {
        const placeholders = {
            'en': "Describe your symptoms or health concern...",
            'te': "మీ లక్షణాలు లేదా ఆరోగ్య సమస్యను వివరించండి...",
            'hi': "अपने लक्षणों या स्वास्थ्य संबंधी चिंता का वर्णन करें...",
            'ta': "உங்கள் அறிகுறிகள் அல்லது சுகாதார கவலையை ವಿವரிக்கவும்...",
            'kn': "ನಿಮ್ಮ ರೋಗಲಕ್ಷಣಗಳನ್ನು ಅಥವಾ ಆರೋಗ್ಯ ಕಾಳಜಿಯನ್ನು ವಿವರಿಸಿ...",
            'ml': "നിങ്ങളുടെ ലക്ഷണങ്ങളോ ആരോഗ്യ പ്രശ്നമോ വിവരിക്കുക..."
        };
        userInputField.placeholder = placeholders[languageCode] || placeholders['en'];
    }

    // Reset side analysis panel fields
    function resetAnalysisPanels() {
        if (symptomChips) symptomChips.innerHTML = '<p class="empty-placeholder">No symptoms extracted yet.</p>';
        if (riskBar) {
            riskBar.style.width = '0%';
            riskBar.className = 'risk-bar';
        }
        if (riskLabel) {
            riskLabel.textContent = 'None';
            riskLabel.className = 'risk-level-none';
        }
        if (predictionResults) predictionResults.innerHTML = '<p class="empty-placeholder">Awaiting input...</p>';
        if (allergyAlerts) allergyAlerts.innerHTML = '<p class="empty-placeholder">No active warnings.</p>';
    }

    // Load list of past sessions
    function loadSessionsList() {
        if (!sessionsList) return;
        fetch(sessionsApiUrl)
            .then(res => res.json())
            .then(data => {
                if (data.sessions && data.sessions.length > 0) {
                    sessionsList.innerHTML = '';
                    data.sessions.forEach(session => {
                        const div = document.createElement('div');
                        div.className = `session-item ${session.session_id === activeSessionId ? 'active' : ''}`;
                        div.dataset.id = session.session_id;
                        div.innerHTML = `
                            <div class="session-item-header">
                                <span>${session.started_at}</span>
                                <span class="risk-badge font-size-10">${session.risk_level.toUpperCase()}</span>
                            </div>
                            <div class="session-item-snippet">${session.snippet}</div>
                        `;
                        div.addEventListener('click', () => {
                            loadSessionHistory(session.session_id);
                        });
                        sessionsList.appendChild(div);
                    });
                } else {
                    sessionsList.innerHTML = '<p class="empty-placeholder" style="padding: 15px;">No previous sessions found.</p>';
                }
            })
            .catch(err => {
                console.error("Error loading chat sessions:", err);
                sessionsList.innerHTML = '<p class="empty-placeholder" style="color: var(--text-muted); padding: 15px;">Unable to fetch conversations.</p>';
            });
    }

    // Fetch message history for selected session
    function loadSessionHistory(sessionId) {
        activeSessionId = sessionId;
        localStorage.setItem('ai_chat_session_id', sessionId);
        
        // Highlight active session
        if (sessionsList) {
            document.querySelectorAll('.session-item').forEach(el => {
                el.classList.toggle('active', el.dataset.id === sessionId);
            });
        }

        // Set loading states
        messagesContainer.innerHTML = '<div class="empty-placeholder">Loading history...</div>';
        resetAnalysisPanels();

        fetch(`${historyApiUrl}?session_id=${sessionId}`)
            .then(res => {
                if (!res.ok) throw new Error("History load failed");
                return res.json();
            })
            .then(data => {
                messagesContainer.innerHTML = '';
                
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        if (msg.role === 'user') {
                            appendUserMessage(msg.content, msg.timestamp);
                        } else {
                            appendBotMessage(msg, msg.timestamp);
                        }
                    });
                }
                
                // Update header info
                if (activeSessionTitle) activeSessionTitle.textContent = `Session: ${sessionId.substring(0, 8)}...`;
                if (activeSessionMeta) activeSessionMeta.textContent = `Smart AI Consultation`;

                // Set language selector based on session language
                languageCode = data.language || 'en';
                if (langSelect) langSelect.value = languageCode;
                updateUIPlaceholders();

                // Update analysis sidebar with historical data if available
                updateAnalysisSidebar({
                    symptoms: data.extracted_symptoms || [],
                    risk_level: data.risk_level || 'none',
                    predictions: [], // historical details are not saved in session directly, but predictions are listed below
                    allergy_alerts: []
                });

                scrollToBottom();
            })
            .catch(err => {
                console.error("Error loading history:", err);
                messagesContainer.innerHTML = '<div class="empty-placeholder" style="color: #ef4444;">Failed to load conversation history.</div>';
            });
    }

    // Send a message wrapper
    function sendMessage() {
        const text = userInputField.value.trim();
        if (!text) return;
        userInputField.value = '';
        sendMessageText(text);
    }

    // Interactive message sender
    function sendMessageText(text, displayText = '') {
        userInputField.disabled = true;
        sendBtn.disabled = true;

        appendUserMessage(displayText || text);
        scrollToBottom();

        typingIndicator.classList.remove('hidden');
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
            if (!res.ok) throw new Error("Server error");
            return res.json();
        })
        .then(data => {
            typingIndicator.classList.add('hidden');
            userInputField.disabled = false;
            sendBtn.disabled = false;
            userInputField.focus();

            appendBotMessage({
                content: data.response
            });

            if (data.session_id && data.session_id !== activeSessionId) {
                activeSessionId = data.session_id;
                localStorage.setItem('ai_chat_session_id', activeSessionId);
                loadSessionsList();
            }

            if (activeSessionTitle) activeSessionTitle.textContent = `Session: ${activeSessionId.substring(0, 8)}...`;

            if (data.analysis) {
                updateAnalysisSidebar(data.analysis);
            }

            scrollToBottom();
        })
        .catch(err => {
            console.error("AJAX Error:", err);
            typingIndicator.classList.add('hidden');
            userInputField.disabled = false;
            sendBtn.disabled = false;

            appendBotMessage({
                content: "I'm sorry, I'm experiencing a temporary connection issue. Please try again in a moment. If you are experiencing a medical emergency, please call emergency services or visit the nearest hospital immediately."
            });
            scrollToBottom();
        });
    }

    // Intercept clicks on interactive buttons
    messagesContainer.addEventListener('click', function(e) {
        const btn = e.target.closest('.chat-btn');
        if (btn) {
            e.preventDefault();
            const val = btn.getAttribute('data-value');
            const display = btn.getAttribute('data-display') || val;
            
            // Disable actions in the same bubble
            btn.closest('.message-bubble').querySelectorAll('.chat-btn').forEach(b => {
                b.disabled = true;
            });
            
            sendMessageText(val, display);
        }
    });

    // Handle Appointment Form Booking Submissions
    window.submitBookingForm = function(form) {
        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });
        
        const submitBtn = form.querySelector('.submit-booking-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Booking...';
        }
        
        sendMessageText(JSON.stringify(data), `📅 Appointment Booked for ${data.name} on ${data.date} at ${data.time}`);
    };


    // Append user message bubble
    function appendUserMessage(content, timeStr = '') {
        const timestamp = timeStr || getCurrentTimeStr();
        const row = document.createElement('div');
        row.className = 'message-row user';
        row.innerHTML = `
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    <p>${escapeHTML(content)}</p>
                </div>
                <span class="message-timestamp">${timestamp}</span>
            </div>
        `;
        messagesContainer.appendChild(row);
    }

    // Append bot message bubble
    function appendBotMessage(msgObj, timeStr = '') {
        const timestamp = timeStr || getCurrentTimeStr();
        const row = document.createElement('div');
        row.className = 'message-row bot';
        
        let text = msgObj.content;
        if (msgObj.translated_content && languageCode !== 'en') {
            text = msgObj.translated_content;
        }

        if (text.includes('video-room-console') || text.includes('voice-only') || text.includes('doctor-chat-console')) {
            callStartTime = Date.now();
            cameraActive = false;
            micActive = true;
            screenShareActive = false;
        }

        // Format code / lists nicely in responses
        let formattedText = formatBotMarkdown(text);

        row.innerHTML = `
            <div class="bot-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    ${formattedText}
                </div>
                <span class="message-timestamp">${timestamp}</span>
            </div>
        `;
        messagesContainer.appendChild(row);

        // Voice speech out loud
        speakBotResponse(text);
    }

    // Update the Sidebar Panels based on AJAX analysis payload
    function updateAnalysisSidebar(analysis) {
        if (symptomChips) {
            if (analysis.symptoms && analysis.symptoms.length > 0) {
                symptomChips.innerHTML = '';
                analysis.symptoms.forEach(s => {
                    const name = s.symptom_name || s.name || s;
                    const chip = document.createElement('span');
                    chip.className = 'symptom-chip';
                    chip.textContent = name;
                    symptomChips.appendChild(chip);
                });
            } else {
                symptomChips.innerHTML = '<p class="empty-placeholder">No symptoms extracted yet.</p>';
            }
        }

        if (allergyAlerts) {
            if (analysis.allergy_alerts && analysis.allergy_alerts.length > 0) {
                allergyAlerts.innerHTML = '';
                analysis.allergy_alerts.forEach(alert => {
                    const item = document.createElement('div');
                    item.className = 'allergy-alert-item';
                    item.innerHTML = `
                        <i class="fas fa-exclamation-circle"></i>
                        <span>${escapeHTML(alert)}</span>
                    `;
                    allergyAlerts.appendChild(item);
                });
            } else {
                allergyAlerts.innerHTML = '<p class="empty-placeholder">No active warnings.</p>';
            }
        }
    }

    // Auto-scroll Viewport
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

    // Helper: Escape HTML string to avoid XSS
    function escapeHTML(str) {
        if (typeof str !== 'string') return str;
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Helper: Markdown parser for chat messages (supports embedded HTML elements)
    function formatBotMarkdown(text) {
        if (!text) return '';
        let hasComponents = text.includes('<div') || text.includes('<form');
        let formatted = text;
        formatted = formatted.replace(/\n/g, '<br>');
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/<br>\*\s(.*?)/g, '<br>• $1');
        formatted = formatted.replace(/<br>-\s(.*?)/g, '<br>• $1');
        if (hasComponents) {
            return formatted;
        }
        return `<p>${formatted}</p>`;
    }

    // Media Upload Listeners
    const mediaUploadBtn = document.getElementById('mediaUploadBtn');
    const mediaFileInput = document.getElementById('mediaFileInput');

    if (mediaUploadBtn && mediaFileInput) {
        mediaUploadBtn.addEventListener('click', () => mediaFileInput.click());
        mediaFileInput.addEventListener('change', uploadMediaFile);
    }

    function uploadMediaFile() {
        const file = mediaFileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', activeSessionId);
        formData.append('csrfmiddlewaretoken', csrfToken);

        userInputField.disabled = true;
        sendBtn.disabled = true;
        typingIndicator.classList.remove('hidden');

        fetch(uploadApiUrl, {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            typingIndicator.classList.add('hidden');
            userInputField.disabled = false;
            sendBtn.disabled = false;
            mediaFileInput.value = '';

            if (data.status === 'success') {
                loadSessionHistory(activeSessionId);
            } else {
                alert("Upload failed: " + (data.error || "Unknown error"));
            }
        })
        .catch(err => {
            console.error("Upload error:", err);
            typingIndicator.classList.add('hidden');
            userInputField.disabled = false;
            sendBtn.disabled = false;
            alert("Network error occurred during upload.");
        });
    }

    // Interactive Calling Controls Globals
    let callStartTime = null;
    let cameraActive = false;
    let micActive = true;
    let screenShareActive = false;

    window.triggerDirectUpload = function() {
        if (mediaFileInput) mediaFileInput.click();
    };

    window.toggleCameraControl = function(btn) {
        cameraActive = !cameraActive;
        const localVideo = document.getElementById('localVideoFeed');
        if (cameraActive) {
            btn.innerHTML = '<i class="fas fa-video"></i> Camera On';
            btn.classList.add('active');
            btn.classList.remove('inactive');
            if (localVideo) {
                navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => {
                    localVideo.srcObject = stream;
                    localVideo.style.display = 'block';
                    const placeholder = localVideo.nextElementSibling;
                    if (placeholder) placeholder.style.display = 'none';
                })
                .catch(err => {
                    console.warn("Camera permission denied: ", err);
                    cameraActive = false;
                    btn.innerHTML = '<i class="fas fa-video-slash"></i> Camera Off';
                    btn.classList.remove('active');
                });
            }
        } else {
            btn.innerHTML = '<i class="fas fa-video-slash"></i> Camera Off';
            btn.classList.remove('active');
            btn.classList.add('inactive');
            if (localVideo) {
                localVideo.style.display = 'none';
                if (localVideo.srcObject) {
                    localVideo.srcObject.getTracks().forEach(t => t.stop());
                    localVideo.srcObject = null;
                }
                const placeholder = localVideo.nextElementSibling;
                if (placeholder) placeholder.style.display = 'flex';
            }
        }
    };

    window.toggleMicControl = function(btn) {
        micActive = !micActive;
        if (micActive) {
            btn.innerHTML = '<i class="fas fa-microphone"></i> Mic On';
            btn.classList.add('active');
            btn.classList.remove('inactive');
        } else {
            btn.innerHTML = '<i class="fas fa-microphone-slash"></i> Mic Off';
            btn.classList.remove('active');
            btn.classList.add('inactive');
        }
    };

    window.toggleScreenShareControl = function(btn) {
        screenShareActive = !screenShareActive;
        if (screenShareActive) {
            btn.innerHTML = '<i class="fas fa-desktop"></i> Sharing Screen';
            btn.classList.add('active');
            if (navigator.mediaDevices.getDisplayMedia) {
                navigator.mediaDevices.getDisplayMedia({ video: true })
                .then(stream => {
                    alert("Screen share established successfully!");
                })
                .catch(err => {
                    console.warn(err);
                    screenShareActive = false;
                    btn.innerHTML = '<i class="fas fa-desktop"></i> Share Screen';
                    btn.classList.remove('active');
                });
            }
        } else {
            btn.innerHTML = '<i class="fas fa-desktop"></i> Share Screen';
            btn.classList.remove('active');
        }
    };

    window.endConsultationCall = function(btn, type) {
        const duration = callStartTime ? Math.floor((Date.now() - callStartTime) / 1000) : 0;
        
        const localVideo = document.getElementById('localVideoFeed');
        if (localVideo && localVideo.srcObject) {
            localVideo.srcObject.getTracks().forEach(t => t.stop());
            localVideo.srcObject = null;
        }
        
        fetch(logCallApiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                session_id: activeSessionId,
                duration_seconds: duration,
                call_type: type,
                camera_used: cameraActive,
                mic_used: micActive,
                screen_share_used: screenShareActive
            })
        })
        .then(res => res.json())
        .then(data => {
            sendMessageText(`Call completed with duration ${duration}s`, `📞 Session Ended`);
        })
        .catch(err => {
            console.error("Log call error:", err);
            sendMessageText(`Call completed`, `📞 Session Ended`);
        });
    };

    // Character Counter Logic
    const charCounter = document.getElementById('charCounter');
    if (userInputField && charCounter) {
        userInputField.addEventListener('input', function () {
            const len = this.value.length;
            charCounter.textContent = `${len} / 250`;
            if (len > 250) {
                charCounter.style.color = '#ef4444';
            } else {
                charCounter.style.color = '';
            }
        });
    }

    // Voice Speech to Text (Speech Recognition)
    const voiceInputBtn = document.getElementById('voiceInputBtn');
    const voiceStatusMsg = document.getElementById('voiceStatusMsg');
    let recognition = null;
    let isListening = false;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function () {
            isListening = true;
            if (voiceInputBtn) voiceInputBtn.style.color = '#ef4444';
            if (voiceStatusMsg) voiceStatusMsg.textContent = "Listening... Speak now";
        };

        recognition.onresult = function (event) {
            const resultText = event.results[0][0].transcript;
            userInputField.value = resultText;
            if (userInputField) {
                userInputField.dispatchEvent(new Event('input'));
            }
            if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice captured!";
        };

        recognition.onerror = function (event) {
            console.error("Speech recognition error:", event.error);
            if (voiceStatusMsg) voiceStatusMsg.textContent = "Error: " + event.error;
            stopListening();
        };

        recognition.onend = function () {
            stopListening();
        };
    } else {
        if (voiceInputBtn) {
            voiceInputBtn.title = "Voice recognition not supported in this browser";
            voiceInputBtn.style.opacity = '0.5';
        }
    }

    function startListening() {
        if (!recognition) return;
        const langMap = {
            'en': 'en-US',
            'te': 'te-IN',
            'hi': 'hi-IN',
            'ta': 'ta-IN',
            'kn': 'kn-IN',
            'ml': 'ml-IN'
        };
        recognition.lang = langMap[languageCode] || 'en-US';
        try {
            recognition.start();
        } catch (e) {
            console.error(e);
        }
    }

    function stopListening() {
        isListening = false;
        if (voiceInputBtn) voiceInputBtn.style.color = '';
        if (voiceStatusMsg) voiceStatusMsg.textContent = "Press mic to dictate symptoms";
        if (recognition) {
            try {
                recognition.stop();
            } catch (e) {}
        }
    }

    if (voiceInputBtn) {
        voiceInputBtn.addEventListener('click', function () {
            if (isListening) {
                stopListening();
            } else {
                startListening();
            }
        });
    }

    // Voice Output (Text to Speech)
    const voiceSpeakToggle = document.getElementById('voiceSpeakToggle');
    let speakEnabled = false;

    if (voiceSpeakToggle) {
        voiceSpeakToggle.addEventListener('click', function () {
            speakEnabled = !speakEnabled;
            if (speakEnabled) {
                this.innerHTML = '<i class="fas fa-volume-up" style="color: #2563EB;"></i>';
                this.title = "Mute Voice Output";
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice output enabled";
            } else {
                this.innerHTML = '<i class="fas fa-volume-mute"></i>';
                this.title = "Enable Voice Output";
                window.speechSynthesis.cancel();
                if (voiceStatusMsg) voiceStatusMsg.textContent = "Voice output muted";
            }
        });
    }

    function speakBotResponse(text) {
        if (!speakEnabled || !('speechSynthesis' in window)) return;
        
        window.speechSynthesis.cancel();
        
        // Remove HTML tags for clean speech
        const cleanText = text.replace(/<[^>]*>/g, '').trim();
        if (!cleanText) return;

        const utterance = new SpeechSynthesisUtterance(cleanText);
        const speechLangMap = {
            'en': 'en-US',
            'te': 'te-IN',
            'hi': 'hi-IN',
            'ta': 'ta-IN',
            'kn': 'kn-IN',
            'ml': 'ml-IN'
        };
        utterance.lang = speechLangMap[languageCode] || 'en-US';
        window.speechSynthesis.speak(utterance);
    }

    // Minimize / Close Button Event Listeners
    const minimizeChatBtn = document.getElementById('minimizeChatBtn');
    const closeChatBtn = document.getElementById('closeChatBtn');
    const chatWorkspace = document.querySelector('.chat-workspace');

    if (minimizeChatBtn) {
        minimizeChatBtn.addEventListener('click', function () {
            if (chatWorkspace) {
                chatWorkspace.classList.toggle('minimized');
            }
        });
    }

    if (closeChatBtn) {
        closeChatBtn.addEventListener('click', function () {
            window.location.href = '/patients/dashboard/';
        });
    }
});
