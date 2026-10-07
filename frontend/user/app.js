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

    // 📅 予定カード (Schedule Card UI Elements & State)
    const todaySchedulesCard = document.getElementById("today-schedules-card");
    const todayDateBadge = document.getElementById("today-date-badge");
    const scheduleDatePicker = document.getElementById("schedule-date-picker");
    const btnCloseScheduleCard = document.getElementById("btn-close-schedule-card");
    const btnShowScheduleCard = document.getElementById("btn-show-schedule-card");
    const btnReAnnounceSchedules = document.getElementById("btn-re-announce-schedules");
    const todaySchedulesList = document.getElementById("today-schedules-list");
    const mimamoriScheduleReportCard = document.getElementById("mimamori-schedule-report-card");
    const mimamoriScheduleReportText = document.getElementById("mimamori-schedule-report-text");

    let isScheduleCardVisible = true;
    let scheduleCardHideTimer = null;
    let isBootScheduleAnnouncement = false;
    let currentScheduleAnnouncementAudio = null;
    let currentScheduleAnnouncementText = "";
    let cachedTodaySchedules = [];
    let isAnnouncementPlaying = false;
    let bootAnnouncementTimeout = null;
    const notified2MinScheduleIds = new Set();

    function updateShowScheduleBtnVisibility() {
        if (!btnShowScheduleCard) return;
        // シンプル画面では予定ボタンを表示しない
        if (currentUIMode === "simple") {
            btnShowScheduleCard.classList.add("hidden");
        } else {
            // 詳細画面では予定カードを消すと予定ボタンを表示
            if (!isScheduleCardVisible) {
                btnShowScheduleCard.classList.remove("hidden");
            } else {
                btnShowScheduleCard.classList.add("hidden");
            }
        }
    }

    function hideScheduleCard() {
        if (scheduleCardHideTimer) {
            clearTimeout(scheduleCardHideTimer);
            scheduleCardHideTimer = null;
        }
        if (todaySchedulesCard) {
            todaySchedulesCard.classList.add("hidden");
        }
        isScheduleCardVisible = false;
        console.log("[Schedule Card]: Card hidden.");
        updateShowScheduleBtnVisibility();
    }

    function showScheduleCard(speakAnnouncement = false) {
        if (scheduleCardHideTimer) {
            clearTimeout(scheduleCardHideTimer);
            scheduleCardHideTimer = null;
        }
        if (todaySchedulesCard) {
            todaySchedulesCard.classList.remove("hidden");
        }
        isScheduleCardVisible = true;
        console.log("[Schedule Card]: Card shown. Auto-close timer set for 60 seconds.");
        updateShowScheduleBtnVisibility();

        // 予定カードは60秒で自動で閉じる
        scheduleCardHideTimer = setTimeout(() => {
            console.log("[Schedule Card]: Auto-closing schedule card after 60 seconds.");
            hideScheduleCard();
        }, 60000);

        if (speakAnnouncement && currentScheduleAnnouncementAudio && !isAnnouncementPlaying) {
            if (typeof playScheduleAnnouncement === "function") {
                playScheduleAnnouncement();
            }
        }
    }

    // 🎨 Etegami UI Elements & Handlers
    let isEtegamiCardVisible = false; // ① 初期画面では非表示
    let isEtegamiUpdating = false;
    const etegamiCard = document.getElementById("etegami-card");
    const etegamiShikishiFrame = document.getElementById("etegami-shikishi-frame");
    const btnOpenEtegamiModal = document.getElementById("btn-open-etegami-modal");
    const etegamiModal = document.getElementById("etegami-modal");
    const btnCloseEtegamiModal = document.getElementById("btn-close-etegami-modal");
    const btnCloseEtegamiModalBottom = document.getElementById("btn-close-etegami-modal-bottom");
    const btnShowEtegamiCard = document.getElementById("btn-show-etegami-card");
    const btnCloseEtegamiCard = document.getElementById("btn-close-etegami-card");

    function updateShowEtegamiBtnVisibility() {
        if (!btnShowEtegamiCard) return;
        // ③ シンプル表示モードでは何も表示しません
        if (currentUIMode === "simple") {
            btnShowEtegamiCard.classList.add("hidden");
        } else {
            // ② 詳細表示モードにおいて 表示状態では「デジタル絵手紙」のボタンを表示（カード非表示時にボタン表示、カード表示時は非表示）
            if (!isEtegamiCardVisible) {
                btnShowEtegamiCard.classList.remove("hidden");
            } else {
                btnShowEtegamiCard.classList.add("hidden");
            }
        }
    }

    function showEtegamiCard(forceScroll = true) {
        if (etegamiCard) {
            etegamiCard.classList.remove("hidden");
            if (forceScroll) {
                setTimeout(() => {
                    try {
                        etegamiCard.scrollIntoView({ behavior: "smooth", block: "center" });
                    } catch (e) {}
                }, 100);
            }
        }
        isEtegamiCardVisible = true;
        console.log("[Etegami Card]: Card shown.");
        updateShowEtegamiBtnVisibility();

        // 🎨 開いた時にモード・モデル未決定の場合は「どちらの絵にしますか」から開始し、モデル決定まで他の入力をブロック
        // （完成直後の場合は再度モード確認モーダルを開かない）
        if (currentEtegamiPhase === ETEGAMI_PHASE.COMPLETED) {
            console.log("[Etegami Card]: Suppressed startup mode modal because current phase is COMPLETED.");
            return;
        }
        if (!hasConfirmedEtegamiModeAndEngine) {
            const modeModal = document.getElementById("etegami-mode-confirm-modal");
            if (modeModal) {
                modeModal.classList.remove("hidden");
            }
            isEtegamiModalSelecting = true;
            isEtegamiConfirming = true;
            isModalOpen = true;
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify({ type: "etegami_card_opened" }));
            }
        } else if (typeof setEtegamiPhase === "function" && currentEtegamiPhase === ETEGAMI_PHASE.IDLE) {
            setEtegamiPhase(ETEGAMI_PHASE.LISTENING);
        }
    }

    function hideEtegamiCard() {
        if (etegamiCard) {
            etegamiCard.classList.add("hidden");
        }
        isEtegamiCardVisible = false;
        console.log("[Etegami Card]: Card hidden.");
        updateShowEtegamiBtnVisibility();

        const modeModal = document.getElementById("etegami-mode-confirm-modal");
        const engineModal = document.getElementById("etegami-engine-confirm-modal");
        if (modeModal) modeModal.classList.add("hidden");
        if (engineModal) engineModal.classList.add("hidden");
        if (isEtegamiModalSelecting) {
            isEtegamiModalSelecting = false;
            isEtegamiConfirming = false;
            isModalOpen = false;
        }
    }

    // 🎨 デジタル絵手紙：第一キーワード（対象）× 第二キーワード（アクション）による意図判定
    function checkEtegamiVoiceIntent(text) {
        if (!text) return null;
        const norm = text
            .replace(/[。、.!?！？\s]/g, "")
            .replace(/絵お/g, "絵を")
            .replace(/えお/g, "えを")
            .replace(/手紙お/g, "手紙を")
            .replace(/ベジタル/g, "デジタル")
            .replace(/デジダル/g, "デジタル")
            .replace(/ペテ紙/g, "絵手紙")
            .replace(/ぺてがみ/g, "絵手紙")
            .replace(/ペテガミ/g, "絵手紙")
            .replace(/ベテガミ/g, "絵手紙")
            .replace(/手紙を書きたい/g, "絵手紙を書きたい")
            .replace(/手紙書きたい/g, "絵手紙書きたい");

        // 1. 明確な終了・非表示パターン（絵手紙終了、会話終了、一旦終了、閉じて、消して、やめる等）
        const GENERAL_HIDE_PATTERNS = [
            "一旦終了", "会話終了", "会話は終了", "会話を終了", "終了します", "終了して", "終了",
            "おしまい", "もういいよ", "もうやめる", "やめる", "やめて",
            "閉じてください", "とじてください", "閉じて", "とじて", "閉じる", "とじる", "閉じました", "とじました",
            "消して", "けして", "消す", "けす", "消しました", "けしました",
            "非表示"
        ];
        const ETEGAMI_SPECIFIC_HIDE_PATTERNS = [
            "絵を閉", "絵をとじ", "絵閉", "絵とじ", "絵手紙を閉", "絵手紙をとじ", "絵手紙閉", "絵手紙とじ",
            "絵を消", "絵消", "絵手紙を消", "絵手紙消", "絵手紙終了", "絵を終了", "絵終了",
            "デジタル絵手紙を閉", "デジタル絵手紙閉", "デジタル絵手紙終了", "デジタル絵手紙を終了", "デジタル絵手紙非表示",
            "絵手紙非表示", "絵非表示", "お絵描きをやめる", "お絵描き終了", "お絵描きをおしま", "お絵描きおしま"
        ];

        // 終了アクションが含まれている場合（作成希望キーワード「描きたい」「開いて」等がない限り確実に閉じる）
        const hasGeneralHide = GENERAL_HIDE_PATTERNS.some(p => norm.includes(p));
        const hasEtegamiHide = ETEGAMI_SPECIFIC_HIDE_PATTERNS.some(p => norm.includes(p));
        const hasDrawAction = ["描きたい", "かきたい", "書きたい", "新しく描いて", "出して", "見せて", "開いて", "更新して"].some(k => norm.includes(k));

        if ((hasGeneralHide || hasEtegamiHide) && !hasDrawAction) {
            return false;
        }

        // 会話中の通常発話やシステム案内（「通常会話に戻します」「完成しました」など）はトリガー除外
        if (norm.includes("通常会話") || norm.includes("普通会話") || norm.includes("完成しました") || norm.includes("保存しました")) {
            return null;
        }

        // 2. 絵手紙・お絵描きの対象キーワード（必須）
        const hasExplicitArtWord = [
            "絵手紙", "えてがみ", "デジタル絵手紙", "デジタルえてがみ", "デジタル絵",
            "お絵描き", "お絵かき", "おえかき", "イラスト", "絵を", "絵の", "絵が"
        ].some(w => norm.includes(w));

        if (!hasExplicitArtWord) {
            return null;
        }

        // 3. 意図の明確なアクション動詞（必須：単に「絵手紙」と口にしただけでは起動しない）
        const hasCreationVerb = [
            "描きたい", "かきたい", "書きたい", "描こう", "かこう", "書こう",
            "作りたい", "つくろう", "作ろう", "新しく描いて", "始めたい", "はじめたい", "起動"
        ].some(v => norm.includes(v));

        const hasShowVerb = [
            "開いて", "ひらいて", "開く", "ひらく",
            "出して", "だして", "出したい", "だしたい",
            "表示して", "ひょうじして", "表示",
            "見せて", "みせて", "見たい", "みたい"
        ].some(v => norm.includes(v));

        const isFalseKakitai = ["汗をかき", "汗かき", "恥をかき", "恥かき"].some(f => norm.includes(f));
        if (isFalseKakitai) {
            return null;
        }

        if (hasCreationVerb || hasShowVerb) {
            return true;
        }

        return null;
    }

    function handleEtegamiVoiceTrigger(text, source = "voice") {
        if (isEtegamiConfirming || isEtegamiModalSelecting) {
            console.log(`[Etegami Voice Trigger] (${source}): Blocked voice hide/show trigger because confirmation/selection modal is active: "${text}"`);
            return false;
        }
        // 完成直後10秒間のクールダウン期間中は音声による再起動を防止
        if (window._lastEtegamiCompletedTime && (Date.now() - window._lastEtegamiCompletedTime < 10000)) {
            console.log(`[Etegami Voice Trigger] (${source}): Cooldown active after completion - ignoring trigger.`);
            return false;
        }
        const intent = checkEtegamiVoiceIntent(text);
        if (intent === true) {
            console.log(`[Etegami Voice Trigger] (${source}): Detected SHOW trigger in "${text}"`);
            showEtegamiCard();
            return true;
        } else if (intent === false) {
            console.log(`[Etegami Voice Trigger] (${source}): Detected HIDE trigger in "${text}"`);
            hideEtegamiCard();
            return true;
        }
        return false;
    }
    window.checkEtegamiVoiceIntent = checkEtegamiVoiceIntent;
    window.handleEtegamiVoiceTrigger = handleEtegamiVoiceTrigger;

    if (btnShowEtegamiCard) {
        btnShowEtegamiCard.addEventListener("click", () => {
            console.log("[User UI]: Show Etegami button clicked");
            showEtegamiCard();
        });
    }

    if (btnCloseEtegamiCard) {
        btnCloseEtegamiCard.addEventListener("click", () => {
            console.log("[User UI]: Close Etegami card button (✕) clicked");
            hideEtegamiCard();
        });
    }

    function openEtegamiModal() {
        if (etegamiModal) etegamiModal.classList.remove("hidden");
    }
    function closeEtegamiModal() {
        if (etegamiModal) etegamiModal.classList.add("hidden");
    }
    if (etegamiShikishiFrame) etegamiShikishiFrame.addEventListener("click", openEtegamiModal);
    if (btnOpenEtegamiModal) btnOpenEtegamiModal.addEventListener("click", openEtegamiModal);
    if (btnCloseEtegamiModal) btnCloseEtegamiModal.addEventListener("click", closeEtegamiModal);
    if (btnCloseEtegamiModalBottom) btnCloseEtegamiModalBottom.addEventListener("click", closeEtegamiModal);

    const btnCompleteEtegami = document.getElementById("btn-complete-etegami");
    if (btnCompleteEtegami) {
        btnCompleteEtegami.addEventListener("click", () => {
            console.log("[User UI]: Complete Etegami button clicked");
            if (isEtegamiUpdating) return;
            const updatingBadge = document.getElementById("etegami-updating-badge");
            if (updatingBadge) updatingBadge.classList.remove("hidden");
            isEtegamiUpdating = true;
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify({ type: "complete_etegami" }));
            } else if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "complete_etegami" }));
            }
        });
    }

    // ==========================================
    // 🎨 デジタル絵手紙 4工程シーケンシャル管理
    // ==========================================
    const ETEGAMI_PHASE = {
        IDLE: "idle",                       // 初期・待機
        LISTENING: "listening",             // ① 聞き取り中
        CONFIRM_CONTENT: "confirm_content", // ② 内容確認中
        DRAWING: "drawing",                 // ③ 描画中
        CONFIRM_FINISH: "confirm_finish",   // ④ 完成確認中
        COMPLETED: "completed"              // 完成・保存済み
    };

    let currentEtegamiPhase = ETEGAMI_PHASE.IDLE;
    let currentEtegamiMotif = "";
    let currentEtegamiCalligraphy = "心穏やかに 寄り添う日々";
    let currentEtegamiTranscript = "";
    let currentEtegamiPromptEn = "";
    let etegamiAccumulatedUtterances = [];
    let etegamiAccumulatedText = "";
    let isEtegamiConfirming = false;
    let isEtegamiModalSelecting = false;
    let hasConfirmedEtegamiModeAndEngine = false;
    let isFirstEtegamiLoad = true;
    let hasActiveSessionGeneration = false;
    let lastGeneratedArtworkData = null;
    let lastConfirmFinishOpenTime = 0;
    let lastConfirmContentOpenTime = 0;

    // 🎨 絵手紙ステータスバッジの明確な表示更新ヘルパー
    function setEtegamiStatusBadge(status, customText = "") {
        const statusBadge = document.getElementById("etegami-status-badge");
        if (!statusBadge) return;
        statusBadge.classList.remove("hidden", "badge-drafting", "badge-updating", "badge-ready", "badge-completed");

        if (status === "updating") {
            statusBadge.classList.add("badge-updating");
            statusBadge.innerHTML = `<span class="spin-icon">🎨</span><span>⏳ ${customText || "絵を生成中... (お待ちください)"}</span>`;
        } else if (status === "ready") {
            statusBadge.classList.add("badge-ready");
            statusBadge.innerHTML = `<span>✅</span><span>${customText || "描画完了！ (確認してください)"}</span>`;
        } else if (status === "completed") {
            statusBadge.classList.add("badge-completed");
            statusBadge.innerHTML = `<span>💮</span><span>${customText || "完成・保存済み"}</span>`;
        } else {
            statusBadge.classList.add("badge-drafting");
            statusBadge.innerHTML = `<span>🎨</span><span>${customText || "下絵表示中"}</span>`;
        }
    }
    window.setEtegamiStatusBadge = setEtegamiStatusBadge;

    // 🔄 4工程シーケンシャル状態遷移マネージャー
    function setEtegamiPhase(phase, payload = {}) {
        console.log(`[Etegami Phase Machine]: Transition '${currentEtegamiPhase}' -> '${phase}'`, payload);
        currentEtegamiPhase = phase;

        const pillListening = document.getElementById("step-pill-listening");
        const pillConfirmContent = document.getElementById("step-pill-confirm-content");
        const pillDrawing = document.getElementById("step-pill-drawing");
        const pillConfirmFinish = document.getElementById("step-pill-confirm-finish");

        const listeningPanel = document.getElementById("etegami-listening-panel");
        const motifConfirmModal = document.getElementById("etegami-motif-confirm-modal");
        const artworkConfirmModal = document.getElementById("etegami-artwork-confirm-modal");
        const saveConfirmModal = document.getElementById("etegami-save-confirm-modal");
        const updatingBadge = document.getElementById("etegami-updating-badge");
        const previewImg = document.getElementById("artwork-confirm-preview-img");
        const artworkTitleEl = document.getElementById("artwork-confirm-title");

        // 全ピルのクラスをリセット
        [pillListening, pillConfirmContent, pillDrawing, pillConfirmFinish].forEach(p => {
            if (p) p.classList.remove("active", "done");
        });

        if (phase === ETEGAMI_PHASE.LISTENING) {
            // ① 聞き取り中: 聞き取った内容を表示し、「次へ」ボタンを押すまで継続
            if (pillListening) pillListening.classList.add("active");
            if (listeningPanel) listeningPanel.classList.remove("hidden");
            if (motifConfirmModal) motifConfirmModal.classList.add("hidden");
            if (artworkConfirmModal) artworkConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.add("hidden");

            isEtegamiConfirming = false;
            isEtegamiUpdating = false;
            isModalOpen = false;

            setEtegamiStatusBadge("drafting", "① 描く内容を聞き取り中");

            if (payload.text) {
                updateEtegamiListeningText(payload.text);
            }
        } else if (phase === ETEGAMI_PHASE.CONFIRM_CONTENT) {
            // ② 内容確認中: 「はい」または「いいえ」が押されるまで進まない
            if (pillListening) pillListening.classList.add("done");
            if (pillConfirmContent) pillConfirmContent.classList.add("active");

            if (listeningPanel) listeningPanel.classList.add("hidden");
            if (artworkConfirmModal) artworkConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.add("hidden");

            const motifTarget = document.getElementById("motif-confirm-target");
            const detailsTarget = document.getElementById("motif-confirm-details");
            const calligraphyTarget = document.getElementById("motif-confirm-calligraphy");
            const motifToConfirm = payload.motif || currentEtegamiMotif || currentEtegamiTranscript || "思い出の情景";
            currentEtegamiMotif = motifToConfirm;

            if (motifTarget) motifTarget.textContent = motifToConfirm;
            if (detailsTarget) {
                detailsTarget.textContent = payload.accumulated_text || etegamiAccumulatedText || currentEtegamiTranscript || "（お話しされた内容）";
            }
            if (calligraphyTarget) calligraphyTarget.textContent = payload.calligraphy || currentEtegamiCalligraphy;

            if (motifConfirmModal) {
                motifConfirmModal.classList.remove("hidden");
                try { motifConfirmModal.scrollTop = 0; } catch (e) {}

                const btnOk = document.getElementById("btn-motif-confirm-ok");
                const btnRetry = document.getElementById("btn-motif-confirm-retry");
                if (btnOk) {
                    btnOk.disabled = true;
                    btnOk.style.opacity = "0.6";
                    btnOk.style.pointerEvents = "none";
                }
                if (btnRetry) {
                    btnRetry.disabled = true;
                    btnRetry.style.opacity = "0.6";
                    btnRetry.style.pointerEvents = "none";
                }
                setTimeout(() => {
                    if (btnOk) {
                        btnOk.disabled = false;
                        btnOk.style.opacity = "1";
                        btnOk.style.pointerEvents = "auto";
                    }
                    if (btnRetry) {
                        btnRetry.disabled = false;
                        btnRetry.style.opacity = "1";
                        btnRetry.style.pointerEvents = "auto";
                    }
                }, 800);
            }

            lastConfirmContentOpenTime = Date.now();
            isEtegamiConfirming = true;
            isEtegamiUpdating = false;
            isModalOpen = true;

            setEtegamiStatusBadge("drafting", "② 内容確認中 (はい/いいえ選択)");
            showTemporaryToast(`🎨 みまもりさん：『${motifToConfirm}』を描きますか？画面のボタンをタッチしてくださいね。`, 6000);

            // サーバー（Gemini Live）へ音声案内通知
            const notifyPayload = {
                type: "etegami_motif_confirm_prompt_notice",
                motif: motifToConfirm
            };
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify(notifyPayload));
            } else if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(notifyPayload));
            }
        } else if (phase === ETEGAMI_PHASE.DRAWING) {
            // ③ 描画中: バックエンドでAI描画処理中
            hasActiveSessionGeneration = true;
            if (pillListening) pillListening.classList.add("done");
            if (pillConfirmContent) pillConfirmContent.classList.add("done");
            if (pillDrawing) pillDrawing.classList.add("active");

            if (listeningPanel) listeningPanel.classList.add("hidden");
            if (motifConfirmModal) motifConfirmModal.classList.add("hidden");
            if (artworkConfirmModal) artworkConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.remove("hidden");

            const updatingSub = document.getElementById("updating-text-sub");
            if (updatingSub) {
                updatingSub.textContent = `「${currentEtegamiMotif || '絵手紙'}」を描いています`;
            }

            // 📝 掻き出し・描画中のプロンプト蓄積表示
            const updatingPromptBox = document.getElementById("updating-prompt-box");
            const updatingPromptJa = document.getElementById("updating-prompt-ja");
            const updatingPromptEn = document.getElementById("updating-prompt-en");
            const fullAccText = payload.accumulated_text || etegamiAccumulatedText || currentEtegamiTranscript || "";
            const fullPromptEn = payload.prompt_en || currentEtegamiPromptEn || "";

            if (updatingPromptBox) {
                if (fullAccText || fullPromptEn) {
                    updatingPromptBox.classList.remove("hidden");
                    if (updatingPromptJa) {
                        updatingPromptJa.textContent = fullAccText ? `【要望・会話詳細】: ${fullAccText}` : `【モチーフ】: ${currentEtegamiMotif || '思い出の情景'}`;
                    }
                    if (updatingPromptEn) {
                        updatingPromptEn.textContent = fullPromptEn ? `【AI画像プロンプト】: ${fullPromptEn}` : "";
                    }
                } else {
                    updatingPromptBox.classList.add("hidden");
                }
            }

            isEtegamiConfirming = false;
            isEtegamiUpdating = true;
            isModalOpen = false;

            setEtegamiStatusBadge("updating", "③ AIが絵を描いています...");
            showTemporaryToast("🎨 AIが絵手紙を描いています。少々お待ちください…", 5000);
        } else if (phase === ETEGAMI_PHASE.CONFIRM_FINISH) {
            // ④ 完成確認中: 描き上がった絵手紙の確認。「はい」または「いいえ」が押されるまで進まない
            if (pillListening) pillListening.classList.add("done");
            if (pillConfirmContent) pillConfirmContent.classList.add("done");
            if (pillDrawing) pillDrawing.classList.add("done");
            if (pillConfirmFinish) pillConfirmFinish.classList.add("active");

            if (listeningPanel) listeningPanel.classList.add("hidden");
            if (motifConfirmModal) motifConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.add("hidden");

            const artworkData = payload.data || lastGeneratedArtworkData;
            if (artworkData) {
                if (artworkTitleEl) {
                    artworkTitleEl.textContent = artworkData.title || `【手作り絵手紙】${currentEtegamiMotif || '思い出の風景'}`;
                }
                if (previewImg && artworkData.image_url) {
                    const cacheBuster = Date.now();
                    previewImg.src = artworkData.image_url.includes("?") 
                        ? `${artworkData.image_url}&t=${cacheBuster}` 
                        : `${artworkData.image_url}?t=${cacheBuster}`;
                }
            }

            // 📝 完成確認画面でもプロンプトの蓄積を表示
            const confirmPromptContainer = document.getElementById("artwork-confirm-prompt-container");
            const confirmPromptJa = document.getElementById("artwork-confirm-prompt-ja");
            const confirmPromptEn = document.getElementById("artwork-confirm-prompt-en");
            const finishAccText = (artworkData && artworkData.accumulated_text) || etegamiAccumulatedText || currentEtegamiTranscript || "";
            const finishPromptEn = (artworkData && (artworkData.prompt_en || (artworkData.image_generation_prompt && artworkData.image_generation_prompt.positive_prompt))) || currentEtegamiPromptEn || "";

            if (confirmPromptContainer) {
                if (finishAccText || finishPromptEn) {
                    confirmPromptContainer.classList.remove("hidden");
                    if (confirmPromptJa) {
                        confirmPromptJa.textContent = finishAccText ? `【要望・会話詳細】: ${finishAccText}` : `【モチーフ】: ${currentEtegamiMotif || '思い出の情景'}`;
                    }
                    if (confirmPromptEn) {
                        confirmPromptEn.textContent = finishPromptEn ? `【AI画像プロンプト】: ${finishPromptEn}` : "";
                    }
                } else {
                    confirmPromptContainer.classList.add("hidden");
                }
            }

            if (artworkConfirmModal) {
                artworkConfirmModal.classList.remove("hidden");
                try { artworkConfirmModal.scrollTop = 0; } catch (e) {}

                const btnOk = document.getElementById("btn-artwork-confirm-ok");
                const btnRetry = document.getElementById("btn-artwork-confirm-retry");
                if (btnOk) {
                    btnOk.disabled = true;
                    btnOk.style.opacity = "0.6";
                    btnOk.style.pointerEvents = "none";
                }
                if (btnRetry) {
                    btnRetry.disabled = true;
                    btnRetry.style.opacity = "0.6";
                    btnRetry.style.pointerEvents = "none";
                }
                setTimeout(() => {
                    if (btnOk) {
                        btnOk.disabled = false;
                        btnOk.style.opacity = "1";
                        btnOk.style.pointerEvents = "auto";
                    }
                    if (btnRetry) {
                        btnRetry.disabled = false;
                        btnRetry.style.opacity = "1";
                        btnRetry.style.pointerEvents = "auto";
                    }
                }, 800);
            }

            lastConfirmFinishOpenTime = Date.now();
            isEtegamiConfirming = true;
            isEtegamiUpdating = false;
            isModalOpen = true;

            setEtegamiStatusBadge("ready", "④ 完成確認中 (はい/いいえ選択)");
            showTemporaryToast("✨ 絵が描き上がりました！この絵でよろしいですか？画面のボタンをタッチしてくださいね。", 7000);

            // サーバー（Gemini Live）へ音声案内通知
            const notifyPayload = {
                type: "etegami_artwork_ready",
                title: (artworkData && artworkData.title) ? artworkData.title : (currentEtegamiMotif || "手作り絵手紙")
            };
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                liveWs.send(JSON.stringify(notifyPayload));
            } else if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(notifyPayload));
            }
        } else if (phase === ETEGAMI_PHASE.COMPLETED) {
            // 💮 完成・保存済み
            if (pillListening) pillListening.classList.add("done");
            if (pillConfirmContent) pillConfirmContent.classList.add("done");
            if (pillDrawing) pillDrawing.classList.add("done");
            if (pillConfirmFinish) pillConfirmFinish.classList.add("done");

            if (listeningPanel) listeningPanel.classList.add("hidden");
            if (motifConfirmModal) motifConfirmModal.classList.add("hidden");
            if (artworkConfirmModal) artworkConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.add("hidden");

            isEtegamiConfirming = false;
            isEtegamiUpdating = false;
            isModalOpen = false;

            setEtegamiStatusBadge("completed", "💮 完成・保存済み");

            // 終了処理：次回の絵手紙開始に向けてモード選択状態等をリセット
            hasConfirmedEtegamiModeAndEngine = false;
            currentEtegamiMotif = "";
            currentEtegamiTranscript = "";
            window._lastEtegamiCompletedTime = Date.now();

            // UI通知と音声案内「通常会話に戻します」を実行
            if (typeof showTemporaryToast === "function") {
                showTemporaryToast("💮 絵手紙が完成しました。通常会話に戻します。", 5000);
            } else if (typeof showUIToast === "function") {
                showUIToast("💮 絵手紙が完成しました。通常会話に戻します。", "simple");
            }
            if (typeof playTTSVoice === "function") {
                playTTSVoice("絵手紙が完成しました。通常会話に戻します。", true);
            }

            // 完成・保存の余韻を少し表示した後、色紙カードを閉じて通常会話状態(IDLE)へ戻す
            if (window._etegamiCompletedCloseTimer) clearTimeout(window._etegamiCompletedCloseTimer);
            window._etegamiCompletedCloseTimer = setTimeout(() => {
                console.log("[Etegami Card]: Closing card and returning to IDLE (normal conversation).");
                hideEtegamiCard();
                currentEtegamiPhase = ETEGAMI_PHASE.IDLE;
            }, 3000);
        } else {
            // IDLE
            if (listeningPanel) listeningPanel.classList.add("hidden");
            if (motifConfirmModal) motifConfirmModal.classList.add("hidden");
            if (artworkConfirmModal) artworkConfirmModal.classList.add("hidden");
            if (saveConfirmModal) saveConfirmModal.classList.add("hidden");
            if (updatingBadge) updatingBadge.classList.add("hidden");
            isEtegamiConfirming = false;
            isEtegamiUpdating = false;
        }
    }
    window.setEtegamiPhase = setEtegamiPhase;

    // 互換性ラッパー（外部やレガシーハンドラからの呼び出し用）
    function showArtworkConfirmModal(data) {
        setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_FINISH, { data: data });
    }
    window.showArtworkConfirmModal = showArtworkConfirmModal;

    function showSaveConfirmModal() {
        setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_FINISH);
    }
    window.showSaveConfirmModal = showSaveConfirmModal;

    // 👂 聞き取りテキスト更新ヘルパー（「この内容で次に進む」が押されるまで連続で蓄積・表示）
    function updateEtegamiListeningText(text) {
        if (!text) return;
        // 完成・保存済みの時は更新しない
        if (currentEtegamiPhase === ETEGAMI_PHASE.COMPLETED) {
            return;
        }
        const clean = text.trim();
        if (!clean) return;

        // 聞き取った文字列を連続で蓄積
        const lastIdx = etegamiAccumulatedUtterances.length - 1;
        if (lastIdx >= 0) {
            const lastUtterance = etegamiAccumulatedUtterances[lastIdx];
            if (clean === lastUtterance) {
                // 完全重複はスキップ
                return;
            }
            if (clean.startsWith(lastUtterance) || (clean.length > lastUtterance.length && clean.includes(lastUtterance))) {
                // 直前発話の途中経過・補完（長くなった差分に置き換え）
                etegamiAccumulatedUtterances[lastIdx] = clean;
            } else if (lastUtterance.startsWith(clean)) {
                // 直前発話より短いPrefixはスキップ
                return;
            } else {
                // 新しい文・発話として追加
                etegamiAccumulatedUtterances.push(clean);
            }
        } else {
            etegamiAccumulatedUtterances.push(clean);
        }

        // 句読点で自然に連結して連続表示テキストを作成
        etegamiAccumulatedText = etegamiAccumulatedUtterances
            .map(u => u.replace(/[。、]+$/, ""))
            .filter(Boolean)
            .join("。");
        if (etegamiAccumulatedText && !etegamiAccumulatedText.endsWith("。")) {
            etegamiAccumulatedText += "。";
        }

        currentEtegamiTranscript = etegamiAccumulatedText;
        const listeningTextEl = document.getElementById("etegami-listening-text");
        if (listeningTextEl) {
            listeningTextEl.textContent = etegamiAccumulatedText;
            listeningTextEl.scrollTop = listeningTextEl.scrollHeight;
        }

        // キーワード抽出してモチーフ候補を自動更新
        const candidates = [
            "座敷を走るスマートなマルチーズ", "スマートなマルチーズ", "座敷を走るマルチーズ", "マルチーズ",
            "座敷の中で子犬が走っている", "座敷の中で犬が走っている", "座敷の中を走る子犬", "座敷の中を走る犬",
            "座敷の中を走り回る犬", "座敷を走り回る犬", "座敷で走り回る犬", "座敷を走り回る白い犬", "座敷を走る白い犬",
            "座敷で走る子犬", "座敷で走る犬", "座敷を走る子犬", "座敷を走る犬",
            "こちらに向かって走る犬", "こちらに走る犬", "走ってくる犬", "走る白い犬", "走る子犬", "走る犬",
            "座敷と子犬", "座敷と白い犬", "座敷と犬", "座敷の風景", "座敷",
            "白い子犬", "白い犬", "子犬", "柴犬", "わんこ", "犬",
            "三毛猫", "子猫", "猫", "黒板", "生徒の机", "机", "先生", "教室", "学校",
            "文化祭", "学園祭", "喫茶店", "喫茶", "純喫茶", "カフェ", "コーヒー", "珈琲",
            "夕焼け", "夕暮れ", "夕日", "夕陽", "縁側", "お茶",
            "小鳥", "雀", "すずめ", "ことり", "運動会", "お弁当", "煮物", "昭和",
            "桜", "さくら", "花見", "お花見", "朝顔", "風鈴", "向日葵", "ひまわり",
            "雪景色", "雪", "椿", "つばき", "コスモス", "秋桜", "紅葉", "もみじ", "富士山", "海", "山"
        ];
        for (const c of candidates) {
            if (currentEtegamiTranscript.includes(c)) {
                currentEtegamiMotif = c;
                break;
            }
        }
        if (!currentEtegamiMotif && currentEtegamiTranscript.length > 0) {
            const cleanNoPunct = currentEtegamiTranscript.replace(/[。、！？\s]/g, "");
            if (cleanNoPunct.length > 0) {
                currentEtegamiMotif = cleanNoPunct.length > 24 ? cleanNoPunct.substring(0, 24) : cleanNoPunct;
            }
        }
    }
    window.updateEtegamiListeningText = updateEtegamiListeningText;

    function updateEtegamiDisplay(data) {
        if (!data) return;
        if (data.force_open === true && !data.is_completed) {
            showEtegamiCard();
        }
        // Note: Do NOT hide motifConfirmModal here to prevent premature modal dismissal while user is confirming
        const listeningBadgeEl = document.getElementById("etegami-listening-badge");
        if (listeningBadgeEl) listeningBadgeEl.classList.add("hidden");

        const cardImg = document.getElementById("etegami-card-img");
        const cardImgNext = document.getElementById("etegami-card-img-next");
        const calligraphyEl = document.getElementById("etegami-calligraphy");
        const stampEl = document.getElementById("etegami-stamp");
        const titleEl = document.getElementById("etegami-title");
        const dateEl = document.getElementById("etegami-date");
        const seasonTagEl = document.getElementById("etegami-season-tag");
        const updatingBadge = document.getElementById("etegami-updating-badge");

        const modalImg = document.getElementById("etegami-modal-img");
        const modalCalligraphy = document.getElementById("etegami-modal-calligraphy");
        const modalStamp = document.getElementById("etegami-modal-stamp");
        const modalTitle = document.getElementById("etegami-modal-title");
        const modalSeasonTag = document.getElementById("etegami-modal-season-tag");

        const rawUrl = data.image_url || "/family/assets/sample_postcard.jpg";
        const cacheBuster = Date.now();
        const newUrl = rawUrl.includes("?") ? `${rawUrl}&t=${cacheBuster}` : `${rawUrl}?t=${cacheBuster}`;
        const newTitle = data.title || "【手作り絵手紙】";
        const newCalligraphy = data.calligraphy || "心穏やかに 寄り添う日々";
        const newStamp = data.stamp_icon || "🌸";
        const seasonMap = { "spring": "🌸 春", "summer": "🌻 夏", "autumn": "🍁 秋", "winter": "❄️ 冬" };
        const seasonText = seasonMap[data.season] || (data.season ? `🌿 ${data.season}` : "🍁 秋");
        const dateText = data.date_str || new Date().toLocaleDateString('ja-JP', { year: 'numeric', month: 'long' });

        const voiceHint = document.getElementById("etegami-voice-hint");
        if (data.is_updating === true) {
            hasActiveSessionGeneration = true; // Actively generating new artwork in this session
            if (updatingBadge) updatingBadge.classList.remove("hidden");
            if (voiceHint) voiceHint.classList.remove("hidden");
            setEtegamiStatusBadge("updating");
        } else {
            if (updatingBadge) updatingBadge.classList.add("hidden");
            if (voiceHint) voiceHint.classList.add("hidden");
        }

        // Auto show etegami card if force_open is requested
        if (data.force_open === true && typeof showEtegamiCard === "function") {
            showEtegamiCard();
        }

        // Smooth cross-fade transition with cache-busting
        if (cardImg && cardImgNext) {
            const imgLoader = new Image();
            imgLoader.onload = () => {
                cardImgNext.src = newUrl;
                cardImgNext.classList.add("current");
                cardImgNext.classList.remove("next");
                cardImg.classList.add("next");
                cardImg.classList.remove("current");

                setTimeout(() => {
                    cardImg.src = newUrl;
                    cardImg.classList.add("current");
                    cardImg.classList.remove("next");
                    cardImgNext.classList.add("next");
                    cardImgNext.classList.remove("current");
                    if (updatingBadge) updatingBadge.classList.add("hidden");
                    isEtegamiUpdating = false;

                    // 🎨 描画更新が完了したタイミングで「完成確認中」へ確実に遷移！
                    lastGeneratedArtworkData = data;
                    if (data.is_completed) {
                        setEtegamiPhase(ETEGAMI_PHASE.COMPLETED);
                    } else if (data.is_initial || isFirstEtegamiLoad) {
                        setEtegamiStatusBadge("drafting");
                    } else {
                        // ユーザーセッションで生成された新しい絵手紙は例外なく④完成確認中へ遷移！
                        hasActiveSessionGeneration = false;
                        setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_FINISH, { data: data });
                    }
                    isFirstEtegamiLoad = false;
                }, 850);
            };
            imgLoader.onerror = () => {
                console.warn("[Etegami Image]: Failed to load image:", newUrl);
                cardImg.src = rawUrl;
                if (updatingBadge) updatingBadge.classList.add("hidden");
                isEtegamiUpdating = false;
                lastGeneratedArtworkData = data;
                if (data.is_completed) {
                    setEtegamiPhase(ETEGAMI_PHASE.COMPLETED);
                } else if (!data.is_initial && !isFirstEtegamiLoad) {
                    hasActiveSessionGeneration = false;
                    setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_FINISH, { data: data });
                }
                isFirstEtegamiLoad = false;
            };
            imgLoader.src = newUrl;
        } else if (cardImg) {
            cardImg.src = newUrl;
            if (updatingBadge) updatingBadge.classList.add("hidden");
            isEtegamiUpdating = false;
            lastGeneratedArtworkData = data;
            if (data.is_completed) {
                setEtegamiPhase(ETEGAMI_PHASE.COMPLETED);
            } else if (!data.is_initial && !isFirstEtegamiLoad) {
                hasActiveSessionGeneration = false;
                setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_FINISH, { data: data });
            }
            isFirstEtegamiLoad = false;
        }

        if (calligraphyEl) calligraphyEl.textContent = newCalligraphy;
        if (stampEl) stampEl.textContent = newStamp;
        if (titleEl) titleEl.textContent = newTitle;
        if (dateEl) dateEl.textContent = dateText;
        if (seasonTagEl) seasonTagEl.textContent = seasonText;

        if (modalImg) modalImg.src = newUrl;
        if (modalCalligraphy) modalCalligraphy.textContent = newCalligraphy;
        if (modalStamp) modalStamp.textContent = newStamp;
        if (modalTitle) modalTitle.textContent = newTitle;
        if (modalSeasonTag) modalSeasonTag.textContent = seasonText;

        const statusBadge = document.getElementById("etegami-status-badge");
        const completeBtn = document.getElementById("btn-complete-etegami");
        const isCompleted = !!data.is_completed;

        if (statusBadge) {
            statusBadge.classList.remove("hidden");
            if (data.is_updating === true) {
                statusBadge.className = "etegami-status-badge badge-updating";
                statusBadge.innerHTML = "<span class='spin-icon'>✨</span><span>絵手紙を描いています…</span>";
            } else if (isCompleted) {
                statusBadge.className = "etegami-status-badge badge-completed";
                statusBadge.innerHTML = "<span>💮</span><span>ご本人様と完成</span>";
            } else {
                statusBadge.className = "etegami-status-badge badge-drafting";
                statusBadge.innerHTML = "<span>🎨</span><span>下絵表示中</span>";
            }
        }

        // 🏷️ 絵手紙 描画エンジンバッジ & セレクターの更新
        const engineBadge = document.getElementById("etegami-engine-badge");
        const modalEngineBadge = document.getElementById("etegami-modal-engine-badge");

        let engineType = "free";
        let engineName = "🟢 無料AI (Pollinations)";
        let engineDesc = "Pollinations.ai 完全無料AI画像生成";

        if (data.engine === "pollinations" || data.engine_type === "cloud_free") {
            engineType = "free";
            engineName = "🟢 無料AI (Pollinations)";
            engineDesc = "Pollinations.ai 完全無料AI画像生成（登録不要）";
        } else if (data.engine === "gemini_imagen" || data.engine_type === "cloud_paid") {
            engineType = "paid";
            engineName = "🔵 Google Image (有料)";
            engineDesc = "Google AI Studio クラウド画像生成 (有料版)";
        } else if (data.image_url && (data.image_url.includes("sample_postcard") || data.image_url.includes("generated_relaxation") || data.image_url.includes("generated_healing") || data.image_url.includes("generated_classroom") || data.image_url.includes("generated_bunkasai") || data.image_url.includes("generated_kissaten") || data.image_url.includes("generated_undoukai"))) {
            engineType = "preset";
            engineName = "🍁 季節アーカイブ";
            engineDesc = "施設選定アーカイブ絵手紙";
        } else if (data.api_notice || data.engine === "local_watercolor") {
            engineType = "local";
            engineName = "🖌️ 自立水彩画 (Local)";
            engineDesc = data.api_notice ? `自立水彩画エンジン (${data.api_notice})` : "ローカル水彩画エンジン（通信障害やAPI制限時も手元PCで即時自立描画）";
        }

        const updateEngineBadgeEl = (el) => {
            if (!el) return;
            el.className = `etegami-engine-badge badge-engine-${engineType}`;
            el.textContent = engineName;
            el.title = `描画エンジン: ${engineDesc}`;
        };
        updateEngineBadgeEl(engineBadge);
        updateEngineBadgeEl(modalEngineBadge);

        if (typeof updateEngineToggleUI === "function") {
            updateEngineToggleUI(data.engine === "gemini_imagen" ? "google_image" : "pollinations");
        }

        if (completeBtn) {
            if (isCompleted) {
                completeBtn.classList.add("completed-done");
                completeBtn.innerHTML = "<span>💮</span><span>完成済み</span>";
                completeBtn.disabled = true;
            } else {
                completeBtn.classList.remove("completed-done");
                completeBtn.innerHTML = "<span>💮</span><span>完成</span>";
                completeBtn.disabled = false;
            }
            if (data.is_updating === true) {
                completeBtn.classList.remove("hidden");
            } else {
                completeBtn.classList.add("hidden");
            }
        }

        console.log("[Etegami Display Updated]:", newTitle, newCalligraphy, "isCompleted=", isCompleted);
        if (data.is_initial === true || isFirstEtegamiLoad || !hasActiveSessionGeneration) {
            isFirstEtegamiLoad = false;
        } else {
            if (isCompleted) {
                if (typeof showTemporaryToast === "function") {
                    showTemporaryToast(`💮 絵手紙が完成しました。通常会話に戻します。`, 5000);
                } else if (typeof showUIToast === "function") {
                    showUIToast(`💮 絵手紙が完成しました。通常会話に戻します。`, "simple");
                }
            } else {
                // New or updated artwork ready: prominently show and center card
                showEtegamiCard(true);
                if (typeof showTemporaryToast === "function") {
                    showTemporaryToast(`🎨 みまもりさん：新しい絵手紙を描きました（${newTitle}）`, 5500);
                } else if (typeof showUIToast === "function") {
                    showUIToast(`🎨 みまもりさん：新しい絵手紙を描きました（${newTitle}）`, "simple");
                }
            }
        }
        if (data && data.force_open === true && !isCompleted) {
            showEtegamiCard(true);
        }
    }

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

    // ==========================================================
    // 🌿 UI Mode (Simple vs Detailed) Management
    // ==========================================================
    // Default to 'simple' mode on startup
    let currentUIMode = "simple";
    let lastUIModeChangeTime = 0;

    function showUIToast(message, type = "simple") {
        let toast = document.getElementById("ui-mode-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "ui-mode-toast";
            toast.className = "ui-mode-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.className = `ui-mode-toast ${type} show`;
        clearTimeout(window.uiToastTimer);
        window.uiToastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, 2500);
    }

    function setUIMode(mode, showToast = true, force = false) {
        const targetMode = mode === "simple" ? "simple" : "detailed";
        
        // Prevent duplicate switching if already in target mode (Idempotency)
        if (!force && currentUIMode === targetMode) {
            console.log("[Care-Link UI Mode]: Already in target mode:", targetMode, "(skipping duplicate)");
            return false;
        }

        currentUIMode = targetMode;
        lastUIModeChangeTime = Date.now();
        localStorage.setItem("carelink_ui_mode", currentUIMode);
        console.log("[Care-Link UI Mode]: Switched to", currentUIMode);

        if (currentUIMode === "simple") {
            document.body.classList.add("simple-mode");
            try {
                if (window.eruda) {
                    window.eruda.hide();
                    const erudaEl = document.getElementById("eruda");
                    if (erudaEl) erudaEl.style.display = "none";
                }
            } catch (e) {}
            if (showToast) {
                showUIToast("🌿 シンプル画面に切り替えました", "simple");
            }
        } else {
            document.body.classList.remove("simple-mode");
            try {
                if (window.eruda) {
                    const erudaEl = document.getElementById("eruda");
                    if (erudaEl) erudaEl.style.display = "";
                }
            } catch (e) {}
            if (showToast) {
                showUIToast("📋 詳細画面に切り替えました", "detailed");
            }
        }
        if (typeof updateShowScheduleBtnVisibility === "function") {
            updateShowScheduleBtnVisibility();
        }
        if (typeof updateShowEtegamiBtnVisibility === "function") {
            updateShowEtegamiBtnVisibility();
        }
        return true;
    }

    // Start in Simple Mode by default unless ui=detailed is requested in URL
    const initialUIMode = (urlParams.get("ui") === "detailed" || urlParams.get("mode") === "detailed") ? "detailed" : "simple";
    setUIMode(initialUIMode, false, true);

    if (roomBadge) {
        roomBadge.style.cursor = "pointer";
        roomBadge.title = "タップでシンプル画面／詳細画面を切り替え";
        roomBadge.addEventListener("click", () => {
            setUIMode(currentUIMode === "simple" ? "detailed" : "simple", true);
        });
    }

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
            if (typeof updateEtegamiListeningText === "function" && (currentEtegamiPhase === ETEGAMI_PHASE.LISTENING || isEtegamiCardVisible)) {
                updateEtegamiListeningText(clean);
            }

            // Instant client-side trigger for confidential recording stop/resume
            const STOP_KEYWORDS = [
                "ここだけの話", "内緒", "言わんといて", "言わないで", "記録を止めて", "記録止めて",
                "秘密", "メモせんといて", "誰にも言わないで", "記録停止", "記録を停止", "録音停止",
                "録音を停止", "記録しないで", "記録やめて", "きろくていし"
            ];
            const RESUME_KEYWORDS = [
                "記録再開", "記録を再開", "内緒話はおしまい", "秘密はおしまい", "通常の会話に戻",
                "普通の会話に戻", "録音再開", "録音を再開", "記録していい", "きろくさいかい"
            ];

            if (STOP_KEYWORDS.some(k => clean.includes(k))) {
                console.log("[SpeechRec Confidential Mode]: Instant client stop trigger:", clean);
                const changed = handleRecordingStatus(false, "会話記録停止");
                if (changed && liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "stop_recording", text: clean }));
                }
            } else if (RESUME_KEYWORDS.some(k => clean.includes(k))) {
                console.log("[SpeechRec Confidential Mode]: Instant client resume trigger:", clean);
                const changed = handleRecordingStatus(true, "会話記録再開");
                if (changed && liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "resume_recording", text: clean }));
                }
            }

            // UI Mode voice commands (みまもりさん音声切り替え)
            const TO_SIMPLE_COMMANDS = [
                "画面を簡単にして", "単純な画面にして", "シンプルな画面にして", "シンプル画面にして",
                "画面簡単にして", "単純画面にして", "かんたんながめんにして", "たんじゅんながめんにして",
                "シンプル画面に切り替えて", "単純画面に切り替えて", "画面をシンプルにして", "画面シンプルにして",
                "シンプル画面に切り替え", "単純画面に切り替え", "簡単にして", "シンプルにして"
            ];
            const TO_DETAILED_COMMANDS = [
                "詳細画面にして", "元の画面にして", "画面を戻して", "詳しい画面にして",
                "詳細な画面にして", "元の画面戻して", "しょうさいがめんにして", "詳細画面に切り替えて",
                "詳細画面に切り替え", "元に戻して", "画面戻して"
            ];

            const isSwitchGeneric = (clean.includes("画面") && clean.includes("切り替")) || clean.includes("画面変えて");

            if (TO_SIMPLE_COMMANDS.some(cmd => clean.includes(cmd)) || (currentUIMode === "detailed" && isSwitchGeneric)) {
                console.log("[SpeechRec UI Mode]: Voice triggered Simple Mode:", clean);
                const changed = setUIMode("simple", true);
                if (changed && liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "client_ui_mode", mode: "simple" }));
                }
            } else if (TO_DETAILED_COMMANDS.some(cmd => clean.includes(cmd)) || (currentUIMode === "simple" && isSwitchGeneric)) {
                console.log("[SpeechRec UI Mode]: Voice triggered Detailed Mode:", clean);
                const changed = setUIMode("detailed", true);
                if (changed && liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "client_ui_mode", mode: "detailed" }));
                }
            }

            // Schedule Card voice commands (予定カードの表示・終了)
            const SHOW_SCHEDULE_COMMANDS = [
                "予定を教えて", "スケジュールを教えて", "予定を出して", "スケジュールを出して",
                "予定見せて", "スケジュール見せて", "予定表示して", "スケジュール表示して",
                "予定を表示して", "スケジュールを表示して", "予定を見せて", "スケジュールを見せて",
                "今日の予定教えて", "今日のスケジュール教えて", "予定教えて", "スケジュール教えて",
                "予定出して", "スケジュール出して", "予定カード出して", "予定カードを出して",
                "よていをおしえて", "すけじゅーるをおしえて", "よていをだして", "すけじゅーるをだして"
            ];
            const HIDE_SCHEDULE_COMMANDS = [
                "予定ありがとう", "スケジュールありがとう", "予定を消して", "スケジュールを消して",
                "予定消して", "スケジュール消して", "予定閉じて", "スケジュール閉じて",
                "予定を閉じて", "スケジュールを閉じて", "予定カード消して", "予定カードを消して",
                "予定終了", "スケジュール終了", "よていありがとう", "すけじゅーるありがとう",
                "よていをけして", "すけじゅーるをけして", "よていけして", "すけじゅーるけして"
            ];

            if (SHOW_SCHEDULE_COMMANDS.some(cmd => clean.includes(cmd))) {
                console.log("[SpeechRec Schedule]: Voice triggered SHOW schedule card:", clean);
                if (typeof showScheduleCard === "function") {
                    showScheduleCard(true);
                }
            } else if (HIDE_SCHEDULE_COMMANDS.some(cmd => clean.includes(cmd))) {
                console.log("[SpeechRec Schedule]: Voice triggered HIDE schedule card:", clean);
                if (typeof hideScheduleCard === "function") {
                    hideScheduleCard();
                }
            }

            // 🎨 Etegami Card voice commands (デジタル絵手紙カードの表示・終了: 第一キーワード × 第二キーワード)
            handleEtegamiVoiceTrigger(clean, "WebSpeechRec");
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

    isDebugMode = urlParams.get("debug") === "true" || urlParams.get("eruda") === "true" || localStorage.getItem("nursing_debug_mode") === "true";
    function ensureErudaLoaded() {
        if (!window.eruda && !document.getElementById("eruda-script")) {
            const script = document.createElement("script");
            script.id = "eruda-script";
            script.src = "https://cdn.jsdelivr.net/npm/eruda";
            script.onload = () => {
                if (window.eruda) {
                    window.eruda.init();
                    console.log("[Care-Link] 🛠️ Eruda Mobile DevTools Loaded dynamically");
                }
            };
            document.head.appendChild(script);
        }
    }

    const headerBtnCopyLogs = document.getElementById("header-btn-copy-logs");
    function updateDebugUI() {
        if (isDebugMode && systemInfo.enable_debug_mode) {
            if (debugBadge) debugBadge.classList.remove("hidden");
            if (headerBtnCopyLogs) headerBtnCopyLogs.classList.remove("hidden");
            localStorage.setItem("nursing_debug_mode", "true");
            ensureErudaLoaded();
            if (typeof connectLiveWS === "function" && (!liveWs || liveWs.readyState !== WebSocket.OPEN)) {
                connectLiveWS();
            }
        } else {
            if (debugBadge) debugBadge.classList.add("hidden");
            if (headerBtnCopyLogs) headerBtnCopyLogs.classList.add("hidden");
            localStorage.setItem("nursing_debug_mode", "false");
        }
    }
    if (isDebugMode) {
        ensureErudaLoaded();
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

    let hasAnnouncedTodaySchedulesOnBoot = false;
    let isCheckingRegistration = false;
    let isLoadingSchedules = false;

    // Fetch user details from Server API
    async function checkRegistration(triggerAnnouncement = false) {
        if (isCheckingRegistration) {
            console.log("[checkRegistration]: Already checking registration, skipping duplicate call.");
            return true;
        }
        isCheckingRegistration = true;
        try {
            const response = await fetch(`/api/users/terminal/${terminalId}`);
            if (response.status === 404) {
                if (isDebugMode && terminalId !== "user_tablet_1") {
                    console.log("Unregistered terminal in debug mode, auto-fallback to user_tablet_1");
                    terminalId = "user_tablet_1";
                    localStorage.setItem("nursing_terminal_id", terminalId);
                    if (displayTerminalId) displayTerminalId.textContent = terminalId;
                    isCheckingRegistration = false;
                    return await checkRegistration(triggerAnnouncement);
                }
                showRegisterScreen();
                return false;
            }
            if (!response.ok) throw new Error("API Error");
            
            userDetails = await response.json();
            roomBadge.textContent = `${userDetails.room_number}号室 ${userDetails.name}様`;
            hideRegisterScreen();
            micBtn.disabled = false;
            // 📅 起動時に本日のご予定を読み込み (カードは非表示で保持し、勝手な音声案内は行いません)
            if (typeof loadTodaySchedules === "function") {
                loadTodaySchedules(false);
            }
            return true;
        } catch (err) {
            console.error("Error fetching user details:", err);
            statusText.textContent = "サーバーに接続できません";
            return false;
        } finally {
            isCheckingRegistration = false;
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
            micBtn.disabled = false;
            statusText.textContent = "お話しする準備ができました";
            if (!userDetails) {
                const registered = await checkRegistration(false);
                if (!registered) {
                    statusText.textContent = "端末の登録をお待ちしています...";
                    micBtn.disabled = true;
                }
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
                    if (data.text) {
                        handleEtegamiVoiceTrigger(data.text, "StandardWS_Transcription");
                        if (typeof updateEtegamiListeningText === "function" && (currentEtegamiPhase === ETEGAMI_PHASE.LISTENING || isEtegamiCardVisible)) {
                            updateEtegamiListeningText(data.text);
                        }
                    }
                    break;

                case "ui_mode_change":
                    console.log("[User WS]: Received ui_mode_change ->", data.mode);
                    setUIMode(data.mode, true);
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

                case "etegami_listening":
                    const lBadge = document.getElementById("etegami-listening-badge");
                    if (lBadge) {
                        if (data.listening) lBadge.classList.remove("hidden");
                        else lBadge.classList.add("hidden");
                    }
                    break;

                case "etegami_motif_confirm_prompt":
                    if (data.motif) {
                        currentEtegamiMotif = data.motif;
                        if (typeof updateEtegamiListeningText === "function") {
                            updateEtegamiListeningText(data.motif);
                        }
                    }
                    if (data.calligraphy) currentEtegamiCalligraphy = data.calligraphy;
                    if (currentEtegamiPhase === ETEGAMI_PHASE.CONFIRM_CONTENT) {
                        setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_CONTENT, data);
                    }
                    break;

                case "etegami_motif_confirm_dismiss":
                    const confModal2 = document.getElementById("etegami-motif-confirm-modal");
                    if (confModal2) confModal2.classList.add("hidden");
                    const lBadge3 = document.getElementById("etegami-listening-badge");
                    if (lBadge3) lBadge3.classList.add("hidden");
                    isEtegamiConfirming = false;
                    isModalOpen = false;
                    break;

                case "etegami_mode_confirm_prompt":
                    const modeModalMain = document.getElementById("etegami-mode-confirm-modal");
                    if (modeModalMain) modeModalMain.classList.remove("hidden");
                    isEtegamiConfirming = true;
                    isModalOpen = true;
                    break;

                case "etegami_mode_confirm_dismiss":
                    const modeModalMain2 = document.getElementById("etegami-mode-confirm-modal");
                    if (modeModalMain2) modeModalMain2.classList.add("hidden");
                    isEtegamiConfirming = false;
                    isModalOpen = false;
                    break;

                case "etegami_engine_confirm_prompt":
                    const engModalMain = document.getElementById("etegami-engine-confirm-modal");
                    if (engModalMain) engModalMain.classList.remove("hidden");
                    isEtegamiConfirming = true;
                    isModalOpen = true;
                    break;

                case "etegami_engine_updated":
                    const engModalMain2 = document.getElementById("etegami-engine-confirm-modal");
                    if (engModalMain2) engModalMain2.classList.add("hidden");
                    isEtegamiConfirming = false;
                    isModalOpen = false;
                    if (typeof updateEngineToggleUI === "function") {
                        updateEngineToggleUI(data.engine);
                    }
                    break;

                case "show_artwork_confirm_modal":
                    showArtworkConfirmModal(data);
                    break;

                case "show_save_confirm_modal":
                    showSaveConfirmModal();
                    break;

                case "guardrail_result":
                    handleGuardrailResult(data);
                    break;

                case "vital_recorded":
                    console.log("[User WS] Vital recorded:", data);
                    if (typeof updateVitalDisplay === "function") {
                        updateVitalDisplay(data.heart_rate, data.spo2, data.is_alert, data.alert_reason);
                    }
                    break;

                case "emergency_sos_ack":
                    console.log("[User WS] Emergency SOS acknowledged by server:", data);
                    showTemporaryToast("🚨 スタッフステーションへ緊急SOSを発信しました");
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

                case "today_schedules":
                case "schedule_updated":
                    console.log("[User WS] Schedule event received:", data.type);
                    if (typeof loadTodaySchedules === "function") {
                        loadTodaySchedules(false);
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
        if (!terminalId) return;
        if (liveWs && (liveWs.readyState === WebSocket.OPEN || liveWs.readyState === WebSocket.CONNECTING)) {
            console.log("[connectLiveWS]: Already open or connecting, skipping duplicate.");
            return;
        }
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/user/${terminalId}/live`;
        liveWs = new WebSocket(wsUrl);

        liveWs.onopen = () => {
            console.log("Gemini Live WS connected");
        };

        liveWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "live_audio_output") {
                // If Mimamori-san is currently announcing schedules, drop Gemini Live audio to prevent interruption
                if (isAnnouncementPlaying || isTTSAnnouncing) {
                    console.log("[LiveWS]: Dropped live_audio_output because Mimamori schedule announcement is playing.");
                    return;
                }
                console.log("[LiveWS]: Received live_audio_output chunk (b64 len:", data.data ? data.data.length : 0, ", rate:", data.sample_rate || 24000, ")");
                setLiveLampState("speaking");
                setAvatarState("speaking");
                playPCM24Chunk(data.data, data.sample_rate || 24000);
            } else if (data.type === "ui_mode_change") {
                console.log("[LiveWS]: Received ui_mode_change ->", data.mode);
                if (Date.now() - lastUIModeChangeTime < 4000 && currentUIMode === data.mode) {
                    console.log("[LiveWS]: Already switched recently to", data.mode, "- skipping duplicate");
                } else {
                    setUIMode(data.mode, true);
                }
            } else if (data.type === "schedule_visibility") {
                console.log("[LiveWS]: Received schedule_visibility ->", data.visible);
                if (data.visible) {
                    if (typeof showScheduleCard === "function") {
                        showScheduleCard(false);
                    }
                } else {
                    if (typeof hideScheduleCard === "function") {
                        hideScheduleCard();
                    }
                }
            } else if (data.type === "etegami_visibility") {
                console.log("[LiveWS]: Received etegami_visibility ->", data.visible);
                if (data.visible) {
                    if (typeof showEtegamiCard === "function") {
                        showEtegamiCard();
                    }
                } else {
                    if (typeof hideEtegamiCard === "function") {
                        hideEtegamiCard();
                    }
                }
            } else if (data.type === "live_response" || data.type === "live_text_output") {
                const rawText = data.text || "";

                // Detect Gemini Live internal command speech
                const isToSimple = (
                    rawText.includes("単純画面に切り替") || 
                    rawText.includes("画面切り替") || 
                    rawText.includes("シンプル画面に切り替") ||
                    (rawText.includes("業務連絡") && (rawText.includes("単純画面") || rawText.includes("シンプル画面")))
                );
                const isToDetailed = (
                    rawText.includes("詳細画面に切り替") ||
                    (rawText.includes("業務連絡") && rawText.includes("詳細画面"))
                );

                // Ignore Gemini Live screen switching command if already switched within 4 seconds
                if (Date.now() - lastUIModeChangeTime > 4000) {
                    if (isToSimple) {
                        console.log("[Gemini Live Voice]: Detected simple mode command from Gemini speech:", rawText);
                        setUIMode("simple", true);
                    } else if (isToDetailed) {
                        console.log("[Gemini Live Voice]: Detected detailed mode command from Gemini speech:", rawText);
                        setUIMode("detailed", true);
                    }
                } else if (isToSimple || isToDetailed) {
                    console.log("[Gemini Live Voice]: Screen already switched recently (within 4s) - ignoring Gemini Live command:", rawText);
                }

                // Detect Gemini Live schedule card commands
                const isToGeminiShowSched = (
                    rawText.includes("みまもりさん予定カードの表示をお願いします") ||
                    rawText.includes("予定カードの表示をお願い") ||
                    rawText.includes("予定カードを表示")
                );
                const isToGeminiHideSched = (
                    rawText.includes("みまもりさん予定カードの表示を終了してください") ||
                    rawText.includes("予定カードの表示を終了") ||
                    rawText.includes("予定カードを終了") ||
                    rawText.includes("予定カードを消して")
                );

                if (isToGeminiShowSched) {
                    console.log("[Gemini Live Voice]: Detected show schedule card command:", rawText);
                    if (typeof showScheduleCard === "function") {
                        showScheduleCard(false);
                    }
                } else if (isToGeminiHideSched) {
                    console.log("[Gemini Live Voice]: Detected hide schedule card command:", rawText);
                    if (typeof hideScheduleCard === "function") {
                        hideScheduleCard();
                    }
                }

                // Note: Etegami card visibility is controlled only by resident voice or user UI buttons, not Gemini speech.

                // Detect Gemini Live recording commands
                const isToStopRec = (
                    rawText.includes("会話記録を停止") ||
                    rawText.includes("会話記録の停止") ||
                    rawText.includes("記録停止") ||
                    rawText.includes("記録を停止")
                );
                const isToResumeRec = (
                    rawText.includes("会話記録を再開") ||
                    rawText.includes("会話記録の再開") ||
                    rawText.includes("記録再開") ||
                    rawText.includes("記録を再開")
                );

                if (Date.now() - lastRecordingChangeTime > 4000) {
                    if (isToStopRec) {
                        console.log("[Gemini Live Voice]: Detected recording stop command from Gemini speech:", rawText);
                        handleRecordingStatus(false, "会話記録停止");
                    } else if (isToResumeRec) {
                        console.log("[Gemini Live Voice]: Detected recording resume command from Gemini speech:", rawText);
                        handleRecordingStatus(true, "会話記録再開");
                    }
                }

                // Filter out the internal command preamble for cleaner speech box display
                const sanitizeAiPreamble = (text) => {
                    return (text || "")
                        .replace(/みまもりさん[へ]?業務連絡[、,][^。.\n]+[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?予定カードの表示[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*デジタル絵手紙を表示[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*デジタル絵手紙をとじて[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*デジタル絵手紙を閉じて[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*絵手紙を表示[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*絵手紙をとじて[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*絵手紙を閉じて[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*デジタル絵手紙更新[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*絵手紙更新[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*デジタル絵手紙完成[^。.\n]*[。.・\n]?/g, "")
                        .replace(/みまもりさん[、へ]?[^。.\n]*絵手紙完成[^。.\n]*[。.・\n]?/g, "")
                        .trim();
                };
                const cleanText = sanitizeAiPreamble(rawText);

                if (aiResponseBox && cleanText) {
                    if (data.type === "live_text_output") {
                        if (!aiResponseBox.textContent || 
                            aiResponseBox.textContent.includes("表示されます") || 
                            aiResponseBox.textContent.includes("待っています") || 
                            aiResponseBox.textContent.includes("リアルタイム音声") ||
                            aiResponseBox.textContent.includes("お返答中")) {
                            aiResponseBox.textContent = cleanText;
                        } else if (!aiResponseBox.textContent.endsWith(cleanText)) {
                            aiResponseBox.textContent += cleanText;
                        }
                    } else {
                        aiResponseBox.textContent = cleanText;
                    }
                    setLiveLampState("speaking");
                    setAvatarState("speaking");
                }
            } else if (data.type === "transcription_result") {
                if (isEtegamiModalSelecting) {
                    console.log("[LiveWS]: Suppressed transcription_result during mode/engine modal selection");
                    return;
                }
                // Always display latest user speech transcription result on screen
                if (userSpeechBox && data.text) {
                    userSpeechBox.textContent = data.text;
                }
                if (data.text) {
                    handleEtegamiVoiceTrigger(data.text, "LiveWS_Transcription");
                    if (typeof updateEtegamiListeningText === "function" && (currentEtegamiPhase === ETEGAMI_PHASE.LISTENING || isEtegamiCardVisible)) {
                        updateEtegamiListeningText(data.text);
                    }
                }
            } else if (data.type === "chat_response") {
                if (isEtegamiModalSelecting) {
                    console.log("[LiveWS]: Suppressed chat_response during mode/engine modal selection");
                    return;
                }
                if (userSpeechBox && data.user_text) {
                    userSpeechBox.textContent = data.user_text;
                    handleEtegamiVoiceTrigger(data.user_text, "LiveWS_ChatResponseUser");
                    if (typeof updateEtegamiListeningText === "function" && (currentEtegamiPhase === ETEGAMI_PHASE.LISTENING || isEtegamiCardVisible)) {
                        updateEtegamiListeningText(data.user_text);
                    }
                }
                if (aiResponseBox && data.text) aiResponseBox.textContent = (typeof sanitizeAiPreamble === "function") ? sanitizeAiPreamble(data.text) : data.text;
            } else if (data.type === "pii_warning") {
                handlePIIWarning(data.message);
            } else if (data.type === "gemini_thinking") {
                setLiveLampState("thinking");
                setAvatarState("thinking");
                if (statusText) statusText.textContent = "🧠 Gemini考え中...";
                const thought = (data.thought || "").toLowerCase();
                // Note: Gemini internal thought should NEVER trigger etegami UI card transitions.
                const isThoughtSimple = data.thought && (data.thought.includes("単純画面に切り替") || data.thought.includes("画面切り替") || data.thought.includes("シンプル画面に切り替") || thought.includes("simple screen") || thought.includes("initiating screen transition"));
                const isThoughtDetailed = data.thought && (data.thought.includes("詳細画面に切り替") || thought.includes("detailed screen"));
                const isThoughtStopRec = data.thought && (data.thought.includes("会話記録を停止") || data.thought.includes("記録停止") || thought.includes("conversation halt") || thought.includes("cease recording") || thought.includes("stop recording"));
                const isThoughtResumeRec = data.thought && (data.thought.includes("会話記録を再開") || data.thought.includes("記録再開") || thought.includes("resume recording"));
                const isThoughtShowSched = data.thought && (data.thought.includes("予定カードの表示") || data.thought.includes("予定カードを表示") || thought.includes("show schedule card") || thought.includes("display schedule card"));
                const isThoughtHideSched = data.thought && (data.thought.includes("予定カードの表示を終了") || data.thought.includes("予定カードを終了") || thought.includes("hide schedule card") || thought.includes("close schedule card"));

                if (isThoughtShowSched) {
                    if (typeof showScheduleCard === "function") showScheduleCard(false);
                } else if (isThoughtHideSched) {
                    if (typeof hideScheduleCard === "function") hideScheduleCard();
                }

                // Note: Gemini internal thought should never trigger etegami UI card transitions.

                if (Date.now() - lastUIModeChangeTime > 4000) {
                    if (isThoughtSimple) {
                        console.log("[Gemini Live Thought]: Detected simple mode in thought:", data.thought);
                        setUIMode("simple", true);
                    } else if (isThoughtDetailed) {
                        console.log("[Gemini Live Thought]: Detected detailed mode in thought:", data.thought);
                        setUIMode("detailed", true);
                    }
                } else if (isThoughtSimple || isThoughtDetailed) {
                    console.log("[Gemini Live Thought]: Screen already switched recently (within 4s) - ignoring thought command:", data.thought);
                }

                if (Date.now() - lastRecordingChangeTime > 4000) {
                    if (isThoughtStopRec) {
                        console.log("[Gemini Live Thought]: Detected recording stop in thought:", data.thought);
                        handleRecordingStatus(false, "会話記録停止");
                    } else if (isThoughtResumeRec) {
                        console.log("[Gemini Live Thought]: Detected recording resume in thought:", data.thought);
                        handleRecordingStatus(true, "会話記録再開");
                    }
                }
            } else if (data.type === "guardrail_result") {
                handleGuardrailResult(data);
            } else if (data.type === "recording_status") {
                if (Date.now() - lastRecordingChangeTime < 4000 && isCurrentRecordingActive === data.active) {
                    console.log("[LiveWS]: Recording status already switched recently - skipping duplicate server message");
                } else {
                    handleRecordingStatus(data.active, data.message);
                }
            } else if (data.type === "etegami_updating") {
                console.log("[LiveWS]: Received etegami_updating ->", data.updating, data);
                isEtegamiUpdating = !!data.updating;
                const updatingBadge = document.getElementById("etegami-updating-badge");
                const updatingTextMain = document.getElementById("updating-text-main");
                const updatingTextSub = document.getElementById("updating-text-sub");
                const lampEtegami = document.getElementById("lamp-etegami");
                const lampEtegamiLabel = document.getElementById("lamp-etegami-label");
                const voiceHint = document.getElementById("etegami-voice-hint");
                const statusBadge = document.getElementById("etegami-status-badge");
                const completeBtn = document.getElementById("btn-complete-etegami");

                if (data.updating) {
                    if (typeof showEtegamiCard === "function") {
                        showEtegamiCard(true);
                    }
                    if (updatingBadge) {
                        updatingBadge.classList.remove("hidden");
                    }
                    if (updatingTextMain) {
                        updatingTextMain.textContent = "AIが新しい絵手紙を描いています…";
                    }
                    if (updatingTextSub) {
                        const motifText = data.motif || "心温まる思い出の風景";
                        const engineText = data.engine_label || "無料AI Pollinations";
                        updatingTextSub.textContent = `「${motifText}」（${engineText}）`;
                    }
                    if (data.motif) currentEtegamiMotif = data.motif;
                    if (data.prompt_en) currentEtegamiPromptEn = data.prompt_en;
                    if (data.accumulated_text) etegamiAccumulatedText = data.accumulated_text;

                    const updatingPromptBox = document.getElementById("updating-prompt-box");
                    const updatingPromptJa = document.getElementById("updating-prompt-ja");
                    const updatingPromptEn = document.getElementById("updating-prompt-en");
                    const fullAccText = data.accumulated_text || etegamiAccumulatedText || currentEtegamiTranscript || "";
                    const fullPromptEn = data.prompt_en || currentEtegamiPromptEn || "";

                    if (updatingPromptBox) {
                        if (fullAccText || fullPromptEn) {
                            updatingPromptBox.classList.remove("hidden");
                            if (updatingPromptJa) {
                                updatingPromptJa.textContent = fullAccText ? `【要望・会話詳細】: ${fullAccText}` : `【モチーフ】: ${data.motif || currentEtegamiMotif || '思い出の情景'}`;
                            }
                            if (updatingPromptEn) {
                                updatingPromptEn.textContent = fullPromptEn ? `【AI画像プロンプト】: ${fullPromptEn}` : "";
                            }
                        } else {
                            updatingPromptBox.classList.add("hidden");
                        }
                    }

                    if (voiceHint) voiceHint.classList.remove("hidden");
                    if (statusBadge) {
                        statusBadge.classList.remove("hidden");
                        statusBadge.className = "etegami-status-badge badge-updating";
                        statusBadge.innerHTML = "<span class='spin-icon'>🎨</span><span>⏳ AI描画中...</span>";
                    }
                    if (completeBtn) completeBtn.classList.add("hidden");
                    if (lampEtegami) {
                        lampEtegami.classList.remove("hidden", "lamp-completed");
                        lampEtegami.classList.add("lamp-updating");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = `🎨 みまもりさん：${data.motif || '絵'}を描いているところです`;
                    }
                } else {
                    if (updatingBadge) updatingBadge.classList.add("hidden");
                    if (voiceHint) voiceHint.classList.add("hidden");
                    if (statusBadge) {
                        statusBadge.classList.remove("hidden");
                        statusBadge.className = "etegami-status-badge badge-drafting";
                        statusBadge.innerHTML = "<span>🎨</span><span>下絵表示中</span>";
                    }
                    if (lampEtegami) {
                        lampEtegami.classList.remove("lamp-updating");
                        lampEtegami.classList.add("lamp-completed");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = "✨ みまもりさん：絵手紙更新完了";
                        clearTimeout(window._etegamiLampTimer);
                        window._etegamiLampTimer = setTimeout(() => {
                            if (lampEtegami) {
                                lampEtegami.classList.remove("lamp-completed");
                                lampEtegami.classList.add("hidden");
                            }
                        }, 4000);
                    }
                }
            } else if (data.type === "mimamori_acknowledgement") {
                console.log("[LiveWS]: Received mimamori_acknowledgement ->", data.message, "speak_text=", data.speak_text);
                if (data.message) {
                    showTemporaryToast(data.message, 4500);
                }
                // 🔇 みまもりさんは音声を停止してテキスト表示のみ（ジェミナイとの自然な音声対話に専念）
                const lampEtegami = document.getElementById("lamp-etegami");
                const lampEtegamiLabel = document.getElementById("lamp-etegami-label");
                const voiceHint = document.getElementById("etegami-voice-hint");
                const statusBadge = document.getElementById("etegami-status-badge");
                const completeBtn = document.getElementById("btn-complete-etegami");
                if (data.action === "etegami_prepared") {
                    if (lampEtegami) {
                        lampEtegami.classList.remove("hidden", "lamp-completed");
                        lampEtegami.classList.add("lamp-updating");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = "🎨 みまもりさん：準備中";
                        clearTimeout(window._etegamiLampTimer);
                        window._etegamiLampTimer = setTimeout(() => {
                            if (lampEtegami) {
                                lampEtegami.classList.remove("lamp-updating");
                                lampEtegami.classList.add("hidden");
                            }
                        }, 5000);
                    }
                } else if (data.action === "etegami_busy") {
                    if (lampEtegami) {
                        lampEtegami.classList.remove("hidden", "lamp-completed");
                        lampEtegami.classList.add("lamp-updating");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = "🎨 みまもりさん：今絵を描いているところです";
                        clearTimeout(window._etegamiLampTimer);
                        window._etegamiLampTimer = setTimeout(() => {
                            if (lampEtegami) {
                                lampEtegami.classList.remove("lamp-updating");
                                lampEtegami.classList.add("hidden");
                            }
                        }, 4000);
                    }
                } else if (data.action === "etegami_updated") {
                    if (voiceHint) voiceHint.classList.add("hidden");
                    if (completeBtn) completeBtn.classList.add("hidden");
                    if (statusBadge) {
                        statusBadge.classList.remove("hidden");
                        statusBadge.className = "etegami-status-badge badge-drafting";
                        statusBadge.innerHTML = "<span>🎨</span><span>下絵表示中</span>";
                    }
                    if (lampEtegami) {
                        lampEtegami.classList.remove("hidden", "lamp-updating");
                        lampEtegami.classList.add("lamp-completed");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = "✨ みまもりさん：絵手紙更新完了";
                        clearTimeout(window._etegamiLampTimer);
                        window._etegamiLampTimer = setTimeout(() => {
                            if (lampEtegami) {
                                lampEtegami.classList.remove("lamp-completed");
                                lampEtegami.classList.add("hidden");
                            }
                        }, 4000);
                    }
                } else if (data.action === "etegami_generation_failed" || data.action === "etegami_generation_aborted") {
                    const updatingBadge = document.getElementById("etegami-updating-badge");
                    if (updatingBadge) updatingBadge.classList.add("hidden");
                    if (voiceHint) voiceHint.classList.add("hidden");
                    isEtegamiUpdating = false;
                    if (lampEtegami) {
                        lampEtegami.classList.remove("lamp-updating", "lamp-completed");
                        lampEtegami.classList.add("hidden");
                    }
                    if (statusBadge) {
                        statusBadge.classList.remove("hidden");
                        statusBadge.className = "etegami-status-badge badge-drafting";
                        statusBadge.innerHTML = "<span>⚠️</span><span>描画中断</span>";
                    }
                } else if (data.action === "etegami_complete") {
                    if (voiceHint) voiceHint.classList.add("hidden");
                    if (statusBadge) statusBadge.classList.add("hidden");
                    if (completeBtn) completeBtn.classList.add("hidden");
                    if (lampEtegami) {
                        lampEtegami.classList.remove("hidden", "lamp-updating");
                        lampEtegami.classList.add("lamp-completed");
                        if (lampEtegamiLabel) lampEtegamiLabel.textContent = "💮 みまもりさん：絵手紙完成";
                        clearTimeout(window._etegamiLampTimer);
                        window._etegamiLampTimer = setTimeout(() => {
                            if (lampEtegami) {
                                lampEtegami.classList.remove("lamp-completed");
                                lampEtegami.classList.add("hidden");
                            }
                        }, 4000);
                    }
                    if (typeof showTemporaryToast === "function") {
                        showTemporaryToast("💮 絵手紙が完成しました。通常会話に戻します。", 5000);
                    }
                    if (typeof playTTSVoice === "function") {
                        playTTSVoice("絵手紙が完成しました。通常会話に戻します。", true);
                    }
                    if (typeof hideEtegamiCard === "function") {
                        hideEtegamiCard();
                    }
                    currentEtegamiPhase = ETEGAMI_PHASE.IDLE;
                }
            } else if (data.type === "etegami_completed_notice") {
                console.log("[LiveWS]: Received etegami_completed_notice ->", data.message);
                if (typeof showTemporaryToast === "function") {
                    showTemporaryToast(data.message || "💮 絵手紙が完成しました。通常会話に戻します。", 5000);
                }
                if (typeof playTTSVoice === "function") {
                    playTTSVoice(data.message || "絵手紙が完成しました。通常会話に戻します。", true);
                }
                if (typeof hideEtegamiCard === "function") {
                    hideEtegamiCard();
                }
                currentEtegamiPhase = ETEGAMI_PHASE.IDLE;
            } else if (data.type === "etegami_update") {
                console.log("[LiveWS]: Received etegami_update ->", data);
                updateEtegamiDisplay(data);
            } else if (data.type === "etegami_listening") {
                console.log("[LiveWS]: Received etegami_listening ->", data.listening);
                const listeningBadge = document.getElementById("etegami-listening-badge");
                if (listeningBadge) {
                    if (data.listening && currentEtegamiPhase !== ETEGAMI_PHASE.COMPLETED) {
                        listeningBadge.classList.remove("hidden");
                    } else {
                        listeningBadge.classList.add("hidden");
                    }
                }
            } else if (data.type === "etegami_motif_confirm_prompt") {
                console.log("[LiveWS]: Received etegami_motif_confirm_prompt ->", data);
                if (data.motif) {
                    currentEtegamiMotif = data.motif;
                }
                if (data.prompt_en) {
                    currentEtegamiPromptEn = data.prompt_en;
                }
                if (data.accumulated_text && !etegamiAccumulatedText) {
                    etegamiAccumulatedText = data.accumulated_text;
                    currentEtegamiTranscript = data.accumulated_text;
                }
                if (data.calligraphy) currentEtegamiCalligraphy = data.calligraphy;
                setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_CONTENT, data);
            } else if (data.type === "etegami_motif_confirm_dismiss") {
                console.log("[LiveWS]: Received etegami_motif_confirm_dismiss");
                const confirmModal = document.getElementById("etegami-motif-confirm-modal");
                if (confirmModal) confirmModal.classList.add("hidden");
                const listeningBadge = document.getElementById("etegami-listening-badge");
                if (listeningBadge) listeningBadge.classList.add("hidden");
                isEtegamiConfirming = false;
                isModalOpen = false;
            } else if (data.type === "stop_audio_playback") {
                console.log("[LiveWS]: Received stop_audio_playback -> halting all audio immediately");
                stopLiveAudioPlayback();
                setAvatarState("idle");
                setLiveLampState("idle");
            } else if (data.type === "etegami_mode_confirm_prompt") {
                console.log("[LiveWS]: Received etegami_mode_confirm_prompt ->", data);
                const modeModal = document.getElementById("etegami-mode-confirm-modal");
                if (modeModal) modeModal.classList.remove("hidden");
                isEtegamiModalSelecting = true;
                isEtegamiConfirming = true;
                isModalOpen = true;
            } else if (data.type === "etegami_mode_confirm_dismiss") {
                console.log("[LiveWS]: Received etegami_mode_confirm_dismiss");
                const modeModal = document.getElementById("etegami-mode-confirm-modal");
                if (modeModal) modeModal.classList.add("hidden");
            } else if (data.type === "etegami_engine_confirm_prompt") {
                console.log("[LiveWS]: Received etegami_engine_confirm_prompt ->", data);
                const confirmModal = document.getElementById("etegami-engine-confirm-modal");
                if (confirmModal) confirmModal.classList.remove("hidden");
                isEtegamiModalSelecting = true;
                isEtegamiConfirming = true;
                isModalOpen = true;
            } else if (data.type === "etegami_engine_updated") {
                console.log("[LiveWS]: Received etegami_engine_updated ->", data);
                const confirmModal = document.getElementById("etegami-engine-confirm-modal");
                if (confirmModal) confirmModal.classList.add("hidden");
                isEtegamiModalSelecting = false;
                isEtegamiConfirming = false;
                isModalOpen = false;
                hasConfirmedEtegamiModeAndEngine = true;
                if (typeof updateEngineToggleUI === "function") {
                    updateEngineToggleUI(data.engine);
                }
                if (currentEtegamiPhase === ETEGAMI_PHASE.IDLE) {
                    setEtegamiPhase(ETEGAMI_PHASE.LISTENING);
                }
            } else if (data.type === "show_artwork_confirm_modal") {
                console.log("[LiveWS]: Received show_artwork_confirm_modal ->", data);
                showArtworkConfirmModal(data);
            } else if (data.type === "show_save_confirm_modal") {
                console.log("[LiveWS]: Received show_save_confirm_modal ->", data);
                showSaveConfirmModal();
            } else if (data.type === "api_error_notice") {
                console.warn("[LiveWS]: Received api_error_notice ->", data.title, data.message);
                const bannerText = `⚠️ ${data.title || 'APIエラー'}: ${data.message}`;
                if (typeof showTemporaryToast === "function") {
                    showTemporaryToast(bannerText, 7000);
                } else if (typeof showUIToast === "function") {
                    showUIToast(bannerText, "warning");
                }
                const updatingBadge = document.getElementById("etegami-updating-badge");
                if (updatingBadge) updatingBadge.classList.add("hidden");
                const voiceHint = document.getElementById("etegami-voice-hint");
                if (voiceHint) voiceHint.classList.add("hidden");
                isEtegamiUpdating = false;
                const lampEtegami = document.getElementById("lamp-etegami");
                if (lampEtegami) {
                    lampEtegami.classList.remove("lamp-updating");
                    lampEtegami.classList.add("hidden");
                }
                const debugBadge = document.getElementById("debug-badge");
                if (debugBadge) {
                    debugBadge.textContent = bannerText;
                    debugBadge.classList.remove("hidden");
                }
            }
        };

        liveWs.onclose = () => {
            console.log("Gemini Live WS disconnected");
            setTimeout(connectLiveWS, 3000);
        };
    }

    // 🔒 Mimamori-san Recording Status & Popup Handler
    let isCurrentRecordingActive = true;
    let lastRecordingChangeTime = 0;

    function handleRecordingStatus(isActive, message, force = false) {
        // Prevent duplicate toggling if already in the target recording state
        if (!force && isCurrentRecordingActive === isActive) {
            console.log("[Mimamori Recording Status]: Already in target state:", isActive, "(skipping duplicate)");
            return false;
        }

        isCurrentRecordingActive = isActive;
        lastRecordingChangeTime = Date.now();
        console.log("[Mimamori Recording Status]: Switched to", isActive, message);
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
        return true;
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

        // Client-side Failsafe: Suppress false-positive emergency/alert if text does not contain genuine distress words
        const distressEmergencyKeywords = ["胸が痛", "息ができない", "息が苦し", "苦しい", "助けて", "倒れた", "転んだ", "激痛", "血が出た", "死にそう", "誰か来て", "救急"];
        const distressAlertKeywords = ["熱がある", "頭痛がひどい", "頭が痛い", "吐き気", "めまいがひど", "スタッフを呼", "スタッフさん呼", "看護師さん呼", "看護師呼", "先生呼"];
        const combinedText = ((data.summary || "") + " " + (data.detail || "") + " " + (currentUtteranceText || "")).trim();

        if (status === "EMERGENCY" || stage === 3) {
            if (!distressEmergencyKeywords.some(kw => combinedText.includes(kw))) {
                console.warn("[Guardrail Failsafe]: Suppressed false-positive EMERGENCY modal for non-distress text:", combinedText);
                return;
            }
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
            if (!distressAlertKeywords.some(kw => combinedText.includes(kw)) && !isPII) {
                console.warn("[Guardrail Failsafe]: Suppressed false-positive ALERT modal for non-distress text:", combinedText);
                return;
            }
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
    let lastAIAudioEndTime = 0;
    const JITTER_BUFFER_SEC = 0.12; // 120ms initial buffer for seamless stutter-free playback

    function stopLiveAudioPlayback() {
        if (pcm24EndTimer) clearTimeout(pcm24EndTimer);
        isAISpeaking = false;
        isPlayingPCM24 = false;
        lastAIAudioEndTime = Date.now();
        nextAudioStartTime = 0;
        if (liveAudioCtx && liveAudioCtx.state !== "closed") {
            try {
                liveAudioCtx.close();
                liveAudioCtx = null;
            } catch (e) {}
        }
    }

    let pcmChunkRemainder = null;

    function playPCM24Chunk(base64Data, sampleRate) {
        if (!liveAudioCtx || liveAudioCtx.state === "closed") {
            liveAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
        }
        if (liveAudioCtx.state === "suspended") {
            liveAudioCtx.resume();
        }
        try {
            const binaryStr = atob(base64Data);
            let rawBytes = new Uint8Array(binaryStr.length);
            for (let i = 0; i < binaryStr.length; i++) {
                rawBytes[i] = binaryStr.charCodeAt(i);
            }

            // Prepend leftover byte from previous odd-length chunk
            if (pcmChunkRemainder && pcmChunkRemainder.length > 0) {
                const combined = new Uint8Array(pcmChunkRemainder.length + rawBytes.length);
                combined.set(pcmChunkRemainder);
                combined.set(rawBytes, pcmChunkRemainder.length);
                rawBytes = combined;
                pcmChunkRemainder = null;
            }

            // Ensure even byte length for 16-bit PCM samples to prevent RangeError
            if (rawBytes.length % 2 !== 0) {
                pcmChunkRemainder = rawBytes.slice(-1);
                rawBytes = rawBytes.slice(0, -1);
            }

            if (rawBytes.length === 0) return;

            const int16Array = new Int16Array(rawBytes.buffer, rawBytes.byteOffset, rawBytes.length / 2);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }

            const buffer = liveAudioCtx.createBuffer(1, float32Array.length, sampleRate);
            buffer.getChannelData(0).set(float32Array);

            const source = liveAudioCtx.createBufferSource();
            source.buffer = buffer;
            source.connect(liveAudioCtx.destination);

            // Interruption & Collision Protection: Cancel any active SpeechSynthesis (Mimamori TTS) when Gemini speaks
            if (window.speechSynthesis && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
                try {
                    window.speechSynthesis.cancel();
                    isTTSAnnouncing = false;
                    console.log("[Live Audio]: Immediately cancelled Mimamori TTS to prevent voice overlap with Gemini.");
                } catch (e) {}
            }

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
                lastAIAudioEndTime = Date.now();
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

    function playTTSVoice(text, force = false) {
        if (!text || !window.speechSynthesis) return;

        // Mutual Exclusion: If Gemini Live is currently speaking or has audio queued, suppress Mimamori TTS voice unless force is true
        if (!force && (isPlayingPCM24 || isAISpeaking || (liveAudioCtx && nextAudioStartTime > liveAudioCtx.currentTime + 0.1))) {
            console.log("[TTS]: Suppressed Mimamori voice ('" + text + "') to prevent overlap with Gemini speech.");
            return;
        }

        if (force) {
            stopLiveAudioPlayback();
        }

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

            // Immediately send EOS to Gemini Live on manual mic OFF so speech concludes instantly without waiting for VAD silence
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                const textToSend = (currentUtteranceText || "").trim();
                console.log("[Mic Button OFF]: User concluded speech manually. Sending EOS frame to Gemini Live.");
                if (textToSend) handleEtegamiVoiceTrigger(textToSend, "ClientMicStopEOS");
                liveWs.send(JSON.stringify({ type: "eos", text: textToSend }));
            }
            currentUtteranceText = "";

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
                
                // Unlock Web Audio Context on user click for reliable Gemini Live playback
                if (!liveAudioCtx || liveAudioCtx.state === "closed") {
                    liveAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
                }
                if (liveAudioCtx.state === "suspended") {
                    liveAudioCtx.resume();
                }

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
                let chunksSentInUtterance = 0;
                let preSpeechRingBuffer = []; // ring buffer of last 3 chunks (~150ms) to preserve initial consonants
                const NOISE_GATE_THRESHOLD = 0.0018; // Sensitive threshold for laptop/tablet internal mics
                const AI_ECHO_GUARD_MS = 400; // 0.4s minimal acoustic echo cooldown guard

                recorder.onChunkCallback = (resampledChunk) => {
                    // Mute microphone completely when AI is speaking, modal is open, system is announcing,
                    // or within post-playback acoustic echo cooldown window
                    const isEchoCooldown = (Date.now() - lastAIAudioEndTime < AI_ECHO_GUARD_MS);
                    if (isPlayingPCM24 || isAISpeaking || isModalOpen || isTTSAnnouncing || isEchoCooldown) {
                        preSpeechRingBuffer = [];
                        voiceHangoverFrames = 0;
                        isSpeakingUtterance = false;
                        chunksSentInUtterance = 0;
                        vadSilenceFrames = 0;
                        currentUtteranceText = "";
                        window.isSpeechRecActive = false;
                        return;
                    }

                    // 1. Calculate instant RMS volume of mic input
                    let sum = 0;
                    for (let i = 0; i < resampledChunk.length; i++) {
                        sum += resampledChunk[i] * resampledChunk[i];
                    }
                    const rms = Math.sqrt(sum / resampledChunk.length);

                    // 2. Hardware-level instant VAD with noise-gate
                    const speechThreshold = (currentLampState === "thinking") ? 0.005 : NOISE_GATE_THRESHOLD;
                    const isVoiceActive = rms > speechThreshold || window.isSpeechRecActive;
                    const b64Pcm = float32ToInt16Base64(resampledChunk);

                    if (isVoiceActive) {
                        // User started speaking or is actively speaking
                        if (!isSpeakingUtterance && userSpeechBox) {
                            userSpeechBox.textContent = "🎙️ 聞き取り中...";
                        }
                        if (voiceHangoverFrames <= 0 && preSpeechRingBuffer.length > 0) {
                            // Flush pre-speech buffer so leading consonants are intact
                            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                                for (const preChunk of preSpeechRingBuffer) {
                                    liveWs.send(JSON.stringify({
                                        type: "live_pcm_chunk",
                                        data: preChunk
                                    }));
                                    chunksSentInUtterance++;
                                }
                            }
                            preSpeechRingBuffer = [];
                        }

                        voiceHangoverFrames = 8; // ~400ms hangover to cover inter-syllable micro-pauses
                        isSpeakingUtterance = true;
                        vadSilenceFrames = 0;

                        if (currentLampState !== "thinking" || rms > 0.008) {
                            setLiveLampState("sending");
                        }

                        // Stream active voice chunk to Gemini Live
                        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                            liveWs.send(JSON.stringify({
                                type: "live_pcm_chunk",
                                data: b64Pcm
                            }));
                            chunksSentInUtterance++;
                            if (chunksSentInUtterance === 1 || chunksSentInUtterance % 25 === 0) {
                                console.log(`[Mic VAD]: Streaming chunk #${chunksSentInUtterance} to Gemini Live (rms: ${rms.toFixed(4)})`);
                            }
                        }
                    } else if (voiceHangoverFrames > 0) {
                        // Trailing speech hangover window: stream chunk to avoid cutting word endings
                        voiceHangoverFrames--;
                        if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                            liveWs.send(JSON.stringify({
                                type: "live_pcm_chunk",
                                data: b64Pcm
                            }));
                            chunksSentInUtterance++;
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
                                const textToSend = (!isEcho && cleanText) ? cleanText : "";
                                if (textToSend) handleEtegamiVoiceTrigger(textToSend, "ClientVadEOS");

                                // Only send EOS if actual human speech occurred (either text recognized OR >= 3 chunks streamed for short words like 'はい', 'いいえ')
                                if (chunksSentInUtterance >= 3 || textToSend) {
                                    if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                                        console.log("[Mic VAD] Speech concluded. Sending EOS frame (chunks:", chunksSentInUtterance, ", text:", textToSend || "<audio-only>", ")");
                                        liveWs.send(JSON.stringify({ type: "eos", text: textToSend }));
                                    }
                                } else {
                                    console.log("[Mic VAD] Dropping empty / noise-only silence trigger (chunks:", chunksSentInUtterance, ", text: empty). No EOS sent.");
                                    setLiveLampState("idle");
                                }
                                chunksSentInUtterance = 0;
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

    let activeAudioUrl = null;

    function base64ToBlob(base64Data, mimeType = "audio/mp3") {
        const binaryStr = atob(base64Data);
        const len = binaryStr.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }
        return new Blob([bytes], { type: mimeType });
    }

    function playBase64Audio(base64Data, onEnded, onError) {
        if (activeAudio) {
            try { activeAudio.pause(); } catch(e){}
            activeAudio = null;
        }
        if (activeAudioUrl) {
            try { URL.revokeObjectURL(activeAudioUrl); } catch(e){}
            activeAudioUrl = null;
        }

        try {
            const blob = base64ToBlob(base64Data, "audio/mp3");
            activeAudioUrl = URL.createObjectURL(blob);
            activeAudio = new Audio(activeAudioUrl);

            activeAudio.onended = () => {
                if (activeAudioUrl) {
                    URL.revokeObjectURL(activeAudioUrl);
                    activeAudioUrl = null;
                }
                activeAudio = null;
                if (onEnded) onEnded();
            };

            activeAudio.onerror = (e) => {
                console.error("[playBase64Audio] Audio playback error:", e);
                if (activeAudioUrl) {
                    URL.revokeObjectURL(activeAudioUrl);
                    activeAudioUrl = null;
                }
                activeAudio = null;
                if (onError) onError(e);
                else if (onEnded) onEnded();
            };

            activeAudio.play().catch(err => {
                console.warn("[playBase64Audio] Audio play blocked/failed:", err);
                if (activeAudioUrl) {
                    URL.revokeObjectURL(activeAudioUrl);
                    activeAudioUrl = null;
                }
                activeAudio = null;
                if (onError) onError(err);
                else if (onEnded) onEnded();
            });
        } catch (convErr) {
            console.error("[playBase64Audio] Blob conversion error:", convErr);
            if (onError) onError(convErr);
            else if (onEnded) onEnded();
        }
    }

    // =========================================================================
    // 📅 予定カード (Schedules Management & Boot Announcement Listeners)
    // =========================================================================

    if (btnReAnnounceSchedules) {
        btnReAnnounceSchedules.addEventListener("click", () => {
            console.log("[Schedule Card]: '🔊 予定を聞く' button clicked.");
            playScheduleAnnouncement();
        });
    }

    if (btnCloseScheduleCard) {
        btnCloseScheduleCard.addEventListener("click", () => {
            console.log("[Schedule Card]: Close button (✕) clicked.");
            hideScheduleCard();
        });
    }

    if (btnShowScheduleCard) {
        btnShowScheduleCard.addEventListener("click", () => {
            console.log("[Schedule Card]: Re-show schedule button clicked.");
            showScheduleCard(true);
        });
    }

    if (scheduleDatePicker) {
        const todayDate = new Date();
        const yyyy = todayDate.getFullYear();
        const mm = String(todayDate.getMonth() + 1).padStart(2, '0');
        const dd = String(todayDate.getDate()).padStart(2, '0');
        scheduleDatePicker.value = `${yyyy}-${mm}-${dd}`;

        scheduleDatePicker.addEventListener("change", (e) => {
            const pickedDate = e.target.value;
            console.log("[Schedule Card]: Date picked:", pickedDate);
            if (scheduleCardHideTimer) {
                clearTimeout(scheduleCardHideTimer);
                scheduleCardHideTimer = null;
            }
            loadTodaySchedules(false, pickedDate);
        });
    }

    function escapeScheduleHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function getScheduleCategoryIcon(cat) {
        switch (cat) {
            case "rehab": return "🏃";
            case "bath": return "♨️";
            case "barber": return "✂️";
            case "visit": return "👨‍👩‍👧";
            case "meal": return "🍵";
            case "medication": return "💊";
            case "event": return "🌸";
            default: return "📝";
        }
    }

    function formatDateJapanese(dateStr) {
        try {
            const parts = dateStr.split("-");
            if (parts.length === 3) {
                const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
                const days = ["日", "月", "火", "水", "木", "金", "土"];
                return `${parseInt(parts[1], 10)}月${parseInt(parts[2], 10)}日(${days[d.getDay()]})`;
            }
        } catch (e) {}
        return dateStr;
    }

    async function loadTodaySchedules(autoAnnounce = false, targetDate = null) {
        if (!terminalId) return;
        if (isLoadingSchedules) {
            console.log("[loadTodaySchedules]: Already loading schedules, skipping duplicate request.");
            return;
        }
        isLoadingSchedules = true;

        let queryDate = targetDate;
        if (!queryDate && scheduleDatePicker && scheduleDatePicker.value) {
            queryDate = scheduleDatePicker.value;
        }

        try {
            const url = queryDate 
                ? `/api/users/terminal/${terminalId}/today_schedules?date=${encodeURIComponent(queryDate)}`
                : `/api/users/terminal/${terminalId}/today_schedules`;
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();
            
            if (scheduleDatePicker && data.date) {
                scheduleDatePicker.value = data.date;
            }

            if (todayDateBadge && data.date) {
                todayDateBadge.textContent = formatDateJapanese(data.date);
            }

            currentScheduleAnnouncementText = data.announcement_text || "";
            currentScheduleAnnouncementAudio = data.audio_base64 || "";
            cachedTodaySchedules = data.schedules || [];

            // 🤖 「予定カード」下の「みまもりさんの予定報告」テキストを更新
            if (mimamoriScheduleReportText && currentScheduleAnnouncementText) {
                mimamoriScheduleReportText.textContent = currentScheduleAnnouncementText;
            }

            if (todaySchedulesList) {
                todaySchedulesList.innerHTML = "";
                const schedules = data.schedules || [];
                if (schedules.length === 0) {
                    const emptyMsg = data.is_today 
                        ? "本日のご予定はありません。ごゆっくりお過ごしください。"
                        : `${formatDateJapanese(data.date)}のご予定はありません。`;
                    todaySchedulesList.innerHTML = `<div class="schedules-empty-msg">${emptyMsg}</div>`;
                } else {
                    const now = new Date();
                    const currentHHMM = String(now.getHours()).padStart(2, '0') + ":" + String(now.getMinutes()).padStart(2, '0');
                    
                    const upcoming = [];
                    const past = [];
                    schedules.forEach(s => {
                        let isPast = s.is_past;
                        if (typeof isPast !== "boolean") {
                            isPast = data.is_today ? Boolean(s.time && s.time < currentHHMM) : false;
                        }
                        if (isPast) {
                            past.push({ ...s, is_past: true });
                        } else {
                            upcoming.push({ ...s, is_past: false });
                        }
                    });

                    // 予定カードのHTML生成
                    const renderScheduleRow = (s, isPast) => {
                        const row = document.createElement("div");
                        row.className = isPast ? "schedule-item-row past" : "schedule-item-row";
                        row.dataset.scheduleId = s.id || "";
                        const icon = getScheduleCategoryIcon(s.category);
                        const locHtml = s.location ? `<span class="schedule-item-loc">📍 ${escapeScheduleHtml(s.location)}</span>` : "";
                        const notesHtml = s.notes ? `<span class="schedule-item-notes">${escapeScheduleHtml(s.notes)}</span>` : "";
                        const statusBadge = isPast 
                            ? `<span class="schedule-status-badge past">終了</span>` 
                            : `<span class="schedule-status-badge upcoming">予定</span>`;

                        row.innerHTML = `
                            <div class="schedule-time-badge">${escapeScheduleHtml(s.time)}</div>
                            <div class="schedule-item-icon">${icon}</div>
                            <div class="schedule-item-content">
                                <div class="schedule-item-title">
                                    ${escapeScheduleHtml(s.title)}
                                    ${statusBadge}
                                </div>
                                <div class="schedule-item-sub">
                                    ${locHtml}
                                    ${notesHtml}
                                </div>
                            </div>
                        `;
                        return row;
                    };

                    // 1. これからの予定を上部に表示
                    upcoming.forEach(s => {
                        todaySchedulesList.appendChild(renderScheduleRow(s, false));
                    });

                    // 2. 終了した予定がある場合、区切りを入れて下部に表示
                    if (past.length > 0) {
                        if (upcoming.length > 0) {
                            const divider = document.createElement("div");
                            divider.className = "schedule-divider-label";
                            divider.innerHTML = "<span>終了したご予定</span>";
                            todaySchedulesList.appendChild(divider);
                        }
                        past.forEach(s => {
                            todaySchedulesList.appendChild(renderScheduleRow(s, true));
                        });
                    }
                }
            }

            // 予定データ取得完了 (※起動時の勝手な音声再生や画面タップ乗っ取りは行いません)
        } catch (err) {
            console.warn("Failed to load today schedules:", err);
            if (todaySchedulesList) {
                todaySchedulesList.innerHTML = '<div class="schedules-empty-msg">予定の取得に失敗しました</div>';
            }
        } finally {
            isLoadingSchedules = false;
        }
    }

    function playScheduleAnnouncement() {
        if (isAnnouncementPlaying) {
            console.log("[Schedule Announcement]: Already playing, ignoring duplicate trigger.");
            return;
        }

        if (!currentScheduleAnnouncementAudio) {
            console.log("[Schedule Announcement]: Audio not loaded yet, fetching now...");
            loadTodaySchedules(false).then(() => {
                if (currentScheduleAnnouncementAudio && !isAnnouncementPlaying) {
                    playScheduleAnnouncement();
                }
            });
            return;
        }

        isAnnouncementPlaying = true;
        isAISpeaking = true;
        isTTSAnnouncing = true;

        if (btnReAnnounceSchedules) {
            btnReAnnounceSchedules.classList.add("playing");
        }

        if (aiResponseBox && currentScheduleAnnouncementText) {
            aiResponseBox.textContent = currentScheduleAnnouncementText;
        }
        if (mimamoriScheduleReportText && currentScheduleAnnouncementText) {
            mimamoriScheduleReportText.textContent = currentScheduleAnnouncementText;
        }

        statusText.textContent = "みまもりさんが予定をご案内中...";
        setLiveLampState("speaking");
        setAvatarState("speaking");

        // Suppress SpeechRec recognition buffer during system announcement
        window.isSpeechRecActive = false;

        console.log("[Schedule Announcement]: Playing audio announcement (size:", currentScheduleAnnouncementAudio.length, "bytes b64)...");

        playBase64Audio(
            currentScheduleAnnouncementAudio, 
            () => {
                console.log("[Schedule Announcement]: Finished speaking full schedule.");
                if (btnReAnnounceSchedules) {
                    btnReAnnounceSchedules.classList.remove("playing");
                    btnReAnnounceSchedules.classList.remove("attention-pulse");
                }
                lastAIAudioEndTime = Date.now();
                // Keep microphone muted for 1200ms after announcement to eliminate room reverberation
                setTimeout(() => {
                    isAnnouncementPlaying = false;
                    isAISpeaking = false;
                    isTTSAnnouncing = false;
                    lastAIAudioEndTime = Date.now();
                    window.isSpeechRecActive = false;
                    if (!isModalOpen) {
                        statusText.textContent = "お話しする準備ができました";
                        setLiveLampState("idle");
                        setAvatarState("idle");
                    }
                }, 1200);

                if (isBootScheduleAnnouncement) {
                    isBootScheduleAnnouncement = false;
                    if (scheduleCardHideTimer) clearTimeout(scheduleCardHideTimer);
                    scheduleCardHideTimer = setTimeout(() => {
                        hideScheduleCard();
                    }, 60000);
                }
            },
            (err) => {
                console.warn("[Schedule Announcement] Audio playback blocked by browser policy or stopped:", err);
                if (btnReAnnounceSchedules) {
                    btnReAnnounceSchedules.classList.remove("playing");
                }
                isAnnouncementPlaying = false;
                isAISpeaking = false;
                isTTSAnnouncing = false;
                window.isSpeechRecActive = false;
                if (!isModalOpen) {
                    statusText.textContent = "お話しする準備ができました";
                    setLiveLampState("idle");
                    setAvatarState("idle");
                }
            }
        );
    }

    // ⏰ 予定時刻の2分前リマインダー監視 (毎10秒チェック)
    function checkUpcomingScheduleReminders() {
        if (!cachedTodaySchedules || cachedTodaySchedules.length === 0) return;
        // 通話中や緊急ポップアップ表示中、発話中は割り込まない
        if (isAnnouncementPlaying || isAISpeaking || isIntercomCallActive) return;

        const now = new Date();
        const currentHHMM = String(now.getHours()).padStart(2, '0') + ":" + String(now.getMinutes()).padStart(2, '0');

        for (const s of cachedTodaySchedules) {
            const schedKey = s.id ? String(s.id) : (s.time + "_" + s.title);
            if (notified2MinScheduleIds.has(schedKey)) continue;

            // 2分前時刻を取得 (バックエンド計算値またはフォールバック)
            let remTime = s.reminder_time;
            if (!remTime && s.time) {
                try {
                    const [h, m] = s.time.split(":").map(Number);
                    let total = h * 60 + m - 2;
                    if (total < 0) total += 24 * 60;
                    remTime = String(Math.floor(total / 60)).padStart(2, '0') + ":" + String(total % 60).padStart(2, '0');
                } catch(e) {}
            }

            if (remTime && remTime === currentHHMM) {
                notified2MinScheduleIds.add(schedKey);
                console.log(`[みまもりさん 2分前通知]: 予定「${s.title}」の2分前です。自動案内を開始します。`);

                const reminderText = s.reminder_text || `${s.time}に${s.title}が予定されています`;

                // 1. 「今日のご予定」下の表示を更新 & 枠を強調アニメーション
                if (mimamoriScheduleReportText) {
                    mimamoriScheduleReportText.textContent = `📢 【予定のお知らせ】${reminderText}`;
                }
                if (mimamoriScheduleReportCard) {
                    mimamoriScheduleReportCard.classList.add("highlight-2min");
                    setTimeout(() => {
                        mimamoriScheduleReportCard.classList.remove("highlight-2min");
                    }, 40000);
                }

                // 該当予定の行を一時的にハイライト
                if (todaySchedulesList && s.id) {
                    const targetRow = todaySchedulesList.querySelector(`[data-schedule-id="${s.id}"]`);
                    if (targetRow) {
                        targetRow.classList.add("highlighted");
                        setTimeout(() => targetRow.classList.remove("highlighted"), 30000);
                    }
                }

                // 2. 音声アナウンス再生
                if (s.reminder_audio) {
                    playScheduleReminderAudio(s.reminder_audio, reminderText);
                }
                break; // 1回のチェックで1件のみ発話
            }
        }
    }

    function playScheduleReminderAudio(audioBase64, reminderText) {
        if (isAnnouncementPlaying || isAISpeaking) return;
        isAnnouncementPlaying = true;
        isAISpeaking = true;
        isTTSAnnouncing = true;
        window.isSpeechRecActive = false;

        statusText.textContent = "まもなく予定の時間です";
        setLiveLampState("speaking");
        setAvatarState("speaking");

        if (aiResponseBox) {
            aiResponseBox.textContent = reminderText;
        }

        playBase64Audio(
            audioBase64,
            () => {
                console.log("[みまもりさん 2分前通知]: 音声案内が完了しました。");
                setTimeout(() => {
                    isAnnouncementPlaying = false;
                    isAISpeaking = false;
                    isTTSAnnouncing = false;
                    window.isSpeechRecActive = false;
                    if (!isModalOpen) {
                        statusText.textContent = "お話しする準備ができました";
                        setLiveLampState("idle");
                        setAvatarState("idle");
                    }
                }, 800);
            },
            (err) => {
                console.warn("[みまもりさん 2分前通知] 音声再生終了:", err);
                isAnnouncementPlaying = false;
                isAISpeaking = false;
                isTTSAnnouncing = false;
                window.isSpeechRecActive = false;
                if (!isModalOpen) {
                    statusText.textContent = "お話しする準備ができました";
                    setLiveLampState("idle");
                    setAvatarState("idle");
                }
            }
        );
    }

    // 10秒おきに2分前予定リマインダーをチェック
    setInterval(checkUpcomingScheduleReminders, 10000);

    if (btnReAnnounceSchedules) {
        btnReAnnounceSchedules.addEventListener("click", () => {
            if (isAnnouncementPlaying) {
                console.log("[Schedule Announcement]: User clicked to stop playback.");
                if (activeAudio) {
                    try { activeAudio.pause(); } catch(e){}
                    activeAudio = null;
                }
                if (activeAudioUrl) {
                    try { URL.revokeObjectURL(activeAudioUrl); } catch(e){}
                    activeAudioUrl = null;
                }
                isAnnouncementPlaying = false;
                isAISpeaking = false;
                isTTSAnnouncing = false;
                btnReAnnounceSchedules.classList.remove("playing");
                statusText.textContent = "お話しする準備ができました";
                setLiveLampState("idle");
                setAvatarState("idle");
            } else {
                playScheduleAnnouncement();
            }
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

    // -------------------------------------------------------------
    // ⌚ スマートウォッチ連携 (Web Bluetooth API) & バイタルシミュレータ モジュール
    // -------------------------------------------------------------
    const watchBadge = document.getElementById("watch-badge");
    const watchModal = document.getElementById("watch-modal");
    const btnCloseWatchModal = document.getElementById("btn-close-watch-modal");
    const btnCloseWatchModalFooter = document.getElementById("btn-close-watch-modal-footer");
    const modalHrDisplay = document.getElementById("modal-hr-display");
    const modalSpo2Display = document.getElementById("modal-spo2-display");
    const btnBleConnect = document.getElementById("btn-ble-connect");
    const btnBleFast = document.getElementById("btn-ble-fast");
    const btnBleDisconnect = document.getElementById("btn-ble-disconnect");
    const bleDeviceInfo = document.getElementById("ble-device-info");

    const simBtnNormal = document.getElementById("sim-btn-normal");
    const simBtnTachycardia = document.getElementById("sim-btn-tachycardia");
    const simBtnHypoxia = document.getElementById("sim-btn-hypoxia");
    const simBtnAutoPulse = document.getElementById("sim-btn-auto-pulse");
    const autoPulseLabel = document.getElementById("auto-pulse-label");
    const simBtnSos = document.getElementById("sim-btn-sos");

    let bleDevice = null;
    let heartRateChar = null;
    let currentHeartRate = null;
    let currentSpO2 = null;
    let autoPulseTimer = null;

    function showTemporaryToast(message, duration = 3500) {
        let toast = document.getElementById("app-global-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "app-global-toast";
            toast.style.cssText = "position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(15, 23, 42, 0.9); color: #ffffff; padding: 14px 28px; border-radius: 30px; font-size: 1.15rem; font-weight: 700; z-index: 20000; box-shadow: 0 10px 25px rgba(0,0,0,0.3); transition: opacity 0.3s ease; pointer-events: none;";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = "1";
        if (toast._timer) clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.style.opacity = "0";
        }, duration);
    }

    function updateVitalDisplay(hr, spo2, isAlert = false, alertReason = "") {
        if (hr !== undefined && hr !== null) {
            currentHeartRate = hr;
            if (modalHrDisplay) modalHrDisplay.innerHTML = `${hr} <span style="font-size: 1.1rem; color: #64748b; font-weight: 600;">bpm</span>`;
        }
        if (spo2 !== undefined && spo2 !== null) {
            currentSpO2 = spo2;
            if (modalSpo2Display) modalSpo2Display.innerHTML = `${spo2} <span style="font-size: 1.1rem; color: #64748b; font-weight: 600;">%</span>`;
        }
        if (watchBadge) {
            const hrStr = currentHeartRate ? `${currentHeartRate} bpm` : "--";
            const spo2Str = currentSpO2 ? `${currentSpO2}%` : "--";
            watchBadge.textContent = `⌚ ❤️ ${hrStr} 🫁 ${spo2Str}`;
            if (isAlert) {
                watchBadge.className = "badge watch-badge alert";
                watchBadge.title = `⚠️ 異常検知: ${alertReason}`;
            } else {
                watchBadge.className = "badge watch-badge connected";
                watchBadge.title = "スマートウォッチ接続中 (タップで詳細表示)";
            }
        }
    }

    function sendVitalData(vitalPayload) {
        if (vitalPayload.heart_rate !== undefined) currentHeartRate = vitalPayload.heart_rate;
        if (vitalPayload.spo2 !== undefined) currentSpO2 = vitalPayload.spo2;
        updateVitalDisplay(currentHeartRate, currentSpO2);

        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "vital_data",
                ...vitalPayload
            }));
        } else if (currentUserId) {
            fetch(`/api/users/${currentUserId}/vitals`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(vitalPayload)
            }).catch(e => console.error("REST vital error:", e));
        }
    }

    function sendEmergencySOS(reason = "スマートウォッチ転倒/緊急SOS検知") {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "emergency_sos",
                reason: reason,
                heart_rate: currentHeartRate || 120,
                spo2: currentSpO2 || 95,
                source: "smartwatch_sos"
            }));
        } else if (currentUserId) {
            fetch(`/api/users/${currentUserId}/vitals`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    is_sos: true,
                    sos_reason: reason,
                    heart_rate: currentHeartRate || 120,
                    spo2: currentSpO2 || 95,
                    source: "smartwatch_sos"
                })
            }).catch(e => console.error("REST sos error:", e));
        }
        showTemporaryToast("🚨 緊急SOSをスタッフステーションへ送信しました！");
    }

    // Web Bluetooth API Heart Rate Handler
    function handleHeartRateMeasurement(event) {
        const value = event.target.value;
        const flags = value.getUint8(0);
        const rate16Bits = flags & 0x1;
        let hr = rate16Bits ? value.getUint16(1, /*littleEndian=*/true) : value.getUint8(1);
        console.log("[BLE Smartwatch] Heart Rate Measurement:", hr, "bpm");
        
        sendVitalData({
            heart_rate: hr,
            spo2: currentSpO2 || 98,
            source: "smartwatch_ble",
            raw_text: `スマートウォッチBLE心拍: ${hr} bpm`
        });
    }

    function handleBleNotification(charUuid, dataView) {
        if (!dataView) return;
        const bytes = new Uint8Array(dataView.buffer);
        const hexStr = Array.from(bytes).map(b => '0x' + b.toString(16).padStart(2, '0').toUpperCase()).join(' ');
        console.log(`[BLE Packet] 📥 ${charUuid} (${bytes.length} bytes):`, hexStr);

        // Simple heuristic for FitCloud / real-time heart rate / SpO2 packet
        // Many fitness trackers send packets starting with header or [type, length, ...]
        // If 4-20 bytes packet contains plausible heart rate (40-200)
        if (bytes.length >= 3) {
            for (let i = 0; i < bytes.length; i++) {
                // Look for plausible heart rate range if header or tag matches
                const val = bytes[i];
                if (val >= 45 && val <= 180 && (i === 1 || i === 2 || i === 3)) {
                    console.log(`[BLE Vital Candidate] Index ${i} has potential HR: ${val} bpm`);
                }
            }
        }
    }

    function onBLEDisconnected() {
        console.warn("[BLE Smartwatch] Device disconnected");
        if (window._bleKeepAliveTimer) {
            clearInterval(window._bleKeepAliveTimer);
            window._bleKeepAliveTimer = null;
        }
        if (bleDeviceInfo) bleDeviceInfo.textContent = "切断されました";
        if (btnBleConnect) btnBleConnect.classList.remove("hidden");
        if (btnBleFast) btnBleFast.classList.remove("hidden");
        if (btnBleDisconnect) btnBleDisconnect.classList.add("hidden");
        if (watchBadge) {
            watchBadge.className = "badge watch-badge";
            watchBadge.textContent = "⌚ ウォッチ切断";
        }
        showTemporaryToast("⌚ スマートウォッチとのBluetooth接続が切断されました");
    }

    async function connectBLESmartwatch(fastMode = false) {
        console.log(`[BLE Smartwatch] 🚀 connectBLESmartwatch triggered (fastMode: ${fastMode})`);
        if (!navigator.bluetooth) {
            console.error("[BLE Smartwatch] ❌ Web Bluetooth API is NOT supported on this browser/platform.");
            alert("お使いのブラウザは Web Bluetooth API に対応していません。\n(Android Chrome / Edge 等の対応ブラウザをご利用いただくか、シミュレータ機能をお試しください)");
            return;
        }

        try {
            const fitCloudCandidateServices = [
                'heart_rate',
                'battery_service',
                'device_information',
                'health_thermometer',
                'pulse_oximeter',
                '0000fee7-0000-1000-8000-00805f9b34fb', // FitCloudPro Main / Realtek
                '0000fee8-0000-1000-8000-00805f9b34fb',
                '0000fee9-0000-1000-8000-00805f9b34fb',
                '0000feea-0000-1000-8000-00805f9b34fb',
                '000055ff-0000-1000-8000-00805f9b34fb',
                '0000ffe0-0000-1000-8000-00805f9b34fb',
                '0000ffe1-0000-1000-8000-00805f9b34fb',
                '0000ffe2-0000-1000-8000-00805f9b34fb',
                '0000fff0-0000-1000-8000-00805f9b34fb',
                '0000fff1-0000-1000-8000-00805f9b34fb',
                '0000fff2-0000-1000-8000-00805f9b34fb',
                '0000180d-0000-1000-8000-00805f9b34fb',
                '0000180f-0000-1000-8000-00805f9b34fb',
                '0000180a-0000-1000-8000-00805f9b34fb',
                '6e400001-b5a3-f393-e0a9-e50e24dcca9e'  // Nordic UART
            ];

            if (fastMode) {
                if (bleDeviceInfo) bleDeviceInfo.textContent = "B16Pro を高速スキャン中... (一覧から選択してください)";
                console.log("[BLE Smartwatch] 🚀 Starting targeted scan for B16Pro...");
                bleDevice = await navigator.bluetooth.requestDevice({
                    filters: [
                        { namePrefix: 'B16' },
                        { namePrefix: 'b16' },
                        { name: 'B16Pro' }
                    ],
                    optionalServices: fitCloudCandidateServices
                });
            } else {
                if (bleDeviceInfo) bleDeviceInfo.textContent = "Bluetooth機器をスキャン中... (一覧から B16Pro を選択してください)";
                console.log("[BLE Smartwatch] 🔍 Starting broad scan (acceptAllDevices)...");
                bleDevice = await navigator.bluetooth.requestDevice({
                    acceptAllDevices: true,
                    optionalServices: fitCloudCandidateServices
                });
            }

            const rawName = bleDevice.name || "";
            const deviceIdShort = bleDevice.id ? bleDevice.id.slice(0, 6) : "Unknown";
            let displayName = rawName || `名称不明デバイス (${deviceIdShort})`;

            console.log("[BLE Smartwatch] ✅ User selected device:", {
                id: bleDevice.id,
                name: rawName,
                displayName: displayName
            });

            if (bleDeviceInfo) bleDeviceInfo.textContent = `接続試行中: ${displayName}...`;
            bleDevice.addEventListener('gattserverdisconnected', onBLEDisconnected);

            console.log("[BLE Smartwatch] Connecting to GATT server...");
            const server = await bleDevice.gatt.connect();
            console.log("[BLE Smartwatch] ✅ GATT Server connected successfully!", server);

            // 2. Discover all available primary services
            let allServices = [];
            try {
                allServices = await server.getPrimaryServices();
                console.log("[BLE Smartwatch] 🎯 getPrimaryServices() found:", allServices.map(s => s.uuid));
            } catch (e) {
                console.warn("[BLE Smartwatch] Bulk getPrimaryServices() error:", e.name, e.message);
            }

            const discoveredServices = [];
            // If getPrimaryServices returned services, explore their characteristics
            if (allServices && allServices.length > 0) {
                for (const svc of allServices) {
                    discoveredServices.push(svc.uuid);
                    console.log(`[BLE Smartwatch] 🎯 Discovered Service: ${svc.uuid}`);
                    try {
                        const chars = await svc.getCharacteristics();
                        console.log(`[BLE Smartwatch]    Chars in ${svc.uuid}:`, chars.map(c => c.uuid));
                        for (const ch of chars) {
                            console.log(`[BLE Smartwatch]      Char ${ch.uuid}:`, {
                                read: ch.properties.read,
                                write: ch.properties.write,
                                notify: ch.properties.notify,
                                indicate: ch.properties.indicate
                            });
                            if (ch.properties.notify || ch.properties.indicate) {
                                try {
                                    await ch.startNotifications();
                                    ch.addEventListener('characteristicvaluechanged', (e) => {
                                        handleBleNotification(ch.uuid, e.target.value);
                                    });
                                    console.log(`[BLE Smartwatch]      🔔 Subscribed to notifications on ${ch.uuid}`);
                                } catch (subErr) {
                                    console.warn(`[BLE Smartwatch]      Failed to subscribe to ${ch.uuid}:`, subErr.message);
                                }
                            }
                        }
                    } catch (charErr) {
                        console.warn(`[BLE Smartwatch]    Chars query error in ${svc.uuid}:`, charErr.message);
                    }
                }
            } else {
                // Fallback probing of candidate services individually
                for (const svcUuid of fitCloudCandidateServices) {
                    try {
                        const svc = await server.getPrimaryService(svcUuid);
                        discoveredServices.push(svc.uuid);
                        console.log(`[BLE Smartwatch] 🎯 Probed Service: ${svc.uuid}`);
                        const chars = await svc.getCharacteristics();
                        for (const ch of chars) {
                            if (ch.properties.notify || ch.properties.indicate) {
                                try {
                                    await ch.startNotifications();
                                    ch.addEventListener('characteristicvaluechanged', (e) => {
                                        handleBleNotification(ch.uuid, e.target.value);
                                    });
                                    console.log(`[BLE Smartwatch]      🔔 Subscribed to notifications on ${ch.uuid}`);
                                } catch (subErr) {
                                    console.warn(`[BLE Smartwatch]      Failed to subscribe to ${ch.uuid}:`, subErr.message);
                                }
                            }
                        }
                    } catch (svcErr) {
                        console.log(`[BLE Probing] Service ${svcUuid} not found/accessible:`, svcErr.name, svcErr.message);
                    }
                }
            }
            console.log("[BLE Smartwatch] 📋 Total Discovered GATT Services:", discoveredServices);

            // Attempt standard heart_rate service
            let heartRateService = null;
            try {
                heartRateService = await server.getPrimaryService('heart_rate');
            } catch(e) {}

            if (heartRateService) {
                heartRateChar = await heartRateService.getCharacteristic('heart_rate_measurement');
                await heartRateChar.startNotifications();
                heartRateChar.addEventListener('characteristicvaluechanged', handleHeartRateMeasurement);
                if (bleDeviceInfo) bleDeviceInfo.textContent = `✅ 接続完了 (標準心拍サービス稼働): ${displayName}`;
                console.log("[BLE Smartwatch] ✅ Subscribed to standard heart_rate_measurement!");
            } else {
                if (bleDeviceInfo) bleDeviceInfo.textContent = `✅ 接続完了 (独自GATT稼働中): ${displayName}`;
                console.log("[BLE Smartwatch] Device connected. FitCloudPro GATT protocol. Discovered:", discoveredServices);
            }

            // Start BLE Keepalive ping (every 5 seconds) to prevent device sleep
            if (window._bleKeepAliveTimer) clearInterval(window._bleKeepAliveTimer);
            window._bleKeepAliveTimer = setInterval(async () => {
                if (bleDevice && bleDevice.gatt && bleDevice.gatt.connected) {
                    console.log("[BLE KeepAlive] Connection active.");
                } else {
                    clearInterval(window._bleKeepAliveTimer);
                }
            }, 5000);

            if (btnBleConnect) btnBleConnect.classList.add("hidden");
            if (btnBleFast) btnBleFast.classList.add("hidden");
            if (btnBleDisconnect) btnBleDisconnect.classList.remove("hidden");
            if (watchBadge) {
                watchBadge.className = "badge watch-badge connected";
                watchBadge.textContent = `⌚ ${displayName.slice(0, 10)}`;
            }
            showTemporaryToast(`⌚ ${displayName} と接続しました`);
        } catch (err) {
            console.error("[BLE Smartwatch] ❌ BLE Connection failed:", {
                name: err.name,
                message: err.message,
                stack: err.stack
            });
            if (bleDeviceInfo) {
                if (err.name === "NotFoundError") {
                    bleDeviceInfo.textContent = "スキャンがキャンセルされたか、デバイスが見つかりませんでした。(ウォッチ側面ボタン長押しで「再起動」をお試しください)";
                } else if (err.name === "NetworkError" || err.message?.includes("connection failed")) {
                    bleDeviceInfo.textContent = "接続エラー: 専用アプリがBluetoothを占有している可能性があります。スマホ側アプリを一度終了して再試行してください。";
                } else {
                    bleDeviceInfo.textContent = `接続エラー (${err.name}): ${err.message || err}`;
                }
            }
        }
    }

    function disconnectBLESmartwatch() {
        if (bleDevice && bleDevice.gatt && bleDevice.gatt.connected) {
            bleDevice.gatt.disconnect();
        }
        onBLEDisconnected();
    }

    function initSmartwatchModule() {
        if (watchBadge && watchModal) {
            watchBadge.addEventListener("click", () => watchModal.classList.remove("hidden"));
        }
        if (btnCloseWatchModal && watchModal) {
            btnCloseWatchModal.addEventListener("click", () => watchModal.classList.add("hidden"));
        }
        if (btnCloseWatchModalFooter && watchModal) {
            btnCloseWatchModalFooter.addEventListener("click", () => watchModal.classList.add("hidden"));
        }

        if (btnBleConnect) {
            btnBleConnect.addEventListener("click", () => connectBLESmartwatch(false));
        }
        if (btnBleFast) {
            btnBleFast.addEventListener("click", () => connectBLESmartwatch(true));
        }
        if (btnBleDisconnect) {
            btnBleDisconnect.addEventListener("click", disconnectBLESmartwatch);
        }

        // Simulator Event Listeners
        if (simBtnNormal) {
            simBtnNormal.addEventListener("click", () => {
                sendVitalData({
                    heart_rate: 72,
                    spo2: 98,
                    source: "simulator",
                    raw_text: "シミュレータ: 正常バイタル (72bpm / 98%)"
                });
                showTemporaryToast("🟢 正常バイタルを送信しました (心拍 72bpm / SpO2 98%)");
            });
        }

        if (simBtnTachycardia) {
            simBtnTachycardia.addEventListener("click", () => {
                sendVitalData({
                    heart_rate: 128,
                    spo2: 97,
                    source: "simulator",
                    raw_text: "シミュレータ: 頻脈アラートテスト (128bpm)"
                });
                showTemporaryToast("⚠️ 頻脈アラートを送信しました (心拍 128bpm)");
            });
        }

        if (simBtnHypoxia) {
            simBtnHypoxia.addEventListener("click", () => {
                sendVitalData({
                    heart_rate: 85,
                    spo2: 91,
                    source: "simulator",
                    raw_text: "シミュレータ: 低酸素アラートテスト (SpO2 91%)"
                });
                showTemporaryToast("🫁 低酸素アラートを送信しました (SpO2 91%)");
            });
        }

        if (simBtnAutoPulse) {
            simBtnAutoPulse.addEventListener("click", () => {
                if (autoPulseTimer) {
                    clearInterval(autoPulseTimer);
                    autoPulseTimer = null;
                    if (autoPulseLabel) autoPulseLabel.textContent = "▶️ 自動心拍パルス";
                    showTemporaryToast("自動心拍パルス送信を停止しました");
                } else {
                    if (autoPulseLabel) autoPulseLabel.textContent = "⏹️ 自動送信停止";
                    showTemporaryToast("自動心拍パルス送信を開始しました (5秒間隔)");
                    const pulse = 70 + Math.floor(Math.random() * 8);
                    sendVitalData({ heart_rate: pulse, spo2: 98, source: "simulator" });
                    
                    autoPulseTimer = setInterval(() => {
                        const hr = 70 + Math.floor(Math.random() * 8);
                        sendVitalData({ heart_rate: hr, spo2: 98, source: "simulator" });
                    }, 5000);
                }
            });
        }

        if (simBtnSos) {
            simBtnSos.addEventListener("click", () => {
                sendEmergencySOS("スマートウォッチ転倒/緊急SOS検知");
            });
        }

        // 📋 One-tap Copy Diagnostic and BLE Logs Handler
        async function copyDebugLogs(triggerBtn) {
            const time = new Date().toISOString();
            const ua = navigator.userAgent;
            const bleSupported = !!navigator.bluetooth;
            const isHttps = window.location.protocol === 'https:';
            const currentBleStatus = bleDeviceInfo ? bleDeviceInfo.textContent.trim() : "未接続";
            
            let report = `=== Care-Link 端末診断＆デバッグログ ===\n`;
            report += `取得日時: ${time}\n`;
            report += `URL: ${window.location.href}\n`;
            report += `端末/ブラウザ: ${ua}\n`;
            report += `Web Bluetooth対応: ${bleSupported ? "○ 対応" : "× 非対応"}\n`;
            report += `HTTPSセキュア通信: ${isHttps ? "○ (HTTPS)" : "× (非HTTPS)"}\n`;
            report += `BLE表示ステータス: ${currentBleStatus}\n`;
            report += `WS接続状態: ${ws && ws.readyState === WebSocket.OPEN ? "OPEN" : "CLOSED"}\n`;
            report += `Gemini Live WS状態: ${liveWs && liveWs.readyState === WebSocket.OPEN ? "OPEN" : "CLOSED"}\n`;
            report += `\n--- 直近のコンソールログ (最新 ${window.__carelink_logs ? window.__carelink_logs.length : 0} 件) ---\n`;
            if (window.__carelink_logs && window.__carelink_logs.length > 0) {
                report += window.__carelink_logs.join('\n');
            } else {
                report += "(記録されたログはありません)";
            }

            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(report);
                } else {
                    const ta = document.createElement("textarea");
                    ta.value = report;
                    ta.style.position = "fixed";
                    ta.style.opacity = "0";
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand("copy");
                    document.body.removeChild(ta);
                }
                showTemporaryToast("✅ デバッグログをクリップボードにコピーしました！");
                if (triggerBtn) {
                    const origHtml = triggerBtn.innerHTML;
                    triggerBtn.innerHTML = "<span>✅</span><span>コピー完了！</span>";
                    const origBg = triggerBtn.style.background;
                    triggerBtn.style.background = "#10b981";
                    setTimeout(() => {
                        triggerBtn.innerHTML = origHtml;
                        triggerBtn.style.background = origBg;
                    }, 2500);
                }
            } catch (err) {
                console.error("Copy logs failed:", err);
                prompt("以下のログを手動でコピーしてください:", report);
            }
        }

        const btnCopyDebugLogs = document.getElementById("btn-copy-debug-logs");
        if (btnCopyDebugLogs) {
            btnCopyDebugLogs.addEventListener("click", () => copyDebugLogs(btnCopyDebugLogs));
        }
        if (headerBtnCopyLogs) {
            headerBtnCopyLogs.addEventListener("click", () => copyDebugLogs(headerBtnCopyLogs));
        }
    }

    // 🎨 Etegami Image Generation Engine Selector & Confirmation Modal Controls
    function updateEngineToggleUI(engine) {
        const btnFree = document.getElementById("btn-engine-toggle-free");
        const btnPaid = document.getElementById("btn-engine-toggle-paid");
        const isPaid = (engine === "google_image" || engine === "paid" || engine === "gemini_imagen");
        if (btnFree) btnFree.classList.toggle("active", !isPaid);
        if (btnPaid) btnPaid.classList.toggle("active", isPaid);
    }

    function initEtegamiEngineSelector() {
        const btnFree = document.getElementById("btn-engine-toggle-free");
        const btnPaid = document.getElementById("btn-engine-toggle-paid");
        const btnModalFree = document.getElementById("btn-modal-choose-free");
        const btnModalPaid = document.getElementById("btn-modal-choose-paid");
        const confirmModal = document.getElementById("etegami-engine-confirm-modal");

        const sendEngineChoice = (engine) => {
            updateEngineToggleUI(engine);
            if (confirmModal) confirmModal.classList.add("hidden");

            // 🛑 即座にジェミナイの音声を完全中断＆アバター・ランプを停止
            stopLiveAudioPlayback();
            setAvatarState("idle");
            setLiveLampState("idle");

            // モデル決定完了 -> モーダル選択ロック解除して聞き取り中へ
            isEtegamiModalSelecting = false;
            isEtegamiConfirming = false;
            isModalOpen = false;
            hasConfirmedEtegamiModeAndEngine = true;
            setEtegamiPhase(ETEGAMI_PHASE.LISTENING);

            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                console.log("[Etegami Engine]: Sending set_image_engine ->", engine);
                liveWs.send(JSON.stringify({
                    type: "set_image_engine",
                    engine: engine
                }));
            }
        };

        if (btnFree) {
            btnFree.addEventListener("click", () => sendEngineChoice("pollinations"));
        }
        if (btnPaid) {
            btnPaid.addEventListener("click", () => sendEngineChoice("google_image"));
        }
        if (btnModalFree) {
            btnModalFree.addEventListener("click", () => sendEngineChoice("pollinations"));
        }
        if (btnModalPaid) {
            btnModalPaid.addEventListener("click", () => sendEngineChoice("google_image"));
        }
    }

    // 🖌️ 絵手紙モード選択モーダル（昔の絵か新規か）の制御
    function initEtegamiModeConfirm() {
        const modeModal = document.getElementById("etegami-mode-confirm-modal");
        const btnBase = document.getElementById("btn-modal-choose-base");
        const btnNew = document.getElementById("btn-modal-choose-new");

        const sendModeChoice = (mode) => {
            if (modeModal) modeModal.classList.add("hidden");

            // 🛑 即座にジェミナイの音声を完全中断＆アバター・ランプを停止
            stopLiveAudioPlayback();
            setAvatarState("idle");
            setLiveLampState("idle");

            if (mode === "asset_base") {
                // ベースモデル選択完了 -> モーダル選択ロック解除して聞き取り中へ
                isEtegamiModalSelecting = false;
                isEtegamiConfirming = false;
                isModalOpen = false;
                hasConfirmedEtegamiModeAndEngine = true;
                setEtegamiPhase(ETEGAMI_PHASE.LISTENING);
            } else {
                // 新しい絵を描く -> 次の画像AIモデル選択モーダルへ進むため、選択中ロックは維持
                isEtegamiModalSelecting = true;
                isEtegamiConfirming = true;
                isModalOpen = true;
                const engineModal = document.getElementById("etegami-engine-confirm-modal");
                if (engineModal) engineModal.classList.remove("hidden");
            }

            const payload = {
                type: "set_prepare_mode",
                mode: mode
            };
            if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                console.log("[Etegami Mode]: Sending set_prepare_mode via liveWs ->", payload);
                liveWs.send(JSON.stringify(payload));
            } else if (ws && ws.readyState === WebSocket.OPEN) {
                console.log("[Etegami Mode]: Sending set_prepare_mode via ws ->", payload);
                ws.send(JSON.stringify(payload));
            }
        };

        if (btnBase) {
            btnBase.addEventListener("click", () => sendModeChoice("asset_base"));
        }
        if (btnNew) {
            btnNew.addEventListener("click", () => sendModeChoice("generate_new"));
        }
    }

    // 👂 ① 聞き取り中パネルの「次へ進む」「内容クリア」ボタン制御
    function initEtegamiListeningNext() {
        const btnNext = document.getElementById("btn-etegami-listening-next");
        const btnClear = document.getElementById("btn-etegami-listening-clear");

        if (btnClear) {
            btnClear.addEventListener("click", (e) => {
                e.stopPropagation();
                console.log("[Etegami]: Resident pressed '内容クリア' -> Clearing transcript & motif");
                etegamiAccumulatedUtterances = [];
                etegamiAccumulatedText = "";
                currentEtegamiTranscript = "";
                currentEtegamiMotif = "";
                const listeningTextEl = document.getElementById("etegami-listening-text");
                if (listeningTextEl) {
                    listeningTextEl.textContent = "（お話しされた内容をお待ちしています…）";
                }
                showTemporaryToast("🗑️ 聞き取った内容をクリアしました。もう一度お話しくださいね。", 4000);
                const payload = {
                    type: "clear_etegami_transcript"
                };
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify(payload));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(payload));
                }
            });
        }

        if (btnNext) {
            btnNext.addEventListener("click", (e) => {
                e.stopPropagation();
                console.log("[Etegami]: Resident pressed 'この内容で次に進む' -> Advancing to CONFIRM_CONTENT");
                const fullText = etegamiAccumulatedText || currentEtegamiTranscript || "";
                let chosenMotif = currentEtegamiMotif;
                if (!chosenMotif && fullText) {
                    const clean = fullText.replace(/[。、！？\s]/g, "");
                    chosenMotif = clean.length > 24 ? clean.substring(0, 24) : clean;
                }
                chosenMotif = chosenMotif || "思い出の風景";
                currentEtegamiMotif = chosenMotif;

                setEtegamiPhase(ETEGAMI_PHASE.CONFIRM_CONTENT, {
                    motif: chosenMotif,
                    accumulated_text: fullText
                });

                const payload = {
                    type: "etegami_listening_next",
                    motif: chosenMotif,
                    accumulated_text: fullText
                };
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify(payload));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(payload));
                }
            });
        }
    }

    // 👂 ② 内容確認モーダルの制御（はい/いいえが押されるまで進まない）
    function initEtegamiMotifConfirm() {
        const btnOk = document.getElementById("btn-motif-confirm-ok");
        const btnRetry = document.getElementById("btn-motif-confirm-retry");

        if (btnOk) {
            btnOk.addEventListener("click", (e) => {
                e.stopPropagation();
                if (currentEtegamiPhase !== ETEGAMI_PHASE.CONFIRM_CONTENT) {
                    console.log("[Etegami Motif Confirm]: Ignored OK click because not in CONFIRM_CONTENT phase:", currentEtegamiPhase);
                    return;
                }
                if (Date.now() - lastConfirmContentOpenTime < 800) {
                    console.log("[Etegami Motif Confirm]: Ignored premature OK click within 800ms guard");
                    return;
                }
                console.log("[Etegami Motif Confirm]: Resident confirmed motif (はい) -> Advancing to DRAWING");
                const fullText = etegamiAccumulatedText || currentEtegamiTranscript || "";
                setEtegamiPhase(ETEGAMI_PHASE.DRAWING, {
                    motif: currentEtegamiMotif || "思い出の風景",
                    prompt_en: currentEtegamiPromptEn,
                    accumulated_text: fullText
                });
                const payload = {
                    type: "etegami_motif_confirm_response",
                    confirmed: true,
                    motif: currentEtegamiMotif || "思い出の風景",
                    accumulated_text: fullText
                };
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify(payload));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(payload));
                }
            });
        }

        if (btnRetry) {
            btnRetry.addEventListener("click", (e) => {
                e.stopPropagation();
                if (currentEtegamiPhase !== ETEGAMI_PHASE.CONFIRM_CONTENT) {
                    console.log("[Etegami Motif Confirm]: Ignored Retry click because not in CONFIRM_CONTENT phase:", currentEtegamiPhase);
                    return;
                }
                if (Date.now() - lastConfirmContentOpenTime < 800) {
                    console.log("[Etegami Motif Confirm]: Ignored premature Retry click within 800ms guard");
                    return;
                }
                console.log("[Etegami Motif Confirm]: Resident requested retry (いいえ) -> Returning to LISTENING");
                setEtegamiPhase(ETEGAMI_PHASE.LISTENING);

                const payload = {
                    type: "etegami_motif_confirm_response",
                    confirmed: false
                };
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify(payload));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(payload));
                }
                showTemporaryToast("🎨 承知しました。どのような絵手紙を描きましょうか？教えてくださいね。", 4500);
            });
        }
    }

    // 🖼️ ④ 完成確認モーダルの制御（はい/いいえが押されるまで進まない）
    function initEtegamiArtworkConfirm() {
        const btnOk = document.getElementById("btn-artwork-confirm-ok");
        const btnRetry = document.getElementById("btn-artwork-confirm-retry");

        if (btnOk) {
            btnOk.addEventListener("click", (e) => {
                e.stopPropagation();
                if (currentEtegamiPhase !== ETEGAMI_PHASE.CONFIRM_FINISH) {
                    console.log("[Etegami Artwork Confirm]: Ignored OK click because not in CONFIRM_FINISH phase:", currentEtegamiPhase);
                    return;
                }
                if (Date.now() - lastConfirmFinishOpenTime < 800) {
                    console.log("[Etegami Artwork Confirm]: Ignored premature OK click within 800ms guard");
                    return;
                }
                console.log("[Etegami Artwork Confirm]: Resident approved artwork (はい) -> Completing & Saving!");
                setEtegamiPhase(ETEGAMI_PHASE.COMPLETED);
                etegamiAccumulatedUtterances = [];
                etegamiAccumulatedText = "";
                currentEtegamiTranscript = "";
                currentEtegamiMotif = "";

                showTemporaryToast("💮 絵手紙が完成しました。通常会話に戻します。", 5000);
                playTTSVoice("絵手紙が完成しました。通常会話に戻します。", true);
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "complete_etegami" }));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "complete_etegami" }));
                }
            });
        }

        if (btnRetry) {
            btnRetry.addEventListener("click", (e) => {
                e.stopPropagation();
                if (currentEtegamiPhase !== ETEGAMI_PHASE.CONFIRM_FINISH) {
                    console.log("[Etegami Artwork Confirm]: Ignored Retry click because not in CONFIRM_FINISH phase:", currentEtegamiPhase);
                    return;
                }
                if (Date.now() - lastConfirmFinishOpenTime < 800) {
                    console.log("[Etegami Artwork Confirm]: Ignored premature Retry click within 800ms guard");
                    return;
                }
                console.log("[Etegami Artwork Confirm]: Resident explicitly requested redraw (いいえ) -> Returning to LISTENING");
                setEtegamiPhase(ETEGAMI_PHASE.LISTENING);

                const payload = {
                    type: "etegami_artwork_retry"
                };
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify(payload));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(payload));
                }
                showTemporaryToast("🎨 みまもりさん：承知しました。どのように描き直しましょうか？教えてくださいね。", 4500);
            });
        }
    }

    // 💾 絵手紙保存確認モーダルの制御（レガシー互換用）
    function initEtegamiSaveConfirm() {
        const modal = document.getElementById("etegami-save-confirm-modal");
        const btnYes = document.getElementById("btn-save-confirm-yes");
        const btnNo = document.getElementById("btn-save-confirm-no");

        if (btnYes) {
            btnYes.addEventListener("click", (e) => {
                e.stopPropagation();
                if (modal) modal.classList.add("hidden");
                setEtegamiPhase(ETEGAMI_PHASE.COMPLETED);
                showTemporaryToast("💮 絵手紙が完成しました。通常会話に戻します。", 5000);
                playTTSVoice("絵手紙が完成しました。通常会話に戻します。", true);
                if (liveWs && liveWs.readyState === WebSocket.OPEN) {
                    liveWs.send(JSON.stringify({ type: "complete_etegami" }));
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "complete_etegami" }));
                }
            });
        }

        if (btnNo) {
            btnNo.addEventListener("click", (e) => {
                e.stopPropagation();
                if (modal) modal.classList.add("hidden");
                setEtegamiPhase(ETEGAMI_PHASE.LISTENING);
                showTemporaryToast("🎨 みまもりさん：下絵のまま残しておきますね。いつでも保存できますよ。", 4500);
            });
        }
    }

    // Initialize application connection
    async function initApp() {
        try {
            await checkSystemInfo();
            updateDebugUI();
            await checkRegistration(false);
            connectWS();
            initSmartwatchModule();
            initEtegamiEngineSelector();
            initEtegamiModeConfirm();
            initEtegamiListeningNext();
            initEtegamiMotifConfirm();
            initEtegamiArtworkConfirm();
            initEtegamiSaveConfirm();

            // 起動時の初期化：絵手紙確認モーダルとセッション生成フラグを確実にリセット
            [
                "etegami-artwork-confirm-modal",
                "etegami-save-confirm-modal",
                "etegami-motif-confirm-modal",
                "etegami-mode-confirm-modal",
                "etegami-engine-confirm-modal"
            ].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.add("hidden");
            });
            isEtegamiConfirming = false;
            hasActiveSessionGeneration = false;
            preSpeechRingBuffer = [];

            if (isDebugMode) {
                connectLiveWS();
            }
        } catch (e) {
            console.error("App init error:", e);
        }
    }
    initApp();
});

