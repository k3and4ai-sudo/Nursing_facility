---
title: "Gemini Live API 統合実装・変更まとめレポート (2026-09-03)"
date: 2026-09-03
type: technical-report
project: Nursing_facility_Care-Link
status: completed
tags:
  - GeminiLive
  - BidiGenerateContent
  - FullDuplex
  - AutoHealing
  - CareLink
  - Obsidian
---

# 🚀 Gemini Live API 統合実装・最新改修仕様まとめ

> [!SUCCESS] **概要サマリー**
> 本ドキュメントは、Google Gemini Multimodal Live API (`BidiGenerateContent` WebSocket) を介護施設向けリアルタイム音声対話システム **Care-Link** へ組み込むにあたり、**完全全二重ストリーミング・超低遅延応答・自動自己修復セッション維持・UI連動**を達成するために実施した全技術的変更・改善内容を体系化した Obsidian 対応ナレッジノートです。

---

## 📌 1. 核心的なアーキテクチャ改善と変更点

### 1.1 ⚡ 完全全二重（Full-Duplex）連続パケット送出
- **従来の課題**: 
  再生中ミュートガード（`if (isPlayingPCM24) return;`）が存在していたため、AIの応答再生中にマイク音声パケットが遮断され、発話が手元で溜まっているように感じられる原因となっていた。
- **改善仕様**: 
  - マイクオン中は相手（Gemini Live）の状態や再生有無に関わらず、**16kHz Raw PCMパケット（base64）を100%リアルタイムで連続送出**。
  - セルフインターラプション（割り込み・話しかけ）を標準サポート。

### 1.2 🎙️ ハードウェア直結 RMS 音量 VAD による 0ms ランプ連動
- **従来の課題**: 
  ブラウザのテキスト認識API（Web Speech API）の文字確定を待ってから発話完了（EOS）を判定していたため、Chrome側の1〜2秒の遅延にひっぱられ、「考え中...」ランプが点灯せず応答も遅れてた。
- **改善仕様**: 
  - Web Audio API による入力音量レベル（RMS）の即時計算を導入。
  - 感度しきい値を `0.0015`（PC内蔵マイク・囁き声にも反応）に設定。
  - 発話検知時 ➔ 🎤 **「あなたの声」送信中**（エメラルドグリーン）が **0ms（即時）** で点灯。
  - 約 150〜200ms の無音ポーズ検知時 ➔ 🧠 **「Gemini考え中...」**（アンバーイエロー）が **即座** にパッと点灯し、無条件で Gemini Live へ発話完了シグナル（`turnComplete: true`）を送信。

### 1.3 🔄 接続切断防止・全自動自己修復（Auto-Healing）ルーチン
- **従来の課題**: 
  Google Gemini Live サーバーはターン完了後や一定時間後に WebSocket 接続を切断（Close）する仕様があり、切断後の発話時に `turnComplete` が順序エラーとなって会話がフリーズ・途切れていた。
- **改善仕様**: 
  - **背景自動自己修復（`_auto_reconnect`）**: Google側から切断された瞬間、バックグラウンドで 0.3 秒以内に自動再接続と `setup_frame` 送信を完了させ、常に「ホットスタンバイ状態」を維持。
  - **パケットロスゼロのキューイング (`pending_chunks`)**: 再接続中に送信されたPCMパケットはメモリキューに保持され、接続完了直後に自動一括送出。
  - **無条件 `turnComplete: true`**: テキスト情報が空（`""`）の場合でも、発話完了時には必ず `turnComplete: true` を送信し、Gemini Live が絶対に応答生成を開始するようデッドロックを排除。

### 1.4 🚫 二重応答（Ollama / REST API 衝突）の完全排除
- **従来の課題**: 
  発話文字起こしイベントに連動して、裏で HTTP REST API（Gemini 2.0 Flash）や Ollama / gTTS フォールバック処理が並行起動し、Gemini Liveのネイティブ音声と重複して応答が生成されていた。
- **改善仕様**: 
  - 並行応答生成処理 (`fetch_and_send_text_reply`) および Ollama フォールバック処理をコードから**完全削除**。
  - 対話エンジンを **Gemini Live (Bidi WebSocket) 単体** に一本化。

### 1.5 🛡️ PII ガードラッシュと字幕表示の分離
- **従来の課題**: 
  個人情報監視用の Whisper STT がスピーカーの返答音声を拾い、ハルシネーションテキスト（「ポッド高評価と回向を練習...」）を「あなたの声」ボックスに上書き出力していた。
- **改善仕様**: 
  - バックエンド Whisper STT からのテキスト出力 (`on_transcription`) を**完全遮断**。
  - 「あなたの声」は Chrome Web Speech API のみのローカル描画に限定し、無関係な文字化け表示をゼロ化。
  - PII検査間隔を 3.0 秒（96,000 bytes）に最適化し、CPU/GPUの不要な負荷を大幅削減。

---

## 🛠️ プロトコル＆通信フレーム定義

### 1. 接続 & 初期化セットアップ (`setup`)
```json
{
  "setup": {
    "model": "models/gemini-2.5-flash-native-audio-latest",
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "speechConfig": {
        "voiceConfig": {
          "prebuiltVoiceConfig": { "voiceName": "Puck" }
        }
      }
    },
    "systemInstruction": {
      "parts": [{ "text": "介護施設向けAIアシスタントの役割定義および直近の会話履歴文脈" }]
    }
  }
}
```

### 2. マイク音声リアルタイム送信 (`realtimeInput`)
```json
{
  "realtimeInput": {
    "mediaChunks": [
      {
        "mimeType": "audio/pcm;rate=16000",
        "data": "<Base64 encoded 16kHz PCM audio>"
      }
    ]
  }
}
```

### 3. 発話完了通知 (`clientContent` / EOS)
```json
{
  "clientContent": {
    "turns": [
      {
        "role": "user",
        "parts": [{ "text": "<認知的テキスト（任意）>" }]
      }
    ],
    "turnComplete": true
  }
}
```

---

## 📂 主要変更コードファイル一覧

| ファイルパス | 役割・主な改修内容 |
|---|---|
| [backend/gemini_live.py](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/gemini_live.py) | Gemini Live WebSocket セッション管理、`_auto_reconnect` 自己修復、`pending_chunks` キュー、`turnComplete` 無条件送信 |
| [backend/main.py](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/main.py) | `/ws/user/{terminal_id}/live` エンドポイント。重複REST/Ollama生成の削除、`add_pcm_chunk_sync` 同期化 |
| [frontend/user/app.js](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/frontend/user/app.js) | Web Audio RMS音量VAD (しきい値 `0.0015`), 150msポーズ検知, カプセルボタン発光制御, 重複TTS呼び出し削除 |
| [frontend/user/style.css](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/frontend/user/style.css) | 3ステータスランプ（`lamp-sending`, `lamp-thinking`, `lamp-speaking`）のフル発光・パルスアニメーション |

---

*作成日時: 2026-09-03*  
*対象システム: Care-Link Nursing Facility Management System*  
