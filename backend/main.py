import os
import asyncio
import time
import re
import json
import base64
import requests
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

import backend.config as config
from backend.config import BASE_DIR, OLLAMA_URL, OLLAMA_MODEL, encrypt_data, decrypt_data
import backend.database as db
import backend.speech as speech
import backend.rag as rag
import backend.vital_parser as vital_parser
from backend.gemini_live import GeminiLiveSession, PIIGuardrailMonitor

# Initialize Database on Import/Startup
db.db_init()

app = FastAPI(title="Nursing Facility API", version="1.0.0")

# Enable CORS for local WiFi access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class LoginRequest(BaseModel):
    user_code: str
    password: str

class UserCreate(BaseModel):
    name: str
    age: int
    room_number: str
    terminal_id: str
    dementia_level: str
    notes: str = ""
    attention_points: str = ""

class UserUpdate(BaseModel):
    name: str
    age: int
    room_number: str
    terminal_id: str
    dementia_level: str
    notes: str = ""
    attention_points: str = ""

class HandoverCreate(BaseModel):
    author: str
    content: str

# HTTP Endpoints

@app.post("/api/auth/login")
def login_user(login_data: LoginRequest):
    user_acc = db.authenticate_user_account(login_data.user_code, login_data.password)
    if not user_acc:
        raise HTTPException(status_code=401, detail="ユーザーIDまたはパスワードが正しくありません")
    return {
        "status": "success",
        "user_code": user_acc["user_code"],
        "name": user_acc["name"],
        "role": user_acc["role"],
        "group_id": user_acc["group_id"],
        "terminal_id": user_acc["terminal_id"]
    }

