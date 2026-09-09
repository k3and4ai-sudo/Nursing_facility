// Care-Link Unified Application Router & Mode Manager
document.addEventListener("DOMContentLoaded", () => {
    // Session State
    let currentUser = null;
    let ws = null;

    // UI Elements - Login
    const loginOverlay = document.getElementById("login-overlay");
    const loginForm = document.getElementById("login-form");
    const userCodeInput = document.getElementById("user-code");
    const userPassInput = document.getElementById("user-pass");
    const loginError = document.getElementById("login-error");
    const demoButtons = document.querySelectorAll(".btn-demo");

    // UI Elements - Navigation & Shell
    const appWrapper = document.getElementById("app-wrapper");
    const roleBadge = document.getElementById("role-badge");
    const userDisplayName = document.getElementById("user-display-name");
    const logoutBtn = document.getElementById("logout-btn");
    const modeViews = document.querySelectorAll(".mode-view");

    // Patient Mode UI Elements
    const pStatusBadge = document.getElementById("p-status-badge");
    const pMicBtn = document.getElementById("p-mic-btn");
    const pStatusText = document.getElementById("p-status-text");
    const pGuideText = document.getElementById("p-guide-text");
    const pSubtitleBox = document.getElementById("p-subtitle-box");
    const pAiAvatar = document.getElementById("p-ai-avatar");
    const pWaveformCanvas = document.getElementById("p-waveform-canvas");
    const pUserSpeechBox = document.getElementById("p-user-speech-box");
    const pUserSpeechText = document.getElementById("p-user-speech-text");
    
    // Processing Status elements
    const pProcessingIndicator = document.getElementById("p-processing-indicator");
    const pLampStt = document.getElementById("p-lamp-stt");
    const pLampLlm = document.getElementById("p-lamp-llm");
    const pLampTts = document.getElementById("p-lamp-tts");
    const pTimeStt = document.getElementById("p-time-stt");
    const pTimeLlm = document.getElementById("p-time-llm");
    const pTimeTts = document.getElementById("p-time-tts");
    
    // Audio Recorder & Canvas Animation
    let recorder = null;
    let isRecording = false;
    let activeAudio = null;
    let waveformAnimFrame = null;
    const canvasCtx = pWaveformCanvas ? pWaveformCanvas.getContext("2d") : null;

    // UI Elements - Server Status
    const statusFrontend = document.getElementById("status-frontend");
    const statusBackend = document.getElementById("status-backend");
    const addressFrontend = document.getElementById("address-frontend");
    const addressBackend = document.getElementById("address-backend");

    async function checkServerHealth() {
        // Dynamic Address Update
        if (addressFrontend) {
            addressFrontend.textContent = window.location.origin || "http://localhost:8080";
        }
        if (addressBackend) {
            // Default backend API location is http://localhost:8000
            const backendOrigin = window.location.port === "8000" ? window.location.origin : "http://localhost:8000";
            addressBackend.textContent = backendOrigin;
        }

        // Frontend Check: Browser parsed HTML & JS, so Web server is active
        if (statusFrontend) {
            statusFrontend.className = "status-pill status-online";
            statusFrontend.textContent = "🟢 起動中";
        }

        // Backend Check: Ping API endpoint
        if (statusBackend) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);
                const res = await fetch("/api/users", { method: "GET", cache: "no-store", signal: controller.signal });
                clearTimeout(timeoutId);

                if (res.ok) {
                    statusBackend.className = "status-pill status-online";
                    statusBackend.textContent = "🟢 起動中";
                } else {
                    statusBackend.className = "status-pill status-offline";
                    statusBackend.textContent = "🔴 停止中";
                }
            } catch (err) {
                statusBackend.className = "status-pill status-offline";
                statusBackend.textContent = "🔴 停止中";
            }
        }

        // Fetch System Release Flags
        try {
            const infoRes = await fetch("/api/config/system_info");
            if (infoRes.ok) {
                const sysInfo = await infoRes.json();
                const dbDemoBtn = document.querySelector('.btn-demo[data-user="DB"]');
                if (dbDemoBtn) {
                    dbDemoBtn.style.display = sysInfo.enable_debug_mode ? "inline-flex" : "none";
                }
            }
        } catch (e) {}
    }

    // Run health check initially and periodically every 10s
    checkServerHealth();
    setInterval(checkServerHealth, 10000);

    // Restore Session if exists
    const savedSession = sessionStorage.getItem("care_link_session");
    if (savedSession) {
        currentUser = JSON.parse(savedSession);
        initMode(currentUser);
    }

    // Demo Buttons Quick Login
    demoButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            userCodeInput.value = btn.dataset.user;
            userPassInput.value = btn.dataset.pass;
            performLogin(btn.dataset.user, btn.dataset.pass);
        });
    });

    // Login Form Submit
    loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        performLogin(userCodeInput.value, userPassInput.value);
    });

    async function performLogin(userCode, password) {
        loginError.classList.add("hidden");
        if (userCode && userCode.toUpperCase() === "DB") {
            localStorage.setItem("nursing_debug_mode", "true");
            userCode = "patient01";
            password = "patient123";
        }
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_code: userCode, password })
            });

            if (!res.ok) {
                loginError.classList.remove("hidden");
                return;
            }

            const data = await res.json();
            currentUser = data;
            sessionStorage.setItem("care_link_session", JSON.stringify(currentUser));
            initMode(currentUser);

        } catch (err) {
            console.error("Login error:", err);
            loginError.textContent = "サーバーに接続できません";
            loginError.classList.remove("hidden");
        }
    }

    function initMode(user) {
        loginOverlay.classList.add("hidden");
        appWrapper.classList.remove("hidden");
        userDisplayName.textContent = user.name;

        // Hide all mode views
        modeViews.forEach(v => v.classList.add("hidden"));

        const roles = {
            patient: { label: "👴 利用者モード", target: "mode-patient", bg: "theme-light" },
            staff: { label: "👩‍⚕️ 介護スタッフモード", target: "mode-staff", bg: "theme-dark" },
            family: { label: "👨‍👩‍👧 ご家族モード", target: "mode-family", bg: "theme-dark" },
            barber: { label: "💈 訪問理容・美容師モード", target: "mode-barber", bg: "theme-dark" }
        };

        const config = roles[user.role] || roles.patient;
        roleBadge.textContent = config.label;
        document.body.className = config.bg;
        
        const targetView = document.getElementById(config.target);
        if (targetView) targetView.classList.remove("hidden");

        // Initialize specific mode features
        if (user.role === "patient") {
            initPatientMode(user);
        } else if (user.role === "staff") {
            initStaffMode(user);
        } else if (user.role === "family") {
            // Seamlessly redirect to dedicated family portal
            window.location.href = "/family/";
            return;
        } else if (user.role === "barber") {
            initBarberMode(user);
        }
    }

    // 1. PATIENT MODE LOGIC
    function initPatientMode(user) {
        const terminalId = user.terminal_id || "user_tablet_1";
        recorder = new WavAudioRecorder();

        function handlePatientProcessingStatus(status, sttTime, llmTime) {
            if (status === "stt_start") {
                pLampStt.className = "lamp-dot active-stt";
                pLampLlm.className = "lamp-dot idle";
                pLampTts.className = "lamp-dot idle";
            } else if (status === "llm_start") {
                pLampStt.className = "lamp-dot idle";
                if (sttTime !== undefined && sttTime !== null) pTimeStt.textContent = parseFloat(sttTime).toFixed(2) + "秒";
                pLampLlm.className = "lamp-dot active-llm";
                pLampTts.className = "lamp-dot idle";
            } else if (status === "tts_start") {
                pLampStt.className = "lamp-dot idle";
                pLampLlm.className = "lamp-dot idle";
                if (llmTime !== undefined && llmTime !== null) pTimeLlm.textContent = parseFloat(llmTime).toFixed(2) + "秒";
                pLampTts.className = "lamp-dot active-tts";
            }
        }
        
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/user/${terminalId}`);

        setPatientState("ready");

        ws.onopen = () => {
            setPatientState("ready");
            pMicBtn.disabled = false;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "processing_status") {
                handlePatientProcessingStatus(data.status, data.stt_time, data.llm_time);
            }
            else if (data.type === "transcription_result") {
                // Display user spoken transcription immediately
                pUserSpeechBox.classList.remove("hidden");
                pUserSpeechText.textContent = data.text;
            } 
            else if (data.type === "chat_response") {
                // Finalize indicators
                pLampStt.className = "lamp-dot idle";
                pLampLlm.className = "lamp-dot idle";
                pLampTts.className = "lamp-dot idle";
                
                if (data.stt_time !== undefined && data.stt_time !== null) pTimeStt.textContent = parseFloat(data.stt_time).toFixed(2) + "秒";
                if (data.llm_time !== undefined && data.llm_time !== null) pTimeLlm.textContent = parseFloat(data.llm_time).toFixed(2) + "秒";
                if (data.tts_time !== undefined && data.tts_time !== null) pTimeTts.textContent = parseFloat(data.tts_time).toFixed(2) + "秒";

                setPatientState("speaking");
                pSubtitleBox.textContent = data.text;
                
                if (activeAudio) activeAudio.pause();
                activeAudio = new Audio("data:audio/mp3;base64," + data.audio);
                activeAudio.onended = () => {
                    setPatientState("ready");
                };
                activeAudio.play().catch(e => console.warn(e));
            }
        };

        pMicBtn.onclick = async () => {
            if (isRecording) {
                isRecording = false;
                pMicBtn.classList.remove("recording");
                setPatientState("thinking");
                
                // Reset and Show status indicators
                pProcessingIndicator.classList.remove("hidden");
                pLampStt.className = "lamp-dot idle";
                pLampLlm.className = "lamp-dot idle";
                pLampTts.className = "lamp-dot idle";
                pTimeStt.textContent = "-";
                pTimeLlm.textContent = "-";
                pTimeTts.textContent = "-";
                
                const blob = recorder.stop();
                if (blob && ws && ws.readyState === WebSocket.OPEN) {
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        ws.send(JSON.stringify({
                            type: "audio_input",
                            audio: reader.result.split(',')[1]
                        }));
                    };
                }
            } else {
                try {
                    await recorder.start();
                    isRecording = true;
                    pMicBtn.classList.add("recording");
                    setPatientState("listening");
                } catch (err) {
                    console.error("Microphone access error:", err);
                    setPatientState("ready");
                    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                        pStatusText.textContent = "マイクが拒否されました（ブラウザのアドレスバー横で許可してください）";
                    } else if (err.message === "SECURITY_ORIGIN_ERROR") {
                        pStatusText.textContent = "http://localhost:8000 で接続してください（IPアドレス直接指定は制限されます）";
                    } else if (err.name === "NotFoundError") {
                        pStatusText.textContent = "マイク機器が見つかりません（マイクを接続してください）";
                    } else {
                        pStatusText.textContent = `マイクエラー: ${err.message || err.name || '接続不可'}`;
                    }
                }
            }
        };
    }

    function setPatientState(state) {
        if (!pStatusBadge) return;

        // Reset state classes
        pStatusBadge.className = "patient-status-badge";

        if (state === "ready") {
            pStatusBadge.classList.add("state-ready");
            pStatusBadge.textContent = "🟢 お話しできます";
            pStatusText.textContent = "お話しする準備ができました";
            pGuideText.textContent = "ボタンを１回押して、お話ししてください";
            pAiAvatar.className = "avatar-circle idle";
            if (pWaveformCanvas) pWaveformCanvas.classList.add("hidden");
            if (waveformAnimFrame) cancelAnimationFrame(waveformAnimFrame);
        } 
        else if (state === "listening") {
            pStatusBadge.classList.add("state-listening");
            pStatusBadge.textContent = "🎤 お声を聴いています...";
            pStatusText.textContent = "お話ししてください...";
            pGuideText.textContent = "話し終わったらもう一度ボタンを押してください";
            pAiAvatar.className = "avatar-circle listening";
            if (pWaveformCanvas) {
                pWaveformCanvas.classList.remove("hidden");
                drawOscilloscopeWaveform();
            }
        } 
        else if (state === "thinking") {
            pStatusBadge.classList.add("state-thinking");
            pStatusBadge.textContent = "🧠 AIが考えています...";
            pStatusText.textContent = "回答を考えています...";
            pGuideText.textContent = "少々お待ちください";
            pAiAvatar.className = "avatar-circle thinking";
            if (pWaveformCanvas) pWaveformCanvas.classList.add("hidden");
            if (waveformAnimFrame) cancelAnimationFrame(waveformAnimFrame);
        } 
        else if (state === "speaking") {
            pStatusBadge.classList.add("state-speaking");
            pStatusBadge.textContent = "🔊 AIがお話ししています...";
            pStatusText.textContent = "お話し中...";
            pGuideText.textContent = "じっくりお聴きください";
            pAiAvatar.className = "avatar-circle speaking";
            if (pWaveformCanvas) pWaveformCanvas.classList.add("hidden");
            if (waveformAnimFrame) cancelAnimationFrame(waveformAnimFrame);
        }
    }

    // Oscilloscope Waveform Animation Frame Loop
    let wavePhase = 0;
    function drawOscilloscopeWaveform() {
        if (!isRecording || !recorder || !canvasCtx) {
            if (waveformAnimFrame) cancelAnimationFrame(waveformAnimFrame);
            return;
        }

        waveformAnimFrame = requestAnimationFrame(drawOscilloscopeWaveform);

        const bufferLength = 256;
        const dataArray = new Uint8Array(bufferLength);
        if (recorder && typeof recorder.getWaveformData === "function") {
            recorder.getWaveformData(dataArray);
        } else {
            dataArray.fill(128);
        }

        // Fixed canvas resolution for rendering
        if (!pWaveformCanvas.width || pWaveformCanvas.width !== 360) {
            pWaveformCanvas.width = 360;
        }
        if (!pWaveformCanvas.height || pWaveformCanvas.height !== 80) {
            pWaveformCanvas.height = 80;
        }

        const width = 360;
        const height = 80;

        canvasCtx.fillStyle = "#0f172a";
        canvasCtx.fillRect(0, 0, width, height);

        // Draw grid lines for oscilloscope aesthetic
        canvasCtx.strokeStyle = "rgba(56, 189, 248, 0.15)";
        canvasCtx.lineWidth = 1;
        canvasCtx.beginPath();
        canvasCtx.moveTo(0, height / 2);
        canvasCtx.lineTo(width, height / 2);
        canvasCtx.stroke();

        // Calculate audio amplitude
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
            const sample = Math.abs(dataArray[i] - 128);
            sum += sample;
        }
        const avgAmplitude = sum / bufferLength;

        // Oscilloscope Wave path
        canvasCtx.lineWidth = 3;
        canvasCtx.strokeStyle = avgAmplitude > 2 ? "#38bdf8" : "#818cf8"; // Cyan when speaking, Indigo when background
        canvasCtx.shadowBlur = avgAmplitude > 2 ? 12 : 4;
        canvasCtx.shadowColor = avgAmplitude > 2 ? "#0284c7" : "#4f46e5";
        canvasCtx.beginPath();

        const sliceWidth = width * 1.0 / bufferLength;
        let x = 0;
        wavePhase += 0.15;
        const gainFactor = 2.8; // Amplification for clear visual response

        for (let i = 0; i < bufferLength; i++) {
            let v = ((dataArray[i] - 128) / 128.0) * gainFactor;
            v = Math.max(-1, Math.min(1, v));

            // Add subtle sine pulse if room is quiet
            if (avgAmplitude < 1) {
                v = Math.sin(i * 0.15 + wavePhase) * 0.08;
            }
            const y = (height / 2) + (v * height * 0.45);

            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }

            x += sliceWidth;
        }

        canvasCtx.lineTo(width, height / 2);
        canvasCtx.stroke();
        canvasCtx.shadowBlur = 0; // Reset shadow
    }

    // 2. STAFF MODE LOGIC
    function initStaffMode(user) {
        loadStaffVitals();
    }

    async function loadStaffVitals() {
        try {
            const res = await fetch("/api/vitals");
            const vitals = await res.json();
            const tbody = document.getElementById("s-vitals-tbody");
            tbody.innerHTML = "";

            if (vitals.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center">記録はありません</td></tr>`;
                return;
            }

            vitals.forEach(v => {
                const tr = document.createElement("tr");
                if (v.is_alert) tr.className = "alert-row";
                tr.innerHTML = `
                    <td>${v.room_number || '-'}</td>
                    <td>${v.user_name}</td>
                    <td>${new Date(v.timestamp).toLocaleTimeString("ja-JP")}</td>
                    <td>${v.temperature ? v.temperature + '℃' : '-'}</td>
                    <td>${v.bp_sys ? v.bp_sys + '/' + v.bp_dia : '-'}</td>
                    <td>${v.weight ? v.weight + 'kg' : '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (err) {
            console.error(err);
        }
    }

    // 3. FAMILY MODE LOGIC
    function initFamilyMode(user) {
        document.getElementById("f-visit-form").onsubmit = (e) => {
            e.preventDefault();
            alert("面会予約を送信し、Googleカレンダーに反映しました！");
        };
    }

    // 4. BARBER MODE LOGIC
    function initBarberMode(user) {
        document.querySelectorAll(".finish-barber-btn").forEach(btn => {
            btn.onclick = () => {
                alert("理美容の完了報告を送信し、スタッフおよびご家族に通知しました。");
                btn.disabled = true;
                btn.textContent = "報告完了";
            };
        });
    }

    // LOGOUT
    logoutBtn.addEventListener("click", () => {
        sessionStorage.removeItem("care_link_session");
        if (ws) ws.close();
        location.reload();
    });
});
