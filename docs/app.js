// Care-Link Family Mode Portal Logic
document.addEventListener("DOMContentLoaded", () => {
    // Session State
    let currentFamilyUser = null;
    let patientData = null;
    let tempChartInstance = null;
    let bpChartInstance = null;
    let bgmAudioCtx = null;
    let isBgmPlaying = false;
    let bgmIntervalId = null;

    // Movie Animation State
    let movieAnimFrame = null;
    let movieStartTime = null;
    let isMoviePlaying = false;
    let movieDurationSec = 25;
    const movieCanvas = document.getElementById("movieCanvas");
    const movieCtx = movieCanvas ? movieCanvas.getContext("2d") : null;
    const postcardImg = document.getElementById("postcard-img");

    // UI Elements
    const patientNameHeader = document.getElementById("patient-name-header");
    const patientRoomHeader = document.getElementById("patient-room-header");
    const familyUserName = document.getElementById("family-user-name");
    const logoutBtn = document.getElementById("logout-btn");
    
    const patientNameHero = document.getElementById("patient-name-hero");
    const vitalStatusBadge = document.getElementById("vital-status-badge");
    const patientDemographics = document.getElementById("patient-demographics");
    const quickTemp = document.getElementById("quick-temp");
    const quickBp = document.getElementById("quick-bp");
    const quickMood = document.getElementById("quick-mood");

    const episodeSummaryText = document.getElementById("episode-summary-text");
    const episodeTime = document.getElementById("episode-time");
    const postcardHistoryChips = document.getElementById("postcard-history-chips");
    const recentChatList = document.getElementById("recent-chat-list");
    const postcardTitle = document.getElementById("postcard-title");
    const postcardRecipient = document.getElementById("postcard-recipient");
    const postcardDate = document.getElementById("postcard-date");
    const postcardGreeting = document.getElementById("postcard-greeting");
    const postcardSeasonBar = document.getElementById("postcard-season-bar");
    const postcardDownloadBtn = document.getElementById("postcard-download-btn");
    const postcardPrintBtn = document.getElementById("postcard-print-btn");
    const bgmPlayBtn = document.getElementById("bgm-play-btn");
    const bgmTitle = document.getElementById("bgm-title");
    let currentSeason = "autumn";

    const vitalsTableBody = document.getElementById("vitals-table-body");
    const visitationForm = document.getElementById("visitation-form");
    const visitDateInput = document.getElementById("visit-date-input");
    const visitCountInput = document.getElementById("visit-count-input");
    const visitMsgInput = document.getElementById("visit-msg-input");
    const bookingAlert = document.getElementById("booking-alert");
    const reservationCardsContainer = document.getElementById("reservation-cards-container");

    const movieStartBtn = document.getElementById("movie-start-btn");
    const moviePlayOverlay = document.getElementById("movie-play-overlay");
    const movieToggleBtn = document.getElementById("movie-toggle-btn");
    const movieProgress = document.getElementById("movie-progress");
    const movieTimeDisplay = document.getElementById("movie-time-display");
    const movieDownloadBtn = document.getElementById("movie-download-btn");
    const movieTitle = document.getElementById("movie-title");
    const movieSubtitleMeta = document.getElementById("movie-subtitle-meta");
    const movieWeekBadge = document.getElementById("movie-week-badge");
    const movieHistoryChips = document.getElementById("movie-history-chips");

    // Intercom Voice Call Elements & State
    const familyIntercomSection = document.getElementById("family-intercom-section");
    const familyTerminalStatusBadge = document.getElementById("family-terminal-status-badge");
    const familyCallButtons = document.getElementById("family-call-buttons");
    const familyCallBtn = document.getElementById("family-call-btn");
    const familyForceCallBtn = document.getElementById("family-force-call-btn");
    const familyCallActiveBox = document.getElementById("family-call-active-box");
    const familyCallStateText = document.getElementById("family-call-state-text");
    const familyCallTimer = document.getElementById("family-call-timer");
    const familyHangupBtn = document.getElementById("family-hangup-btn");
    const familyCallNotice = document.getElementById("family-call-notice");

    let familyWs = null;
    let intercomStream = null;
    let intercomRecorder = null;
    let isIntercomCallActive = false;
    let intercomTimerInterval = null;
    let intercomSeconds = 0;
    let audioQueue = [];
    let isPlayingQueue = false;
    let currentTerminalStatus = "offline";

    // --- Dynamic Backend Host Resolution for External / GitHub Pages Access ---
    function getStoredBackendUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const paramServer = urlParams.get("server") || urlParams.get("backend");
        if (paramServer) {
            const cleaned = paramServer.replace(/\/+$/, "");
            localStorage.setItem("carelink_backend_server", cleaned);
            return cleaned;
        }
        const stored = localStorage.getItem("carelink_backend_server");
        if (stored) return stored.replace(/\/+$/, "");

        const hostname = window.location.hostname;
        if (hostname === "localhost" || hostname === "127.0.0.1" || hostname.endsWith(".local")) {
            return "";
        }
        return null;
    }

    function getApiUrl(endpoint) {
        const base = getStoredBackendUrl();
        if (!base) return endpoint;
        return `${base}${endpoint}`;
    }

    function getWsUrl(endpoint) {
        const base = getStoredBackendUrl();
        if (base) {
            const wsProto = base.startsWith("https") ? "wss:" : "ws:";
            const hostPart = base.replace(/^https?:\/\//, "");
            return `${wsProto}//${hostPart}${endpoint}`;
        }
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${protocol}//${window.location.host}${endpoint}`;
    }

    function getAssetUrl(rawUrl) {
        if (!rawUrl) return "assets/sample_postcard.jpg";
        if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://") || rawUrl.startsWith("data:")) {
            return rawUrl;
        }
        // Normalize /family/assets/... or /assets/... to assets/...
        let cleaned = rawUrl.replace(/^\/?family\//, "");
        if (cleaned.startsWith("/")) cleaned = cleaned.substring(1);
        return cleaned;
    }

    // Server Config UI Elements
    const serverSettingsBtn = document.getElementById("server-settings-btn");
    const serverConfigBanner = document.getElementById("server-config-banner");
    const serverUrlInput = document.getElementById("server-url-input");
    const btnSaveServerUrl = document.getElementById("btn-save-server-url");
    const btnCloseServerBanner = document.getElementById("btn-close-server-banner");
    const serverConfigStatusText = document.getElementById("server-config-status-text");

    function setupServerConfigUI() {
        const currentUrl = getStoredBackendUrl();
        const hostname = window.location.hostname;
        const isLocal = (hostname === "localhost" || hostname === "127.0.0.1" || hostname.endsWith(".local"));

        if (currentUrl) {
            if (serverUrlInput) serverUrlInput.value = currentUrl;
            if (serverConfigStatusText) serverConfigStatusText.textContent = `接続中: ${currentUrl}`;
        }

        // Show banner automatically if on external host (e.g. GitHub Pages) and not yet configured
        if (!isLocal && !currentUrl && serverConfigBanner) {
            serverConfigBanner.classList.remove("hidden");
        }

        if (serverSettingsBtn && serverConfigBanner) {
            serverSettingsBtn.addEventListener("click", () => {
                serverConfigBanner.classList.toggle("hidden");
                if (!serverConfigBanner.classList.contains("hidden") && serverUrlInput) {
                    serverUrlInput.focus();
                }
            });
        }

        if (btnCloseServerBanner && serverConfigBanner) {
            btnCloseServerBanner.addEventListener("click", () => {
                serverConfigBanner.classList.add("hidden");
            });
        }

        if (btnSaveServerUrl && serverUrlInput) {
            btnSaveServerUrl.addEventListener("click", () => {
                let val = serverUrlInput.value.trim();
                if (!val) {
                    localStorage.removeItem("carelink_backend_server");
                    alert("接続先サーバー設定をクリアしました（ローカルオリジンを使用します）。");
                } else {
                    if (!val.startsWith("http://") && !val.startsWith("https://")) {
                        val = "https://" + val;
                    }
                    val = val.replace(/\/+$/, "");
                    localStorage.setItem("carelink_backend_server", val);
                    alert(`接続先サーバーを保存しました:\n${val}\n再接続します。`);
                }
                window.location.reload();
            });
        }
    }

    // Tabs
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    // 1. Initialize Authentication & Session
    async function initSession() {
        setupServerConfigUI();

        const stored = sessionStorage.getItem("care_link_session");
        if (stored) {
            try {
                currentFamilyUser = JSON.parse(stored);
            } catch (e) {
                currentFamilyUser = null;
            }
        }

        // Default to family01 for direct test access
        const userCode = (currentFamilyUser && currentFamilyUser.user_code) ? currentFamilyUser.user_code : "family01";

        try {
            const res = await fetch(getApiUrl(`/api/family/my_patient?user_code=${encodeURIComponent(userCode)}`));
            if (!res.ok) {
                if (res.status === 401 || res.status === 403) {
                    alert("ご家族アカウントの認証に失敗しました。ログイン画面へ移動します。");
                    window.location.href = "/";
                    return;
                }
                throw new Error("データの取得に失敗しました");
            }
            patientData = await res.json();
            renderAllData(patientData);
            loadReservations(userCode);
            connectFamilyWS(userCode);
        } catch (err) {
            console.error("Family data fetch error:", err);
            const currentUrl = getStoredBackendUrl();
            if (!currentUrl && window.location.hostname !== "localhost") {
                episodeSummaryText.innerHTML = "⚠️ 施設サーバーの接続先URLが設定されていません。<br>上の「接続設定」からCloudflareトンネル等のURLを設定してください。";
                if (serverConfigBanner) serverConfigBanner.classList.remove("hidden");
            } else {
                episodeSummaryText.textContent = "現在サーバーと接続できません。後ほど再度ご確認ください。";
            }
        }
    }

    // ==========================================================================
    // Family Intercom & WebSocket Voice Calling Logic
    // ==========================================================================
    function updateFamilyCallUI() {
        if (!familyTerminalStatusBadge) return;

        const labels = {
            offline: "⚪ オフライン",
            idle: "🟢 待機中",
            chatting: "💬 会話中",
            intercom: "📞 通話中"
        };
        familyTerminalStatusBadge.className = `terminal-status-badge ${currentTerminalStatus}`;
        familyTerminalStatusBadge.textContent = labels[currentTerminalStatus] || "⚪ 不明";

        if (isIntercomCallActive) {
            familyCallButtons.classList.add("hidden");
            familyCallActiveBox.classList.remove("hidden");
            familyIntercomSection.classList.add("in-call");
            familyCallNotice.classList.add("hidden");
            return;
        }

        familyCallActiveBox.classList.add("hidden");
        familyCallButtons.classList.remove("hidden");
        familyIntercomSection.classList.remove("in-call");

        const allowForce = patientData && patientData.patient && patientData.patient.allow_force_answer_family === 1;
        if (allowForce) {
            familyForceCallBtn.classList.remove("hidden");
        } else {
            familyForceCallBtn.classList.add("hidden");
        }

        if (currentTerminalStatus === "offline") {
            familyCallBtn.disabled = true;
            familyForceCallBtn.disabled = true;
            familyCallNotice.textContent = "⚠️ 居室端末がオフライン（未接続）のため、現在発信できません。";
            familyCallNotice.classList.remove("hidden");
        } else if (currentTerminalStatus === "intercom") {
            familyCallBtn.disabled = true;
            familyForceCallBtn.disabled = true;
            familyCallNotice.textContent = "⚠️ 現在、居室端末は通話中（施設スタッフ対応中等）です。";
            familyCallNotice.classList.remove("hidden");
        } else {
            // idle or chatting
            familyCallBtn.disabled = false;
            familyForceCallBtn.disabled = false;
            familyCallNotice.classList.add("hidden");
        }
    }

    function connectFamilyWS(userCode) {
        if (familyWs) {
            try { familyWs.close(); } catch(e) {}
        }
        const wsUrl = getWsUrl(`/ws/family/${encodeURIComponent(userCode)}`);
        
        familyWs = new WebSocket(wsUrl);

        familyWs.onopen = () => {
            console.log("Family Intercom WS connected");
        };

        familyWs.onclose = () => {
            console.log("Family Intercom WS disconnected, retrying in 3s...");
            setTimeout(() => {
                if (currentFamilyUser) connectFamilyWS(userCode);
            }, 3000);
        };

        familyWs.onerror = (err) => {
            console.error("Family Intercom WS error:", err);
        };

        familyWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("Family WS Received:", data.type);

                switch (data.type) {
                    case "terminal_status":
                        currentTerminalStatus = data.status;
                        updateFamilyCallUI();
                        break;

                    case "call_started":
                        isIntercomCallActive = true;
                        updateFamilyCallUI();
                        startFamilyAudioStream();
                        break;

                    case "intercom_audio":
                        playIntercomChunk(data.audio);
                        break;

                    case "intercom_hangup":
                    case "call_ended":
                        endFamilyIntercomCall(false);
                        break;

                    case "call_rejected":
                        endFamilyIntercomCall(false);
                        familyCallNotice.textContent = "⚠️ " + (data.message || "通話が拒否されました");
                        familyCallNotice.classList.remove("hidden");
                        showToast(data.message || "通話を開始できませんでした", false);
                        break;

                    case "call_interrupted":
                        endFamilyIntercomCall(false);
                        familyCallNotice.textContent = "🚨 " + (data.message || "スタッフ対応のため通話を終了しました");
                        familyCallNotice.classList.remove("hidden");
                        showToast(data.message || "施設スタッフ対応のため通話が終了しました", false);
                        break;

                    case "call_error":
                        endFamilyIntercomCall(false);
                        showToast(data.message || "エラーが発生しました", false);
                        break;
                }
            } catch (e) {
                console.error("Failed to parse WS message:", e);
            }
        };
    }

    async function startFamilyCall(isForce = false) {
        if (!patientData || !patientData.patient || !patientData.patient.terminal_id) {
            alert("見守り対象の居室端末情報が取得できません。");
            return;
        }
        if (currentTerminalStatus === "offline") {
            alert("居室端末がオフラインのため発信できません。");
            return;
        }

        if (!familyWs || familyWs.readyState !== WebSocket.OPEN) {
            alert("通信サーバーに接続されていません。再接続をお待ちください。");
            return;
        }

        isIntercomCallActive = true;
        familyCallStateText.textContent = isForce ? "緊急呼び出し中..." : "呼び出し中...";
        familyCallTimer.textContent = "00:00";
        updateFamilyCallUI();

        familyWs.send(JSON.stringify({
            type: "call_request",
            target: patientData.patient.terminal_id,
            force: isForce
        }));
    }

    async function startFamilyAudioStream() {
        audioQueue = [];
        isPlayingQueue = false;
        intercomSeconds = 0;
        familyCallStateText.textContent = "通話中...";

        // Timer
        if (intercomTimerInterval) clearInterval(intercomTimerInterval);
        intercomTimerInterval = setInterval(() => {
            intercomSeconds++;
            const mins = String(Math.floor(intercomSeconds / 60)).padStart(2, '0');
            const secs = String(intercomSeconds % 60).padStart(2, '0');
            familyCallTimer.textContent = `${mins}:${secs}`;
        }, 1000);

        try {
            intercomStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true }
            });

            const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
            intercomRecorder = new MediaRecorder(intercomStream, { mimeType });

            intercomRecorder.ondataavailable = async (e) => {
                if (e.data.size > 0 && familyWs && familyWs.readyState === WebSocket.OPEN && patientData) {
                    const reader = new FileReader();
                    reader.readAsDataURL(e.data);
                    reader.onloadend = () => {
                        const base64Chunk = reader.result.split(',')[1];
                        familyWs.send(JSON.stringify({
                            type: "audio_stream",
                            target: patientData.patient.terminal_id,
                            audio: base64Chunk
                        }));
                    };
                }
            };

            intercomRecorder.start(250);
            console.log("Family intercom audio streaming started...");

        } catch (err) {
            console.error("Family mic stream failed:", err);
            familyCallStateText.textContent = "マイクに接続できません";
            setTimeout(() => endFamilyIntercomCall(true), 2000);
        }
    }

    function playIntercomChunk(base64Chunk) {
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
        aud.onerror = playNextQueueItem;
        aud.play().catch(err => {
            console.warn("Family queue play blocked:", err);
            playNextQueueItem();
        });
    }

    function endFamilyIntercomCall(notifyServer = true) {
        if (!isIntercomCallActive) return;
        isIntercomCallActive = false;

        if (intercomTimerInterval) {
            clearInterval(intercomTimerInterval);
            intercomTimerInterval = null;
        }
        familyCallTimer.textContent = "00:00";

        if (intercomRecorder && intercomRecorder.state !== "inactive") {
            intercomRecorder.stop();
        }
        if (intercomStream) {
            intercomStream.getTracks().forEach(track => track.stop());
            intercomStream = null;
        }

        if (notifyServer && familyWs && familyWs.readyState === WebSocket.OPEN && patientData && patientData.patient) {
            familyWs.send(JSON.stringify({
                type: "hangup",
                target: patientData.patient.terminal_id
            }));
        }

        updateFamilyCallUI();
    }

    if (familyCallBtn) {
        familyCallBtn.addEventListener("click", () => startFamilyCall(false));
    }
    if (familyForceCallBtn) {
        familyForceCallBtn.addEventListener("click", () => startFamilyCall(true));
    }
    if (familyHangupBtn) {
        familyHangupBtn.addEventListener("click", () => endFamilyIntercomCall(true));
    }

        // Helper: Show Toast Notification
        function showToast(message, isSuccess = true) {
            let toast = document.getElementById("carelink-toast");
            if (!toast) {
                toast = document.createElement("div");
                toast.id = "carelink-toast";
                toast.style.position = "fixed";
                toast.style.bottom = "28px";
                toast.style.right = "28px";
                toast.style.backgroundColor = isSuccess ? "#2d6a4f" : "#b02a37";
                toast.style.color = "#ffffff";
                toast.style.padding = "16px 24px";
                toast.style.borderRadius = "12px";
                toast.style.boxShadow = "0 8px 30px rgba(0,0,0,0.25)";
                toast.style.fontSize = "15px";
                toast.style.fontWeight = "600";
                toast.style.zIndex = "99999";
                toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                toast.style.display = "flex";
                toast.style.alignItems = "center";
                toast.style.gap = "12px";
                toast.style.lineHeight = "1.5";
                document.body.appendChild(toast);
            }
            toast.style.backgroundColor = isSuccess ? "#2d6a4f" : "#b02a37";
            toast.innerHTML = `<span style="font-size: 1.4rem;">${isSuccess ? '📥' : '⚠️'}</span> <div>${message.replace(/\n/g, '<br>')}</div>`;
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
            
            clearTimeout(toast._timer);
            toast._timer = setTimeout(() => {
                toast.style.opacity = "0";
                toast.style.transform = "translateY(10px)";
            }, 4500);
        }

        // Helper: Show File Saved Notification with Full Path & Copy Button
        function showFileSavedNotice(fileType, filename, fullPath) {
            let toast = document.getElementById("carelink-toast");
            if (!toast) {
                toast = document.createElement("div");
                toast.id = "carelink-toast";
                toast.style.position = "fixed";
                toast.style.bottom = "28px";
                toast.style.right = "28px";
                toast.style.backgroundColor = "#1f4e38";
                toast.style.border = "1px solid #52b788";
                toast.style.color = "#ffffff";
                toast.style.padding = "18px 24px";
                toast.style.borderRadius = "14px";
                toast.style.boxShadow = "0 10px 35px rgba(0,0,0,0.35)";
                toast.style.fontSize = "14px";
                toast.style.zIndex = "99999";
                toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                toast.style.maxWidth = "480px";
                toast.style.width = "calc(100vw - 56px)";
                document.body.appendChild(toast);
            }
            toast.style.backgroundColor = "#1f4e38";
            toast.style.border = "1px solid #52b788";
            toast.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <span style="font-size: 1.5rem;">📥</span>
                    <strong style="font-size: 15px; color: #d8f3dc;">【${fileType}】を保存しました</strong>
                </div>
                <div style="font-size: 13px; color: #e9ecef; margin-bottom: 8px;">
                    ファイル名: <code style="background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px; font-weight: 600; color: #95d5b2;">${filename}</code>
                </div>
                <div style="background: rgba(0,0,0,0.45); padding: 10px 12px; border-radius: 8px; border: 1px solid rgba(82, 183, 136, 0.4);">
                    <div style="font-size: 11px; color: #b7e4c7; margin-bottom: 4px; font-weight: 700;">📂 保存先フルパス:</div>
                    <div id="toast-filepath-text" style="font-family: monospace; font-size: 12px; color: #ffffff; word-break: break-all; user-select: all; background: rgba(0,0,0,0.3); padding: 6px 8px; border-radius: 4px;">
                        ${fullPath}
                    </div>
                    <button id="toast-copy-path-btn" style="margin-top: 8px; background: #52b788; color: #081c15; border: none; padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; transition: background 0.2s;">
                        📋 フルパスをコピー
                    </button>
                </div>
            `;
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";

            const copyBtn = document.getElementById("toast-copy-path-btn");
            if (copyBtn) {
                copyBtn.addEventListener("click", () => {
                    navigator.clipboard.writeText(fullPath).then(() => {
                        copyBtn.textContent = "✓ コピーしました！";
                        copyBtn.style.background = "#95d5b2";
                        setTimeout(() => {
                            copyBtn.textContent = "📋 フルパスをコピー";
                            copyBtn.style.background = "#52b788";
                        }, 2500);
                    }).catch(() => {
                        copyBtn.textContent = "✓ 選択してコピーしてください";
                    });
                });
            }

            clearTimeout(toast._timer);
            toast._timer = setTimeout(() => {
                toast.style.opacity = "0";
                toast.style.transform = "translateY(10px)";
            }, 8500);
        }

        // Dynamic Download Link Updater (Native Link directly triggers browser download manager)
        function updatePostcardDownloadLink() {
            if (!postcardDownloadBtn) return;
            const pName = (patientData && patientData.patient) ? patientData.patient.name : "山田太郎";
            const dateStr = (postcardDate && postcardDate.textContent) ? postcardDate.textContent.trim().replace(/[\s\/年月日]/g, "") : "本日";
            const filename = `care_link_postcard_${pName}_${currentSeason}_${dateStr}.jpg`;

            let rawUrl = "";
            if (postcardImg) {
                rawUrl = postcardImg.getAttribute("src") || postcardImg.src || "";
            }
            if (!rawUrl) rawUrl = "/family/assets/generated_relaxation_porch.jpg";

            const downloadUrl = getApiUrl(`/api/family/download_raw_postcard?image_url=${encodeURIComponent(rawUrl)}&filename=${encodeURIComponent(filename)}`);
            postcardDownloadBtn.setAttribute("href", downloadUrl);
            postcardDownloadBtn.setAttribute("download", filename);
        }

    // 2. Render Portal UI Data
    function renderAllData(data) {
        const patient = data.patient;
        const family = data.family_user;
        const latestVital = data.latest_vital;

        // Header & Hero
        patientNameHeader.textContent = `${patient.name} 様`;
        patientRoomHeader.textContent = `${patient.room_number}号室`;
        familyUserName.textContent = family.name || "ご家族様";

        patientNameHero.textContent = `${patient.name} 様`;
        patientDemographics.textContent = `${patient.room_number}号室 | ${patient.age || 85}歳 | グループ: ${family.group_name}`;

        // Status Badge
        if (data.vital_status === "stable") {
            vitalStatusBadge.className = "badge-status badge-stable";
            vitalStatusBadge.textContent = "🟢 安定・良好";
        } else {
            vitalStatusBadge.className = "badge-status badge-caution";
            vitalStatusBadge.textContent = "🟡 要確認 (スタッフ見守り中)";
        }

        // Quick Metrics
        if (latestVital) {
            quickTemp.innerHTML = `${latestVital.temperature ? latestVital.temperature.toFixed(1) : "--.-"} <span class="unit">℃</span>`;
            quickBp.innerHTML = `${latestVital.bp_sys || "---"}/${latestVital.bp_dia || "--"} <span class="unit">mmHg</span>`;
        }
        quickMood.textContent = data.recent_mood || "穏やか";

        // Tab 1: Episodes & Moments
        const multimedia = data.recent_multimedia || {};
        
        // 3-line summary renderer (for smartphone optimization)
        renderSummary3Lines(multimedia.summary_text, multimedia.summary_3lines);

        postcardTitle.textContent = multimedia.card_title || "【デジタル絵手紙】思い出カード";
        if (multimedia.card_image_url) {
            postcardImg.src = getAssetUrl(multimedia.card_image_url);
        }
        if (postcardRecipient) {
            postcardRecipient.textContent = `${patient.name} 様`;
        }
        if (postcardDate && multimedia.date_str) {
            postcardDate.textContent = multimedia.date_str;
        }
        if (episodeTime && multimedia.date_str) {
            episodeTime.textContent = `${multimedia.date_str} 記録`;
        }
        if (postcardGreeting && multimedia.card_greetings) {
            postcardGreeting.textContent = multimedia.card_greetings;
        }
        if (bgmTitle && multimedia.bgm_title) {
            bgmTitle.textContent = multimedia.bgm_title;
        }
        if (multimedia.card_season) {
            currentSeason = multimedia.card_season;
            highlightActiveSeasonButton(currentSeason);
        }
        updatePostcardDownloadLink();

        // Render Past Postcards & Moments Archive Chips
        renderHistoryChips(multimedia.history_cards || []);

        // Chat Highlights
        recentChatList.innerHTML = "";
        const history = data.chat_history || [];
        if (history.length === 0) {
            recentChatList.innerHTML = `<div class="chat-loading">本日の対話記録はまだありません。</div>`;
        } else {
            history.slice(-4).forEach(item => {
                const row = document.createElement("div");
                const isUser = item.sender === "user";
                row.className = `chat-bubble-row ${isUser ? "chat-user" : "chat-ai"}`;
                row.innerHTML = `
                    <span class="chat-speaker">${isUser ? `🗣️ ${patient.name} 様` : "🤖 ケア・リンク AI"} (${item.timestamp ? item.timestamp.substring(11, 16) : "-"})</span>
                    <div>${item.message}</div>
                `;
                recentChatList.appendChild(row);
            });
        }

        // Tab 2: Vitals Charts & Table
        renderVitalsCharts(data.vitals_chronological || []);
        renderVitalsTable(data.vitals || []);

        // Tab 4: Movie Engine Initialization
        preloadMovieImages();
        renderMovieHistoryChips();
        updateMovieHeaders();
    }

    // Helper: Render Smartphone-friendly 3-line summary
    function renderSummary3Lines(text, summary3lines) {
        if (!episodeSummaryText) return;
        const content = summary3lines || text || "";
        const lines = content.split("\n").filter(l => l.trim().length > 0);
        if (lines.length >= 2) {
            episodeSummaryText.innerHTML = lines.slice(0, 3).map((line, idx) => {
                const match = line.match(/^【(.*?)】(.*)$/);
                if (match) {
                    return `<div class="summary-3lines-item">
                        <span class="summary-bullet">${match[1]}</span>
                        <span class="summary-line-text">${match[2]}</span>
                    </div>`;
                }
                const bulletLabels = ["話題", "ご様子", "見守り"];
                const label = bulletLabels[idx] || `点 ${idx + 1}`;
                return `<div class="summary-3lines-item">
                    <span class="summary-bullet">${label}</span>
                    <span class="summary-line-text">${line}</span>
                </div>`;
            }).join("");
        } else {
            episodeSummaryText.textContent = content;
        }
    }

    // Helper: Render Historical Postcard & Episode Chips
    function renderHistoryChips(cards) {
        if (!postcardHistoryChips) return;
        postcardHistoryChips.innerHTML = "";
        if (!cards || cards.length === 0) {
            postcardHistoryChips.innerHTML = `<span class="history-loading-hint">過去の絵手紙はありません</span>`;
            return;
        }

        cards.forEach((card, index) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `history-chip-btn ${index === 0 ? "active" : ""}`;
            const cleanTitle = card.title ? card.title.replace(/^【.*?】/, '') : "絵手紙";
            const dateDisplay = card.date_label || card.short_date || "9/9";
            btn.innerHTML = `
                <span class="history-chip-date">📅 ${dateDisplay}</span>
                <span class="history-chip-badge">${card.badge || "過去"}</span>
                <span class="history-chip-title">${cleanTitle}</span>
            `;
            btn.addEventListener("click", () => {
                document.querySelectorAll(".history-chip-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                switchPostcardView(card);
            });
            postcardHistoryChips.appendChild(btn);
        });
    }

    // Helper: Switch active postcard and summary to chosen history card
    function switchPostcardView(card) {
        if (postcardTitle && card.title) postcardTitle.textContent = card.title;
        if (postcardImg && card.image_url) {
            postcardImg.style.opacity = "0.3";
            postcardImg.src = getAssetUrl(card.image_url);
            postcardImg.onload = () => { postcardImg.style.opacity = "1"; };
        }
        if (postcardDate && card.date_str) {
            postcardDate.textContent = card.date_str;
        }
        if (episodeTime && card.date_str) {
            episodeTime.textContent = `${card.date_str} 記録`;
        }
        if (postcardGreeting && (card.calligraphy || card.title)) {
            postcardGreeting.textContent = card.calligraphy || card.title;
        }
        renderSummary3Lines(card.summary_text, card.summary_3lines);
        updatePostcardDownloadLink();
    }

    // 3. Render Charts with Chart.js
    function renderVitalsCharts(vitalsList) {
        if (!vitalsList || vitalsList.length === 0) return;

        const labels = vitalsList.map(v => (v.timestamp ? v.timestamp.substring(5, 16) : "-"));
        const temps = vitalsList.map(v => v.temperature);
        const sysList = vitalsList.map(v => v.bp_sys);
        const diaList = vitalsList.map(v => v.bp_dia);

        // Temperature Chart
        const tempCanvas = document.getElementById("tempChart");
        if (tempCanvas) {
            if (tempChartInstance) tempChartInstance.destroy();
            tempChartInstance = new Chart(tempCanvas, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "体温 (℃)",
                        data: temps,
                        borderColor: "#e07a5f",
                        backgroundColor: "rgba(224, 122, 95, 0.15)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                        pointBackgroundColor: "#e07a5f"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            min: 35.5,
                            max: 38.5,
                            ticks: { stepSize: 0.5 }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        // Blood Pressure Chart
        const bpCanvas = document.getElementById("bpChart");
        if (bpCanvas) {
            if (bpChartInstance) bpChartInstance.destroy();
            bpChartInstance = new Chart(bpCanvas, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: "収縮期 (上)",
                            data: sysList,
                            borderColor: "#d87080",
                            backgroundColor: "rgba(216, 112, 128, 0.1)",
                            tension: 0.3,
                            pointRadius: 5,
                            pointBackgroundColor: "#d87080"
                        },
                        {
                            label: "拡張期 (下)",
                            data: diaList,
                            borderColor: "#4a7c9d",
                            backgroundColor: "transparent",
                            borderDash: [5, 5],
                            tension: 0.3,
                            pointRadius: 4,
                            pointBackgroundColor: "#4a7c9d"
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            min: 50,
                            max: 180,
                            ticks: { stepSize: 20 }
                        }
                    }
                }
            });
        }
    }

    // Render Vitals History Table
    function renderVitalsTable(vitals) {
        vitalsTableBody.innerHTML = "";
        if (!vitals || vitals.length === 0) {
            vitalsTableBody.innerHTML = `<tr><td colspan="5" class="text-center">記録がありません</td></tr>`;
            return;
        }

        vitals.forEach(v => {
            const tr = document.createElement("tr");
            const isCaution = (v.temperature && v.temperature >= 37.5) || (v.bp_sys && v.bp_sys >= 150) || v.is_alert;
            tr.innerHTML = `
                <td>${v.timestamp || "-"}</td>
                <td><strong>${v.temperature ? v.temperature.toFixed(1) + " ℃" : "-"}</strong></td>
                <td>${v.bp_sys || "-"}/${v.bp_dia || "-"} mmHg</td>
                <td>${v.weight ? v.weight.toFixed(1) + " kg" : "-"}</td>
                <td>
                    <span class="${isCaution ? 'status-tag-caution' : 'status-tag-ok'}">
                        ${isCaution ? '⚠️ 要注意' : '🟢 良好'}
                    </span>
                </td>
            `;
            vitalsTableBody.appendChild(tr);
        });
    }

    // 4. Tab 3: Visitation Reservation
    async function loadReservations(userCode) {
        try {
            const res = await fetch(getApiUrl(`/api/family/reservations?user_code=${encodeURIComponent(userCode)}`));
            if (!res.ok) throw new Error("予約一覧取得失敗");
            const list = await res.json();
            renderReservations(list);
        } catch (err) {
            console.error("Reservations fetch error:", err);
            reservationCardsContainer.innerHTML = `<div class="loading-text">予約履歴を読み込めませんでした。</div>`;
        }
    }

    function renderReservations(list) {
        reservationCardsContainer.innerHTML = "";
        if (!list || list.length === 0) {
            reservationCardsContainer.innerHTML = `<div class="loading-text">現在、登録されている面会予約はありません。</div>`;
            return;
        }

        list.forEach(item => {
            const card = document.createElement("div");
            card.className = "res-card-item";
            const isConfirmed = item.status === "confirmed";
            card.innerHTML = `
                <div class="res-item-left">
                    <div class="res-datetime">📅 ${item.visit_datetime}</div>
                    <div class="res-details">
                        👥 人数: ${item.visitors_count}名 | 
                        📝 メッセージ: ${item.message || "なし"}
                    </div>
                </div>
                <div class="res-item-right">
                    <span class="res-status-badge ${isConfirmed ? 'res-status-confirmed' : 'res-status-pending'}">
                        ${isConfirmed ? '✓ 確定・カレンダー同期済' : '⏳ 申請中 (施設確認中)'}
                    </span>
                </div>
            `;
            reservationCardsContainer.appendChild(card);
        });
    }

    // Booking Form Submission
    visitationForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const userCode = (currentFamilyUser && currentFamilyUser.user_code) ? currentFamilyUser.user_code : "family01";
        if (!patientData || !patientData.patient) {
            alert("利用者データが読み込まれていません。");
            return;
        }

        const payload = {
            patient_id: patientData.patient.id,
            user_code: userCode,
            visit_datetime: visitDateInput.value.replace("T", " "),
            visitors_count: parseInt(visitCountInput.value) || 1,
            message: visitMsgInput.value.trim()
        };

        try {
            const res = await fetch(getApiUrl("/api/family/reservations"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (res.ok) {
                bookingAlert.className = "booking-alert success";
                bookingAlert.textContent = data.message || "面会予約を送信しました！";
                bookingAlert.classList.remove("hidden");
                visitationForm.reset();
                loadReservations(userCode);
                setTimeout(() => bookingAlert.classList.add("hidden"), 6000);
            } else {
                throw new Error(data.detail || "予約送信エラー");
            }
        } catch (err) {
            bookingAlert.className = "booking-alert error";
            bookingAlert.textContent = `予約送信に失敗しました: ${err.message}`;
            bookingAlert.classList.remove("hidden");
        }
    });

    // Set default datetime to tomorrow 14:00
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(14, 0, 0, 0);
    const tomorrowIso = tomorrow.toISOString().slice(0, 16);
    if (visitDateInput) visitDateInput.value = tomorrowIso;

    // 5. Ambient BGM Synthesizer (Web Audio API Pentatonic Japanese Scale)
    function toggleBgm() {
        if (isBgmPlaying) {
            stopBgm();
        } else {
            playBgm();
        }
    }

    function playBgm() {
        if (!bgmAudioCtx) {
            bgmAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (bgmAudioCtx.state === "suspended") {
            bgmAudioCtx.resume();
        }

        isBgmPlaying = true;
        bgmPlayBtn.classList.add("playing");
        bgmPlayBtn.querySelector(".play-icon").textContent = "⏸";
        bgmPlayBtn.querySelector(".play-label").textContent = "音声を停止";

        // Seasonal Pentatonic Scales
        const seasonalScales = {
            spring: [261.63, 277.18, 349.23, 392.00, 415.30, 523.25], // Miyako-bushi / Sakura
            summer: [329.63, 415.30, 493.88, 523.25, 659.25],         // Ryukyu bell chime
            autumn: [293.66, 349.23, 392.00, 440.00, 523.25, 587.33], // Insen / Yo warm
            winter: [220.00, 261.63, 293.66, 329.63, 392.00, 440.00]  // Quiet serene
        };
        const scale = seasonalScales[currentSeason] || seasonalScales.autumn;
        let noteIndex = 0;

        function playSoftTone(freq) {
            if (!isBgmPlaying) return;
            const now = bgmAudioCtx.currentTime;
            const osc = bgmAudioCtx.createOscillator();
            const gain = bgmAudioCtx.createGain();

            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now);

            // Gentle attack and decay
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.08, now + 0.15);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.8);

            osc.connect(gain);
            gain.connect(bgmAudioCtx.destination);

            osc.start(now);
            osc.stop(now + 2.0);
        }

        // Arpeggiate melody gently
        playSoftTone(scale[0]);
        bgmIntervalId = setInterval(() => {
            const r = Math.floor(Math.random() * scale.length);
            playSoftTone(scale[r]);
        }, 1200);
    }

    function stopBgm() {
        isBgmPlaying = false;
        if (bgmIntervalId) {
            clearInterval(bgmIntervalId);
            bgmIntervalId = null;
        }
        bgmPlayBtn.classList.remove("playing");
        bgmPlayBtn.querySelector(".play-icon").textContent = "▶";
        bgmPlayBtn.querySelector(".play-label").textContent = "音声を再生";
    }

    bgmPlayBtn.addEventListener("click", toggleBgm);

    // 6. AI Short Movie Canvas Engine (Weekly Slideshow Archives + Ken Burns + Captions)
    const WEEKLY_MOVIES = [
        {
            id: "week-2026-09-07",
            week_start: "9月7日",
            week_label: "9月7日週",
            date_range: "令和8年9月7日〜9月13日",
            badge: "最新",
            title: "秋の夕暮れと安らぎの対話ウィーク",
            bgm_mood: "autumn",
            slides: [
                {
                    image_url: "assets/generated_relaxation_porch.jpg",
                    date_tag: "9月9日 (夜)",
                    caption_title: "秋の夕暮れ 心静かに 和",
                    caption_desc: "「相手の表情を気にしてしまう…とお話しされ、温かいお茶でほっと一息つかれました」"
                },
                {
                    image_url: "assets/generated_undoukai_bento.jpg",
                    date_tag: "9月9日 (昼)",
                    caption_title: "昭和懐かしの運動会とお弁当",
                    caption_desc: "「『おばあちゃんの煮物が美味しかった』と昔の運動会のお弁当を嬉しそうに語られました」"
                },
                {
                    image_url: "assets/generated_healing_sparrows.jpg",
                    date_tag: "9月8日",
                    caption_title: "寄り添う小鳥と秋の風",
                    caption_desc: "「庭先を訪れる小鳥を眺めながら、心穏やかにリラックスした午後を過ごされました」"
                },
                {
                    image_url: "assets/sample_postcard.jpg",
                    date_tag: "9月7日",
                    caption_title: "秋の訪れとコスモス庭園",
                    caption_desc: "「秋の訪れを感じながら、穏やかな笑顔でお元気に過ごされています」"
                }
            ]
        },
        {
            id: "week-2026-08-31",
            week_start: "8月31日",
            week_label: "8月31日週",
            date_range: "令和8年8月31日〜9月6日",
            badge: "先週",
            title: "昭和の思い出と運動会弁当ウィーク",
            bgm_mood: "autumn",
            slides: [
                {
                    image_url: "assets/generated_undoukai_bento.jpg",
                    date_tag: "9月2日",
                    caption_title: "家族で囲んだ手作り弁当",
                    caption_desc: "「家族みんなで応援した運動会の思い出を生き生きとお話しされました」"
                },
                {
                    image_url: "assets/sample_postcard.jpg",
                    date_tag: "9月1日",
                    caption_title: "初秋の庭とコスモス",
                    caption_desc: "「涼しい風が吹き始め、心地よい季節の変わり目を楽しまれました」"
                },
                {
                    image_url: "assets/sample_postcard_summer.jpg",
                    date_tag: "8月31日",
                    caption_title: "夏の終わりの涼風と風鈴",
                    caption_desc: "「朝顔と風鈴の音色に癒され、ゆったりとした時間を過ごされました」"
                }
            ]
        },
        {
            id: "week-2026-08-24",
            week_start: "8月24日",
            week_label: "8月24日週",
            date_range: "令和8年8月24日〜8月30日",
            badge: "過去",
            title: "晩夏の風鈴と日常の語らいウィーク",
            bgm_mood: "summer",
            slides: [
                {
                    image_url: "assets/sample_postcard_summer.jpg",
                    date_tag: "8月28日",
                    caption_title: "涼風の朝顔と風鈴",
                    caption_desc: "「夏の爽やかな風に吹かれながら、スタッフと楽しそうに語らいました」"
                },
                {
                    image_url: "assets/sample_postcard_spring.jpg",
                    date_tag: "8月24日",
                    caption_title: "和みの回想録",
                    caption_desc: "「昔の楽しい思い出を振り返り、安心した表情を見せてくださいました」"
                }
            ]
        }
    ];

    let currentWeeklyMovieIndex = 0;
    let preloadedMovieImages = {};

    function preloadMovieImages() {
        WEEKLY_MOVIES.forEach(wm => {
            wm.slides.forEach(s => {
                const assetUrl = getAssetUrl(s.image_url);
                if (!preloadedMovieImages[assetUrl]) {
                    const img = new Image();
                    img.src = assetUrl;
                    preloadedMovieImages[assetUrl] = img;
                }
            });
        });
    }

    function updateMovieHeaders() {
        const wm = WEEKLY_MOVIES[currentWeeklyMovieIndex] || WEEKLY_MOVIES[0];
        const pName = (patientData && patientData.patient) ? patientData.patient.name : "山田 太郎";
        if (movieTitle) {
            movieTitle.textContent = `${wm.week_label}: ${pName} 様の「${wm.title}」ショートムービー`;
        }
        if (movieSubtitleMeta) {
            movieSubtitleMeta.textContent = `${wm.date_range} (週の始まり: ${wm.week_start}) | その週の対話画像スライドショー (${wm.slides.length}枚収録)`;
        }
        if (movieWeekBadge) {
            movieWeekBadge.textContent = `📅 ${wm.week_label} (${wm.badge})`;
        }
    }

    function renderMovieHistoryChips() {
        if (!movieHistoryChips) return;
        movieHistoryChips.innerHTML = "";
        WEEKLY_MOVIES.forEach((wm, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `history-chip-btn ${idx === currentWeeklyMovieIndex ? "active" : ""}`;
            btn.innerHTML = `
                <span class="history-chip-date">📅 ${wm.week_label}</span>
                <span class="history-chip-badge">${wm.badge}</span>
                <span class="history-chip-title">${wm.title}</span>
            `;
            btn.addEventListener("click", () => {
                switchWeeklyMovie(idx);
            });
            movieHistoryChips.appendChild(btn);
        });
    }

    function switchWeeklyMovie(idx) {
        currentWeeklyMovieIndex = idx;
        if (movieHistoryChips) {
            const btns = movieHistoryChips.querySelectorAll(".history-chip-btn");
            btns.forEach((b, i) => {
                b.classList.toggle("active", i === idx);
            });
        }
        updateMovieHeaders();

        if (isMoviePlaying) {
            stopMovie();
        }
        drawMovieFrame(0);
        movieProgress.style.width = "0%";
        movieTimeDisplay.textContent = `00:00 / 00:${movieDurationSec.toString().padStart(2, "0")}`;
    }

    function drawSeasonalParticles(ctx, w, h, time, mood) {
        if (mood === "spring") {
            ctx.fillStyle = "rgba(255, 183, 178, 0.8)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 57 + time * 15) % (w + 40)) - 20;
                const py = ((i * 83 + time * 25) % (h + 40)) - 20;
                ctx.beginPath();
                ctx.ellipse(px, py, 7, 3.5, (time + i * 12) * 0.05, 0, Math.PI * 2);
                ctx.fill();
            }
        } else if (mood === "summer") {
            ctx.fillStyle = "rgba(160, 235, 195, 0.75)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 61 + time * 18) % (w + 40)) - 20;
                const py = ((i * 71 + time * 12) % (h + 40)) - 20;
                ctx.beginPath();
                ctx.arc(px, py, (i % 3) + 2, 0, Math.PI * 2);
                ctx.fill();
            }
        } else if (mood === "winter") {
            ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
            for (let i = 0; i < 18; i++) {
                const px = ((i * 47 + Math.sin(time * 0.05 + i) * 20) % (w + 40)) - 20;
                const py = ((i * 59 + time * 16) % (h + 40)) - 20;
                ctx.beginPath();
                ctx.arc(px, py, (i % 3) + 2.5, 0, Math.PI * 2);
                ctx.fill();
            }
        } else {
            ctx.fillStyle = "rgba(235, 135, 90, 0.75)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 53 + time * 18) % (w + 40)) - 20;
                const py = ((i * 79 + time * 22) % (h + 40)) - 20;
                ctx.beginPath();
                ctx.ellipse(px, py, 6, 4, (time + i * 15) * 0.04, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    function initMovieCanvas() {
        if (!movieCtx) return;
        preloadMovieImages();
        updateMovieHeaders();
        renderMovieHistoryChips();
        drawMovieFrame(0);
    }

    function drawMovieFrame(progressRatio) {
        if (!movieCtx) return;
        const w = movieCanvas.width;
        const h = movieCanvas.height;

        movieCtx.clearRect(0, 0, w, h);

        // Background dark stage fill
        movieCtx.fillStyle = "#1e1714";
        movieCtx.fillRect(0, 0, w, h);

        const wm = WEEKLY_MOVIES[currentWeeklyMovieIndex] || WEEKLY_MOVIES[0];
        const slides = wm.slides;
        const numSlides = slides.length;

        // Slide calculation based on progress
        const rawPos = progressRatio * numSlides;
        let slideIdx = Math.min(Math.floor(rawPos), numSlides - 1);
        let localRatio = rawPos - slideIdx;
        if (progressRatio >= 1.0) {
            slideIdx = numSlides - 1;
            localRatio = 1.0;
        }

        const currentSlide = slides[slideIdx];
        const assetUrl = getAssetUrl(currentSlide.image_url);
        const curImg = preloadedMovieImages[assetUrl] || postcardImg;

        // Draw slide image with smooth Ken Burns Zoom & Pan
        if (curImg && curImg.complete && curImg.naturalWidth > 0) {
            movieCtx.save();
            const scale = 1.0 + localRatio * 0.12; // 12% subtle Ken Burns zoom
            const panX = Math.sin(localRatio * Math.PI) * 16;
            const panY = localRatio * 10;

            movieCtx.translate(w / 2 + panX, h / 2 + panY);
            movieCtx.scale(scale, scale);

            const imgAspect = curImg.naturalWidth / curImg.naturalHeight;
            const canvasAspect = w / h;
            let dw = w, dh = h;
            if (imgAspect > canvasAspect) {
                dw = h * imgAspect;
            } else {
                dh = w / imgAspect;
            }
            movieCtx.drawImage(curImg, -dw / 2, -dh / 2, dw, dh);
            movieCtx.restore();
        } else if (postcardImg && postcardImg.complete) {
            movieCtx.drawImage(postcardImg, 0, 0, w, h);
        }

        // Cross-fade overlay transition on slide change
        if (localRatio < 0.18 && slideIdx > 0) {
            const prevSlide = slides[slideIdx - 1];
            const prevImg = preloadedMovieImages[prevSlide.image_url];
            if (prevImg && prevImg.complete) {
                const fadeAlpha = 1.0 - (localRatio / 0.18);
                movieCtx.save();
                movieCtx.globalAlpha = fadeAlpha;
                movieCtx.drawImage(prevImg, 0, 0, w, h);
                movieCtx.restore();
            }
        }

        // Floating Seasonal Particles
        const time = progressRatio * 100;
        drawSeasonalParticles(movieCtx, w, h, time, wm.bgm_mood || currentSeason);

        // Top Slide Header Pill (Top-left on video)
        movieCtx.save();
        movieCtx.fillStyle = "rgba(0, 0, 0, 0.6)";
        movieCtx.beginPath();
        if (movieCtx.roundRect) {
            movieCtx.roundRect(24, 20, 310, 36, 18);
        } else {
            movieCtx.rect(24, 20, 310, 36);
        }
        movieCtx.fill();
        movieCtx.strokeStyle = "rgba(255, 255, 255, 0.35)";
        movieCtx.lineWidth = 1;
        movieCtx.stroke();

        movieCtx.font = "bold 13px 'Zen Maru Gothic', sans-serif";
        movieCtx.fillStyle = "#ffffff";
        movieCtx.textAlign = "left";
        movieCtx.fillText(`📅 ${currentSlide.date_tag}  |  スライド ${slideIdx + 1} / ${numSlides}`, 38, 43);
        movieCtx.restore();

        // Subtitle Overlay Banner (Bottom of video)
        const bannerH = 105;
        const grad = movieCtx.createLinearGradient(0, h - bannerH, 0, h);
        grad.addColorStop(0, "rgba(20, 15, 12, 0)");
        grad.addColorStop(0.25, "rgba(20, 15, 12, 0.82)");
        grad.addColorStop(1, "rgba(15, 10, 8, 0.95)");
        movieCtx.fillStyle = grad;
        movieCtx.fillRect(0, h - bannerH, w, bannerH);

        // Slide title & caption
        movieCtx.save();
        // Title in warm gold
        movieCtx.font = "bold 15px 'Zen Maru Gothic', sans-serif";
        movieCtx.fillStyle = "#fbd38d";
        movieCtx.textAlign = "center";
        movieCtx.fillText(`✨ ${currentSlide.caption_title}`, w / 2, h - 58);

        // Description in clean white
        movieCtx.font = "600 17px 'Zen Maru Gothic', sans-serif";
        movieCtx.fillStyle = "#ffffff";
        movieCtx.shadowColor = "rgba(0, 0, 0, 0.8)";
        movieCtx.shadowBlur = 6;
        movieCtx.fillText(currentSlide.caption_desc, w / 2, h - 25);
        movieCtx.shadowBlur = 0;
        movieCtx.restore();
    }

    function playMovie() {
        isMoviePlaying = true;
        moviePlayOverlay.classList.add("hidden");
        movieToggleBtn.textContent = "一時停止";
        movieStartTime = performance.now();
        playBgm();

        function step(timestamp) {
            if (!isMoviePlaying) return;
            const elapsed = (timestamp - movieStartTime) / 1000;
            const progress = Math.min(elapsed / movieDurationSec, 1.0);

            drawMovieFrame(progress);

            // Update Progress Bar & Time
            movieProgress.style.width = `${progress * 100}%`;
            const curMin = Math.floor(elapsed / 60).toString().padStart(2, "0");
            const curSec = Math.floor(elapsed % 60).toString().padStart(2, "0");
            movieTimeDisplay.textContent = `${curMin}:${curSec} / 00:${movieDurationSec.toString().padStart(2, "0")}`;

            if (progress < 1.0) {
                movieAnimFrame = requestAnimationFrame(step);
            } else {
                stopMovie();
            }
        }
        movieAnimFrame = requestAnimationFrame(step);
    }

    function stopMovie() {
        isMoviePlaying = false;
        if (movieAnimFrame) cancelAnimationFrame(movieAnimFrame);
        moviePlayOverlay.classList.remove("hidden");
        movieToggleBtn.textContent = "再生";
        stopBgm();
    }

    movieStartBtn.addEventListener("click", playMovie);
    movieToggleBtn.addEventListener("click", () => {
        if (isMoviePlaying) stopMovie();
        else playMovie();
    });

    // Movie Video Export & Recording (MediaRecorder API)
    let isMovieRecording = false;
    let movieMediaRecorder = null;
    let movieRecordedChunks = [];

    async function recordAndDownloadMovie() {
        if (!movieCanvas) return;
        if (isMovieRecording) return;

        // Check MediaRecorder & captureStream support
        if (!movieCanvas.captureStream || typeof MediaRecorder === "undefined") {
            alert("お使いのブラウザは動画の直接書き出しに対応していません。Google Chrome等の最新ブラウザをご利用ください。");
            return;
        }

        try {
            isMovieRecording = true;
            if (movieDownloadBtn) {
                movieDownloadBtn.disabled = true;
                movieDownloadBtn.innerHTML = `<span>⏳ 録画中 (0%)...</span>`;
            }

            // Determine mimeType (MP4 or WebM)
            let mimeType = "video/webm";
            if (MediaRecorder.isTypeSupported("video/mp4")) {
                mimeType = "video/mp4";
            } else if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9")) {
                mimeType = "video/webm;codecs=vp9";
            } else if (MediaRecorder.isTypeSupported("video/webm")) {
                mimeType = "video/webm";
            }

            const stream = movieCanvas.captureStream(30); // 30 FPS
            movieMediaRecorder = new MediaRecorder(stream, { mimeType });
            movieRecordedChunks = [];

            movieMediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    movieRecordedChunks.push(e.data);
                }
            };

            const wm = WEEKLY_MOVIES[currentWeeklyMovieIndex] || WEEKLY_MOVIES[0];
            const pName = (patientData && patientData.patient) ? patientData.patient.name : "山田太郎";
            const ext = mimeType.includes("mp4") ? "mp4" : "webm";
            const filename = `care_link_movie_${pName}_${wm.week_key}.${ext}`;

            movieMediaRecorder.onstop = () => {
                const blob = new Blob(movieRecordedChunks, { type: mimeType });
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = blobUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                setTimeout(() => URL.revokeObjectURL(blobUrl), 3000);

                isMovieRecording = false;
                if (movieDownloadBtn) {
                    movieDownloadBtn.disabled = false;
                    movieDownloadBtn.innerHTML = `📥 動画を保存`;
                }
                const fullPath = `/home/k3and4/ダウンロード/${filename}`;
                showFileSavedNotice("思い出ショート動画", filename, fullPath);
            };

            // Start Recording & Start Playback
            movieMediaRecorder.start();

            // Record duration: 16 seconds (smooth 4-slide showcase)
            const recordSec = 16;
            const recordStartTime = performance.now();
            isMoviePlaying = true;
            moviePlayOverlay.classList.add("hidden");
            movieToggleBtn.textContent = "一時停止";
            playBgm();

            function recordStep(timestamp) {
                if (!isMovieRecording) return;
                const elapsed = (timestamp - recordStartTime) / 1000;
                const progress = Math.min(elapsed / recordSec, 1.0);

                drawMovieFrame(progress);

                // Update UI progress
                movieProgress.style.width = `${progress * 100}%`;
                const curSec = Math.floor(elapsed);
                movieTimeDisplay.textContent = `00:${curSec.toString().padStart(2, "0")} / 00:${recordSec.toString().padStart(2, "0")}`;
                const pct = Math.floor(progress * 100);
                if (movieDownloadBtn) {
                    movieDownloadBtn.innerHTML = `<span>⏳ 録画中 (${pct}%)...</span>`;
                }

                if (progress < 1.0) {
                    movieAnimFrame = requestAnimationFrame(recordStep);
                } else {
                    // Complete recording
                    if (movieMediaRecorder && movieMediaRecorder.state !== "inactive") {
                        movieMediaRecorder.stop();
                    }
                    stopMovie();
                }
            }

            movieAnimFrame = requestAnimationFrame(recordStep);

        } catch (err) {
            console.error("Movie recording error:", err);
            isMovieRecording = false;
            if (movieDownloadBtn) {
                movieDownloadBtn.disabled = false;
                movieDownloadBtn.innerHTML = `📥 動画を保存`;
            }
            alert("動画の出力に失敗しました。もう一度お試しください。");
        }
    }

    if (movieDownloadBtn) {
        movieDownloadBtn.addEventListener("click", recordAndDownloadMovie);
    }

    // 7. Tab Switching Logic
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            tabPanels.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) {
                targetPanel.classList.add("active");
                // Resize charts if vitals tab selected
                if (targetId === "tab-vitals") {
                    setTimeout(() => {
                        if (tempChartInstance) tempChartInstance.resize();
                        if (bpChartInstance) bpChartInstance.resize();
                    }, 50);
                } else if (targetId === "tab-movie") {
                    initMovieCanvas();
                }
            }
        });
    });

    // 8. Postcard Season Switcher, Download & Print Logic
    function highlightActiveSeasonButton(seasonKey) {
        if (!postcardSeasonBar) return;
        const btns = postcardSeasonBar.querySelectorAll(".btn-season");
        btns.forEach(btn => {
            if (btn.dataset.season === seasonKey) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

    async function switchSeason(seasonKey) {
        currentSeason = seasonKey;
        highlightActiveSeasonButton(seasonKey);
        
        const userCode = (currentFamilyUser && currentFamilyUser.user_code) ? currentFamilyUser.user_code : "family01";
        try {
            const res = await fetch(getApiUrl(`/api/family/my_patient?user_code=${encodeURIComponent(userCode)}&season=${encodeURIComponent(seasonKey)}`));
            if (res.ok) {
                const data = await res.json();
                patientData = data;
                renderAllData(data);
                if (movieCtx) {
                    drawMovieFrame(0);
                }
            }
        } catch (e) {
            console.error("Season switch error:", e);
        }
    }

    function initPostcardActions() {
        if (postcardSeasonBar) {
            postcardSeasonBar.addEventListener("click", (e) => {
                const btn = e.target.closest(".btn-season");
                if (!btn) return;
                const season = btn.dataset.season;
                if (season && season !== currentSeason) {
                    switchSeason(season);
                }
            });
        }



        if (postcardDownloadBtn) {
            postcardDownloadBtn.addEventListener("click", () => {
                updatePostcardDownloadLink();
                const pName = (patientData && patientData.patient) ? patientData.patient.name : "山田太郎";
                const dateStr = (postcardDate && postcardDate.textContent) ? postcardDate.textContent.trim().replace(/[\s\/年月日]/g, "") : "本日";
                const filename = `care_link_postcard_${pName}_${currentSeason}_${dateStr}.jpg`;
                const fullPath = `/home/k3and4/ダウンロード/${filename}`;
                showFileSavedNotice("デジタル絵手紙", filename, fullPath);
            });
        }

        if (postcardPrintBtn) {
            postcardPrintBtn.addEventListener("click", () => {
                const win = window.open("", "_blank");
                const pName = (patientData && patientData.patient) ? patientData.patient.name : "利用者";
                const greeting = postcardGreeting ? postcardGreeting.textContent : "";
                const dateStr = postcardDate ? postcardDate.textContent : "";
                win.document.write(`
                    <!DOCTYPE html>
                    <html lang="ja">
                    <head>
                        <meta charset="UTF-8">
                        <title>【ケア・リンク デジタル絵手紙】${pName} 様</title>
                        <style>
                            body { font-family: 'Hiragino Mincho ProN', 'Yu Mincho', serif; text-align: center; padding: 30px; background: #faf8f5; }
                            .card-wrap { max-width: 650px; margin: 0 auto; border: 1px solid #dcd3c8; padding: 20px; border-radius: 12px; background: #fff; box-shadow: 0 4px 15px rgba(0,0,0,0.06); }
                            img { max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
                            .meta-box { margin-top: 20px; text-align: left; line-height: 1.8; border-top: 1px dashed #dcd3c8; padding-top: 15px; }
                            .recipient { font-size: 1.3rem; font-weight: bold; color: #2c2520; }
                            .date { float: right; font-size: 0.95rem; color: #887b70; }
                            .greeting { font-size: 1.1rem; color: #4a3b32; margin: 12px 0; font-style: italic; }
                            .footer { text-align: right; margin-top: 15px; }
                            .stamp { display: inline-block; border: 2px solid #b22222; color: #b22222; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-family: sans-serif; font-size: 0.85rem; }
                        </style>
                    </head>
                    <body>
                        <div class="card-wrap">
                            <img src="${postcardImg.src}">
                            <div class="meta-box">
                                <span class="recipient">${pName} 様</span>
                                <span class="date">${dateStr}</span>
                                <div style="clear: both;"></div>
                                <p class="greeting">${greeting}</p>
                                <div class="footer">
                                    <span class="stamp">ケア・リンク AI見守り</span>
                                </div>
                            </div>
                        </div>
                        <script>
                            window.onload = function() { window.print(); }
                        </script>
                    </body>
                    </html>
                `);
                win.document.close();
            });
        }
    }

    // 9. Logout
    logoutBtn.addEventListener("click", () => {
        sessionStorage.removeItem("care_link_session");
        window.location.href = "/";
    });

    // Kickoff
    initSession();
    initPostcardActions();
    setTimeout(initMovieCanvas, 300);
});
