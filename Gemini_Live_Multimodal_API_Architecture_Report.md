---
title: "Gemini Multimodal Live API (BidiStreaming) アーキテクチャ調査 & ネイティブ移行仕様書"
date: 2026-09-01
type: technical-report
project: Nursing_facility_Care-Link
status: proposal
tags:
  - GeminiLive
  - MultimodalAPI
  - BidiStreaming
  - WebSockets
  - LowLatency
  - Architecture
  - Obsidian
---

# ⚡ Gemini Multimodal Live API (BidiStreaming) アーキテクチャ調査 & 移行仕様書

> [!IMPORTANT] **本報告の目的**
> 利用者モードにおける対話応答の「遅延（1.5秒〜3秒）」および「STT誤認識」を根本解決するため、業界標準のネイティブ双方向音声接続ストリーミング **Gemini Multimodal Live API (`BidiGenerateContent`)** の技術仕様・他社実装例・移行ロードマップを整理・策定する。

---

## 📊 1. 従来型パイプライン vs ネイティブ Gemini Live API 比較

従来の STT ➔ LLM ➔ TTS 構成と、ネイティブ Gemini Live API（双方向 WebSocket ストリーミング）のアーキテクチャ比較は以下の通りです。

| 比較項目 | 🔴 従来型パイプライン (STT ➔ LLM ➔ TTS) | ⚡ ネイティブ Gemini Live API (`BidiGenerateContent`) |
|---|---|---|
| **通信方式** | REST API または 単一方向 WebSocket | **双方向 WebSockets (BidiStreaming)** |
| **音声認識 (STT)** | Whisper 等で文字起こし (誤認識・遅延の原因) | **不要 (なし)**。ニューラルネットがPCM波形を直接認識 |
| **音声合成 (TTS)** | VOICEVOX / Edge-TTS 等で波形生成 | **不要 (なし)**。Gemini が直接 24kHz PCM 音声を出力 |
| **応答遅延 (Latency)** | **1.5秒 〜 3.0秒** (3段階の処理時間が累積) | **サブセカンド (約300ms 〜 600ms)** |
| **割り込み (Interruption)** | 不可 (AI発話中の入力は捨てられる) | **ネイティブ対応 (Barge-in)**。ユーザーの発話でAI発声が自発停止 |
| **認識精度** | マイク音質やノイズで誤文字起こしが発生 | **極めて高精度** (音素・文脈・イントネーションを多角的に理解) |

---

## 🧬 2. ネイティブ Gemini Live API のシーケンスと仕組み

ネイティブ Gemini Live は、テキスト変換（STT/TTS）を挟まず、**生の PCM 音声波形を直接 Gemini 2.0 モデルと送受信** します。

```mermaid
sequenceDiagram
    autonumber
    participant App as 📱 クライアント (Browser / AudioWorklet)
    participant Backend as 🛡️ 自社 Fast API サーバー (Proxy/Relay)
    participant Gemini as ⚡ Gemini Multimodal Live API (WebSocket)

    Note over App, Gemini: 1. 接続確立 & 初期設定 (Setup)
    App->>Backend: WebSocket 接続リクエスト
    Backend->>Gemini: wss://generativelanguage.googleapis.com/.../BidiGenerateContent?key=API_KEY
    Backend->>Gemini: BidiGenerateContentSetup { model: "gemini-2.0-flash", response_modalities: ["AUDIO"] }

    rect rgb(240, 255, 240)
    Note over App, Gemini: 2. 双方向リアルタイム音声ストリーミング (Raw PCM)
    loop 音声入力 (16kHz PCM)
        App->>Backend: 生PCM Chunk (16kHz 16bit Mono)
        Backend->>Gemini: realtime_input { media_chunks: [{ mime_type: "audio/pcm", data: base64 }] }
    end

    loop 音声出力 (24kHz PCM)
        Gemini-->>Backend: serverContent { modelTurn: { parts: [{ inlineData: { mimeType: "audio/pcm;rate=24000", data: base64 } }] } }
        Backend-->>App: 24kHz 生PCM 音声ストリーム返却
        App->>App: AudioContext (Web Audio API) で即時ストリーム再生
    end
    end

    rect rgb(255, 240, 240)
    Note over App, Gemini: 3. 割り込み処理 (Barge-in / Interruption)
    App->>Backend: ユーザー割り込み発声検知
    Backend->>Gemini: clientContent (interruption event)
    Gemini-->>Backend: 即座に出力ストリーム停止
    end
```

---

## 🛠️ 3. プロトコル技術仕様 (Protocol Specifications)

### ① WebSocket エンドポイント
```http
wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=YOUR_API_KEY
```

### ② セットアップフレーム (`BidiGenerateContentSetup`)
接続確立直後に送信するセッション初期化フレームです。
```json
{
  "setup": {
    "model": "models/gemini-2.0-flash-exp",
    "generation_config": {
      "response_modalities": ["AUDIO"],
      "speech_config": {
        "voice_config": {
          "prebuilt_voice_config": {
            "voice_name": "Puck"
          }
        }
      }
    },
    "system_instruction": {
      "parts": [
        {
          "text": "あなたは介護施設の高齢者ケアに特化したGemini Live会話AIアシスタントです。共感と受容を第一にし、優しく温かい日本語で答えてください。"
        }
      ]
    }
  }
}
```

