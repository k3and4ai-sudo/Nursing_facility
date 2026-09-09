import os
import io
import wave
import ctypes
import numpy as np
from backend.config import WHISPER_BACKEND, WHISPER_MODEL_NAME, WHISPER_COMPUTE_TYPE, TTS_ENGINE, AUDIO_DIR

# Ensure libcublas.so.12 is found for CTranslate2 (faster-whisper)
def _ensure_cublas_loaded():
    candidates = [
        "/usr/local/lib/ollama/cuda_v12/libcublas.so.12",
        "/usr/local/lib/ollama/cuda_v13/libcublas.so.13",
        "/usr/local/cuda-13.0/targets/x86_64-linux/lib/libcublas.so.13",
        "/usr/lib/x86_64-linux-gnu/libcublas.so.12"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
                break
            except Exception:
                pass

_ensure_cublas_loaded()

# Lazy load whisper to speed up startup
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if WHISPER_BACKEND == "faster-whisper":
            try:
                from faster_whisper import WhisperModel
                compute_type = WHISPER_COMPUTE_TYPE if device == "cuda" else "int8"
                print(f"Loading faster-whisper model '{WHISPER_MODEL_NAME}' ({compute_type}) on device '{device}'...")
                _whisper_model = WhisperModel(WHISPER_MODEL_NAME, device=device, compute_type=compute_type)
                print(f"faster-whisper model '{WHISPER_MODEL_NAME}' loaded successfully on {device}.")
                return _whisper_model
            except Exception as e:
                print(f"Failed to load faster-whisper ({e}), falling back to openai-whisper...")
        
        # Fallback to standard whisper
        import whisper
        print(f"Loading standard Whisper model '{WHISPER_MODEL_NAME}' on device '{device}'...")
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME, device=device)
        print(f"Standard Whisper model '{WHISPER_MODEL_NAME}' loaded successfully on {device}.")
    return _whisper_model

def decode_wav_to_float32(audio_bytes: bytes) -> np.ndarray:
    """
    Safely decodes single or concatenated WAV byte buffers to a 16kHz mono float32 numpy array.
    Strips embedded WAV headers if multiple WAV chunks were concatenated together.
    """
    if not audio_bytes:
        return np.array([], dtype=np.float32)
        
    chunks = []
    raw_pos = 0
    while True:
        riff_idx = audio_bytes.find(b'RIFF', raw_pos)
        if riff_idx == -1:
            break
        next_riff = audio_bytes.find(b'RIFF', riff_idx + 4)
        if next_riff == -1:
            wav_chunk = audio_bytes[riff_idx:]
            raw_pos = len(audio_bytes)
        else:
            wav_chunk = audio_bytes[riff_idx:next_riff]
            raw_pos = next_riff
            
        try:
            with wave.open(io.BytesIO(wav_chunk), 'rb') as wav_file:
                params = wav_file.getparams()
                n_channels, sampwidth, framerate, n_frames = params[:4]
                raw_data = wav_file.readframes(n_frames)
                
                if sampwidth == 2:
                    data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 1:
                    data = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                elif sampwidth == 4:
                    data = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    continue
                
                if n_channels > 1:
                    data = data.reshape(-1, n_channels).mean(axis=1)
                    
                if framerate != 16000:
                    new_length = int(len(data) * 16000 / framerate)
                    data = np.interp(
                        np.linspace(0, len(data) - 1, new_length),
                        np.arange(len(data)),
                        data
                    ).astype(np.float32)
                chunks.append(data)
        except Exception as e:
            print(f"Error parsing audio chunk: {e}")
            
    if not chunks:
        return np.array([], dtype=np.float32)
        
    return np.concatenate(chunks)

import re

def has_repetitive_loop(text: str) -> bool:
    """
    Detects Whisper hallucination loops (e.g. repeated phrase or word loops like '東京都市の東京都市の...').
    """
    if not text:
        return False
    cleaned = re.sub(r'[\s、,。!！?？]+', '', text)
    if len(cleaned) < 6:
        return False
    # Check for short patterns (2 chars repeated >= 4 times: e.g. トントントントン)
    if re.search(r'(.{2}?)\1{3,}', cleaned):
        return True
    # Check for patterns of 3 to 25 chars repeated >= 3 times: e.g. 東京都市東京都市東京都市
    if re.search(r'(.{3,25}?)\1{2,}', cleaned):
        return True
    return False

def is_japanese_speech(text: str) -> bool:
    """
    Validates if transcribed text is valid Japanese speech and filters out Whisper hallucinations.
    """
    if not text:
        return False
    hallucination_blacklist = [
        "ご視聴", "チャンネル登録", "字幕", "amara.org", "bandits", "tässä", 
        "capacity", "ogels", "マキム", "チンコ", "http", "www", "ごらんくだ", "ご覧くだ"
    ]
    if any(black in text.lower() for black in hallucination_blacklist):
        return False

    # Check for repetitive loop hallucinations (e.g. '東京都市の東京都市の...')
    if has_repetitive_loop(text):
        return False
    
    # Filter out repetitive loop hallucinations (e.g., "お食事、散歩" or "散歩、散歩" repeated over and over)
    words = [w for w in re.split(r'[、,。\s]+', text) if w]
    if len(words) >= 4:
        from collections import Counter
        counts = Counter(words)
        most_common_count = counts.most_common(1)[0][1]
        if (most_common_count / len(words)) >= 0.35:
            return False
            
    jp_char_count = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
    total_len = len(text)
    if total_len == 0:
        return False
    
    if (jp_char_count / total_len) < 0.4:
        return False
        
    return True

def transcribe_numpy_array(audio_array: np.ndarray, initial_prompt: str = "介護施設での会話。") -> str:
    """
    Transcribes a 16kHz float32 mono numpy array using Faster-Whisper or standard Whisper.
    """
    if len(audio_array) == 0:
        return ""
    try:
        import torch
        model = get_whisper_model()
        
        # Audio energy check: if peak or RMS is near zero (silence), return empty
        if np.max(np.abs(audio_array)) < 0.015:
            return ""

        use_fp16 = torch.cuda.is_available()
        
        # Branch between faster-whisper and standard whisper
        if hasattr(model, "feature_extractor") and hasattr(model, "model"):
            # faster-whisper WhisperModel (CTranslate2) with VAD filter and repetition penalty
            segments, info = model.transcribe(
                audio_array,
                language="ja",
                initial_prompt=initial_prompt,
                beam_size=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
                condition_on_previous_text=False,
                no_speech_threshold=0.6
            )
            text = "".join(seg.text for seg in segments).strip()
        else:
            # standard openai-whisper
            result = model.transcribe(
                audio_array, 
                language="ja", 
                fp16=use_fp16,
                initial_prompt=initial_prompt,
                temperature=0.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False
            )
            text = result.get("text", "").strip()
        
        if not is_japanese_speech(text):
            print(f"Filtered out Whisper hallucinated text: '{text}'")
            return ""
            
        return text
    except Exception as e:
        print(f"Error during audio array transcription: {e}")
        return ""

def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes (WAV format) using Whisper on CUDA/CPU.
    """
    if not audio_bytes:
        return ""
    audio_array = decode_wav_to_float32(audio_bytes)
    return transcribe_numpy_array(audio_array)

import re

def remove_emojis(text: str) -> str:
    """
    Removes ONLY emojis without touching Japanese Kanji, Hiragana, or Katakana.
    """
    if not text:
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FAFF"  # extended symbols
        "\u2600-\u26FF"          # misc symbols
        "\u2700-\u27BF"          # dingbats
        "]+",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', text).strip()
    return cleaned if cleaned else text

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
