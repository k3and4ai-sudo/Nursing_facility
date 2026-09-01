import os
from cryptography.fernet import Fernet

# Project Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nursing_facility.db")
AUDIO_DIR = os.path.join(BASE_DIR, "audio_temp")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Ollama settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:2b")
# By default, use the main model for embeddings, or nomic-embed-text for high performance
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "gemma2:2b")

# Speech Processing
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", "tiny")  # "small", "base", "medium" etc.
TTS_ENGINE = os.getenv("TTS_ENGINE", "gtts")  # "gtts" or "local" (mock/system)

# Gemini API / Gemini Live Settings (Debug Mode)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Release Flag: Set ENABLE_DEBUG_MODE=false in production to completely abolish debug features
ENABLE_DEBUG_MODE = os.getenv("ENABLE_DEBUG_MODE", "true").lower() == "true"

# Vital Sign Thresholds (Alert limits)
TEMP_MIN = 35.0
TEMP_MAX = 37.5
BP_SYS_MIN = 90
BP_SYS_MAX = 140
BP_DIA_MIN = 50
BP_DIA_MAX = 90
WEIGHT_MIN = 30.0
WEIGHT_MAX = 150.0

# Database Encryption Key Setup
# Save key to a file so it persists between restarts
KEY_FILE = os.path.join(BASE_DIR, ".enc_key")
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "rb") as f:
        ENCRYPTION_KEY = f.read()
else:
    ENCRYPTION_KEY = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(ENCRYPTION_KEY)

cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_data(data: str) -> str:
    """Encrypts string data using Fernet symmetric encryption."""
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode("utf-8")).decode("utf-8")

def decrypt_data(token: str) -> str:
    """Decrypts token back to string data."""
    if not token:
        return ""
    try:
        return cipher_suite.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return "[Decryption Error]"
