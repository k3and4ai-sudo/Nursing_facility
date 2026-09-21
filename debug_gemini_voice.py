#!/usr/bin/env bash
# Wrapper to run debug_gemini_voice.py with .venv
""":"
exec .venv/bin/python "$0" "$@"
"""

import os
import sys
import time
import json
import asyncio
import base64
import wave
import subprocess
import argparse
import numpy as np
import websockets
from dotenv import load_dotenv

# Load .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
if not MODEL.startswith("models/"):
    MODEL = f"models/{MODEL}"

GEMINI_WS_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"

def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  🎙️  {title}")
    print("=" * 60)

def check_audio_devices():
    """Checks PipeWire / ALSA audio devices and prints input/output status."""
    print("[1] オーディオ入出力デバイスの確認中...")
    try:
        res = subprocess.run(["wpctl", "status"], capture_output=True, text=True, check=True)
        lines = res.stdout.split("\n")
        sources = []
        sinks = []
        in_sources = False
        in_sinks = False
        for l in lines:
            if "Sinks:" in l:
                in_sinks = True
                in_sources = False
                continue
            elif "Sources:" in l:
                in_sources = True
                in_sinks = False
                continue
            elif in_sinks and ("Sink endpoints:" in l or "Sources:" in l):
                in_sinks = False
            elif in_sources and ("Source endpoints:" in l or "Streams:" in l):
                in_sources = False

            if in_sinks and "*" in l:
                sinks.append(l.strip())
            if in_sources and "*" in l:
                sources.append(l.strip())

        if sources:
            print("  🎤 デフォルト・マイク入力 (Source):", sources[0])
        if sinks:
            print("  🔊 デフォルト・スピーカー出力 (Sink):", sinks[0])
    except Exception as e:
        print(f"  ⚠️ デバイス情報取得スキップ: {e}")

