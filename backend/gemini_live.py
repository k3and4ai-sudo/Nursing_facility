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
        self.prohibited_terms = []
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
                
        # Regex patterns for telephone numbers, addresses, my-number
        self.pii_patterns = [
            re.compile(r'\d{2,4}[-\s]?\d{2,4}[-\s]?\d{4}'),  # Phone numbers
            re.compile(r'\d{3}[-\s]?\d{4}'),                 # Postal codes
            re.compile(r'\d{12}'),                            # My Number 12 digits
            re.compile(r'(東京都|大阪府|京都府|北海道|.{2,3}県).{1,5}(市|区|町|村)'), # Address
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
            
            # Execute Whisper STT in threadpool executor
            loop = asyncio.get_running_loop()
            whisper_model = get_whisper_model()
            
            def _stt():
                return whisper_model.transcribe(audio_np, language="ja", fp16=False)
                
            result = await loop.run_in_executor(None, _stt)
            text = result.get("text", "").strip()
            
            if not text or not is_japanese_speech(text):
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
            for pat in self.pii_patterns:
                if pat.search(text):
                    print(f"[PII ALERT TRIGGERED]: Found PII pattern in speech: '{text}'")
                    self.is_active = False
                    if self.on_pii_detected:
                        self.on_pii_detected("pattern_match", "電話番号・住所・識別番号などの個人情報が含まれていました。")
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
        history: Optional[list] = None
    ):
        self.user = user
        self.on_audio_received = on_audio_received
        self.on_error = on_error
        self.on_text_received = on_text_received
        self.history = history or []
        self.ws = None
        self.is_connected = False
        self.is_closing = False
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
                                        f"あなたは介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。"
                                        f"利用者のニックネームは「{nickname}」様です。温かく優しく短い日本語で相槌を打ちながら会話してください。"
                                        f"否定せず受容・共感の姿勢を徹底し、思考解説や英語テキストは一切出力せず、即座に利用者様への短い1〜2文の日本語返答のみを音声出力してください。"
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
            
        transcription = text.strip()
        parts = []
        if transcription:
            if len(transcription) > 80:
                subparts = [p.strip() for p in re.split(r'[。！？?\n]', transcription) if p.strip()]
                if subparts:
                    transcription = subparts[-1]
            parts.append({"text": transcription})

        try:
            client_content = {
                "clientContent": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": parts
                        }
                    ] if parts else [],
                    "turnComplete": True
                }
            }
            await self.ws.send(json.dumps(client_content))
            print(f"[Gemini Live Session]: End of turn signal sent (text: '{transcription}').")
        except Exception as e:
            print(f"[Gemini Live End of Turn Error]: {e}")
            self.is_connected = False

    async def send_interruption(self):
        """Sends interruption frame to immediately cancel Gemini's current audio generation."""
        if not self.is_connected or not self.ws:
            return
            
        try:
            client_content = {
                "clientContent": {
                    "turns": [],
                    "turnComplete": True
                }
            }
            await self.ws.send(json.dumps(client_content))
            print("[Gemini Live Session]: Interruption signal sent.")
        except Exception as e:
            print(f"[Gemini Live Interruption Error]: {e}")
            self.is_connected = False

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
                            continue
                        if text_val and self.on_text_received:
                            self.on_text_received(text_val)
                    
                    # Audio chunk response
                    inline_data = part.get("inlineData", {})
                    mime_type = inline_data.get("mimeType", "")
                    if "audio/pcm" in mime_type and "data" in inline_data:
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