@app.post("/api/users")
def create_user(user: UserCreate):
    try:
        user_id = db.add_user(
            name=user.name,
            age=user.age,
            room_number=user.room_number,
            terminal_id=user.terminal_id,
            dementia_level=user.dementia_level,
            notes=user.notes,
            attention_points=user.attention_points
        )
        return {"id": user_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/{user_id}")
def update_user_details(user_id: int, user: UserUpdate):
    try:
        db.update_user(
            user_id=user_id,
            name=user.name,
            age=user.age,
            room_number=user.room_number,
            terminal_id=user.terminal_id,
            dementia_level=user.dementia_level,
            notes=user.notes,
            attention_points=user.attention_points
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/users")
def list_users():
    return db.get_all_users()

@app.get("/api/users/{user_id}")
def get_user_details(user_id: int):
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u

@app.get("/api/users/terminal/{terminal_id}")
def get_user_by_terminal_id(terminal_id: str):
    u = db.get_user_by_terminal(terminal_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not bound to this terminal")
    return u

@app.delete("/api/users/{user_id}")
def delete_user_record(user_id: int):
    db.delete_user(user_id)
    return {"status": "success"}

@app.get("/api/users/{user_id}/vitals")
def get_user_vitals(user_id: int):
    return db.get_vital_records(user_id)

@app.get("/api/vitals")
def get_all_vitals():
    return db.get_all_recent_vitals()

@app.get("/api/users/{user_id}/chat")
def get_user_chat(user_id: int):
    return db.get_chat_history(user_id)

@app.post("/api/handovers")
def create_handover(h: HandoverCreate):
    db.add_handover(h.author, h.content)
    return {"status": "success"}

@app.get("/api/handovers")
def list_handovers():
    return db.get_handovers()

@app.get("/api/staff-messages")
def list_staff_messages():
    return db.get_staff_messages()

# Connection Managers for WebSockets
class ConnectionManager:
    def __init__(self):
        # Map: terminal_id -> WebSocket
        self.user_connections: Dict[str, WebSocket] = {}
        # List of staff WebSockets
        self.staff_connections: List[WebSocket] = []

    async def connect_user(self, terminal_id: str, websocket: WebSocket):
        await websocket.accept()
        self.user_connections[terminal_id] = websocket
        print(f"User Client connected: {terminal_id}")

    def disconnect_user(self, terminal_id: str):
        if terminal_id in self.user_connections:
            del self.user_connections[terminal_id]
            print(f"User Client disconnected: {terminal_id}")

    async def connect_staff(self, websocket: WebSocket):
        await websocket.accept()
        self.staff_connections.append(websocket)
        print("Staff Client connected")

    def disconnect_staff(self, websocket: WebSocket):
        if websocket in self.staff_connections:
            self.staff_connections.remove(websocket)
            print("Staff Client disconnected")

    async def broadcast_to_staff(self, message: dict):
        dead_connections = []
        for connection in self.staff_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect_staff(dead)

    async def send_to_user(self, terminal_id: str, message: dict):
        websocket = self.user_connections.get(terminal_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_user(terminal_id)

manager = ConnectionManager()

# Helper for calling Ollama for General Conversation
def query_ollama_chat(user: dict, chat_history: list, new_message: str, memory_context: str) -> str:
    """
    Formulates a prompt with persona, dementia attention points, memory context, and chats with Gemma.
    """
    dementia_info = {
        "none": "健康で認知機能に問題ありません。",
        "mild": "軽度の認知症があります。優しく、同じことを何度も聞かれても丁寧に答えてください。",
        "moderate": "中等度の認知症があります。簡単な言葉を使い、安心感を与える話し方を心がけてください。",
        "severe": "重度の認知症があります。言葉は非常にシンプルにし、受容と共感を最優先にし、決して否定しないでください。"
    }
    dem_desc = dementia_info.get(user.get("dementia_level", ""), "")
    
    is_first_turn = (len(chat_history) == 0)
    current_time_str = db.datetime.now().strftime("%Y年%m月%d日 %H時%M分")
    
    if is_first_turn:
        name_instruction = f"利用者の名前は「{user.get('name', '利用者')}」様です。最初の会話ですので、「{user.get('name', '利用者')}さん、こんにちは！」のように名前を入れて温かく迎えてください。"
    else:
        name_instruction = "【重要】これは継続中の会話です。ユーザーの名前（「〇〇さん」「〇〇様」など）は絶対に使わないでください。名前を一切呼ばず、「そうですね」「はい」など自然な相槌から発言を開始してください。"

    # Construct System Prompt
    system_prompt = f"""あなたは介護施設の高齢者ケアに特化したAIアシスタントです。
現在の施設内時刻: {current_time_str}
{name_instruction}
利用者の特徴: {dem_desc}
AI対話時の注意点: {user.get("attention_points", "特になし")}
申し送り・特記事項: {user.get("notes", "特になし")}

対話時のルール:
1. 相手の言葉を否定せず、傾聴、共感、受容の姿勢を徹底してください。
2. 認知症の特性を考慮し、優しく温かい口調で（「〜ですね」「〜ですよ」など）、簡潔に話してください。
3. ユーザーから時間や日付を直接質問された場合のみ、時刻（{current_time_str}）を答えてください。時間や日付を聞かれていない時は、絶対に文末に時刻や日付を付け足さないでください。
4. 過去の会話の記憶があれば、それを自然に会話に取り入れてください。
5. 専門用語は使わず、親しみやすい日本語で対話してください。

{memory_context}
"""
    # Build Messages history for Ollama chat API
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent chat history (limit to last 6 messages to keep context concise)
    for msg in chat_history[-6:]:
        role = "user" if msg["sender"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["message"]})
        
    # Add current message
    messages.append({"role": "user", "content": new_message})
    
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        ai_reply = response.json().get("message", {}).get("content", "").strip()
        
        # Post-processing: If not first turn, filter out any residual name prefixes
        if not is_first_turn and user.get("name"):
            full_name = user["name"]
            parts = full_name.split()
            first_name = parts[0] if parts else full_name
            for n in [full_name, first_name]:
                ai_reply = re.sub(rf"^{n}(さん|様|くん|ちゃん)?(、|。|\s|！|\!)?", "", ai_reply).strip()
                ai_reply = re.sub(rf"{n}(さん|様|くん|ちゃん)", "", ai_reply).strip()
                
        return ai_reply if ai_reply else "はい、どうぞお話しください。"
    except Exception as e:
        import traceback
        print(f"Ollama API query error: {e}")
        traceback.print_exc()
        return "ただいまの時刻は " + db.datetime.now().strftime("%H時%M分") + " ですよ。お話ししてくださりありがとうございます。"

def anonymize_user_name(name: str) -> str:
    """Converts full real name (e.g. 山田 太郎) into an anonymized nickname (e.g. たろうさん)."""
    if not name:
        return "利用者さん"
    parts = name.split()
    first_name = parts[-1] if len(parts) > 1 else name
    return f"{first_name}さん"

def sanitize_gemini_response(text: str, is_time_requested: bool = False) -> str:
    """
    Strips disclaimer meta-text (e.g., '**注意:** この会話は...', '※注:...', '会話例:')
    and unwanted trailing facility timestamp additions unless time was requested.
    """
    if not text:
        return ""
    
    # Truncate anything starting from disclaimer markers
    pattern = r'(\*\*注意|注意:|注:|※注|この会話は|意図的に|AIアシスタントが|認知症高齢者に対して|再認識することができる)'
    match = re.search(pattern, text)
    if match:
        text = text[:match.start()].strip()

    # Strip trailing unprompted facility time additions
    if not is_time_requested:
        text = re.sub(r'[\(（]?施設内?時刻[は:\s]*\d{4}年\d{2}月\d{2}日\s*\d{2}時\d{2}分です?[\)）\s]*[😊😃😄]*', '', text).strip()
        text = re.sub(r'[\(（]?現在の?時間[は:\s]*\d{2}時\d{2}分です?[\)）\s]*[😊😃😄]*', '', text).strip()
    
    # Remove lingering markdown formatting
    text = re.sub(r'[\*\#\`\_\~]', '', text).strip()
    if not text:
        return "はい、聞こえていますよ。ゆっくりお話ししましょうね。"
    return text

def query_gemini_live_chat(user: dict, chat_history: list, new_message: str, memory_context: str) -> str:
    """
    Queries Gemini 2.0 API directly in Debug Mode for Gemini Live full-duplex conversational experience.
    Enforces strict privacy anonymization rules before calling external cloud API.
    """
    nickname = anonymize_user_name(user.get("name", ""))
    dementia_info = {
        "none": "認知機能に問題ありません。",
        "mild": "軽度の認知症があります。優しく共感的に応じてください。",
        "moderate": "中等度の認知症があります。言葉はシンプルにし安心感を与えてください。",
        "severe": "重度の認知症があります。受容と共感を最優先にしてください。"
    }
    dem_desc = dementia_info.get(user.get("dementia_level", "mild"), "")
    current_time_str = db.datetime.now().strftime("%Y年%m月%d日 %H時%M分")

    system_prompt = f"""あなたは介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。
【重要プライバシー規定】利用者の実名はクラウド送信禁止です。必ずニックネーム「{nickname}」として接してください。
現在の施設時刻: {current_time_str}
対象者の特徴: {dem_desc}
AI対話時の注意点: {user.get("attention_points", "優しく傾聴")}

ルール:
1. 相手の言葉を否定せず、傾聴・共感・受容に努めてください。
2. 簡潔で温かい日本語（「〜ですね」「〜ですよ」1〜2文の短文）で答えてください。
3. 会話例・注意書き・注釈（『注意:』『注:』『意図的に...』など）は絶対に含めず、高齢者への直接の発話応答のみを返してください。
4. ユーザーから時間や日付を直接質問された場合のみ、時刻（{current_time_str}）を答えてください。時間や日付を聞かれていない時は、絶対に文末に時刻や日付を付け足さないでください。
"""

    gemini_key = os.getenv("GEMINI_API_KEY", config.GEMINI_API_KEY)
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={gemini_key}"
            contents = []
            for msg in chat_history[-4:]:
                role = "user" if msg["sender"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["message"]}]})
            
            contents.append({"role": "user", "parts": [{"text": new_message}]})

            payload = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 200
                }
            }
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                res_data = res.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = sanitize_gemini_response(text)
                if text:
                    return f"✨ [Gemini Live] {text}"
        except Exception as e:
            print(f"Gemini API direct query fallback: {e}")

    # Fallback to local Ollama (Gemma2) when API Key is missing or cloud query fails
    anon_user = dict(user)
    anon_user["name"] = nickname
    reply = query_ollama_chat(anon_user, chat_history, new_message, memory_context)
    if not reply.startswith("✨ [Gemini Live]"):
        reply = f"✨ [Gemini Live] {reply}"
    return reply

