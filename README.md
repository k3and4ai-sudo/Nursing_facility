# Nursing Facility AI アシスタント管理システム

介護施設向けのAIアシスタントを活用した統合管理システムです。  
音声対話・バイタルサイン記録・申し送り管理などをブラウザだけで完結できます。

---

## 📋 主な機能

| 機能 | 説明 |
|---|---|
| 🎙️ 音声対話 | Whisper による音声認識 + gTTS による読み上げ |
| 🤖 AI アシスタント | Ollama (gemma4) による自然言語応答 |
| 📊 バイタル管理 | 体温・血圧・体重の記録・アラート |
| 📝 申し送り | スタッフ間の引き継ぎ情報管理 |
| 👤 利用者管理 | 入居者情報・認知症レベルの管理 |
| 🔒 データ暗号化 | Fernet 暗号化によるDB保護 |

---

## 🗂️ プロジェクト構成

```
Nursing_facility/
├── pyproject.toml          # プロジェクト定義
├── .env.example            # 環境変数テンプレート
├── README.md               # このファイル
├── backend/
│   ├── main.py             # FastAPI アプリ本体
│   ├── config.py           # 設定・暗号化
│   ├── database.py         # SQLite DB 操作
│   ├── speech.py           # 音声処理 (Whisper / gTTS)
│   ├── rag.py              # RAG (検索拡張生成)
│   ├── vital_parser.py     # バイタルサイン解析
│   ├── requirements.txt    # 依存パッケージ
│   └── nursing_facility.db # SQLite データベース
└── frontend/
    ├── staff/              # スタッフ向けUI
    │   ├── index.html
    │   ├── app.js
    │   └── style.css
    └── user/               # 利用者・家族向けUI
        ├── index.html
        ├── app.js
        ├── style.css
        └── wav_encoder.js  # 音声録音エンコーダー
```

---

## 🚀 セットアップ

### 1. 前提条件

- Python 3.12 以上
- [Ollama](https://ollama.com) がローカルで起動済み
- `gemma4:26b` モデルがダウンロード済み

```bash
# Ollama モデルのダウンロード
ollama pull gemma4:26b
```

### 2. 仮想環境の作成と依存インストール

```bash
# 仮想環境を作成
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージをインストール
pip install -r backend/requirements.txt
```

### 3. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して必要に応じて設定を変更
```

### 4. サーバーの起動

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 アクセス

| 画面 | URL |
|---|---|
| API ドキュメント | http://localhost:8000/docs |
| スタッフ画面 | http://localhost:8000/staff/ |
| 利用者・家族画面 | http://localhost:8000/user/ |

---

## ⚙️ 環境変数

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama サーバーURL |
| `OLLAMA_MODEL` | `gemma4:26b` | 使用するLLMモデル |
| `OLLAMA_EMBED_MODEL` | `gemma4:26b` | 埋め込みモデル |
| `WHISPER_MODEL_NAME` | `tiny` | Whisper モデルサイズ |
| `TTS_ENGINE` | `gtts` | TTSエンジン |

---

## 🧪 テスト

```bash
source .venv/bin/activate
pytest backend/test_backend.py -v
```

---

## 📄 ライセンス

MIT License
