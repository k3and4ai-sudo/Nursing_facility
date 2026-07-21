// main application logic for user client
document.addEventListener("DOMContentLoaded", () => {
    let terminalId = localStorage.getItem("nursing_terminal_id");
    if (!terminalId) {
        // Generate random terminal ID
        terminalId = "user_tablet_" + Math.floor(1000 + Math.random() * 9000);
        localStorage.setItem("nursing_terminal_id", terminalId);
    }
    
    // UI Elements
    const roomBadge = document.getElementById("room-badge");
    const connectionStatus = document.getElementById("connection-status");
    const aiAvatar = document.getElementById("ai-avatar");
    const statusText = document.getElementById("status-text");
    const micBtn = document.getElementById("mic-btn");
    const guideText = document.getElementById("guide-text");
    const subtitleBox = document.getElementById("subtitle-box");
    
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
                case "chat_response":
                    handleChatResponse(data.text, data.audio);
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

    // Dialogue Interaction
    micBtn.addEventListener("click", toggleDialogueRecording);

    async function toggleDialogueRecording() {
        if (isRecording) {
            // Stop recording and send
            isRecording = false;
            micBtn.classList.remove("recording");
            setAvatarState("thinking");
            statusText.textContent = "考えています...";
            guideText.textContent = "少々お待ちください";
            
            const audioBlob = recorder.stop();
            if (audioBlob) {
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64Audio = reader.result.split(',')[1];
                    ws.send(JSON.stringify({
                        type: "audio_input",
                        audio: base64Audio
                    }));
                };
            }
        } else {
            // Start recording
            // Stop any playing audio first
            if (activeAudio) {
                activeAudio.pause();
                activeAudio = null;
            }
            
            try {
                await recorder.start();
                isRecording = true;
                micBtn.classList.add("recording");
                setAvatarState("listening");
                statusText.textContent = "お話ししてください...";
                guideText.textContent = "話し終わったらもう一度ボタンを押してください";
                subtitleBox.textContent = "";
            } catch (err) {
                statusText.textContent = "マイクが使えません";
                console.error(err);
            }
        }
    }

    function handleChatResponse(text, base64Audio) {
        subtitleBox.textContent = text;
        statusText.textContent = "お話し中...";
        setAvatarState("speaking");
        
        playBase64Audio(base64Audio, () => {
            // Callback when finished speaking
            statusText.textContent = "お話しする準備ができました";
            setAvatarState("idle");
            guideText.textContent = "ボタンを１回押して、お話ししてください";
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
    connectWS();
});