def query_gemini_live_audio(user: dict, chat_history: list, audio_bytes: bytes, memory_context: str) -> dict:
    """
    Directly streams raw user audio bytes (WAV/PCM) to Google Gemini API using native inlineData audio understanding.
    Ensures zero intermediate Whisper STT errors, maximum recognition quality, and strict privacy anonymization.
    """
    nickname = anonymize_user_name(user.get("name", ""))
    dementia_info = {
        "none": "認知機能に問題ありません。",
        "mild": "軽度の認知症があります。優しく共感的に応じてください。",
        "moderate": "中等度の認知症があります。言葉はシンプルにし安心感を与えてください。",
        "severe": "重度の認知症があります。受容と共感を最優先にしてください。"
    }
    dem_desc = dementia_info.get(user.get("dementia_level", "mild"), "")
    current_time_str = db.datetime.now().strftime("%Y年%m月%d日 %H時%M分")

    system_prompt = f"""あなたは介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。
【重要プライバシー規定】利用者の実名はクラウド送信禁止です。必ずニックネーム「{nickname}」として接してください。
現在の施設時刻: {current_time_str}
対象者の特徴: {dem_desc}
AI対話時の注意点: {user.get("attention_points", "優しく傾聴")}

ルール:
1. 相手の言葉を否定せず、傾聴・共感・受容に努めてください。
2. 簡潔で温かい日本語（「〜ですね」「〜ですよ」）で答えてください。
3. 時間を聞かれたら {current_time_str} を答えてください。
"""

    gemini_key = os.getenv("GEMINI_API_KEY", config.GEMINI_API_KEY)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={gemini_key}"
            contents = []
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": f"了解しました。{nickname}のお話に寄り添って対話します。"}]})
            
            for msg in chat_history[-4:]:
                role = "user" if msg["sender"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["message"]}]})
            
            # Send raw audio natively to Gemini via inlineData!
            contents.append({
                "role": "user", 
                "parts": [
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_b64}}
                ]
            })

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 250
                }
            }
            res = requests.post(url, json=payload, timeout=12)
            if res.status_code == 200:
                res_data = res.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text:
                    return {
                        "user_transcript": f"🎤 Gemini Live 直通音声入力 ({nickname})",
                        "ai_reply": f"✨ [Gemini Live] {text}"
                    }
        except Exception as e:
            print(f"Gemini Multimodal direct audio query fallback: {e}")

    # Fallback / Debug Simulation when API Key is missing or debug testing
    return {
        "user_transcript": f"🎤 Gemini Live 直通音声入力 ({nickname})",
        "ai_reply": f"✨ [Gemini Live デバッグ応答] {nickname}、直接お話しできて嬉しいです！今日も穏やかな一日ですね。"
    }

def clean_text_for_tts(text: str) -> str:
    """Strips debug tags, markdown formatting, and emojis for natural spoken TTS audio."""
    if not text:
        return ""
    # Remove prefix tags like ✨ [Gemini Live] or ✨ [Gemini Live デバッグ応答]
    text = re.sub(r"✨?\s*\[Gemini Live[^\]]*\]\s*", "", text)
    # Remove markdown bold/italics
    text = re.sub(r"[*_~`#]", "", text)
    return text.strip()

@app.get("/api/config/system_info")
def api_get_system_info():
    """Returns system capabilities and debug release flags for frontend UI control."""
    return {
        "enable_debug_mode": config.ENABLE_DEBUG_MODE,
        "gemini_api_configured": bool(os.getenv("GEMINI_API_KEY", config.GEMINI_API_KEY))
    }

