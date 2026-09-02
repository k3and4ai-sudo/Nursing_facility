---
title: "Gemini Live API 実装変更点・技術仕様まとめ報告書 (Obsidian保管用)"
date: 2026-09-02
type: technical-report
project: Nursing_facility_Care-Link
status: completed
tags:
  - GeminiLive
  - MultimodalAPI
  - BidiStreaming
  - WebSockets
  - LowLatency
  - Architecture
  - Obsidian
  - Care-Link
---

# ⚡ Gemini Multimodal Live API 実装変更点・技術仕様まとめ報告書

> [!IMPORTANT] **ドキュメント概要**
> 本ドキュメントは、Care-Link 介護アシスタントシステムにおける **Gemini Multimodal Live API (`BidiGenerateContent` WebSocket)** 導入に伴い実施した技術的変更点、アーキテクチャ最適化、不具合解消（マイクブロック・エコー自爆・タイムアウト・被りUI）の全内容を記録した Obsidian 用技術ノウハウ書です。

---

## 📊 1. 変更前後の技術仕様比較

| 項目 | 🔴 従来の課題・動作 | 🟢 本日の変更・最適化仕様 |
|---|---|---|
| **マイク入力ゲート** | RMS `>= 0.015` の厳密な閾値制限でPC内蔵マイクの音声を全ブロック（無音・無回答） | **RMS制限を完全廃止**。マイクON中は16kHz Raw PCM音声を 100% 確実に WebSocket 送出 |
| **スピーカーエコー** | AIの回答音声をマイクが拾い、「あなたの声」に誤表示されAIが自己返答する無限ループ | **エコー防止ロック (`isAISpeaking`)** を導入。AI音声再生中はマイク認識を自動無視 |
| **WebSocket設定** | `["TEXT", "AUDIO"]` 指定時に Google 側から `Error 1007: Not Supported` で強制切断 | **`"responseModalities": ["AUDIO"]`**（ネイティブ音声単体）へ固定しセッション切断を防止 |
| **返答テキスト生成** | 音声単体モードで右側ボックス（「Gemini Liveからの返答」）にテキストが非表示 | 発話確定（`eos`）時にバックエンドからテキスト応答を**非同期・非ブロッキング**で生成・送信 |
| **ステータスランプ** | ランプが小さく認識困難。画面被りや順序遅延タイマーによるフリーズが発生 | **ボタン全域発光（全点滅）デザイン化**。人工タイマーを廃止し**完全非同期イベント駆動**化 |
| **セッション復旧** | 通信切断時（Quota Exceeded/Idle）に会話が突然ストップ | **自動再接続（Auto-Reconnect）ガード** を組み込み、次の発話時に即時復旧 |

---

## 🧬 2. Gemini Live API リアルタイム通信シーケンス

最新の完全非同期（Event-Driven）フルデュプレックス通信シーケンスです。

```mermaid
sequenceDiagram
    autonumber
    participant Client as 📱 利用者タブレット (app.js)
    participant FastAPI as 🛡️ 自社 backend (main.py)
    participant GeminiWS as ⚡ Gemini Live API (BidiWebSocket)
    participant GeminiFlash as 🤖 Gemini 2.0 Flash (REST)

    Note over Client, GeminiWS: 1. WebSocket 接続 & 初期化 (Setup)
    Client->>FastAPI: connectLiveWS() [ws://localhost:8000/ws/user/1/live]
    FastAPI->>GeminiWS: wss://generativelanguage.googleapis.com/.../BidiGenerateContent
    FastAPI->>GeminiWS: Setup Frame { model: "gemini-2.5-flash-native-audio-latest", responseModalities: ["AUDIO"] }

    rect rgb(235, 255, 235)
    Note over Client, GeminiWS: 2. マイク音声入力 ＆ ステータスランプ点灯
    loop 16kHz PCM Stream
        Client->>FastAPI: { type: "live_pcm_chunk", data: base64 }
        Client->>Client: setLiveLampState("sending") ➔ 🎤「あなたの声」送信中 (全点滅・緑)
        FastAPI->>GeminiWS: realtimeInput { mediaChunks: [{ mimeType: "audio/pcm;rate=16000", data: base64 }] }
    end
    end

    rect rgb(255, 250, 235)
    Note over Client, GeminiWS: 3. 発話確定 (EOS) ＆ ノンブロッキング並行処理
    Client->>FastAPI: { type: "eos", text: "こんにちは" }
    Client->>Client: setLiveLampState("thinking") ➔ 🧠 Gemini考え中... (全点滅・黄)
    
    par [非同期送信 A]
        FastAPI->>GeminiWS: clientContent { turns: [{ role: "user", parts: [{ text: "こんにちは" }] }], turnComplete: true }
    and [非同期送信 B]
        FastAPI->>GeminiFlash: generateContent ("こんにちは") ➔ 返答テキスト即時生成
        GeminiFlash-->>FastAPI: "こんにちは！今日もお元気ですか？"
        FastAPI-->>Client: { type: "live_response", text: "こんにちは！今日もお元気ですか？" }
        Client->>Client: #ai-response-box にテキスト更新
    end
    end

    rect rgb(235, 245, 255)
    Note over Client, GeminiWS: 4. 24kHz Native PCM 音声ストリーム受信 ＆ 再生
    GeminiWS-->>FastAPI: serverContent { modelTurn: { parts: [{ inlineData: { mimeType: "audio/pcm;rate=24000", data: base64 } }] } }
    FastAPI-->>Client: { type: "live_audio_output", sample_rate: 24000, data: base64 }
    Client->>Client: setLiveLampState("speaking") ➔ 🔊 Gemini応答中 (全点滅・青)
    Client->>Client: isAISpeaking = true (マイク音の自爆防止ロック)
    Client->>Client: playPCM24Chunk() スピーカー再生
    Client->>Client: 再生終了 ➔ isAISpeaking = false ➔ setLiveLampState("idle")
    end
```

