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
    const debugBadge = document.getElementById("debug-badge");
    const connectionStatus = document.getElementById("connection-status");
    const aiAvatar = document.getElementById("ai-avatar");
    const statusText = document.getElementById("status-text");
    const micBtn = document.getElementById("mic-btn");
    const guideText = document.getElementById("guide-text");
    const subtitleBox = document.getElementById("subtitle-box");
    const userSpeechBox = document.getElementById("user-speech-box");
    const aiResponseBox = document.getElementById("ai-response-box");

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

    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
        const SpeechRecClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        speechRec = new SpeechRecClass();
        speechRec.continuous = true;
        speechRec.interimResults = true;
        speechRec.lang = "ja-JP";

        speechRec.onresult = (event) => {
            // Ignore microphone input while AI is speaking (prevents speaker echo feedback loop)
            if (isAISpeaking || isPlayingPCM24) {
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
            if (clean && userSpeechBox) {
                userSpeechBox.textContent = clean;
                currentUtteranceText = clean;
                setLiveLampState("sending");

                if (speechDebounceTimer) clearTimeout(speechDebounceTimer);
                speechDebounceTimer = setTimeout(() => {
                    if (!isAISpeaking && !isPlayingPCM24 && currentUtteranceText && currentUtteranceText !== lastSentSpeechText) {
                        lastSentSpeechText = currentUtteranceText;
                        const textToSend = currentUtteranceText;
                        currentUtteranceText = "";
                        setLiveLampState("thinking");
                        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                            console.log("[SpeechRec] Sending EOS text to Gemini Live:", textToSend);
                            liveWs.send(JSON.stringify({ type: "eos", text: textToSend }));
                        }
                    }
                }, 300);
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
    const callStatus = document.getElementById("call-status");
    const hangupBtn = document.getElementById("hangup-btn");

    // Audio Elements
    let activeAudio = null;
    const recorder = new WavAudioRecorder();
    let isRecording = false;

    // Intercom / Calling Variables
    let intercomStream = null;
    let intercomRecorder = null;
    let isCallActive = false;
    let audioQueue = [];
    let isPlayingQueue = false;

    // WebSocket Reference
    let ws = null;
    let userDetails = null;

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

                case "incoming_call": // Intercom Call requested (Pattern A)
                    handleIncomingCall();
                    break;

                case "intercom_audio": // Intercom incoming audio chunks
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
                        playTTSVoice(data.text);
                    }
                    setLiveLampState("speaking");
                    setAvatarState("speaking");
                }
            } else if (data.type === "transcription_result") {
                if (userSpeechBox && data.text) {
                    userSpeechBox.textContent = data.text;
                }
            } else if (data.type === "chat_response") {
                if (userSpeechBox && data.user_text) userSpeechBox.textContent = data.user_text;
                if (aiResponseBox && data.text) aiResponseBox.textContent = data.text;
                if (data.audio) playBase64Audio(data.audio);
            } else if (data.type === "pii_warning") {
                handlePIIWarning(data.message);
            }
        };

        liveWs.onclose = () => {
            console.log("Gemini Live WS disconnected");
            setTimeout(connectLiveWS, 3000);
        };
    }

    const lampSending = document.getElementById("lamp-sending");
    const lampThinking = document.getElementById("lamp-thinking");
    const lampSpeaking = document.getElementById("lamp-speaking");

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

        if (state === "sending" && lampSending) {
            lampSending.classList.add("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
            silenceTimeout = setTimeout(() => {
                if (lampSending) lampSending.classList.remove("lamp-active");
            }, 600);
        } else if (state === "thinking" && lampThinking) {
            lampThinking.classList.add("lamp-active");
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
            thinkingTimeoutTimer = setTimeout(() => {
                if (lampThinking) lampThinking.classList.remove("lamp-active");
                setAvatarState("idle");
                if (statusText) statusText.textContent = "お話しする準備ができました";
            }, 4000);
        } else if (state === "speaking" && lampSpeaking) {
            lampSpeaking.classList.add("lamp-active");
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
        } else if (state === "idle") {
            if (lampSending) lampSending.classList.remove("lamp-active");
            if (lampThinking) lampThinking.classList.remove("lamp-active");
            if (lampSpeaking) lampSpeaking.classList.remove("lamp-active");
        }
    }

    let nextAudioStartTime = 0;
    let isPlayingPCM24 = false;
    let pcm24EndTimer = null;

    function playPCM24Chunk(base64Data, sampleRate) {
        if (!liveAudioCtx) {
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
            if (nextAudioStartTime < currentTime) {
                nextAudioStartTime = currentTime + 0.02;
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
                if (statusText) statusText.textContent = "お話しする準備ができました";
            }, (nextAudioStartTime - currentTime) * 1000 + 300);

            setAvatarState("speaking");
            statusText.textContent = "Gemini Live と対話中...";

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
        setLiveLampState("speaking");
        setAvatarState("speaking");

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "ja-JP";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onend = () => {
            setTimeout(() => {
                isAISpeaking = false;
                setLiveLampState("idle");
                setAvatarState("idle");
                if (statusText) statusText.textContent = "お話しする準備ができました";
            }, 300);
        };

        utterance.onerror = () => {
            isAISpeaking = false;
            setLiveLampState("idle");
            setAvatarState("idle");
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
        if (liveAudioCtx) {
            liveAudioCtx.suspend();
        }
        if (piiWarningOverlay) {
            if (piiWarningText) piiWarningText.textContent = message || "個人情報保護のため会話を一時停止しました。";
            piiWarningOverlay.classList.remove("hidden");
        }
        setAvatarState("idle");
        statusText.textContent = "⚠️ プライバシー保護による一時停止中";
        playTTSVoice("個人情報保護のため、会話を一時停止しました。個人情報は話さないようお願いいたします。");
    }

    if (resumePiiBtn) {
        resumePiiBtn.addEventListener("click", () => {
            if (piiWarningOverlay) piiWarningOverlay.classList.add("hidden");
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
        
        if (waveformAnimId) {
            cancelAnimationFrame(waveformAnimId);
            waveformAnimId = null;
        }

        function draw() {
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
                let speechChunkCount = 0;
                let lastSentSpeechText = "";

                recorder.onChunkCallback = (resampledChunk) => {
                    // Mute mic streaming while Gemini AI is actively speaking back to avoid feedback loop
                    if (isPlayingPCM24) {
                        return;
                    }

                    if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                        // Unconditionally stream raw PCM audio chunks to Gemini Live while microphone is active
                        const b64Pcm = float32ToInt16Base64(resampledChunk);
                        liveWs.send(JSON.stringify({
                            type: "live_pcm_chunk",
                            data: b64Pcm
                        }));
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
    function handleIncomingCall() {
        intercomOverlay.classList.remove("hidden");
        callStatus.textContent = "スタッフから呼び出し中...";
        
        // Auto-answer after 2 seconds for hands-free elderly usage
        setTimeout(() => {
            if (intercomOverlay.classList.contains("hidden")) return; // Call canceled
            startIntercomSession();
        }, 2000);
    }

    async function startIntercomSession() {
        isCallActive = true;
        callStatus.textContent = "通話中...";
        audioQueue = [];
        isPlayingQueue = false;

        try {
            // Get microphone stream for intercom (low latency chunks)
            intercomStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true }
            });

            // MediaRecorder for streaming
            // We use standard container. Browser will record audio chunks.
            const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
            intercomRecorder = new MediaRecorder(intercomStream, { mimeType });
            
            intercomRecorder.ondataavailable = async (e) => {
                if (e.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
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

            // Stream chunks every 250ms
            intercomRecorder.start(250);
            console.log("Intercom streaming started...");

        } catch (err) {
            console.error("Failed to start intercom mic stream:", err);
            callStatus.textContent = "マイク接続に失敗しました";
            setTimeout(() => endIntercomCall(true), 2000);
        }
    }

    function playIntercomChunk(base64Chunk) {
        // Enqueue incoming staff voice chunks and play them sequentially
        audioQueue.push("data:audio/webm;base64," + base64Chunk);
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
        aud.onerror = playNextQueueItem; // skip if error
        aud.play().catch(err => {
            console.warn("Queue play blocked:", err);
            playNextQueueItem();
        });
    }

    function endIntercomCall(notifyServer = true) {
        if (!isCallActive) return;
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

        intercomOverlay.classList.add("hidden");
        
        if (notifyServer && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "hangup" }));
        }

        statusText.textContent = "お話しする準備ができました";
        setAvatarState("idle");
    }

    hangupBtn.addEventListener("click", () => {
        endIntercomCall(true);
    });

    // Helper functions
    function setAvatarState(state) {
        aiAvatar.className = `avatar-circle ${state}`;
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