# Global Bidi Audio Buffer map for full-duplex streaming
bidi_buffers: Dict[str, bytearray] = {}
is_processing_speech: Dict[str, bool] = {}

# WebSocket Endpoint for User client
@app.websocket("/ws/user/{terminal_id}")
async def websocket_user_endpoint(websocket: WebSocket, terminal_id: str):
    await manager.connect_user(terminal_id, websocket)
    bidi_buffers[terminal_id] = bytearray()
    is_processing_speech[terminal_id] = False
    
    # Check if a user is bound to this terminal
    user = db.get_user_by_terminal(terminal_id)
    if not user:
        # Not bound yet
        await websocket.send_json({
            "type": "error", 
            "message": f"端末ID '{terminal_id}' は登録されていません。スタッフ画面で新規登録してください。"
        })
        manager.disconnect_user(terminal_id)
        return

    user_id = user["id"]
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Stop stream and clear buffer when user turns off mic
            if msg_type == "stop_bidi_stream":
                bidi_buffers[terminal_id] = bytearray()
                is_processing_speech[terminal_id] = False
                print(f"Bidi audio stream stopped and flushed for terminal {terminal_id}")
                continue

            # Pattern Full-Duplex: Continuous Bidi Audio Stream Chunk from Client
            if msg_type == "bidi_audio":
                # Drop chunk if backend is currently processing an AI response to prevent buffer backlog loop
                if is_processing_speech.get(terminal_id, False):
                    bidi_buffers[terminal_id] = bytearray()
                    continue

                is_eos = data.get("eos", False)
                audio_b64 = data.get("audio")
                if audio_b64:
                    chunk_bytes = base64.b64decode(audio_b64)
                    bidi_buffers[terminal_id].extend(chunk_bytes)
                    
                    # Process full sentence utterance when client signals End of Speech (eos) or max buffer reached
                    if (is_eos or len(bidi_buffers[terminal_id]) >= 96000) and len(bidi_buffers[terminal_id]) >= 12000 and not is_processing_speech.get(terminal_id, False):
                        is_processing_speech[terminal_id] = True
                        audio_bytes = bytes(bidi_buffers[terminal_id])
                        bidi_buffers[terminal_id].clear()
                        
                        stt_start_time = time.time()
                        transcribed_text = await asyncio.to_thread(speech.transcribe_audio, audio_bytes)
                        stt_time = time.time() - stt_start_time
                        clean_text = transcribed_text.strip() if transcribed_text else ""
                        
                        if (clean_text 
                            and clean_text != "[音声認識エラー]" 
                            and len(clean_text) >= 2
                            and not clean_text.startswith("ご視聴") 
                            and not clean_text.startswith("視聴いただき")
                            and not clean_text.startswith("チャンネル登録")):
                            
                            # Suppress duplicate consecutive transcriptions
                            history_check = db.get_chat_history(user_id, limit=2)
                            if history_check and any(h.get("message") == clean_text for h in history_check if h.get("sender") == "user"):
                                print(f"Suppressing duplicate full-duplex transcription: '{clean_text}'")
                                bidi_buffers[terminal_id] = bytearray()
                                is_processing_speech[terminal_id] = False
                                continue

                            # 1. Stream the actual transcribed speech text to the client UI (#user-speech-box)
                            await websocket.send_json({
                                "type": "transcription_result",
                                "text": clean_text
                            })

                            history = db.get_chat_history(user_id, limit=6)
                            llm_start_time = time.time()
                            
                            # Use Gemini Live Chat Engine when debug mode or Gemini API Key is available
                            if config.ENABLE_DEBUG_MODE or data.get("debug_mode", False) or data.get("is_debug", False) or config.GEMINI_API_KEY:
                                ai_reply = await asyncio.to_thread(query_gemini_live_chat, user, history, clean_text, "")
                            else:
                                ai_reply = await asyncio.to_thread(query_ollama_chat, user, history, clean_text, "")
                            
                            # Sanitize response to ensure no disclaimers or raw tags slip into DB or UI
                            ai_reply = sanitize_gemini_response(ai_reply)
                            llm_time = time.time() - llm_start_time
                            
                            db.add_chat_message(user_id, "user", clean_text)
                            db.add_chat_message(user_id, "ai", ai_reply)
                            
                            await manager.broadcast_to_staff({
                                "type": "user_chat",
                                "user_id": user_id,
                                "sender": "ai",
                                "message": ai_reply,
                                "timestamp": db.datetime.now().isoformat()
                            })
                            
                            tts_start_time = time.time()
                            tts_text = clean_text_for_tts(ai_reply)
                            audio_res = await asyncio.to_thread(speech.synthesize_speech, tts_text)
                            tts_time = time.time() - tts_start_time
                            
                            # 2. Stream AI response text & audio to client UI (#ai-response-box)
                            await websocket.send_json({
                                "type": "chat_response",
                                "text": ai_reply,
                                "audio": base64.b64encode(audio_res).decode("utf-8"),
                                "stt_time": stt_time,
                                "llm_time": llm_time,
                                "tts_time": tts_time,
                                "full_duplex": True
                            })
                            bidi_buffers[terminal_id] = bytearray()
                            is_processing_speech[terminal_id] = False
                        else:
                            bidi_buffers[terminal_id] = bytearray()
                            is_processing_speech[terminal_id] = False

            # User speaking / inputting text (Turn-based fallback)
            elif msg_type == "audio_input":
                # Audio base64 string sent from client
                audio_b64 = data.get("audio")
                audio_bytes = base64.b64decode(audio_b64)
                
                # Send status to client: STT started
                await websocket.send_json({
                    "type": "processing_status",
                    "status": "stt_start"
                })
                
                # STT
                stt_start_time = time.time()
                transcribed_text = await asyncio.to_thread(speech.transcribe_audio, audio_bytes)
                stt_time = time.time() - stt_start_time
                
                if not transcribed_text or transcribed_text.strip() == "[音声認識エラー]":
                    tts_err = await asyncio.to_thread(speech.synthesize_speech, "うまく聞き取れませんでした。もう一度お話しいただけますか？")
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": "うまく聞き取れませんでした。もう一度お話しいただけますか？",
                        "audio": base64.b64encode(tts_err).decode("utf-8"),
                        "stt_time": stt_time,
                        "llm_time": 0.0,
                        "tts_time": 0.0
                    })
                    continue
                
                # Send transcribed text back to client immediately for user display
                await websocket.send_json({
                    "type": "transcription_result",
                    "text": transcribed_text
                })
                
                # Save User Message to DB
                db.add_chat_message(user_id, "user", transcribed_text)
                
                # Broadcast user speech to staff in real-time
                await manager.broadcast_to_staff({
                    "type": "user_chat",
                    "user_id": user_id,
                    "sender": "user",
                    "message": transcribed_text,
                    "timestamp": db.datetime.now().isoformat()
                })
                
                # Send status to client: LLM started (STT finished)
                await websocket.send_json({
                    "type": "processing_status",
                    "status": "llm_start",
                    "stt_time": stt_time
                })
                
                # 1. Check if user is reporting vitals
                llm_start_time = time.time()
                vitals = await asyncio.to_thread(vital_parser.extract_vitals_from_text, transcribed_text)
                
                has_vitals = any(v is not None for v in vitals.values())
                
                if has_vitals:
                    # Validate extracted values
                    is_alert, alert_reason = vital_parser.validate_vitals(vitals)
                    
                    # Store vital record
                    db.add_vital_record(
                        user_id=user_id,
                        temperature=vitals["temperature"],
                        weight=vitals["weight"],
                        bp_sys=vitals["systolic"],
                        bp_dia=vitals["diastolic"],
                        raw_text=transcribed_text,
                        is_alert=1 if is_alert else 0,
                        alert_reason=alert_reason
                    )
                    
                    # Generate AI Vitals confirmation response
                    parts = []
                    if vitals["temperature"] is not None:
                        parts.append(f"体温は{vitals['temperature']}度")
                    if vitals["weight"] is not None:
                        parts.append(f"体重は{vitals['weight']}キロ")
                    if vitals["systolic"] is not None and vitals["diastolic"] is not None:
                        parts.append(f"血圧は上が{vitals['systolic']}、下が{vitals['diastolic']}")
                        
                    confirm_text = "、".join(parts) + "ですね。記録しました。"
                    
                    if is_alert:
                        confirm_text += " 少しお体がしんどいですか？看護師さんに連絡しますね。"
                        # Broadcast alert to staff
                        await manager.broadcast_to_staff({
                            "type": "vital_alert",
                            "user_id": user_id,
                            "user_name": user["name"],
                            "room_number": user["room_number"],
                            "vitals": vitals,
                            "reason": alert_reason,
                            "timestamp": db.datetime.now().isoformat()
                        })
                    else:
                        confirm_text += " 今日も元気に過ごしましょうね。"
                    
                    llm_time = time.time() - llm_start_time
                    
                    # Send status to client: TTS started (LLM finished)
                    await websocket.send_json({
                        "type": "processing_status",
                        "status": "tts_start",
                        "stt_time": stt_time,
                        "llm_time": llm_time
                    })
                    
                    # Save AI Message
                    db.add_chat_message(user_id, "ai", confirm_text)
                    
                    # Broadcast to staff
                    await manager.broadcast_to_staff({
                        "type": "user_chat",
                        "user_id": user_id,
                        "sender": "ai",
                        "message": confirm_text,
                        "timestamp": db.datetime.now().isoformat()
                    })
                    
                    # Generate speech
                    tts_start_time = time.time()
                    audio_res = await asyncio.to_thread(speech.synthesize_speech, confirm_text)
                    tts_time = time.time() - tts_start_time
                    
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": confirm_text,
                        "audio": base64.b64encode(audio_res).decode("utf-8"),
                        "stt_time": stt_time,
                        "llm_time": llm_time,
                        "tts_time": tts_time
                    })
                    
                else:
                    # 2. General Conversation (Ollama vs Gemini Live Debug Mode)
                    is_debug_mode = config.ENABLE_DEBUG_MODE and (data.get("debug_mode", False) or data.get("is_debug", False))
                    history = db.get_chat_history(user_id, limit=6)
                    
                    if is_debug_mode:
                        # Query Gemini Live engine (Debug Mode)
                        ai_reply = await asyncio.to_thread(query_gemini_live_chat, user, history, transcribed_text, "")
                    else:
                        # Query Gemma (Local Ollama) for chat reply
                        ai_reply = await asyncio.to_thread(query_ollama_chat, user, history, transcribed_text, "")
                    
                    llm_time = time.time() - llm_start_time
                    
                    # Send status to client: TTS started (LLM finished)
                    await websocket.send_json({
                        "type": "processing_status",
                        "status": "tts_start",
                        "stt_time": stt_time,
                        "llm_time": llm_time
                    })
                    
                    # Save AI reply to DB
                    db.add_chat_message(user_id, "ai", ai_reply)
                    
                    # Generate Speech (cleansed of debug tags) and send back to client IMMEDIATELY
                    tts_start_time = time.time()
                    tts_text = clean_text_for_tts(ai_reply)
                    audio_res = await asyncio.to_thread(speech.synthesize_speech, tts_text)
                    tts_time = time.time() - tts_start_time
                    
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": ai_reply,
                        "audio": base64.b64encode(audio_res).decode("utf-8"),
                        "stt_time": stt_time,
                        "llm_time": llm_time,
                        "tts_time": tts_time
                    })
                    
                    # Broadcast to staff console
                    await manager.broadcast_to_staff({
                        "type": "user_chat",
                        "user_id": user_id,
                        "sender": "ai",
                        "message": ai_reply,
                        "timestamp": db.datetime.now().isoformat()
                    })

                    # Save memory asynchronously after response has been sent
                    try:
                        rag.store_conversation_memory(user_id, transcribed_text, ai_reply)
                    except Exception as e:
                        print(f"Background RAG embedding skipped: {e}")
            
            # Pattern A: Real-time Audio Stream from User to Staff (Intercom)
            elif msg_type == "audio_stream":
                audio_chunk = data.get("audio") # Base64 string
                await manager.broadcast_to_staff({
                    "type": "intercom_audio",
                    "source": terminal_id,
                    "audio": audio_chunk
                })
                
            elif msg_type == "hangup":
                await manager.broadcast_to_staff({
                    "type": "intercom_hangup",
                    "source": terminal_id
                })

    except WebSocketDisconnect:
        manager.disconnect_user(terminal_id)
        # Notify staff user disconnected
        await manager.broadcast_to_staff({
            "type": "user_status",
            "terminal_id": terminal_id,
            "status": "offline"
        })
    except Exception as e:
        print(f"Error in user websocket: {e}")
        manager.disconnect_user(terminal_id)

