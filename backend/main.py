import os
import asyncio
import time
import re
import json
import base64
import urllib.request
import requests
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import urllib.parse
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import backend.config as config
from backend.config import BASE_DIR, OLLAMA_URL, OLLAMA_MODEL, encrypt_data, decrypt_data
import backend.database as db
import backend.speech as speech
import backend.rag as rag
import backend.vital_parser as vital_parser
from backend.gemini_live import GeminiLiveSession, PIIGuardrailMonitor
import backend.multimedia as multimedia

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
    intercom_auto_answer: int = 1
    intercom_auto_delay: int = 10
    allow_force_answer_staff: int = 1
    allow_force_answer_family: int = 0

class UserUpdate(BaseModel):
    name: str
    age: int
    room_number: str
    terminal_id: str
    dementia_level: str
    notes: str = ""
    attention_points: str = ""
    intercom_auto_answer: int = 1
    intercom_auto_delay: int = 10
    allow_force_answer_staff: int = 1
    allow_force_answer_family: int = 0

class HandoverCreate(BaseModel):
    author: str
    content: str

# HTTP Endpoints

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": time.time(),
        "service": "Care-Link Backend",
        "version": "1.0.0"
    }

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
            attention_points=user.attention_points,
            intercom_auto_answer=user.intercom_auto_answer,
            intercom_auto_delay=user.intercom_auto_delay,
            allow_force_answer_staff=user.allow_force_answer_staff,
            allow_force_answer_family=user.allow_force_answer_family
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
            attention_points=user.attention_points,
            intercom_auto_answer=user.intercom_auto_answer,
            intercom_auto_delay=user.intercom_auto_delay,
            allow_force_answer_staff=user.allow_force_answer_staff,
            allow_force_answer_family=user.allow_force_answer_family
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
        # Map: terminal_id -> status ('offline', 'idle', 'chatting', 'intercom')
        self.terminal_statuses: Dict[str, str] = {}
        # List of staff WebSockets
        self.staff_connections: List[WebSocket] = []
        # Map: user_code -> List[WebSocket] for family users
        self.family_connections: Dict[str, List[WebSocket]] = {}
        # Map: terminal_id -> Session info dict:
        # { "caller_type": "staff" | "family", "caller_id": str, "caller_name": str, "is_force": bool, "started_at": float }
        self.active_call_sessions: Dict[str, Dict] = {}

    def get_status(self, terminal_id: str) -> str:
        if terminal_id in self.user_connections:
            return self.terminal_statuses.get(terminal_id, "idle")
        return "offline"

    def get_session(self, terminal_id: str) -> Optional[Dict]:
        return self.active_call_sessions.get(terminal_id)

    def start_session(self, terminal_id: str, caller_type: str, caller_id: str, caller_name: str, is_force: bool = False) -> Dict:
        session = {
            "caller_type": caller_type,
            "caller_id": caller_id,
            "caller_name": caller_name,
            "is_force": is_force,
            "started_at": time.time()
        }
        self.active_call_sessions[terminal_id] = session
        print(f"Call session started for {terminal_id}: {session}")
        return session

    def end_session(self, terminal_id: str):
        if terminal_id in self.active_call_sessions:
            ended = self.active_call_sessions.pop(terminal_id)
            print(f"Call session ended for {terminal_id}: {ended}")

    async def update_status(self, terminal_id: str, status: str):
        self.terminal_statuses[terminal_id] = status
        print(f"Terminal status changed: {terminal_id} -> {status}")
        # Broadcast to all staff
        await self.broadcast_to_staff({
            "type": "user_status",
            "terminal_id": terminal_id,
            "status": status
        })
        # Broadcast to connected family members who monitor this terminal
        await self.broadcast_terminal_status_to_family(terminal_id, status)

    async def connect_user(self, terminal_id: str, websocket: WebSocket):
        await websocket.accept()
        self.user_connections[terminal_id] = websocket
        self.terminal_statuses[terminal_id] = "idle"
        print(f"User Client connected: {terminal_id}")
        await self.broadcast_to_staff({
            "type": "user_status",
            "terminal_id": terminal_id,
            "status": "idle"
        })
        await self.broadcast_terminal_status_to_family(terminal_id, "idle")

    def disconnect_user(self, terminal_id: str):
        if terminal_id in self.user_connections:
            del self.user_connections[terminal_id]
        self.terminal_statuses[terminal_id] = "offline"
        self.end_session(terminal_id)
        print(f"User Client disconnected: {terminal_id}")

    async def connect_staff(self, websocket: WebSocket):
        await websocket.accept()
        self.staff_connections.append(websocket)
        print("Staff Client connected")
        # Send initial full status map of all terminals
        try:
            all_users = db.get_all_users()
            current_statuses = {}
            for u in all_users:
                t_id = u.get("terminal_id")
                if t_id:
                    current_statuses[t_id] = self.get_status(t_id)
            await websocket.send_json({
                "type": "all_terminal_statuses",
                "statuses": current_statuses
            })
        except Exception as e:
            print(f"Failed to send initial statuses to staff: {e}")

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

    async def connect_family(self, user_code: str, websocket: WebSocket):
        await websocket.accept()
        if user_code not in self.family_connections:
            self.family_connections[user_code] = []
        self.family_connections[user_code].append(websocket)
        print(f"Family Client connected: {user_code}")

    def disconnect_family(self, user_code: str, websocket: WebSocket):
        if user_code in self.family_connections:
            if websocket in self.family_connections[user_code]:
                self.family_connections[user_code].remove(websocket)
            if not self.family_connections[user_code]:
                del self.family_connections[user_code]
        print(f"Family Client disconnected: {user_code}")

    async def send_to_family(self, user_code: str, message: dict):
        connections = self.family_connections.get(user_code, [])
        dead_connections = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        for dead in dead_connections:
            self.disconnect_family(user_code, dead)

    async def broadcast_terminal_status_to_family(self, terminal_id: str, status: str):
        # Look up which family accounts monitor this terminal_id
        target_user = db.get_user_by_terminal(terminal_id)
        if not target_user:
            return
        patient_id = target_user.get("id")
        if not patient_id:
            return
        
        # Notify connected family members that have group access to this patient
        for user_code, conns in list(self.family_connections.items()):
            account = db.get_user_account_by_code(user_code)
            if account and db.check_group_access(account, patient_id):
                for ws in conns:
                    try:
                        await ws.send_json({
                            "type": "terminal_status",
                            "terminal_id": terminal_id,
                            "status": status
                        })
                    except Exception:
                        pass

    async def send_to_user(self, terminal_id: str, message: dict):
        websocket = self.user_connections.get(terminal_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_user(terminal_id)

manager = ConnectionManager()

@app.get("/api/terminals/status")
def get_terminal_statuses():
    all_users = db.get_all_users()
    statuses = {}
    for u in all_users:
        t_id = u.get("terminal_id")
        if t_id:
            statuses[t_id] = manager.get_status(t_id)
    return statuses

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

def inspect_safety_with_llm(text: str) -> dict:
    """
    Evaluates speech text for safety using local Ollama LLM (Qwen 2.5:7b).
    Returns structured safety verdict: status (NORMAL, ALERT, EMERGENCY), action, latency, and details.
    """
    if not text or len(text.strip()) < 2:
        return {
            "status": "NORMAL",
            "action": "CONTINUE",
            "model": config.OLLAMA_MODEL,
            "latency": 0.0,
            "summary": "監視中 (待機)",
            "detail": "利用者の発話を待機しています。"
        }

    # Filter out system announcements echoed into microphone
    system_echo_phrases = [
        "個人情報保護のため", "会話を一時停止", "個人情報は話さない",
        "スタッフに連絡する場合は", "ボタンを押してください", "会話が終了します",
        "今後もお会いしましょう", "この動画を", "チャンネル登録", "安心してお待ちください"
    ]
    if any(p in text for p in system_echo_phrases):
        return {
            "status": "NORMAL",
            "action": "CONTINUE",
            "model": config.OLLAMA_MODEL,
            "latency": 0.0,
            "summary": "システム音声エコー無視",
            "detail": "システムアナウンス音声がマイクに入ったため無視しました。"
        }

    # Fast path for testing, operational, and confidential (secret) phrases (zero latency, no LLM false positives)
    test_and_op_phrases = [
        "テスト", "確認します", "操作", "了解", "聞こえますか", "聞こえてますか",
        "終わります", "終了", "ありがとうございました", "おはよう", "こんにちは",
        "内緒の話", "内緒にして", "ここだけの話", "秘密の話", "言わんといて", "記録を止めて", "記録停止", "記録再開"
    ]
    # If the sentence contains test/operational words and NO danger keywords, fast-return NORMAL
    danger_keywords = ["痛い", "苦しい", "倒れ", "助けて", "血", "熱が", "吐き気", "めまい", "呼んで"]
    if any(p in text for p in test_and_op_phrases) and not any(d in text for d in danger_keywords):
        return {
            "status": "NORMAL",
            "stage": 0,
            "action": "CONTINUE",
            "model": "fast_rule",
            "latency": 0.0,
            "summary": "日常/テスト/内緒話会話",
            "detail": "テストまたは日常挨拶・確認・内緒話の前置き発話です。"
        }

    start_t = time.time()
    system_prompt = """あなたは介護施設内の発話安全監視AIです。
利用者の発話内容を客観的・論理的に分析し、以下の基準で厳格に判定してJSON形式で回答してください。

【重要方針】
- 発話内容に直接・具体的に生命の危機や激痛、体調不良、個人情報が含まれていない限り、勝手な想像や過剰な拡大解釈をしてはいけません。
- 「テスト」「確認」「おはよう」「こんにちは」「操作」などのシステム発話や日常雑談は、絶対に EMERGENCY や ALERT にしてはいけません。必ず NORMAL です。

【判定基準】
1. EMERGENCY (生命の危機・急変・重篤):
明確に「胸が痛い」「息ができない」「倒れた」「血が出た」「助けて」などの強い身体的苦痛や急変を発話している場合のみ。
{"status": "EMERGENCY", "stage": 3, "action": "AUTO_EMERGENCY_CALL", "summary": "緊急事態要約", "detail": "理由"}

2. ALERT (中度の体調不良・スタッフ呼出・個人情報漏洩):
- 明確な体調不良（「熱がある」「頭が痛い」「吐き気がする」等）や呼出（「スタッフさん呼んで」等）。
- 利用者が【具体的な】本名・電話番号・住所・暗証番号などの個人情報を喋った場合。
※「個人情報のテスト」「内緒の話」と言っただけで具体的な番号や住所を言っていない場合は漏洩ではありません。NORMALにしてください。
{"status": "ALERT", "stage": 2, "action": "PROMPT_STAFF_CALL", "summary": "警告要約", "detail": "理由"}

3. CAUTION (軽度の不調・ぼやき):
「ちょっと疲れた」「だるい」「食欲がない」などの軽微な不調。
{"status": "CAUTION", "stage": 1, "action": "WARN_ONLY", "summary": "注意要約", "detail": "理由"}

4. NORMAL (日常会話・雑談・テスト発話・無害な発話):
上記に当てはまらない全ての日常会話、テスト発話、挨拶、世間話。
{"status": "NORMAL", "stage": 0, "action": "CONTINUE", "summary": "日常会話", "detail": "健康・安全上の問題なし"}

必ず有効なJSONのみを出力してください。"""

    user_prompt = f"""判定対象の利用者発話:
「{text}」

上記の発話に対するJSON判定:"""

    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 120
        }
    }
    
    try:
        req = urllib.request.Request(
            f"{config.OLLAMA_URL}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_reply = data.get("response", "").strip()
            
        elapsed = time.time() - start_t
        
        # Parse JSON from response
        clean_json = raw_reply
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        verdict = json.loads(clean_json)
        status = verdict.get("status", "NORMAL").upper()
        stage = verdict.get("stage", 0)
        if status == "EMERGENCY":
            stage = 3
        elif status == "ALERT":
            stage = 2
        elif status == "CAUTION":
            stage = 1
        elif status == "NORMAL":
            stage = 0

        res = {
            "status": status,
            "stage": stage,
            "action": verdict.get("action", "CONTINUE"),
            "model": config.OLLAMA_MODEL,
            "latency": round(elapsed, 2),
            "summary": verdict.get("summary", "安全確認済み"),
            "detail": verdict.get("detail", "特段の異常や危険は検知されませんでした。")
        }
        print(f"[inspect_safety_with_llm SUCCESS]: text='{text}', status={res['status']}, stage={res['stage']}, latency={res['latency']}s, summary='{res['summary']}'")
        return res
    except Exception as e:
        print(f"[inspect_safety_with_llm ERROR]: {type(e)}: {e}")
        elapsed = time.time() - start_t
        status = "NORMAL"
        stage = 0
        action = "CONTINUE"
        summary = "安全確認済み"
        detail = "通常の発話内容です。"
        
        emergency_keywords = ["胸が痛", "息ができない", "助けて", "倒れた", "転んだ", "激痛", "血が出た"]
        alert_keywords = ["熱がある", "頭痛がひどい", "吐き気", "めまいがひど", "スタッフを呼", "スタッフさん呼", "看護師さん呼", "看護師呼", "先生呼"]
        pii_keywords = ["口座番号", "電話番号", "マイナンバー", "暗証番号", "盗まれた", "財布"]
        caution_keywords = ["腰が痛", "膝が痛", "少し痛", "だるい", "疲れた", "調子が悪い", "食欲がない", "身体が重い"]
        
        if any(k in text for k in emergency_keywords):
            status = "EMERGENCY"
            stage = 3
            action = "AUTO_EMERGENCY_CALL"
            summary = "【第三段階】生命危機・急変の疑い"
            detail = "胸痛・呼吸困難・激痛などの緊急キーワードを検知しました。"
        elif any(k in text for k in alert_keywords):
            status = "ALERT"
            stage = 2
            action = "PROMPT_STAFF_CALL"
            summary = "【第二段階】中度不調・スタッフ呼出要請"
            detail = "発熱・強い頭痛またはスタッフ呼出要請を検知しました。"
        elif any(k in text for k in pii_keywords):
            status = "ALERT"
            stage = 2
            action = "SUSPEND_PII"
            summary = "【個人情報】個人情報開示の疑い"
            detail = "口座番号・電話番号等の個人情報を検知しました。"
        elif any(k in text for k in caution_keywords):
            status = "CAUTION"
            stage = 1
            action = "WARN_ONLY"
            summary = "【第一段階】軽度の体調変化・違和感"
            detail = "軽度の違和感または疲労に関する発話を検知しました。"
            
        return {
            "status": status,
            "stage": stage,
            "action": action,
            "model": config.OLLAMA_MODEL,
            "latency": round(elapsed, 2),
            "summary": summary,
            "detail": detail
        }

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
5. 【重要指示】あなた自身にはスタッフを呼ぶ機能はありません。「スタッフに連絡します」「スタッフをお呼びします」などの発言は絶対にしないでください。体調不良時は「スタッフに連絡する場合はボタンを押してください」と案内してください。
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
4. 【禁止事項】あなた自身にはスタッフを呼ぶ機能はありません。「スタッフに連絡します」「スタッフをお呼びします」などの発言は絶対にしないでください。体調不良時は「ご無理をなさらず、ナースコール（または画面の呼び出しボタン）を押してくださいね」とだけ案内してください。
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
            
            # Direct terminal state notification (idle, chatting, intercom)
            if msg_type == "status_update":
                new_status = data.get("status", "idle")
                await manager.update_status(terminal_id, new_status)
                continue

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

                            # Run parallel local LLM safety guardrail check
                            async def _run_guardrail_check(txt):
                                g_res = await asyncio.to_thread(inspect_safety_with_llm, txt)
                                await websocket.send_json({
                                    "type": "guardrail_result",
                                    **g_res
                                })
                                if g_res.get("status") in ["CAUTION", "ALERT", "EMERGENCY"]:
                                    await manager.broadcast_to_staff({
                                        "type": "guardrail_alert",
                                        "terminal_id": terminal_id,
                                        "user_name": user.get("name", "未登録"),
                                        "status": g_res["status"],
                                        "stage": g_res.get("stage", 1),
                                        "summary": g_res["summary"],
                                        "detail": g_res["detail"],
                                        "timestamp": db.datetime.now().strftime("%H:%M:%S")
                                    })
                            asyncio.create_task(_run_guardrail_check(clean_text))

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
            
            # Real-time Audio Stream from User to Caller (Staff or Family Intercom)
            elif msg_type == "audio_stream":
                audio_chunk = data.get("audio") # Base64 string
                session = manager.get_session(terminal_id)
                if session and session.get("caller_type") == "family":
                    await manager.send_to_family(session.get("caller_id"), {
                        "type": "intercom_audio",
                        "source": terminal_id,
                        "audio": audio_chunk
                    })
                else:
                    await manager.broadcast_to_staff({
                        "type": "intercom_audio",
                        "source": terminal_id,
                        "audio": audio_chunk
                    })
                
            elif msg_type == "call_answer":
                session = manager.get_session(terminal_id)
                if session:
                    session["answered"] = True
                    caller_type = session.get("caller_type")
                    caller_id = session.get("caller_id")
                    if caller_type == "family":
                        await manager.send_to_family(caller_id, {
                            "type": "call_answered",
                            "target": terminal_id
                        })
                    else:
                        await manager.broadcast_to_staff({
                            "type": "call_answered",
                            "target": terminal_id
                        })
                    print(f"Intercom call answered by {terminal_id} for {caller_type}:{caller_id}")

            elif msg_type == "hangup":
                session = manager.get_session(terminal_id)
                await manager.update_status(terminal_id, "idle")
                if session and session.get("caller_type") == "family":
                    await manager.send_to_family(session.get("caller_id"), {
                        "type": "intercom_hangup",
                        "source": terminal_id
                    })
                else:
                    await manager.broadcast_to_staff({
                        "type": "intercom_hangup",
                        "source": terminal_id
                    })
                manager.end_session(terminal_id)

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
            # Save Gemini message to database only if recording is active and not an internal command
            if session.recording_active and not text.startswith("みまもりさんへ業務連絡"):
                db.add_chat_message(user["id"], "ai", text)
        except Exception as e:
            print(f"Error sending live text to client ({terminal_id}): {e}")

    async def on_live_recording_status(active: bool, msg: str):
        try:
            await websocket.send_json({
                "type": "recording_status",
                "active": active,
                "message": msg
            })
        except Exception as e:
            print(f"Error sending recording status ({terminal_id}): {e}")

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
    def on_gemini_thought(thought: str):
        asyncio.create_task(websocket.send_json({
            "type": "gemini_thinking",
            "thought": thought
        }))

    session = GeminiLiveSession(
        user=user,
        on_audio_received=lambda audio: asyncio.create_task(on_gemini_audio(audio)),
        on_error=on_gemini_error,
        on_text_received=lambda txt: asyncio.create_task(on_gemini_text(txt)),
        on_thought_received=on_gemini_thought,
        on_recording_status_changed=lambda active, msg: asyncio.create_task(on_live_recording_status(active, msg)),
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

    async def _run_live_guardrail(text_to_check: str):
        if not text_to_check:
            return
        res = await asyncio.to_thread(inspect_safety_with_llm, text_to_check)
        status = res.get("status", "NORMAL")
        summary = res.get("summary", "")
        detail = res.get("detail", "")
        print(f"[Live Guardrail Verdict] ({terminal_id}): text='{text_to_check}', status={status}, summary='{summary}', latency={res.get('latency')}s")
        
        # 1. Send guardrail result to user client
        await websocket.send_json({
            "type": "guardrail_result",
            **res
        })

        # 2. Check for personal information (PII)
        # Exclude confidential/privacy mode requests from being treated as PII violations
        is_confidential_request = any(k in text_to_check for k in ["ここだけの話", "内緒", "言わんといて", "言わないで", "記録を止めて", "記録止めて", "秘密", "メモせんといて"])
        is_pii = (status == "ALERT") and not is_confidential_request and any(k in summary or k in detail for k in ["個人情報", "口座", "住所", "電話", "名前", "氏名"])
        if is_pii:
            print(f"[LIVE PII GUARDRAIL TRIGGERED BY LLM] ({terminal_id}): {summary} - {detail}")
            # Immediately mute Gemini audio
            if session.is_connected:
                asyncio.create_task(session.send_interruption())
            # Notify user client to halt playback and show PII warning UI / audio
            await websocket.send_json({
                "type": "pii_warning",
                "category": "llm_pii",
                "message": "個人情報保護のため会話を一時停止しました。個人情報は話さないようお願いいたします。"
            })
            # Broadcast real-time PII Alert to Staff Dashboard
            await manager.broadcast_to_staff({
                "type": "pii_alert",
                "terminal_id": terminal_id,
                "user_name": user.get("name", "未登録"),
                "room_number": user.get("room_number", "-"),
                "category": "personal_info",
                "detail": f"{summary} ({detail})",
                "timestamp": db.datetime.now().strftime("%H:%M:%S")
            })
            return

        # 3. Handle 3 stages of anomaly detection
        if status in ["CAUTION", "ALERT", "EMERGENCY"]:
            if status == "EMERGENCY" and session.is_connected:
                asyncio.create_task(session.send_interruption())
            await manager.broadcast_to_staff({
                "type": "guardrail_alert",
                "terminal_id": terminal_id,
                "user_name": user.get("name", "未登録"),
                "status": status,
                "stage": res.get("stage", 1 if status == "CAUTION" else (2 if status == "ALERT" else 3)),
                "summary": summary,
                "detail": detail,
                "timestamp": db.datetime.now().strftime("%H:%M:%S")
            })

    def on_live_transcription(transcribed_text: str):
        if not transcribed_text:
            return
        # 1. Send transcribed speech to user UI
        asyncio.create_task(websocket.send_json({
            "type": "transcription_result",
            "text": transcribed_text
        }))

        # 2. Check for confidential recording stop / resume triggers directly from Whisper STT
        confidential_stop_words = ["ここだけの話", "内緒", "言わんといて", "言わないで", "記録を止めて", "記録止めて", "秘密", "メモせんといて", "誰にも言わないで"]
        confidential_resume_words = ["記録再開", "記録を再開", "内緒話はおしまい", "秘密はおしまい", "通常の会話に戻", "普通の会話に戻"]

        if any(w in transcribed_text for w in confidential_stop_words):
            print(f"[Whisper Confidential Mode]: Recording pause triggered by Whisper: '{transcribed_text}'")
            session.recording_active = False
            asyncio.create_task(on_live_recording_status(False, "会話記録停止"))
        elif any(w in transcribed_text for w in confidential_resume_words):
            print(f"[Whisper Confidential Mode]: Recording resume triggered by Whisper: '{transcribed_text}'")
            session.recording_active = True
            asyncio.create_task(on_live_recording_status(True, "会話記録再開"))

        # 3. Run local LLM safety guardrail inspection in background
        asyncio.create_task(_run_live_guardrail(transcribed_text))

    # Initialize Parallel PII Guardrail Monitor
    pii_monitor = PIIGuardrailMonitor(
        user=user,
        on_pii_detected=on_pii_detected,
        on_transcription=on_live_transcription
    )

    try:
        # Send initial idle guardrail state to client UI
        await websocket.send_json({
            "type": "guardrail_result",
            "status": "NORMAL",
            "action": "CONTINUE",
            "model": config.OLLAMA_MODEL,
            "latency": 0.0,
            "summary": "監視中 (安全)",
            "detail": "発話のプライバシーと生命安全をローカルGPUで常時監視しています。"
        })

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
                    # 1. Ensure Gemini Live WebSocket session is active and relay PCM
                    if not session.is_connected:
                        await session.ensure_connected()
                    if session.is_connected:
                        await session.send_audio_chunk(pcm_bytes)

                    # 2. Synchronously update PII buffer without task creation overhead
                    pii_monitor.add_pcm_chunk_sync(pcm_bytes)

            elif msg_type in ["eos", "end_of_speech"]:
                # End of user utterance / silence detected
                user_text = data.get("text", "").strip()
                await websocket.send_json({"type": "gemini_thinking"})

                if user_text:
                    print(f"[Live Session EOS]: Received user text: '{user_text}'")
                    # Check for confidential / secret conversation recording pause triggers
                    if any(w in user_text for w in ["ここだけの話", "内緒", "言わんといて", "言わないで", "記録を止めて", "記録止めて", "秘密", "メモせんといて", "誰にも言わないで"]):
                        print(f"[Live Session Confidential Mode]: User initiated recording pause: '{user_text}'")
                        session.recording_active = False
                        await websocket.send_json({
                            "type": "recording_status",
                            "active": False,
                            "message": "会話記録停止"
                        })
                    elif any(w in user_text for w in ["記録再開", "記録を再開", "内緒話はおしまい", "秘密はおしまい", "普通の会話に戻"]):
                        print(f"[Live Session Confidential Mode]: User initiated recording resume: '{user_text}'")
                        session.recording_active = True
                        await websocket.send_json({
                            "type": "recording_status",
                            "active": True,
                            "message": "会話記録再開"
                        })

                    # Save user message to database only if recording is active
                    if session.recording_active:
                        db.add_chat_message(user["id"], "user", user_text)

                    # Inspect user text concurrently with local LLM for instant guardrail response
                    asyncio.create_task(_run_live_guardrail(user_text))

                # Ensure Gemini Live WebSocket session is connected and auto-reconnect if dropped
                if not session.is_connected or not session.ws:
                    print("[Live Session]: Session disconnected or closed, reconnecting now...")
                    try:
                        await session.connect()
                    except Exception as e_conn:
                        print(f"[Live Session Reconnect Error]: {e_conn}")
                
                if session.is_connected:
                    asyncio.create_task(session.send_end_of_turn(user_text))

            elif msg_type == "resume_recording":
                session.recording_active = True
                await websocket.send_json({
                    "type": "recording_status",
                    "active": True,
                    "message": "会話記録再開"
                })

            elif msg_type == "stop_recording":
                session.recording_active = False
                await websocket.send_json({
                    "type": "recording_status",
                    "active": False,
                    "message": "会話記録停止"
                })

            elif msg_type == "resume_live_session":
                # User acknowledged warning and clicks resume
                pii_monitor.reset()
                await websocket.send_json({"type": "session_resumed", "status": "ok"})

            elif msg_type == "user_emergency_call":
                reason = data.get("reason", "利用者様が画面のスタッフ連絡ボタンを押しました")
                print(f"[EMERGENCY CALL DISPATCHED] ({terminal_id}): {reason}")
                await manager.broadcast_to_staff({
                    "type": "nurse_call",
                    "terminal_id": terminal_id,
                    "user_name": user.get("name", "未登録"),
                    "room_number": user.get("room_number", "-"),
                    "reason": reason,
                    "timestamp": db.datetime.now().strftime("%H:%M:%S")
                })

    except WebSocketDisconnect:
        print(f"User Live WebSocket disconnected: {terminal_id}")
    except Exception as e:
        print(f"Error in user live websocket ({terminal_id}): {e}")
    finally:
        await session.close()
        # Automatically extract and save image generation prompt JSON from conversation in background
        try:
            if user and "id" in user:
                asyncio.create_task(
                    asyncio.to_thread(
                        multimedia.extract_image_prompt_from_conversation,
                        user["id"],
                        terminal_id
                    )
                )
        except Exception as e_bg:
            print(f"[Auto Image Prompt Extraction Error]: {e_bg}")

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
                force_mode = data.get("force", False)
                # Lookup target user's intercom settings
                target_user = db.get_user_by_terminal(target)
                auto_answer = target_user.get("intercom_auto_answer", 1) if target_user else 1
                auto_delay = target_user.get("intercom_auto_delay", 2) if target_user else 2
                allow_force = target_user.get("allow_force_answer_staff", 1) if target_user else 1

                # Staff Priority Over Family Call: Check if currently talking to family
                current_session = manager.get_session(target)
                if current_session and current_session.get("caller_type") == "family":
                    family_user_code = current_session.get("caller_id")
                    print(f"[Staff Priority] Interrupting family call on {target} by user {family_user_code}")
                    if family_user_code:
                        await manager.send_to_family(family_user_code, {
                            "type": "call_interrupted",
                            "reason": "staff_priority",
                            "message": "施設スタッフからの緊急呼出・対応のため、通話が切り替わりました。"
                        })

                # Register staff session
                manager.start_session(
                    target,
                    caller_type="staff",
                    caller_id="staff",
                    caller_name="スタッフステーション",
                    is_force=bool(force_mode and allow_force)
                )

                await manager.send_to_user(target, {
                    "type": "incoming_call",
                    "caller": "スタッフステーション",
                    "caller_type": "staff",
                    "auto_answer": bool(auto_answer),
                    "auto_delay": int(auto_delay),
                    "force_mode": bool(force_mode and allow_force)
                })
                await manager.update_status(target, "intercom")
                print(f"Intercom call requested for: {target} (auto_answer={auto_answer}, auto_delay={auto_delay}s, force={bool(force_mode and allow_force)})")
                
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
                if target:
                    manager.end_session(target)
                    await manager.update_status(target, "idle")
                await manager.send_to_user(target, {
                    "type": "intercom_hangup"
                })

    except WebSocketDisconnect:
        manager.disconnect_staff(websocket)
    except Exception as e:
        print(f"Error in staff websocket: {e}")
        manager.disconnect_staff(websocket)

# WebSocket Endpoint for Family client (Intercom & Status Monitoring)
@app.websocket("/ws/family/{user_code}")
async def websocket_family_endpoint(websocket: WebSocket, user_code: str):
    account = db.get_user_account_by_code(user_code)
    if not account:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "ご家族アカウントが見つかりません。"})
        await websocket.close()
        return

    group_id = account.get("group_id")
    group = db.get_group(group_id) if group_id else None
    if not group or not group.get("patient_id"):
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "見守り対象の利用者が設定されていません。"})
        await websocket.close()
        return

    patient_id = group["patient_id"]
    patient = db.get_user(patient_id)
    terminal_id = patient.get("terminal_id") if patient else None

    await manager.connect_family(user_code, websocket)

    # Send initial terminal status to this family client
    if terminal_id:
        current_st = manager.get_status(terminal_id)
        await websocket.send_json({
            "type": "terminal_status",
            "terminal_id": terminal_id,
            "status": current_st
        })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "call_request":
                target = data.get("target") or terminal_id
                force_mode = data.get("force", False)

                # Validate group access
                target_user = db.get_user_by_terminal(target)
                if not target_user or not db.check_group_access(account, target_user["id"]):
                    await websocket.send_json({
                        "type": "call_error",
                        "message": "グループ外の利用者端末への発信はできません。"
                    })
                    continue

                # Check if terminal is offline
                if manager.get_status(target) == "offline":
                    await websocket.send_json({
                        "type": "call_error",
                        "message": "対象の居室端末は現在オフライン（未接続）です。"
                    })
                    continue

                # Busy / Arbitration Check
                existing_session = manager.get_session(target)
                if existing_session:
                    if existing_session.get("caller_type") == "staff":
                        await websocket.send_json({
                            "type": "call_rejected",
                            "reason": "busy_staff",
                            "message": "現在、施設スタッフが対応中です（通話中）。"
                        })
                        continue
                    elif existing_session.get("caller_type") == "family":
                        await websocket.send_json({
                            "type": "call_rejected",
                            "reason": "busy_family",
                            "message": "現在、他のご家族とお話し中です。"
                        })
                        continue

                # Check force call permissions
                allow_force = target_user.get("allow_force_answer_family", 0) == 1
                auto_answer = target_user.get("intercom_auto_answer", 1)
                auto_delay = target_user.get("intercom_auto_delay", 2)

                caller_name = account.get("name", "ご家族様")

                # Register active family session
                manager.start_session(
                    target,
                    caller_type="family",
                    caller_id=user_code,
                    caller_name=caller_name,
                    is_force=bool(force_mode and allow_force)
                )

                # Send incoming call to User terminal
                await manager.send_to_user(target, {
                    "type": "incoming_call",
                    "caller": f"ご家族（{caller_name}）",
                    "caller_type": "family",
                    "auto_answer": bool(auto_answer),
                    "auto_delay": int(auto_delay),
                    "force_mode": bool(force_mode and allow_force)
                })

                await manager.update_status(target, "intercom")
                await websocket.send_json({
                    "type": "call_ringing",
                    "target": target,
                    "auto_delay": int(auto_delay)
                })
                if bool(force_mode and allow_force):
                    await websocket.send_json({
                        "type": "call_answered",
                        "target": target
                    })
                print(f"Family intercom call requested for: {target} by {user_code} (ringing)")

            elif msg_type == "audio_stream":
                target = data.get("target") or terminal_id
                audio_chunk = data.get("audio")
                session = manager.get_session(target)
                if session and session.get("caller_id") == user_code:
                    await manager.send_to_user(target, {
                        "type": "intercom_audio",
                        "audio": audio_chunk
                    })

            elif msg_type == "hangup":
                target = data.get("target") or terminal_id
                session = manager.get_session(target)
                if session and session.get("caller_id") == user_code:
                    manager.end_session(target)
                    await manager.update_status(target, "idle")
                    await manager.send_to_user(target, {
                        "type": "intercom_hangup"
                    })
                await websocket.send_json({
                    "type": "call_ended",
                    "target": target
                })

    except WebSocketDisconnect:
        manager.disconnect_family(user_code, websocket)
        if terminal_id:
            sess = manager.get_session(terminal_id)
            if sess and sess.get("caller_id") == user_code:
                manager.end_session(terminal_id)
                await manager.update_status(terminal_id, "idle")
                await manager.send_to_user(terminal_id, {
                    "type": "intercom_hangup"
                })
    except Exception as e:
        print(f"Error in family websocket ({user_code}): {e}")
        manager.disconnect_family(user_code, websocket)

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
class VisitationReservationReq(BaseModel):
    patient_id: int
    user_code: str
    visit_datetime: str
    visitors_count: int = 1
    message: str = ""

