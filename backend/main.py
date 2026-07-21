import os
import json
import base64
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

from backend.config import BASE_DIR, OLLAMA_URL, OLLAMA_MODEL, encrypt_data, decrypt_data
import backend.database as db
import backend.speech as speech
import backend.rag as rag
import backend.vital_parser as vital_parser

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
    dem_desc = dementia_info.get(user["dementia_level"], "")
    
    # Construct System Prompt
    system_prompt = f"""あなたは介護施設の高齢者ケアに特化したAIアシスタントです。
利用者の名前は「{user["name"]}」様です。
利用者の特徴: {dem_desc}
AI対話時の注意点: {user["attention_points"]}
申し送り・特記事項: {user["notes"]}

対話時のルール:
1. 相手の言葉を否定せず、傾聴、共感、受容の姿勢を徹底してください。
2. 認知症の特性を考慮し、優しく温かい口調で（「〜ですね」「〜ですよ」など）、簡潔に話してください。
3. 過去の会話の記憶があれば、それを自然に会話に取り入れてください。
4. 専門用語は使わず、親しみやすい日本語で対話してください。
5. 【重要】毎回の発言の冒頭で相手の名前（「〇〇さん」「〇〇様」など）を絶対に連呼・連用しないでください。自然な相槌から対話を開始してください。

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
        response = requests.post(url, json=payload, timeout=25)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Ollama API query error: {e}")
        return f"{user['name']}さん、お呼びですか？何かお手伝いできることはありますか？"

# WebSocket Endpoint for User client
@app.websocket("/ws/user/{terminal_id}")
async def websocket_user_endpoint(websocket: WebSocket, terminal_id: str):
    await manager.connect_user(terminal_id, websocket)
    
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
            
            # User speaking / inputting text
            if msg_type == "audio_input":
                # Audio base64 string sent from client
                audio_b64 = data.get("audio")
                audio_bytes = base64.b64decode(audio_b64)
                
                # STT
                transcribed_text = speech.transcribe_audio(audio_bytes)
                if not transcribed_text or transcribed_text.strip() == "[音声認識エラー]":
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": "うまく聞き取れませんでした。もう一度お話しいただけますか？",
                        "audio": base64.b64encode(speech.synthesize_speech("うまく聞き取れませんでした。もう一度お話しいただけますか？")).decode("utf-8")
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
                
                # 1. Check if user is reporting vitals
                vitals = vital_parser.extract_vitals_from_text(transcribed_text)
                
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
                    audio_res = speech.synthesize_speech(confirm_text)
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": confirm_text,
                        "audio": base64.b64encode(audio_res).decode("utf-8")
                    })
                    
                else:
                    # 2. General Conversation (Fast Ollama query)
                    history = db.get_chat_history(user_id, limit=6)
                    
                    # Query Gemma for chat reply
                    ai_reply = query_ollama_chat(user, history, transcribed_text, "")
                    
                    # Save AI reply to DB
                    db.add_chat_message(user_id, "ai", ai_reply)
                    
                    # Generate Speech and send back to client IMMEDIATELY for ultra-low latency
                    audio_res = speech.synthesize_speech(ai_reply)
                    await websocket.send_json({
                        "type": "chat_response",
                        "text": ai_reply,
                        "audio": base64.b64encode(audio_res).decode("utf-8")
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

# Serve static frontend files
frontend_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