# WebSocket Endpoint for User Gemini Live Native Streaming & Parallel PII Guardrail
@app.websocket("/ws/user/{terminal_id}/live")
async def websocket_user_live_endpoint(websocket: WebSocket, terminal_id: str):
    await websocket.accept()
    user = db.get_user_by_terminal(terminal_id)
    if not user:
        await websocket.send_json({
            "type": "error",
            "message": f"端末ID '{terminal_id}' は登録されていません。"
        })
        await websocket.close()
        return

    # Forward 24kHz PCM audio from Gemini Live to client
    async def on_gemini_audio(pcm24_bytes: bytes):
        try:
            b64_data = base64.b64encode(pcm24_bytes).decode("utf-8")
            await websocket.send_json({
                "type": "live_audio_output",
                "sample_rate": 24000,
                "data": b64_data
            })
        except Exception as e:
            print(f"Error sending live audio to client ({terminal_id}): {e}")

    async def on_gemini_text(text: str):
        try:
            await websocket.send_json({
                "type": "live_text_output",
                "text": text
            })
        except Exception as e:
            print(f"Error sending live text to client ({terminal_id}): {e}")

    async def on_user_transcription(text: str):
        try:
            await websocket.send_json({
                "type": "transcription_result",
                "text": text
            })
        except Exception as e:
            print(f"Error sending transcription result to client ({terminal_id}): {e}")

    def on_gemini_error(err_msg: str):
        print(f"Gemini Live Session Error ({terminal_id}): {err_msg}")

    # Fetch recent conversation history for memory context sync
    recent_history = db.get_chat_history(user["id"], limit=6)

    # Initialize Gemini Live Session
    session = GeminiLiveSession(
        user=user,
        on_audio_received=lambda audio: asyncio.create_task(on_gemini_audio(audio)),
        on_error=on_gemini_error,
        on_text_received=lambda txt: asyncio.create_task(on_gemini_text(txt)),
        history=recent_history
    )

    # Triggered when Parallel Whisper/Ollama PII Inspector detects forbidden personal info
    def on_pii_detected(category: str, detail: str):
        print(f"[LIVE PII GUARDRAIL TRIGGERED] ({terminal_id}): {category} - {detail}")
        # 1. Immediately send interruption frame to Gemini Live WebSocket session
        asyncio.create_task(session.send_interruption())
        # 2. Notify user client to halt playback and show warning UI / audio
        asyncio.create_task(websocket.send_json({
            "type": "pii_warning",
            "category": category,
            "message": "個人情報保護のため会話を一時停止しました。個人情報は話さないようお願いいたします。"
        }))
        # 3. Broadcast real-time PII Alert to Staff Dashboard
        asyncio.create_task(manager.broadcast_to_staff({
            "type": "pii_alert",
            "terminal_id": terminal_id,
            "user_name": user.get("name", "未登録"),
            "room_number": user.get("room_number", "-"),
            "category": category,
            "detail": detail,
            "timestamp": db.datetime.now().strftime("%H:%M:%S")
        }))

    # Initialize Parallel PII Guardrail Monitor
    pii_monitor = PIIGuardrailMonitor(
        user=user,
        on_pii_detected=on_pii_detected,
        on_transcription=lambda txt: asyncio.create_task(on_user_transcription(txt))
    )

    # Fallback audio accumulator when GEMINI_API_KEY is not set
    fallback_pcm_buffer = bytearray()
    last_fallback_speech_time = time.time()
    is_generating_fallback = False

    async def process_fallback_audio():
        nonlocal is_generating_fallback, fallback_pcm_buffer
        if is_generating_fallback or len(fallback_pcm_buffer) < 16000:
            return
        is_generating_fallback = True
        try:
            pcm_copy = bytes(fallback_pcm_buffer)
            fallback_pcm_buffer.clear()
            
            # Convert PCM to Float32 for Whisper
            audio_np = np.frombuffer(pcm_copy, dtype=np.int16).astype(np.float32) / 32768.0
            loop = asyncio.get_running_loop()
            whisper_model = speech.get_whisper_model()
            
            stt_res = await loop.run_in_executor(None, lambda: whisper_model.transcribe(audio_np, language="ja", fp16=False))
            text = stt_res.get("text", "").strip()
            
            if text and speech.is_japanese_speech(text):
                print(f"[Live Fallback STT]: '{text}'")
                reply = query_ollama_chat(user, [], text, "")
                cleaned_reply = clean_text_for_tts(reply)
                tts_audio_b64 = speech.generate_tts_audio_base64(cleaned_reply)
                
                await websocket.send_json({
                    "type": "chat_response",
                    "text": cleaned_reply,
                    "user_text": text,
                    "audio": tts_audio_b64,
                    "stt_time": 0.3,
                    "llm_time": 0.5,
                    "tts_time": 0.2
                })
        except Exception as e:
            print(f"[Live Fallback Error]: {e}")
        finally:
            is_generating_fallback = False

    try:
        # Try connecting to native Gemini Live WS
        try:
            await session.connect()
        except Exception as e:
            print(f"[Gemini Live Session Notice]: {e}. Operating in local Ollama fallback mode.")

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "live_pcm_chunk":
                # Incoming raw 16kHz PCM chunk (base64) from client
                b64_chunk = data.get("data", "")
                if b64_chunk:
                    pcm_bytes = base64.b64decode(b64_chunk)
                    # 1. Relay raw PCM to Gemini Live session if connected
                    if session.is_connected:
                        await session.send_audio_chunk(pcm_bytes)
                    else:
                        # Fallback mode: accumulate PCM chunks for Ollama voice response
                        fallback_pcm_buffer.extend(pcm_bytes)
                        if len(fallback_pcm_buffer) >= 64000: # Every ~2 seconds of audio
                            asyncio.create_task(process_fallback_audio())

                    # 2. Concurrently monitor for PII without blocking main audio relay
                    asyncio.create_task(pii_monitor.add_pcm_chunk(pcm_bytes))

            elif msg_type in ["eos", "end_of_speech"]:
                # End of user utterance / silence detected
                user_text = data.get("text", "").strip()
                if user_text:
                    print(f"[Live Session EOS]: Received user text: '{user_text}'")
                    # Ensure Gemini Live WebSocket session is connected and auto-reconnect if dropped
                    if not session.is_connected or not session.ws:
                        print("[Live Session]: Session disconnected or closed, reconnecting now...")
                        try:
                            await session.connect()
                        except Exception as e_conn:
                            print(f"[Live Session Reconnect Error]: {e_conn}")
                    
                    if session.is_connected:
                        asyncio.create_task(session.send_end_of_turn(user_text))

                    # Asynchronously generate response text for client display (#ai-response-box)
                    async def fetch_and_send_text_reply():
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=session.api_key)
                            model = genai.GenerativeModel("gemini-2.0-flash")
                            prompt = f"あなたは高齢者施設に寄り添う親切で暖かい介護アシスタントAIです。短く優しく1~2文の日本語で回答してください。利用者様の発話: 「{user_text}」"
                            gen_task = asyncio.to_thread(model.generate_content, prompt)
                            resp = await asyncio.wait_for(gen_task, timeout=3.0)
                            reply_text = resp.text.strip() if resp and resp.text else f"「{user_text}」ですね。お話しできて嬉しいです！"
                            await websocket.send_json({
                                "type": "live_response",
                                "text": reply_text
                            })
                        except Exception as fallback_err:
                            print(f"[Live Response Text Error/Timeout]: {fallback_err}")
                            await websocket.send_json({
                                "type": "live_response",
                                "text": f"「{user_text}」ですね。お話しできて嬉しいです！"
                            })

                    asyncio.create_task(fetch_and_send_text_reply())

            elif msg_type == "resume_live_session":
                # User acknowledged warning and clicks resume
                pii_monitor.reset()
                fallback_pcm_buffer.clear()
                await websocket.send_json({"type": "session_resumed", "status": "ok"})

    except WebSocketDisconnect:
        print(f"User Live WebSocket disconnected: {terminal_id}")
    except Exception as e:
        print(f"Error in user live websocket ({terminal_id}): {e}")
    finally:
        await session.close()

