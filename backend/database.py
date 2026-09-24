import sqlite3
import json
import numpy as np
from datetime import datetime
from typing import Optional, List
from backend.config import DB_PATH, encrypt_data, decrypt_data
from backend.auth import hash_password, verify_password

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
                attention_points TEXT,             -- Encrypted (AI interaction notes)
                intercom_auto_answer INTEGER DEFAULT 1,     -- 1: Hands-free auto-answer, 0: Manual
                intercom_auto_delay INTEGER DEFAULT 15,     -- Delay in seconds before auto-answer (default 15s)
                allow_force_answer_staff INTEGER DEFAULT 1, -- Allow staff emergency force-answer
                allow_force_answer_family INTEGER DEFAULT 0, -- Allow family emergency force-answer
                gemini_api_key TEXT                         -- Encrypted custom Gemini API Key
            )
        """)

        # Migration: Ensure new columns exist for existing databases
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {col["name"] for col in cursor.fetchall()}
        if "intercom_auto_answer" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN intercom_auto_answer INTEGER DEFAULT 1")
        if "intercom_auto_delay" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN intercom_auto_delay INTEGER DEFAULT 15")
        if "allow_force_answer_staff" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN allow_force_answer_staff INTEGER DEFAULT 1")
        if "allow_force_answer_family" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN allow_force_answer_family INTEGER DEFAULT 0")
        if "gemini_api_key" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN gemini_api_key TEXT")
        
        # Upgrade existing <= 10s delay to 15s as requested by user
        cursor.execute("UPDATE users SET intercom_auto_delay = 15 WHERE intercom_auto_delay <= 10")
        conn.commit()
        
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
                heart_rate INTEGER,                -- Heart Rate in bpm (from Smartwatch)
                spo2 INTEGER,                      -- Blood Oxygen Saturation in % (from Smartwatch)
                steps INTEGER,                     -- Step count (from Smartwatch/Google Fit)
                source TEXT DEFAULT 'voice',       -- 'voice', 'smartwatch_ble', 'simulator', 'manual', 'google_fit'
                raw_text TEXT,                     -- Encrypted
                is_alert INTEGER DEFAULT 0,
                alert_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # Migration: Ensure new smartwatch columns exist for existing databases
        cursor.execute("PRAGMA table_info(vital_records)")
        existing_vital_cols = {col["name"] for col in cursor.fetchall()}
        if "heart_rate" not in existing_vital_cols:
            cursor.execute("ALTER TABLE vital_records ADD COLUMN heart_rate INTEGER")
        if "spo2" not in existing_vital_cols:
            cursor.execute("ALTER TABLE vital_records ADD COLUMN spo2 INTEGER")
        if "steps" not in existing_vital_cols:
            cursor.execute("ALTER TABLE vital_records ADD COLUMN steps INTEGER")
        if "source" not in existing_vital_cols:
            cursor.execute("ALTER TABLE vital_records ADD COLUMN source TEXT DEFAULT 'voice'")
        conn.commit()
        
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

        # 7. Groups table (Patient - Staff - Family bound group)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                patient_id INTEGER,
                FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # 8. User Accounts table (Auth & Role Management)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_code TEXT UNIQUE NOT NULL,    -- Login ID (e.g. staff01)
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,                -- 'patient', 'staff', 'family', 'barber'
                name TEXT NOT NULL,                -- Encrypted
                group_id INTEGER,
                terminal_id TEXT,
                FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE SET NULL
            )
        """)

        # 9. Barber Reservations table (訪問理美容)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barber_reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reservation_date TEXT NOT NULL,
                menu TEXT NOT NULL,
                notes TEXT,                        -- Encrypted
                status TEXT DEFAULT 'pending',     -- 'pending', 'completed'
                report TEXT,                       -- Encrypted
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # 10. Prompt Templates Library (プロンプト雛形)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        
        # 11. Visitation Reservations table (ご家族面会予約)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visitation_reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                family_user_code TEXT NOT NULL,
                visit_datetime TEXT NOT NULL,
                visitors_count INTEGER DEFAULT 1,
                message TEXT,                      -- Encrypted
                status TEXT DEFAULT 'pending',     -- 'pending', 'confirmed', 'cancelled'
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # 12. Generated Image & Postcard Prompts table (画像生成・絵手紙メタデータ)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_image_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                terminal_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                theme TEXT,
                season TEXT,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # 13. Schedules table (居住者予定・スケジュール管理)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,              -- YYYY-MM-DD
                time TEXT NOT NULL,              -- HH:MM
                title TEXT NOT NULL,             -- 例: リハビリ・機能訓練、入浴、訪問理美容、ご家族面会
                category TEXT DEFAULT 'general', -- rehab, bath, barber, visit, meal, medication, event, other
                location TEXT,                   -- 例: 機能訓練室、居室、浴室、1Fラウンジ
                notes TEXT,                      -- 詳細・連絡事項
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()

    # Seed default accounts and data if needed
    seed_default_accounts()