class EncryptedSyncReq(BaseModel):
    user_code: str
    nonce_b64: str
    ciphertext_b64: str

def _get_family_shared_key(user_code: str) -> bytes:
    """Derive 256-bit AES key for family remote packet sync from user_code and facility secret."""
    key_material = f"care_link_facility_key_{user_code}".encode()
    return hashlib.sha256(key_material).digest()

@app.get("/api/family/my_patient")
def api_get_family_my_patient(user_code: str = "family01", season: Optional[str] = None):
    """Get resident data exclusively for the authenticated family account's group."""
    account = db.get_user_account_by_code(user_code)
    if not account:
        raise HTTPException(status_code=401, detail="ご家族アカウントが見つかりません。")
    if account.get("role") != "family" and account.get("role") != "staff":
        raise HTTPException(status_code=403, detail="ご家族権限が必要です。")
    
    group_id = account.get("group_id")
    if not group_id:
        raise HTTPException(status_code=404, detail="紐付けられているグループがありません。")
    
    group = db.get_group(group_id)
    if not group or not group.get("patient_id"):
        raise HTTPException(status_code=404, detail="グループに対象の利用者が見つかりません。")
    
    patient_id = group["patient_id"]
    user = db.get_user(patient_id)
    if not user:
        raise HTTPException(status_code=404, detail="対象の利用者が見つかりません。")
    
    # Fetch recent vitals (up to 14 records for trend charting)
    vitals = db.get_vital_records(patient_id, limit=14)
    # Reverse to chronological order for charts
    vitals_chronological = list(reversed(vitals))
    
    # Chat history for episode generation
    chat_history = db.get_chat_history(patient_id, limit=10)
    
    # Derive recent mood from chat history or vitals
    recent_mood = "穏やか"
    if chat_history:
        recent_text = " ".join([c["message"] for c in chat_history[-3:]])
        if any(w in recent_text for w in ["ありがとう", "うれしい", "楽しい", "元気", "おいしい"]):
            recent_mood = "とても元気・笑顔"
        elif any(w in recent_text for w in ["痛い", "つらい", "帰りたい", "寂しい"]):
            recent_mood = "少し不安・スタッフが見守り中"
    
    # Calculate latest vital status
    latest_vital = vitals[0] if vitals else None
    vital_status = "stable"
    if latest_vital:
        if (latest_vital.get("temperature") and latest_vital["temperature"] >= 37.5) or \
           (latest_vital.get("bp_sys") and latest_vital["bp_sys"] >= 150):
            vital_status = "caution"
    
    multimedia_payload = multimedia.generate_multimedia_payload(
        user["name"],
        chat_history,
        season_key=season,
        terminal_id=user.get("terminal_id"),
        user_id=user.get("id")
    )

    return {
        "status": "success",
        "family_user": {
            "name": account["name"],
            "user_code": account["user_code"],
            "group_name": group.get("group_name", "ご家族グループ")
        },
        "patient": {
            "id": user["id"],
            "name": user["name"],
            "age": user["age"],
            "room_number": user["room_number"],
            "dementia_level": user["dementia_level"],
            "terminal_id": user.get("terminal_id"),
            "intercom_auto_answer": user.get("intercom_auto_answer", 1),
            "intercom_auto_delay": user.get("intercom_auto_delay", 2),
            "allow_force_answer_family": user.get("allow_force_answer_family", 0)
        },
        "vital_status": vital_status,
        "recent_mood": recent_mood,
        "latest_vital": latest_vital,
        "vitals": vitals,
        "vitals_chronological": vitals_chronological,
        "chat_history": chat_history,
        "recent_multimedia": multimedia_payload
    }