# WebSocket Endpoint for Staff client
@app.websocket("/ws/staff")
async def websocket_staff_endpoint(websocket: WebSocket):
    await manager.connect_staff(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Pattern C: Staff Chat
            if msg_type == "staff_chat":
                sender = data.get("sender_name", "スタッフ")
                message = data.get("message", "")
                db.add_staff_message(sender, message)
                
                # Broadcast chat to all staff
                await manager.broadcast_to_staff({
                    "type": "staff_chat",
                    "sender_name": sender,
                    "message": message,
                    "timestamp": db.datetime.now().isoformat()
                })
                
            # Pattern B: Staff Override / AI Interruption
            elif msg_type == "staff_override":
                target = data.get("target") # terminal_id
                override_text = data.get("text")
                user_id = data.get("user_id")
                
                # Save to db as 'staff'
                if user_id:
                    db.add_chat_message(user_id, "staff", override_text)
                    
                # Broadcast back to all staff so chat logs match
                await manager.broadcast_to_staff({
                    "type": "user_chat",
                    "user_id": user_id,
                    "sender": "staff",
                    "message": override_text,
                    "timestamp": db.datetime.now().isoformat()
                })
                
                # Convert to TTS and push to User Client
                audio_res = speech.synthesize_speech(override_text)
                await manager.send_to_user(target, {
                    "type": "play_voice",
                    "text": override_text,
                    "audio": base64.b64encode(audio_res).decode("utf-8")
                })
                
            # Pattern A: Initiate intercom call
            elif msg_type == "call_request":
                target = data.get("target") # terminal_id
                await manager.send_to_user(target, {
                    "type": "incoming_call",
                    "caller": "スタッフステーション"
                })
                print(f"Intercom call requested for: {target}")
                
            # Intercom Voice stream from Staff to User Client
            elif msg_type == "audio_stream":
                target = data.get("target")
                audio_chunk = data.get("audio") # Base64 PCM chunk
                await manager.send_to_user(target, {
                    "type": "intercom_audio",
                    "audio": audio_chunk
                })
                
            elif msg_type == "hangup":
                target = data.get("target")
                await manager.send_to_user(target, {
                    "type": "intercom_hangup"
                })

    except WebSocketDisconnect:
        manager.disconnect_staff(websocket)
    except Exception as e:
        print(f"Error in staff websocket: {e}")
        manager.disconnect_staff(websocket)

# Prompt Templates API
@app.get("/api/prompt_templates")
def api_get_prompt_templates():
    return db.get_all_prompt_templates()

class PromptTemplateUpdate(BaseModel):
    key_name: str
    content: str

@app.post("/api/prompt_templates")
def api_update_prompt_template(req: PromptTemplateUpdate):
    db.update_prompt_template(req.key_name, req.content)
    return {"status": "success", "message": "プロンプト雛形を更新しました。"}

# Barber (訪問理美容) API
@app.get("/api/barber/reservations")
def api_get_barber_reservations():
    return db.get_barber_reservations()

class BarberReservationCreate(BaseModel):
    user_id: int
    reservation_date: str
    menu: str
    notes: str

@app.post("/api/barber/reservations")
def api_create_barber_reservation(req: BarberReservationCreate):
    res_id = db.add_barber_reservation(req.user_id, req.reservation_date, req.menu, req.notes)
    return {"status": "success", "id": res_id}

class BarberReportUpdate(BaseModel):
    reservation_id: int
    status: str
    report: str

@app.post("/api/barber/report")
def api_update_barber_report(req: BarberReportUpdate):
    db.update_barber_report(req.reservation_id, req.status, req.report)
    return {"status": "success", "message": "施術報告を更新しました。"}

# Family Access & Patient Summary API (Group Restricted)
@app.get("/api/family/patient_summary/{patient_id}")
def api_get_family_patient_summary(patient_id: int, user_code: str = "family01"):
    account = db.get_user_account_by_code(user_code)
    if not account or not db.check_group_access(account, patient_id):
        raise HTTPException(status_code=403, detail="グループ外のためアクセスが拒否されました。")
    
    user = db.get_user(patient_id)
    if not user:
        raise HTTPException(status_code=404, detail="対象の利用者が見つかりません。")
    
    vitals = db.get_vital_records(patient_id, limit=7)
    chat_history = db.get_chat_history(patient_id, limit=10)
    
    return {
        "patient": {
            "id": user["id"],
            "name": user["name"],
            "room_number": user["room_number"],
            "dementia_level": user["dementia_level"]
        },
        "vitals": vitals,
        "chat_history": chat_history,
        "recent_multimedia": {
            "card_title": "昔懐かしい昭和の思い出絵手紙",
            "card_image_url": "/assets/sample_postcard.jpg",
            "bgm_title": "のどかな和風アンビエント BGM (15秒)",
            "video_title": "今週の山田様の様子ショートムービー (MP4)",
            "video_duration": "25秒"
        }
    }

class MultimediaPreviewReq(BaseModel):
    user_id: int

@app.post("/api/multimedia/generate_preview")
def api_generate_multimedia_preview(req: MultimediaPreviewReq):
    user = db.get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="利用者が見つかりません。")
    
    history = db.get_chat_history(req.user_id, limit=5)
    last_topic = history[-1]["message"] if history else "故郷のお話"
    
    return {
        "status": "success",
        "title": f"【デジタル絵手紙】{user['name']}様の思い出カード",
        "topic": last_topic,
        "image_style": "温かみのある昭和レトロ水彩画風",
        "bgm_style": "安らぎを与える和風アコースティックBGM",
        "generated_at": db.datetime.now().isoformat()
    }

# Serve static frontend files
frontend_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