---

## 🛠️ 3. 詳細な変更技術ポイント

### 3.1 RMSノイズゲート制限の撤廃 (`frontend/user/app.js`)
- **技術詳細**: 従来の `recorder.onChunkCallback` では、マイク入力音量の二乗平均平方根 (RMS) を計算し `rms >= 0.015` の場合のみパケットを送信していました。
- **課題**: PC内蔵マイク（特にノートPCやタブレット）では口元で話しても RMS が `0.005` 〜 `0.012` 程度にしかならず、音声データが1パケットも送信されない障害が発生していました。
- **対応**: RMSチェックを完全に削除し、マイクがONである限り全PCMパケットを無条件でリアルタイム送出するように変更。

### 3.2 アコースティック・エコー（自己発話誤認識）ロック (`app.js`)
- **技術詳細**: スピーカーから出力される Gemini の音声（またはTTS音声）をマイクがピックアップし、Web Speech API が「利用者の発話」として再認識してしまう問題。
- **対応**: 
  - フラグ `isAISpeaking` を導入。
  - `playPCM24Chunk()` および `playTTSVoice()` の再生開始時に `isAISpeaking = true` をセットし、`speechRec.onresult` 内で `if (isAISpeaking) return;` としてマイク認識結果を破棄。
  - 再生終了時に `300ms` の安全マージンを置いて `isAISpeaking = false` に復帰。

### 3.3 Gemini Live API `responseModalities` 設定とエラー 1007 の回避 (`backend/gemini_live.py`)
- **技術詳細**: `models/gemini-2.5-flash-native-audio-latest` の Bidi WebSocket 接続において、`"responseModalities": ["TEXT", "AUDIO"]` を指定すると、Googleサーバーより以下のエラーが返却され接続が切断されます。
  > `WebSocket connection closed (code=1007, reason='The requested combination of response modalities (AUDIO, TEXT) is not supported by the model.')`
- **対応**: `responseModalities` を `"AUDIO"`（音声単体）に固定。字幕表示用テキストは、バックエンド側で REST API（`gemini-2.0-flash`）を `asyncio.create_task` で非同期呼び出しして相補的に生成・表示するアーキテクチャを採用。

### 3.4 3ステータスランプのフル背景発光・全点灯システム (`frontend/user/style.css` & `index.html`)
- **レイアウト固定**:
  - `index.html` 内で `#status-lamps-bar` を `<footer class="footer">` 最上部に配置し、`display: flex !important; flex-direction: column !important;` を指定。メッセージボックスとの重なりを100%排除。
- **ボタン全域発光デザイン**:
  - 従来: 小さな14pxの丸ドットのみが点滅。
  - 変更後: カプセルボタン（文字背景全体）が色鮮やかなグラデーションで大きく全点灯・パルス発光。
  - 🎤 **「あなたの声」送信中**: エメラルドグリーン（`#10b981` ➔ `#059669`）
  - 🧠 **Gemini考え中...**: アンバーイエロー（`#f59e0b` ➔ `#d97706`）
  - 🔊 **Gemini応答中**: ロイヤルブルー（`#3b82f6` ➔ `#2563eb`）
- **ノンブロッキング非同期切替**:
  - 順序強制用タイマー（`setTimeout`）を撤廃し、WebSocket イベント受領と同時にノータイムで非同期切替。

---

## 📁 4. 変更ファイルおよび主要修正コードマップ

| 修正ファイル | 担当機能 | 関連主要コード・関数 |
|---|---|---|
| [backend/main.py](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/main.py) | WebSocket サーバー・ノンブロッキングEOS処理 | `websocket_user_live_endpoint`, `asyncio.create_task(session.send_end_of_turn)` |
| [backend/gemini_live.py](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/gemini_live.py) | Bidi WebSocket セッション・プロトコル管理 | `GeminiLiveSession.connect()`, `_receive_loop()`, `"responseModalities": ["AUDIO"]` |
| [frontend/user/index.html](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/frontend/user/index.html) | footer 内UIレイアウト構造化 | `<footer class="footer">`, `#status-lamps-bar` |
| [frontend/user/style.css](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/frontend/user/style.css) | 3ランプのフル背景発光＆パルスアニメーション | `.status-lamp`, `#lamp-sending.lamp-active`, `#lamp-thinking.lamp-active`, `#lamp-speaking.lamp-active` |
| [frontend/user/app.js](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/frontend/user/app.js) | 音声ストリーミング・エコーロック・イベント制御 | `isAISpeaking`, `playPCM24Chunk()`, `setLiveLampState()`, `speechRec.onresult` |

---

## 🔄 5. 今後の課題と次回再開手順 (Handover)

### ⚠️ 会話切断（セッション停止）の課題分析
特定のリクエスト（例：歌唱・音楽要求や長時間発話）時に、Google Bidi サーバーから以下のエラーが返却され WebSocket 接続が自動切断される場合があります。
- `code=1007: The audio content type (CONTENT_TYPE_AUDIO) is not supported`
- `code=1011: Quota Exceeded`

### 🚀 次回開発ステップ
1. **`gemini_live.py` 内への自動永続再接続ループの実装**
   - 接続切断を検知した際、バックグラウンドタスクで即座に新規 Bidi WebSocket セッションを透過的に再確立する永続ループを導入。
2. **コンテキスト（会話履歴）のセッション同期**
   - セッション再接続時でも会話の文脈が途切れないよう `setup` プロンプトへ直近メッセージ履歴を埋め込む処理の拡張。

---
*作成日時: 2026-09-02 17:28 (JST)*  
*作成者: Care-Link AI 開発チーム*
