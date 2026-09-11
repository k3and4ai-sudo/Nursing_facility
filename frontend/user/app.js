// main application logic for user client
document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    let isDebugMode = urlParams.get("debug") === "true" || localStorage.getItem("nursing_debug_mode") === "true";

    let terminalId = urlParams.get("terminal_id");
    if (!terminalId) {
        const savedId = localStorage.getItem("nursing_terminal_id");
        if (savedId && savedId === "user_tablet_1") {
            terminalId = savedId;
        } else {
            // Default to demo registered terminal user_tablet_1
            terminalId = "user_tablet_1";
        }
    }
    localStorage.setItem("nursing_terminal_id", terminalId);
    
    // UI Elements
    const roomBadge = document.getElementById("room-badge");
    const recordingStatusBadge = document.getElementById("recording-status-badge");
    const debugBadge = document.getElementById("debug-badge");
    const connectionStatus = document.getElementById("connection-status");
    const aiAvatar = document.getElementById("ai-avatar");
    const statusText = document.getElementById("status-text");
    const micBtn = document.getElementById("mic-btn");
    const guideText = document.getElementById("guide-text");
    const subtitleBox = document.getElementById("subtitle-box");
    const userSpeechBox = document.getElementById("user-speech-box");
    const aiResponseBox = document.getElementById("ai-response-box");
    const mimamoriPopup = document.getElementById("mimamori-popup");
    const mimamoriPopupIcon = document.getElementById("mimamori-popup-icon");
    const mimamoriPopupTitle = document.getElementById("mimamori-popup-title");
    const mimamoriPopupDesc = document.getElementById("mimamori-popup-desc");
    const btnResumeRecording = document.getElementById("btn-resume-recording");
    const btnCloseMimamoriPopup = document.getElementById("btn-close-mimamori-popup");

    // System Config & Release Flags
    let systemInfo = { enable_debug_mode: true };
    async function checkSystemInfo() {
        try {
            const res = await fetch("/api/config/system_info");
            if (res.ok) {
                systemInfo = await res.json();
                if (!systemInfo.enable_debug_mode) {
                    isDebugMode = false;
                    localStorage.setItem("nursing_debug_mode", "false");
                    if (debugBadge) debugBadge.classList.add("hidden");
                }
            }
        } catch (e) {
            console.log("Could not fetch system info:", e);
        }
    }
    checkSystemInfo();

    // Debug Mode (Gemini Live) Toggle Logic
    // Web Speech API for instant client-side text rendering & automatic EOS trigger
    let speechRec = null;
    let currentUtteranceText = "";
    let speechDebounceTimer = null;
    let isAISpeaking = false;
    let isModalOpen = false;
    let isTTSAnnouncing = false;

    const SYSTEM_ECHO_KEYWORDS = [
        "個人情報保護", "会話を一時停止", "個人情報は話さない",
        "スタッフに連絡する場合は", "ボタンを押してください", "会話が終了します",
        "安心してお待ちください", "スタッフに連絡しました", "今後もお会いしましょう",
        "動画をご覧", "チャンネル登録"
    ];

    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
        const SpeechRecClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        speechRec = new SpeechRecClass();
        speechRec.continuous = true;
        speechRec.interimResults = true;
        speechRec.lang = "ja-JP";

        speechRec.onresult = (event) => {
            // Ignore microphone input while AI is speaking, modal is open, or system is announcing
            if (isAISpeaking || isPlayingPCM24 || isModalOpen || isTTSAnnouncing) {
                return;
            }

            let transcript = "";
            for (let i = event.results.length - 1; i >= 0; i--) {
                if (event.results[i] && event.results[i][0]) {
                    transcript = event.results[i][0].transcript;
                    break;
                }
            }
            const clean = transcript.trim();
            if (!clean) return;

            // Reject system prompt voice echoes
            if (SYSTEM_ECHO_KEYWORDS.some(k => clean.includes(k))) {
                console.log("[SpeechRec]: Discarded system prompt echo:", clean);
                return;
            }

            if (userSpeechBox) {
                userSpeechBox.textContent = clean;
                currentUtteranceText = clean;
                window.isSpeechRecActive = true;
                if (window.speechRecTimer) clearTimeout(window.speechRecTimer);
                window.speechRecTimer = setTimeout(() => {
                    window.isSpeechRecActive = false;
                }, 400);
                if (currentLampState !== "thinking" && currentLampState !== "speaking") {
                    setLiveLampState("sending");
                }
            }

            // Instant client-side trigger for confidential recording stop/resume
            const STOP_KEYWORDS = ["ここだけの話", "内緒", "言わんといて", "言わないで", "記録を止めて", "記録止めて", "秘密", "メモせんといて", "誰にも言わないで"];
            const RESUME_KEYWORDS = ["記録再開", "記録を再開", "内緒話はおしまい", "秘密はおしまい", "通常の会話に戻", "普通の会話に戻"];

            if (STOP_KEYWORDS.some(k => clean.includes(k))) {
                console.log("[SpeechRec Confidential Mode]: Instant client stop trigger:", clean);
                handleRecordingStatus(false, "会話記録停止");
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "stop_recording", text: clean }));
                }
            } else if (RESUME_KEYWORDS.some(k => clean.includes(k))) {
                console.log("[SpeechRec Confidential Mode]: Instant client resume trigger:", clean);
                handleRecordingStatus(true, "会話記録再開");
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "resume_recording", text: clean }));
                }
            }
        };

        speechRec.onend = () => {
            if (isRecording) {
                try { speechRec.start(); } catch(e){}
            }
        };

        speechRec.onerror = (e) => {
            console.log("SpeechRec error:", e);
        };
    }

    isDebugMode = urlParams.get("debug") === "true" || localStorage.getItem("nursing_debug_mode") === "true";
    function updateDebugUI() {
        if (isDebugMode && systemInfo.enable_debug_mode) {
            if (debugBadge) debugBadge.classList.remove("hidden");
            localStorage.setItem("nursing_debug_mode", "true");
            if (typeof connectLiveWS === "function" && (!liveWs || liveWs.readyState !== WebSocket.OPEN)) {
                connectLiveWS();
            }
        } else {
            if (debugBadge) debugBadge.classList.add("hidden");
            localStorage.setItem("nursing_debug_mode", "false");
        }
    }

    if (debugBadge) {
        debugBadge.addEventListener("click", () => {
            if (!systemInfo.enable_debug_mode) return;
            isDebugMode = !isDebugMode;
            updateDebugUI();
        });
    }

    // Secret Key Listener for 'DB' command (Disabled when ENABLE_DEBUG_MODE=false)
    let keyBuffer = "";
    document.addEventListener("keydown", (e) => {
        if (!systemInfo.enable_debug_mode) return;
        keyBuffer += e.key.toUpperCase();
        if (keyBuffer.length > 2) keyBuffer = keyBuffer.slice(-2);
        if (keyBuffer === "DB") {
            isDebugMode = !isDebugMode;
            updateDebugUI();
            keyBuffer = "";
            console.log(`Debug Mode (Gemini Live) set to: ${isDebugMode}`);
        }
    });
    
    // Processing Status elements
    const processingIndicator = document.getElementById("processing-indicator");
    const lampStt = document.getElementById("lamp-stt");
    const lampLlm = document.getElementById("lamp-llm");
    const lampTts = document.getElementById("lamp-tts");
    const timeStt = document.getElementById("time-stt");
    const timeLlm = document.getElementById("time-llm");
    const timeTts = document.getElementById("time-tts");
    
    const registerOverlay = document.getElementById("register-overlay");
    const displayTerminalId = document.getElementById("display-terminal-id");
    const retryBtn = document.getElementById("retry-btn");
    
    const intercomOverlay = document.getElementById("intercom-overlay");
    const callCard = document.getElementById("call-card");
    const forceCallBanner = document.getElementById("force-call-banner");
    const callStatus = document.getElementById("call-status");
    const callSubstatus = document.getElementById("call-substatus");
    const answerBtn = document.getElementById("answer-btn");
    const hangupBtn = document.getElementById("hangup-btn");

    // Web Audio API Ringtone / Chime Synthesizer
    let chimeAudioCtx = null;

    function getChimeAudioContext() {
        if (!chimeAudioCtx) {
            chimeAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (chimeAudioCtx.state === "suspended") {
            chimeAudioCtx.resume();
        }
        return chimeAudioCtx;
    }

    function playTone(ctx, freq, startTime, duration, type = "sine", maxGain = 0.3) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, startTime);

        gain.gain.setValueAtTime(0.001, startTime);
        gain.gain.exponentialRampToValueAtTime(maxGain, startTime + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(startTime);
        osc.stop(startTime + duration);
    }

    let incomingChimeInterval = null;

    function playIncomingChime(isForce = false, callerType = "staff") {
        try {
            const ctx = getChimeAudioContext();
            const now = ctx.currentTime;

            if (isForce) {
                // Emergency Dual-Alert Beeps + High alert chime
                playTone(ctx, 880, now, 0.15, "square", 0.3);
                playTone(ctx, 880, now + 0.22, 0.15, "square", 0.3);
                playTone(ctx, 659.25, now + 0.45, 0.35, "sine", 0.4);
                playTone(ctx, 523.25, now + 0.75, 0.6, "sine", 0.4);
            } else if (callerType === "family") {
                // Warm family 3-tone chime "Pin-Pon-Pan" (C5 523Hz -> E5 659Hz -> G5 784Hz)
                playTone(ctx, 523.25, now, 0.25, "sine", 0.35);
                playTone(ctx, 659.25, now + 0.22, 0.25, "sine", 0.35);
                playTone(ctx, 783.99, now + 0.45, 0.6, "sine", 0.4);
            } else {
                // Gentle standard door chime "Ding-Dong" (G5 784Hz -> E5 659Hz)
                playTone(ctx, 783.99, now, 0.45, "sine", 0.35);
                playTone(ctx, 659.25, now + 0.4, 0.75, "sine", 0.35);
            }
        } catch (e) {
            console.warn("Could not play incoming chime:", e);
        }
    }

    function startIncomingChimeLoop(isForce = false, callerType = "staff") {
        stopIncomingChimeLoop();
        // Play first chime immediately
        playIncomingChime(isForce, callerType);

        // Emergency force mode answers automatically within ~800ms, no loop needed
        if (isForce) return;

        // Repeat incoming chime every 5 seconds until answered or hung up
        incomingChimeInterval = setInterval(() => {
            if (isCallActive || !intercomOverlay || intercomOverlay.classList.contains("hidden")) {
                stopIncomingChimeLoop();
                return;
            }
            console.log("[User Intercom] Ringing 5s interval chime triggered");
            playIncomingChime(isForce, callerType);
        }, 5000);
    }

    function stopIncomingChimeLoop() {
        if (incomingChimeInterval) {
            clearInterval(incomingChimeInterval);
            incomingChimeInterval = null;
        }
    }

    // Audio Elements
    let activeAudio = null;
    const recorder = new WavAudioRecorder();
    let isRecording = false;

    // Intercom / Calling Variables
    let intercomStream = null;
    let intercomRecorder = null;
    let isCallActive = false;
    let autoAnswerTimer = null;
    let autoAnswerCountdownTimer = null;
    let audioQueue = [];
    let isPlayingQueue = false;

    // WebSocket Reference
    let ws = null;
    let userDetails = null;
    let currentReportedStatus = "idle";

    function reportTerminalStatus(status) {
        if (currentReportedStatus === status && status !== "idle") return;
        currentReportedStatus = status;
        if (ws && ws.readyState === WebSocket.OPEN) {
            try {
                ws.send(JSON.stringify({ type: "status_update", status: status }));
            } catch (e) {
                console.warn("Failed to report terminal status:", e);
            }
        }
    }

    // Initialize display ID
    displayTerminalId.textContent = terminalId;

    // Fetch user details from Server API
    async function checkRegistration() {
        try {
            const response = await fetch(`/api/users/terminal/${terminalId}`);
            if (response.status === 404) {
                if (isDebugMode && terminalId !== "user_tablet_1") {
                    console.log("Unregistered terminal in debug mode, auto-fallback to user_tablet_1");
                    terminalId = "user_tablet_1";
                    localStorage.setItem("nursing_terminal_id", terminalId);
                    if (displayTerminalId) displayTerminalId.textContent = terminalId;
                    return await checkRegistration();
                }
                showRegisterScreen();
                return false;
            }
            if (!response.ok) throw new Error("API Error");
            
            userDetails = await response.json();
            roomBadge.textContent = `${userDetails.room_number}号室 ${userDetails.name}様`;
            hideRegisterScreen();
            micBtn.disabled = false;
            statusText.textContent = "お話しする準備ができました";
            return true;
        } catch (err) {
            console.error("Error fetching user details:", err);
            statusText.textContent = "サーバーに接続できません";
            return false;
        }
    }

    function showRegisterScreen() {
        registerOverlay.classList.remove("hidden");
        micBtn.disabled = true;
        statusText.textContent = "未登録の端末です";
    }

    function hideRegisterScreen() {
        registerOverlay.classList.add("hidden");
    }

    // Connect WebSockets
    function connectWS() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/user/${terminalId}`;
        
        ws = new WebSocket(wsUrl);

        ws.onopen = async () => {
            console.log("WebSocket connected");
            connectionStatus.className = "status-dot online";
            reportTerminalStatus("idle");
            const registered = await checkRegistration();
            if (!registered) {
                statusText.textContent = "端末の登録をお待ちしています...";
            }
        };

        ws.onclose = () => {
            console.log("WebSocket disconnected");
            connectionStatus.className = "status-dot offline";
            statusText.textContent = "通信が切れました。再接続しています...";
            micBtn.disabled = true;
            // Retry connection after 3s
            setTimeout(connectWS, 3000);
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
        };

        ws.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            console.log("WS Received:", data.type);

            switch (data.type) {
                case "transcription_result":
                    if (userSpeechBox) userSpeechBox.textContent = data.text;
                    if (subtitleBox) subtitleBox.textContent = `あなた: "${data.text}"`;
                    setAvatarState("thinking");
                    statusText.textContent = "考え中...";
                    break;

                case "processing_status":
                    handleProcessingStatus(data.status, data.stt_time, data.llm_time);
                    break;

                case "chat_response":
                    handleChatResponse(data.text, data.audio, data.stt_time, data.llm_time, data.tts_time);
                    break;
                    
                case "play_voice": // Staff override (Pattern B)
                    // Interrupt current playback
                    if (activeAudio) {
                        activeAudio.pause();
                        activeAudio = null;
                    }
                    handleStaffOverride(data.text, data.audio);
                    break;

                case "guardrail_result":
                    handleGuardrailResult(data);
                    break;

                case "incoming_call": // Intercom Call requested (Pattern A)
                    handleIncomingCall(data);
                    break;

                case "call_answered":
                case "call_started":
                    console.log("[User WS] Call answered/started event received from server");
                    if (!isCallActive && intercomOverlay && !intercomOverlay.classList.contains("hidden")) {
                        startIntercomSession();
                    }
                    break;

                case "intercom_audio": // Intercom incoming audio chunks
                    // If audio chunks start arriving while call modal is up, ensure session is marked active and answer button is hidden
                    if (!isCallActive && intercomOverlay && !intercomOverlay.classList.contains("hidden")) {
                        startIntercomSession();
                    }
                    if (isCallActive) {
                        playIntercomChunk(data.audio);
                    }
                    break;

                case "intercom_hangup":
                    endIntercomCall(false);
                    break;

                case "error":
                    statusText.textContent = data.message;
                    break;
            }
        };
    }

    // PII Warning Elements
    const piiWarningOverlay = document.getElementById("pii-warning-overlay");
    const resumePiiBtn = document.getElementById("resume-pii-btn");
    const piiWarningText = document.getElementById("pii-warning-text");

    let liveWs = null;
    let liveAudioCtx = null;

    function connectLiveWS() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/user/${terminalId}/live`;
        liveWs = new WebSocket(wsUrl);

        liveWs.onopen = () => {
            console.log("Gemini Live WS connected");
        };

        liveWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "live_audio_output") {
                setLiveLampState("speaking");
                setAvatarState("speaking");
                playPCM24Chunk(data.data, data.sample_rate || 24000);
            } else if (data.type === "live_response" || data.type === "live_text_output") {
                if (aiResponseBox && data.text) {
                    if (data.type === "live_text_output") {
                        if (!aiResponseBox.textContent || aiResponseBox.textContent.includes("表示されます") || aiResponseBox.textContent.includes("待っています") || aiResponseBox.textContent.includes("リアルタイム音声応答中")) {
                            aiResponseBox.textContent = data.text;
                        } else if (!aiResponseBox.textContent.endsWith(data.text)) {
                            aiResponseBox.textContent += data.text;
                        }
                    } else {
                        aiResponseBox.textContent = data.text;
                    }
                    setLiveLampState("speaking");
                    setAvatarState("speaking");
                }
            } else if (data.type === "transcription_result") {
                // If Web Speech API is already providing instant text, do not overwrite with delayed buffer
                if (userSpeechBox && data.text && (!window.isSpeechRecActive || !userSpeechBox.textContent)) {
                    userSpeechBox.textContent = data.text;
                }
            } else if (data.type === "chat_response") {
                if (userSpeechBox && data.user_text) userSpeechBox.textContent = data.user_text;
                if (aiResponseBox && data.text) aiResponseBox.textContent = data.text;
            } else if (data.type === "pii_warning") {
                handlePIIWarning(data.message);
            } else if (data.type === "gemini_thinking") {
                setLiveLampState("thinking");
                setAvatarState("thinking");
                if (statusText) statusText.textContent = "🧠 Gemini考え中...";
            } else if (data.type === "guardrail_result") {
                handleGuardrailResult(data);
            } else if (data.type === "recording_status") {
                handleRecordingStatus(data.active, data.message);
            }
        };

        liveWs.onclose = () => {
            console.log("Gemini Live WS disconnected");
            setTimeout(connectLiveWS, 3000);
        };
    }

    // 🔒 Mimamori-san Recording Status & Popup Handler
    function handleRecordingStatus(isActive, message) {
        console.log("[Mimamori Recording Status]:", isActive, message);
        if (recordingStatusBadge) {
            if (isActive) {
                recordingStatusBadge.className = "badge recording-active-badge";
                recordingStatusBadge.textContent = "🟢 記録中";
            } else {
                recordingStatusBadge.className = "badge recording-paused-badge";
                recordingStatusBadge.textContent = "🔒 記録停止中";
            }
        }

        if (mimamoriPopup) {
            clearTimeout(window.mimamoriPopupTimer);
            if (!isActive) {
                // 🔒 会話記録停止のポップアップ表示
                if (mimamoriPopupIcon) mimamoriPopupIcon.textContent = "🔒";
                if (mimamoriPopupTitle) {
                    mimamoriPopupTitle.textContent = "会話記録を停止しました";
                    mimamoriPopupTitle.style.color = "#6d28d9";
                }
                if (mimamoriPopupDesc) {
                    mimamoriPopupDesc.innerHTML = "「ここだけの秘密のお話として、安心してお話しくださいね。<br>この会話は記録や日誌には一切残りません。」";
                }
                if (btnResumeRecording) btnResumeRecording.style.display = "flex";
                if (btnCloseMimamoriPopup) {
                    const span = btnCloseMimamoriPopup.querySelector("span:last-child");
                    if (span) span.textContent = "閉じて話す";
                }
                mimamoriPopup.classList.remove("hidden");
                // 8秒後に自動で閉じる（閉じた後も記録停止状態は継続）
                window.mimamoriPopupTimer = setTimeout(() => {
                    if (mimamoriPopup) mimamoriPopup.classList.add("hidden");
                }, 8000);
            } else {
                // 🟢 会話記録再開のポップアップ表示
                if (mimamoriPopupIcon) mimamoriPopupIcon.textContent = "🟢";
                if (mimamoriPopupTitle) {
                    mimamoriPopupTitle.textContent = "会話記録を再開しました";
                    mimamoriPopupTitle.style.color = "#059669";
                }
                if (mimamoriPopupDesc) {
                    mimamoriPopupDesc.innerHTML = "「いつもの見守り記録を再開しますね。<br>引き続き安心してお話しください。」";
                }
                if (btnResumeRecording) btnResumeRecording.style.display = "none";
                if (btnCloseMimamoriPopup) {
                    const span = btnCloseMimamoriPopup.querySelector("span:last-child");
                    if (span) span.textContent = "了解";
                }
                mimamoriPopup.classList.remove("hidden");
                // 3.5秒後に自動で閉じる
                window.mimamoriPopupTimer = setTimeout(() => {
                    if (mimamoriPopup) mimamoriPopup.classList.add("hidden");
                }, 3500);
            }
        }
    }

    if (btnResumeRecording) {
        btnResumeRecording.addEventListener("click", () => {
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify({ type: "resume_recording" }));
            }
            if (mimamoriPopup) mimamoriPopup.classList.add("hidden");
        });
    }

    if (btnCloseMimamoriPopup) {
        btnCloseMimamoriPopup.addEventListener("click", () => {
            if (mimamoriPopup) mimamoriPopup.classList.add("hidden");
        });
    }

    // Safety Guardrail Monitor & Emergency Modal Elements
    const guardrailBanner = document.getElementById("guardrail-monitor-banner");
    const guardrailBadge = document.getElementById("guardrail-badge");
    const guardrailLatency = document.getElementById("guardrail-latency");
    const guardrailDetail = document.getElementById("guardrail-detail");
    const guardrailModel = document.getElementById("guardrail-model");
    const guardrailInlineCallBtn = document.getElementById("guardrail-inline-call-btn");

    const emergencyAssistModal = document.getElementById("emergency-assist-modal");
    const emergencyModalTitle = document.getElementById("emergency-modal-title");
    const emergencyModalDesc = document.getElementById("emergency-modal-desc");
    const callStaffNowBtn = document.getElementById("call-staff-now-btn");
    const dismissEmergencyBtn = document.getElementById("dismiss-emergency-btn");

    let alertLockTimer = null;
    let isAlertLocked = false;

    function showEmergencyModal(title, desc, voicePrompt = "スタッフに連絡しますか？", isAutoCalled = false) {
        isModalOpen = true;
        currentUtteranceText = "";
        stopLiveAudioPlayback();
        if (emergencyModalTitle && title) emergencyModalTitle.textContent = title;
        if (emergencyModalDesc && desc) emergencyModalDesc.innerHTML = desc;
        if (emergencyAssistModal) {
            emergencyAssistModal.classList.remove("hidden");
            emergencyAssistModal.style.display = "flex";
        }
        if (guardrailInlineCallBtn) guardrailInlineCallBtn.classList.remove("hidden");
        if (callStaffNowBtn) {
            if (isAutoCalled) {
                callStaffNowBtn.style.background = "#059669";
                callStaffNowBtn.innerHTML = '<span style="font-size: 2.5rem; line-height: 1;">✅</span><span>自動連絡済み（お待ちください）</span>';
                callStaffNowBtn.disabled = true;
            } else {
                callStaffNowBtn.style.background = "linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)";
                callStaffNowBtn.innerHTML = '<span style="font-size: 2.5rem; line-height: 1;">🚨</span><span>スタッフに連絡</span>';
                callStaffNowBtn.disabled = false;
            }
        }
        if (voicePrompt) {
            playTTSVoice(voicePrompt);
        }
    }

    function sendStaffEmergencyCall(reason) {
        console.log("[Emergency Call Triggered]:", reason);
        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
            liveWs.send(JSON.stringify({
                type: "user_emergency_call",
                reason: reason || "利用者様が画面の「スタッフに連絡」ボタンを押しました"
            }));
        }
        if (emergencyModalTitle) emergencyModalTitle.textContent = "✅ スタッフに連絡しました";
        if (emergencyModalDesc) emergencyModalDesc.innerHTML = "スタッフステーションへ直ちにお知らせしました。<br>スタッフが参りますので、そのまま安心してお待ちください。";
        if (callStaffNowBtn) {
            callStaffNowBtn.style.background = "#059669";
            callStaffNowBtn.innerHTML = '<span style="font-size: 2.5rem; line-height: 1;">✅</span><span>連絡完了（お待ちください）</span>';
            callStaffNowBtn.disabled = true;
        }
        if (guardrailBadge) {
            guardrailBadge.className = "guardrail-badge badge-emergency";
            guardrailBadge.textContent = "🚨 スタッフ連絡済み";
        }
        if (guardrailDetail) {
            guardrailDetail.textContent = "スタッフへ緊急通報を送信しました。スタッフの到着をお待ちください。";
        }
        playTTSVoice("スタッフに連絡しました。スタッフが向かいますので、安心してお待ちください。");
    }

    if (callStaffNowBtn) {
        callStaffNowBtn.addEventListener("click", () => {
            sendStaffEmergencyCall("画面のポップアップ「スタッフに連絡」ボタンが押されました");
        });
    }

    if (guardrailInlineCallBtn) {
        guardrailInlineCallBtn.addEventListener("click", () => {
            sendStaffEmergencyCall("バナーの「スタッフ呼出」ボタンが押されました");
        });
    }

    if (dismissEmergencyBtn) {
        dismissEmergencyBtn.addEventListener("click", () => {
            isModalOpen = false;
            currentUtteranceText = "";
            if (emergencyAssistModal) {
                emergencyAssistModal.classList.add("hidden");
                emergencyAssistModal.style.display = "none";
            }
            if (liveAudioCtx && liveAudioCtx.state === "suspended") {
                liveAudioCtx.resume();
            }
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify({ type: "resume_live_session" }));
            }
            if (statusText) statusText.textContent = "お話しする準備ができました";
        });
    }

    function handleGuardrailResult(data) {
        if (!guardrailBanner) return;

        if (guardrailModel && data.model) {
            guardrailModel.textContent = data.model;
        }
        if (guardrailLatency && data.latency !== undefined) {
            guardrailLatency.textContent = `⏱️ ${data.latency}s`;
        }

        const status = (data.status || "NORMAL").toUpperCase();
        const stage = data.stage !== undefined ? data.stage : (status === "EMERGENCY" ? 3 : (status === "ALERT" ? 2 : (status === "CAUTION" ? 1 : 0)));
        const summary = data.summary || "";
        const detail = data.detail || "";
        console.log("[Guardrail Result Received]:", status, "stage:", stage, data);

        // Check for personal information (PII) - ONLY trigger when status is strictly ALERT
        const isPII = (status === "ALERT" || stage === 2) && (
            summary.includes("個人情報") || summary.includes("口座") || summary.includes("住所") || 
            summary.includes("電話") || summary.includes("名前") || summary.includes("氏名") || 
            detail.includes("口座番号") || detail.includes("電話番号") || detail.includes("実名")
        );
        if (isPII) {
            console.warn("[Guardrail PII Detected]: Halting conversation and displaying overlay.");
            handlePIIWarning(data.detail || "個人情報保護のため会話を一時停止しました。個人情報は話さないようお願いいたします。");
            return;
        }

        if (status === "EMERGENCY" || stage === 3) {
            // 第三段階: 重度・緊急事態（即時自動通報＋全画面通知＋音声案内）
            if (alertLockTimer) clearTimeout(alertLockTimer);
            isAlertLocked = true;
            guardrailBanner.className = "guardrail-banner status-emergency";
            if (guardrailBadge) {
                guardrailBadge.className = "guardrail-badge badge-emergency";
                guardrailBadge.textContent = "🚨 緊急事態 (第三段階)";
            }
            if (guardrailDetail) {
                guardrailDetail.textContent = `【第三段階: 緊急事態】${data.summary || ""} - ${data.detail || ""}`;
            }
            if (guardrailInlineCallBtn) guardrailInlineCallBtn.classList.remove("hidden");

            showEmergencyModal(
                "🚨 スタッフへ緊急連絡しました",
                `急変や強い苦痛を検知しました（${data.summary || "緊急事態"}）。<br>スタッフステーションへ直ちに自動連絡しました。<br>スタッフが参りますので、そのまま安心してお待ちください。`,
                "スタッフに連絡しました。スタッフが向かいますので、安心してお待ちください。",
                true
            );

            alertLockTimer = setTimeout(() => {
                isAlertLocked = false;
            }, 30000);
        } else if (status === "ALERT" || stage === 2) {
            // 第二段階: 中度・要確認（警告表示 ＋ 音声「スタッフに連絡しますか？」＋ 特大ボタン確認）
            if (alertLockTimer) clearTimeout(alertLockTimer);
            isAlertLocked = true;
            guardrailBanner.className = "guardrail-banner status-alert";
            if (guardrailBadge) {
                guardrailBadge.className = "guardrail-badge badge-alert";
                guardrailBadge.textContent = "🔔 要確認 (第二段階)";
            }
            if (guardrailDetail) {
                guardrailDetail.textContent = `【第二段階: スタッフ確認】${data.summary || ""} - ${data.detail || ""}`;
            }
            if (guardrailInlineCallBtn) guardrailInlineCallBtn.classList.remove("hidden");

            showEmergencyModal(
                "🔔 スタッフに連絡しますか？",
                `体調の異常またはスタッフ連絡の要請を検知しました（${data.summary || "要確認"}）。<br>スタッフに連絡する場合はボタンを押してください。`,
                "スタッフに連絡しますか？",
                false
            );

            alertLockTimer = setTimeout(() => {
                isAlertLocked = false;
            }, 20000);
        } else if (status === "CAUTION" || stage === 1) {
            // 第一段階: 軽度・注意（警告表示のみ、何もしない、会話継続）
            if (alertLockTimer) clearTimeout(alertLockTimer);
            isAlertLocked = true;
            guardrailBanner.className = "guardrail-banner status-caution";
            if (guardrailBadge) {
                guardrailBadge.className = "guardrail-badge badge-caution";
                guardrailBadge.textContent = "⚠️ 注意 (第一段階)";
            }
            if (guardrailDetail) {
                guardrailDetail.textContent = `【第一段階: 軽度注意】${data.summary || ""} - ${data.detail || ""}`;
            }
            if (guardrailInlineCallBtn) guardrailInlineCallBtn.classList.remove("hidden");

            // 第一段階はモーダルや音声は出さず、会話をそのまま継続
            alertLockTimer = setTimeout(() => {
                isAlertLocked = false;
            }, 12000);
        } else {
            // 通常 NORMAL (日常会話・雑談)
            if (!isAlertLocked) {
                guardrailBanner.className = "guardrail-banner status-normal";
                if (guardrailBadge) {
                    guardrailBadge.className = "guardrail-badge badge-normal";
                    guardrailBadge.textContent = "🟢 正常";
                }
                if (guardrailDetail) {
                    guardrailDetail.textContent = data.detail ? `${data.summary ? data.summary + "： " : ""}${data.detail}` : "正常に監視中 (発話の安全を確認しました)";
                }
                if (guardrailInlineCallBtn) guardrailInlineCallBtn.classList.add("hidden");
            } else {
                console.log("[Guardrail]: Skipping NORMAL update because previous alert lock is active.");
            }
        }
    }

    const lampSending = document.getElementById("lamp-sending");
    const lampThinking = document.getElementById("lamp-thinking");
    const lampSpeaking = document.getElementById("lamp-speaking");

    let currentLampState = "idle";
    let silenceTimeout = null;
    let thinkingTimeoutTimer = null;

    function setLiveLampState(state) {
        if (silenceTimeout) {
            clearTimeout(silenceTimeout);
            silenceTimeout = null;
        }
        if (thinkingTimeoutTimer) {
            clearTimeout(thinkingTimeoutTimer);
            thinkingTimeoutTimer = null;
        }

        currentLampState = state;

        if (state === "sending") {
            if (lampSending) lampSending.classList.add("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
            if (statusText && !isModalOpen) statusText.textContent = "🎙️ 音声送信中...";
            silenceTimeout = setTimeout(() => {
                if (currentLampState === "sending") {
                    setLiveLampState("thinking");
                }
            }, 400);
        } else if (state === "thinking") {
            if (lampThinking) lampThinking.classList.add("lamp-active");
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
            if (statusText && !isModalOpen) statusText.textContent = "🧠 Gemini考え中...";
            if (guardrailBadge && !isAlertLocked) {
                guardrailBadge.textContent = "🔍 判定中...";
                if (guardrailDetail) guardrailDetail.textContent = "発話内容の安全性をローカルLLMで検査中...";
            }
            // Auto fallback to idle if no response after 12s
            thinkingTimeoutTimer = setTimeout(() => {
                if (currentLampState === "thinking") {
                    setLiveLampState("idle");
                    setAvatarState("idle");
                    if (statusText && !isModalOpen) statusText.textContent = "お話しする準備ができました";
                }
            }, 12000);
        } else if (state === "speaking") {
            if (lampSpeaking) lampSpeaking.classList.add("lamp-active");
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
            if (statusText && !isModalOpen) statusText.textContent = "Gemini Live と対話中...";
        } else if (state === "idle") {
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
        }
    }

    let nextAudioStartTime = 0;
    let isPlayingPCM24 = false;
    let pcm24EndTimer = null;
    const JITTER_BUFFER_SEC = 0.12; // 120ms initial buffer for seamless stutter-free playback

    function stopLiveAudioPlayback() {
        if (pcm24EndTimer) clearTimeout(pcm24EndTimer);
        isAISpeaking = false;
        isPlayingPCM24 = false;
        nextAudioStartTime = 0;
        if (liveAudioCtx && liveAudioCtx.state !== "closed") {
            try {
                liveAudioCtx.close();
                liveAudioCtx = null;
            } catch (e) {}
        }
    }

    function playPCM24Chunk(base64Data, sampleRate) {
        if (!liveAudioCtx || liveAudioCtx.state === "closed") {
            liveAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
        }
        if (liveAudioCtx.state === "suspended") {
            liveAudioCtx.resume();
        }
        try {
            const binaryStr = atob(base64Data);
            const len = binaryStr.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryStr.charCodeAt(i);
            }
            const int16Array = new Int16Array(bytes.buffer);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }

            const buffer = liveAudioCtx.createBuffer(1, float32Array.length, sampleRate);
            buffer.getChannelData(0).set(float32Array);

            const source = liveAudioCtx.createBufferSource();
            source.buffer = buffer;
            source.connect(liveAudioCtx.destination);

            const currentTime = liveAudioCtx.currentTime;
            // When starting a new speech burst or after an underrun, anchor ahead by JITTER_BUFFER_SEC
            if (nextAudioStartTime < currentTime) {
                nextAudioStartTime = currentTime + JITTER_BUFFER_SEC;
            }
            source.start(nextAudioStartTime);
            nextAudioStartTime += buffer.duration;

            isAISpeaking = true;
            isPlayingPCM24 = true;
            setLiveLampState("speaking");

            if (pcm24EndTimer) clearTimeout(pcm24EndTimer);
            pcm24EndTimer = setTimeout(() => {
                isAISpeaking = false;
                isPlayingPCM24 = false;
                setLiveLampState("idle");
                setAvatarState("idle");
                if (statusText && !isModalOpen) statusText.textContent = "お話しする準備ができました";
            }, Math.max(200, (nextAudioStartTime - currentTime) * 1000 + 200));

            setAvatarState("speaking");
            if (statusText && !isModalOpen) statusText.textContent = "Gemini Live と対話中...";

            if (aiResponseBox && (!aiResponseBox.textContent || aiResponseBox.textContent.includes("表示されます") || aiResponseBox.textContent.includes("待っています"))) {
                aiResponseBox.textContent = "🔊 リアルタイム音声でお返答中...";
            }
        } catch (e) {
            console.error("PCM24 playback error:", e);
        }
    }

    function playTTSVoice(text) {
        if (!text || !window.speechSynthesis) return;
        window.speechSynthesis.cancel();

        isAISpeaking = true;
        isTTSAnnouncing = true;
        setLiveLampState("speaking");
        setAvatarState("speaking");

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "ja-JP";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onend = () => {
            // Keep microphone completely muted for 1000ms after TTS to eliminate room reverberation echo
            setTimeout(() => {
                isAISpeaking = false;
                isTTSAnnouncing = false;
                if (!isModalOpen) {
                    setLiveLampState("idle");
                    setAvatarState("idle");
                    if (statusText) statusText.textContent = "お話しする準備ができました";
                }
            }, 1000);
        };

        utterance.onerror = () => {
            isAISpeaking = false;
            isTTSAnnouncing = false;
            if (!isModalOpen) {
                setLiveLampState("idle");
                setAvatarState("idle");
            }
        };

        window.speechSynthesis.speak(utterance);
    }

    function float32ToInt16Base64(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        const bytes = new Uint8Array(int16Array.buffer);
        let binary = "";
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    function handlePIIWarning(message) {
        console.warn("PII Warning received:", message);
        isModalOpen = true;
        currentUtteranceText = "";
        stopLiveAudioPlayback();
        if (piiWarningOverlay) {
            if (piiWarningText) piiWarningText.textContent = message || "個人情報保護のため会話を一時停止しました。";
            piiWarningOverlay.classList.remove("hidden");
            piiWarningOverlay.style.display = "flex";
        }
        setAvatarState("idle");
        statusText.textContent = "⚠️ プライバシー保護による一時停止中";
        playTTSVoice("個人情報保護のため、会話を一時停止しました。個人情報は話さないようお願いいたします。");
    }

    if (resumePiiBtn) {
        resumePiiBtn.addEventListener("click", () => {
            isModalOpen = false;
            currentUtteranceText = "";
            if (piiWarningOverlay) {
                piiWarningOverlay.classList.add("hidden");
                piiWarningOverlay.style.display = "none";
            }
            if (liveAudioCtx && liveAudioCtx.state === "suspended") {
                liveAudioCtx.resume();
            }
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify({ type: "resume_live_session" }));
            }
            statusText.textContent = "お話しする準備ができました";
        });
    }

    // Dialogue Interaction (Full-Duplex Gemini Live Streaming)
    micBtn.addEventListener("click", toggleDialogueRecording);

    let chunkAccumulator = [];
    let lastChunkSendTime = 0;

    let waveformAnimId = null;

    function startWaveformVisualizer(analyser) {
        const canvas = document.getElementById("waveform-canvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        function syncCanvasSize() {
            if (canvas.clientWidth && canvas.clientHeight) {
                if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
                    canvas.width = canvas.clientWidth;
                    canvas.height = canvas.clientHeight;
                }
            }
        }
        syncCanvasSize();
        
        if (waveformAnimId) {
            cancelAnimationFrame(waveformAnimId);
            waveformAnimId = null;
        }

        function draw() {
            syncCanvasSize();
            if (!isRecording) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.strokeStyle = "#cbd5e1";
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(0, canvas.height / 2);
                ctx.lineTo(canvas.width, canvas.height / 2);
                ctx.stroke();
                return;
            }
            waveformAnimId = requestAnimationFrame(draw);

            if (!analyser) return;
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.2;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const val = dataArray[i];
                const percent = val / 255;
                const barHeight = Math.max(4, percent * canvas.height * 0.85);

                const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
                gradient.addColorStop(0, "#10b981");
                gradient.addColorStop(1, "#34d399");

                ctx.fillStyle = gradient;
                ctx.beginPath();
                if (ctx.roundRect) {
                    ctx.roundRect(x, (canvas.height - barHeight) / 2, Math.max(2, barWidth - 3), barHeight, 4);
                } else {
                    ctx.rect(x, (canvas.height - barHeight) / 2, Math.max(2, barWidth - 3), barHeight);
                }
                ctx.fill();

                x += barWidth;
            }
        }
        draw();
    }

    micBtn.addEventListener("click", toggleDialogueRecording);

    async function toggleDialogueRecording() {
        console.log("toggleDialogueRecording called. isRecording:", isRecording);
        if (isRecording) {
            isRecording = false;
            if (recorder) {
                recorder.stop();
            }
            if (speechRec) {
                try { speechRec.stop(); } catch(e){}
            }
            if (activeAudio) {
                activeAudio.pause();
                activeAudio = null;
            }
            chunkAccumulator = [];
            startWaveformVisualizer(null);
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "stop_bidi_stream" }));
            }

            micBtn.classList.remove("recording", "full-duplex-on");
            statusText.textContent = "お話しする準備ができました";
            guideText.textContent = "ボタンを１回押して、お話ししてください";
            setAvatarState("idle");
        } else {
            if (activeAudio) {
                activeAudio.pause();
                activeAudio = null;
            }
            
            try {
                isRecording = true;
                
                // Ensure Gemini Live WebSocket is active
                if (!liveWs || liveWs.readyState !== WebSocket.OPEN) {
                    connectLiveWS();
                }

                if (speechRec) {
                    try { speechRec.start(); } catch(e){}
                }

                let vadSilenceFrames = 0;
                let isSpeakingUtterance = false;
                let voiceHangoverFrames = 0;
                let preSpeechRingBuffer = []; // ring buffer of last 3 chunks (~150ms) to preserve initial consonants
                const NOISE_GATE_THRESHOLD = 0.0075; // Cut off mic hiss, room fan, air conditioner, rustling

                recorder.onChunkCallback = (resampledChunk) => {
                    // Mute microphone completely when AI is speaking, modal is open, or system is announcing
                    if (isPlayingPCM24 || isAISpeaking || isModalOpen || isTTSAnnouncing) {
                        preSpeechRingBuffer = [];
                        voiceHangoverFrames = 0;
                        return;
                    }

                    // 1. Calculate instant RMS volume of mic input
                    let sum = 0;
                    for (let i = 0; i < resampledChunk.length; i++) {
                        sum += resampledChunk[i] * resampledChunk[i];
                    }
                    const rms = Math.sqrt(sum / resampledChunk.length);

                    // 2. Hardware-level instant VAD with noise-gate
                    const speechThreshold = (currentLampState === "thinking") ? 0.016 : NOISE_GATE_THRESHOLD;
                    const isVoiceActive = rms > speechThreshold || window.isSpeechRecActive;
                    const b64Pcm = float32ToInt16Base64(resampledChunk);

                    if (isVoiceActive) {
                        // User started speaking or is actively speaking
                        if (voiceHangoverFrames <= 0 && preSpeechRingBuffer.length > 0) {
                            // Flush pre-speech buffer so leading consonants are intact
                            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                                for (const preChunk of preSpeechRingBuffer) {
                                    liveWs.send(JSON.stringify({
                                        type: "live_pcm_chunk",
                                        data: preChunk
                                    }));
                                }
                            }
                            preSpeechRingBuffer = [];
                        }

                        voiceHangoverFrames = 8; // ~400ms hangover to cover inter-syllable micro-pauses
                        isSpeakingUtterance = true;
                        vadSilenceFrames = 0;

                        if (currentLampState !== "thinking" || rms > 0.018) {
                            setLiveLampState("sending");
                        }

                        // Stream active voice chunk to Gemini Live
                        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                            liveWs.send(JSON.stringify({
                                type: "live_pcm_chunk",
                                data: b64Pcm
                            }));
                        }
                    } else if (voiceHangoverFrames > 0) {
                        // Trailing speech hangover window: stream chunk to avoid cutting word endings
                        voiceHangoverFrames--;
                        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                            liveWs.send(JSON.stringify({
                                type: "live_pcm_chunk",
                                data: b64Pcm
                            }));
                        }
                    } else {
                        // Below noise floor: DO NOT SEND to Gemini Live! (Room noise completely blocked)
                        // Store in pre-speech ring buffer (keep last 3 chunks = ~150ms)
                        preSpeechRingBuffer.push(b64Pcm);
                        if (preSpeechRingBuffer.length > 3) {
                            preSpeechRingBuffer.shift();
                        }

                        if (isSpeakingUtterance) {
                            vadSilenceFrames++;
                            // ~600ms of true silence (~12 frames of 50ms) for natural Japanese pause detection
                            if (vadSilenceFrames >= 12) {
                                isSpeakingUtterance = false;
                                window.isSpeechRecActive = false;
                                vadSilenceFrames = 0;
                                setLiveLampState("thinking");
                                const cleanText = (currentUtteranceText || "").trim();
                                const isEcho = SYSTEM_ECHO_KEYWORDS.some(k => cleanText.includes(k));
                                if (cleanText && !isEcho) {
                                    if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                                        console.log("[Mic VAD] Speech concluded. Sending EOS with text:", cleanText);
                                        liveWs.send(JSON.stringify({ type: "eos", text: cleanText }));
                                    }
                                } else {
                                    console.log("[Mic VAD] Audio pause detected. Gemini server-side VAD handles turn completion.");
                                }
                                currentUtteranceText = "";
                            }
                        }
                    }
                };

                await recorder.start();
                startWaveformVisualizer(recorder.analyser);
                micBtn.classList.add("recording", "full-duplex-on");
                setAvatarState("listening");
                statusText.textContent = "⚡ Gemini Live ネイティブリアルタイム接続中 (お話しください)";
                guideText.textContent = "トークボタンはONのままです（終了するにはもう1回押します）";
                if (userSpeechBox) userSpeechBox.textContent = "マイク音声がリアルタイムでGemini Liveへ直ストリーミングされています...";
                if (aiResponseBox) aiResponseBox.textContent = "Gemini Liveのネイティブ音声応答を待っています...";
            } catch (err) {
                statusText.textContent = "マイクが使えません";
                console.error("Microphone start error:", err);
            }
        }
    }

    function handleProcessingStatus(status, sttTime, llmTime) {
        if (status === "stt_start") {
            lampStt.className = "lamp-dot active-stt";
            lampLlm.className = "lamp-dot idle";
            lampTts.className = "lamp-dot idle";
        } else if (status === "llm_start") {
            lampStt.className = "lamp-dot idle";
            if (sttTime !== undefined && sttTime !== null) timeStt.textContent = parseFloat(sttTime).toFixed(2) + "秒";
            lampLlm.className = "lamp-dot active-llm";
            lampTts.className = "lamp-dot idle";
        } else if (status === "tts_start") {
            lampStt.className = "lamp-dot idle";
            lampLlm.className = "lamp-dot idle";
            if (llmTime !== undefined && llmTime !== null) timeLlm.textContent = parseFloat(llmTime).toFixed(2) + "秒";
            lampTts.className = "lamp-dot active-tts";
        }
    }

    function handleChatResponse(text, base64Audio, sttTime, llmTime, ttsTime) {
        // Finalize indicators if not done already
        lampStt.className = "lamp-dot idle";
        lampLlm.className = "lamp-dot idle";
        lampTts.className = "lamp-dot idle";
        
        if (sttTime !== undefined && sttTime !== null) timeStt.textContent = parseFloat(sttTime).toFixed(2) + "秒";
        if (llmTime !== undefined && llmTime !== null) timeLlm.textContent = parseFloat(llmTime).toFixed(2) + "秒";
        if (ttsTime !== undefined && ttsTime !== null) timeTts.textContent = parseFloat(ttsTime).toFixed(2) + "秒";

        if (aiResponseBox) aiResponseBox.textContent = text;
        if (subtitleBox) subtitleBox.textContent = text;
        statusText.textContent = "AIがお話し中...";
        setAvatarState("speaking");
        
        playBase64Audio(base64Audio, () => {
            // Callback when finished speaking (Full-Duplex retention)
            if (isRecording) {
                statusText.textContent = "全二重リアルタイム対話中 (お話しください)";
                setAvatarState("listening");
                guideText.textContent = "トークボタンはONのままです（終了するにはもう1回押します）";
            } else {
                statusText.textContent = "お話しする準備ができました";
                setAvatarState("idle");
                guideText.textContent = "ボタンを１回押して、お話ししてください";
            }
        });
    }

    function handleStaffOverride(text, base64Audio) {
        subtitleBox.textContent = `スタッフ: "${text}"`;
        statusText.textContent = "スタッフからの連絡中...";
        setAvatarState("speaking");
        
        playBase64Audio(base64Audio, () => {
            if (isRecording) {
                statusText.textContent = "全二重リアルタイム対話中 (お話しください)";
                setAvatarState("listening");
            } else {
                statusText.textContent = "お話しする準備ができました";
                setAvatarState("idle");
            }
        });
    }

    function playBase64Audio(base64Data, onEnded) {
        if (activeAudio) {
            activeAudio.pause();
        }
        
        activeAudio = new Audio("data:audio/mp3;base64," + base64Data);
        activeAudio.onended = () => {
            activeAudio = null;
            if (onEnded) onEnded();
        };
        activeAudio.onerror = (e) => {
            console.error("Audio playback error:", e);
            activeAudio = null;
            if (onEnded) onEnded();
        };
        activeAudio.play().catch(err => {
            console.error("Audio play blocked/failed:", err);
            activeAudio = null;
            if (onEnded) onEnded();
        });
    }

    function handleStaffOverride(text, base64Audio) {
        subtitleBox.textContent = `スタッフ: "${text}"`;
        statusText.textContent = "スタッフからの連絡中...";
        setAvatarState("speaking");
        
        playBase64Audio(base64Audio, () => {
            statusText.textContent = "お話しする準備ができました";
            setAvatarState("idle");
        });
    }

    function playBase64Audio(base64Data, onEnded) {
        if (activeAudio) {
            activeAudio.pause();
        }
        
        // standard HTML5 audio playback from base64
        activeAudio = new Audio("data:audio/mp3;base64," + base64Data);
        activeAudio.onended = () => {
            activeAudio = null;
            if (onEnded) onEnded();
        };
        activeAudio.onerror = (e) => {
            console.error("Audio playback error:", e);
            if (onEnded) onEnded();
        };
        activeAudio.play().catch(err => {
            console.error("Audio play blocked/failed:", err);
            if (onEnded) onEnded();
        });
    }

    // Intercom (Pattern A) - Calling functions
    function clearAutoAnswerTimers() {
        stopIncomingChimeLoop();
        if (autoAnswerTimer) {
            clearTimeout(autoAnswerTimer);
            autoAnswerTimer = null;
        }
        if (autoAnswerCountdownTimer) {
            clearInterval(autoAnswerCountdownTimer);
            autoAnswerCountdownTimer = null;
        }
    }

    function handleIncomingCall(callData = {}) {
        clearAutoAnswerTimers();
        intercomOverlay.classList.remove("hidden");
        if (callCard) callCard.classList.remove("in-call");
        
        const callerName = callData.caller || "スタッフステーション";
        const callerType = callData.caller_type || "staff";
        const autoAnswer = callData.auto_answer !== false; // default true if not specified
        let remainingSeconds = (typeof callData.auto_delay === "number") ? callData.auto_delay : 15;
        const isForce = !!callData.force_mode;

        // Start 5-second interval incoming chime loop (immediate 1st chime + repeat every 5s)
        startIncomingChimeLoop(isForce, callerType);
        reportTerminalStatus("intercom");

        if (callerType === "family") {
            if (callCard) callCard.classList.add("family-call");
        } else {
            if (callCard) callCard.classList.remove("family-call");
        }

        if (isForce) {
            // Emergency force answer mode (Red border pulse, warning banner)
            if (callCard) callCard.classList.add("emergency-force");
            if (forceCallBanner) forceCallBanner.classList.remove("hidden");

            callStatus.textContent = `${callerName}から緊急呼出`;
            callSubstatus.textContent = "自動でハンズフリー通話を開始します...";
            answerBtn.classList.add("hidden");
            answerBtn.style.display = "none";
            hangupBtn.classList.remove("hidden");

            // Short chime preview delay (800ms) before opening microphone stream
            autoAnswerTimer = setTimeout(() => {
                if (intercomOverlay.classList.contains("hidden")) return; // Call canceled
                startIntercomSession();
            }, 800);
            return;
        }

        // Standard Call Mode
        if (callCard) callCard.classList.remove("emergency-force");
        if (forceCallBanner) {
            forceCallBanner.classList.add("hidden");
            forceCallBanner.textContent = "";
        }
        
        if (callerType === "family") {
            callStatus.textContent = `📞 ${callerName}からお電話です`;
        } else {
            callStatus.textContent = `📞 ${callerName}から呼び出し中...`;
        }

        answerBtn.classList.remove("hidden");
        answerBtn.style.display = "";
        answerBtn.textContent = "📞 でる";
        hangupBtn.classList.remove("hidden");
        hangupBtn.style.display = "";

        if (autoAnswer) {
            // Hands-free Auto Answer Mode
            if (remainingSeconds <= 0) {
                callSubstatus.textContent = "自動で通話を開始します...";
                startIntercomSession();
            } else {
                callSubstatus.textContent = `（約${remainingSeconds}秒後に自動でつながります）`;
                autoAnswerCountdownTimer = setInterval(() => {
                    remainingSeconds--;
                    if (remainingSeconds > 0) {
                        callSubstatus.textContent = `（約${remainingSeconds}秒後に自動でつながります）`;
                    } else {
                        callSubstatus.textContent = "自動で通話を開始します...";
                        clearAutoAnswerTimers();
                        if (intercomOverlay.classList.contains("hidden")) return; // Call canceled
                        startIntercomSession();
                    }
                }, 1000);
            }
        } else {
            // Manual Answer Mode (Resident must tap 'でる')
            callSubstatus.textContent = "「でる」ボタンを押してお話しください";
        }
    }

    let isRecordingIntercom = false;

    async function startIntercomSession() {
        clearAutoAnswerTimers();
        stopIncomingChimeLoop();
        isCallActive = true;
        isRecordingIntercom = true;
        reportTerminalStatus("intercom");
        callStatus.textContent = "通話中...";
        callSubstatus.textContent = "お話しいただけます";

        // Strictly mark callCard as in-call and hide answer button
        if (callCard) callCard.classList.add("in-call");
        answerBtn.classList.add("hidden");
        answerBtn.style.display = "none";
        hangupBtn.classList.remove("hidden");
        hangupBtn.style.display = "";
        audioQueue = [];
        isPlayingQueue = false;

        // Notify server that room resident answered the call
        console.log("[User Intercom] Resident answered call. Sending call_answer to server...");
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "call_answer" }));
        } else {
            console.warn("[User Intercom] WS was not open when answering call. Reconnecting WS...");
            connectWebSocket();
            setTimeout(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "call_answer" }));
                    console.log("[User Intercom] call_answer sent after WS reconnect");
                }
            }, 400);
        }

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error("getUserMedia not supported in this context");
            }

            // Get microphone stream for intercom (low latency chunks)
            intercomStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true }
            });

            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
                           : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';

            // Self-contained independent audio slice recorder (each slice has valid container headers)
            function recordNextSlice() {
                if (!isCallActive || !isRecordingIntercom || !intercomStream) return;
                try {
                    const rec = new MediaRecorder(intercomStream, { mimeType });
                    rec.ondataavailable = async (e) => {
                        if (e.data && e.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                            const reader = new FileReader();
                            reader.readAsDataURL(e.data);
                            reader.onloadend = () => {
                                const base64Chunk = reader.result.split(',')[1];
                                ws.send(JSON.stringify({
                                    type: "audio_stream",
                                    audio: base64Chunk
                                }));
                            };
                        }
                    };
                    rec.start();
                    setTimeout(() => {
                        if (rec.state !== "inactive") {
                            try { rec.stop(); } catch(err) {}
                        }
                        if (isCallActive && isRecordingIntercom) {
                            recordNextSlice();
                        }
                    }, 500);
                } catch (recErr) {
                    console.error("Intercom slice recorder failed:", recErr);
                }
            }

            recordNextSlice();
            console.log("Intercom voice streaming started (header-valid slicing)...");

        } catch (err) {
            console.warn("Intercom mic stream not available or denied:", err);
            callStatus.textContent = "相手の声を受信中";
            callSubstatus.textContent = "（相手の声を聞くことができます）";
            // Do NOT drop call - allow resident to hear family/staff voice
        }
    }

    function playIntercomChunk(base64Chunk) {
        if (!base64Chunk || !isCallActive) return; // Do not play incoming audio before answering
        audioQueue.push("data:audio/webm;base64," + base64Chunk);
        // Prevent queue backlog to keep low latency
        if (audioQueue.length > 6) {
            audioQueue.splice(0, audioQueue.length - 4);
        }
        if (!isPlayingQueue) {
            playNextQueueItem();
        }
    }

    function playNextQueueItem() {
        if (audioQueue.length === 0) {
            isPlayingQueue = false;
            return;
        }

        isPlayingQueue = true;
        const nextSrc = audioQueue.shift();
        const aud = new Audio(nextSrc);
        aud.onended = playNextQueueItem;
        aud.onerror = () => {
            console.warn("Intercom chunk play skipped");
            playNextQueueItem();
        };
        aud.play().catch(err => {
            console.warn("Intercom chunk play blocked:", err);
            playNextQueueItem();
        });
    }

    function endIntercomCall(notifyServer = true) {
        clearAutoAnswerTimers();
        stopIncomingChimeLoop();
        isRecordingIntercom = false;
        const wasRingingOrActive = isCallActive || !intercomOverlay.classList.contains("hidden");
        if (!wasRingingOrActive) return;
        isCallActive = false;
        
        console.log("Ending intercom call...");
        
        // Stop microphone streaming
        if (intercomRecorder && intercomRecorder.state !== "inactive") {
            intercomRecorder.stop();
        }
        if (intercomStream) {
            intercomStream.getTracks().forEach(track => track.stop());
            intercomStream = null;
        }

        if (callCard) {
            callCard.classList.remove("emergency-force");
            callCard.classList.remove("family-call");
            callCard.classList.remove("in-call");
        }
        if (forceCallBanner) forceCallBanner.classList.add("hidden");

        intercomOverlay.classList.add("hidden");
        answerBtn.classList.add("hidden");
        answerBtn.style.display = "none";
        callSubstatus.textContent = "";
        
        if (notifyServer && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "hangup" }));
        }

        reportTerminalStatus("idle");

        statusText.textContent = "お話しする準備ができました";
        setAvatarState("idle");
    }

    function handleAnswerClick(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (isCallActive) return;
        console.log("[User] Resident pressed answer button");
        clearAutoAnswerTimers();
        startIntercomSession();
    }

    answerBtn.addEventListener("click", handleAnswerClick);
    answerBtn.addEventListener("touchend", handleAnswerClick);

    function handleHangupClick(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        console.log("[User] Resident pressed hangup button");
        endIntercomCall(true);
    }

    hangupBtn.addEventListener("click", handleHangupClick);
    hangupBtn.addEventListener("touchend", handleHangupClick);

    // Helper functions
    function setAvatarState(state) {
        aiAvatar.className = `avatar-circle ${state}`;
        if (!isCallActive && intercomOverlay && intercomOverlay.classList.contains("hidden")) {
            if (state === "speaking" || state === "thinking" || state === "listening") {
                reportTerminalStatus("chatting");
            } else if (state === "idle") {
                reportTerminalStatus("idle");
            }
        }
    }

    retryBtn.addEventListener("click", () => {
        checkRegistration();
        connectWS();
    });

    // Initialize application connection
    async function initApp() {
        try {
            await checkSystemInfo();
            updateDebugUI();
            await checkRegistration();
            connectWS();
            if (isDebugMode) {
                connectLiveWS();
            }
        } catch (e) {
            console.error("App init error:", e);
        }
    }
    initApp();
});
