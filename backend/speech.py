import os
import io
import wave
import numpy as np
from backend.config import WHISPER_MODEL_NAME, TTS_ENGINE, AUDIO_DIR

# Lazy load whisper to speed up startup
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading Whisper model '{WHISPER_MODEL_NAME}' on device '{device}'...")
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME, device=device)
        print(f"Whisper model '{WHISPER_MODEL_NAME}' loaded successfully on {device}.")
    return _whisper_model

def decode_wav_to_float32(audio_bytes: bytes) -> np.ndarray:
    """
    Decodes raw WAV bytes to a 16kHz mono float32 numpy array.
    This bypasses Whisper's internal ffmpeg dependency.
    """
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        params = wav_file.getparams()
        n_channels, sampwidth, framerate, n_frames = params[:4]
        raw_data = wav_file.readframes(n_frames)
        
        # Convert buffer to numpy array
        if sampwidth == 2:
            data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 1:
            data = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif sampwidth == 4:
            data = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")
        
        # Convert to mono if stereo by averaging channels
        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)
            
        # Resample to 16000Hz (Whisper's required sampling rate)
        if framerate != 16000:
            new_length = int(len(data) * 16000 / framerate)
            # Linear interpolation resampling
            data = np.interp(
                np.linspace(0, len(data) - 1, new_length),
                np.arange(len(data)),
                data
            ).astype(np.float32)
            
        return data

def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes (WAV format) using Whisper on CUDA/CPU.
    """
    if not audio_bytes:
        return ""
    try:
        import torch
        model = get_whisper_model()
        audio_array = decode_wav_to_float32(audio_bytes)
        
        use_fp16 = torch.cuda.is_available()
        initial_prompt = "介護施設の高齢者・利用者との日常会話。体温は36度5分、血圧は120の80、体重は50キロです。体調、食事、散歩。"
        result = model.transcribe(
            audio_array, 
            language="ja", 
            fp16=use_fp16,
            initial_prompt=initial_prompt
        )
        return result.get("text", "").strip()
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return "[音声認識エラー]"

import re

def remove_emojis(text: str) -> str:
    """
    Removes emojis, pictographs, and special symbols for clean TTS reading.
    """
    if not text:
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

def synthesize_speech(text: str) -> bytes:
    """
    Synthesizes text into speech audio bytes (MP3/WAV format) with emojis stripped.
    """
    if not text:
        return b""
    
    clean_text = remove_emojis(text)
    if not clean_text:
        clean_text = text
    
    if TTS_ENGINE == "gtts":
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='ja')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            return fp.getvalue()
        except Exception as e:
            print(f"gTTS failed (likely offline): {e}. Falling back to local offline generator.")
            # Fallback to local audio generator
            
    # Local fallback: Generate a simple WAV beep/tone or silent audio
    # to prevent application crashes and provide system robustness
    return generate_fallback_audio(text)

def generate_fallback_audio(text: str) -> bytes:
    """
    Generates a simple silent or synth WAV as a fallback when internet TTS is unavailable.
    """
    # Create a 0.5s soft beep tone indicating AI finished thinking but couldn't speak
    sample_rate = 16000
    duration = 0.5
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Simple sine wave (440Hz A4 note)
    sine_wave = np.sin(2 * np.pi * 440 * t) * 0.5
    
    # Save as WAV bytes
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Convert float32 to int16 PCM
        audio_data = (sine_wave * 32767).astype(np.int16)
        wav_file.writeframes(audio_data.tobytes())
        
    return wav_io.getvalue()
