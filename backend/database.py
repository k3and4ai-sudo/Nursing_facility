import sqlite3
import json
import numpy as np
from datetime import datetime
from backend.config import DB_PATH, encrypt_data, decrypt_data

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    """Initializes the database schema if tables do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Users (Patients) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,                -- Encrypted
                age INTEGER,
                room_number TEXT,
                terminal_id TEXT UNIQUE,           -- Used for 1-to-1 client binding
                dementia_level TEXT,               -- e.g., 'none', 'mild', 'moderate', 'severe'
                notes TEXT,                        -- Encrypted
                attention_points TEXT              -- Encrypted (AI interaction notes)
            )
        """)
        
        # 2. Vital Records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vital_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                temperature REAL,
                weight REAL,
                bp_sys INTEGER,
                bp_dia INTEGER,
                raw_text TEXT,                     -- Encrypted
                is_alert INTEGER DEFAULT 0,
                alert_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # 3. Chat History table (short-term & interface history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                sender TEXT NOT NULL,              -- 'user', 'ai', 'staff'
                message TEXT NOT NULL,             -- Encrypted
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # 4. Long-term Memory Embeddings table (RAG)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                text_chunk TEXT NOT NULL,          -- Encrypted
                embedding TEXT NOT NULL,           -- JSON array of floats
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # 5. Staff Messages (Chat room) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                message TEXT NOT NULL              -- Encrypted
            )
        """)
        
        # 6. Handover Notes (申し送り) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS handover_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL              -- Encrypted
            )
        """)
        
        conn.commit()

# User Management Functions
def add_user(name: str, age: int, room_number: str, terminal_id: str, dementia_level: str, notes: str, attention_points: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO users (name, age, room_number, terminal_id, dementia_level, notes, attention_points) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                encrypt_data(notes), encrypt_data(attention_points)
            )
        )
        conn.commit()
        return cursor.lastrowid

def update_user(user_id: int, name: str, age: int, room_number: str, terminal_id: str, dementia_level: str, notes: str, attention_points: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users 
               SET name = ?, age = ?, room_number = ?, terminal_id = ?, dementia_level = ?, notes = ?, attention_points = ?
               WHERE id = ?""",
            (
                encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                encrypt_data(notes), encrypt_data(attention_points), user_id
            )
        )
        conn.commit()

def get_user(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["name"] = decrypt_data(data["name"])
            data["notes"] = decrypt_data(data["notes"])
            data["attention_points"] = decrypt_data(data["attention_points"])
            return data
    return None

def get_user_by_terminal(terminal_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE terminal_id = ?", (terminal_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["name"] = decrypt_data(data["name"])
            data["notes"] = decrypt_data(data["notes"])
            data["attention_points"] = decrypt_data(data["attention_points"])
            return data
    return None

def get_all_users():
    users = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        for row in cursor.fetchall():
            data = dict(row)
            data["name"] = decrypt_data(data["name"])
            data["notes"] = decrypt_data(data["notes"])
            data["attention_points"] = decrypt_data(data["attention_points"])
            users.append(data)
    return users

def delete_user(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

# Vital Records Functions
def add_vital_record(user_id: int, temperature: float, weight: float, bp_sys: int, bp_dia: int, raw_text: str, is_alert: int, alert_reason: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            """INSERT INTO vital_records (user_id, timestamp, temperature, weight, bp_sys, bp_dia, raw_text, is_alert, alert_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, timestamp, temperature, weight, bp_sys, bp_dia, encrypt_data(raw_text), is_alert, alert_reason)
        )
        conn.commit()
        return cursor.lastrowid

def get_vital_records(user_id: int, limit: int = 100):
    records = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM vital_records WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", 
            (user_id, limit)
        )
        for row in cursor.fetchall():
            data = dict(row)
            data["raw_text"] = decrypt_data(data["raw_text"])
            records.append(data)
    return records

def get_all_recent_vitals(limit: int = 100):
    records = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT v.*, u.name as user_name, u.room_number 
               FROM vital_records v 
               JOIN users u ON v.user_id = u.id 
               ORDER BY v.timestamp DESC LIMIT ?""", 
            (limit,)
        )
        for row in cursor.fetchall():
            data = dict(row)
            data["user_name"] = decrypt_data(data["user_name"])
            data["raw_text"] = decrypt_data(data["raw_text"])
            records.append(data)
    return records

# Chat History Functions
def add_chat_message(user_id: int, sender: str, message: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
            (user_id, timestamp, sender, encrypt_data(message))
        )
        conn.commit()
        return cursor.lastrowid

def get_chat_history(user_id: int, limit: int = 50):
    history = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        for row in cursor.fetchall():
            data = dict(row)
            data["message"] = decrypt_data(data["message"])
            history.append(data)
    # Return in chronological order
    return history[::-1]

# Long-term Memory / RAG Functions
def add_memory(user_id: int, text_chunk: str, embedding_vector: list):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO memories (user_id, timestamp, text_chunk, embedding) VALUES (?, ?, ?, ?)",
            (user_id, timestamp, encrypt_data(text_chunk), json.dumps(embedding_vector))
        )
        conn.commit()

def search_memories(user_id: int, query_vector: list, limit: int = 3):
    """Calculates cosine similarity in python to find relevant past memories."""
    memories = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        
    if not rows or not query_vector:
        return []
        
    q_vec = np.array(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return []

    scored_memories = []
    for row in rows:
        text_chunk = decrypt_data(row["text_chunk"])
        try:
            emb_vec = np.array(json.loads(row["embedding"]), dtype=np.float32)
            emb_norm = np.linalg.norm(emb_vec)
            if emb_norm == 0:
                continue
            similarity = float(np.dot(q_vec, emb_vec) / (q_norm * emb_norm))
            scored_memories.append((similarity, text_chunk))
        except Exception:
            continue
            
    # Sort by similarity descending
    scored_memories.sort(key=lambda x: x[0], reverse=True)
    return [text for score, text in scored_memories[:limit] if score > 0.35]

# Staff Chat / Handover Functions
def add_staff_message(sender_name: str, message: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO staff_messages (timestamp, sender_name, message) VALUES (?, ?, ?)",
            (timestamp, sender_name, encrypt_data(message))
        )
        conn.commit()

def get_staff_messages(limit: int = 100):
    messages = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staff_messages ORDER BY timestamp DESC LIMIT ?", (limit,))
        for row in cursor.fetchall():
            data = dict(row)
            data["message"] = decrypt_data(data["message"])
            messages.append(data)
    return messages[::-1]

def add_handover(author: str, content: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO handover_notes (timestamp, author, content) VALUES (?, ?, ?)",
            (timestamp, author, encrypt_data(content))
        )
        conn.commit()

def get_handovers(limit: int = 50):
    handovers = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM handover_notes ORDER BY timestamp DESC LIMIT ?", (limit,))
        for row in cursor.fetchall():
            data = dict(row)
            data["content"] = decrypt_data(data["content"])
            handovers.append(data)
    return handovers
