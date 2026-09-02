// Staff station dashboard logic
document.addEventListener("DOMContentLoaded", () => {
    // Current Active States
    let activeTab = "dashboard";
    let selectedUserId = null;
    let selectedTerminalId = null;
    let selectedUserName = null;
    let activeAlerts = [];
    
    // Web Audio Intercom variables
    let intercomStream = null;
    let intercomRecorder = null;
    let isIntercomCallActive = false;
    let intercomTimerInterval = null;
    let intercomSeconds = 0;
    let audioQueue = [];
    let isPlayingQueue = false;

    // Charts references
    let tempChart = null;
    let bpChart = null;
    let weightChart = null;

    // WebSocket Reference
    let ws = null;

    // UI Elements - Tabs & Navigation
    const menuButtons = document.querySelectorAll(".menu-btn");
    const tabSections = document.querySelectorAll(".tab-content");
    const tabTitle = document.getElementById("tab-title");
    const connStatus = document.getElementById("conn-status");
    const alertBadge = document.getElementById("alert-badge");
    const alertSound = document.getElementById("alert-sound");

    // UI Elements - Dashboard
    const alertList = document.getElementById("alert-list");
    const recentVitalsTbody = document.getElementById("recent-vitals-tbody");
    const summaryList = document.getElementById("summary-list");
    const clearAlertsBtn = document.getElementById("clear-alerts-btn");

    // UI Elements - Patient Master
    const patientForm = document.getElementById("patient-form");
    const pIdInput = document.getElementById("p-id");
    const pNameInput = document.getElementById("p-name");
    const pAgeInput = document.getElementById("p-age");
    const pRoomInput = document.getElementById("p-room");
    const pTerminalInput = document.getElementById("p-terminal");
    const pDementiaInput = document.getElementById("p-dementia");
    const pAttentionInput = document.getElementById("p-attention");
    const pNotesInput = document.getElementById("p-notes");
    const savePatientBtn = document.getElementById("save-patient-btn");
    const cancelEditBtn = document.getElementById("cancel-edit-btn");
    const patientList = document.getElementById("patient-list");
    const formTitle = document.getElementById("form-title");

    // UI Elements - Vitals Selector
    const vitalUserSelector = document.getElementById("vital-user-selector");
    const vitalsChartEmpty = document.getElementById("vitals-chart-empty");
    const vitalsChartWrapper = document.getElementById("vitals-chart-wrapper");

    // UI Elements - Live Console & Intercom
    const intercomRoomList = document.getElementById("intercom-room-list");
    const callControlCard = document.getElementById("call-control-card");
    const callTargetName = document.getElementById("call-target-name");
    const callTargetRoom = document.getElementById("call-target-room");
    const callTimer = document.getElementById("call-timer");
    const staffCallBtn = document.getElementById("staff-call-btn");
    const staffHangupBtn = document.getElementById("staff-hangup-btn");
    const activeMonitorBadge = document.getElementById("active-monitor-badge");
    const liveChatWindow = document.getElementById("live-chat-window");
    const overrideInputText = document.getElementById("override-input-text");
    const overrideSendBtn = document.getElementById("override-send-btn");

    // UI Elements - Handover & Staff Chat
    const handoverForm = document.getElementById("handover-form");
    const hAuthor = document.getElementById("h-author");
    const hContent = document.getElementById("h-content");
    const handoverListBox = document.getElementById("handover-list-box");
    const staffChatWindow = document.getElementById("staff-chat-window");
    const staffChatInput = document.getElementById("staff-chat-input");
    const staffChatSend = document.getElementById("staff-chat-send");

    // 1. WebSocket Setup
    function connectWS() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/staff`;
        
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("Staff WS connected");
            connStatus.className = "status-badge connected";
            connStatus.textContent = "サーバー接続中";
            loadAllData();
        };

        ws.onclose = () => {
            console.log("Staff WS disconnected");
            connStatus.className = "status-badge disconnected";
            connStatus.textContent = "切断（再接続中...）";
            setTimeout(connectWS, 3000);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Staff WS Received:", data.type);

            switch (data.type) {
                case "user_chat":
                    // If monitoring this specific user, update chat window
                    if (selectedUserId && parseInt(selectedUserId) === parseInt(data.user_id)) {
                        appendMessageToConsole(data.sender, data.message);
                    }
                    // Refresh dashboard lists to show recent logs
                    loadRecentVitals();
                    break;
                    
                case "vital_alert":
                    triggerVitalAlert(data.user_name, data.room_number, data.reason, data.timestamp);
                    break;

                case "pii_alert":
                    triggerPIIAlert(data.user_name, data.room_number, data.detail, data.timestamp);
                    break;

                case "intercom_audio":
                    if (isIntercomCallActive && selectedTerminalId === data.source) {
                        playIntercomChunk(data.audio);
                    }
                    break;

                case "intercom_hangup":
                    if (isIntercomCallActive && selectedTerminalId === data.source) {
                        endIntercomSession(false);
                    }
                    break;

                case "staff_chat":
                    appendStaffChatMessage(data.sender_name, data.message, data.timestamp);
                    break;

                case "user_status":
                    // Update user lists dynamically if needed
                    loadIntercomRooms();
                    break;
            }
        };
    }

    // 2. Navigation Control
    menuButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabName = btn.dataset.tab;
            
            // Toggle active menu button
            menuButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Toggle active tab content
            tabSections.forEach(sec => sec.classList.remove("active"));
            const targetSec = document.getElementById(`tab-${tabName}`);
            targetSec.classList.add("active");

            // Set Title
            tabTitle.textContent = btn.querySelector("span").textContent;
            activeTab = tabName;

            // Trigger tab-specific loads
            if (tabName === "dashboard") {
                loadRecentVitals();
            } else if (tabName === "patients") {
                loadPatients();
            } else if (tabName === "vitals") {
                populateVitalsSelector();
            } else if (tabName === "live-console") {
                loadIntercomRooms();
            } else if (tabName === "handover") {
                loadHandovers();
                loadStaffChatHistory();
            } else if (tabName === "prompts") {
                loadPromptTemplates();
            } else if (tabName === "barber") {
                loadBarberReservations();
                populateBarberUserSelector();
            }
        });
    });

    // 3. Load All Data (Invoked on WebSocket Connect)
    function loadAllData() {
        loadRecentVitals();
        loadPatients();
        populateVitalsSelector();
        loadIntercomRooms();
        loadHandovers();
        loadStaffChatHistory();
    }

    // LINE Share Window Helper
    async function openLineShareWindow(userId, name, room, alertReason = null) {
        let text = `【ケア・リンク 家族連絡】\n`;
        text += `${room ? room + '号室 ' : ''}${name}様に関するご報告です。\n\n`;

        // 1. Fetch latest vitals
        try {
            const vitalsRes = await fetch("/api/vitals");
            const vitalsData = await vitalsRes.json();
            const userVitals = vitalsData.find(v => v.user_name === name);
            if (userVitals) {
                const time = new Date(userVitals.timestamp).toLocaleTimeString("ja-JP", {hour: '2-digit', minute:'2-digit'});
                text += `■ 直近のバイタル測定（${time}）:\n`;
                if (userVitals.temperature) text += `・体温: ${userVitals.temperature} ℃\n`;
                if (userVitals.bp_sys) text += `・血圧: ${userVitals.bp_sys}/${userVitals.bp_dia} mmHg\n`;
                if (userVitals.weight) text += `・体重: ${userVitals.weight} kg\n`;
            }
        } catch (err) {
            console.error("Failed to fetch vitals for LINE message:", err);
        }

        // 2. Alert info
        if (alertReason) {
            text += `\n⚠️ 警告: ${alertReason}\n`;
        }

        // 3. Last conversation message
        if (userId) {
            try {
                const chatRes = await fetch(`/api/users/${userId}/chat`);
                const chatData = await chatRes.json();
                const lastUserMsg = chatData.slice().reverse().find(msg => msg.sender === "user");
                if (lastUserMsg) {
                    text += `\n■ ご本人の直近のご発言:\n「${lastUserMsg.message}」\n`;
                }
            } catch (err) {
                console.error("Failed to fetch chat for LINE message:", err);
            }
        }

        text += `\nご不明な点等ございましたら、施設までお気軽にお問い合わせください。`;

        const lineUrl = `https://line.me/R/share?text=${encodeURIComponent(text)}`;
        window.open(lineUrl, "_blank");
    }

    // 4. Dashboard Logic & Alerts
    async function loadRecentVitals() {
        try {
            const res = await fetch("/api/vitals");
            const data = await res.json();
            
            recentVitalsTbody.innerHTML = "";
            if (data.length === 0) {
                recentVitalsTbody.innerHTML = `<tr><td colspan="6" class="text-center">バイタル記録はありません</td></tr>`;
                return;
            }

            data.forEach(v => {
                const tr = document.createElement("tr");
                if (v.is_alert) tr.className = "alert-row";
                
                const time = new Date(v.timestamp).toLocaleTimeString("ja-JP", {hour: '2-digit', minute:'2-digit'});
                tr.innerHTML = `
                    <td>${v.room_number || '-'}</td>
                    <td><strong>${v.user_name}</strong></td>
                    <td>${time}</td>
                    <td>${v.temperature ? v.temperature + ' ℃' : '-'}</td>
                    <td>${v.bp_sys ? v.bp_sys + '/' + v.bp_dia + ' mmHg' : '-'}</td>
                    <td>${v.weight ? v.weight + ' kg' : '-'}</td>
                `;
                recentVitalsTbody.appendChild(tr);
            });

            // Rebuild summaries based on recent vital remarks
            buildConversationsSummary(data);
        } catch (err) {
            console.error("Error loading recent vitals:", err);
        }
    }

    function buildConversationsSummary(vitals) {
        summaryList.innerHTML = "";
        
        // Group by user
        const userSummaryMap = {};
        vitals.forEach(v => {
            if (!userSummaryMap[v.user_name] && v.raw_text) {
                userSummaryMap[v.user_name] = {
                    room: v.room_number,
                    text: v.raw_text,
                    alert: v.is_alert,
                    reason: v.alert_reason
                };
            }
        });

        const users = Object.keys(userSummaryMap);
        if (users.length === 0) {
            summaryList.innerHTML = `<div class="no-data-msg">本日の会話データはありません</div>`;
            return;
        }

        users.forEach(name => {
            const item = userSummaryMap[name];
            const div = document.createElement("div");
            div.className = "summary-card";
            
            // Simple keyword-based sentiment check for demonstration
            let sentiment = "neutral";
            let sentimentLabel = "良好";
            
            const text = item.text.toLowerCase();
            if (item.alert || text.includes("しんどい") || text.includes("痛い") || text.includes("悪い")) {
                sentiment = "negative";
                sentimentLabel = "不穏 / 体調不良";
            } else if (text.includes("元気") || text.includes("美味しい") || text.includes("良い") || text.includes("ありがとう")) {
                sentiment = "positive";
                sentimentLabel = "安定";
            }

            div.innerHTML = `
                <div class="summary-card-header">
                    <h4>${item.room ? item.room + '号室 ' : ''}${name}様</h4>
                    <span class="sentiment-badge ${sentiment}">${sentimentLabel}</span>
                </div>
                <p>発話: "${item.text}"</p>
                ${item.alert ? `<p style="color:var(--danger); font-size:11px; margin-top:4px;">※警告: ${item.reason}</p>` : ''}
            `;
            summaryList.appendChild(div);
        });
    }

    function triggerVitalAlert(name, room, reason, timestamp) {
        // Active Alert List update
        const id = "alert_" + Date.now();
        activeAlerts.unshift({ id, name, room, reason, timestamp, isPii: false });
        
        // Render alert UI
        renderAlertsList();
        
        // Show indicator and sound
        alertBadge.classList.remove("hidden");
        try {
            alertSound.play().catch(e => console.log("Sound play blocked until user interaction."));
        } catch(e) {}
    }

    function triggerPIIAlert(name, room, detail, timestamp) {
        const id = "pii_alert_" + Date.now();
        const reason = `【個人情報保護アラート】${detail || "会話中に実名・住所・番号が検知されGemini Liveを停止しました。"}`;
        activeAlerts.unshift({ id, name, room, reason, timestamp, isPii: true });
        renderAlertsList();
        alertBadge.classList.remove("hidden");
        try {
            alertSound.play().catch(e => console.log("Sound play blocked until user interaction."));
        } catch(e) {}
    }

    function renderAlertsList() {
        if (activeAlerts.length === 0) {
            alertList.innerHTML = `<div class="no-alerts-msg">現在、異常値アラートは発生していません。</div>`;
            alertBadge.classList.add("hidden");
            alertSound.pause();
            alertSound.currentTime = 0;
            return;
        }

        alertList.innerHTML = "";
        activeAlerts.forEach(a => {
            const div = document.createElement("div");
            div.className = "alert-card-item";
            const time = new Date(a.timestamp).toLocaleTimeString("ja-JP");
            div.innerHTML = `
                <div class="details">
                    <h4>🚨 異常検知: ${a.room ? a.room + '号室 ' : ''}${a.name}様</h4>
                    <p>理由: ${a.reason}</p>
                </div>
                <div class="alert-actions" style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
                    <button class="btn btn-line btn-sm line-alert-btn" data-name="${a.name}" data-room="${a.room || ''}" data-reason="${a.reason}">LINE連絡</button>
                    <div class="time">${time}</div>
                </div>
            `;
            alertList.appendChild(div);
        });

        document.querySelectorAll(".line-alert-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                let patientId = null;
                try {
                    const res = await fetch("/api/users");
                    const data = await res.json();
                    const p = data.find(user => user.name === btn.dataset.name);
                    if (p) patientId = p.id;
                } catch (e) {
                    console.error("Error looking up patient id for alert LINE:", e);
                }
                openLineShareWindow(patientId, btn.dataset.name, btn.dataset.room, btn.dataset.reason);
            });
        });
    }

    clearAlertsBtn.addEventListener("click", () => {
        activeAlerts = [];
        renderAlertsList();
    });

    // 5. Patient Master CRUD
    async function loadPatients() {
        try {
            const res = await fetch("/api/users");
            const data = await res.json();
            
            patientList.innerHTML = "";
            if (data.length === 0) {
                patientList.innerHTML = `<div class="text-center pad-20">利用者が登録されていません</div>`;
                return;
            }

            data.forEach(p => {
                const div = document.createElement("div");
                div.className = "patient-card";
                
                const demLevels = { none: "なし", mild: "軽度", moderate: "中等度", severe: "重度" };
                const demLabel = demLevels[p.dementia_level] || p.dementia_level;

                div.innerHTML = `
                    <div class="details">
                        <h4>${p.room_number ? p.room_number + '号室 ' : ''}${p.name} (${p.age || '-'}歳)</h4>
                        <p>端末ID: <strong>${p.terminal_id}</strong> | 認知症: ${demLabel}</p>
                        ${p.notes ? `<p style="font-size:11px; color:var(--text-muted);">メモ: ${p.notes}</p>` : ''}
                    </div>
                    <div class="actions">
                        <button class="btn btn-line btn-sm line-patient-btn" data-id="${p.id}" data-name="${p.name}" data-room="${p.room_number || ''}">LINE連絡</button>
                        <button class="btn btn-secondary btn-sm edit-p-btn" data-id="${p.id}">編集</button>
                        <button class="btn btn-danger btn-sm delete-p-btn" data-id="${p.id}">削除</button>
                    </div>
                `;
                patientList.appendChild(div);
            });

            // Bind edit/delete/LINE events
            document.querySelectorAll(".line-patient-btn").forEach(btn => {
                btn.addEventListener("click", () => openLineShareWindow(parseInt(btn.dataset.id), btn.dataset.name, btn.dataset.room));
            });
            document.querySelectorAll(".edit-p-btn").forEach(btn => {
                btn.addEventListener("click", () => editPatient(parseInt(btn.dataset.id)));
            });
            document.querySelectorAll(".delete-p-btn").forEach(btn => {
                btn.addEventListener("click", () => deletePatient(parseInt(btn.dataset.id)));
            });

        } catch (err) {
            console.error("Error loading patients:", err);
        }
    }

    patientForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            name: pNameInput.value,
            age: parseInt(pAgeInput.value) || 0,
            room_number: pRoomInput.value,
            terminal_id: pTerminalInput.value,
            dementia_level: pDementiaInput.value,
            notes: pNotesInput.value,
            attention_points: pAttentionInput.value
        };

        const id = pIdInput.value;
        const method = id ? "PUT" : "POST";
        const url = id ? `/api/users/${id}` : "/api/users";

        try {
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                patientForm.reset();
                pIdInput.value = "";
                formTitle.textContent = "➕ 利用者 新規登録";
                savePatientBtn.textContent = "登録する";
                cancelEditBtn.classList.add("hidden");
                loadPatients();
                populateVitalsSelector();
                loadIntercomRooms();
            } else {
                const err = await res.json();
                alert("登録に失敗しました: " + (err.detail || "エラー"));
            }
        } catch (err) {
            console.error("Error saving patient:", err);
        }
    });

    async function editPatient(id) {
        try {
            const res = await fetch(`/api/users/${id}`);
            const p = await res.json();
            
            pIdInput.value = p.id;
            pNameInput.value = p.name;
            pAgeInput.value = p.age || "";
            pRoomInput.value = p.room_number || "";
            pTerminalInput.value = p.terminal_id;
            pDementiaInput.value = p.dementia_level;
            pAttentionInput.value = p.attention_points || "";
            pNotesInput.value = p.notes || "";

            formTitle.textContent = "✏️ 利用者情報の編集";
            savePatientBtn.textContent = "更新する";
            cancelEditBtn.classList.remove("hidden");
        } catch (err) {
            console.error("Error fetching patient for edit:", err);
        }
    }

    cancelEditBtn.addEventListener("click", () => {
        patientForm.reset();
        pIdInput.value = "";
        formTitle.textContent = "➕ 利用者 新規登録";
        savePatientBtn.textContent = "登録する";
        cancelEditBtn.classList.add("hidden");
    });

    async function deletePatient(id) {
        if (!confirm("本当にこの利用者を削除しますか？紐付くバイタルやチャット履歴もすべて削除されます。")) return;
        try {
            const res = await fetch(`/api/users/${id}`, { method: "DELETE" });
            if (res.ok) {
                loadPatients();
                populateVitalsSelector();
                loadIntercomRooms();
            }
        } catch (err) {
            console.error("Error deleting patient:", err);
        }
    }

    // 6. Vitals Chart (Chart.js)
    async function populateVitalsSelector() {
        try {
            const res = await fetch("/api/users");
            const users = await res.json();
            
            const currentSelected = vitalUserSelector.value;
            vitalUserSelector.innerHTML = `<option value="">-- 利用者を選択してください --</option>`;
            
            users.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p.id;
                opt.textContent = `${p.room_number ? p.room_number + '号室 ' : ''}${p.name}`;
                vitalUserSelector.appendChild(opt);
            });

            if (currentSelected) {
                vitalUserSelector.value = currentSelected;
            }
        } catch (err) {
            console.error("Error populating vitals selector:", err);
        }
    }

    vitalUserSelector.addEventListener("change", () => {
        const userId = vitalUserSelector.value;
        if (!userId) {
            vitalsChartEmpty.classList.remove("hidden");
            vitalsChartWrapper.classList.add("hidden");
            return;
        }

        vitalsChartEmpty.classList.add("hidden");
        vitalsChartWrapper.classList.remove("hidden");
        loadVitalCharts(userId);
    });

    async function loadVitalCharts(userId) {
        try {
            const res = await fetch(`/api/users/${userId}/vitals`);
            const records = await res.json();
            
            // Sort records by timestamp chronological
            records.sort((a,b) => new Date(a.timestamp) - new Date(b.timestamp));

            const labels = records.map(r => new Date(r.timestamp).toLocaleDateString("ja-JP") + " " + new Date(r.timestamp).toLocaleTimeString("ja-JP", {hour: '2-digit', minute:'2-digit'}));
            const temps = records.map(r => r.temperature);
            const weights = records.map(r => r.weight);
            const sys = records.map(r => r.bp_sys);
            const dia = records.map(r => r.bp_dia);

            // Destroy previous charts if exist
            if (tempChart) tempChart.destroy();
            if (bpChart) bpChart.destroy();
            if (weightChart) weightChart.destroy();

            // Draw Temp Chart
            const ctxTemp = document.getElementById("tempChart").getContext("2d");
            tempChart = new Chart(ctxTemp, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: '体温 (℃)',
                        data: temps,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.2,
                        fill: true
                    }]
                },
                options: { responsive: true, scales: { y: { min: 34, max: 42 } } }
            });

            // Draw BP Chart
            const ctxBp = document.getElementById("bpChart").getContext("2d");
            bpChart = new Chart(ctxBp, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: '最高血圧 (mmHg)',
                            data: sys,
                            borderColor: '#3b82f6',
                            tension: 0.1
                        },
                        {
                            label: '最低血圧 (mmHg)',
                            data: dia,
                            borderColor: '#10b981',
                            tension: 0.1
                        }
                    ]
                },
                options: { responsive: true, scales: { y: { min: 40, max: 200 } } }
            });

            // Draw Weight Chart
            const ctxWeight = document.getElementById("weightChart").getContext("2d");
            weightChart = new Chart(ctxWeight, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: '体重 (kg)',
                        data: weights,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        tension: 0.1,
                        fill: true
                    }]
                },
                options: { responsive: true }
            });

        } catch (err) {
            console.error("Error drawing charts:", err);
        }
    }

    // 7. Live Dialog Console & Intercom (Pattern A & B)
    async function loadIntercomRooms() {
        try {
            const res = await fetch("/api/users");
            const users = await res.json();
            
            intercomRoomList.innerHTML = "";
            if (users.length === 0) {
                intercomRoomList.innerHTML = `<div class="text-center pad-20">利用者が登録されていません</div>`;
                return;
            }

            users.forEach(p => {
                const div = document.createElement("div");
                div.className = "room-call-item";
                if (selectedUserId && parseInt(selectedUserId) === p.id) {
                    div.classList.add("selected");
                }
                
                div.innerHTML = `
                    <div>
                        <span class="room-badge">${p.room_number || '-'}号室</span>
                        <strong style="margin-left:8px;">${p.name}様</strong>
                    </div>
                `;
                
                div.addEventListener("click", () => {
                    document.querySelectorAll(".room-call-item").forEach(item => item.classList.remove("selected"));
                    div.classList.add("selected");
                    selectIntercomTarget(p);
                });

                intercomRoomList.appendChild(div);
            });
        } catch (err) {
            console.error("Error loading intercom rooms:", err);
        }
    }

    function selectIntercomTarget(p) {
        selectedUserId = p.id;
        selectedTerminalId = p.terminal_id;
        selectedUserName = p.name;

        // Update Call Card info
        callTargetName.textContent = `${p.name}様`;
        callTargetRoom.textContent = `${p.room_number || '-'}号室`;
        callControlCard.classList.remove("disabled");
        staffCallBtn.disabled = false;

        // Update Monitor badge
        activeMonitorBadge.textContent = `監視中: ${p.room_number || '-'}号室 ${p.name}様`;
        activeMonitorBadge.style.display = "inline-block";

        // Enable override box
        overrideInputText.disabled = false;
        overrideSendBtn.disabled = false;
        overrideInputText.placeholder = `AIとの会話に割り込んで、${p.name}様に音声を送ります...`;

        // Load historical chat logs
        loadChatHistory(p.id);

        // Show LINE contact button
        const liveLineBtn = document.getElementById("live-line-btn");
        if (liveLineBtn) {
            liveLineBtn.style.display = "inline-block";
            const newBtn = liveLineBtn.cloneNode(true);
            liveLineBtn.parentNode.replaceChild(newBtn, liveLineBtn);
            newBtn.addEventListener("click", () => {
                openLineShareWindow(p.id, p.name, p.room_number);
            });
        }
    }

    async function loadChatHistory(userId) {
        try {
            const res = await fetch(`/api/users/${userId}/chat`);
            const history = await res.json();
            
            liveChatWindow.innerHTML = "";
            if (history.length === 0) {
                liveChatWindow.innerHTML = `<div class="chat-log-placeholder">会話ログはまだありません</div>`;
                return;
            }

            history.forEach(msg => {
                appendMessageToConsole(msg.sender, msg.message);
            });
        } catch (err) {
            console.error("Error loading chat history:", err);
        }
    }

    function appendMessageToConsole(sender, text) {
        // Remove placeholder if exists
        const placeholder = liveChatWindow.querySelector(".chat-log-placeholder");
        if (placeholder) placeholder.remove();

        const div = document.createElement("div");
        div.className = `chat-msg ${sender}`;
        
        let label = "利用者";
        if (sender === "ai") label = "AIアシスタント";
        if (sender === "staff") label = "割り込み（スタッフ）";

        div.innerHTML = `
            <span class="sender-tag">${label}</span>
            <div>${text}</div>
        `;
        liveChatWindow.appendChild(div);
        
        // Auto scroll to bottom
        liveChatWindow.scrollTop = liveChatWindow.scrollHeight;
    }

    // Override input event (Pattern B)
    overrideSendBtn.addEventListener("click", sendOverrideText);
    overrideInputText.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendOverrideText();
    });

    function sendOverrideText() {
        const text = overrideInputText.value.trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN || !selectedTerminalId) return;

        ws.send(JSON.stringify({
            type: "staff_override",
            target: selectedTerminalId,
            user_id: selectedUserId,
            text: text
        }));

        overrideInputText.value = "";
    }

    // Intercom Voice Chat (Pattern A)
    staffCallBtn.addEventListener("click", startIntercomSession);
    staffHangupBtn.addEventListener("click", () => endIntercomSession(true));

    async function startIntercomSession() {
        if (!selectedTerminalId || isIntercomCallActive) return;
        
        console.log("Requesting intercom call with:", selectedTerminalId);
        isIntercomCallActive = true;
        
        // Send request via WebSocket
        ws.send(JSON.stringify({
            type: "call_request",
            target: selectedTerminalId
        }));

        // Adjust UI
        staffCallBtn.classList.add("hidden");
        staffHangupBtn.classList.remove("hidden");
        callControlCard.classList.add("active");
        callTimer.textContent = "呼び出し中...";
        
        // Reset timer
        intercomSeconds = 0;
        audioQueue = [];
        isPlayingQueue = false;

        try {
            // Get microphone stream
            intercomStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true }
            });

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
                            target: selectedTerminalId,
                            audio: base64Chunk
                        }));
                    };
                }
            };

            // Start streaming chunks every 250ms
            intercomRecorder.start(250);
            
            // Start timer UI
            intercomTimerInterval = setInterval(() => {
                intercomSeconds++;
                const mins = String(Math.floor(intercomSeconds / 60)).padStart(2, '0');
                const secs = String(intercomSeconds % 60).padStart(2, '0');
                callTimer.textContent = `${mins}:${secs}`;
            }, 1000);

        } catch (err) {
            console.error("Microphone capture failed:", err);
            callTimer.textContent = "エラー";
            setTimeout(() => endIntercomSession(true), 2000);
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
            console.warn("Queue play blocked:", err);
            playNextQueueItem();
        });
    }

    function endIntercomSession(notifyUser = true) {
        if (!isIntercomCallActive) return;
        isIntercomCallActive = false;

        console.log("Ending intercom session...");

        // Stop timer
        if (intercomTimerInterval) {
            clearInterval(intercomTimerInterval);
            intercomTimerInterval = null;
        }
        callTimer.textContent = "00:00";

        // Stop microphone
        if (intercomRecorder && intercomRecorder.state !== "inactive") {
            intercomRecorder.stop();
        }
        if (intercomStream) {
            intercomStream.getTracks().forEach(track => track.stop());
            intercomStream = null;
        }

        // Notify other client
        if (notifyUser && ws && ws.readyState === WebSocket.OPEN && selectedTerminalId) {
            ws.send(JSON.stringify({
                type: "hangup",
                target: selectedTerminalId
            }));
        }

        // Adjust UI
        staffCallBtn.classList.remove("hidden");
        staffHangupBtn.classList.add("hidden");
        callControlCard.classList.remove("active");
    }

    // 8. Handover notes & Staff Chat (Pattern C)
    async function loadHandovers() {
        try {
            const res = await fetch("/api/handovers");
            const data = await res.json();
            
            handoverListBox.innerHTML = "";
            if (data.length === 0) {
                handoverListBox.innerHTML = `<div class="no-data-msg">登録されている申し送り事項はありません</div>`;
                return;
            }

            data.forEach(h => {
                const div = document.createElement("div");
                div.className = "handover-card";
                
                const timeStr = new Date(h.timestamp).toLocaleString("ja-JP");
                
                div.innerHTML = `
                    <div class="handover-card-header">
                        <span>記入者: <strong>${h.author}</strong></span>
                        <span>${timeStr}</span>
                    </div>
                    <p>${h.content}</p>
                `;
                handoverListBox.appendChild(div);
            });
        } catch (err) {
            console.error("Error loading handovers:", err);
        }
    }

    handoverForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
            author: hAuthor.value,
            content: hContent.value
        };

        try {
            const res = await fetch("/api/handovers", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                hContent.value = ""; // clear content but keep author name for convenience
                loadHandovers();
            }
        } catch (err) {
            console.error("Error saving handover:", err);
        }
    });

    async function loadStaffChatHistory() {
        try {
            const res = await fetch("/api/staff-messages");
            const data = await res.json();
            
            staffChatWindow.innerHTML = "";
            if (data.length === 0) {
                staffChatWindow.innerHTML = `<div class="no-data-msg">メッセージはありません</div>`;
                return;
            }

            data.forEach(msg => {
                appendStaffChatMessage(msg.sender_name, msg.message, msg.timestamp);
            });
        } catch (err) {
            console.error("Error loading staff chat:", err);
        }
    }

    function appendStaffChatMessage(sender, text, timestamp) {
        const placeholder = staffChatWindow.querySelector(".no-data-msg");
        if (placeholder) placeholder.remove();

        const div = document.createElement("div");
        div.className = "chat-msg user"; // Styling mirrors other chat bubble
        const time = new Date(timestamp).toLocaleTimeString("ja-JP", {hour: '2-digit', minute:'2-digit'});
        
        div.innerHTML = `
            <span class="sender-tag">${sender} (${time})</span>
            <div>${text}</div>
        `;
        staffChatWindow.appendChild(div);
        staffChatWindow.scrollTop = staffChatWindow.scrollHeight;
    }

    staffChatSend.addEventListener("click", sendStaffChatMessage);
    staffChatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendStaffChatMessage();
    });

    function sendStaffChatMessage() {
        const text = staffChatInput.value.trim();
        const author = hAuthor.value.trim() || "スタッフ";
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

        ws.send(JSON.stringify({
            type: "staff_chat",
            sender_name: author,
            message: text
        }));

        staffChatInput.value = "";
    }

    // 9. Prompt Templates Library Logic
    async function loadPromptTemplates() {
        const container = document.getElementById("prompt-templates-list");
        if (!container) return;
        try {
            const res = await fetch("/api/prompt_templates");
            const data = await res.json();
            
            container.innerHTML = "";
            if (data.length === 0) {
                container.innerHTML = `<div class="no-data-msg">登録されているプロンプト雛形はありません</div>`;
                return;
            }

            data.forEach(tmpl => {
                const card = document.createElement("div");
                card.className = "card prompt-card";
                card.style.marginBottom = "15px";
                card.innerHTML = `
                    <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0;">${tmpl.title}</h4>
                        <span class="badge" style="background: rgba(37,99,235,0.2); color: #60a5fa; padding: 4px 10px; border-radius: 4px; font-size: 12px;">${tmpl.category}</span>
                    </div>
                    <div class="card-body">
                        <textarea id="tmpl-content-${tmpl.key_name}" rows="4" style="width: 100%; background: #0f172a; border: 1px solid #334155; color: #f8fafc; padding: 10px; border-radius: 6px; font-family: inherit; font-size: 13px; margin-bottom: 10px;">${tmpl.content}</textarea>
                        <div style="display: flex; justify-content: flex-end; gap: 10px;">
                            <button class="btn btn-secondary btn-sm" onclick="alert('ペルソナプロンプトを適用しました。次のAI対話から反映されます。')">AIペルソナに適用</button>
                            <button class="btn btn-primary btn-sm" onclick="savePromptTemplate('${tmpl.key_name}')">内容を更新・保存</button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        } catch (err) {
            console.error("Error loading prompt templates:", err);
        }
    }

    window.savePromptTemplate = async function(keyName) {
        const textarea = document.getElementById(`tmpl-content-${keyName}`);
        if (!textarea) return;
        try {
            const res = await fetch("/api/prompt_templates", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ key_name: keyName, content: textarea.value.trim() })
            });
            if (res.ok) {
                alert("プロンプト雛形を更新・保存しました。");
                loadPromptTemplates();
            }
        } catch (err) {
            console.error("Error saving prompt template:", err);
        }
    };

    // 10. Barber Management Logic
    async function populateBarberUserSelector() {
        const selector = document.getElementById("b-user-id");
        if (!selector) return;
        try {
            const res = await fetch("/api/users");
            const data = await res.json();
            selector.innerHTML = `<option value="">選択してください</option>`;
            data.forEach(u => {
                selector.innerHTML += `<option value="${u.id}">${u.room_number ? u.room_number + '号室: ' : ''}${u.name}</option>`;
            });
        } catch (err) {
            console.error("Error populating barber user selector:", err);
        }
    }

    async function loadBarberReservations() {
        const container = document.getElementById("barber-reservations-list");
        if (!container) return;
        try {
            const res = await fetch("/api/barber/reservations");
            const data = await res.json();
            
            container.innerHTML = "";
            if (data.length === 0) {
                container.innerHTML = `<div class="no-data-msg">訪問理美容の予約はありません</div>`;
                return;
            }

            data.forEach(r => {
                const card = document.createElement("div");
                card.className = "card reservation-card";
                card.style.marginBottom = "15px";
                const isCompleted = r.status === "completed";
                const statusBadge = isCompleted ? `<span class="badge" style="background: rgba(34,197,94,0.2); color: #4ade80; padding: 3px 8px; border-radius: 4px; font-size: 12px;">施術完了</span>` : `<span class="badge" style="background: rgba(234,179,8,0.2); color: #facc15; padding: 3px 8px; border-radius: 4px; font-size: 12px;">予約中</span>`;
                
                card.innerHTML = `
                    <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <h4>${r.room_number ? r.room_number + '号室: ' : ''}<strong>${r.user_name}</strong> 様</h4>
                        ${statusBadge}
                    </div>
                    <div class="card-body">
                        <p style="margin-bottom: 5px;"><strong>予約日時:</strong> ${r.reservation_date}</p>
                        <p style="margin-bottom: 5px;"><strong>メニュー:</strong> ${r.menu}</p>
                        ${r.notes ? `<p style="margin-bottom: 5px; color: #f87171;"><strong>注意点:</strong> ${r.notes}</p>` : ''}
                        ${r.report ? `<p style="margin-top: 8px; background: rgba(15,23,42,0.6); padding: 8px; border-radius: 4px;"><strong>施術完了報告:</strong> ${r.report}</p>` : ''}
                    </div>
                `;
                container.appendChild(card);
            });
        } catch (err) {
            console.error("Error loading barber reservations:", err);
        }
    }

    const barberForm = document.getElementById("barber-form");
    if (barberForm) {
        barberForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const bUserId = document.getElementById("b-user-id").value;
            const bDate = document.getElementById("b-date").value;
            const bMenu = document.getElementById("b-menu").value;
            const bNotes = document.getElementById("b-notes").value;

            try {
                const res = await fetch("/api/barber/reservations", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: parseInt(bUserId),
                        reservation_date: bDate.replace("T", " "),
                        menu: bMenu,
                        notes: bNotes
                    })
                });
                if (res.ok) {
                    alert("訪問理美容の予約を登録しました。");
                    barberForm.reset();
                    loadBarberReservations();
                }
            } catch (err) {
                console.error("Error creating barber reservation:", err);
            }
        });
    }

    // Initialize Connection
    connectWS();
});
