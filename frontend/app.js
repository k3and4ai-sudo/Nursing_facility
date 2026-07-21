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

    // Patient Mode UI
    const pMicBtn = document.getElementById("p-mic-btn");
    const pStatusText = document.getElementById("p-status-text");
    const pGuideText = document.getElementById("p-guide-text");
    const pSubtitleBox = document.getElementById("p-subtitle-box");
    const pAiAvatar = document.getElementById("p-ai-avatar");
    
    // Audio Recorder
    let recorder = null;
    let isRecording = false;
    let activeAudio = null;

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
            initFamilyMode(user);
        } else if (user.role === "barber") {
            initBarberMode(user);
        }
    }

    // 1. PATIENT MODE LOGIC
    function initPatientMode(user) {
        const terminalId = user.terminal_id || "user_tablet_1";
        recorder = new WavAudioRecorder();
        
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/user/${terminalId}`);

        ws.onopen = () => {
            pStatusText.textContent = "お話しする準備ができました";
            pMicBtn.disabled = false;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "chat_response") {
                pSubtitleBox.textContent = data.text;
                pStatusText.textContent = "お話し中...";
                pAiAvatar.className = "avatar-circle speaking";
                
                if (activeAudio) activeAudio.pause();
                activeAudio = new Audio("data:audio/mp3;base64," + data.audio);
                activeAudio.onended = () => {
                    pStatusText.textContent = "お話しする準備ができました";
                    pAiAvatar.className = "avatar-circle idle";
                };
                activeAudio.play().catch(e => console.warn(e));
            }
        };

        pMicBtn.onclick = async () => {
            if (isRecording) {
                isRecording = false;
                pMicBtn.classList.remove("recording");
                pAiAvatar.className = "avatar-circle thinking";
                pStatusText.textContent = "考えています...";
                
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
                    pAiAvatar.className = "avatar-circle listening";
                    pStatusText.textContent = "お話ししてください...";
                } catch (err) {
                    pStatusText.textContent = "マイクに接続できません";
                }
            }
        };
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