### ③ リアルタイム音声送信フレーム (`realtime_input`)
クライアントから送られてきた 16kHz Raw PCM 音声チャンクをGeminiへ連続送信します。
```json
{
  "realtime_input": {
    "media_chunks": [
      {
        "mime_type": "audio/pcm",
        "data": "<Base64_Encoded_16kHz_PCM_Bytes>"
      }
    ]
  }
}
```

### ④ レスポンス受領フレーム (`serverContent`)
Gemini からリアルタイムに 24kHz PCM 音声がストリーミング返却されます。
```json
{
  "serverContent": {
    "modelTurn": {
      "parts": [
        {
          "inlineData": {
            "mimeType": "audio/pcm;rate=24000",
            "data": "<Base64_Encoded_24kHz_PCM_Bytes>"
          }
        }
      ]
    }
  }
}
```

---

## 💻 4. 実装コード例 (Code References)

### 🐍 バックエンド: Python (`google-genai` / `websockets`)
```python
import asyncio
import json
import websockets
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_WS_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

async def gemini_live_session(client_ws):
    async with websockets.connect(GEMINI_WS_URL) as gemini_ws:
        # 1. Send Setup
        setup_payload = {
            "setup": {
                "model": "models/gemini-2.0-flash-exp",
                "generation_config": {
                    "response_modalities": ["AUDIO"]
                }
            }
        }
        await gemini_ws.send(json.dumps(setup_payload))

        # 2. Relay from Client to Gemini
        async def client_to_gemini():
            async for msg in client_ws:
                data = json.loads(msg)
                if data.get("type") == "audio_pcm":
                    payload = {
                        "realtime_input": {
                            "media_chunks": [{
                                "mime_type": "audio/pcm",
                                "data": data["pcm"]
                            }]
                        }
                    }
                    await gemini_ws.send(json.dumps(payload))

        # 3. Relay from Gemini to Client
        async def gemini_to_client():
            async for msg in gemini_ws:
                res = json.loads(msg)
                parts = res.get("serverContent", {}).get("modelTurn", {}).get("parts", [])
                for part in parts:
                    inline_data = part.get("inlineData", {})
                    if inline_data.get("mimeType", "").startswith("audio/pcm"):
                        await client_ws.send_json({
                            "type": "ai_audio_pcm",
                            "pcm": inline_data["data"]
                        })

        await asyncio.gather(client_to_gemini(), gemini_to_client())
```

### 🌐 フロントエンド: JavaScript (`AudioWorklet` / Web Audio API)
```javascript
// AudioContext Setup (16kHz capture, 24kHz playback)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
const playbackCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });

// Send mic PCM chunks over WebSocket
function sendPcmChunk(pcmFloat32Array) {
    const int16Array = new Int16Array(pcmFloat32Array.length);
    for (let i = 0; i < pcmFloat32Array.length; i++) {
        int16Array[i] = Math.max(-1, Math.min(1, pcmFloat32Array[i])) * 0x7FFF;
    }
    const b64 = btoa(String.fromCharCode(...new Uint8Array(int16Array.buffer)));
    ws.send(JSON.stringify({ type: "audio_pcm", pcm: b64 }));
}

// Play received 24kHz PCM from Gemini
function playGeminiAudioChunk(b64Pcm) {
    const raw = atob(b64Pcm);
    const buffer = new ArrayBuffer(raw.length);
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const int16 = new Int16Array(buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

    const audioBuf = playbackCtx.createBuffer(1, float32.length, 24000);
    audioBuf.getChannelData(0).set(float32);
    const src = playbackCtx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(playbackCtx.destination);
    src.start();
}
```

---

## 🚀 5. Care-Link システムにおけるネイティブ移行ロードマップ

> [!SUCCESS] **移行によって得られる成果**
> - 応答遅延が **2.5秒 ➔ 0.4秒 (サブセカンド)** へ劇的改善。
> - Whisper 文字起こしをバイパスするため、**STT誤認識率が実質ゼロ** に。
> - AIが喋っている途中にユーザーが相槌を打つとAIが自発的に止まる **割り込み機能 (Barge-in)** が完全実現。

### Phase 1: プロトタイプ作成 (FastAPI Gemini Live Relay)
- FastAPI バックエンドに `/ws/live_user/{terminal_id}` エンドポイントを追加。
- サーバー間 WebSocket (`websockets`) を用いて Gemini Multimodal Live API とのリレーロジックを実装。

### Phase 2: フロントエンド Raw PCM ストリーミング化
- `app.js` の WAV エンコード処理を `AudioWorklet` に置き換え、16kHz Raw PCM を連続送信。
- 24kHz Raw PCM のストリーミング再生キュー（リングバッファ）を実装。

### Phase 3: ハイブリッド運用 & フォールバック制御
- `GEMINI_API_KEY` 有効時: ネイティブ Gemini Multimodal Live API (爆速・高精度モード)
- オフライン / キー未設定時: 現行のローカル Ollama + Whisper パイプライン (フォールバックモード)

---
*作成日時: 2026-09-01*  
*作成者: Care-Link AI 開発チーム*