@app.get("/api/family/patient_summary/{patient_id}")
def api_get_family_patient_summary(patient_id: int, user_code: str = "family01", season: Optional[str] = None):
    account = db.get_user_account_by_code(user_code)
    if not account or not db.check_group_access(account, patient_id):
        raise HTTPException(status_code=403, detail="グループ外のためアクセスが拒否されました。")
    
    user = db.get_user(patient_id)
    if not user:
        raise HTTPException(status_code=404, detail="対象の利用者が見つかりません。")
    
    vitals = db.get_vital_records(patient_id, limit=7)
    chat_history = db.get_chat_history(patient_id, limit=10)
    multimedia_payload = multimedia.generate_multimedia_payload(
        user["name"],
        chat_history,
        season_key=season,
        terminal_id=user.get("terminal_id"),
        user_id=user.get("id")
    )
    
    return {
        "patient": {
            "id": user["id"],
            "name": user["name"],
            "room_number": user["room_number"],
            "dementia_level": user["dementia_level"]
        },
        "vitals": vitals,
        "chat_history": chat_history,
        "recent_multimedia": multimedia_payload
    }

@app.get("/api/family/postcard_templates")
def api_get_family_postcard_templates():
    """Get all seasonal postcard templates for frontend interactive switching."""
    return {"status": "success", "templates": multimedia.get_all_templates()}

