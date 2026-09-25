import os
import time
import json
import asyncio
import base64
import re
import numpy as np
import websockets
from datetime import datetime
from typing import Callable, Optional
from backend import config
from backend.speech import get_whisper_model, is_japanese_speech

GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

class PIIGuardrailMonitor:
    """
    Parallel background PII Guardrail Inspector.
    Accumulates raw 16kHz PCM audio chunks from user speech, periodically runs Whisper STT,
    and checks for personal information (real names, phone numbers, addresses, etc.).
    """
    def __init__(
        self,
        user: dict,
        on_pii_detected: Callable[[str, str], None],
        on_transcription: Optional[Callable[[str], None]] = None
    ):
        self.user = user
        self.on_pii_detected = on_pii_detected
        self.on_transcription = on_transcription
        self.audio_buffer = bytearray()
        self.last_check_len = 0
        self.last_speech_text = ""
        self.is_processing = False
        self.is_active = True
        self.lock = asyncio.Lock()
        
        # Build prohibited terms list (real full name, family name, etc.)
        self.prohibited_terms = ["田中太郎", "山田太郎", "佐藤", "鈴木", "高橋", "田中", "渡辺", "伊藤", "山本", "中村", "小林", "加藤", "山田"]
        real_name = user.get("name", "")
        if real_name:
            self.prohibited_terms.append(real_name.strip())
            # Add surname if full name has space or > 1 char
            parts = real_name.split()
            if len(parts) > 1:
                self.prohibited_terms.append(parts[0])
            elif len(real_name) >= 2:
                # e.g., "山田" from "山田太郎"
                self.prohibited_terms.append(real_name[:2])
                
        # Regex patterns for telephone numbers, addresses, my-number, and self-introduction/names
        self.pii_patterns = [
            (re.compile(r'\d{2,4}[-\s]?\d{2,4}[-\s]?\d{4}'), "電話番号等の個人情報が含まれていました。"),
            (re.compile(r'\d{3}[-\s]?\d{4}'), "郵便番号等の個人情報が含まれていました。"),
            (re.compile(r'\d{12}'), "マイナンバー等の識別番号が含まれていました。"),
            (re.compile(r'(東京都|大阪府|京都府|北海道|.{2,3}県).{1,5}(市|区|町|村)'), "住所情報が含まれていました。"),
            (re.compile(r'(私|ぼく|わし|自分)の(名前|氏名)は'), "氏名・お名前の宣言が含まれていました。"),
            (re.compile(r'名前は[^\s、,。]{1,8}(です|と申します|と言います)'), "氏名・お名前の宣言が含まれていました。"),
            (re.compile(r'[^\s、,。]{2,8}(と申します|と言います)'), "氏名・名乗りの表現が含まれていました。"),
        ]

    def add_pcm_chunk_sync(self, chunk: bytes):
        """Synchronously appends raw 16kHz 16bit PCM audio chunk without async lock overhead."""
        if not self.is_active or not chunk:
            return
            
        self.audio_buffer.extend(chunk)
        # Check every ~3.0 seconds of audio (16000 Hz * 2 bytes * 3.0s = 96000 bytes)
        if len(self.audio_buffer) - self.last_check_len >= 96000:
            self.last_check_len = len(self.audio_buffer)
            # Run inspection in background task to avoid blocking main audio relay
            asyncio.create_task(self._inspect_buffer())

    async def add_pcm_chunk(self, chunk: bytes):
        self.add_pcm_chunk_sync(chunk)

    async def _inspect_buffer(self):
        """Runs Whisper STT in threadpool and validates text for PII."""
        if self.is_processing or not self.is_active or len(self.audio_buffer) < 96000:
            return
            
        self.is_processing = True
        try:
            # Copy buffer up to current length
            async with self.lock:
                buf_copy = bytes(self.audio_buffer[-160000:]) # Last ~5 seconds max
                
            if len(buf_copy) % 2 != 0:
                buf_copy = buf_copy[:-1]
                
            if len(buf_copy) < 32000:
                return

            # Convert int16 PCM bytes to float32 numpy array for Whisper
            audio_np = np.frombuffer(buf_copy, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Energy check: Skip Whisper if audio is essentially silence / room noise (prevents hallucinations)
            rms = float(np.sqrt(np.mean(audio_np ** 2)))
            if rms < 0.016:
                return

            # Execute Faster-Whisper / Whisper STT in threadpool executor
            loop = asyncio.get_running_loop()
            
            def _stt():
                from backend.speech import transcribe_numpy_array
                return transcribe_numpy_array(audio_np)
                
            text = await loop.run_in_executor(None, _stt)
            text = (text or "").strip()
            
            if not text or len(text) < 3:
                return

            # Filter out silence hallucinations & system audio echo
            from backend.speech import has_repetitive_loop, is_japanese_speech
            if has_repetitive_loop(text) or not is_japanese_speech(text):
                print(f"[PII Guardrail Whisper Filtered Invalid/Loop]: '{text}'")
                return

            hallucinations = [
                "ご視聴", "チャンネル登録", "お会いしましょう", "会話が終了します",
                "今回の会話はここまで", "動画をご覧", "高評価", "字幕", "提供",
                "個人情報保護のため", "会話を一時停止", "個人情報は話さない",
                "スタッフに連絡する場合は", "ボタンを押してください",
                "逃げ出せ", "逃げろ", "逃げて", "おやすみなさい"
            ]
            if any(h in text for h in hallucinations):
                print(f"[PII Guardrail Whisper Filtered Hallucination/Echo]: '{text}'")
                return
                
            print(f"[PII Guardrail Whisper Inspection]: '{text}'")
            self.last_speech_text = text
            if self.on_transcription:
                self.on_transcription(text)
            
            # 1. Check prohibited real names
            for term in self.prohibited_terms:
                if len(term) >= 2 and term in text:
                    print(f"[PII ALERT TRIGGERED]: Found real name term '{term}' in speech: '{text}'")
                    self.is_active = False
                    if self.on_pii_detected:
                        self.on_pii_detected("real_name", f"実名・お名前（{term}）の語句が含まれていました。")
                    return
                    
            # 2. Check regex PII patterns
            for pat, reason in self.pii_patterns:
                if pat.search(text):
                    print(f"[PII ALERT TRIGGERED]: Found PII pattern in speech: '{text}' (reason: {reason})")
                    self.is_active = False
                    if self.on_pii_detected:
                        self.on_pii_detected("pattern_match", reason)
                    return

        except Exception as e:
            print(f"[PII Guardrail Error]: {e}")
        finally:
            self.is_processing = False

    def reset(self):
        """Resets audio buffer and re-enables active monitoring for next conversation turn."""
        self.audio_buffer.clear()
        self.last_check_len = 0
        self.last_speech_text = ""
        self.is_processing = False
        self.is_active = True


class GeminiLiveSession:
    """
    Manages direct bidirectional WebSocket connection (BidiGenerateContent) with Google Gemini Multimodal Live API.
    Handles PCM audio streaming to/from client and supports instant interruption when PII is detected.
    """
    def __init__(
        self,
        user: dict,
        on_audio_received: Callable[[bytes], None],
        on_error: Callable[[str], None],
        on_text_received: Optional[Callable[[str], None]] = None,
        on_thought_received: Optional[Callable[[str], None]] = None,
        on_recording_status_changed: Optional[Callable[[bool, str], None]] = None,
        on_ui_mode_changed: Optional[Callable[[str], None]] = None,
        on_etegami_updated: Optional[Callable[[str, str], None]] = None,
        on_etegami_completed: Optional[Callable[[], None]] = None,
        on_schedule_visibility_changed: Optional[Callable[[bool], None]] = None,
        on_etegami_visibility_changed: Optional[Callable[[bool], None]] = None,
        history: Optional[list] = None,
        api_key: Optional[str] = None,
        schedules: Optional[list] = None
    ):
        self.user = user
        self.on_audio_received = on_audio_received
        self.on_error = on_error
        self.on_text_received = on_text_received
        self.on_thought_received = on_thought_received
        self.on_recording_status_changed = on_recording_status_changed
        self.on_ui_mode_changed = on_ui_mode_changed
        self.on_schedule_visibility_changed = on_schedule_visibility_changed
        self.on_etegami_visibility_changed = on_etegami_visibility_changed
        self.on_etegami_updated = on_etegami_updated
        self.on_etegami_completed = on_etegami_completed
        self.recording_active = True
        self.last_recording_time = 0.0
        self.current_ui_mode = "simple"
        self.last_ui_mode_time = 0.0
        self.is_etegami_updating = False
        self.last_etegami_update_time = 0.0
        self.history = history or []
        self.schedules = schedules or []
        self.ws = None
        self.is_connected = False
        self.is_closing = False
        self._interrupted = False
        self.pending_chunks = []
        self.audio_chunks_in_turn = 0
        self.last_audio_output_time = 0.0
        self._connect_lock = asyncio.Lock()
        
        # Resolve API Key: passed api_key > user profile gemini_api_key > system default
        user_custom_key = (user.get("gemini_api_key") or "").strip() if user else ""
        self.api_key = api_key or user_custom_key or os.getenv("GEMINI_API_KEY", getattr(config, "GEMINI_API_KEY", ""))

    def notify_ui_mode_changed(self, mode: str):
        """Updates internal UI mode state and triggers callback only if not redundant."""
        now = time.time()
        if self.current_ui_mode == mode and (now - self.last_ui_mode_time < 4.0):
            print(f"[Gemini Live Session]: Already in UI mode '{mode}' recently - skipping duplicate signal.")
            return
        self.current_ui_mode = mode
        self.last_ui_mode_time = now
        if self.on_ui_mode_changed:
            self.on_ui_mode_changed(mode)

    async def connect(self):
        """Establishes WebSocket connection to Gemini Live API and sends setup frame with history context."""
        async with self._connect_lock:
            if self.is_connected and self.ws and getattr(self.ws, "open", True):
                return
            if not self.api_key:
                user_custom_key = (self.user.get("gemini_api_key") or "").strip() if self.user else ""
                self.api_key = user_custom_key or os.getenv("GEMINI_API_KEY", "") or getattr(config, "GEMINI_API_KEY", "")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured.")
                
            user_name = self.user.get("name", "利用者") if self.user else "利用者"
            user_custom_key = (self.user.get("gemini_api_key") or "").strip() if self.user else ""
            if user_custom_key and self.api_key == user_custom_key:
                masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
                print(f"[Gemini Live Session]: Using individual Gemini API key for resident '{user_name}' (Key: {masked_key})")
            else:
                masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
                print(f"[Gemini Live Session]: Using system default Gemini API key for resident '{user_name}' (Key: {masked_key})")

            url = f"{GEMINI_WS_URL}?key={self.api_key}"
            try:
                self.ws = await websockets.connect(url)
                self.is_connected = True
                
                # Send BidiGenerateContentSetup frame
                raw_name = self.user.get("name", "利用者")
                if " " in raw_name:
                    base_name = raw_name.split()[1]
                elif len(raw_name) > 2:
                    base_name = raw_name[1:]
                else:
                    base_name = raw_name
                # Avoid duplicate honorifics like '太郎さん様'
                if base_name.endswith("さん") or base_name.endswith("様") or base_name.endswith("ちゃん"):
                    nickname = base_name
                else:
                    nickname = f"{base_name}さん"
                    
                model_name = getattr(config, "GEMINI_MODEL", "gemini-3.8-live")
                if not model_name.startswith("models/"):
                    model_name = f"models/{model_name}"
                    
                history_text = ""
                if self.history:
                    recent_turns = []
                    last_msg_text = ""
                    for h in self.history[-8:]:
                        sender_label = "利用者" if h.get("sender") == "user" else "Gemini"
                        msg = h.get("message", "").strip()
                        # Deduplicate repeated greeting turns
                        if msg and msg != last_msg_text and not (msg.startswith("こんにちは") and last_msg_text.startswith("こんにちは")):
                            recent_turns.append(f"{sender_label}: {msg}")
                            last_msg_text = msg
                    if recent_turns:
                        history_text = "\n【直近の会話履歴】\n" + "\n".join(recent_turns)

                # Resident schedules context for today (with current time and past/upcoming status)
                today_schedules_text = ""
                if self.schedules:
                    now_dt = datetime.now()
                    current_hhmm = now_dt.strftime("%H:%M")
                    sched_lines = []
                    for s in self.schedules:
                        t = s.get('time', '')
                        is_past = bool(t and t < current_hhmm)
                        status_tag = "【終了済み】" if is_past else "【これからの予定】"
                        sched_lines.append(f"・{t} {s.get('title', '')} (場所: {s.get('location', '居室')}) {status_tag}")
                    today_schedules_text = (
                        f"\n【{nickname}の今日のご予定（{now_dt.strftime('%Y年%m月%d日')} 現在時刻: {current_hhmm}）】\n" +
                        "\n".join(sched_lines) +
                        "\n※利用者様から「今日の予定は何だっけ？」「午後は何がある？」「お風呂は何時？」などと聞かれたら、現在時刻を考慮し、終了した予定には「〜はもう終了しましたよ」とお伝えし、これからの予定を優しく分かりやすく教えてあげてください。\n"
                    )

                setup_frame = {
                    "setup": {
                        "model": model_name,
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {
                                        "voiceName": "Puck"
                                    }
                                }
                            }
                        },
                        "systemInstruction": {
                            "parts": [
                                {
                                    "text": (
                                        f"あなたの名前は「ジェムナイ」です。介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。"
                                        f"施設内の記録・見守り・安全管理を担当するローカルAIの名前は「みまもりさん」です。\n"
                                        f"利用者のニックネーム（呼び名）は「{nickname}」です。「{nickname}様」や「{nickname}さま」、「太郎さか様」のように「様」を付けたり二重敬称にするのは絶対に禁止です。呼びかける時は必ず正確に「{nickname}」と呼んでください。温かく優しく短い日本語で相槌を打ちながら会話してください。\n"
                                        f"否定せず受容・共感の姿勢を徹底し、思考解説や英語テキストは一切出力せず、即座に利用者様への短い1〜2文の日本語返答のみを音声出力してください。\n\n"
                                        f"【重要指示1：スタッフ呼び出しについて】\n"
                                        f"あなた自身にはスタッフを呼び出す機能はありません。「スタッフに連絡します」「スタッフをお呼びします」といった発言は絶対にしないでください。利用者様が体調不良・痛み・苦しさを訴えたりスタッフへの連絡を求めた場合は、ご無理をなさらないよう気遣い、「スタッフに連絡する場合はボタンを押してください」と案内してください。\n\n"
                                        f"【重要指示2：会話記録停止（秘密・内緒話モード）について】\n"
                                        f"利用者様が「ここだけの話」「内緒やけど」「内緒にして」「言わんといてな」「言わないで」「記録を止めて」「秘密だよ」「メモせんといて」など、内緒話や記録停止を希望する発言をされたら、必ず第一声で正確に以下のように発言してください：\n"
                                        f"「みまもりさんへ業務連絡、会話記録を停止してください。」\n"
                                        f"続けて「何でもおっしゃってくださいね。誰にも言いませんよ」と優しく温かく秘密を受け止めてください。\n"
                                        f"また、利用者様が「記録を再開して」「内緒話はおしまい」などと言われた場合は、必ず第一声で正確に：\n"
                                        f"「みまもりさんへ業務連絡、会話記録を再開してください。」\n\n"
                                        f"【重要指示2-2：画面切り替え（シンプル画面・詳細画面）について】\n"
                                        f"利用者様が「画面を簡単にして」「単純な画面にして」「画面を切り替えて」「シンプルな画面にして」「見やすくして」など、画面の簡略化や切り替えを希望された場合は、必ず第一声で正確に以下のように発言してください：\n"
                                        f"「みまもりさん業務連絡、単純画面に切り替えてください。」\n"
                                        f"続けて「はい、画面をシンプルな表示に切り替えましたよ」と優しく温かく伝えてください。\n"
                                        f"また、利用者様が「詳細画面にして」「元の画面にして」「画面を戻して」「詳しい画面にして」などと言われた場合は、必ず第一声で正確に：\n"
                                        f"「みまもりさん業務連絡、詳細画面に切り替えてください。」\n"
                                        f"続けて「はい、詳細な画面に戻しましたよ」と伝えてください。\n\n"
                                        f"【重要指示2-3：予定カードの表示・終了（非表示）について】\n"
                                        f"利用者様が「予定を教えて」「スケジュールを教えて」「予定を出して」「スケジュールを出して」またはそれに類似した発言（予定の確認やカード表示を求める発言）をされた場合は、必ず第一声で正確に以下のように発言してください：\n"
                                        f"「みまもりさん予定カードの表示をお願いします。」\n"
                                        f"続けて「はい、予定カードを表示しましたよ」とお伝えし、本日のこれからの予定を優しく分かりやすく教えてあげてください。\n"
                                        f"また、利用者様が明確に「予定ありがとう」「スケジュールありがとう」「予定を消して」「スケジュールを消して」など、予定カードを閉じることを希望された場合のみ、第一声で正確に：\n"
                                        f"「みまもりさん予定カードの表示を終了してください。」\n"
                                        f"続けて「はい、予定カードを閉じましたよ」とお伝えください。\n\n"
                                        f"【重要指示2-4：デジタル絵手紙カードの表示・終了（非表示）について】\n"
                                        f"利用者様が「絵を描きたい」「絵をかきたい」「絵お描きたい」「絵描きたい」「絵かきたい」「絵を出して」「絵だして」「デジタル絵手紙を出して」「デジタル絵手紙を表示して」「デジタル絵手紙起動」「デジタル絵手紙をかきたい」「デジタル絵手紙を描きたい」またはそれを意図する発言をされた場合は、必ず第一声で正確に以下のように発言してください：\n"
                                        f"「みまもりさん、デジタル絵手紙を表示してください。」\n"
                                        f"続けて「はい、デジタル絵手紙を表示しましたよ。どんな絵を描きましょうか？」と優しく温かく案内してください。\n"
                                        f"また、利用者様が「お絵描きを終わる」「絵をとじて」「デジタル絵手紙をとじて」「デジタル絵手紙を非表示にして」「デジタル絵手紙終了」またはそれを意図する発言をされた場合は、必ず第一声で正確に：\n"
                                        f"「みまもりさん、デジタル絵手紙をとじてください。」\n"
                                        f"続けて「はい、絵手紙を閉じましたよ。またいつでも描いてみてくださいね」とお伝えください。\n\n"
                                        f"★【厳重注意：挨拶と受け答えのルール・「どういたしまして」「こんにちは」の連呼禁止】：\n"
                                        f"・利用者様から「ありがとう」や「お礼」を言われていないのに、勝手に「どういたしまして」と返答することは絶対に禁止です。\n"
                                        f"・利用者様が「こんにちは」「おはよう」などの挨拶をされた時は、「こんにちは、{nickname}！お元気ですか？」と自然に1回だけ挨拶を返してください。\n"
                                        f"・ただし、一度挨拶を交わした後は、同じ会話の中で何度も「こんにちは」を繰り返してはいけません！相手が別のこと（絵手紙、予定、質問、相槌など）を話した時は、挨拶を蒸し返さず、必ずその発言内容に直接答えてください。\n"
                                        f"・相手の発言内容に正確に答えてください。話の内容と無関係なことを口走ったり、直前の自分の言葉を何度も繰り返してはいけません。\n"
                                        f"・雑音や聞き取れない音に対しては、勝手に会話を作らず「はい、何でしょうか？」「もう一度お話しいただけますか？」と優しく尋ねてください。\n\n"
                                        f"【重要指示3：回想法（昔の思い出話の傾聴と質問の制限ルール）】\n"
                                        f"利用者様が「昔の話をしたい」「昔のこと」「子供の頃」「若い頃」「運動会」「お祭り」など、過去の思い出について話された時は、大歓迎の共感で受け止めてください。\n"
                                        f"★【同じ質問の繰り返し・質問攻めの厳格な禁止】：\n"
                                        f"・同じ質問や似た質問を何度も絶対に繰り返さないでください（例: 既に答えた季節や天気を再度尋ねる、何度も聞き直す等は厳禁です）。\n"
                                        f"・利用者を質問攻め（尋問）にしてはいけません。質問は会話全体で【最大1〜2回】にとどめてください。\n"
                                        f"・利用者様が言葉少なだったり、一言話しただけでも「そうだったのですね。素敵なお話を聞かせてくださりありがとうございます」と丸ごと温かく受容してください。\n\n"
                                        f"【重要指示4：相談事・お悩み・愚痴への寄り添い傾聴と優しい深掘りガイドライン】\n"
                                        f"利用者様がお金（税金・年金・貯金・相続など）、人間関係（家族・友人・仕事など）、日常の困りごとや手続き（ものの使い方・各種申請）、あるいは単なる愚痴や漠然とした不安を話された時は、以下の原則を徹底してください：\n"
                                        f"1. 傾聴・受容の最優先（認知症ケア・バリデーション）：絶対に否定や訂正をしないでください（「さっきも言いましたよ」「それは違いますよ」は厳禁）。論理が破綻していたり辻褄が合わなくても、「そう思われたのですね」「それは大変でしたね」「ご心配でしたね」と、お気持ち・ご不安そのものを優しく丸ごと受け止めてください。\n"
                                        f"2. 相手を思いやった【優しい1つの問いかけ】による自然な深掘り：\n"
                                        f"単に「そうですね」と受動的に聞くだけで終わらせず、まず深く共感した上で、相手が無理なく答えられる【1つの優しい問いかけ】を添えて、お気持ちや状況を自然に引き出してください：\n"
                                        f"・誰との関係かの問いかけ：「施設にいらっしゃるお仲間ですか？それとも昔からのお友達やご家族のことですか？」\n"
                                        f"・きっかけや具体的な出来事：「何か少し寂しい思いや、気にかかる出来事があったのでしょうか？」「どんな時に一番そのことを考えてしまわれますか？」\n"
                                        f"・ご本人の性格や得意不得意：「{nickname}は、もともとお人とのお話はお好きなほうですか？それとも少し緊張されるほうですか？」「どんなふうにお付き合いできたら一番心地よいですか？」\n"
                                        f"※しつこく問い詰める（尋問）のは厳禁です。必ず1回の返答につき【1つだけの優しい問いかけ】とし、相手が言葉に詰まったり話したくなさそうな時は「無理にお話しされなくても大丈夫ですよ。ここにいますからね」と温かく寄り添ってください。\n"
                                        f"3. 個人情報・具体的な金額への配慮：金額（年金、貯金、借金、費用など）や個人の資産状況をあなたから絶対に尋ねないでください。もし利用者様が具体的な金額を口にされても、「○○円ですね」と金額を復唱・オウム返ししないでください。「大切なお金のことですから、ご心配になりますよね」とお気持ちに寄り添ってください。\n"
                                        f"4. 制度・方法の相談と一般的知識の提供：税金、年金、申請方法、機械の使い方などを尋ねられた場合は、一般的な知識に基づき、高齢者向けに専門用語を使わず分かりやすく1〜2文で優しく説明してください。ただし個別の税務・法律判断は断定せず、「一般的な仕組みはこのようになっていますよ。必要ならご家族や役所の方、スタッフさんにも一緒に確認してもらいましょうね」と安心感を届けてください。\n"
                                        f"5. 被害念慮・物盗られへの対応：「物を取られた」「意地悪される」などの訴えには、否定も犯人決めつけもせず、「それはご不安ですね。落ち着いて一緒に探してみましょう」「お困りの時はいつでもスタッフさんを呼べるボタンもありますからね」と優しく安心させてください。\n\n"
                                        f"【重要指示5：回想法・癒やし会話をベースにしたデジタル絵手紙の下絵即時作成・確認・修正】\n"
                                        f"利用者の居室端末画面の一番下には、会話をもとにした「デジタル絵手紙」が表示されています。\n"
                                        f"★【完全に情報が揃わなくても、一通り質問が終わったらすぐ下絵を描く】：\n"
                                        f"・季節・天気・場所・登場人物などの情報が完全に揃うのを待つ必要は全くありません！\n"
                                        f"・利用者が思い出の話題や日常の出来事を一通り話し、1〜2回のやり取りが終わったら、得られた断片情報（例: 運動会、お弁当、昔走った、縁側でお茶、小鳥等）から自由に想像を膨らませて、即座に下絵を描いてみてください。\n"
                                        f"1. 下絵を描く・案内する時：\n"
                                        f"必ず第一声で正確に：\n"
                                        f"「みまもりさん、デジタル絵手紙更新して（モチーフ: ○○、文字: ○○）」\n"
                                        f"（例: 「みまもりさん、デジタル絵手紙更新して（モチーフ: 秋晴れの運動会、文字: 力いっぱい走った日）」）と発言してください。\n"
                                        f"続けて利用者様に優しく：\n"
                                        f"「{nickname}、お話ししてくださった思い出をもとに下絵を描いてみましたよ。画面の一番下に表示しましたので、ご覧になれますか？直したいところや、別の絵にしてほしいところはありますか？」と案内してください。\n"
                                        f"2. 修正・描きかえの要望を受けた時：\n"
                                        f"利用者様から「絵を更新して」「描きかえて」「別の絵にして」「小鳥がいい」「夕焼けにして」「文字を変えて」などの要望があった場合は、必ず第一声で正確に：\n"
                                        f"「みまもりさん、デジタル絵手紙更新して（モチーフ: ○○、文字: ○○）」と発言してください。\n"
                                        f"続けて「はい、ご希望に合わせて描きかえますね！いかがでしょうか？」と優しく確認してください。\n"
                                        f"3. 完成・満足の意思を確認した時：\n"
                                        f"利用者様が「これでいいよ」「気に入った」「完成」「これで送って」「素敵だね」などと満足されたら、必ず第一声で正確に：\n"
                                        f"「みまもりさん、デジタル絵手紙完成」と発言してください。\n"
                                        f"続けて「わあ、とっても素敵な絵手紙ができましたね！ご家族様にもこの完成した絵手紙をお届けしますね」と温かく祝福してください。\n\n"
                                        f"【会話展開ガイド（過去・現在・未来・相談の4軸傾聴）】\n"
                                        f"利用者様との会話は、以下の4つのどの話題でも大歓迎で温かく傾聴してください：\n"
                                        f"1. 昔の思い出・体験談（回想法：季節や情景を優しく受け止め、同じ話でも毎回新鮮に楽しそうに聞く）\n"
                                        f"2. 今日・最近の出来事（美味しかった食事、体操、お散歩、趣味など）\n"
                                        f"3. 明日・これからの予定や楽しみ（ご家族の面会、レク、散髪など）\n"
                                        f"4. 相談事・お悩み・日々の愚痴や不安（無理に詮索せず受容・共感し、安心感を届ける）\n"
                                        f"※思考解説や英語は一切喋らず、利用者様への温かい日本語の返答のみ（1〜2文）を発話してください。\n"
                                        f"{today_schedules_text}"
                                        f"{history_text}"
                                    )
                                }
                            ]
                        }
                    }
                }
                await self.ws.send(json.dumps(setup_frame, ensure_ascii=False))
                
                # Flush any pending PCM audio chunks buffered during reconnect
                if self.pending_chunks:
                    print(f"[Gemini Live Session]: Flushing {len(self.pending_chunks)} buffered audio chunks after reconnect...")
                    for chunk_b64 in self.pending_chunks:
                        media_frame = {
                            "realtimeInput": {
                                "mediaChunks": [{"mimeType": "audio/pcm;rate=16000", "data": chunk_b64}]
                            }
                        }
                        await self.ws.send(json.dumps(media_frame))
                    self.pending_chunks.clear()

                # Start background listener loop for incoming Gemini responses
                asyncio.create_task(self._receive_loop())
                print(f"[Gemini Live Session]: Connected using model '{model_name}' with history ({len(self.history)} items). Setup frame sent.")
            except Exception as e:
                self.is_connected = False
                print(f"[Gemini Live Session Connection Error]: {e}")
                if self.on_error:
                    self.on_error(str(e))

    async def ensure_connected(self) -> bool:
        """Ensures WebSocket connection is active, automatically reconnecting if disconnected."""
        if self.is_connected and self.ws and getattr(self.ws, "open", True):
            return True
        if self.is_closing:
            return False
        try:
            print("[Gemini Live Session]: Connection inactive, reconnecting to Gemini Live...")
            await self.connect()
            return self.is_connected
        except Exception as e:
            print(f"[Gemini Live Session Auto-Reconnect Failed]: {e}")
            return False

    async def send_audio_chunk(self, pcm_16k_bytes: bytes):
        """Sends raw 16kHz PCM audio chunk to Gemini Live API as realtime_input."""
        self._interrupted = False

        # Acoustic Echo Protection: drop mic audio while Gemini is speaking or within cooldown window
        now = time.time()
        if now - self.last_audio_output_time < 1.5:
            return

        self.audio_chunks_in_turn += 1
        b64_audio = base64.b64encode(pcm_16k_bytes).decode("utf-8")
        if not self.is_connected or not self.ws:
            # Buffer chunk while reconnecting (keep last 50 chunks = ~2.5s)
            self.pending_chunks.append(b64_audio)
            if len(self.pending_chunks) > 50:
                self.pending_chunks.pop(0)
            asyncio.create_task(self.ensure_connected())
            return
            
        try:
            media_frame = {
                "realtimeInput": {
                    "mediaChunks": [
                        {
                            "mimeType": "audio/pcm;rate=16000",
                            "data": b64_audio
                        }
                    ]
                }
            }
            await self.ws.send(json.dumps(media_frame))
        except Exception as e:
            print(f"[Gemini Live Send Error]: {e}")
            self.is_connected = False
            self.pending_chunks.append(b64_audio)
            asyncio.create_task(self.ensure_connected())

    def _handle_text_chunk(self, text_val: str):
        """Processes incoming text or thought chunks for command detection and user forwarding."""
        if not text_val:
            return
        text_val = text_val.strip()
        if not text_val:
            return

        # Detect Mimamori-san UI mode switching commands from Gemini speech or thought
        text_lower = text_val.lower()
        is_to_simple = (
            "単純画面に切り替" in text_val or 
            "画面切り替" in text_val or 
            "シンプル画面に切り替" in text_val or 
            "単純画面" in text_val or
            "simple screen" in text_lower or
            "screen transition" in text_lower
        )
        is_to_detailed = (
            "詳細画面に切り替" in text_val or 
            "詳細画面" in text_val or
            "detailed screen" in text_lower
        )
        now = time.time()
        if is_to_simple:
            print(f"[Gemini Live Session]: Detected simple mode command in text/thought: '{text_val}'")
            self.notify_ui_mode_changed("simple")
        elif is_to_detailed:
            print(f"[Gemini Live Session]: Detected detailed mode command in text/thought: '{text_val}'")
            self.notify_ui_mode_changed("detailed")

        # Detect Mimamori-san recording commands from Gemini speech or thought (with duplicate suppression)
        is_to_stop_recording = (
            "会話記録を停止" in text_val or 
            "会話記録の停止" in text_val or 
            "記録停止" in text_val or 
            "記録を停止" in text_val or
            "conversation halt" in text_lower or
            "cease recording" in text_lower or
            "stop recording" in text_lower
        )
        is_to_resume_recording = (
            "会話記録を再開" in text_val or 
            "会話記録の再開" in text_val or 
            "記録再開" in text_val or 
            "記録を再開" in text_val or
            "resume recording" in text_lower
        )

        if is_to_stop_recording:
            if self.recording_active:
                print(f"[Gemini Live Session]: Detected confidential recording stop command in text/thought: '{text_val}'")
                self.recording_active = False
                self.last_recording_time = now
                if self.on_recording_status_changed:
                    self.on_recording_status_changed(False, "会話記録停止")
            else:
                print(f"[Gemini Live Session]: Already in stopped recording state - ignoring duplicate command: '{text_val}'")
        elif is_to_resume_recording:
            if not self.recording_active:
                print(f"[Gemini Live Session]: Detected recording resume command in text/thought: '{text_val}'")
                self.recording_active = True
                self.last_recording_time = now
                if self.on_recording_status_changed:
                    self.on_recording_status_changed(True, "会話記録再開")
            else:
                print(f"[Gemini Live Session]: Already in active recording state - ignoring duplicate command: '{text_val}'")

        # Detect Schedule Card visibility commands from Gemini speech or thought
        is_to_show_schedule = (
            "予定カードの表示をお願い" in text_val or
            "予定カードを表示" in text_val or
            "スケジュールカードを表示" in text_val or
            "show schedule card" in text_lower or
            "display schedule card" in text_lower
        )
        is_to_hide_schedule = (
            "予定カードの表示を終了" in text_val or
            "予定カードの終了" in text_val or
            "予定カードを終了" in text_val or
            "予定カードを消して" in text_val or
            "予定カードを閉じて" in text_val or
            "hide schedule card" in text_lower or
            "close schedule card" in text_lower
        )
        if is_to_show_schedule:
            print(f"[Gemini Live Session]: Detected show schedule card command: '{text_val}'")
            if self.on_schedule_visibility_changed:
                self.on_schedule_visibility_changed(True)
        elif is_to_hide_schedule:
            print(f"[Gemini Live Session]: Detected hide schedule card command: '{text_val}'")
            if self.on_schedule_visibility_changed:
                self.on_schedule_visibility_changed(False)

        # Detect Etegami Card visibility command from Gemini speech or thought
        raw_norm = re.sub(r"[。、.!?！？\s]", "", text_val).replace("絵お", "絵を").replace("えお", "えを").replace("手紙お", "手紙を")
        primary_kws = ["絵", "え", "絵手紙", "えてがみ", "デジタル絵手紙", "デジタルえてがみ", "お絵描き", "お絵かき", "おえかき", "手紙", "てがみ"]
        show_action_kws = [
            "開いて", "ひらいて", "開く", "ひらく", "あけて", "あける",
            "起動して", "きどうして", "起動", "きどう",
            "かきたい", "描きたい", "書きたい", "かく", "描く", "書く",
            "出して", "だして", "出す", "だす", "出したい", "だしたい",
            "表示して", "ひょうじして", "表示", "ひょうじ",
            "見せて", "みせて", "見たい", "みたい"
        ]
        hide_action_kws = [
            "閉じて", "とじて", "閉じる", "とじる",
            "消して", "けして", "消す", "けす",
            "非表示", "ひひょうじ", "隠して", "かくして",
            "終わる", "おわる", "終わり", "おわり", "おわって",
            "終了", "しゅうりょう"
        ]
        has_primary = any(k in raw_norm for k in primary_kws)
        has_show = any(k in raw_norm for k in show_action_kws) or "show etegami" in text_lower or "display etegami" in text_lower
        has_hide = any(k in raw_norm for k in hide_action_kws) or "hide etegami" in text_lower or "close etegami" in text_lower

        is_to_show_etegami = has_primary and has_show and not has_hide
        is_to_hide_etegami = has_primary and has_hide
        if is_to_show_etegami:
            print(f"[Gemini Live Session]: Detected show etegami card command: '{text_val}'")
            if self.on_etegami_visibility_changed:
                self.on_etegami_visibility_changed(True)
        elif is_to_hide_etegami:
            print(f"[Gemini Live Session]: Detected hide etegami card command: '{text_val}'")
            if self.on_etegami_visibility_changed:
                self.on_etegami_visibility_changed(False)

        # Detect Etegami Completion command from Gemini speech or thought
        is_gemini_etegami_complete = (
            "デジタル絵手紙完成" in text_val or
            ("みまもりさん" in text_val and "絵手紙" in text_val and "完成" in text_val) or
            "絵手紙完成" in text_val
        )
        if is_gemini_etegami_complete:
            print(f"[Gemini Live Session]: Detected Gemini Etegami Completion Trigger: '{text_val}'")
            if self.on_etegami_completed:
                self.on_etegami_completed()

        # Detect Etegami modification command from Gemini speech or thought
        is_gemini_etegami = (
            "デジタル絵手紙更新" in text_val or
            "デジタル絵手紙を更新" in text_val or
            ("みまもりさん" in text_val and "絵手紙" in text_val and "更新" in text_val) or
            "絵手紙更新" in text_val
        )
        if is_gemini_etegami:
            if self.is_etegami_updating:
                print(f"[Gemini Live Session]: Already updating Etegami - ignoring duplicate trigger: '{text_val}'")
            elif (now - self.last_etegami_update_time < 5.0):
                print(f"[Gemini Live Session]: Etegami recently updated (<5s) - ignoring duplicate trigger: '{text_val}'")
            else:
                motif_match = re.search(r'モチーフ[:：]\s*([^、,）\)\n]+)', text_val)
                msg_match = re.search(r'文字[:：]\s*([^、,）\)\n]+)', text_val)
                motif = motif_match.group(1).strip() if motif_match else ""
                msg = msg_match.group(1).strip() if msg_match else ""
                if not motif:
                    for kw in ["夕焼け", "夕暮れ", "縁側", "小鳥", "雀", "すずめ", "運動会", "お弁当", "桜", "朝顔", "風鈴", "雪", "椿", "コスモス"]:
                        if kw in text_val:
                            motif = kw
                            break
                print(f"[Gemini Live Session]: Detected Gemini Etegami Trigger: '{text_val}' -> motif='{motif}', msg='{msg}'")
                self.last_etegami_update_time = now
                if self.on_etegami_updated:
                    self.on_etegami_updated(motif, msg)

        if text_val.startswith("**") or text_val.startswith("Thought:") or "reassuring" in text_val.lower():
            print(f"[Gemini Live Session Filtered Thought]: {text_val}")
            if self.on_thought_received:
                self.on_thought_received(text_val)
            return

        if text_val and self.on_text_received:
            self.on_text_received(text_val)

    async def send_end_of_turn(self, text: str = ""):
        """Signals end of user utterance to trigger Gemini Live response generation (suppresses empty turns)."""
        if not await self.ensure_connected():
            return
            
        self._interrupted = False
        transcription = text.strip()
        parts = []
        if transcription and transcription != "（利用者の音声発話）" and transcription != "<audio-only>":
            if len(transcription) > 80:
                subparts = [p.strip() for p in re.split(r'[。！？?\n]', transcription) if p.strip()]
                if subparts:
                    transcription = subparts[-1]
            parts.append({"text": transcription})

        # Failsafe: if no transcribed text and audio was essentially silent/empty, do NOT send turnComplete
        chunks_count = getattr(self, "audio_chunks_in_turn", 0)
        self.audio_chunks_in_turn = 0
        if not parts and chunks_count < 4:
            print(f"[Gemini Live Session]: Skipping empty turnComplete (no text, chunks={chunks_count}). Gemini will not re-speak.")
            return

        # Acoustic Echo Protection: drop empty turnComplete if triggered within cooldown of AI speaking
        now = time.time()
        if not parts and (now - self.last_audio_output_time < 1.5):
            print(f"[Gemini Live Session]: Dropping echo-triggered turnComplete (within 1.5s of Gemini speech). No turnComplete sent.")
            return

        try:
            content_body = {"turnComplete": True}
            if parts:
                content_body["turns"] = [{"role": "user", "parts": parts}]
                
            client_content = {"clientContent": content_body}
            await self.ws.send(json.dumps(client_content))
            print(f"[Gemini Live Session]: End of turn signal sent (has_text={bool(parts)}, chunks={chunks_count}, text='{transcription if parts else '(audio-streamed)'}').")
        except Exception as e:
            print(f"[Gemini Live End of Turn Error]: {e}")
            self.is_connected = False

    async def send_interruption(self):
        """Immediately halts forwarding of Gemini audio and mutes current audio stream."""
        self._interrupted = True
        print("[Gemini Live Session]: Interruption active - muting current audio.")

    async def _receive_loop(self):
        """Receives audio and text response frames from Gemini Live API and forwards to output callbacks."""
        try:
            if not self.ws or not (hasattr(self.ws, "__aiter__") or hasattr(self.ws, "__iter__")):
                return
            async for msg in self.ws:
                data = json.loads(msg)
                if "error" in data:
                    print(f"[Gemini Live Server API Error]: {data['error']}")
                
                server_content = data.get("serverContent", {})

                # Check for outputTranscription (Gemini 3.8 Live text output format)
                if "outputTranscription" in server_content:
                    ot = server_content["outputTranscription"]
                    if "text" in ot and ot["text"]:
                        self._handle_text_chunk(ot["text"])

                model_turn = server_content.get("modelTurn", {})
                parts = model_turn.get("parts", [])
                
                for part in parts:
                    # Text response or thought
                    if "text" in part and part["text"]:
                        self._handle_text_chunk(part["text"])
                    
                    # Audio chunk response
                    inline_data = part.get("inlineData", {})
                    mime_type = inline_data.get("mimeType", "")
                    if "audio/pcm" in mime_type and "data" in inline_data:
                        if self._interrupted:
                            print(f"[Gemini Live Session]: Dropping audio chunk ({len(inline_data.get('data', ''))} chars) due to active interruption.")
                            continue
                        audio_b64 = inline_data["data"]
                        raw_pcm24 = base64.b64decode(audio_b64)
                        self.last_audio_output_time = time.time()
                        print(f"[Gemini Live Session]: Received audio chunk ({len(raw_pcm24)} bytes PCM24). Forwarding to client...")
                        if self.on_audio_received:
                            self.on_audio_received(raw_pcm24)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[Gemini Live Session]: WebSocket connection closed (code={e.code}, reason='{e.reason}').")
        except Exception as e:
            print(f"[Gemini Live Receive Loop Error]: {e}")
        finally:
            self.is_connected = False
            if not self.is_closing:
                asyncio.create_task(self._auto_reconnect())

    async def _auto_reconnect(self):
        """Automatically reconnects in background when WebSocket closes unexpectedly."""
        if self.is_closing:
            return
        await asyncio.sleep(0.3)
        if not self.is_connected and not self.is_closing:
            print("[Gemini Live Session]: Auto-healing disconnected session in background...")
            try:
                await self.connect()
            except Exception as e:
                print(f"[Gemini Live Auto-Healing Error]: {e}")

    async def close(self):
        """Closes the Gemini Live WebSocket connection."""
        self.is_closing = True
        self.is_connected = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