def record_microphone(duration_sec: float, output_wav: str) -> bool:
    """Records audio from default (mini-jack analog) mic using pw-record."""
    print(f"\n[2] 🎤 マイク録音を開始します（{duration_sec} 秒間、何か話しかけてください）...")
    print("    👉 例:「こんにちは！今日の調子はどうですか？」")
    
    cmd = [
        "pw-record",
        "--channels", "1",
        "--rate", "16000",
        "--format", "s16",
        output_wav
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(int(duration_sec)):
            remaining = int(duration_sec) - i
            print(f"    ⏺️ 録音中... 残り {remaining} 秒", end="\r", flush=True)
            time.sleep(1.0)
        time.sleep(duration_sec - int(duration_sec))
        proc.terminate()
        proc.wait(timeout=2.0)
        print("\n    ✅ 録音完了！")
    except Exception as e:
        print(f"    ❌ 録音エラー: {e}")
        return False

    # Check recorded audio stats
    try:
        with wave.open(output_wav, "rb") as wf:
            frames = wf.getnframes()
            data = wf.readframes(frames)
            samples = np.frombuffer(data, dtype=np.int16)
            max_amp = np.max(np.abs(samples))
            rms = np.sqrt(np.mean(samples.astype(float)**2))
            print(f"    📊 録音データ統計: サンプル数={frames} ({frames/16000:.2f}秒), 最大振幅={max_amp}, RMS音量={rms:.1f}")
            if max_amp < 100:
                print("    ⚠️ 注意: 音量が非常に小さい（ほぼ無音）です。マイク端子の差し込みや音量設定をご確認ください。")
    except Exception as e:
        print(f"    ⚠️ 統計解析エラー: {e}")

    return True

def play_audio(wav_path: str):
    """Plays 24kHz audio via pw-play or aplay."""
    print(f"\n[4] 🔊 スピーカーから Gemini 3.8 Live の返答音声を再生中...")
    try:
        subprocess.run(["pw-play", wav_path], check=True)
        print("    ✅ 音声再生完了！")
    except Exception:
        try:
            subprocess.run(["aplay", wav_path], check=True)
            print("    ✅ 音声再生完了 (aplay)！")
        except Exception as e:
            print(f"    ❌ 音声再生エラー: {e}")

async def run_gemini_session(wav_path: str = None, input_text: str = None):
    """Connects to Gemini 3.8 Live WebSocket, sends audio or text, streams response audio & text."""
    if not API_KEY:
        print("❌ GEMINI_API_KEY が設定されていません。.env を確認してください。")
        return

    print_header(f"Gemini 3.8 Live 接続テスト: {MODEL}")
    print(f"  モデル名: {MODEL}")
    print(f"  APIキー: {API_KEY[:6]}...{API_KEY[-4:] if len(API_KEY)>10 else '***'}")

    setup_frame = {
        "setup": {
            "model": MODEL,
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
                            "あなたの名前は「ジェムナイ」です。介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。"
                            "温かく優しく短い日本語（1〜2文）で相槌を打ちながら会話してください。"
                        )
                    }
                ]
            }
        }
    }

    print("\n[3] 🌐 Gemini 3.8 Live サーバーへ WebSocket 接続中...")
    async with websockets.connect(GEMINI_WS_URL) as ws:
        await ws.send(json.dumps(setup_frame))
        setup_resp = await ws.recv()
        setup_data = json.loads(setup_resp)
        if "setupComplete" in setup_data:
            print("    ✅ WebSocket 接続・Setup 成功！")
        else:
            print("    ⚠️ Setup レスポンス:", setup_data)

        # Send Input: either audio PCM or text prompt
        if wav_path and os.path.exists(wav_path):
            print("    📤 マイク音声（16kHz PCM）を Gemini 3.8 Live へストリーミング送信中...")
            with wave.open(wav_path, "rb") as wf:
                raw_pcm = wf.readframes(wf.getnframes())

            # Send in 100ms chunks (1600 samples = 3200 bytes)
            chunk_size = 3200
            for i in range(0, len(raw_pcm), chunk_size):
                chunk = raw_pcm[i:i+chunk_size]
                b64 = base64.b64encode(chunk).decode("utf-8")
                media_frame = {
                    "realtimeInput": {
                        "mediaChunks": [{"mimeType": "audio/pcm;rate=16000", "data": b64}]
                    }
                }
                await ws.send(json.dumps(media_frame))
                await asyncio.sleep(0.05)

            # Signal End-of-Turn
            print("    🛎️ 発話終了シグナル (turnComplete) を送信...")
            await ws.send(json.dumps({
                "clientContent": {
                    "turnComplete": True,
                    "turns": [{"role": "user", "parts": [{"text": "（利用者の音声発話）"}]}]
                }
            }))
        elif input_text:
            print(f"    📤 テキスト入力（テスト用）を送信中: 「{input_text}」...")
            await ws.send(json.dumps({
                "clientContent": {
                    "turnComplete": True,
                    "turns": [{"role": "user", "parts": [{"text": input_text}]}]
                }
            }))

        print("\n    📥 Gemini 3.8 Live からの応答を受信中...")
        collected_pcm24 = bytearray()
        received_text_parts = []
        start_time = time.time()
        first_audio_latency = None

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=12.0)
                data = json.loads(msg)

                if "error" in data:
                    print(f"    ❌ Gemini API エラー: {data['error']}")
                    break

                sc = data.get("serverContent", {})
                
                # Check for outputTranscription (Gemini 3.8 Live text output format)
                if "outputTranscription" in sc:
                    ot = sc["outputTranscription"]
                    if "text" in ot and ot["text"]:
                        t = ot["text"].strip()
                        received_text_parts.append(t)
                        print(f"    💬 [Gemini 3.8 テキスト応答]: {t}")

                # Check for model audio stream
                if "modelTurn" in sc:
                    mt = sc["modelTurn"]
                    parts = mt.get("parts", [])
                    for p in parts:
                        if "inlineData" in p:
                            inline = p["inlineData"]
                            if "audio/pcm" in inline.get("mimeType", ""):
                                if first_audio_latency is None:
                                    first_audio_latency = time.time() - start_time
                                    print(f"    ⚡ 初回音声受信レイテンシ: {first_audio_latency*1000:.1f} ms")
                                raw_chunk = base64.b64decode(inline["data"])
                                collected_pcm24.extend(raw_chunk)

                if sc.get("turnComplete"):
                    print(f"    🏁 応答生成完了（合計音声サイズ: {len(collected_pcm24)} バイト, 約 {len(collected_pcm24)/48000:.2f} 秒）")
                    break
            except asyncio.TimeoutError:
                print("    ⌛ 受信タイムアウト (12秒経過)")
                break

    if not collected_pcm24:
        print("    ❌ 返答音声を受信できませんでした。")
        return

    # Write received 24kHz PCM to output WAV file
    output_wav = "/tmp/gemini_response_24k.wav"
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(24000) # 24kHz
        wf.writeframes(bytes(collected_pcm24))

    # Play via speakers
    play_audio(output_wav)

def main():
    parser = argparse.ArgumentParser(description="Gemini 3.8 Live マイク＆スピーカー デバッグツール")
    parser.add_argument("--text", type=str, default=None, help="マイクを使わず指定テキストで直接Gemini 3.8に発話テスト")
    parser.add_argument("--duration", type=float, default=4.0, help="マイク録音時間（秒）デフォルト: 4.0")
    parser.add_argument("--check-devices-only", action="store_true", help="オーディオデバイスの確認のみ実行")
    args = parser.parse_args()

    print_header("Care-Link Gemini 3.8 Live 音声デバッグツール")
    check_audio_devices()

    if args.check_devices_only:
        return

    if args.text:
        # Direct text prompt test
        asyncio.run(run_gemini_session(input_text=args.text))
    else:
        # Microphone record & playback test
        mic_wav = "/tmp/debug_mic_input.wav"
        ok = record_microphone(args.duration, mic_wav)
        if ok:
            asyncio.run(run_gemini_session(wav_path=mic_wav))

if __name__ == "__main__":
    main()