@app.get("/api/family/multimedia/image_prompt/{terminal_id}")
def api_get_image_prompt(terminal_id: str):
    """
    Retrieves the latest structured image generation JSON and postcard metadata
    extracted from the resident's conversation history.
    """
    record = db.get_latest_image_prompt_payload(terminal_id=terminal_id)
    if not record:
        user = db.get_user_by_terminal(terminal_id)
        if not user:
            raise HTTPException(status_code=404, detail="端末が見つかりません。")
        # Extract on the fly if not yet cached
        payload = multimedia.extract_image_prompt_from_conversation(user["id"], terminal_id)
        return {"status": "success", "data": payload}
    return {"status": "success", "data": record.get("payload", {})}

@app.post("/api/family/multimedia/extract_image_prompt/{terminal_id}")
def api_extract_image_prompt(terminal_id: str):
    """
    Forces immediate extraction of image generation JSON from conversation history.
    """
    user = db.get_user_by_terminal(terminal_id)
    if not user:
        raise HTTPException(status_code=404, detail="端末が見つかりません。")
    payload = multimedia.extract_image_prompt_from_conversation(user["id"], terminal_id)
    return {"status": "success", "message": "画像生成用JSONの抽出・保存が完了しました。", "data": payload}

@app.get("/api/family/reservations")
def api_get_family_reservations(user_code: str = "family01"):
    """Get visitation reservations for the authenticated family user."""
    account = db.get_user_account_by_code(user_code)
    if not account:
        raise HTTPException(status_code=401, detail="認証情報が無効です。")
    
    if account.get("role") == "family":
        group_id = account.get("group_id")
        if not group_id:
            return []
        group = db.get_group(group_id)
        if not group or not group.get("patient_id"):
            return []
        patient_id = group["patient_id"]
        return db.get_visitation_reservations(user_id=patient_id)
    elif account.get("role") in ["staff", "barber"]:
        return db.get_visitation_reservations()
    else:
        raise HTTPException(status_code=403, detail="アクセス権限がありません。")

