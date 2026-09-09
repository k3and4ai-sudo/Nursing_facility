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

    // Tabs
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    // 1. Initialize Authentication & Session
    async function initSession() {
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
            const res = await fetch(`/api/family/my_patient?user_code=${encodeURIComponent(userCode)}`);
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
        } catch (err) {
            console.error("Family data fetch error:", err);
            episodeSummaryText.textContent = "現在サーバーと接続できません。後ほど再度ご確認ください。";
        }
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
        episodeSummaryText.textContent = multimedia.summary_text || 
            `本日はスタッフやAIとお話しされ、とても落ち着いてお元気に過ごされています。`;
        
        postcardTitle.textContent = multimedia.card_title || "【デジタル絵手紙】思い出カード";
        if (multimedia.card_image_url) {
            postcardImg.src = multimedia.card_image_url;
        }
        if (postcardRecipient) {
            postcardRecipient.textContent = `${patient.name} 様`;
        }
        if (postcardDate && multimedia.date_str) {
            postcardDate.textContent = multimedia.date_str;
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
            const res = await fetch(`/api/family/reservations?user_code=${encodeURIComponent(userCode)}`);
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
            const res = await fetch("/api/family/reservations", {
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

    // 6. AI Short Movie Canvas Engine (Ken Burns Pan/Zoom + Subtitles + Particles)
    function initMovieCanvas() {
        if (!movieCtx) return;
        drawMovieFrame(0);
    }

    function drawMovieFrame(progressRatio) {
        if (!movieCtx) return;
        const w = movieCanvas.width;
        const h = movieCanvas.height;

        movieCtx.clearRect(0, 0, w, h);

        // Background Warm Paper Fill
        movieCtx.fillStyle = "#fff8f0";
        movieCtx.fillRect(0, 0, w, h);

        // Draw Postcard with Smooth Ken Burns Zoom & Pan
        if (postcardImg && postcardImg.complete) {
            movieCtx.save();
            const scale = 1.0 + progressRatio * 0.15; // Smooth 15% zoom
            const offsetX = Math.sin(progressRatio * Math.PI) * 20;
            const offsetY = progressRatio * 15;

            movieCtx.translate(w / 2 + offsetX, h / 2 + offsetY);
            movieCtx.scale(scale, scale);
            movieCtx.drawImage(postcardImg, -w / 2, -h / 2, w, h);
            movieCtx.restore();
        }

        // Floating Seasonal Particles
        const time = progressRatio * 100;
        if (currentSeason === "spring") {
            movieCtx.fillStyle = "rgba(255, 183, 178, 0.8)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 57 + time * 15) % (w + 40)) - 20;
                const py = ((i * 83 + time * 25) % (h + 40)) - 20;
                movieCtx.beginPath();
                movieCtx.ellipse(px, py, 7, 3.5, (time + i * 12) * 0.05, 0, Math.PI * 2);
                movieCtx.fill();
            }
        } else if (currentSeason === "summer") {
            movieCtx.fillStyle = "rgba(160, 235, 195, 0.75)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 61 + time * 18) % (w + 40)) - 20;
                const py = ((i * 71 + time * 12) % (h + 40)) - 20;
                movieCtx.beginPath();
                movieCtx.arc(px, py, (i % 3) + 2, 0, Math.PI * 2);
                movieCtx.fill();
            }
        } else if (currentSeason === "winter") {
            movieCtx.fillStyle = "rgba(255, 255, 255, 0.85)";
            for (let i = 0; i < 18; i++) {
                const px = ((i * 47 + Math.sin(time * 0.05 + i) * 20) % (w + 40)) - 20;
                const py = ((i * 59 + time * 16) % (h + 40)) - 20;
                movieCtx.beginPath();
                movieCtx.arc(px, py, (i % 3) + 2.5, 0, Math.PI * 2);
                movieCtx.fill();
            }
        } else {
            movieCtx.fillStyle = "rgba(235, 135, 90, 0.75)";
            for (let i = 0; i < 15; i++) {
                const px = ((i * 53 + time * 18) % (w + 40)) - 20;
                const py = ((i * 79 + time * 22) % (h + 40)) - 20;
                movieCtx.beginPath();
                movieCtx.ellipse(px, py, 6, 4, (time + i * 15) * 0.04, 0, Math.PI * 2);
                movieCtx.fill();
            }
        }

        // Subtitle Overlay Banner
        const bannerH = 90;
        const grad = movieCtx.createLinearGradient(0, h - bannerH, 0, h);
        grad.addColorStop(0, "rgba(40, 30, 25, 0)");
        grad.addColorStop(0.3, "rgba(40, 30, 25, 0.75)");
        grad.addColorStop(1, "rgba(40, 30, 25, 0.9)");
        movieCtx.fillStyle = grad;
        movieCtx.fillRect(0, h - bannerH, w, bannerH);

        // Dynamic Subtitle Text based on progress
        const pName = (patientData && patientData.patient) ? patientData.patient.name : "入居者";
        const seasonIcons = { spring: "🌸", summer: "🌻", autumn: "🍁", winter: "❄️" };
        const icon = seasonIcons[currentSeason] || "🎨";
        let subtitleText = `${icon} 【今週の様子】${pName} 様の思い出記録`;
        if (progressRatio > 0.25 && progressRatio <= 0.6) {
            subtitleText = `「昔懐かしい故郷のお山や思い出を嬉しそうにお話しされました」`;
        } else if (progressRatio > 0.6 && progressRatio <= 0.85) {
            subtitleText = `「本日も食欲旺盛で、スタッフと笑顔でご歓談されています」`;
        } else if (progressRatio > 0.85) {
            subtitleText = `ケア・リンク AI見守り | ご家族の面会を心よりお待ちしております`;
        }

        movieCtx.font = "bold 20px 'Zen Maru Gothic', sans-serif";
        movieCtx.fillStyle = "#ffffff";
        movieCtx.textAlign = "center";
        movieCtx.shadowColor = "rgba(0, 0, 0, 0.6)";
        movieCtx.shadowBlur = 8;
        movieCtx.fillText(subtitleText, w / 2, h - 35);
        movieCtx.shadowBlur = 0;
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
            const res = await fetch(`/api/family/my_patient?user_code=${encodeURIComponent(userCode)}&season=${encodeURIComponent(seasonKey)}`);
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
                const link = document.createElement("a");
                link.href = postcardImg.src;
                const pName = (patientData && patientData.patient) ? patientData.patient.name : "絵手紙";
                link.download = `care_link_postcard_${pName}_${currentSeason}.jpg`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
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
