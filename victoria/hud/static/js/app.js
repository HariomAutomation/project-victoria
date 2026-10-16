/**
 * Victoria AI - Holographic HUD Frontend Orchestrator
 * Integrates 3D Neural Hologram, Audio Waveform, Telemetry, Chat Console & REA Control Deck.
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // DOM Elements
    // -------------------------------------------------------------
    // Telemetry Elements
    const activeModelVal = document.getElementById('activeModelVal');
    const toolsCountVal = document.getElementById('toolsCountVal');
    const voiceStatusVal = document.getElementById('voiceStatusVal');
    const cpuPercent = document.getElementById('cpuPercent');
    const cpuBar = document.getElementById('cpuBar');
    const ramPercent = document.getElementById('ramPercent');
    const ramBar = document.getElementById('ramBar');
    const diskPercent = document.getElementById('diskPercent');
    const diskBar = document.getElementById('diskBar');

    // Quick Actions
    const screenshotBtn = document.getElementById('screenshotBtn');
    const volDownBtn = document.getElementById('volDownBtn');
    const volUpBtn = document.getElementById('volUpBtn');
    const modelSelector = document.getElementById('modelSelector');

    // Chat Elements
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const micBtn = document.getElementById('micBtn');
    const sendBtn = document.getElementById('sendBtn');
    const ttsAudio = document.getElementById('ttsAudio');

    // REA Control Elements
    const reaForm = document.getElementById('reaForm');
    const reaTargetInput = document.getElementById('reaTargetInput');
    const reaTypeSelect = document.getElementById('reaTypeSelect');
    const runReaBtn = document.getElementById('runReaBtn');
    const reportsList = document.getElementById('reportsList');
    const blueprintCode = document.getElementById('blueprintCode');

    // Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const reportsTab = document.getElementById('reportsTab');
    const previewTab = document.getElementById('previewTab');

    let audioSourceConnected = false;

    // -------------------------------------------------------------
    // 1. Telemetry & Health Polling
    // -------------------------------------------------------------
    async function updateTelemetry() {
        try {
            const res = await fetch('/api/status');
            if (!res.ok) return;
            const data = await res.json();

            // Update top chips
            if (activeModelVal && data.active_model) {
                activeModelVal.textContent = data.active_model.toUpperCase();
            }
            if (toolsCountVal && data.tools_count !== undefined) {
                toolsCountVal.textContent = `${data.tools_count} LOADED`;
            }

            // Sync model selector if not actively focused
            if (modelSelector && document.activeElement !== modelSelector && data.active_model) {
                modelSelector.value = data.active_model;
            }

            // Update Hardware Gauges
            const t = data.telemetry;
            if (t) {
                if (cpuPercent && cpuBar) {
                    const cpu = Math.round(t.cpu_percent || 0);
                    cpuPercent.textContent = `${cpu}%`;
                    cpuBar.style.width = `${cpu}%`;
                }
                if (ramPercent && ramBar) {
                    const ram = Math.round(t.ram_percent || 0);
                    ramPercent.textContent = `${ram}% (${t.ram_used_gb || 0}/${t.ram_total_gb || 0} GB)`;
                    ramBar.style.width = `${ram}%`;
                }
                if (diskPercent && diskBar) {
                    const disk = Math.round(t.disk_percent || 0);
                    diskPercent.textContent = `${disk}%`;
                    diskBar.style.width = `${disk}%`;
                }
            }
        } catch (err) {
            console.warn('Telemetry fetch error:', err);
        }
    }

    // Poll status every 3 seconds
    setInterval(updateTelemetry, 3000);
    updateTelemetry();

    // -------------------------------------------------------------
    // 2. Quick Actions
    // -------------------------------------------------------------
    async function sendAction(action, value = null) {
        try {
            const res = await fetch('/api/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, value })
            });
            const data = await res.json();
            return data;
        } catch (err) {
            console.error('Action error:', err);
        }
    }

    if (screenshotBtn) {
        screenshotBtn.addEventListener('click', async () => {
            screenshotBtn.disabled = true;
            screenshotBtn.textContent = '📸 Capturing...';
            const data = await sendAction('screenshot');
            screenshotBtn.disabled = false;
            screenshotBtn.textContent = '📸 Screen';
            if (data && data.result) {
                appendMessage('system', `📸 स्क्रीनशॉट सहेजा गया: ${data.result}`);
            }
        });
    }

    if (volDownBtn) {
        volDownBtn.addEventListener('click', async () => {
            await sendAction('volume_down');
        });
    }

    if (volUpBtn) {
        volUpBtn.addEventListener('click', async () => {
            await sendAction('volume_up');
        });
    }

    if (modelSelector) {
        modelSelector.addEventListener('change', async (e) => {
            const selected = e.target.value;
            appendMessage('system', `🔄 AI Brain स्विच किया जा रहा है: ${selected}...`);
            const res = await sendAction('switch_model', selected);
            if (res && res.result) {
                appendMessage('system', `✅ AI Brain सक्रिय: ${selected}`);
                if (activeModelVal) activeModelVal.textContent = selected.toUpperCase();
            }
        });
    }

    // -------------------------------------------------------------
    // 3. Chat Messaging & Audio Feedback
    // -------------------------------------------------------------
    function appendMessage(sender, text, timestamp = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `msg ${sender}-msg`;

        const avatar = document.createElement('div');
        avatar.className = 'msg-avatar';
        avatar.textContent = sender === 'user' ? 'U' : (sender === 'system' ? '⚙️' : 'V');

        const body = document.createElement('div');
        body.className = 'msg-body';

        const senderTitle = document.createElement('div');
        senderTitle.className = 'msg-sender';
        senderTitle.textContent = sender === 'user' ? 'You' : (sender === 'system' ? 'System' : 'Victoria');

        const textDiv = document.createElement('div');
        textDiv.className = 'msg-text';
        
        // Basic formatting: handle code blocks or line breaks
        if (text.includes('```')) {
            textDiv.innerHTML = formatMarkdown(text);
        } else {
            textDiv.textContent = text;
        }

        body.appendChild(senderTitle);
        body.appendChild(textDiv);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(body);

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatMarkdown(content) {
        // Simple client-side sanitizer and code block formatter
        let escaped = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks ```code```
        escaped = escaped.replace(/```([\s\S]*?)```/g, (match, p1) => {
            return `<pre class="chat-code-block"><code>${p1}</code></pre>`;
        });

        // Inline backticks `code`
        escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
        
        // Line breaks
        return escaped.replace(/\n/g, '<br>');
    }

    // Connect Audio Element to Waveform Canvas
    function initAudioStream() {
        if (!audioSourceConnected && ttsAudio && window.waveformVisualizer) {
            try {
                window.waveformVisualizer.connectAudioElement(ttsAudio);
                audioSourceConnected = true;
            } catch (err) {
                console.log("Audio analyzer connection notice:", err);
            }
        }
    }

    // Hook audio events to 3D Holographic Brain state
    if (ttsAudio) {
        ttsAudio.addEventListener('play', () => {
            if (window.neuralBrain) window.neuralBrain.setState('SPEAKING');
            if (voiceStatusVal) voiceStatusVal.textContent = 'SPEAKING';
        });

        ttsAudio.addEventListener('ended', () => {
            if (window.neuralBrain) window.neuralBrain.setState('IDLE');
            if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
        });

        ttsAudio.addEventListener('pause', () => {
            if (window.neuralBrain) window.neuralBrain.setState('IDLE');
            if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
        });

        ttsAudio.addEventListener('error', () => {
            if (window.neuralBrain) window.neuralBrain.setState('IDLE');
            if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
        });
    }

    // Submit Chat
    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (!message) return;

            // Render User Message
            appendMessage('user', message);
            chatInput.value = '';

            // Update Brain to Thinking state
            if (window.neuralBrain) window.neuralBrain.setState('THINKING');
            if (voiceStatusVal) voiceStatusVal.textContent = 'THINKING';
            sendBtn.disabled = true;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, speak: true })
                });

                if (!res.ok) {
                    throw new Error(`Server returned status ${res.status}`);
                }

                const data = await res.json();

                // Render Assistant Message
                appendMessage('assistant', data.response || "आदेश पूरा कर दिया गया है।");

                // Play Audio Speech if available
                if (data.audio_url && ttsAudio) {
                    initAudioStream();
                    ttsAudio.src = data.audio_url;
                    ttsAudio.play().catch(e => console.log("Audio autoplay notice:", e));
                } else {
                    if (window.neuralBrain) window.neuralBrain.setState('IDLE');
                    if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
                }

            } catch (err) {
                appendMessage('system', `त्रुटि: ${err.message}`);
                if (window.neuralBrain) window.neuralBrain.setState('IDLE');
                if (voiceStatusVal) voiceStatusVal.textContent = 'ONLINE';
            } finally {
                sendBtn.disabled = false;
                chatInput.focus();
            }
        });
    }

    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', () => {
            chatMessages.innerHTML = `
                <div class="msg assistant-msg">
                    <div class="msg-avatar">V</div>
                    <div class="msg-body">
                        <div class="msg-sender">Victoria</div>
                        <div class="msg-text">कंसोल रीसेट हो गया है। मैं आपके आदेश की प्रतीक्षा कर रही हूँ मालिक!</div>
                    </div>
                </div>
            `;
        });
    }

    // -------------------------------------------------------------
    // 4. Web Speech API Voice Recognition (Hindi/English)
    // -------------------------------------------------------------
    let recognition = null;
    let isListening = false;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'hi-IN'; // Default to Hindi, falls back naturally

        recognition.onstart = () => {
            isListening = true;
            if (micBtn) micBtn.classList.add('listening');
            if (voiceStatusVal) voiceStatusVal.textContent = 'HEARING';
            if (chatInput) chatInput.placeholder = 'सुन रही हूँ... बोलिए...';
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (chatInput && transcript) {
                chatInput.value = transcript;
                // Automatically transmit spoken command
                chatForm.dispatchEvent(new Event('submit'));
            }
        };

        recognition.onerror = (event) => {
            console.log('Speech recognition event:', event.error);
            stopMic();
        };

        recognition.onend = () => {
            stopMic();
        };
    }

    function stopMic() {
        isListening = false;
        if (micBtn) micBtn.classList.remove('listening');
        if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
        if (chatInput) chatInput.placeholder = "विक्टोरिया को आदेश दें (e.g. 'reverse engineer https://github.com' या 'वॉल्यूम बढ़ाओ')...";
    }

    if (micBtn) {
        micBtn.addEventListener('click', () => {
            if (!recognition) {
                alert("इस ब्राउज़र में Web Speech API समर्थित नहीं है। Chrome या Chromium का उपयोग करें।");
                return;
            }
            if (isListening) {
                recognition.stop();
            } else {
                initAudioStream();
                try {
                    recognition.start();
                } catch (e) {
                    console.warn(e);
                }
            }
        });
    }

    // -------------------------------------------------------------
    // 5. REA (Reverse Engineer Anything) Engine
    // -------------------------------------------------------------
    async function loadReports() {
        if (!reportsList) return;
        try {
            const res = await fetch('/api/reports');
            if (!res.ok) return;
            const reports = await res.json();

            if (!reports || reports.length === 0) {
                reportsList.innerHTML = `<div class="empty-state">अभी तक कोई टीयरडाउन रिपोर्ट मौजूद नहीं है। ऊपर कोई टारगेट डालकर 'DEEP TEARDOWN' पर क्लिक करें।</div>`;
                return;
            }

            reportsList.innerHTML = '';
            reports.forEach(r => {
                const item = document.createElement('div');
                item.className = 'report-item';
                const dateStr = new Date(r.created_at * 1000).toLocaleString();
                const kb = Math.round(r.size / 1024);

                item.innerHTML = `
                    <div class="report-title">⚡ ${r.title}</div>
                    <div class="report-meta">📄 ${r.filename} &bull; ${kb} KB &bull; ${dateStr}</div>
                `;

                item.addEventListener('click', () => {
                    viewReport(r.filename);
                });

                reportsList.appendChild(item);
            });
        } catch (err) {
            console.warn('Reports load error:', err);
        }
    }

    async function viewReport(filename) {
        try {
            const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`);
            if (!res.ok) return;
            const data = await res.json();

            if (blueprintCode) {
                blueprintCode.textContent = data.content || '// Empty report';
            }

            // Switch to Blueprint Tab
            switchTab('preview');
        } catch (err) {
            console.error('Error viewing report:', err);
        }
    }

    // Handle REA Form Submission
    if (reaForm) {
        reaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const target = reaTargetInput.value.trim();
            const targetType = reaTypeSelect.value;
            if (!target) return;

            // UI state updates
            runReaBtn.disabled = true;
            runReaBtn.innerHTML = `<span>⏳ REA ANALYZING TARGET...</span>`;
            if (window.neuralBrain) window.neuralBrain.setState('REA_ACTIVE');
            if (voiceStatusVal) voiceStatusVal.textContent = 'REA RECON';

            appendMessage('system', `⚡ REA Teardown शुरू किया जा रहा है: '${target}' (${targetType})...`);

            try {
                const res = await fetch('/api/rea', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target: target, target_type: targetType })
                });

                if (!res.ok) {
                    throw new Error(`REA Server error ${res.status}`);
                }

                const report = await res.json();
                appendMessage('assistant', `✅ REA Teardown पूरा हुआ!\nटारगेट: ${report.target}\nप्रकार: ${report.target_type}\nसमय: ${report.duration_seconds}s\nरिपोर्ट: ${report.markdown_report_path}`);

                // Reload reports list
                await loadReports();

                // If markdown file path exists, extract basename and view
                if (report.markdown_report_path) {
                    const filename = report.markdown_report_path.split('/').pop();
                    await viewReport(filename);
                }

            } catch (err) {
                appendMessage('system', `❌ REA त्रुटि: ${err.message}`);
            } finally {
                runReaBtn.disabled = false;
                runReaBtn.innerHTML = `<span>⚡ DEEP TEARDOWN & RECONSTRUCT</span>`;
                if (window.neuralBrain) window.neuralBrain.setState('IDLE');
                if (voiceStatusVal) voiceStatusVal.textContent = 'LISTENING';
            }
        });
    }

    const personaTab = document.getElementById('personaTab');
    const personaContent = document.getElementById('personaContent');
    const personaBtn = document.getElementById('personaBtn');

    async function loadPersona() {
        if (!personaContent) return;
        try {
            const res = await fetch('/api/persona');
            if (!res.ok) return;
            const data = await res.json();
            personaContent.textContent = data.markdown || JSON.stringify(data.profile, null, 2);
        } catch (err) {
            console.warn('Persona load error:', err);
        }
    }

    if (personaBtn) {
        personaBtn.addEventListener('click', () => {
            switchTab('persona');
        });
    }

    const memoryTab = document.getElementById('memoryTab');
    const memoriesList = document.getElementById('memoriesList');
    const memorySearchInput = document.getElementById('memorySearchInput');
    const memorySearchBtn = document.getElementById('memorySearchBtn');

    async function loadMemories(query = '') {
        if (!memoriesList) return;
        try {
            const url = query ? `/api/owner-memory?q=${encodeURIComponent(query)}` : '/api/owner-memory';
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();
            const items = data.memories || [];

            if (items.length === 0) {
                memoriesList.innerHTML = `<div class="empty-state">कोई लोकल मेमोरी नहीं मिली।</div>`;
                return;
            }

            memoriesList.innerHTML = '';
            items.forEach(m => {
                const item = document.createElement('div');
                item.className = 'report-item';
                const stars = '⭐'.repeat(m.importance || 3);
                const cat = (m.category || 'fact').toUpperCase();

                item.innerHTML = `
                    <div class="report-title">🧠 [${cat}] ${m.title} <span style="font-size:0.75rem; color:#f59e0b;">${stars}</span></div>
                    <div style="font-size:0.8rem; color:#cbd5e1; margin:4px 0;">${m.content}</div>
                    <div class="report-meta">📅 ${m.created_at} &bull; ID: ${m.id} &bull; रिकॉल: ${m.access_count || 0} बार</div>
                `;
                memoriesList.appendChild(item);
            });
        } catch (err) {
            console.warn('Memory load error:', err);
        }
    }

    if (memorySearchBtn) {
        memorySearchBtn.addEventListener('click', () => {
            loadMemories(memorySearchInput?.value.trim() || '');
        });
    }

    if (memorySearchInput) {
        memorySearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                loadMemories(memorySearchInput.value.trim());
            }
        });
    }

    // Tab Switching
    function switchTab(tabName) {
        tabBtns.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        if (reportsTab) reportsTab.classList.add('hidden');
        if (previewTab) previewTab.classList.add('hidden');
        if (personaTab) personaTab.classList.add('hidden');
        if (memoryTab) memoryTab.classList.add('hidden');
        if (experienceTab) experienceTab.classList.add('hidden');

        if (tabName === 'reports') {
            if (reportsTab) reportsTab.classList.remove('hidden');
        } else if (tabName === 'preview') {
            if (previewTab) previewTab.classList.remove('hidden');
        } else if (tabName === 'persona') {
            if (personaTab) personaTab.classList.remove('hidden');
            loadPersona();
        } else if (tabName === 'memory') {
            if (memoryTab) memoryTab.classList.remove('hidden');
            loadMemories();
        } else if (tabName === 'experience') {
            if (experienceTab) experienceTab.classList.remove('hidden');
            loadExperience();
        }
    }

    const experienceTab = document.getElementById('experienceTab');
    const evolutionRankTitle = document.getElementById('evolutionRankTitle');
    const evolutionScoreBadge = document.getElementById('evolutionScoreBadge');
    const evolutionSummary = document.getElementById('evolutionSummary');
    const learnedRulesList = document.getElementById('learnedRulesList');
    const masteredRecipesList = document.getElementById('masteredRecipesList');
    const newRuleInput = document.getElementById('newRuleInput');
    const saveRuleBtn = document.getElementById('saveRuleBtn');

    async function loadExperience() {
        if (!learnedRulesList && !masteredRecipesList) return;
        try {
            const res = await fetch('/api/experience');
            if (!res.ok) return;
            const data = await res.json();

            if (evolutionRankTitle && data.evolution_level) {
                evolutionRankTitle.textContent = `Level ${data.evolution_level}: ${data.level_title}`;
            }
            if (evolutionScoreBadge && data.evolution_score !== undefined) {
                evolutionScoreBadge.textContent = `Score: ${data.evolution_score} XP`;
            }
            if (evolutionSummary) {
                evolutionSummary.textContent = `विक्टोरिया ने अब तक ${data.total_recipes} टास्क वर्कफ़्लो और ${data.total_rules} व्यक्तिगत नियम सीख लिए हैं।`;
            }

            // Populate learned rules
            if (learnedRulesList) {
                const rules = data.recent_rules || [];
                if (rules.length === 0) {
                    learnedRulesList.innerHTML = `<div class="empty-state">अभी कोई नियम दर्ज नहीं हुआ है।</div>`;
                } else {
                    learnedRulesList.innerHTML = '';
                    rules.forEach(r => {
                        const item = document.createElement('div');
                        item.className = 'report-item';
                        item.innerHTML = `
                            <div class="report-title">🛡️ [${r.rule_type.toUpperCase()}] ${r.rule_instruction}</div>
                            <div class="report-meta">🎯 ट्रिगर: '${r.trigger_keywords}' &bull; लागू हुआ: ${r.times_applied} बार</div>
                        `;
                        learnedRulesList.appendChild(item);
                    });
                }
            }

            // Populate mastered recipes
            if (masteredRecipesList) {
                const recipes = data.top_recipes || [];
                if (recipes.length === 0) {
                    masteredRecipesList.innerHTML = `<div class="empty-state">जैसे-जैसे आप काम करवाएंगे, सिद्ध वर्कफ़्लो यहाँ दर्ज होते जाएंगे।</div>`;
                } else {
                    masteredRecipesList.innerHTML = '';
                    recipes.forEach(rc => {
                        const item = document.createElement('div');
                        item.className = 'report-item';
                        const toolNames = (rc.tools || []).map(t => t.tool).filter(Boolean).join(' ➔ ');
                        item.innerHTML = `
                            <div class="report-title">⚡ ${rc.intent_summary}</div>
                            <div style="font-size:0.75rem; color:#38bdf8; margin: 3px 0;">🛠️ टूल्स: ${toolNames || 'Direct'}</div>
                            <div class="report-meta">🏆 सफलता: ${rc.success_count} बार &bull; अंतिम उपयोग: ${rc.created_at || 'हाल ही में'}</div>
                        `;
                        masteredRecipesList.appendChild(item);
                    });
                }
            }
        } catch (err) {
            console.warn('Experience load error:', err);
        }
    }

    if (saveRuleBtn && newRuleInput) {
        saveRuleBtn.addEventListener('click', async () => {
            const ruleText = newRuleInput.value.trim();
            if (!ruleText) return;
            try {
                const res = await fetch('/api/experience/rules', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trigger: ruleText.slice(0, 30),
                        rule_instruction: ruleText,
                        rule_type: 'correction'
                    })
                });
                if (res.ok) {
                    newRuleInput.value = '';
                    loadExperience();
                    appendMessage('system', `💡 विक्टोरिया ने नया नियम सीखा: "${ruleText}"`);
                }
            } catch (err) {
                console.warn('Save rule error:', err);
            }
        });
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });

    // -------------------------------------------------------------
    // AI Brain & Model Connection Manager
    // -------------------------------------------------------------
    const connectAiBtn = document.getElementById('connectAiBtn');
    const aiStatusDot = document.getElementById('aiStatusDot');
    const brainModal = document.getElementById('brainModal');
    const closeBrainModalBtn = document.getElementById('closeBrainModalBtn');
    const currentActiveEngine = document.getElementById('currentActiveEngine');
    const currentEngineStatus = document.getElementById('currentEngineStatus');
    const connectionStatusBox = document.getElementById('connectionStatusBox');
    const statusText = document.getElementById('statusText');
    const statusSpinner = document.getElementById('statusSpinner');
    const brainTabBtns = document.querySelectorAll('.brain-tab-btn');
    const providerPanels = document.querySelectorAll('.provider-panel');
    const togglePwdBtns = document.querySelectorAll('.toggle-pwd-btn');
    const connectKeyBtns = document.querySelectorAll('.connect-key-btn');
    const activateOllamaBtn = document.getElementById('activateOllamaBtn');
    const ollamaModelSelect = document.getElementById('ollamaModelSelect');
    const openrouterModelSelect = document.getElementById('openrouterModelSelect');
    const refreshFreeModelsBtn = document.getElementById('refreshFreeModelsBtn');
    const freeModelNote = document.getElementById('freeModelNote');
    const openrouterApiKeyInput = document.getElementById('openrouterApiKeyInput');

    async function fetchOpenRouterFreeModels(userKey = '') {
        if (!openrouterModelSelect) return;
        const key = userKey || (openrouterApiKeyInput ? openrouterApiKeyInput.value.trim() : '');
        if (freeModelNote) {
            freeModelNote.textContent = '🔄 Loading latest 100% Free AI Models from OpenRouter...';
            freeModelNote.style.color = 'var(--neon-cyan)';
        }
        if (refreshFreeModelsBtn) refreshFreeModelsBtn.disabled = true;

        try {
            const url = key ? `/api/brain/openrouter/models?api_key=${encodeURIComponent(key)}` : '/api/brain/openrouter/models';
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const models = data.models || [];
            const currentSelected = data.current_selected || '';

            if (models.length > 0) {
                openrouterModelSelect.innerHTML = '';
                models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    const ctxK = m.context_length ? Math.round(m.context_length / 1024) + 'k ctx' : '';
                    opt.textContent = `${m.name} ${ctxK ? `(${ctxK})` : ''} — FREE`;
                    if (m.id === currentSelected || (currentSelected && m.id.includes(currentSelected))) {
                        opt.selected = true;
                    }
                    openrouterModelSelect.appendChild(opt);
                });
                if (freeModelNote) {
                    freeModelNote.textContent = `✨ ${models.length} 100% मुफ़्त AI मॉडल्स उपलब्ध हैं! जो चाहें वह चुनें।`;
                    freeModelNote.style.color = 'var(--neon-green)';
                }
            }
        } catch (err) {
            console.warn('Failed to fetch openrouter free models:', err);
            if (freeModelNote) {
                freeModelNote.textContent = '⚠️ लाइव सूची लोड नहीं हो सकी, पर डिफ़ॉल्ट मुफ़्त मॉडल्स उपयोग हेतु तैयार हैं।';
                freeModelNote.style.color = 'var(--neon-yellow)';
            }
        } finally {
            if (refreshFreeModelsBtn) refreshFreeModelsBtn.disabled = false;
        }
    }

    function showConnectionStatus(state, msg) {
        if (!connectionStatusBox || !statusText) return;
        connectionStatusBox.classList.remove('hidden', 'success', 'error');
        if (state === 'loading') {
            if (statusSpinner) statusSpinner.style.display = 'block';
            statusText.textContent = msg;
        } else if (state === true) {
            if (statusSpinner) statusSpinner.style.display = 'none';
            connectionStatusBox.classList.add('success');
            statusText.textContent = msg;
        } else {
            if (statusSpinner) statusSpinner.style.display = 'none';
            connectionStatusBox.classList.add('error');
            statusText.textContent = msg;
        }
    }

    async function fetchBrainStatus() {
        try {
            const res = await fetch('/api/brain/models');
            if (!res.ok) return;
            const data = await res.json();

            // 1. Update Active Engine display
            if (currentActiveEngine && data.active_model) {
                currentActiveEngine.textContent = data.active_model.toUpperCase().replace(/_/g, ' ');
            }

            // 2. Check active model key presence
            const activeModelObj = data.models ? data.models.find(m => m.id === data.active_model) : null;
            const hasKey = activeModelObj ? activeModelObj.has_key : false;

            if (currentEngineStatus) {
                if (hasKey) {
                    currentEngineStatus.textContent = '● CONNECTED & READY';
                    currentEngineStatus.className = 'badge badge-success';
                } else {
                    currentEngineStatus.textContent = '● API KEY REQUIRED';
                    currentEngineStatus.className = 'badge badge-warn';
                }
            }

            // 3. Update header button dot
            if (aiStatusDot) {
                if (hasKey) {
                    aiStatusDot.className = 'status-dot dot-green';
                } else {
                    aiStatusDot.className = 'status-dot dot-warn';
                }
            }

            // 4. Update Header Chip
            if (activeModelVal && data.active_model) {
                activeModelVal.textContent = data.active_model.toUpperCase();
            }

            // 5. Pre-fill placeholders
            const p = data.providers;
            if (p) {
                const geminiInput = document.getElementById('geminiApiKeyInput');
                if (geminiInput && p.gemini && p.gemini.has_key) {
                    geminiInput.placeholder = `Configured: ${p.gemini.masked_key}`;
                }
                const orInput = document.getElementById('openrouterApiKeyInput');
                if (orInput && p.openrouter && p.openrouter.has_key) {
                    orInput.placeholder = `Configured: ${p.openrouter.masked_key}`;
                }
                const groqInput = document.getElementById('groqApiKeyInput');
                if (groqInput && p.groq && p.groq.has_key) {
                    groqInput.placeholder = `Configured: ${p.groq.masked_key}`;
                }
                const openaiInput = document.getElementById('openaiApiKeyInput');
                if (openaiInput && p.openai && p.openai.has_key) {
                    openaiInput.placeholder = `Configured: ${p.openai.masked_key}`;
                }
            }
        } catch (err) {
            console.warn('Error fetching brain status:', err);
        }
    }

    // Modal open / close handlers
    if (connectAiBtn && brainModal) {
        connectAiBtn.addEventListener('click', () => {
            brainModal.classList.remove('hidden');
            fetchBrainStatus();
            fetchOpenRouterFreeModels();
        });
    }

    if (closeBrainModalBtn && brainModal) {
        closeBrainModalBtn.addEventListener('click', () => {
            brainModal.classList.add('hidden');
        });
    }

    if (brainModal) {
        brainModal.addEventListener('click', (e) => {
            if (e.target === brainModal) {
                brainModal.classList.add('hidden');
            }
        });
    }

    // Toggle password visibility
    togglePwdBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const targetInput = document.getElementById(targetId);
            if (!targetInput) return;
            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                btn.textContent = '🔒';
            } else {
                targetInput.type = 'password';
                btn.textContent = '👁️';
            }
        });
    });

    // Provider Tabs
    brainTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const prov = btn.dataset.provider;
            brainTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            providerPanels.forEach(p => p.classList.add('hidden'));
            const activePanel = document.getElementById(`panel-${prov}`);
            if (activePanel) activePanel.classList.remove('hidden');
            if (connectionStatusBox) connectionStatusBox.classList.add('hidden');
            if (prov === 'openrouter') {
                fetchOpenRouterFreeModels();
            }
        });
    });

    if (refreshFreeModelsBtn) {
        refreshFreeModelsBtn.addEventListener('click', () => {
            fetchOpenRouterFreeModels();
        });
    }

    if (openrouterApiKeyInput) {
        let openrouterDebounce = null;
        openrouterApiKeyInput.addEventListener('input', () => {
            clearTimeout(openrouterDebounce);
            openrouterDebounce = setTimeout(() => {
                const k = openrouterApiKeyInput.value.trim();
                if (k.length > 15) {
                    fetchOpenRouterFreeModels(k);
                }
            }, 600);
        });
        openrouterApiKeyInput.addEventListener('paste', () => {
            setTimeout(() => {
                const k = openrouterApiKeyInput.value.trim();
                if (k.length > 15) {
                    fetchOpenRouterFreeModels(k);
                }
            }, 100);
        });
    }

    // Connect & Verify API Keys
    connectKeyBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const provider = btn.dataset.provider;
            let keyInput = null;
            let modelSelect = null;

            if (provider === 'gemini') {
                keyInput = document.getElementById('geminiApiKeyInput');
                modelSelect = document.getElementById('geminiModelSelect');
            } else if (provider === 'openrouter') {
                keyInput = document.getElementById('openrouterApiKeyInput');
                modelSelect = document.getElementById('openrouterModelSelect');
            } else if (provider === 'groq') {
                keyInput = document.getElementById('groqApiKeyInput');
            } else if (provider === 'openai') {
                keyInput = document.getElementById('openaiApiKeyInput');
            }

            const apiKey = keyInput ? keyInput.value.trim() : '';
            if (!apiKey) {
                showConnectionStatus(false, 'कृपया अपनी API Key यहाँ पेस्ट करें।');
                return;
            }

            showConnectionStatus('loading', `Verifying ${provider.toUpperCase()} credentials with server...`);
            btn.disabled = true;

            try {
                const res = await fetch('/api/brain/api-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: provider,
                        api_key: apiKey,
                        model_name: modelSelect ? modelSelect.value : null,
                        set_active: true
                    })
                });

                const data = await res.json();
                if (!res.ok) {
                    showConnectionStatus(false, data.detail || 'API Key verification failed');
                } else {
                    showConnectionStatus(true, `✅ ${data.message} Active Model: ${data.active_model}`);
                    if (keyInput) keyInput.value = '';
                    await fetchBrainStatus();
                    appendMessage('system', `🎉 AI Brain (${provider.toUpperCase()}) सफलतापूर्वक कनेक्ट हो गया है! अब विक्टोरिया आपकी पूरी तरह से पर्सनल असिस्टेंट है।`);
                }
            } catch (err) {
                showConnectionStatus(false, `Connection error: ${err.message}`);
            } finally {
                btn.disabled = false;
            }
        });
    });

    // Activate Local Ollama
    if (activateOllamaBtn && ollamaModelSelect) {
        activateOllamaBtn.addEventListener('click', async () => {
            const model = ollamaModelSelect.value;
            showConnectionStatus('loading', `Activating local Ollama model (${model})...`);
            try {
                const res = await fetch('/api/brain/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: model })
                });
                const data = await res.json();
                if (res.ok) {
                    showConnectionStatus(true, `✅ Local model ${model} activated!`);
                    await fetchBrainStatus();
                    appendMessage('system', `✅ Local Offline Model (${model}) सक्रिय हो गया है।`);
                } else {
                    showConnectionStatus(false, data.detail || 'Could not activate model');
                }
            } catch (err) {
                showConnectionStatus(false, err.message);
            }
        });
    }

    // Initial load of reports & brain status
    loadReports();
    fetchBrainStatus();
    fetchOpenRouterFreeModels();
});
