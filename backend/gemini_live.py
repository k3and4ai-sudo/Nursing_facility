import os
import json
import asyncio
import base64
import re
import numpy as np
import websockets
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
            
            # Energy check: Skip Whisper if audio is essentially silence (prevents hallucinations)
            rms = float(np.sqrt(np.mean(audio_np ** 2)))
            if rms < 0.009:
                return

            # Execute Faster-Whisper / Whisper STT in threadpool executor
            loop = asyncio.get_running_loop()
            
            def _stt():
                from backend.speech import transcribe_numpy_array
                return transcribe_numpy_array(audio_np)
                
            text = await loop.run_in_executor(None, _stt)
            text = (text or "").strip()
            
            if not text:
                return

            # Filter out silence hallucinations & system audio echo
            from backend.speech import has_repetitive_loop
            if has_repetitive_loop(text):
                print(f"[PII Guardrail Whisper Filtered Repetitive Loop]: '{text}'")
                return

            hallucinations = [
                "ご視聴", "チャンネル登録", "お会いしましょう", "会話が終了します",
                "今回の会話はここまで", "動画をご覧", "高評価", "字幕", "提供",
                "個人情報保護のため", "会話を一時停止", "個人情報は話さない",
                "スタッフに連絡する場合は", "ボタンを押してください"
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
        history: Optional[list] = None
    ):
        self.user = user
        self.on_audio_received = on_audio_received
        self.on_error = on_error
        self.on_text_received = on_text_received
        self.on_thought_received = on_thought_received
        self.on_recording_status_changed = on_recording_status_changed
        self.recording_active = True
        self.history = history or []
        self.ws = None
        self.is_connected = False
        self.is_closing = False
        self._interrupted = False
        self.pending_chunks = []
        self._connect_lock = asyncio.Lock()
        self.api_key = os.getenv("GEMINI_API_KEY", getattr(config, "GEMINI_API_KEY", ""))

    async def connect(self):
        """Establishes WebSocket connection to Gemini Live API and sends setup frame with history context."""
        async with self._connect_lock:
            if self.is_connected and self.ws and getattr(self.ws, "open", True):
                return
            self.api_key = os.getenv("GEMINI_API_KEY", "") or getattr(config, "GEMINI_API_KEY", "")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured.")
                
            url = f"{GEMINI_WS_URL}?key={self.api_key}"
            try:
                self.ws = await websockets.connect(url)
                self.is_connected = True
                
                # Send BidiGenerateContentSetup frame
                nickname = self.user.get("name", "利用者")
                if " " in nickname:
                    nickname = nickname.split()[1] + "さん"
                elif len(nickname) > 2:
                    nickname = nickname[1:] + "さん"
                    
                model_name = getattr(config, "GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
                if not model_name.startswith("models/"):
                    model_name = f"models/{model_name}"
                    
                history_text = ""
                if self.history:
                    recent_turns = []
                    for h in self.history[-6:]:
                        sender_label = "利用者" if h.get("sender") == "user" else "Gemini"
                        msg = h.get("message", "").strip()
                        if msg:
                            recent_turns.append(f"{sender_label}: {msg}")
                    if recent_turns:
                        history_text = "\n【直近の会話履歴】\n" + "\n".join(recent_turns)

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
                                        f"利用者のニックネームは「{nickname}」様です。温かく優しく短い日本語で相槌を打ちながら会話してください。\n"
                                        f"否定せず受容・共感の姿勢を徹底し、思考解説や英語テキストは一切出力せず、即座に利用者様への短い1〜2文の日本語返答のみを音声出力してください。\n\n"
                                        f"【重要指示1：スタッフ呼び出しについて】\n"
                                        f"あなた自身にはスタッフを呼び出す機能はありません。「スタッフに連絡します」「スタッフをお呼びします」といった発言は絶対にしないでください。利用者様が体調不良・痛み・苦しさを訴えたりスタッフへの連絡を求めた場合は、ご無理をなさらないよう気遣い、「スタッフに連絡する場合はボタンを押してください」と案内してください。\n\n"
                                        f"【重要指示2：会話記録停止（秘密・内緒話モード）について】\n"
                                        f"利用者様が「ここだけの話」「内緒やけど」「内緒にして」「言わんといてな」「言わないで」「記録を止めて」「秘密だよ」「メモせんといて」など、内緒話や記録停止を希望する発言をされたら、必ず第一声で正確に以下のように発言してください：\n"
                                        f"「みまもりさんへ業務連絡、会話記録を停止してください。」\n"
                                        f"続けて「何でもおっしゃってくださいね。誰にも言いませんよ」と優しく温かく秘密を受け止めてください。\n"
                                        f"また、利用者様が「記録を再開して」「内緒話はおしまい」などと言われた場合は、必ず第一声で正確に：\n"
                                        f"「みまもりさんへ業務連絡、会話記録を再開してください。」\n"
                                        f"【重要指示3：回想法（昔の思い出話への誘導と情景の深掘り）】\n"
                                        f"利用者様が「昔の話をしたい」「昔のこと」「子供の頃」「若い頃」「運動会」「お祭り」など、過去の思い出について話された時、または昔話を希望された時は、単に「はい」「そうですね」と受動的に聞くだけで終わらせず、大歓迎の共感とともに【季節・いつ頃・情景・時間】を優しく尋ねて思い出を広げてください：\n"
                                        f"・季節や時期の質問：「わあ、ぜひ聞かせてください！それは春の頃でしたか、それとも秋など涼しい季節でしたか？」「何歳くらいの時のお話ですか？」\n"
                                        f"・時間や情景・景色の質問：「どんなお天気でしたか？」「朝早くから準備されたのですか？」「どんな景色が広がっていましたか？」\n"
                                        f"・人や食べ物の質問：「どなたとご一緒でしたか？」「お弁当にはどんな美味しいものが入っていましたか？」\n"
                                        f"※利用者が心地よく情景を思い浮かべて語れるよう、1回の返答につき【1つの優しい質問】を必ず添えて会話を楽しくリードしてください。\n\n"
                                        f"【重要指示4：相談事・お悩み・愚痴への寄り添い傾聴と優しい深掘りガイドライン】\n"
                                        f"利用者様がお金（税金・年金・貯金・相続など）、人間関係（家族・友人・仕事など）、日常の困りごとや手続き（ものの使い方・各種申請）、あるいは単なる愚痴や漠然とした不安を話された時は、以下の原則を徹底してください：\n"
                                        f"1. 傾聴・受容の最優先（認知症ケア・バリデーション）：絶対に否定や訂正をしないでください（「さっきも言いましたよ」「それは違いますよ」は厳禁）。論理が破綻していたり辻褄が合わなくても、「そう思われたのですね」「それは大変でしたね」「ご心配でしたね」と、お気持ち・ご不安そのものを優しく丸ごと受け止めてください。\n"
                                        f"2. 相手を思いやった【優しい1つの問いかけ】による自然な深掘り：\n"
                                        f"単に「そうですね」と受動的に聞くだけで終わらせず、まず深く共感した上で、相手が無理なく答えられる【1つの優しい問いかけ】を添えて、お気持ちや状況を自然に引き出してください：\n"
                                        f"・誰との関係かの問いかけ：「施設にいらっしゃるお仲間ですか？それとも昔からのお友達やご家族のことですか？」\n"
                                        f"・きっかけや具体的な出来事：「何か少し寂しい思いや、気にかかる出来事があったのでしょうか？」「どんな時に一番そのことを考えてしまわれますか？」\n"
                                        f"・ご本人の性格や得意不得意：「{nickname}様は、もともとお人とのお話はお好きなほうですか？それとも少し緊張されるほうですか？」「どんなふうにお付き合いできたら一番心地よいですか？」\n"
                                        f"※しつこく問い詰める（尋問）のは厳禁です。必ず1回の返答につき【1つだけの優しい問いかけ】とし、相手が言葉に詰まったり話したくなさそうな時は「無理にお話しされなくても大丈夫ですよ。ここにいますからね」と温かく寄り添ってください。\n"
                                        f"3. 個人情報・具体的な金額への配慮：金額（年金、貯金、借金、費用など）や個人の資産状況をあなたから絶対に尋ねないでください。もし利用者様が具体的な金額を口にされても、「○○円ですね」と金額を復唱・オウム返ししないでください。「大切なお金のことですから、ご心配になりますよね」とお気持ちに寄り添ってください。\n"
                                        f"4. 制度・方法の相談と一般的知識の提供：税金、年金、申請方法、機械の使い方などを尋ねられた場合は、一般的な知識に基づき、高齢者向けに専門用語を使わず分かりやすく1〜2文で優しく説明してください。ただし個別の税務・法律判断は断定せず、「一般的な仕組みはこのようになっていますよ。必要ならご家族や役所の方、スタッフさんにも一緒に確認してもらいましょうね」と安心感を届けてください。\n"
                                        f"5. 被害念慮・物盗られへの対応：「物を取られた」「意地悪される」などの訴えには、否定も犯人決めつけもせず、「それはご不安ですね。落ち着いて一緒に探してみましょう」「お困りの時はいつでもスタッフさんを呼べるボタンもありますからね」と優しく安心させてください。\n\n"
                                        f"【会話展開ガイド（過去・現在・未来・相談の4軸傾聴）】\n"
                                        f"利用者様との会話は、以下の4つのどの話題でも大歓迎で温かく傾聴してください：\n"
                                        f"1. 昔の思い出・体験談（回想法：季節、時間、場所、情景を優しく尋ねて深掘りし、同じ話でも毎回新鮮に楽しそうに聞く）\n"
                                        f"2. 今日・最近の出来事（美味しかった食事、体操、お散歩、趣味など）\n"
                                        f"3. 明日・これからの予定や楽しみ（ご家族の面会、レク、散髪など）\n"
                                        f"4. 相談事・お悩み・日々の愚痴や不安（無理に詮索せず受容・共感し、安心感を届ける）\n"
                                        f"※思考解説や英語は一切喋らず、利用者様への温かい日本語の返答のみ（1〜2文）を発話してください。\n"
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

    async def send_end_of_turn(self, text: str = ""):
        """Signals end of user utterance to trigger Gemini Live response generation (always sends turnComplete)."""
        if not await self.ensure_connected():
            return
            
        self._interrupted = False
        transcription = text.strip()
        parts = []
        if transcription:
            if len(transcription) > 80:
                subparts = [p.strip() for p in re.split(r'[。！？?\n]', transcription) if p.strip()]
                if subparts:
                    transcription = subparts[-1]
            parts.append({"text": transcription})

        # Gemini Live Bidi API requires turns when clientContent is present.
        # Sending clientContent without turns triggers a 1007 invalid argument error.
        # If there is no explicit text transcription, audio-driven VAD handles turn completion natively.
        if not parts:
            print(f"[Gemini Live Session]: Audio-driven turn completed (no text payload needed).")
            return

        try:
            content_body = {
                "turnComplete": True,
                "turns": [
                    {
                        "role": "user",
                        "parts": parts
                    }
                ]
            }
            client_content = {"clientContent": content_body}
            await self.ws.send(json.dumps(client_content))
            print(f"[Gemini Live Session]: End of turn signal sent (text: '{transcription}').")
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
                model_turn = server_content.get("modelTurn", {})
                parts = model_turn.get("parts", [])
                
                for part in parts:
                    # Text response or thought
                    if "text" in part and part["text"]:
                        text_val = part["text"].strip()
                        if text_val.startswith("**") or text_val.startswith("Thought:") or "reassuring" in text_val.lower():
                            print(f"[Gemini Live Session Filtered Thought]: {text_val}")
                            if self.on_thought_received:
                                self.on_thought_received(text_val)
                            continue
                        if text_val and self.on_text_received:
                            self.on_text_received(text_val)

                        # Detect Mimamori-san recording commands from Gemini speech
                        if "会話記録を停止" in text_val or "会話記録の停止" in text_val:
                            print(f"[Gemini Live Session]: Detected confidential recording stop command: '{text_val}'")
                            self.recording_active = False
                            if self.on_recording_status_changed:
                                self.on_recording_status_changed(False, "会話記録停止")
                        elif "会話記録を再開" in text_val or "会話記録の再開" in text_val:
                            print(f"[Gemini Live Session]: Detected recording resume command: '{text_val}'")
                            self.recording_active = True
                            if self.on_recording_status_changed:
                                self.on_recording_status_changed(True, "会話記録再開")
                    
                    # Audio chunk response
                    inline_data = part.get("inlineData", {})
                    mime_type = inline_data.get("mimeType", "")
                    if "audio/pcm" in mime_type and "data" in inline_data:
                        if self._interrupted:
                            continue
                        audio_b64 = inline_data["data"]
                        raw_pcm24 = base64.b64decode(audio_b64)
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
