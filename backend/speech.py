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
        # Using cpu or gpu automatically
        print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
        print("Whisper model loaded successfully.")
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
    Transcribes audio bytes (WAV format) using Whisper.
    """
    if not audio_bytes:
        return ""
    try:
        model = get_whisper_model()
        # Decode WAV to numpy array to bypass ffmpeg
        audio_array = decode_wav_to_float32(audio_bytes)
        
        # Transcribe with language set to Japanese
        result = model.transcribe(audio_array, language="ja", fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return "[音声認識エラー]"

def synthesize_speech(text: str) -> bytes:
    """
    Synthesizes text into speech audio bytes (MP3/WAV format).
    """
    if not text:
        return b""
    
    if TTS_ENGINE == "gtts":
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='ja')
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