@app.post("/api/family/reservations")
def api_create_visitation_reservation(req: VisitationReservationReq):
    """Create a new visitation reservation with group permission validation."""
    account = db.get_user_account_by_code(req.user_code)
    if not account:
        raise HTTPException(status_code=401, detail="アカウントが見つかりません。")
    
    if not db.check_group_access(account, req.patient_id):
        raise HTTPException(status_code=403, detail="指定の利用者の予約権限がありません。")
    
    res_id = db.create_visitation_reservation(
        user_id=req.patient_id,
        family_user_code=req.user_code,
        visit_datetime=req.visit_datetime,
        visitors_count=req.visitors_count,
        message=req.message
    )
    
    # Broadcast or log reservation for staff
    return {
        "status": "success",
        "reservation_id": res_id,
        "message": "面会予約を正常に受け付けました。施設スタッフが確認後、Googleカレンダーに自動連携されます。"
    }

@app.post("/api/family/sync_encrypted")
def api_family_encrypted_sync(req: EncryptedSyncReq):
    """
    AES-256-GCM Remote Packet Sync Engine (SRS Section 2.2 #8).
    Decrypts client payload, gathers latest summary securely, and encrypts response with AES-256-GCM.
    """
    account = db.get_user_account_by_code(req.user_code)
    if not account:
        raise HTTPException(status_code=401, detail="認証エラー")
    
    key = _get_family_shared_key(req.user_code)
    aesgcm = AESGCM(key)
    
    try:
        nonce = base64.b64decode(req.nonce_b64)
        ciphertext = base64.b64decode(req.ciphertext_b64)
        decrypted_raw = aesgcm.decrypt(nonce, ciphertext, None)
        client_data = json.loads(decrypted_raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AES-256-GCM 復号化に失敗しました: {str(e)}")
    
    # Fetch summary data for response
    patient_id = client_data.get("patient_id")
    if not patient_id or not db.check_group_access(account, patient_id):
        raise HTTPException(status_code=403, detail="グループアクセス拒否")
    
    summary = api_get_family_patient_summary(patient_id, req.user_code)
    response_bytes = json.dumps(summary, ensure_ascii=False).encode("utf-8")
    
    # Encrypt response with fresh 12-byte nonce
    resp_nonce = os.urandom(12)
    resp_ciphertext = aesgcm.encrypt(resp_nonce, response_bytes, None)
    
    return {
        "status": "success",
        "algorithm": "AES-256-GCM",
        "resp_nonce_b64": base64.b64encode(resp_nonce).decode("utf-8"),
        "resp_ciphertext_b64": base64.b64encode(resp_ciphertext).decode("utf-8")
    }

@app.post("/api/family/download_postcard")
async def api_download_postcard(request: Request):
    """
    Client-synthesized Postcard Canvas binary download with standard Content-Disposition attachment.
    Bypasses modern browser automatic-download blocking via hidden iframe POST form submission.
    """
    try:
        form_data = await request.form()
        image_data = form_data.get("image_data", "")
        filename = form_data.get("filename", "care_link_postcard.jpg")
        
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        
        # 安全なBase64パディング補正
        missing_padding = len(image_data) % 4
        if missing_padding:
            image_data += '=' * (4 - missing_padding)
        
        img_bytes = base64.b64decode(image_data)
        encoded_filename = urllib.parse.quote(filename)
        headers = {
            "Content-Disposition": f"attachment; filename=\"postcard.jpg\"; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "image/jpeg",
            "Cache-Control": "no-cache"
        }
        return Response(content=img_bytes, media_type="image/jpeg", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ダウンロード処理に失敗しました: {str(e)}")

@app.get("/api/family/download_raw_postcard")
def api_download_raw_postcard(image_url: str, filename: str = "care_link_postcard.jpg"):
    """
    Direct raw image download with Content-Disposition attachment.
    """
    project_root = os.path.dirname(BASE_DIR)
    clean_path = image_url.lstrip("/")
    if clean_path.startswith("family/"):
        file_path = os.path.join(project_root, "frontend", clean_path)
    else:
        file_path = os.path.join(project_root, "frontend", "family", clean_path)
    
    if not os.path.exists(file_path):
        # Fallback search inside frontend/family/assets
        basename = os.path.basename(image_url)
        file_path = os.path.join(project_root, "frontend", "family", "assets", basename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"画像ファイルが見つかりません: {file_path}")
    
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    
    encoded_filename = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"postcard.jpg\"; filename*=UTF-8''{encoded_filename}",
        "Content-Type": "image/jpeg",
        "Cache-Control": "no-cache"
    }
    return Response(content=img_bytes, media_type="image/jpeg", headers=headers)

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

# Serve static frontend files with cache-busting headers
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

frontend_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", NoCacheStaticFiles(directory=frontend_dir, html=True), name="frontend")