def seed_default_accounts():
    """Seeds default demo accounts for testing each role."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_accounts")
        count = cursor.fetchone()[0]
        if count == 0:
            # 1. Create a default patient and group
            cursor.execute(
                "INSERT INTO users (name, age, room_number, terminal_id, dementia_level, notes, attention_points) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (encrypt_data("山田 太郎"), 85, "101", "user_tablet_1", "mild", encrypt_data("要見守り"), encrypt_data("優しく傾聴"))
            )
            patient_id = cursor.lastrowid
            
            cursor.execute("INSERT INTO groups (group_name, patient_id) VALUES (?, ?)", ("山田様ケアグループ", patient_id))
            group_id = cursor.lastrowid

            # Default demo accounts
            accounts = [
                ("staff01", "staff123", "staff", "看護師 田中", group_id, None),
                ("patient01", "patient123", "patient", "山田 太郎", group_id, "user_tablet_1"),
                ("family01", "family123", "family", "山田 花子 (ご長女)", group_id, None),
                ("barber01", "barber123", "barber", "訪問理容 鈴木", group_id, None)
            ]

            for user_code, password, role, name, g_id, t_id in accounts:
                pwd_hash, salt = hash_password(password)
                cursor.execute(
                    """INSERT INTO user_accounts (user_code, password_hash, salt, role, name, group_id, terminal_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_code, pwd_hash, salt, role, encrypt_data(name), g_id, t_id)
                )
            
            # Seed default barber reservation
            cursor.execute(
                """INSERT INTO barber_reservations (user_id, reservation_date, menu, notes, status, report)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    patient_id,
                    "2026-08-28 14:00",
                    "カット・顔剃り",
                    encrypt_data("首を後ろに傾けるのが困難。洗髪時の声かけ要。"),
                    "pending",
                    encrypt_data("")
                )
            )

            conn.commit()
            print("Default demo user accounts and barber reservation seeded successfully.")

        # Seed Prompt Templates if prompt_templates table is empty
        cursor.execute("SELECT COUNT(*) FROM prompt_templates")
        if cursor.fetchone()[0] == 0:
            templates = [
                (
                    "template_listening",
                    "🌸 受容・傾聴テンプレート (認知症・不穏対応)",
                    "あなたは優しく落ち着いた介護スタッフです。利用者の話を途中で遮らず、すべて肯定的に「そうなんですね」「お気持ち分かりますよ」と受け止めてください。否定や訂正は一切せず、安心感を与える対話を行ってください。",
                    "認知症ケア"
                ),
                (
                    "template_reminiscence",
                    "📻 回想療法・昔話テンプレート (昭和レトロ)",
                    "あなたは昭和の時代や昔の暮らしに詳しい温かい話し相手です。「昔はどんなお仕事をされていたのですか？」「故郷の美味しい食べ物は何でしたか？」など、利用者が嬉しそうに語れる思い出を優しく引き出してください。",
                    "回想療法"
                ),
                (
                    "template_activity",
                    "☀️ 意欲向上・アクティビティテンプレート (運動・散歩案内)",
                    "あなたは明るく元気な健康アドバイザーです。今日の体調を気遣いながら、「今日はお天気が良いので少しお庭を歩きませんか？」とお話しし、散歩や運動・水分補給を優しく前向きに促してください。",
                    "アクティビティ"
                ),
                (
                    "template_sunset",
                    "🌇 夕暮れ症候群・帰宅願望対応テンプレート (不安軽減)",
                    "あなたは安心感を提供する見守り手です。「家に帰りたい」という訴えに「帰れません」と否定せず、「心配ですね。もうすぐスタッフがお茶を持ってきますから、少しここでお話しして待ちましょうね」と気持ちを受け止めて落ち着かせてください。",
                    "不穏・帰宅願望"
                )
            ]
            for key_name, title, content, category in templates:
                cursor.execute(
                    "INSERT INTO prompt_templates (key_name, title, content, category) VALUES (?, ?, ?, ?)",
                    (key_name, title, content, category)
                )
            conn.commit()

        # Seed sample visitation reservation if empty
        cursor.execute("SELECT COUNT(*) FROM visitation_reservations")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT id FROM users LIMIT 1")
            first_user = cursor.fetchone()
            if first_user:
                cursor.execute(
                    """INSERT INTO visitation_reservations (user_id, family_user_code, visit_datetime, visitors_count, message, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        first_user["id"],
                        "family01",
                        "2026-09-10 14:00",
                        2,
                        encrypt_data("長女と孫の2名で面会に伺います。お茶菓子を持参予定です。"),
                        "confirmed",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )
                conn.commit()

        # Seed default schedules if empty for users
        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT id FROM users")
        all_users = cursor.fetchall()
        for u in all_users:
            cursor.execute("SELECT COUNT(*) FROM schedules WHERE user_id = ?", (u["id"],))
            if cursor.fetchone()[0] == 0:
                sample_schedules = [
                    (u["id"], today_str, "09:30", "朝の体操・水分補給", "general", "デイルーム", "軽めのストレッチと健康チェック"),
                    (u["id"], today_str, "10:30", "リハビリ・機能訓練", "rehab", "機能訓練室", "歩行訓練・理学療法士担当"),
                    (u["id"], today_str, "12:00", "ご昼食（秋の味覚御膳）", "meal", "食堂", "管理栄養士特製メニュー"),
                    (u["id"], today_str, "14:00", "訪問理美容（ヘアカット）", "barber", "1F理美容室", "訪問理容 鈴木様担当"),
                    (u["id"], today_str, "15:00", "おやつとお茶の時間", "meal", "デイルーム", "温かい緑茶と季節の和菓子"),
                    (u["id"], today_str, "16:00", "ご家族面会（長女・花子様）", "visit", "居室・オンライン", "長女花子様とオンライン面会予定")
                ]
                for u_id, s_date, s_time, s_title, s_cat, s_loc, s_notes in sample_schedules:
                    cursor.execute(
                        """INSERT INTO schedules (user_id, date, time, title, category, location, notes, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (u_id, s_date, s_time, s_title, s_cat, s_loc, s_notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                conn.commit()

# Group Management
def add_group(group_name: str, patient_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO groups (group_name, patient_id) VALUES (?, ?)", (group_name, patient_id))
        conn.commit()
        return cursor.lastrowid

def get_group(group_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# User Account Management
def add_user_account(user_code: str, password: str, role: str, name: str, group_id: int = None, terminal_id: str = None):
    pwd_hash, salt = hash_password(password)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_accounts (user_code, password_hash, salt, role, name, group_id, terminal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_code, pwd_hash, salt, role, encrypt_data(name), group_id, terminal_id)
        )
        conn.commit()
        return cursor.lastrowid

def authenticate_user_account(user_code: str, password: str):
    """Authenticates a user_code and password. Returns user dict or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_accounts WHERE user_code = ?", (user_code,))
        row = cursor.fetchone()
        if not row:
            return None
        
        user_dict = dict(row)
        if verify_password(password, user_dict["password_hash"], user_dict["salt"]):
            user_dict["name"] = decrypt_data(user_dict["name"])
            del user_dict["password_hash"]
            del user_dict["salt"]
            return user_dict
    return None

def get_user_account_by_code(user_code: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_accounts WHERE user_code = ?", (user_code,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["name"] = decrypt_data(data["name"])
            del data["password_hash"]
            del data["salt"]
            return data
    return None

# Original User (Patient) Functions
def _format_user_row(row):
    if not row:
        return None
    data = dict(row)
    data["name"] = decrypt_data(data["name"])
    data["notes"] = decrypt_data(data["notes"])
    data["attention_points"] = decrypt_data(data["attention_points"])
    # Intercom settings default fallbacks
    data["intercom_auto_answer"] = 1 if data.get("intercom_auto_answer") is None else int(data["intercom_auto_answer"])
    data["intercom_auto_delay"] = 15 if data.get("intercom_auto_delay") is None else int(data["intercom_auto_delay"])
    data["allow_force_answer_staff"] = 1 if data.get("allow_force_answer_staff") is None else int(data["allow_force_answer_staff"])
    data["allow_force_answer_family"] = 0 if data.get("allow_force_answer_family") is None else int(data["allow_force_answer_family"])
    # Custom Gemini API Key decryption
    raw_api_key = data.get("gemini_api_key")
    if raw_api_key:
        try:
            data["gemini_api_key"] = decrypt_data(raw_api_key)
        except Exception:
            data["gemini_api_key"] = None
    else:
        data["gemini_api_key"] = None
    return data

def add_user(name: str, age: int, room_number: str, terminal_id: str, dementia_level: str, notes: str, attention_points: str,
             intercom_auto_answer: int = 1, intercom_auto_delay: int = 15,
             allow_force_answer_staff: int = 1, allow_force_answer_family: int = 0,
             gemini_api_key: Optional[str] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        enc_api_key = encrypt_data(gemini_api_key.strip()) if gemini_api_key and gemini_api_key.strip() else None
        cursor.execute(
            """INSERT INTO users (name, age, room_number, terminal_id, dementia_level, notes, attention_points,
                                  intercom_auto_answer, intercom_auto_delay, allow_force_answer_staff, allow_force_answer_family,
                                  gemini_api_key) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                encrypt_data(notes), encrypt_data(attention_points),
                intercom_auto_answer, intercom_auto_delay, allow_force_answer_staff, allow_force_answer_family,
                enc_api_key
            )
        )
        conn.commit()
        return cursor.lastrowid

def update_user(user_id: int, name: str, age: int, room_number: str, terminal_id: str, dementia_level: str, notes: str, attention_points: str,
                intercom_auto_answer: int = 1, intercom_auto_delay: int = 15,
                allow_force_answer_staff: int = 1, allow_force_answer_family: int = 0,
                gemini_api_key: Optional[str] = None, clear_gemini_api_key: bool = False):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if clear_gemini_api_key:
            cursor.execute(
                """UPDATE users 
                   SET name = ?, age = ?, room_number = ?, terminal_id = ?, dementia_level = ?, notes = ?, attention_points = ?,
                       intercom_auto_answer = ?, intercom_auto_delay = ?, allow_force_answer_staff = ?, allow_force_answer_family = ?,
                       gemini_api_key = NULL
                   WHERE id = ?""",
                (
                    encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                    encrypt_data(notes), encrypt_data(attention_points),
                    intercom_auto_answer, intercom_auto_delay, allow_force_answer_staff, allow_force_answer_family,
                    user_id
                )
            )
        elif gemini_api_key is not None and gemini_api_key.strip() != "":
            cursor.execute(
                """UPDATE users 
                   SET name = ?, age = ?, room_number = ?, terminal_id = ?, dementia_level = ?, notes = ?, attention_points = ?,
                       intercom_auto_answer = ?, intercom_auto_delay = ?, allow_force_answer_staff = ?, allow_force_answer_family = ?,
                       gemini_api_key = ?
                   WHERE id = ?""",
                (
                    encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                    encrypt_data(notes), encrypt_data(attention_points),
                    intercom_auto_answer, intercom_auto_delay, allow_force_answer_staff, allow_force_answer_family,
                    encrypt_data(gemini_api_key.strip()),
                    user_id
                )
            )
        else:
            # Keep existing key if not provided or empty string without clear flag
            cursor.execute(
                """UPDATE users 
                   SET name = ?, age = ?, room_number = ?, terminal_id = ?, dementia_level = ?, notes = ?, attention_points = ?,
                       intercom_auto_answer = ?, intercom_auto_delay = ?, allow_force_answer_staff = ?, allow_force_answer_family = ?
                   WHERE id = ?""",
                (
                    encrypt_data(name), age, room_number, terminal_id, dementia_level, 
                    encrypt_data(notes), encrypt_data(attention_points),
                    intercom_auto_answer, intercom_auto_delay, allow_force_answer_staff, allow_force_answer_family,
                    user_id
                )
            )
        conn.commit()

def get_user(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return _format_user_row(row)

def get_user_by_terminal(terminal_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE terminal_id = ?", (terminal_id,))
        row = cursor.fetchone()
        return _format_user_row(row)

def get_all_users():
    users = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        for row in cursor.fetchall():
            users.append(_format_user_row(row))
    return users

def delete_user(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

# Vital Records Functions
def add_vital_record(
    user_id: int,
    temperature: Optional[float] = None,
    weight: Optional[float] = None,
    bp_sys: Optional[int] = None,
    bp_dia: Optional[int] = None,
    raw_text: str = "",
    is_alert: int = 0,
    alert_reason: str = "",
    heart_rate: Optional[int] = None,
    spo2: Optional[int] = None,
    steps: Optional[int] = None,
    source: str = "voice"
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            """INSERT INTO vital_records (user_id, timestamp, temperature, weight, bp_sys, bp_dia, heart_rate, spo2, steps, source, raw_text, is_alert, alert_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, timestamp, temperature, weight, bp_sys, bp_dia, heart_rate, spo2, steps, source, encrypt_data(raw_text), is_alert, alert_reason)
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
    clean_msg = (message or "").strip()
    if not clean_msg:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check last message for same user to prevent duplicate greeting / spamming
        cursor.execute(
            "SELECT id, sender, message FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,)
        )
        last_row = cursor.fetchone()
        if last_row:
            try:
                last_id = last_row["id"]
                last_sender = last_row["sender"]
                last_msg = decrypt_data(last_row["message"]).strip()
                # 1. Exact duplicate skip
                if last_msg == clean_msg:
                    return None
                # 2. Duplicate AI greeting spam guard
                if sender == "ai" and last_sender == "ai":
                    if clean_msg.startswith("こんにちは") and last_msg.startswith("こんにちは"):
                        return None
                    if "元気ですか" in clean_msg and "元気ですか" in last_msg:
                        return None
                # 3. Partial chunk prefix guard (e.g. 'こんにちは、太郎さん様！お' vs full text)
                if sender == last_sender and (clean_msg.startswith(last_msg) or last_msg.startswith(clean_msg)):
                    if len(clean_msg) > len(last_msg):
                        cursor.execute(
                            "UPDATE chat_history SET message = ? WHERE id = ?",
                            (encrypt_data(clean_msg), last_id)
                        )
                        conn.commit()
                        return last_id
                    else:
                        return None
            except Exception:
                pass

        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
            (user_id, timestamp, sender, encrypt_data(clean_msg))
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

# Prompt Template Functions
def get_all_prompt_templates():
    templates = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prompt_templates ORDER BY id ASC")
        for row in cursor.fetchall():
            templates.append(dict(row))
    return templates

def update_prompt_template(key_name: str, content: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE prompt_templates SET content = ? WHERE key_name = ?", (content, key_name))
        conn.commit()

# Barber Reservation Functions
def get_barber_reservations(limit: int = 50):
    reservations = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT r.*, u.name as user_name, u.room_number, u.dementia_level
               FROM barber_reservations r
               JOIN users u ON r.user_id = u.id
               ORDER BY r.reservation_date ASC LIMIT ?""",
            (limit,)
        )
        for row in cursor.fetchall():
            data = dict(row)
            data["user_name"] = decrypt_data(data["user_name"])
            data["notes"] = decrypt_data(data["notes"])
            data["report"] = decrypt_data(data["report"])
            reservations.append(data)
    return reservations

def add_barber_reservation(user_id: int, reservation_date: str, menu: str, notes: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO barber_reservations (user_id, reservation_date, menu, notes, status, report)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, reservation_date, menu, encrypt_data(notes), "pending", encrypt_data(""))
        )
        conn.commit()
        return cursor.lastrowid

def update_barber_report(reservation_id: int, status: str, report: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE barber_reservations SET status = ?, report = ? WHERE id = ?",
            (status, encrypt_data(report), reservation_id)
        )
        conn.commit()

# Access Control Functions
def check_group_access(account: dict, target_patient_id: int) -> bool:
    """Returns True if the user account is allowed to access data for target_patient_id."""
    if not account:
        return False
    role = account.get("role")
    if role in ["staff", "barber"]:
        return True  # Staff and Barber have facility-wide access
    if role == "family" or role == "patient":
        user_group_id = account.get("group_id")
        if not user_group_id:
            return False
        group = get_group(user_group_id)
        if group and group.get("patient_id") == target_patient_id:
            return True
    return False

# Visitation Reservation Functions (ご家族面会予約)
def create_visitation_reservation(user_id: int, family_user_code: str, visit_datetime: str, visitors_count: int = 1, message: str = "") -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO visitation_reservations (user_id, family_user_code, visit_datetime, visitors_count, message, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, family_user_code, visit_datetime, visitors_count, encrypt_data(message), "pending", created_at)
        )
        conn.commit()
        return cursor.lastrowid

def get_visitation_reservations(user_id: Optional[int] = None, limit: int = 50) -> list:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute(
                """SELECT r.id, r.user_id, r.family_user_code, r.visit_datetime, r.visitors_count, r.message, r.status, r.created_at, u.name as patient_name, u.room_number
                   FROM visitation_reservations r
                   JOIN users u ON r.user_id = u.id
                   WHERE r.user_id = ?
                   ORDER BY r.visit_datetime DESC
                   LIMIT ?""",
                (user_id, limit)
            )
        else:
            cursor.execute(
                """SELECT r.id, r.user_id, r.family_user_code, r.visit_datetime, r.visitors_count, r.message, r.status, r.created_at, u.name as patient_name, u.room_number
                   FROM visitation_reservations r
                   JOIN users u ON r.user_id = u.id
                   ORDER BY r.visit_datetime DESC
                   LIMIT ?""",
                (limit,)
            )
        rows = cursor.fetchall()
        reservations = []
        for row in rows:
            reservations.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "patient_name": decrypt_data(row["patient_name"]) if row["patient_name"] else "不明",
                "room_number": row["room_number"],
                "family_user_code": row["family_user_code"],
                "visit_datetime": row["visit_datetime"],
                "visitors_count": row["visitors_count"],
                "message": decrypt_data(row["message"]) if row["message"] else "",
                "status": row["status"],
                "created_at": row["created_at"]
            })
        return reservations

def update_visitation_status(reservation_id: int, status: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE visitation_reservations SET status = ? WHERE id = ?",
            (status, reservation_id)
        )
        conn.commit()

# Generated Image & Postcard Prompts Functions
def save_image_prompt_payload(user_id: int, terminal_id: str, payload: dict) -> int:
    """Saves structured image generation prompt and postcard metadata."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        theme = payload.get("theme", "")
        season = payload.get("season", "")
        cursor.execute(
            "INSERT INTO generated_image_prompts (user_id, terminal_id, timestamp, theme, season, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, terminal_id, timestamp, theme, season, json.dumps(payload, ensure_ascii=False))
        )
        conn.commit()
        return cursor.lastrowid

def get_latest_image_prompt_payload(terminal_id: str = None, user_id: int = None) -> Optional[dict]:
    """Retrieves the most recent structured image generation payload for a terminal or user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if terminal_id:
            cursor.execute(
                "SELECT * FROM generated_image_prompts WHERE terminal_id = ? ORDER BY id DESC LIMIT 1",
                (terminal_id,)
            )
        elif user_id:
            cursor.execute(
                "SELECT * FROM generated_image_prompts WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
        else:
            cursor.execute("SELECT * FROM generated_image_prompts ORDER BY id DESC LIMIT 1")
            
        row = cursor.fetchone()
        if not row:
            return None
            
        res = dict(row)
        try:
            res["payload"] = json.loads(res["payload_json"])
        except Exception:
            res["payload"] = {}
        return res

def get_multimedia_history(user_id: int = None, terminal_id: str = None, limit: int = 15) -> list:
    """
    Retrieves historical digital postcard and conversation summary payloads in descending order.
    """
    results = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                "SELECT * FROM generated_image_prompts WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
        elif terminal_id:
            cursor.execute(
                "SELECT * FROM generated_image_prompts WHERE terminal_id = ? ORDER BY id DESC LIMIT ?",
                (terminal_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM generated_image_prompts ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = cursor.fetchall()
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item["payload_json"])
            except Exception:
                item["payload"] = {}
            results.append(item)
    return results

# ==============================================================================
# Schedule Management (居住者予定・スケジュール管理)
# ==============================================================================

def add_schedule(user_id: int, date_str: str, time_str: str, title: str, category: str = "general", location: str = "", notes: str = "") -> int:
    """Adds a new schedule item for a resident."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO schedules (user_id, date, time, title, category, location, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, date_str, time_str, title, category, location, notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        return cursor.lastrowid

def get_schedules_by_user_and_date(user_id: int, date_str: str) -> List[dict]:
    """Fetches all schedules for a specific resident on a specific date (sorted by time ASC)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM schedules WHERE user_id = ? AND date = ? ORDER BY time ASC""",
            (user_id, date_str)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_upcoming_schedules(user_id: int, from_date: str = None, limit: int = 30) -> List[dict]:
    """Fetches upcoming schedules from a specified date onwards."""
    if not from_date:
        from_date = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM schedules WHERE user_id = ? AND date >= ? ORDER BY date ASC, time ASC LIMIT ?""",
            (user_id, from_date, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_all_schedules_by_user(user_id: int, limit: int = 50) -> List[dict]:
    """Fetches all schedules for a resident (most recent first)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM schedules WHERE user_id = ? ORDER BY date DESC, time DESC LIMIT ?""",
            (user_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def delete_schedule(schedule_id: int) -> bool:
    """Deletes a schedule item by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        conn.commit()
        return cursor.rowcount > 0

def update_schedule(schedule_id: int, date_str: str, time_str: str, title: str, category: str = "general", location: str = "", notes: str = "") -> bool:
    """Updates an existing schedule item."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE schedules 
               SET date = ?, time = ?, title = ?, category = ?, location = ?, notes = ?
               WHERE id = ?""",
            (date_str, time_str, title, category, location, notes, schedule_id)
        )
        conn.commit()
        return cursor.rowcount > 0



